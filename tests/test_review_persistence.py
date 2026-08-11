import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime

import pytest

from expense_agent.application.review import (
    ReviewCaseStatus,
    ReviewConflictError,
    ReviewerIdentity,
    ReviewProblem,
    ReviewService,
)
from expense_agent.domain import (
    AttachmentReference,
    AutomatedDecision,
    DecisionReason,
    ExtractionResult,
    ExtractionStatus,
    ModelInvocationTrace,
    Money,
    PolicyDecisionRoute,
    ReceiptFacts,
    ReimbursementCase,
    ReimbursementStatus,
    ReimbursementSubmission,
    ReviewOutcome,
    RuleEvaluation,
    RuleOutcome,
)
from expense_agent.infrastructure.review import SqliteReviewRepository

OPENED_AT = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
AUTO_AT = datetime(2026, 4, 10, 9, 5, tzinfo=UTC)
REVIEWED_AT = datetime(2026, 4, 10, 10, 0, tzinfo=UTC)


def _pending_case(request_id: str = "REQ-2001") -> tuple[ReimbursementCase, ExtractionResult]:
    submission = ReimbursementSubmission(
        request_id=request_id,
        submitted_by="employee@company.com",
        submitted_at=OPENED_AT,
        raw_ocr_text="CAFÉ <script>alert('unsafe')</script> TOTAL 89,50",
        claimed_category="meals",
        claimed_amount=Money.brl("93.50"),
        attachments=(
            AttachmentReference(f"receipts/{request_id}.jpg"),
            AttachmentReference(f"receipts/{request_id}-statement.pdf"),
        ),
    )
    case = ReimbursementCase(submission=submission, opened_at=OPENED_AT)
    case.start_processing()
    case.record_automated_decision(
        AutomatedDecision(
            decision_id=f"AUTO-{request_id}",
            request_id=request_id,
            route=PolicyDecisionRoute.HUMAN_REVIEW,
            decided_at=AUTO_AT,
            policy_version="policy-v3",
            reasons=(
                DecisionReason(
                    code="TOTAL_MISMATCH",
                    message="Claimed and extracted totals differ",
                    evidence={"extracted": "89.50", "claimed": "93.50"},
                ),
            ),
            rule_evaluations=(
                RuleEvaluation(
                    rule_id="receipt-total-match",
                    rule_version="2",
                    outcome=RuleOutcome.REVIEW,
                    message="Difference requires human judgment",
                    facts={"difference": "4.00"},
                ),
            ),
        )
    )
    extraction = ExtractionResult(
        request_id=request_id,
        status=ExtractionStatus.SUCCEEDED,
        trace=ModelInvocationTrace(
            provider="ocr-provider",
            model="receipt-extractor-v2",
            prompt_version="receipt-v4",
            prompt_hash="sha256:prompt",
            input_hash="sha256:input",
            raw_response='{"total":"89.50"}',
            invoked_at=AUTO_AT,
            duration_ms=137,
            parameters={"temperature": 0, "response_format": "json"},
        ),
        facts=ReceiptFacts(
            receipt_date=date(2026, 4, 9),
            total=Money.brl("89.50"),
            category="meals",
            merchant_name="Café Central",
            tax_id="12.345.678/0001-90",
            evidence={"total": "TOTAL 89,50"},
            warnings=("low contrast",),
        ),
    )
    return case, extraction


def _seed(repository: SqliteReviewRepository, request_id: str = "REQ-2001") -> None:
    case, extraction = _pending_case(request_id)
    repository.add_pending_case(
        case,
        extraction=extraction,
        correlation_id=f"corr-ingest-{request_id}",
        problems=(
            ReviewProblem(
                code="TOTAL_MISMATCH",
                message="Compare the claimed and receipt totals",
                evidence={"difference": "4.00"},
            ),
        ),
    )


def _service(
    repository: SqliteReviewRepository,
    *,
    decision_id: str,
    event_id: str,
) -> ReviewService:
    return ReviewService(
        repository,
        clock=lambda: REVIEWED_AT,
        decision_id_factory=lambda: decision_id,
        event_id_factory=lambda: event_id,
    )


def _reviewer() -> ReviewerIdentity:
    return ReviewerIdentity(
        reviewer_id="employee-directory:42",
        email="manager@company.com",
        display_name="Review Manager",
    )


def test_pending_case_round_trip_preserves_review_evidence(tmp_path) -> None:
    repository = SqliteReviewRepository(tmp_path / "review.db")
    _seed(repository)

    queue = repository.list_pending()
    details = repository.get("REQ-2001")

    assert len(queue) == 1
    assert queue[0].claimed_amount == Money.brl("93.50")
    assert queue[0].version == 1
    assert details is not None
    assert details.status is ReimbursementStatus.PENDING_REVIEW
    assert details.review_status is ReviewCaseStatus.PENDING
    assert details.raw_ocr_text.startswith("CAFÉ <script>")
    assert tuple(item.location for item in details.attachments) == (
        "receipts/REQ-2001.jpg",
        "receipts/REQ-2001-statement.pdf",
    )
    assert details.extraction is not None
    assert details.extraction.facts is not None
    assert details.extraction.facts.total == Money.brl("89.50")
    assert details.extraction.trace.raw_response == '{"total":"89.50"}'
    assert details.extraction.trace.parameters["temperature"] == 0
    assert details.problems[0].evidence["difference"] == "4.00"
    assert details.automated_decision.policy_version == "policy-v3"
    assert details.automated_decision.rule_evaluations[0].facts["difference"] == "4.00"
    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        initial_audit = connection.execute(
            """
            SELECT event_type, actor_type, actor_id, correlation_id, payload_json
            FROM audit_events WHERE request_id = 'REQ-2001'
            """
        ).fetchone()
    assert initial_audit is not None
    assert initial_audit[0:4] == (
        "review_case_enqueued",
        "system",
        "deterministic-policy-engine",
        "corr-ingest-REQ-2001",
    )
    assert json.loads(initial_audit[4])["automated_decision_id"] == "AUTO-REQ-2001"


def test_decision_status_and_audit_commit_atomically(tmp_path) -> None:
    database_path = tmp_path / "review.db"
    repository = SqliteReviewRepository(database_path)
    _seed(repository)
    service = _service(repository, decision_id="HUMAN-2001", event_id="AUDIT-2001")

    result = service.decide(
        request_id="REQ-2001",
        outcome=ReviewOutcome.APPROVED,
        reason="Statement confirms the claimed amount.",
        reviewer=_reviewer(),
        expected_version=1,
        correlation_id="corr-2001",
    )

    assert result.version == 2
    assert repository.list_pending() == ()
    details = repository.get("REQ-2001")
    assert details is not None
    assert details.status is ReimbursementStatus.APPROVED_AFTER_REVIEW
    assert details.review_status is ReviewCaseStatus.COMPLETED
    assert details.human_decision == result.decision
    assert details.reviewed_by == _reviewer()

    with sqlite3.connect(database_path) as connection:
        decision_row = connection.execute(
            """
            SELECT reviewer_id, reviewer_email, reason, expected_version
            FROM human_decisions WHERE request_id = 'REQ-2001'
            """
        ).fetchone()
        audit_row = connection.execute(
            """
            SELECT actor_id, correlation_id, payload_json
            FROM audit_events
            WHERE request_id = 'REQ-2001' AND event_type = 'human_review_decided'
            """
        ).fetchone()
    assert decision_row == (
        "employee-directory:42",
        "manager@company.com",
        "Statement confirms the claimed amount.",
        1,
    )
    assert audit_row is not None
    assert audit_row[0:2] == ("employee-directory:42", "corr-2001")
    assert json.loads(audit_row[2])["decision_id"] == "HUMAN-2001"
    assert audit_row[2] == json.dumps(
        json.loads(audit_row[2]),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def test_repeated_decision_is_a_conflict_and_does_not_duplicate_records(tmp_path) -> None:
    database_path = tmp_path / "review.db"
    repository = SqliteReviewRepository(database_path)
    _seed(repository)
    service = _service(repository, decision_id="HUMAN-1", event_id="AUDIT-1")
    arguments = {
        "request_id": "REQ-2001",
        "outcome": ReviewOutcome.REJECTED,
        "reason": "Receipt amount is inconsistent.",
        "reviewer": _reviewer(),
        "expected_version": 1,
        "correlation_id": "corr-1",
    }
    service.decide(**arguments)

    with pytest.raises(ReviewConflictError):
        service.decide(**arguments)

    with sqlite3.connect(database_path) as connection:
        human_count = connection.execute("SELECT COUNT(*) FROM human_decisions").fetchone()[0]
        audit_count = connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
    assert human_count == 1
    assert audit_count == 2


def test_two_concurrent_reviewers_produce_exactly_one_terminal_decision(tmp_path) -> None:
    database_path = tmp_path / "review.db"
    repository = SqliteReviewRepository(database_path)
    _seed(repository)
    barrier = threading.Barrier(2)

    class BarrierRepository:
        def list_pending(self):
            return repository.list_pending()

        def get(self, request_id):
            details = repository.get(request_id)
            barrier.wait(timeout=5)
            return details

        def record_human_decision(self, **write):
            return repository.record_human_decision(**write)

    def decide(suffix: str, outcome: ReviewOutcome) -> str:
        service = _service(
            BarrierRepository(),  # type: ignore[arg-type]
            decision_id=f"HUMAN-{suffix}",
            event_id=f"AUDIT-{suffix}",
        )
        try:
            service.decide(
                request_id="REQ-2001",
                outcome=outcome,
                reason=f"Concurrent reviewer {suffix} decision.",
                reviewer=_reviewer(),
                expected_version=1,
                correlation_id=f"corr-{suffix}",
            )
        except ReviewConflictError:
            return "conflict"
        return "committed"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(
            executor.map(
                lambda arguments: decide(*arguments),
                (("approved", ReviewOutcome.APPROVED), ("rejected", ReviewOutcome.REJECTED)),
            )
        )

    assert sorted(outcomes) == ["committed", "conflict"]
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM human_decisions").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] == 2
        status_and_version = connection.execute(
            "SELECT status, version FROM reimbursements WHERE request_id = 'REQ-2001'"
        ).fetchone()
    assert status_and_version is not None
    assert status_and_version[1] == 2
    assert status_and_version[0] in {"approved_after_review", "rejected"}


def test_late_audit_failure_rolls_back_decision_and_status(tmp_path) -> None:
    database_path = tmp_path / "review.db"
    repository = SqliteReviewRepository(database_path)
    _seed(repository, "REQ-first")
    _seed(repository, "REQ-second")
    first = _service(repository, decision_id="HUMAN-first", event_id="AUDIT-shared")
    second = _service(repository, decision_id="HUMAN-second", event_id="AUDIT-shared")
    first.decide(
        request_id="REQ-first",
        outcome=ReviewOutcome.APPROVED,
        reason="Valid receipt.",
        reviewer=_reviewer(),
        expected_version=1,
        correlation_id="corr-first",
    )

    with pytest.raises(ReviewConflictError, match="immutable record"):
        second.decide(
            request_id="REQ-second",
            outcome=ReviewOutcome.REJECTED,
            reason="Invalid receipt.",
            reviewer=_reviewer(),
            expected_version=1,
            correlation_id="corr-second",
        )

    second_details = repository.get("REQ-second")
    assert second_details is not None
    assert second_details.status is ReimbursementStatus.PENDING_REVIEW
    assert second_details.review_status is ReviewCaseStatus.PENDING
    assert second_details.version == 1
    assert second_details.human_decision is None


def test_human_decisions_and_audit_events_are_database_immutable(tmp_path) -> None:
    database_path = tmp_path / "review.db"
    repository = SqliteReviewRepository(database_path)
    _seed(repository)
    _service(repository, decision_id="HUMAN-1", event_id="AUDIT-1").decide(
        request_id="REQ-2001",
        outcome=ReviewOutcome.APPROVED,
        reason="Valid receipt.",
        reviewer=_reviewer(),
        expected_version=1,
        correlation_id="corr-1",
    )

    statements = (
        "UPDATE human_decisions SET reason = 'changed' WHERE decision_id = 'HUMAN-1'",
        "DELETE FROM human_decisions WHERE decision_id = 'HUMAN-1'",
        "UPDATE audit_events SET actor_id = 'changed' WHERE event_id = 'AUDIT-1'",
        "DELETE FROM audit_events WHERE event_id = 'AUDIT-1'",
    )
    for statement in statements:
        with (
            sqlite3.connect(database_path) as connection,
            pytest.raises(sqlite3.IntegrityError),
        ):
            connection.execute(statement)


def test_repository_can_select_delete_journal_for_sandbox_compatibility(tmp_path) -> None:
    database_path = tmp_path / "network-compatible.db"

    repository = SqliteReviewRepository(database_path, journal_mode="delete")

    assert repository.journal_mode == "DELETE"
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"


def test_repository_rejects_unsupported_journal_mode(tmp_path) -> None:
    with pytest.raises(ValueError, match="journal_mode must be WAL or DELETE"):
        SqliteReviewRepository(tmp_path / "invalid.db", journal_mode="MEMORY")
