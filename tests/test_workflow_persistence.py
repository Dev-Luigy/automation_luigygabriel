import hashlib
import sqlite3
from dataclasses import replace
from datetime import UTC, date, datetime

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

    def __init__(self, *, receipt_date: date, total: str, category: str = "meals") -> None:
        self.receipt_date = receipt_date
        self.total = total
        self.category = category
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
                invoked_at=NOW,
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
                input_hash, status, started_at, completed_at, error, correlation_id
            ) VALUES (
                'PARTIAL-RUN', 'LEGACY-ATOMIC', 1, 'legacy-test-v1',
                'legacy-input-hash', 'running', '2026-04-10T12:00:00+00:00',
                NULL, NULL, 'legacy:test'
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
