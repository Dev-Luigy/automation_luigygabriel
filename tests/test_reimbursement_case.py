from datetime import UTC, datetime

import pytest

from expense_agent.domain import (
    AttachmentReference,
    AutomatedDecision,
    DecisionReason,
    DomainValidationError,
    HumanDecision,
    InvalidStateTransition,
    Money,
    PolicyDecisionRoute,
    ReimbursementCase,
    ReimbursementStatus,
    ReimbursementSubmission,
    ReviewOutcome,
    RuleEvaluation,
    RuleOutcome,
)

NOW = datetime(2026, 4, 10, 9, 15, tzinfo=UTC)


def submission() -> ReimbursementSubmission:
    return ReimbursementSubmission(
        request_id="REQ-0001",
        submitted_by="ana.silva@company.com",
        submitted_at=NOW,
        raw_ocr_text="TOTAL R$ 93.50",
        claimed_category="meals",
        claimed_amount=Money.brl("93.50"),
        attachments=(AttachmentReference("receipt_0001.jpg"),),
    )


def automated_decision(route: PolicyDecisionRoute) -> AutomatedDecision:
    outcome = {
        PolicyDecisionRoute.AUTO_APPROVED: RuleOutcome.PASS,
        PolicyDecisionRoute.HUMAN_REVIEW: RuleOutcome.REVIEW,
        PolicyDecisionRoute.REJECTED: RuleOutcome.REJECT,
    }[route]
    return AutomatedDecision(
        decision_id="DEC-0001",
        request_id="REQ-0001",
        route=route,
        decided_at=NOW,
        policy_version="baseline-v1",
        reasons=(DecisionReason(code="TEST_REASON", message="Test decision"),),
        rule_evaluations=(
            RuleEvaluation(
                rule_id="test-rule",
                rule_version="1",
                outcome=outcome,
                message="Rule evaluated for test",
            ),
        ),
    )


def test_human_review_workflow_is_explicit_and_append_only() -> None:
    case = ReimbursementCase(submission=submission(), opened_at=NOW)

    case.start_processing()
    case.record_automated_decision(automated_decision(PolicyDecisionRoute.HUMAN_REVIEW))

    assert case.status is ReimbursementStatus.PENDING_REVIEW

    human_decision = HumanDecision(
        decision_id="DEC-0002",
        request_id="REQ-0001",
        outcome=ReviewOutcome.APPROVED,
        reviewer="manager@company.com",
        reason="The expense was pre-authorized",
        decided_at=NOW,
    )
    case.record_human_decision(human_decision)

    assert case.status is ReimbursementStatus.APPROVED_AFTER_REVIEW
    assert case.decisions == (automated_decision(PolicyDecisionRoute.HUMAN_REVIEW), human_decision)


def test_case_cannot_skip_directly_to_human_decision() -> None:
    case = ReimbursementCase(submission=submission(), opened_at=NOW)
    decision = HumanDecision(
        decision_id="DEC-0002",
        request_id="REQ-0001",
        outcome=ReviewOutcome.REJECTED,
        reviewer="manager@company.com",
        reason="Receipt is not eligible",
        decided_at=NOW,
    )

    with pytest.raises(InvalidStateTransition):
        case.record_human_decision(decision)


def test_mandatory_rejection_rule_requires_rejected_human_outcome() -> None:
    case = ReimbursementCase(submission=submission(), opened_at=NOW)
    case.start_processing()
    case.record_automated_decision(
        AutomatedDecision(
            decision_id="DEC-MANDATORY-REJECT",
            request_id="REQ-0001",
            route=PolicyDecisionRoute.HUMAN_REVIEW,
            decided_at=NOW,
            policy_version="baseline-v2",
            reasons=(
                DecisionReason(
                    code="RECEIPT_TOO_OLD",
                    message="Receipt is older than the policy limit.",
                ),
            ),
            rule_evaluations=(
                RuleEvaluation(
                    rule_id="receipt-age",
                    rule_version="1.1.0",
                    outcome=RuleOutcome.REJECT,
                    message="Receipt must be rejected.",
                ),
            ),
        )
    )
    approval = HumanDecision(
        decision_id="DEC-APPROVE",
        request_id="REQ-0001",
        outcome=ReviewOutcome.APPROVED,
        reviewer="manager@company.com",
        reason="Attempted override",
        decided_at=NOW,
    )

    with pytest.raises(DomainValidationError, match="prevents approval"):
        case.record_human_decision(approval)

    rejection = HumanDecision(
        decision_id="DEC-REJECT",
        request_id="REQ-0001",
        outcome=ReviewOutcome.REJECTED,
        reviewer="manager@company.com",
        reason="Confirmed mandatory age rejection",
        decided_at=NOW,
    )
    case.record_human_decision(rejection)
    assert case.status is ReimbursementStatus.REJECTED


def test_case_rejects_decision_for_another_request() -> None:
    case = ReimbursementCase(submission=submission(), opened_at=NOW)
    case.start_processing()
    wrong_decision = AutomatedDecision(
        decision_id="DEC-9999",
        request_id="REQ-9999",
        route=PolicyDecisionRoute.REJECTED,
        decided_at=NOW,
        policy_version="baseline-v1",
        reasons=(DecisionReason(code="OLD_RECEIPT", message="Receipt is too old"),),
        rule_evaluations=(
            RuleEvaluation(
                rule_id="receipt-age",
                rule_version="1",
                outcome=RuleOutcome.REJECT,
                message="Receipt exceeds 90 days",
            ),
        ),
    )

    with pytest.raises(DomainValidationError, match="does not match"):
        case.record_automated_decision(wrong_decision)


def test_submission_requires_timezone_aware_datetime() -> None:
    with pytest.raises(DomainValidationError, match="timezone"):
        ReimbursementSubmission(
            request_id="REQ-0001",
            submitted_by="ana.silva@company.com",
            submitted_at=datetime(2026, 4, 10, 9, 15),  # noqa: DTZ001 - deliberately naive
            raw_ocr_text="TOTAL R$ 93.50",
            claimed_category="meals",
            claimed_amount=Money.brl("93.50"),
        )
