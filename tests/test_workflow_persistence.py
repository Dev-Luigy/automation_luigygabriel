import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from threading import Barrier

import pytest

from expense_agent.application import (
    InvocationStatus,
    InvocationSummary,
    ProcessingService,
    RequestConflictError,
    ReviewerIdentity,
    ReviewEventQuery,
    ReviewService,
    submission_fingerprint,
)
from expense_agent.domain import (
    AttachmentReference,
    AuditActor,
    AuditEvent,
    ExtractionResult,
    ExtractionStatus,
    ModelInvocationTrace,
    Money,
    PolicyDecisionRoute,
    ReceiptFacts,
    ReimbursementStatus,
    ReimbursementSubmission,
    ReviewOutcome,
)
from expense_agent.infrastructure.review import SqliteReviewRepository

NOW = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)


class StubExtractor:
    provider = "test-provider"
    model = "test-model-v1"
    prompt_version = "test-prompt-v1"
    prompt_hash = "prompt-sha256"

    def __init__(
        self,
        *,
        receipt_date: date,
        total: str,
        category: str = "meals",
        invoked_at: datetime = NOW,
    ) -> None:
        self.receipt_date = receipt_date
        self.total = total
        self.category = category
        self.invoked_at = invoked_at
        self.calls = 0

    def extract(self, submission: ReimbursementSubmission) -> ExtractionResult:
        self.calls += 1
        raw_response = f'{{"total":"{self.total}"}}'
        return ExtractionResult(
            request_id=submission.request_id,
            status=ExtractionStatus.SUCCEEDED,
            trace=ModelInvocationTrace(
                provider=self.provider,
                model=self.model,
                prompt_version=self.prompt_version,
                prompt_hash=self.prompt_hash,
                input_hash=hashlib.sha256(
                    submission.raw_ocr_text.encode("utf-8")
                ).hexdigest(),
                raw_response=raw_response,
                invoked_at=self.invoked_at,
                duration_ms=17,
                parameters={"temperature": 0},
            ),
            facts=ReceiptFacts(
                receipt_date=self.receipt_date,
                total=Money.brl(self.total),
                category=self.category,
                merchant_name="Test Merchant",
            ),
        )


class RaisingExtractor(StubExtractor):
    def extract(self, submission: ReimbursementSubmission) -> ExtractionResult:
        self.calls += 1
        raise TimeoutError("secret provider detail")


class CrashAfterBeginRepository:
    """Fault injector that crashes only after the running attempt is durable."""

    def __init__(self, repository: SqliteReviewRepository) -> None:
        self.repository = repository

    def __getattr__(self, name: str):
        return getattr(self.repository, name)

    def begin_invocation(self, invocation, *, audit_event) -> None:
        self.repository.begin_invocation(invocation, audit_event=audit_event)
        raise RuntimeError("simulated worker crash after invocation start")


class CrashAfterFinishRepository:
    """Fault injector that crashes after provider output is terminal and durable."""

    def __init__(self, repository: SqliteReviewRepository) -> None:
        self.repository = repository

    def __getattr__(self, name: str):
        return getattr(self.repository, name)

    def finish_invocation(self, invocation, *, raw_response, audit_event) -> None:
        self.repository.finish_invocation(
            invocation,
            raw_response=raw_response,
            audit_event=audit_event,
        )
        raise RuntimeError("simulated worker crash after invocation completion")


class BarrierClaimRepository:
    def __init__(self, repository: SqliteReviewRepository, barrier: Barrier) -> None:
        self.repository = repository
        self.barrier = barrier

    def __getattr__(self, name: str):
        return getattr(self.repository, name)

    def claim_processing(self, **kwargs):
        self.barrier.wait(timeout=5)
        return self.repository.claim_processing(**kwargs)


def _submission(
    request_id: str,
    *,
    amount: str = "100.00",
) -> ReimbursementSubmission:
    return ReimbursementSubmission(
        request_id=request_id,
        submitted_by="submitter@example.com",
        submitted_at=NOW,
        raw_ocr_text=f"TEST MERCHANT\nDATE: 10/04/2026\nTOTAL: R$ {amount}",
        claimed_category="meals",
        claimed_amount=Money.brl(amount),
        attachments=(AttachmentReference(f"receipts/{request_id}.jpg"),),
    )


def _service(
    repository: SqliteReviewRepository,
    extractor: StubExtractor,
) -> ProcessingService:
    event_ids = iter(f"EVENT-{index}" for index in range(100))
    return ProcessingService(
        repository,
        extractor,
        clock=lambda: NOW,
        run_id_factory=lambda: "RUN-1",
        invocation_id_factory=lambda: "INVOCATION-1",
        decision_id_factory=lambda: "DECISION-1",
        event_id_factory=lambda: next(event_ids),
    )


def _strand_running_attempt(database_path) -> ReimbursementSubmission:
    repository = SqliteReviewRepository(database_path)
    submission = _submission("REQ-LEASE-RECOVERY")
    service = ProcessingService(
        CrashAfterBeginRepository(repository),  # type: ignore[arg-type]
        StubExtractor(receipt_date=date(2026, 4, 10), total="100.00"),
        clock=lambda: NOW,
        run_id_factory=lambda: "RUN-STRANDED",
        invocation_id_factory=lambda: "INVOCATION-STRANDED",
        decision_id_factory=lambda: "DECISION-UNUSED",
        event_id_factory=iter(f"STRAND-EVENT-{index}" for index in range(20)).__next__,
        processing_lease=timedelta(minutes=5),
    )
    with pytest.raises(RuntimeError, match="simulated worker crash"):
        service.process(
            submission,
            actor=AuditActor("submitter", "user-42"),
            correlation_id="corr-stranded",
        )
    return submission


@pytest.mark.parametrize(
    ("request_id", "amount", "receipt_date", "expected_status", "expected_route"),
    (
        (
            "REQ-AUTO",
            "100.00",
            date(2026, 4, 10),
            ReimbursementStatus.AUTO_APPROVED,
            PolicyDecisionRoute.AUTO_APPROVED,
        ),
        (
            "REQ-REVIEW",
            "500.00",
            date(2026, 4, 10),
            ReimbursementStatus.PENDING_REVIEW,
            PolicyDecisionRoute.HUMAN_REVIEW,
        ),
        (
            "REQ-REJECT",
            "100.00",
            date(2025, 12, 1),
            ReimbursementStatus.REJECTED,
            PolicyDecisionRoute.REJECTED,
        ),
    ),
)
def test_end_to_end_processing_persists_every_route_and_safe_result(
    tmp_path,
    request_id,
    amount,
    receipt_date,
    expected_status,
    expected_route,
) -> None:
    repository = SqliteReviewRepository(tmp_path / f"{request_id}.db")
    extractor = StubExtractor(receipt_date=receipt_date, total=amount)

    outcome = _service(repository, extractor).process(
        _submission(request_id, amount=amount),
        actor=AuditActor("submitter", "user-42"),
        correlation_id=f"corr-{request_id}",
    )

    assert outcome.created is True
    assert outcome.replayed is False
    assert outcome.result.status is expected_status
    assert outcome.result.version == 3
    assert outcome.result.automated_decision is not None
    assert outcome.result.automated_decision.route is expected_route
    assert outcome.result.extraction is not None
    assert outcome.result.extraction.invocation.status is InvocationStatus.SUCCEEDED
    assert not hasattr(outcome.result.extraction.invocation, "raw_response")
    assert "raw_response" not in repr(outcome.result)
    assert outcome.result.processing_run is not None
    assert outcome.result.processing_run.status.value == "completed"
    if expected_status is ReimbursementStatus.PENDING_REVIEW:
        review = repository.get(request_id)
        assert review is not None
        assert review.version == 3
        assert review.problems
    else:
        assert repository.get(request_id) is None


def test_same_payload_replays_and_different_payload_conflicts_with_security_audit(
    tmp_path,
) -> None:
    database_path = tmp_path / "idempotency.db"
    repository = SqliteReviewRepository(database_path)
    extractor = StubExtractor(receipt_date=date(2026, 4, 10), total="100.00")
    service = _service(repository, extractor)
    submission = _submission("REQ-IDEMPOTENT")

    first = service.process(
        submission,
        actor=AuditActor("submitter", "user-42"),
        correlation_id="corr-first",
    )
    replay = service.process(
        submission,
        actor=AuditActor("submitter", "user-42"),
        correlation_id="corr-replay",
    )
    conflicting = replace(submission, claimed_amount=Money.brl("101.00"))
    with pytest.raises(RequestConflictError, match="different input"):
        service.process(
            conflicting,
            actor=AuditActor("submitter", "user-42"),
            correlation_id="corr-conflict",
        )

    assert first.created is True
    assert replay.created is False
    assert replay.result.version == first.result.version == 3
    assert extractor.calls == 1
    with sqlite3.connect(database_path) as connection:
        reimbursement = connection.execute(
            "SELECT status, version, submission_hash FROM reimbursements"
        ).fetchone()
        security_events = connection.execute(
            """
            SELECT event_type FROM audit_events WHERE event_scope = 'security'
            ORDER BY occurred_at, event_id
            """
        ).fetchall()
    assert reimbursement == (
        ReimbursementStatus.AUTO_APPROVED.value,
        3,
        submission_fingerprint(submission),
    )
    assert {row[0] for row in security_events} == {
        "reimbursement_intake_replayed",
        "reimbursement_intake_conflict_rejected",
    }

    business_events = ReviewService(repository).list_events(
        submission.request_id,
        ReviewEventQuery(page_size=100),
    )
    assert [event.event_type for event in business_events.items] == [
        "reimbursement_received",
        "reimbursement_processing_started",
        "automated_decision_recorded",
    ]


def test_unexpected_extractor_exception_becomes_failed_trace_and_pending_review(tmp_path) -> None:
    repository = SqliteReviewRepository(tmp_path / "failure.db")
    extractor = RaisingExtractor(receipt_date=date(2026, 4, 10), total="100.00")

    outcome = _service(repository, extractor).process(
        _submission("REQ-FAILURE"),
        actor=AuditActor("submitter", "user-42"),
        correlation_id="corr-failure",
    )

    assert outcome.result.status is ReimbursementStatus.PENDING_REVIEW
    assert outcome.result.processing_run is not None
    assert outcome.result.processing_run.status.value == "completed"
    assert outcome.result.extraction is not None
    assert outcome.result.extraction.status is ExtractionStatus.FAILED
    assert outcome.result.extraction.error == "extractor invocation failed"
    assert "secret provider detail" not in repr(outcome.result)


def test_real_pipeline_pending_v3_remains_compatible_with_human_decision_v4(tmp_path) -> None:
    repository = SqliteReviewRepository(tmp_path / "pipeline-review.db")
    submission = _submission("REQ-PIPELINE-REVIEW", amount="500.00")
    extractor = StubExtractor(receipt_date=date(2026, 4, 10), total="500.00")
    processing = _service(repository, extractor).process(
        submission,
        actor=AuditActor("submitter", "user-42"),
        correlation_id="corr-pipeline",
    )
    assert processing.result.status is ReimbursementStatus.PENDING_REVIEW
    assert processing.result.version == 3

    reviewer = ReviewerIdentity("reviewer-7", "reviewer@example.com", "Reviewer Seven")
    reviewed = ReviewService(
        repository,
        clock=lambda: NOW,
        decision_id_factory=lambda: "HUMAN-PIPELINE",
        event_id_factory=lambda: "EVENT-HUMAN-PIPELINE",
    ).decide(
        request_id=submission.request_id,
        outcome=ReviewOutcome.APPROVED,
        reason="Receipt and claim were manually verified.",
        reviewer=reviewer,
        expected_version=3,
        correlation_id="corr-human",
    )

    assert reviewed.version == 4
    assert reviewed.resulting_status is ReimbursementStatus.APPROVED_AFTER_REVIEW
    result = repository.get_result(submission.request_id)
    assert result is not None
    assert result.version == 4
    assert result.status is ReimbursementStatus.APPROVED_AFTER_REVIEW
    assert result.human_decision == reviewed.decision
    assert result.reviewed_by == reviewer


def test_late_finalization_audit_failure_rolls_back_financial_outcome(tmp_path) -> None:
    database_path = tmp_path / "finalization-rollback.db"
    repository = SqliteReviewRepository(database_path)
    extractor = StubExtractor(receipt_date=date(2026, 4, 10), total="100.00")
    event_ids = iter(("EVENT-DUP", "EVENT-START", "EVENT-CALL", "EVENT-END", "EVENT-DUP"))
    service = ProcessingService(
        repository,
        extractor,
        clock=lambda: NOW,
        run_id_factory=lambda: "RUN-ROLLBACK",
        invocation_id_factory=lambda: "INVOCATION-ROLLBACK",
        decision_id_factory=lambda: "DECISION-ROLLBACK",
        event_id_factory=lambda: next(event_ids),
    )

    with pytest.raises(RequestConflictError, match="completion conflicts"):
        service.process(
            _submission("REQ-ROLLBACK"),
            actor=AuditActor("submitter", "user-42"),
            correlation_id="corr-rollback",
        )

    result = repository.get_result("REQ-ROLLBACK")
    assert result is not None
    assert result.status is ReimbursementStatus.PROCESSING
    assert result.version == 2
    assert result.extraction is None
    assert result.automated_decision is None
    assert result.processing_run is not None
    assert result.processing_run.status.value == "running"
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM extractions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM automated_decisions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM review_cases").fetchone()[0] == 0


def test_active_lease_replays_without_extraction_then_expired_lease_recovers_after_restart(
    tmp_path,
) -> None:
    database_path = tmp_path / "lease-restart.db"
    submission = _strand_running_attempt(database_path)

    active_time = NOW + timedelta(minutes=4)
    active_extractor = StubExtractor(
        receipt_date=date(2026, 4, 10),
        total="100.00",
        invoked_at=active_time,
    )
    active_service = ProcessingService(
        SqliteReviewRepository(database_path),
        active_extractor,
        clock=lambda: active_time,
        run_id_factory=lambda: "RUN-NOT-ACQUIRED",
        invocation_id_factory=lambda: "INVOCATION-NOT-STARTED",
        decision_id_factory=lambda: "DECISION-NOT-CREATED",
        event_id_factory=iter(f"ACTIVE-EVENT-{index}" for index in range(20)).__next__,
        processing_lease=timedelta(minutes=5),
    )

    active = active_service.process(
        submission,
        actor=AuditActor("submitter", "user-42"),
        correlation_id="corr-active-replay",
    )

    assert active.created is False
    assert active.recovered is False
    assert active.replayed is True
    assert active.result.status is ReimbursementStatus.PROCESSING
    assert active.result.version == 2
    assert active_extractor.calls == 0

    recovery_time = NOW + timedelta(minutes=6)
    recovery_extractor = StubExtractor(
        receipt_date=date(2026, 4, 10),
        total="100.00",
        invoked_at=recovery_time,
    )
    recovered_repository = SqliteReviewRepository(database_path)
    recovered_service = ProcessingService(
        recovered_repository,
        recovery_extractor,
        clock=lambda: recovery_time,
        run_id_factory=lambda: "RUN-RECOVERED",
        invocation_id_factory=lambda: "INVOCATION-RECOVERED",
        decision_id_factory=lambda: "DECISION-RECOVERED",
        event_id_factory=iter(f"RECOVERY-EVENT-{index}" for index in range(30)).__next__,
        processing_lease=timedelta(minutes=5),
    )

    recovered = recovered_service.process(
        submission,
        actor=AuditActor("submitter", "user-42"),
        correlation_id="corr-recovered",
    )

    assert recovered.created is False
    assert recovered.recovered is True
    assert recovered.replayed is False
    assert recovered.result.status is ReimbursementStatus.AUTO_APPROVED
    assert recovered.result.version == 4
    assert recovery_extractor.calls == 1

    terminal_replay = recovered_service.process(
        submission,
        actor=AuditActor("submitter", "user-42"),
        correlation_id="corr-terminal-replay",
    )
    assert terminal_replay.created is False
    assert terminal_replay.recovered is False
    assert terminal_replay.replayed is True
    assert terminal_replay.result.version == 4
    assert recovery_extractor.calls == 1

    with sqlite3.connect(database_path) as connection:
        runs = connection.execute(
            """
            SELECT processing_run_id, run_number, status, lease_expires_at,
                   abandoned_at, error
            FROM processing_runs ORDER BY run_number
            """
        ).fetchall()
        attempts = connection.execute(
            """
            SELECT invocation_id, status, abandoned_at, raw_response, error
            FROM processing_invocation_attempts ORDER BY invoked_at, invocation_id
            """
        ).fetchall()
        decisions = connection.execute(
            "SELECT decision_id, processing_run_id FROM automated_decisions"
        ).fetchall()
        technical_events = connection.execute(
            """
            SELECT event_type, payload_json FROM audit_events
            WHERE event_scope = 'technical' ORDER BY occurred_at, event_id
            """
        ).fetchall()
    assert runs[0][0:4] == ("RUN-STRANDED", 1, "failed", None)
    assert runs[0][4] is not None
    assert runs[0][5] == "processing lease expired; run abandoned"
    assert runs[1][0:5] == ("RUN-RECOVERED", 2, "completed", None, None)
    assert attempts[0][0:2] == ("INVOCATION-STRANDED", "failed")
    assert attempts[0][2] is not None
    assert attempts[0][3] == ""
    assert "expired" in attempts[0][4]
    assert attempts[1][0:3] == ("INVOCATION-RECOVERED", "succeeded", None)
    assert decisions == [("DECISION-RECOVERED", "RUN-RECOVERED")]
    assert {event_type for event_type, _payload in technical_events} >= {
        "model_invocation_abandoned",
        "processing_run_abandoned",
    }
    assert "secret" not in repr(technical_events).lower()

    timeline = ReviewService(recovered_repository).list_events(
        submission.request_id,
        ReviewEventQuery(page_size=100),
    )
    assert [event.event_type for event in timeline.items] == [
        "reimbursement_received",
        "reimbursement_processing_started",
        "reimbursement_processing_resumed",
        "automated_decision_recorded",
    ]
    resumed_event = timeline.items[2]
    assert resumed_event.payload["abandoned_processing_run_id"] == "RUN-STRANDED"
    assert resumed_event.payload["processing_run_id"] == "RUN-RECOVERED"
    assert resumed_event.payload["reason"] == "lease_expired"


def test_concurrent_expired_lease_replays_grant_one_recovery_owner(tmp_path) -> None:
    database_path = tmp_path / "lease-concurrency.db"
    submission = _strand_running_attempt(database_path)
    recovery_time = NOW + timedelta(minutes=6)
    barrier = Barrier(2)
    extractors = [
        StubExtractor(
            receipt_date=date(2026, 4, 10),
            total="100.00",
            invoked_at=recovery_time,
        )
        for _index in range(2)
    ]
    services = []
    for index, extractor in enumerate(extractors, start=1):
        event_ids = iter(
            [f"CONCURRENT-{index}-EVENT-{event}" for event in range(30)]
        )
        repository = BarrierClaimRepository(
            SqliteReviewRepository(database_path),
            barrier,
        )
        services.append(
            ProcessingService(
                repository,  # type: ignore[arg-type]
                extractor,
                clock=lambda: recovery_time,
                run_id_factory=lambda index=index: f"RUN-CONCURRENT-{index}",
                invocation_id_factory=lambda index=index: f"INV-CONCURRENT-{index}",
                decision_id_factory=lambda index=index: f"DEC-CONCURRENT-{index}",
                event_id_factory=event_ids.__next__,
                processing_lease=timedelta(minutes=5),
            )
        )

    def recover(service: ProcessingService):
        return service.process(
            submission,
            actor=AuditActor("submitter", "user-42"),
            correlation_id=f"corr-{id(service)}",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(recover, services))

    assert sum(extractor.calls for extractor in extractors) == 1
    assert sum(outcome.recovered for outcome in outcomes) == 1
    assert all(outcome.created is False for outcome in outcomes)
    assert {outcome.result.status for outcome in outcomes} <= {
        ReimbursementStatus.PROCESSING,
        ReimbursementStatus.AUTO_APPROVED,
    }
    assert sum(
        outcome.result.status is ReimbursementStatus.AUTO_APPROVED
        for outcome in outcomes
    ) >= 1

    with sqlite3.connect(database_path) as connection:
        runs = connection.execute(
            """
            SELECT run_number, status, abandoned_at FROM processing_runs
            ORDER BY run_number
            """
        ).fetchall()
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM automated_decisions),
                (SELECT COUNT(*) FROM extractions),
                (SELECT COUNT(*) FROM audit_events
                    WHERE event_type = 'reimbursement_processing_resumed'),
                (SELECT COUNT(*) FROM processing_runs WHERE status = 'running')
            """
        ).fetchone()
    assert runs[0][0:2] == (1, "failed")
    assert runs[0][2] is not None
    assert runs[1] == (2, "completed", None)
    assert counts == (1, 1, 1, 0)


def test_recovery_audit_failure_rolls_back_abandonment_and_new_lease(tmp_path) -> None:
    database_path = tmp_path / "lease-recovery-rollback.db"
    submission = _strand_running_attempt(database_path)
    recovery_time = NOW + timedelta(minutes=6)
    extractor = StubExtractor(
        receipt_date=date(2026, 4, 10),
        total="100.00",
        invoked_at=recovery_time,
    )
    service = ProcessingService(
        SqliteReviewRepository(database_path),
        extractor,
        clock=lambda: recovery_time,
        run_id_factory=lambda: "RUN-ROLLBACK-NEW",
        invocation_id_factory=lambda: "INV-ROLLBACK-NEW",
        decision_id_factory=lambda: "DEC-ROLLBACK-NEW",
        event_id_factory=iter(
            (
                "RECOVERY-ROLLBACK-REPLAY",
                "STRAND-EVENT-0",  # Existing business event; resume insert must fail.
            )
        ).__next__,
        processing_lease=timedelta(minutes=5),
    )

    with pytest.raises(RequestConflictError, match="processing start conflicts"):
        service.process(
            submission,
            actor=AuditActor("submitter", "user-42"),
            correlation_id="corr-recovery-rollback",
        )

    assert extractor.calls == 0
    with sqlite3.connect(database_path) as connection:
        reimbursement = connection.execute(
            "SELECT status, version FROM reimbursements"
        ).fetchone()
        runs = connection.execute(
            """
            SELECT processing_run_id, status, abandoned_at FROM processing_runs
            ORDER BY run_number
            """
        ).fetchall()
        attempts = connection.execute(
            """
            SELECT invocation_id, status, abandoned_at
            FROM processing_invocation_attempts
            """
        ).fetchall()
        recovery_events = connection.execute(
            """
            SELECT COUNT(*) FROM audit_events
            WHERE event_type IN (
                'model_invocation_abandoned',
                'processing_run_abandoned',
                'reimbursement_processing_resumed'
            )
            """
        ).fetchone()[0]
    assert reimbursement == ("processing", 2)
    assert runs == [("RUN-STRANDED", "running", None)]
    assert attempts == [("INVOCATION-STRANDED", "running", None)]
    assert recovery_events == 0


def test_finished_invocation_is_preserved_and_old_worker_cannot_finalize_after_takeover(
    tmp_path,
) -> None:
    database_path = tmp_path / "finished-invocation-recovery.db"
    repository = SqliteReviewRepository(database_path)
    submission = _submission("REQ-FINISHED-RECOVERY")
    old_extractor = StubExtractor(
        receipt_date=date(2026, 4, 10),
        total="100.00",
        invoked_at=NOW,
    )
    old_service = ProcessingService(
        CrashAfterFinishRepository(repository),  # type: ignore[arg-type]
        old_extractor,
        clock=lambda: NOW,
        run_id_factory=lambda: "RUN-FINISHED-OLD",
        invocation_id_factory=lambda: "INV-FINISHED-OLD",
        decision_id_factory=lambda: "DEC-OLD-UNUSED",
        event_id_factory=iter(f"FINISHED-OLD-EVENT-{i}" for i in range(20)).__next__,
        processing_lease=timedelta(minutes=5),
    )
    with pytest.raises(RuntimeError, match="after invocation completion"):
        old_service.process(
            submission,
            actor=AuditActor("submitter", "user-42"),
            correlation_id="corr-finished-old",
        )

    recovery_time = NOW + timedelta(minutes=6)
    new_extractor = StubExtractor(
        receipt_date=date(2026, 4, 10),
        total="100.00",
        invoked_at=recovery_time,
    )
    restarted = SqliteReviewRepository(database_path)
    recovered = ProcessingService(
        restarted,
        new_extractor,
        clock=lambda: recovery_time,
        run_id_factory=lambda: "RUN-FINISHED-NEW",
        invocation_id_factory=lambda: "INV-FINISHED-NEW",
        decision_id_factory=lambda: "DEC-FINISHED-NEW",
        event_id_factory=iter(f"FINISHED-NEW-EVENT-{i}" for i in range(30)).__next__,
        processing_lease=timedelta(minutes=5),
    ).process(
        submission,
        actor=AuditActor("submitter", "user-42"),
        correlation_id="corr-finished-new",
    )

    assert recovered.recovered is True
    assert recovered.result.status is ReimbursementStatus.AUTO_APPROVED
    assert recovered.result.automated_decision is not None

    old_extraction = StubExtractor(
        receipt_date=date(2026, 4, 10),
        total="100.00",
        invoked_at=NOW,
    ).extract(submission)
    with pytest.raises(RequestConflictError, match="no longer processing"):
        restarted.complete_processing(
            request_id=submission.request_id,
            processing_run_id="RUN-FINISHED-OLD",
            extraction=old_extraction,
            source_invocation_id="INV-FINISHED-OLD",
            automated_decision=recovered.result.automated_decision,
            problems=(),
            expected_version=2,
            resulting_status=ReimbursementStatus.AUTO_APPROVED,
            completed_at=recovery_time,
            decision_event=_event(
                "OLD-WORKER-DECISION-EVENT",
                submission.request_id,
                "automated_decision_recorded",
                AuditActor("system", "deterministic-policy-engine"),
            ),
            review_event=None,
        )

    with sqlite3.connect(database_path) as connection:
        attempts = connection.execute(
            """
            SELECT invocation_id, status, abandoned_at
            FROM processing_invocation_attempts ORDER BY invoked_at, invocation_id
            """
        ).fetchall()
        old_run = connection.execute(
            """
            SELECT status, abandoned_at FROM processing_runs
            WHERE processing_run_id = 'RUN-FINISHED-OLD'
            """
        ).fetchone()
        decision_count = connection.execute(
            "SELECT COUNT(*) FROM automated_decisions"
        ).fetchone()[0]
    assert attempts == [
        ("INV-FINISHED-OLD", "succeeded", None),
        ("INV-FINISHED-NEW", "succeeded", None),
    ]
    assert old_run is not None and old_run[0] == "failed" and old_run[1] is not None
    assert decision_count == 1


def test_claimed_minor_units_cannot_diverge_from_the_immutable_submission(tmp_path) -> None:
    database_path = tmp_path / "immutable-minor-units.db"
    repository = SqliteReviewRepository(database_path)
    submission = _submission("REQ-IMMUTABLE-AMOUNT")
    _service(
        repository,
        StubExtractor(receipt_date=date(2026, 4, 10), total="100.00"),
    ).process(
        submission,
        actor=AuditActor("submitter", "user-42"),
        correlation_id="corr-immutable-amount",
    )

    with sqlite3.connect(database_path) as connection:
        before = connection.execute(
            """
            SELECT claimed_amount, claimed_amount_minor, submission_hash
            FROM reimbursements WHERE request_id = ?
            """,
            (submission.request_id,),
        ).fetchone()
        with pytest.raises(sqlite3.IntegrityError, match="submission is immutable"):
            connection.execute(
                """
                UPDATE reimbursements SET claimed_amount_minor = 1
                WHERE request_id = ?
                """,
                (submission.request_id,),
            )
        after = connection.execute(
            """
            SELECT claimed_amount, claimed_amount_minor, submission_hash
            FROM reimbursements WHERE request_id = ?
            """,
            (submission.request_id,),
        ).fetchone()

    assert before == ("100.00", 10_000, submission_fingerprint(submission))
    assert after == before


def test_existing_database_receives_versioned_minor_unit_immutability_trigger(tmp_path) -> None:
    database_path = tmp_path / "minor-unit-trigger-upgrade.db"
    repository = SqliteReviewRepository(database_path)
    submission = _submission("REQ-MINOR-TRIGGER-UPGRADE")
    _service(
        repository,
        StubExtractor(receipt_date=date(2026, 4, 10), total="100.00"),
    ).process(
        submission,
        actor=AuditActor("submitter", "user-42"),
        correlation_id="corr-minor-trigger-upgrade",
    )

    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            DROP TRIGGER reimbursements_claimed_amount_minor_immutable_v2;
            DROP TRIGGER reimbursements_submission_immutable;
            CREATE TRIGGER reimbursements_submission_immutable
            BEFORE UPDATE OF
                submission_hash, submitted_by, submitted_at, raw_ocr_text,
                claimed_category, claimed_amount, currency, opened_at
            ON reimbursements
            BEGIN
                SELECT RAISE(ABORT, 'reimbursement submission is immutable');
            END;
            """
        )

    SqliteReviewRepository(database_path)

    with sqlite3.connect(database_path) as connection:
        installed = connection.execute(
            """
            SELECT COUNT(*) FROM sqlite_master
            WHERE type = 'trigger'
              AND name = 'reimbursements_claimed_amount_minor_immutable_v2'
            """
        ).fetchone()
        assert installed == (1,)
        with pytest.raises(sqlite3.IntegrityError, match="submission is immutable"):
            connection.execute(
                """
                UPDATE reimbursements SET claimed_amount_minor = 1
                WHERE request_id = ?
                """,
                (submission.request_id,),
            )


def test_pre_lease_running_database_is_migrated_with_a_bounded_active_lease(
    tmp_path,
) -> None:
    database_path = tmp_path / "pre-lease-running.db"
    repository = SqliteReviewRepository(database_path)
    submission = _submission("REQ-PRE-LEASE")
    repository.register_received(
        submission,
        submission_hash=submission_fingerprint(submission),
        opened_at=NOW,
        audit_event=_event(
            "PRE-LEASE-RECEIVED",
            submission.request_id,
            "reimbursement_received",
            AuditActor("submitter", "user-42"),
        ),
    )
    input_hash = hashlib.sha256(submission.raw_ocr_text.encode("utf-8")).hexdigest()

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.executescript(
            """
            DROP TABLE processing_invocation_attempts;
            DROP TABLE processing_runs;

            CREATE TABLE processing_runs (
                processing_run_id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL REFERENCES reimbursements(request_id),
                run_number INTEGER NOT NULL CHECK (run_number >= 1),
                pipeline_version TEXT NOT NULL,
                input_hash TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
                started_at TEXT NOT NULL,
                completed_at TEXT,
                error TEXT,
                correlation_id TEXT NOT NULL,
                UNIQUE (request_id, run_number),
                UNIQUE (processing_run_id, request_id)
            );

            CREATE TABLE processing_invocation_attempts (
                invocation_id TEXT PRIMARY KEY,
                processing_run_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                attempt INTEGER NOT NULL CHECK (attempt >= 1),
                status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                prompt_hash TEXT NOT NULL,
                input_hash TEXT NOT NULL,
                output_hash TEXT,
                raw_response TEXT,
                error TEXT,
                invoked_at TEXT NOT NULL,
                completed_at TEXT,
                duration_ms INTEGER,
                parameters_json TEXT NOT NULL,
                UNIQUE (processing_run_id, stage, attempt),
                FOREIGN KEY (processing_run_id, request_id)
                    REFERENCES processing_runs(processing_run_id, request_id)
            );
            """
        )
        connection.execute(
            """
            UPDATE reimbursements SET status = 'processing', version = 2
            WHERE request_id = ?
            """,
            (submission.request_id,),
        )
        connection.execute(
            """
            INSERT INTO processing_runs (
                processing_run_id, request_id, run_number, pipeline_version,
                input_hash, status, started_at, completed_at, error, correlation_id
            ) VALUES (?, ?, 1, 'baseline-v1', ?, 'running', ?, NULL, NULL, 'legacy-corr')
            """,
            ("RUN-PRE-LEASE", submission.request_id, input_hash, NOW.isoformat()),
        )
        connection.execute(
            """
            INSERT INTO processing_invocation_attempts (
                invocation_id, processing_run_id, request_id, stage, attempt,
                status, provider, model, prompt_version, prompt_hash, input_hash,
                output_hash, raw_response, error, invoked_at, completed_at,
                duration_ms, parameters_json
            ) VALUES (
                'INV-PRE-LEASE', 'RUN-PRE-LEASE', ?, 'primary_extractor', 1,
                'running', 'test-provider', 'test-model-v1', 'test-prompt-v1',
                'prompt-sha256', ?, NULL, NULL, NULL, ?, NULL, NULL, '{}'
            )
            """,
            (submission.request_id, input_hash, NOW.isoformat()),
        )

    migrated = SqliteReviewRepository(database_path)
    active_time = NOW + timedelta(minutes=4)
    extractor = StubExtractor(
        receipt_date=date(2026, 4, 10),
        total="100.00",
        invoked_at=active_time,
    )
    replay = ProcessingService(
        migrated,
        extractor,
        clock=lambda: active_time,
        run_id_factory=lambda: "RUN-MIGRATION-NOT-ACQUIRED",
        invocation_id_factory=lambda: "INV-MIGRATION-NOT-STARTED",
        decision_id_factory=lambda: "DEC-MIGRATION-NOT-CREATED",
        event_id_factory=iter(f"MIGRATION-EVENT-{i}" for i in range(20)).__next__,
        processing_lease=timedelta(minutes=5),
    ).process(
        submission,
        actor=AuditActor("submitter", "user-42"),
        correlation_id="corr-migrated-active",
    )

    assert replay.replayed is True
    assert replay.result.status is ReimbursementStatus.PROCESSING
    assert extractor.calls == 0
    with sqlite3.connect(database_path) as connection:
        run_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(processing_runs)")
        }
        invocation_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(processing_invocation_attempts)"
            )
        }
        lease = connection.execute(
            """
            SELECT lease_expires_at, abandoned_at FROM processing_runs
            WHERE processing_run_id = 'RUN-PRE-LEASE'
            """
        ).fetchone()
    assert {"lease_expires_at", "abandoned_at"} <= run_columns
    assert "abandoned_at" in invocation_columns
    assert lease is not None
    assert datetime.fromisoformat(lease[0]) == NOW + timedelta(minutes=5)
    assert lease[1] is None


def test_legacy_workflow_backfill_rolls_back_as_one_transaction(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "legacy-backfill-rollback.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE reimbursements (
                request_id TEXT PRIMARY KEY,
                submitted_by TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                raw_ocr_text TEXT NOT NULL,
                claimed_category TEXT NOT NULL,
                claimed_amount TEXT NOT NULL,
                currency TEXT NOT NULL,
                opened_at TEXT NOT NULL,
                status TEXT NOT NULL,
                version INTEGER NOT NULL
            );
            INSERT INTO reimbursements VALUES (
                'LEGACY-ATOMIC', 'legacy@example.com', '2026-04-10T12:00:00+00:00',
                'LEGACY OCR', 'meals', '100.00', 'BRL',
                '2026-04-10T12:00:00+00:00', 'received', 1
            );
            """
        )

    def fail_after_partial_backfill(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
                INSERT INTO processing_runs (
                    processing_run_id, request_id, run_number, pipeline_version,
                    input_hash, status, started_at, lease_expires_at,
                    completed_at, error, correlation_id
                ) VALUES (
                    'PARTIAL-RUN', 'LEGACY-ATOMIC', 1, 'legacy-test-v1',
                    'legacy-input-hash', 'running', '2026-04-10T12:00:00+00:00',
                    '2026-04-10T12:05:00+00:00', NULL, NULL, 'legacy:test'
                )
            """
        )
        raise RuntimeError("injected legacy backfill failure")

    with monkeypatch.context() as patch:
        patch.setattr(
            SqliteReviewRepository,
            "_backfill_workflow_records",
            staticmethod(fail_after_partial_backfill),
        )
        with pytest.raises(RuntimeError, match="injected legacy backfill failure"):
            SqliteReviewRepository(database_path)

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM processing_runs").fetchone()[0] == 0

    recovered = SqliteReviewRepository(database_path)
    with sqlite3.connect(recovered.database_path) as connection:
        migrated = connection.execute(
            """
            SELECT claimed_amount_minor, submission_hash
            FROM reimbursements WHERE request_id = 'LEGACY-ATOMIC'
            """
        ).fetchone()
        assert connection.execute("SELECT COUNT(*) FROM processing_runs").fetchone()[0] == 0
    assert migrated is not None
    assert migrated[0] == 10_000
    assert isinstance(migrated[1], str) and migrated[1]


def test_repository_supports_multiple_immutable_attempts_without_business_timeline_leak(
    tmp_path,
) -> None:
    database_path = tmp_path / "attempts.db"
    repository = SqliteReviewRepository(database_path)
    submission = _submission("REQ-ATTEMPTS")
    actor = AuditActor("submitter", "user-42")
    created, received = repository.register_received(
        submission,
        submission_hash=submission_fingerprint(submission),
        opened_at=NOW,
        audit_event=_event("EVENT-RECEIVED", submission.request_id, "reimbursement_received", actor),
    )
    assert created is True
    input_hash = hashlib.sha256(submission.raw_ocr_text.encode("utf-8")).hexdigest()
    version = repository.start_processing(
        request_id=submission.request_id,
        processing_run_id="RUN-MULTI",
        pipeline_version="baseline-v1",
        input_hash=input_hash,
        expected_version=received.version,
        started_at=NOW,
        correlation_id="corr-test",
        audit_event=_event(
            "EVENT-PROCESSING",
            submission.request_id,
            "reimbursement_processing_started",
            AuditActor("system", "processing-orchestrator"),
        ),
    )
    assert version == 2

    for attempt, status, raw, error in (
        (1, InvocationStatus.FAILED, "timeout", "provider timeout"),
        (2, InvocationStatus.SUCCEEDED, '{"total":"100.00"}', None),
    ):
        running = _invocation(attempt, InvocationStatus.RUNNING, input_hash=input_hash)
        repository.begin_invocation(
            running,
            audit_event=_event(
                f"EVENT-START-{attempt}",
                submission.request_id,
                "model_invocation_started",
                AuditActor("system", "extractor:test-provider"),
            ),
        )
        terminal = _invocation(
            attempt,
            status,
            input_hash=input_hash,
            raw=raw,
            error=error,
        )
        repository.finish_invocation(
            terminal,
            raw_response=raw,
            audit_event=_event(
                f"EVENT-END-{attempt}",
                submission.request_id,
                "model_invocation_completed",
                AuditActor("system", "extractor:test-provider"),
            ),
        )

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT attempt, status FROM processing_invocation_attempts
            ORDER BY attempt
            """
        ).fetchall()
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                """
                UPDATE processing_invocation_attempts SET error = 'changed'
                WHERE invocation_id = 'INV-1'
                """
            )
    assert rows == [(1, "failed"), (2, "succeeded")]
    timeline = ReviewService(repository).list_events(
        submission.request_id,
        ReviewEventQuery(page_size=100),
    )
    assert {event.event_type for event in timeline.items} == {
        "reimbursement_received",
        "reimbursement_processing_started",
    }


def _event(
    event_id: str,
    request_id: str,
    event_type: str,
    actor: AuditActor,
) -> AuditEvent:
    return AuditEvent(
        event_id=event_id,
        request_id=request_id,
        event_type=event_type,
        occurred_at=NOW,
        actor=actor,
        correlation_id="corr-test",
    )


def _invocation(
    attempt: int,
    status: InvocationStatus,
    *,
    input_hash: str,
    raw: str = "",
    error: str | None = None,
) -> InvocationSummary:
    terminal = status is not InvocationStatus.RUNNING
    return InvocationSummary(
        invocation_id=f"INV-{attempt}",
        processing_run_id="RUN-MULTI",
        stage="primary_extractor",
        attempt=attempt,
        status=status,
        provider="test-provider",
        model="test-model-v1",
        prompt_version="test-prompt-v1",
        prompt_hash="prompt-sha256",
        input_hash=input_hash,
        output_hash=hashlib.sha256(raw.encode("utf-8")).hexdigest() if terminal else None,
        invoked_at=NOW,
        completed_at=NOW if terminal else None,
        duration_ms=17 if terminal else None,
        error=error,
    )
