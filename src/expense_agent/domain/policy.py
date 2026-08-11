"""Deterministic baseline reimbursement policy.

The policy consumes only validated domain inputs and explicit decision
metadata.  It performs no I/O, reads no clock, and generates no identifiers so
the same inputs always produce the same auditable decision.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Protocol
from zoneinfo import ZoneInfo

from expense_agent.domain._validation import require_aware_datetime
from expense_agent.domain.decisions import (
    AutomatedDecision,
    DecisionReason,
    PolicyDecisionRoute,
    RuleEvaluation,
    RuleOutcome,
)
from expense_agent.domain.exceptions import DomainValidationError
from expense_agent.domain.extraction import ExtractionResult, ExtractionStatus, ReceiptFacts
from expense_agent.domain.reimbursement import ReimbursementSubmission
from expense_agent.domain.value_objects import Currency, Money

BASELINE_POLICY_VERSION = "baseline-v2"
BASELINE_RULE_VERSION = "1.1.0"

AUTO_APPROVAL_LIMIT = Decimal("200.00")
HIGH_VALUE_LIMIT = Decimal("2000.00")
MAX_RECEIPT_AGE_DAYS = 90
_BUSINESS_TIMEZONE = ZoneInfo("America/Sao_Paulo")


class _ReasonCollector(Protocol):
    def __call__(self, code: str, message: str, **evidence: str) -> None: ...


class BaselinePolicy:
    """Evaluate the assignment's versioned, BRL-only baseline policy."""

    policy_version = BASELINE_POLICY_VERSION
    rule_version = BASELINE_RULE_VERSION

    def evaluate(
        self,
        submission: ReimbursementSubmission,
        extraction: ExtractionResult,
        *,
        decision_id: str,
        decided_at: datetime,
    ) -> AutomatedDecision:
        """Return an explainable automated decision for one reimbursement.

        ``decision_id`` and ``decided_at`` are explicit decision metadata.
        Receipt age is anchored to the immutable submission date in the
        Brazilian business timezone, so processing delays cannot change a
        reimbursement's eligibility.
        """

        if not isinstance(submission, ReimbursementSubmission):
            raise DomainValidationError("submission must be a ReimbursementSubmission")
        if not isinstance(extraction, ExtractionResult):
            raise DomainValidationError("extraction must be an ExtractionResult")
        if extraction.request_id != submission.request_id:
            raise DomainValidationError("extraction request_id does not match the submission")
        require_aware_datetime(decided_at, "decided_at")

        reasons: dict[str, DecisionReason] = {}
        evaluations: list[RuleEvaluation] = []

        def add_reason(code: str, message: str, **evidence: str) -> None:
            reasons.setdefault(
                code,
                DecisionReason(code=code, message=message, evidence=evidence),
            )

        facts = extraction.facts
        extraction_succeeded = extraction.status is ExtractionStatus.SUCCEEDED

        if not extraction_succeeded:
            add_reason(
                "EXTRACTION_FAILED",
                "Receipt extraction failed and requires human review.",
                error=extraction.error or "unknown extraction failure",
            )
            evaluations.append(
                self._evaluation(
                    "receipt-extraction-quality",
                    RuleOutcome.REVIEW,
                    "Receipt extraction did not produce facts.",
                    status=extraction.status.value,
                )
            )
        elif facts is not None and facts.warnings:
            add_reason(
                "EXTRACTION_UNCERTAIN",
                "Receipt extraction reported uncertainty and requires human review.",
                warning_count=str(len(facts.warnings)),
            )
            evaluations.append(
                self._evaluation(
                    "receipt-extraction-quality",
                    RuleOutcome.REVIEW,
                    "Receipt extraction produced one or more warnings.",
                    status=extraction.status.value,
                    warning_count=str(len(facts.warnings)),
                )
            )
        else:
            evaluations.append(
                self._evaluation(
                    "receipt-extraction-quality",
                    RuleOutcome.PASS,
                    "Receipt extraction succeeded without warnings.",
                    status=extraction.status.value,
                )
            )

        missing_facts = self._missing_critical_facts(facts)
        if missing_facts:
            add_reason(
                "MISSING_CRITICAL_FACTS",
                "One or more critical receipt facts are missing or invalid.",
                fields=",".join(missing_facts),
            )
            evaluations.append(
                self._evaluation(
                    "critical-receipt-facts",
                    RuleOutcome.REVIEW,
                    "Critical receipt facts are incomplete.",
                    missing_fields=",".join(missing_facts),
                )
            )
        else:
            evaluations.append(
                self._evaluation(
                    "critical-receipt-facts",
                    RuleOutcome.PASS,
                    "All critical receipt facts are present.",
                    fields="receipt_date,total,category",
                )
            )

        self._evaluate_currency(submission, facts, add_reason, evaluations)
        submission_date = submission.submitted_at.astimezone(_BUSINESS_TIMEZONE).date()
        self._evaluate_age(facts, submission_date, add_reason, evaluations)
        self._evaluate_amount_consistency(submission, facts, add_reason, evaluations)
        self._evaluate_category_consistency(submission, facts, add_reason, evaluations)
        self._evaluate_amount_threshold(submission, add_reason, evaluations)

        outcomes = {evaluation.outcome for evaluation in evaluations}
        high_value_review_required = any(
            reason.code == "HIGH_VALUE_REVIEW_REQUIRED" for reason in reasons.values()
        )
        if high_value_review_required:
            # The assignment marks this gate as non-bypassable. A mandatory
            # rejection remains recorded and constrains the later human
            # outcome, but cannot skip the high-value review itself.
            route = PolicyDecisionRoute.HUMAN_REVIEW
        elif RuleOutcome.REJECT in outcomes:
            route = PolicyDecisionRoute.REJECTED
        elif RuleOutcome.REVIEW in outcomes:
            route = PolicyDecisionRoute.HUMAN_REVIEW
        else:
            route = PolicyDecisionRoute.AUTO_APPROVED
            add_reason(
                "AUTO_APPROVAL_ELIGIBLE",
                "The claim satisfies every baseline auto-approval rule.",
                claimed_amount=str(submission.claimed_amount),
            )

        return AutomatedDecision(
            decision_id=decision_id,
            request_id=submission.request_id,
            route=route,
            decided_at=decided_at,
            policy_version=self.policy_version,
            reasons=tuple(reasons.values()),
            rule_evaluations=tuple(evaluations),
        )

    def _evaluate_currency(
        self,
        submission: ReimbursementSubmission,
        facts: ReceiptFacts | None,
        add_reason: _ReasonCollector,
        evaluations: list[RuleEvaluation],
    ) -> None:
        extracted_total = facts.total if facts is not None else None
        claimed_is_brl = submission.claimed_amount.currency is Currency.BRL
        extracted_is_brl = (
            isinstance(extracted_total, Money) and extracted_total.currency is Currency.BRL
        )
        if claimed_is_brl and extracted_is_brl:
            evaluations.append(
                self._evaluation(
                    "supported-currency",
                    RuleOutcome.PASS,
                    "Claimed and extracted amounts use BRL.",
                    currency=Currency.BRL.value,
                )
            )
            return

        if claimed_is_brl and extracted_total is None:
            evaluations.append(
                self._evaluation(
                    "supported-currency",
                    RuleOutcome.REVIEW,
                    "Extracted currency cannot be verified without a receipt total.",
                    claimed_currency=Currency.BRL.value,
                    extracted_currency="missing",
                )
            )
            return

        add_reason(
            "UNSUPPORTED_CURRENCY",
            "Only BRL reimbursements are supported by the baseline policy.",
            claimed_currency=self._currency_value(submission.claimed_amount),
            extracted_currency=self._currency_value(extracted_total),
        )
        evaluations.append(
            self._evaluation(
                "supported-currency",
                RuleOutcome.REVIEW,
                "A claimed or extracted amount is not denominated in BRL.",
                claimed_currency=self._currency_value(submission.claimed_amount),
                extracted_currency=self._currency_value(extracted_total),
            )
        )

    def _evaluate_age(
        self,
        facts: ReceiptFacts | None,
        submission_date: date,
        add_reason: _ReasonCollector,
        evaluations: list[RuleEvaluation],
    ) -> None:
        receipt_date = facts.receipt_date if facts is not None else None
        if not self._is_plain_date(receipt_date):
            evaluations.append(
                self._evaluation(
                    "receipt-age",
                    RuleOutcome.REVIEW,
                    "Receipt age cannot be evaluated without a valid receipt date.",
                    submission_date=submission_date.isoformat(),
                    business_timezone=_BUSINESS_TIMEZONE.key,
                    receipt_date="missing_or_invalid",
                )
            )
            return

        age_days = (submission_date - receipt_date).days
        age_facts = {
            "submission_date": submission_date.isoformat(),
            "business_timezone": _BUSINESS_TIMEZONE.key,
            "receipt_date": receipt_date.isoformat(),
            "age_days": str(age_days),
            "maximum_age_days": str(MAX_RECEIPT_AGE_DAYS),
        }
        if age_days > MAX_RECEIPT_AGE_DAYS:
            add_reason(
                "RECEIPT_TOO_OLD",
                "The receipt is older than 90 days and must be rejected.",
                **age_facts,
            )
            evaluations.append(
                self._evaluation(
                    "receipt-age",
                    RuleOutcome.REJECT,
                    "Receipt age exceeds the mandatory 90-day limit.",
                    **age_facts,
                )
            )
        elif age_days < 0:
            add_reason(
                "RECEIPT_DATE_IN_FUTURE",
                "The receipt date is later than the submission date.",
                **age_facts,
            )
            evaluations.append(
                self._evaluation(
                    "receipt-age",
                    RuleOutcome.REVIEW,
                    "A receipt dated after submission requires human review.",
                    **age_facts,
                )
            )
        else:
            evaluations.append(
                self._evaluation(
                    "receipt-age",
                    RuleOutcome.PASS,
                    "Receipt is no more than 90 days old.",
                    **age_facts,
                )
            )

    def _evaluate_amount_consistency(
        self,
        submission: ReimbursementSubmission,
        facts: ReceiptFacts | None,
        add_reason: _ReasonCollector,
        evaluations: list[RuleEvaluation],
    ) -> None:
        receipt_total = facts.total if facts is not None else None
        if not isinstance(receipt_total, Money):
            evaluations.append(
                self._evaluation(
                    "receipt-total-matches-claim",
                    RuleOutcome.REVIEW,
                    "Claim and receipt total cannot be compared.",
                    claimed_amount=str(submission.claimed_amount),
                    receipt_total="missing_or_invalid",
                )
            )
            return

        amount_facts = {
            "claimed_amount": str(submission.claimed_amount),
            "receipt_total": str(receipt_total),
        }
        if receipt_total != submission.claimed_amount:
            add_reason(
                "AMOUNT_MISMATCH",
                "The claimed amount differs from the extracted receipt total.",
                **amount_facts,
            )
            evaluations.append(
                self._evaluation(
                    "receipt-total-matches-claim",
                    RuleOutcome.REVIEW,
                    "Claimed amount and receipt total do not match.",
                    **amount_facts,
                )
            )
        else:
            evaluations.append(
                self._evaluation(
                    "receipt-total-matches-claim",
                    RuleOutcome.PASS,
                    "Claimed amount matches the receipt total.",
                    **amount_facts,
                )
            )

    def _evaluate_category_consistency(
        self,
        submission: ReimbursementSubmission,
        facts: ReceiptFacts | None,
        add_reason: _ReasonCollector,
        evaluations: list[RuleEvaluation],
    ) -> None:
        receipt_category = facts.category if facts is not None else None
        if not isinstance(receipt_category, str) or not receipt_category.strip():
            evaluations.append(
                self._evaluation(
                    "receipt-category-matches-claim",
                    RuleOutcome.REVIEW,
                    "Claim and receipt category cannot be compared.",
                    claimed_category=submission.claimed_category,
                    receipt_category="missing_or_invalid",
                )
            )
            return

        category_facts = {
            "claimed_category": submission.claimed_category,
            "receipt_category": receipt_category,
        }
        if self._normalized_category(receipt_category) != self._normalized_category(
            submission.claimed_category
        ):
            add_reason(
                "CATEGORY_MISMATCH",
                "The claimed category differs from the extracted receipt category.",
                **category_facts,
            )
            evaluations.append(
                self._evaluation(
                    "receipt-category-matches-claim",
                    RuleOutcome.REVIEW,
                    "Claimed and extracted categories do not match.",
                    **category_facts,
                )
            )
        else:
            evaluations.append(
                self._evaluation(
                    "receipt-category-matches-claim",
                    RuleOutcome.PASS,
                    "Claimed and extracted categories match.",
                    **category_facts,
                )
            )

    def _evaluate_amount_threshold(
        self,
        submission: ReimbursementSubmission,
        add_reason: _ReasonCollector,
        evaluations: list[RuleEvaluation],
    ) -> None:
        amount = submission.claimed_amount.amount
        threshold_facts = {
            "claimed_amount": str(submission.claimed_amount),
            "auto_approval_limit": f"BRL {AUTO_APPROVAL_LIMIT:.2f}",
            "high_value_limit": f"BRL {HIGH_VALUE_LIMIT:.2f}",
        }
        if submission.claimed_amount.currency is not Currency.BRL:
            evaluations.append(
                self._evaluation(
                    "claim-amount-threshold",
                    RuleOutcome.REVIEW,
                    "Amount thresholds are defined only for BRL.",
                    **threshold_facts,
                )
            )
        elif amount <= AUTO_APPROVAL_LIMIT:
            evaluations.append(
                self._evaluation(
                    "claim-amount-threshold",
                    RuleOutcome.PASS,
                    "Claim is within the inclusive auto-approval amount limit.",
                    amount_band="at_or_below_200",
                    **threshold_facts,
                )
            )
        elif amount <= HIGH_VALUE_LIMIT:
            add_reason(
                "AMOUNT_REQUIRES_HUMAN_REVIEW",
                "Claims above BRL 200 require human review.",
                amount_band="200_01_through_2000",
                **threshold_facts,
            )
            evaluations.append(
                self._evaluation(
                    "claim-amount-threshold",
                    RuleOutcome.REVIEW,
                    "Claim is above the auto-approval limit.",
                    amount_band="200_01_through_2000",
                    **threshold_facts,
                )
            )
        else:
            add_reason(
                "HIGH_VALUE_REVIEW_REQUIRED",
                "Claims above BRL 2,000 must receive human review.",
                amount_band="above_2000",
                **threshold_facts,
            )
            evaluations.append(
                self._evaluation(
                    "claim-amount-threshold",
                    RuleOutcome.REVIEW,
                    "Claim exceeds the mandatory high-value review threshold.",
                    amount_band="above_2000",
                    **threshold_facts,
                )
            )

    def _evaluation(
        self,
        rule_id: str,
        outcome: RuleOutcome,
        message: str,
        **facts: str,
    ) -> RuleEvaluation:
        return RuleEvaluation(
            rule_id=rule_id,
            rule_version=self.rule_version,
            outcome=outcome,
            message=message,
            facts=facts,
        )

    @staticmethod
    def _missing_critical_facts(facts: ReceiptFacts | None) -> tuple[str, ...]:
        if facts is None:
            return ("receipt_date", "total", "category")

        missing: list[str] = []
        if not BaselinePolicy._is_plain_date(facts.receipt_date):
            missing.append("receipt_date")
        if not isinstance(facts.total, Money):
            missing.append("total")
        if not isinstance(facts.category, str) or not facts.category.strip():
            missing.append("category")
        return tuple(missing)

    @staticmethod
    def _is_plain_date(value: object) -> bool:
        return isinstance(value, date) and not isinstance(value, datetime)

    @staticmethod
    def _normalized_category(value: str) -> str:
        return " ".join(value.split()).casefold()

    @staticmethod
    def _currency_value(value: Money | None) -> str:
        if not isinstance(value, Money):
            return "missing_or_invalid"
        currency = value.currency
        return currency.value if isinstance(currency, Currency) else str(currency)
