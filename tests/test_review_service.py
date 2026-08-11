from dataclasses import replace
from datetime import UTC, datetime

import pytest

from expense_agent.application import ExecutionIdentity
from expense_agent.application.review import (
    ReviewAuthorizationError,
    ReviewCaseDetails,
    ReviewCaseStatus,
    ReviewConflictError,
    ReviewDecisionResult,
    ReviewerIdentity,
    ReviewNotFoundError,
    ReviewProblem,
    ReviewQueueItem,
    ReviewService,
    decision_idempotency_key_hash,
    review_decision_command_fingerprint,
)
from expense_agent.domain import (
    AttachmentReference,
    AutomatedDecision,
    DecisionReason,
    DomainValidationError,
    Money,
    PolicyDecisionRoute,
    ReimbursementStatus,
    ReimbursementSubmission,
    ReviewOutcome,
    RuleEvaluation,
    RuleOutcome,
)

OPENED_AT = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
DECIDED_AT = datetime(2026, 4, 10, 9, 5, tzinfo=UTC)
REVIEWED_AT = datetime(2026, 4, 10, 10, 0, tzinfo=UTC)


def _details() -> ReviewCaseDetails:
    submission = ReimbursementSubmission(
        request_id="REQ-1001",
        submitted_by="employee@company.com",
        submitted_at=OPENED_AT,
        raw_ocr_text="MERCHANT CAFE TOTAL R$ 93.50",
        claimed_category="meals",
        claimed_amount=Money.brl("93.50"),
        attachments=(AttachmentReference("receipts/REQ-1001.jpg"),),
    )
    automated = AutomatedDecision(
        decision_id="AUTO-1001",
        request_id=submission.request_id,
        route=PolicyDecisionRoute.HUMAN_REVIEW,
        decided_at=DECIDED_AT,
        policy_version="policy-v3",
        reasons=(
            DecisionReason(
                code="TOTAL_MISMATCH",
                message="Claimed and extracted totals differ",
                evidence={"claimed": "93.50", "extracted": "89.50"},
            ),
        ),
        rule_evaluations=(
            RuleEvaluation(
                rule_id="receipt-total-match",
                rule_version="2",
                outcome=RuleOutcome.REVIEW,
                message="Totals do not match",
                facts={"difference": "4.00"},
            ),
        ),
    )
    return ReviewCaseDetails(
        submission=submission,
        opened_at=OPENED_AT,
        status=ReimbursementStatus.PENDING_REVIEW,
        version=1,
        review_status=ReviewCaseStatus.PENDING,
        pending_since=DECIDED_AT,
        extraction=None,
        problems=(ReviewProblem(code="TOTAL_MISMATCH", message="Check the receipt total"),),
        automated_decision=automated,
        submission_actor_id="employee-directory:submitter",
    )


class FakeReviewRepository:
    def __init__(self, details: ReviewCaseDetails | None) -> None:
        self.details = details
        self.write = None

    def list_pending(self) -> tuple[ReviewQueueItem, ...]:
        return ()

    def get(self, request_id: str) -> ReviewCaseDetails | None:
        if self.details is not None and self.details.request_id == request_id:
            return self.details
        return None

    def find_human_decision_by_idempotency(self, **_query):
        return None

    def record_human_decision(self, **write):
        self.write = write
        return ReviewDecisionResult(
            decision=write["decision"],
            resulting_status=write["resulting_status"],
            version=write["expected_version"] + 1,
            audit_event_id=write["audit_event"].event_id,
            replayed=False,
        )


def test_service_uses_canonical_reviewer_and_aggregate_transition() -> None:
    repository = FakeReviewRepository(_details())
    reviewer = ReviewerIdentity(
        reviewer_id="user-42",
        email="manager@company.com",
        display_name="Review Manager",
    )
    service = ReviewService(
        repository,
        clock=lambda: REVIEWED_AT,
        decision_id_factory=lambda: "HUMAN-1001",
        event_id_factory=lambda: "AUDIT-1001",
        execution_identity=ExecutionIdentity(
            build_id="git-test-lock-test",
            configuration_hash="a" * 64,
        ),
    )

    result = service.decide(
        request_id="REQ-1001",
        outcome=ReviewOutcome.APPROVED,
        reason="Receipt and card statement confirm the purchase.",
        reviewer=reviewer,
        expected_version=1,
        correlation_id="corr-1001",
        idempotency_key="decision-key-1001",
        evidence_integrity="verified",
    )

    assert result.resulting_status is ReimbursementStatus.APPROVED_AFTER_REVIEW
    assert result.version == 2
    assert result.decision.reviewer == "user-42"
    assert repository.write is not None
    assert repository.write["reviewer"] == reviewer
    audit = repository.write["audit_event"]
    assert audit.actor.actor_id == "user-42"
    assert audit.payload["request_version"] == 1
    assert audit.payload["to_status"] == "approved_after_review"
    assert audit.payload["build_id"] == "git-test-lock-test"
    assert audit.payload["configuration_hash"] == "a" * 64
    assert audit.payload["evidence_integrity"] == "verified"


def test_service_rejects_missing_or_stale_cases() -> None:
    missing_service = ReviewService(FakeReviewRepository(None))
    with pytest.raises(ReviewNotFoundError):
        missing_service.get("REQ-missing")

    stale = _details()
    stale = ReviewCaseDetails(
        submission=stale.submission,
        opened_at=stale.opened_at,
        status=stale.status,
        version=2,
        review_status=stale.review_status,
        pending_since=stale.pending_since,
        extraction=stale.extraction,
        problems=stale.problems,
        automated_decision=stale.automated_decision,
    )
    service = ReviewService(FakeReviewRepository(stale))
    with pytest.raises(ReviewConflictError, match="expected version"):
        service.decide(
            request_id=stale.request_id,
            outcome=ReviewOutcome.REJECTED,
            reason="Invalid receipt",
            reviewer=ReviewerIdentity("user-1", "reviewer@company.com", "Reviewer"),
            expected_version=1,
            correlation_id="corr-stale",
            idempotency_key="decision-key-stale",
            evidence_integrity="verified",
        )

def test_service_requires_a_reason_and_typed_authenticated_identity() -> None:
    service = ReviewService(FakeReviewRepository(_details()), clock=lambda: REVIEWED_AT)
    reviewer = ReviewerIdentity("user-1", "reviewer@company.com", "Reviewer")

    with pytest.raises(DomainValidationError, match="reason"):
        service.decide(
            request_id="REQ-1001",
            outcome=ReviewOutcome.REJECTED,
            reason="   ",
            reviewer=reviewer,
            expected_version=1,
            correlation_id="corr-1",
            idempotency_key="decision-key-reason",
            evidence_integrity="verified",
        )

    with pytest.raises(DomainValidationError, match="ReviewerIdentity"):
        service.decide(
            request_id="REQ-1001",
            outcome=ReviewOutcome.REJECTED,
            reason="Invalid receipt",
            reviewer="forged-user",  # type: ignore[arg-type]
            expected_version=1,
            correlation_id="corr-2",
            idempotency_key="decision-key-identity",
            evidence_integrity="verified",
        )


@pytest.mark.parametrize(
    "details",
    (
        replace(_details(), submission_actor_id=None),
        replace(_details(), submission_actor_id="user-1"),
        replace(
            _details(),
            submission=replace(
                _details().submission,
                submitted_by="reviewer@company.com",
            ),
        ),
    ),
)
def test_service_enforces_separation_of_duties_for_every_adapter(details) -> None:
    service = ReviewService(FakeReviewRepository(details), clock=lambda: REVIEWED_AT)

    with pytest.raises(ReviewAuthorizationError):
        service.decide(
            request_id="REQ-1001",
            outcome=ReviewOutcome.REJECTED,
            reason="Separation of duties must be enforced.",
            reviewer=ReviewerIdentity("user-1", "reviewer@company.com", "Reviewer"),
            expected_version=1,
            correlation_id="corr-four-eyes",
            idempotency_key="decision-key-four-eyes",
            evidence_integrity="missing",
        )


def test_service_never_approves_without_verified_original_evidence() -> None:
    service = ReviewService(FakeReviewRepository(_details()), clock=lambda: REVIEWED_AT)

    with pytest.raises(DomainValidationError, match="verified original evidence"):
        service.decide(
            request_id="REQ-1001",
            outcome=ReviewOutcome.APPROVED,
            reason="Approval cannot trust unavailable evidence.",
            reviewer=ReviewerIdentity("user-1", "reviewer@company.com", "Reviewer"),
            expected_version=1,
            correlation_id="corr-evidence",
            idempotency_key="decision-key-unverified-evidence",
            evidence_integrity="missing",
        )

def test_service_does_not_allow_human_approval_to_override_mandatory_rejection() -> None:
    details = _details()
    mandatory_decision = replace(
        details.automated_decision,
        reasons=(
            DecisionReason(
                code="RECEIPT_TOO_OLD",
                message="Receipt exceeds the mandatory age limit.",
            ),
            DecisionReason(
                code="HIGH_VALUE_REVIEW_REQUIRED",
                message="High-value gate requires human review.",
            ),
        ),
        rule_evaluations=(
            RuleEvaluation(
                rule_id="receipt-age",
                rule_version="1.1.0",
                outcome=RuleOutcome.REJECT,
                message="Receipt must be rejected.",
            ),
            RuleEvaluation(
                rule_id="claim-amount-threshold",
                rule_version="1.1.0",
                outcome=RuleOutcome.REVIEW,
                message="High-value claim requires human review.",
            ),
        ),
    )
    service = ReviewService(
        FakeReviewRepository(replace(details, automated_decision=mandatory_decision)),
        clock=lambda: REVIEWED_AT,
    )
    reviewer = ReviewerIdentity("user-1", "reviewer@company.com", "Reviewer")

    with pytest.raises(DomainValidationError, match="prevents approval"):
        service.decide(
            request_id=details.request_id,
            outcome=ReviewOutcome.APPROVED,
            reason="Attempted override",
            reviewer=reviewer,
            expected_version=details.version,
            correlation_id="corr-mandatory-reject",
            idempotency_key="decision-key-mandatory",
            evidence_integrity="verified",
        )


@pytest.mark.parametrize(
    "raw_key",
    (
        "short",
        "contains space",
        "contains\tcontrol",
        "não-ascii-key",
        "x" * 129,
    ),
)
def test_decision_idempotency_key_is_bounded_visible_ascii(raw_key: str) -> None:
    with pytest.raises(DomainValidationError, match="idempotency key"):
        decision_idempotency_key_hash(raw_key)

    assert len(decision_idempotency_key_hash("12345678")) == 64
    assert len(decision_idempotency_key_hash("x" * 128)) == 64


def test_command_fingerprint_uses_normalized_reason_and_binds_expected_version() -> None:
    common = {
        "request_id": "REQ-1001",
        "outcome": ReviewOutcome.REJECTED,
        "reviewer_id": "reviewer-1",
    }
    normalized = review_decision_command_fingerprint(
        **common,
        reason="Evidence mismatch.",
        expected_version=3,
    )

    assert normalized == review_decision_command_fingerprint(
        **common,
        reason="  Evidence mismatch.  ",
        expected_version=3,
    )
    assert normalized != review_decision_command_fingerprint(
        **common,
        reason="Evidence mismatch.",
        expected_version=4,
    )
