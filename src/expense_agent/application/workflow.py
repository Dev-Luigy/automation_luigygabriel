"""Auditable intake, extraction, and deterministic-policy orchestration."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from types import MappingProxyType
from typing import Protocol
from uuid import uuid4

from expense_agent.application.extraction import ReceiptExtractor
from expense_agent.application.review import ReviewCaseStatus, ReviewerIdentity, ReviewProblem
from expense_agent.domain import (
    AuditActor,
    AuditEvent,
    AutomatedDecision,
    BaselinePolicy,
    ExtractionResult,
    ExtractionStatus,
    HumanDecision,
    ModelInvocationTrace,
    PolicyDecisionRoute,
    ReceiptFacts,
    ReimbursementCase,
    ReimbursementStatus,
    ReimbursementSubmission,
)
from expense_agent.domain._validation import require_aware_datetime, require_non_blank
from expense_agent.domain.exceptions import DomainValidationError


class RequestNotFoundError(LookupError):
    """Raised when an exact all-status reimbursement lookup finds no request."""


class RequestConflictError(RuntimeError):
    """Raised when an idempotency key or processing transition conflicts."""


class ProcessingRunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class InvocationStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ProcessingRunSummary:
    processing_run_id: str
    run_number: int
    status: ProcessingRunStatus
    pipeline_version: str
    input_hash: str
    started_at: datetime
    completed_at: datetime | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("processing_run_id", "pipeline_version", "input_hash"):
            object.__setattr__(
                self,
                field_name,
                require_non_blank(getattr(self, field_name), field_name),
            )
        if not isinstance(self.run_number, int) or isinstance(self.run_number, bool):
            raise DomainValidationError("run_number must be an integer")
        if self.run_number < 1:
            raise DomainValidationError("run_number must be positive")
        if not isinstance(self.status, ProcessingRunStatus):
            raise DomainValidationError("status must be a ProcessingRunStatus")
        require_aware_datetime(self.started_at, "started_at")
        if self.completed_at is not None:
            require_aware_datetime(self.completed_at, "completed_at")
        if self.status is ProcessingRunStatus.RUNNING:
            if self.completed_at is not None or self.error is not None:
                raise DomainValidationError("a running processing run cannot be completed")
        elif self.completed_at is None:
            raise DomainValidationError("a terminal processing run requires completed_at")
        if self.status is ProcessingRunStatus.FAILED:
            object.__setattr__(self, "error", require_non_blank(self.error or "", "error"))
        elif self.error is not None:
            raise DomainValidationError("only a failed processing run may contain an error")


@dataclass(frozen=True, slots=True)
class InvocationSummary:
    """Safe invocation metadata; protected raw provider output is deliberately absent."""

    invocation_id: str
    processing_run_id: str
    stage: str
    attempt: int
    status: InvocationStatus
    provider: str
    model: str
    prompt_version: str
    prompt_hash: str
    input_hash: str
    invoked_at: datetime
    parameters: Mapping[str, str | int | float | bool | None] = field(default_factory=dict)
    output_hash: str | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "invocation_id",
            "processing_run_id",
            "stage",
            "provider",
            "model",
            "prompt_version",
            "prompt_hash",
            "input_hash",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_blank(getattr(self, field_name), field_name),
            )
        if not isinstance(self.attempt, int) or isinstance(self.attempt, bool) or self.attempt < 1:
            raise DomainValidationError("attempt must be a positive integer")
        if not isinstance(self.status, InvocationStatus):
            raise DomainValidationError("status must be an InvocationStatus")
        require_aware_datetime(self.invoked_at, "invoked_at")
        if self.completed_at is not None:
            require_aware_datetime(self.completed_at, "completed_at")
        if self.duration_ms is not None and (
            not isinstance(self.duration_ms, int)
            or isinstance(self.duration_ms, bool)
            or self.duration_ms < 0
        ):
            raise DomainValidationError("duration_ms must be a non-negative integer")
        if self.status is InvocationStatus.RUNNING:
            if any(
                value is not None
                for value in (self.output_hash, self.completed_at, self.duration_ms, self.error)
            ):
                raise DomainValidationError("a running invocation cannot contain a result")
        else:
            if self.completed_at is None or self.duration_ms is None or self.output_hash is None:
                raise DomainValidationError("a terminal invocation requires result metadata")
            object.__setattr__(
                self,
                "output_hash",
                require_non_blank(self.output_hash, "output_hash"),
            )
            if self.status is InvocationStatus.FAILED:
                object.__setattr__(self, "error", require_non_blank(self.error or "", "error"))
            elif self.error is not None:
                raise DomainValidationError("a successful invocation cannot contain an error")
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


@dataclass(frozen=True, slots=True)
class ExtractionSnapshot:
    """Reviewer-safe extraction result linked to one immutable invocation attempt."""

    status: ExtractionStatus
    facts: ReceiptFacts | None
    error: str | None
    invocation: InvocationSummary

    def __post_init__(self) -> None:
        if not isinstance(self.status, ExtractionStatus):
            raise DomainValidationError("status must be an ExtractionStatus")
        if not isinstance(self.invocation, InvocationSummary):
            raise DomainValidationError("invocation must be an InvocationSummary")
        if self.status is ExtractionStatus.SUCCEEDED:
            if self.facts is None or self.error is not None:
                raise DomainValidationError("a successful extraction requires facts only")
        elif self.facts is not None or not isinstance(self.error, str) or not self.error.strip():
            raise DomainValidationError("a failed extraction requires an error only")


@dataclass(frozen=True, slots=True)
class RequestResult:
    """Exact-ID, all-status projection safe for a normal application response."""

    submission: ReimbursementSubmission
    opened_at: datetime
    status: ReimbursementStatus
    version: int
    processing_run: ProcessingRunSummary | None = None
    extraction: ExtractionSnapshot | None = None
    automated_decision: AutomatedDecision | None = None
    problems: tuple[ReviewProblem, ...] = ()
    review_status: ReviewCaseStatus | None = None
    pending_since: datetime | None = None
    human_decision: HumanDecision | None = None
    reviewed_by: ReviewerIdentity | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.submission, ReimbursementSubmission):
            raise DomainValidationError("submission must be a ReimbursementSubmission")
        require_aware_datetime(self.opened_at, "opened_at")
        if not isinstance(self.status, ReimbursementStatus):
            raise DomainValidationError("status must be a ReimbursementStatus")
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise DomainValidationError("version must be a positive integer")
        object.__setattr__(self, "problems", tuple(self.problems))
        if not all(isinstance(problem, ReviewProblem) for problem in self.problems):
            raise DomainValidationError("problems must contain ReviewProblem values")
        if self.processing_run is not None and not isinstance(
            self.processing_run, ProcessingRunSummary
        ):
            raise DomainValidationError("processing_run must be a ProcessingRunSummary")
        if self.extraction is not None and not isinstance(self.extraction, ExtractionSnapshot):
            raise DomainValidationError("extraction must be an ExtractionSnapshot")
        if (
            self.automated_decision is not None
            and self.automated_decision.request_id != self.request_id
        ):
            raise DomainValidationError("automated decision request_id does not match")
        if self.review_status is None:
            if self.pending_since is not None or self.human_decision is not None:
                raise DomainValidationError("review fields require review_status")
        else:
            if self.pending_since is None:
                raise DomainValidationError("pending_since is required for a review case")
            require_aware_datetime(self.pending_since, "pending_since")
        if self.human_decision is None and self.reviewed_by is not None:
            raise DomainValidationError("reviewed_by requires a human decision")
        if self.human_decision is not None and (
            self.human_decision.request_id != self.request_id or self.reviewed_by is None
        ):
            raise DomainValidationError("human decision review metadata is inconsistent")

    @property
    def request_id(self) -> str:
        return self.submission.request_id


@dataclass(frozen=True, slots=True)
class ProcessingOutcome:
    created: bool
    result: RequestResult

    def __post_init__(self) -> None:
        if not isinstance(self.created, bool):
            raise DomainValidationError("created must be a boolean")
        if not isinstance(self.result, RequestResult):
            raise DomainValidationError("result must be a RequestResult")

    @property
    def replayed(self) -> bool:
        return not self.created


class WorkflowRepository(Protocol):
    def register_received(
        self,
        submission: ReimbursementSubmission,
        *,
        submission_hash: str,
        opened_at: datetime,
        audit_event: AuditEvent,
    ) -> tuple[bool, RequestResult]: ...

    def start_processing(
        self,
        *,
        request_id: str,
        processing_run_id: str,
        pipeline_version: str,
        input_hash: str,
        expected_version: int,
        started_at: datetime,
        correlation_id: str,
        audit_event: AuditEvent,
    ) -> int: ...

    def begin_invocation(
        self,
        invocation: InvocationSummary,
        *,
        audit_event: AuditEvent,
    ) -> None: ...

    def finish_invocation(
        self,
        invocation: InvocationSummary,
        *,
        raw_response: str,
        audit_event: AuditEvent,
    ) -> None: ...

    def complete_processing(
        self,
        *,
        request_id: str,
        processing_run_id: str,
        extraction: ExtractionResult,
        source_invocation_id: str,
        automated_decision: AutomatedDecision,
        problems: tuple[ReviewProblem, ...],
        expected_version: int,
        resulting_status: ReimbursementStatus,
        completed_at: datetime,
        decision_event: AuditEvent,
        review_event: AuditEvent | None,
    ) -> RequestResult: ...

    def get_result(self, request_id: str) -> RequestResult | None: ...


class _Policy(Protocol):
    policy_version: str

    def evaluate(
        self,
        submission: ReimbursementSubmission,
        extraction: ExtractionResult,
        *,
        decision_id: str,
        decided_at: datetime,
    ) -> AutomatedDecision: ...


class ProcessingService:
    """Run durable intake and deterministic routing around one external extraction."""

    def __init__(
        self,
        repository: WorkflowRepository,
        extractor: ReceiptExtractor,
        *,
        policy: _Policy | None = None,
        clock: Callable[[], datetime] | None = None,
        run_id_factory: Callable[[], str] | None = None,
        invocation_id_factory: Callable[[], str] | None = None,
        decision_id_factory: Callable[[], str] | None = None,
        event_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._repository = repository
        self._extractor = extractor
        self._policy = policy or BaselinePolicy()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._run_id_factory = run_id_factory or (lambda: uuid4().hex)
        self._invocation_id_factory = invocation_id_factory or (lambda: uuid4().hex)
        self._decision_id_factory = decision_id_factory or (lambda: uuid4().hex)
        self._event_id_factory = event_id_factory or (lambda: uuid4().hex)

    def process(
        self,
        submission: ReimbursementSubmission,
        *,
        actor: AuditActor,
        correlation_id: str,
    ) -> ProcessingOutcome:
        if not isinstance(submission, ReimbursementSubmission):
            raise DomainValidationError("submission must be a ReimbursementSubmission")
        if not isinstance(actor, AuditActor):
            raise DomainValidationError("actor must be an AuditActor")
        normalized_correlation_id = require_non_blank(correlation_id, "correlation_id")
        opened_at = self._now()
        submission_hash = submission_fingerprint(submission)
        created, registered = self._repository.register_received(
            submission,
            submission_hash=submission_hash,
            opened_at=opened_at,
            audit_event=AuditEvent(
                event_id=self._event_id_factory(),
                request_id=submission.request_id,
                event_type="reimbursement_received",
                occurred_at=opened_at,
                actor=actor,
                correlation_id=normalized_correlation_id,
                payload={
                    "attachment_count": len(submission.attachments),
                    "request_version": 1,
                    "submission_hash": submission_hash,
                    "to_status": ReimbursementStatus.RECEIVED.value,
                },
            ),
        )
        if not created:
            return ProcessingOutcome(created=False, result=registered)

        processing_run_id = require_non_blank(
            self._run_id_factory(), "processing_run_id"
        )
        input_hash = _sha256_text(submission.raw_ocr_text)
        started_at = self._now()
        processing_version = self._repository.start_processing(
            request_id=submission.request_id,
            processing_run_id=processing_run_id,
            pipeline_version=self._policy.policy_version,
            input_hash=input_hash,
            expected_version=registered.version,
            started_at=started_at,
            correlation_id=normalized_correlation_id,
            audit_event=AuditEvent(
                event_id=self._event_id_factory(),
                request_id=submission.request_id,
                event_type="reimbursement_processing_started",
                occurred_at=started_at,
                actor=AuditActor(actor_type="system", actor_id="processing-orchestrator"),
                correlation_id=normalized_correlation_id,
                payload={
                    "from_status": ReimbursementStatus.RECEIVED.value,
                    "pipeline_version": self._policy.policy_version,
                    "processing_run_id": processing_run_id,
                    "request_version": registered.version,
                    "result_version": registered.version + 1,
                    "to_status": ReimbursementStatus.PROCESSING.value,
                },
            ),
        )

        invocation_id = require_non_blank(
            self._invocation_id_factory(), "invocation_id"
        )
        invocation_started_at = self._now()
        running_invocation = InvocationSummary(
            invocation_id=invocation_id,
            processing_run_id=processing_run_id,
            stage="primary_extractor",
            attempt=1,
            status=InvocationStatus.RUNNING,
            provider=self._extractor.provider,
            model=self._extractor.model,
            prompt_version=self._extractor.prompt_version,
            prompt_hash=self._extractor.prompt_hash,
            input_hash=input_hash,
            invoked_at=invocation_started_at,
        )
        self._repository.begin_invocation(
            running_invocation,
            audit_event=AuditEvent(
                event_id=self._event_id_factory(),
                request_id=submission.request_id,
                event_type="model_invocation_started",
                occurred_at=invocation_started_at,
                actor=AuditActor(
                    actor_type="system",
                    actor_id=f"extractor:{self._extractor.provider}",
                ),
                correlation_id=normalized_correlation_id,
                payload={
                    "attempt": 1,
                    "invocation_id": invocation_id,
                    "model": self._extractor.model,
                    "processing_run_id": processing_run_id,
                    "provider": self._extractor.provider,
                    "stage": "primary_extractor",
                },
            ),
        )

        try:
            extraction = self._extractor.extract(submission)
            self._validate_extraction(submission, extraction, running_invocation)
        except Exception as exc:  # noqa: BLE001 - normalize failures at the adapter boundary
            completed_at = self._now()
            duration_ms = max(
                0,
                int((completed_at - invocation_started_at).total_seconds() * 1000),
            )
            extraction = ExtractionResult(
                request_id=submission.request_id,
                status=ExtractionStatus.FAILED,
                trace=ModelInvocationTrace(
                    provider=self._extractor.provider,
                    model=self._extractor.model,
                    prompt_version=self._extractor.prompt_version,
                    prompt_hash=self._extractor.prompt_hash,
                    input_hash=input_hash,
                    raw_response="",
                    invoked_at=invocation_started_at,
                    duration_ms=duration_ms,
                    parameters={"exception_type": type(exc).__name__},
                ),
                error="extractor invocation failed",
            )

        trace = extraction.trace
        invocation_status = (
            InvocationStatus.SUCCEEDED
            if extraction.status is ExtractionStatus.SUCCEEDED
            else InvocationStatus.FAILED
        )
        completed_at = self._now()
        completed_invocation = InvocationSummary(
            invocation_id=invocation_id,
            processing_run_id=processing_run_id,
            stage="primary_extractor",
            attempt=1,
            status=invocation_status,
            provider=trace.provider,
            model=trace.model,
            prompt_version=trace.prompt_version,
            prompt_hash=trace.prompt_hash,
            input_hash=trace.input_hash,
            output_hash=_sha256_text(trace.raw_response),
            invoked_at=trace.invoked_at,
            completed_at=completed_at,
            duration_ms=trace.duration_ms,
            parameters=trace.parameters,
            error=extraction.error,
        )
        self._repository.finish_invocation(
            completed_invocation,
            raw_response=trace.raw_response,
            audit_event=self._invocation_completed_event(
                submission.request_id,
                completed_invocation,
                normalized_correlation_id,
            ),
        )

        decided_at = self._now()
        automated_decision = self._policy.evaluate(
            submission,
            extraction,
            decision_id=require_non_blank(self._decision_id_factory(), "decision_id"),
            decided_at=decided_at,
        )
        case = ReimbursementCase(submission=submission, opened_at=opened_at)
        case.start_processing()
        case.record_automated_decision(automated_decision)
        problems = (
            tuple(
                ReviewProblem(
                    code=reason.code,
                    message=reason.message,
                    evidence=reason.evidence,
                )
                for reason in automated_decision.reasons
            )
            if automated_decision.route is PolicyDecisionRoute.HUMAN_REVIEW
            else ()
        )
        decision_event = AuditEvent(
            event_id=self._event_id_factory(),
            request_id=submission.request_id,
            event_type="automated_decision_recorded",
            occurred_at=decided_at,
            actor=AuditActor(actor_type="system", actor_id="deterministic-policy-engine"),
            correlation_id=normalized_correlation_id,
            payload={
                "decision_id": automated_decision.decision_id,
                "extraction_status": extraction.status.value,
                "from_status": ReimbursementStatus.PROCESSING.value,
                "policy_version": automated_decision.policy_version,
                "processing_run_id": processing_run_id,
                "request_version": processing_version,
                "result_version": processing_version + 1,
                "route": automated_decision.route.value,
                "to_status": case.status.value,
            },
        )
        review_event = None
        if case.status is ReimbursementStatus.PENDING_REVIEW:
            review_event = AuditEvent(
                event_id=self._event_id_factory(),
                request_id=submission.request_id,
                event_type="review_case_enqueued",
                occurred_at=decided_at,
                actor=AuditActor(
                    actor_type="system",
                    actor_id="deterministic-policy-engine",
                ),
                correlation_id=normalized_correlation_id,
                payload={
                    "attachment_count": len(submission.attachments),
                    "automated_decision_id": automated_decision.decision_id,
                    "extraction_status": extraction.status.value,
                    "policy_version": automated_decision.policy_version,
                    "route": automated_decision.route.value,
                    "to_status": case.status.value,
                },
            )
        result = self._repository.complete_processing(
            request_id=submission.request_id,
            processing_run_id=processing_run_id,
            extraction=extraction,
            source_invocation_id=invocation_id,
            automated_decision=automated_decision,
            problems=problems,
            expected_version=processing_version,
            resulting_status=case.status,
            completed_at=decided_at,
            decision_event=decision_event,
            review_event=review_event,
        )
        return ProcessingOutcome(created=True, result=result)

    def get_result(self, request_id: str) -> RequestResult:
        normalized_request_id = require_non_blank(request_id, "request_id")
        result = self._repository.get_result(normalized_request_id)
        if result is None:
            raise RequestNotFoundError(f"request {normalized_request_id!r} was not found")
        return result

    def _invocation_completed_event(
        self,
        request_id: str,
        invocation: InvocationSummary,
        correlation_id: str,
    ) -> AuditEvent:
        return AuditEvent(
            event_id=self._event_id_factory(),
            request_id=request_id,
            event_type="model_invocation_completed",
            occurred_at=invocation.completed_at or self._now(),
            actor=AuditActor(
                actor_type="system",
                actor_id=f"extractor:{invocation.provider}",
            ),
            correlation_id=correlation_id,
            payload={
                "attempt": invocation.attempt,
                "duration_ms": invocation.duration_ms or 0,
                "invocation_id": invocation.invocation_id,
                "processing_run_id": invocation.processing_run_id,
                "stage": invocation.stage,
                "status": invocation.status.value,
            },
        )

    @staticmethod
    def _validate_extraction(
        submission: ReimbursementSubmission,
        extraction: ExtractionResult,
        invocation: InvocationSummary,
    ) -> None:
        if not isinstance(extraction, ExtractionResult):
            raise DomainValidationError("extractor must return an ExtractionResult")
        if extraction.request_id != submission.request_id:
            raise DomainValidationError("extraction request_id does not match the submission")
        trace = extraction.trace
        expected = (
            invocation.provider,
            invocation.model,
            invocation.prompt_version,
            invocation.prompt_hash,
            invocation.input_hash,
        )
        actual = (
            trace.provider,
            trace.model,
            trace.prompt_version,
            trace.prompt_hash,
            trace.input_hash,
        )
        if actual != expected:
            raise DomainValidationError("extractor trace metadata does not match invocation start")

    def _now(self) -> datetime:
        value = self._clock()
        require_aware_datetime(value, "clock result")
        return value.astimezone(UTC)


def submission_fingerprint(submission: ReimbursementSubmission) -> str:
    """Hash the immutable normalized input; correlation and processing data are excluded."""

    if not isinstance(submission, ReimbursementSubmission):
        raise DomainValidationError("submission must be a ReimbursementSubmission")
    payload = {
        "attachments": [attachment.location for attachment in submission.attachments],
        "claimed_amount": format(submission.claimed_amount.amount, "f"),
        "claimed_category": submission.claimed_category,
        "currency": submission.claimed_amount.currency.value,
        "raw_ocr_text": submission.raw_ocr_text,
        "request_id": submission.request_id,
        "submitted_at": submission.submitted_at.astimezone(UTC).isoformat(timespec="microseconds"),
        "submitted_by": submission.submitted_by,
    }
    return _sha256_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


__all__ = [
    "ExtractionSnapshot",
    "InvocationStatus",
    "InvocationSummary",
    "ProcessingOutcome",
    "ProcessingRunStatus",
    "ProcessingRunSummary",
    "ProcessingService",
    "RequestConflictError",
    "RequestNotFoundError",
    "RequestResult",
    "WorkflowRepository",
    "submission_fingerprint",
]
