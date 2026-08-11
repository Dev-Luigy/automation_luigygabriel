"""Application contracts and use cases for the internal human-review queue."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from types import MappingProxyType
from typing import Protocol
from uuid import uuid4

from expense_agent.application.operational_audit import OperationalAuditRecorder
from expense_agent.domain._validation import require_aware_datetime, require_non_blank
from expense_agent.domain.audit import AuditActor, AuditEvent
from expense_agent.domain.decisions import AutomatedDecision, HumanDecision, ReviewOutcome
from expense_agent.domain.exceptions import DomainValidationError
from expense_agent.domain.extraction import ExtractionResult
from expense_agent.domain.reimbursement import (
    AttachmentReference,
    ReimbursementCase,
    ReimbursementStatus,
    ReimbursementSubmission,
)
from expense_agent.domain.value_objects import Money


class ReviewNotFoundError(LookupError):
    """Raised when a reimbursement is not visible in the review repository."""


class ReviewConflictError(RuntimeError):
    """Raised when a stale, repeated, or competing review cannot be committed."""


class ReviewCaseStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class ReviewQueueSort(str, Enum):
    """Stable, language-neutral sort keys supported by the review queue."""

    PENDING_OLDEST = "pending_oldest"
    PENDING_NEWEST = "pending_newest"
    AMOUNT_ASC = "amount_asc"
    AMOUNT_DESC = "amount_desc"
    SUBMITTED_NEWEST = "submitted_newest"


class PendingAgeBucket(str, Enum):
    """Operational SLA buckets evaluated against a fixed queue snapshot time."""

    UNDER_4H = "under_4h"
    BETWEEN_4H_AND_24H = "4h_to_24h"
    OVER_24H = "over_24h"


@dataclass(frozen=True, slots=True)
class ReviewEventQuery:
    """Bounded forward page request for one case's business-event timeline."""

    page_size: int = 25
    cursor: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.page_size, int)
            or isinstance(self.page_size, bool)
            or not 1 <= self.page_size <= 100
        ):
            raise DomainValidationError("page_size must be between 1 and 100")
        if self.cursor is not None:
            normalized_cursor = require_non_blank(self.cursor, "cursor")
            if len(normalized_cursor) > 4096:
                raise DomainValidationError("cursor is too long")
            object.__setattr__(self, "cursor", normalized_cursor)


@dataclass(frozen=True, slots=True)
class ReviewBusinessEvent:
    """Sanitized business event safe for the normal reviewer boundary."""

    event_id: str
    request_id: str
    event_type: str
    occurred_at: datetime
    actor: AuditActor
    correlation_id: str
    payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("event_id", "request_id", "event_type", "correlation_id"):
            object.__setattr__(
                self,
                field_name,
                require_non_blank(getattr(self, field_name), field_name),
            )
        require_aware_datetime(self.occurred_at, "occurred_at")
        if not isinstance(self.actor, AuditActor):
            raise DomainValidationError("actor must be an AuditActor")
        normalized_payload = dict(self.payload)
        if not all(isinstance(key, str) and key.strip() for key in normalized_payload):
            raise DomainValidationError("payload keys must be non-blank strings")
        if not all(
            isinstance(value, (str, int, bool)) for value in normalized_payload.values()
        ):
            raise DomainValidationError("payload values must be scalar business data")
        object.__setattr__(self, "payload", MappingProxyType(normalized_payload))


@dataclass(frozen=True, slots=True)
class ReviewEventPage:
    """One stable chronological keyset page of sanitized business events."""

    items: tuple[ReviewBusinessEvent, ...]
    page_size: int
    has_more: bool
    next_cursor: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        if not all(isinstance(item, ReviewBusinessEvent) for item in self.items):
            raise DomainValidationError("items must contain ReviewBusinessEvent values")
        if not isinstance(self.page_size, int) or not 1 <= self.page_size <= 100:
            raise DomainValidationError("page_size must be between 1 and 100")
        if not isinstance(self.has_more, bool):
            raise DomainValidationError("has_more must be a boolean")
        if self.has_more and not self.next_cursor:
            raise DomainValidationError("next_cursor is required when has_more is true")
        if self.next_cursor is not None and not isinstance(self.next_cursor, str):
            raise DomainValidationError("next_cursor must be a string when present")


@dataclass(frozen=True, slots=True)
class ReviewerIdentity:
    """Canonical reviewer identity supplied by a trusted authentication adapter."""

    reviewer_id: str
    email: str
    display_name: str

    def __post_init__(self) -> None:
        for field_name in ("reviewer_id", "email", "display_name"):
            object.__setattr__(
                self,
                field_name,
                require_non_blank(getattr(self, field_name), field_name),
            )


@dataclass(frozen=True, slots=True)
class ReviewProblem:
    """A concrete issue that explains why a reimbursement needs judgment."""

    code: str
    message: str
    evidence: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", require_non_blank(self.code, "problem code"))
        object.__setattr__(
            self,
            "message",
            require_non_blank(self.message, "problem message"),
        )
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))


@dataclass(frozen=True, slots=True)
class ReviewQueueItem:
    """Small read model used to render the pending-review queue."""

    request_id: str
    submitted_by: str
    submitted_at: datetime
    claimed_category: str
    claimed_amount: Money
    pending_since: datetime
    version: int
    merchant_name: str | None = None
    extracted_amount: Money | None = None
    primary_problem: ReviewProblem | None = None
    problem_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("request_id", "submitted_by", "claimed_category"):
            object.__setattr__(
                self,
                field_name,
                require_non_blank(getattr(self, field_name), field_name),
            )
        require_aware_datetime(self.submitted_at, "submitted_at")
        require_aware_datetime(self.pending_since, "pending_since")
        if not isinstance(self.claimed_amount, Money):
            raise DomainValidationError("claimed_amount must be Money")
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise DomainValidationError("version must be a positive integer")
        if self.merchant_name is not None:
            object.__setattr__(
                self,
                "merchant_name",
                require_non_blank(self.merchant_name, "merchant_name"),
            )
        if self.extracted_amount is not None and not isinstance(self.extracted_amount, Money):
            raise DomainValidationError("extracted_amount must be Money when present")
        if self.primary_problem is not None and not isinstance(
            self.primary_problem, ReviewProblem
        ):
            raise DomainValidationError("primary_problem must be a ReviewProblem when present")
        object.__setattr__(self, "problem_codes", tuple(self.problem_codes))
        if not all(isinstance(code, str) and code.strip() for code in self.problem_codes):
            raise DomainValidationError("problem_codes must contain non-blank strings")


@dataclass(frozen=True, slots=True)
class ReviewQueueQuery:
    """Validated filters and keyset-page request for a pending-review queue."""

    search: str | None = None
    category: str | None = None
    problem_code: str | None = None
    min_amount: Money | None = None
    max_amount: Money | None = None
    submitted_from: datetime | None = None
    submitted_to: datetime | None = None
    pending_before: datetime | None = None
    age_bucket: PendingAgeBucket | None = None
    sort: ReviewQueueSort = ReviewQueueSort.PENDING_OLDEST
    page_size: int = 25
    cursor: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("search", "category", "problem_code"):
            value = getattr(self, field_name)
            if value is not None:
                normalized = require_non_blank(value, field_name)
                if len(normalized) > 200:
                    raise DomainValidationError(f"{field_name} must contain at most 200 characters")
                object.__setattr__(self, field_name, normalized)
        for field_name in ("min_amount", "max_amount"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, Money):
                raise DomainValidationError(f"{field_name} must be Money when present")
        if (
            self.min_amount is not None
            and self.max_amount is not None
            and self.min_amount.amount > self.max_amount.amount
        ):
            raise DomainValidationError("min_amount must not exceed max_amount")
        for field_name in ("submitted_from", "submitted_to", "pending_before"):
            value = getattr(self, field_name)
            if value is not None:
                require_aware_datetime(value, field_name)
        if (
            self.submitted_from is not None
            and self.submitted_to is not None
            and self.submitted_from > self.submitted_to
        ):
            raise DomainValidationError("submitted_from must not be after submitted_to")
        if self.pending_before is not None and self.age_bucket is not None:
            raise DomainValidationError("pending_before and age_bucket cannot be combined")
        if self.age_bucket is not None and not isinstance(self.age_bucket, PendingAgeBucket):
            raise DomainValidationError("age_bucket must be a PendingAgeBucket")
        if not isinstance(self.sort, ReviewQueueSort):
            raise DomainValidationError("sort must be a ReviewQueueSort")
        if (
            not isinstance(self.page_size, int)
            or isinstance(self.page_size, bool)
            or not 10 <= self.page_size <= 100
        ):
            raise DomainValidationError("page_size must be between 10 and 100")
        if self.cursor is not None:
            normalized_cursor = require_non_blank(self.cursor, "cursor")
            if len(normalized_cursor) > 4096:
                raise DomainValidationError("cursor is too long")
            object.__setattr__(self, "cursor", normalized_cursor)


@dataclass(frozen=True, slots=True)
class ReviewQueueSummary:
    """Operational counts for the complete pending queue at one point in time."""

    total_pending: int
    over_24h: int
    high_value: int
    amount_mismatch: int
    high_value_threshold: Money
    as_of: datetime

    def __post_init__(self) -> None:
        for field_name in ("total_pending", "over_24h", "high_value", "amount_mismatch"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise DomainValidationError(f"{field_name} must be a non-negative integer")
        if not isinstance(self.high_value_threshold, Money):
            raise DomainValidationError("high_value_threshold must be Money")
        require_aware_datetime(self.as_of, "as_of")


@dataclass(frozen=True, slots=True)
class ReviewQueuePage:
    """One forward-only keyset page and its actionable queue summary."""

    items: tuple[ReviewQueueItem, ...]
    page_size: int
    sort: ReviewQueueSort
    has_more: bool
    next_cursor: str | None
    summary: ReviewQueueSummary

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        if not all(isinstance(item, ReviewQueueItem) for item in self.items):
            raise DomainValidationError("items must contain ReviewQueueItem values")
        if not isinstance(self.page_size, int) or not 10 <= self.page_size <= 100:
            raise DomainValidationError("page_size must be between 10 and 100")
        if not isinstance(self.sort, ReviewQueueSort):
            raise DomainValidationError("sort must be a ReviewQueueSort")
        if not isinstance(self.has_more, bool):
            raise DomainValidationError("has_more must be a boolean")
        if self.has_more and not self.next_cursor:
            raise DomainValidationError("next_cursor is required when has_more is true")
        if self.next_cursor is not None and not isinstance(self.next_cursor, str):
            raise DomainValidationError("next_cursor must be a string when present")
        if not isinstance(self.summary, ReviewQueueSummary):
            raise DomainValidationError("summary must be a ReviewQueueSummary")


@dataclass(frozen=True, slots=True)
class ReviewCaseDetails:
    """Complete evidence snapshot shown before a reviewer makes a decision."""

    submission: ReimbursementSubmission
    opened_at: datetime
    status: ReimbursementStatus
    version: int
    review_status: ReviewCaseStatus
    pending_since: datetime
    extraction: ExtractionResult | None
    problems: tuple[ReviewProblem, ...]
    automated_decision: AutomatedDecision
    human_decision: HumanDecision | None = None
    reviewed_by: ReviewerIdentity | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.submission, ReimbursementSubmission):
            raise DomainValidationError("submission must be a ReimbursementSubmission")
        require_aware_datetime(self.opened_at, "opened_at")
        require_aware_datetime(self.pending_since, "pending_since")
        if not isinstance(self.status, ReimbursementStatus):
            raise DomainValidationError("status must be a ReimbursementStatus")
        if not isinstance(self.review_status, ReviewCaseStatus):
            raise DomainValidationError("review_status must be a ReviewCaseStatus")
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise DomainValidationError("version must be a positive integer")
        if self.extraction is not None and self.extraction.request_id != self.request_id:
            raise DomainValidationError("extraction request_id does not match the case")
        object.__setattr__(self, "problems", tuple(self.problems))
        if not all(isinstance(problem, ReviewProblem) for problem in self.problems):
            raise DomainValidationError("problems must contain ReviewProblem values")
        if not isinstance(self.automated_decision, AutomatedDecision):
            raise DomainValidationError("automated_decision must be an AutomatedDecision")
        if self.automated_decision.request_id != self.request_id:
            raise DomainValidationError("automated decision request_id does not match the case")
        if self.human_decision is not None:
            if self.human_decision.request_id != self.request_id:
                raise DomainValidationError("human decision request_id does not match the case")
            if self.reviewed_by is None:
                raise DomainValidationError("reviewed_by is required with a human decision")
        elif self.reviewed_by is not None:
            raise DomainValidationError("reviewed_by requires a human decision")

    @property
    def request_id(self) -> str:
        return self.submission.request_id

    @property
    def attachments(self) -> tuple[AttachmentReference, ...]:
        return self.submission.attachments

    @property
    def raw_ocr_text(self) -> str:
        return self.submission.raw_ocr_text


@dataclass(frozen=True, slots=True)
class ReviewDecisionResult:
    decision: HumanDecision
    resulting_status: ReimbursementStatus
    version: int
    audit_event_id: str


class ReviewRepository(Protocol):
    """Persistence boundary required by the human-review use case."""

    def list_pending(self) -> tuple[ReviewQueueItem, ...]: ...

    def search_pending(
        self,
        query: ReviewQueueQuery,
        *,
        as_of: datetime,
    ) -> ReviewQueuePage: ...

    def get(self, request_id: str) -> ReviewCaseDetails | None: ...

    def list_business_events(
        self,
        request_id: str,
        query: ReviewEventQuery,
    ) -> ReviewEventPage | None: ...

    def record_human_decision(
        self,
        *,
        decision: HumanDecision,
        reviewer: ReviewerIdentity,
        expected_version: int,
        resulting_status: ReimbursementStatus,
        audit_event: AuditEvent,
    ) -> int: ...


class ReviewService:
    """Coordinates review reads and an auditable human-decision transaction."""

    def __init__(
        self,
        repository: ReviewRepository,
        *,
        clock: Callable[[], datetime] | None = None,
        decision_id_factory: Callable[[], str] | None = None,
        event_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))
        self._decision_id_factory = decision_id_factory or (lambda: uuid4().hex)
        self._event_id_factory = event_id_factory or (lambda: uuid4().hex)

    @property
    def operational_audit_recorder(self) -> OperationalAuditRecorder | None:
        """Expose the co-located recorder without leaking the whole repository."""

        if isinstance(self._repository, OperationalAuditRecorder):
            return self._repository
        return None

    def list_pending(self) -> tuple[ReviewQueueItem, ...]:
        return self._repository.list_pending()

    def search_pending(self, query: ReviewQueueQuery | None = None) -> ReviewQueuePage:
        """Return a bounded keyset page; retain ``list_pending`` for adapter compatibility."""

        normalized_query = query or ReviewQueueQuery()
        if not isinstance(normalized_query, ReviewQueueQuery):
            raise DomainValidationError("query must be a ReviewQueueQuery")
        return self._repository.search_pending(normalized_query, as_of=self._clock())

    def get(self, request_id: str) -> ReviewCaseDetails:
        normalized_request_id = require_non_blank(request_id, "request_id")
        details = self._repository.get(normalized_request_id)
        if details is None:
            raise ReviewNotFoundError(f"review case {normalized_request_id!r} was not found")
        return details

    def list_events(
        self,
        request_id: str,
        query: ReviewEventQuery | None = None,
    ) -> ReviewEventPage:
        """Return a bounded sanitized business timeline for one review case."""

        normalized_request_id = require_non_blank(request_id, "request_id")
        normalized_query = query or ReviewEventQuery()
        if not isinstance(normalized_query, ReviewEventQuery):
            raise DomainValidationError("query must be a ReviewEventQuery")
        page = self._repository.list_business_events(normalized_request_id, normalized_query)
        if page is None:
            raise ReviewNotFoundError(
                f"review case {normalized_request_id!r} was not found"
            )
        return page

    def decide(
        self,
        *,
        request_id: str,
        outcome: ReviewOutcome,
        reason: str,
        reviewer: ReviewerIdentity,
        expected_version: int,
        correlation_id: str,
    ) -> ReviewDecisionResult:
        """Apply domain rules, then atomically commit the decision and audit fact."""

        normalized_request_id = require_non_blank(request_id, "request_id")
        normalized_correlation_id = require_non_blank(correlation_id, "correlation_id")
        if not isinstance(reviewer, ReviewerIdentity):
            raise DomainValidationError("reviewer must come from a ReviewerIdentity")
        if not isinstance(outcome, ReviewOutcome):
            raise DomainValidationError("outcome must be a ReviewOutcome")
        if (
            not isinstance(expected_version, int)
            or isinstance(expected_version, bool)
            or expected_version < 1
        ):
            raise DomainValidationError("expected_version must be a positive integer")
        if isinstance(reason, str) and len(reason) > 2_000:
            raise DomainValidationError("reason must contain at most 2000 characters")

        details = self.get(normalized_request_id)
        if (
            details.status is not ReimbursementStatus.PENDING_REVIEW
            or details.review_status is not ReviewCaseStatus.PENDING
            or details.version != expected_version
        ):
            raise ReviewConflictError("review case is no longer pending at the expected version")

        decided_at = self._clock()
        decision = HumanDecision(
            decision_id=self._decision_id_factory(),
            request_id=normalized_request_id,
            outcome=outcome,
            reviewer=reviewer.reviewer_id,
            reason=reason,
            decided_at=decided_at,
        )

        # Replay the existing state through the aggregate instead of assigning a
        # final status in the application or persistence layers.
        case = ReimbursementCase(
            submission=details.submission,
            opened_at=details.opened_at,
        )
        case.start_processing()
        case.record_automated_decision(details.automated_decision)
        case.record_human_decision(decision)

        audit_event = AuditEvent(
            event_id=self._event_id_factory(),
            request_id=normalized_request_id,
            event_type="human_review_decided",
            occurred_at=decided_at,
            actor=AuditActor(actor_type="reviewer", actor_id=reviewer.reviewer_id),
            correlation_id=normalized_correlation_id,
            payload={
                "decision_id": decision.decision_id,
                "from_status": ReimbursementStatus.PENDING_REVIEW.value,
                "outcome": decision.outcome.value,
                "reason": decision.reason,
                "request_version": expected_version,
                "to_status": case.status.value,
            },
        )
        version = self._repository.record_human_decision(
            decision=decision,
            reviewer=reviewer,
            expected_version=expected_version,
            resulting_status=case.status,
            audit_event=audit_event,
        )
        return ReviewDecisionResult(
            decision=decision,
            resulting_status=case.status,
            version=version,
            audit_event_id=audit_event.event_id,
        )


__all__ = [
    "PendingAgeBucket",
    "ReviewBusinessEvent",
    "ReviewCaseDetails",
    "ReviewCaseStatus",
    "ReviewConflictError",
    "ReviewDecisionResult",
    "ReviewEventPage",
    "ReviewEventQuery",
    "ReviewNotFoundError",
    "ReviewProblem",
    "ReviewQueueItem",
    "ReviewQueuePage",
    "ReviewQueueQuery",
    "ReviewQueueSort",
    "ReviewQueueSummary",
    "ReviewRepository",
    "ReviewService",
    "ReviewerIdentity",
]
