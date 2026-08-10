from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from expense_agent.domain import (
    BASELINE_POLICY_VERSION,
    BASELINE_RULE_VERSION,
    AttachmentReference,
    BaselinePolicy,
    DomainValidationError,
    ExtractionResult,
    ExtractionStatus,
    ModelInvocationTrace,
    Money,
    PolicyDecisionRoute,
    ReceiptFacts,
    ReimbursementSubmission,
    RuleOutcome,
)

DECIDED_AT = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
SUBMITTED_AT = DECIDED_AT - timedelta(hours=1)
SAO_PAULO = ZoneInfo("America/Sao_Paulo")
SUBMISSION_DATE = SUBMITTED_AT.astimezone(SAO_PAULO).date()
VALID_RECEIPT_DATE = SUBMISSION_DATE - timedelta(days=20)


def submission(
    *,
    request_id: str = "REQ-0001",
    amount: str = "93.50",
    category: str = "meals",
    submitted_at: datetime = SUBMITTED_AT,
) -> ReimbursementSubmission:
    return ReimbursementSubmission(
        request_id=request_id,
        submitted_by="ana.silva@example.com",
        submitted_at=submitted_at,
        raw_ocr_text=f"TOTAL R$ {amount}",
        claimed_category=category,
        claimed_amount=Money.brl(amount),
        attachments=(AttachmentReference("receipt.jpg"),),
    )


def trace() -> ModelInvocationTrace:
    return ModelInvocationTrace(
        provider="deterministic-test",
        model="receipt-fixture-v1",
        prompt_version="receipt-extraction-v1",
        prompt_hash="prompt-sha256",
        input_hash="input-sha256",
        raw_response="{}",
        invoked_at=DECIDED_AT - timedelta(minutes=1),
        duration_ms=10,
        parameters={"temperature": 0},
    )


def successful_extraction(
    claim: ReimbursementSubmission,
    *,
    receipt_date: date | None = VALID_RECEIPT_DATE,
    total: Money | None = None,
    category: str | None = None,
    warnings: tuple[str, ...] = (),
) -> ExtractionResult:
    return ExtractionResult(
        request_id=claim.request_id,
        status=ExtractionStatus.SUCCEEDED,
        trace=trace(),
        facts=ReceiptFacts(
            receipt_date=receipt_date,
            total=claim.claimed_amount if total is None else total,
            category=claim.claimed_category if category is None else category,
            merchant_name="Bistro Central",
            warnings=warnings,
        ),
    )


def evaluate(
    claim: ReimbursementSubmission,
    extraction: ExtractionResult,
    *,
    decision_id: str = "DEC-0001",
    decided_at: datetime = DECIDED_AT,
):
    return BaselinePolicy().evaluate(
        claim,
        extraction,
        decision_id=decision_id,
        decided_at=decided_at,
    )


@pytest.mark.parametrize("amount", ["0.01", "199.99", "200.00"])
def test_at_or_below_200_is_auto_approved_only_when_every_rule_passes(amount: str) -> None:
    claim = submission(amount=amount)

    decision = evaluate(claim, successful_extraction(claim))

    assert decision.route is PolicyDecisionRoute.AUTO_APPROVED
    assert [reason.code for reason in decision.reasons] == ["AUTO_APPROVAL_ELIGIBLE"]
    assert all(item.outcome is RuleOutcome.PASS for item in decision.rule_evaluations)


@pytest.mark.parametrize(
    ("amount", "reason_code"),
    [
        ("200.01", "AMOUNT_REQUIRES_HUMAN_REVIEW"),
        ("2000.00", "AMOUNT_REQUIRES_HUMAN_REVIEW"),
        ("2000.01", "HIGH_VALUE_REVIEW_REQUIRED"),
    ],
)
def test_amounts_above_200_are_routed_to_human_review(
    amount: str,
    reason_code: str,
) -> None:
    claim = submission(amount=amount)

    decision = evaluate(claim, successful_extraction(claim))

    assert decision.route is PolicyDecisionRoute.HUMAN_REVIEW
    assert reason_code in {reason.code for reason in decision.reasons}
    threshold = next(
        item for item in decision.rule_evaluations if item.rule_id == "claim-amount-threshold"
    )
    assert threshold.outcome is RuleOutcome.REVIEW


def test_exactly_90_days_old_is_valid() -> None:
    claim = submission(amount="200.00")
    receipt_date = SUBMISSION_DATE - timedelta(days=90)

    decision = evaluate(
        claim,
        successful_extraction(claim, receipt_date=receipt_date),
    )

    assert decision.route is PolicyDecisionRoute.AUTO_APPROVED
    age = next(item for item in decision.rule_evaluations if item.rule_id == "receipt-age")
    assert age.outcome is RuleOutcome.PASS
    assert age.facts["age_days"] == "90"
    assert age.facts["submission_date"] == SUBMISSION_DATE.isoformat()
    assert age.facts["business_timezone"] == "America/Sao_Paulo"


def test_receipt_older_than_90_days_is_rejected_before_other_routes() -> None:
    claim = submission(amount="2500.00", category="lodging")
    extraction = successful_extraction(
        claim,
        receipt_date=SUBMISSION_DATE - timedelta(days=91),
        category="meals",
        warnings=("category confidence below threshold",),
    )

    decision = evaluate(claim, extraction)

    assert decision.route is PolicyDecisionRoute.REJECTED
    assert "RECEIPT_TOO_OLD" in {reason.code for reason in decision.reasons}
    assert "HIGH_VALUE_REVIEW_REQUIRED" in {reason.code for reason in decision.reasons}
    assert "CATEGORY_MISMATCH" in {reason.code for reason in decision.reasons}
    age = next(item for item in decision.rule_evaluations if item.rule_id == "receipt-age")
    assert age.outcome is RuleOutcome.REJECT


@pytest.mark.parametrize("missing_field", ["receipt_date", "total", "category"])
def test_missing_critical_fact_routes_to_human_review(missing_field: str) -> None:
    claim = submission()
    values = {
        "receipt_date": VALID_RECEIPT_DATE,
        "total": claim.claimed_amount,
        "category": claim.claimed_category,
    }
    values[missing_field] = None
    extraction = ExtractionResult(
        request_id=claim.request_id,
        status=ExtractionStatus.SUCCEEDED,
        trace=trace(),
        facts=ReceiptFacts(**values),
    )

    decision = evaluate(claim, extraction)

    assert decision.route is PolicyDecisionRoute.HUMAN_REVIEW
    missing = next(reason for reason in decision.reasons if reason.code == "MISSING_CRITICAL_FACTS")
    assert missing_field in missing.evidence["fields"]
    completeness = next(
        item for item in decision.rule_evaluations if item.rule_id == "critical-receipt-facts"
    )
    assert completeness.outcome is RuleOutcome.REVIEW


def test_extraction_warning_routes_to_human_review() -> None:
    claim = submission()

    decision = evaluate(
        claim,
        successful_extraction(claim, warnings=("receipt date confidence is low",)),
    )

    assert decision.route is PolicyDecisionRoute.HUMAN_REVIEW
    assert "EXTRACTION_UNCERTAIN" in {reason.code for reason in decision.reasons}


def test_extraction_failure_routes_to_review_and_still_traces_every_rule() -> None:
    claim = submission()
    extraction = ExtractionResult(
        request_id=claim.request_id,
        status=ExtractionStatus.FAILED,
        trace=trace(),
        error="provider timeout",
    )

    decision = evaluate(claim, extraction)

    assert decision.route is PolicyDecisionRoute.HUMAN_REVIEW
    assert "EXTRACTION_FAILED" in {reason.code for reason in decision.reasons}
    assert {item.rule_id for item in decision.rule_evaluations} == {
        "receipt-extraction-quality",
        "critical-receipt-facts",
        "supported-currency",
        "receipt-age",
        "receipt-total-matches-claim",
        "receipt-category-matches-claim",
        "claim-amount-threshold",
    }


def test_amount_mismatch_routes_to_human_review() -> None:
    claim = submission(amount="150.00")

    decision = evaluate(
        claim,
        successful_extraction(claim, total=Money.brl("149.99")),
    )

    assert decision.route is PolicyDecisionRoute.HUMAN_REVIEW
    assert "AMOUNT_MISMATCH" in {reason.code for reason in decision.reasons}


def test_category_mismatch_routes_to_human_review_but_case_does_not() -> None:
    claim = submission(category="Client Meals")

    matching = evaluate(
        claim,
        successful_extraction(claim, category="client   meals"),
        decision_id="DEC-MATCH",
    )
    mismatching = evaluate(
        claim,
        successful_extraction(claim, category="transport"),
        decision_id="DEC-MISMATCH",
    )

    assert matching.route is PolicyDecisionRoute.AUTO_APPROVED
    assert mismatching.route is PolicyDecisionRoute.HUMAN_REVIEW
    assert "CATEGORY_MISMATCH" in {reason.code for reason in mismatching.reasons}


def test_future_receipt_date_routes_to_human_review() -> None:
    claim = submission()

    decision = evaluate(
        claim,
        successful_extraction(claim, receipt_date=SUBMISSION_DATE + timedelta(days=1)),
    )

    assert decision.route is PolicyDecisionRoute.HUMAN_REVIEW
    assert "RECEIPT_DATE_IN_FUTURE" in {reason.code for reason in decision.reasons}


def test_late_decision_does_not_make_receipt_older_than_at_submission() -> None:
    claim = submission(amount="200.00")
    receipt_date = SUBMISSION_DATE - timedelta(days=90)

    decision = evaluate(
        claim,
        successful_extraction(claim, receipt_date=receipt_date),
        decided_at=DECIDED_AT + timedelta(days=180),
    )

    assert decision.route is PolicyDecisionRoute.AUTO_APPROVED
    assert decision.decided_at == DECIDED_AT + timedelta(days=180)
    age = next(item for item in decision.rule_evaluations if item.rule_id == "receipt-age")
    assert age.facts["age_days"] == "90"
    assert "decision_date" not in age.facts


def test_submission_date_is_interpreted_in_sao_paulo() -> None:
    submitted_at = datetime(2026, 4, 10, 1, 0, tzinfo=UTC)
    claim = submission(amount="200.00", submitted_at=submitted_at)
    sao_paulo_submission_date = date(2026, 4, 9)

    decision = evaluate(
        claim,
        successful_extraction(
            claim,
            receipt_date=sao_paulo_submission_date - timedelta(days=90),
        ),
    )

    assert decision.route is PolicyDecisionRoute.AUTO_APPROVED
    age = next(item for item in decision.rule_evaluations if item.rule_id == "receipt-age")
    assert age.facts["submission_date"] == "2026-04-09"
    assert age.facts["age_days"] == "90"


def test_decision_is_reproducible_and_every_rule_is_versioned() -> None:
    claim = submission()
    extraction = successful_extraction(claim)

    first = evaluate(claim, extraction)
    second = evaluate(claim, extraction)

    assert first == second
    assert first.policy_version == BASELINE_POLICY_VERSION
    assert first.decision_id == "DEC-0001"
    assert first.decided_at == DECIDED_AT
    assert first.rule_evaluations
    assert {item.rule_version for item in first.rule_evaluations} == {BASELINE_RULE_VERSION}


def test_policy_rejects_extraction_for_another_request() -> None:
    claim = submission()
    other_claim = submission(request_id="REQ-OTHER")

    with pytest.raises(DomainValidationError, match="does not match"):
        evaluate(claim, successful_extraction(other_claim))


def test_policy_requires_explicit_timezone_aware_decision_time() -> None:
    claim = submission()

    with pytest.raises(DomainValidationError, match="timezone"):
        BaselinePolicy().evaluate(
            claim,
            successful_extraction(claim),
            decision_id="DEC-0001",
            decided_at=datetime(2026, 4, 10, 12, 0),  # noqa: DTZ001 - deliberately naive
        )
