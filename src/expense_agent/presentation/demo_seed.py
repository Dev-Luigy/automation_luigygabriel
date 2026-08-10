"""Create deterministic, non-sensitive review cases for local demonstration."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from expense_agent.application.review import ReviewConflictError, ReviewProblem
from expense_agent.domain.decisions import (
    AutomatedDecision,
    DecisionReason,
    PolicyDecisionRoute,
    RuleEvaluation,
    RuleOutcome,
)
from expense_agent.domain.extraction import (
    ExtractionResult,
    ExtractionStatus,
    ModelInvocationTrace,
    ReceiptFacts,
)
from expense_agent.domain.reimbursement import (
    AttachmentReference,
    ReimbursementCase,
    ReimbursementSubmission,
)
from expense_agent.domain.value_objects import Currency, Money
from expense_agent.infrastructure.review.persistence import SqliteReviewRepository


def _build_case(
    *,
    request_id: str,
    submitted_by: str,
    amount: str,
    extracted_amount: str,
    category: str,
    merchant: str,
    problem_code: str,
    problem_message: str,
    offset_minutes: int,
) -> tuple[ReimbursementCase, ExtractionResult, tuple[ReviewProblem, ...]]:
    now = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=offset_minutes)
    receipt_date = now.date()
    raw_ocr = (
        f"{merchant}\nCNPJ 12.345.678/0001-90\n"
        f"DATA {receipt_date.isoformat()}\nTOTAL R$ {extracted_amount}\n"
        f"CATEGORY {category}"
    )
    submission = ReimbursementSubmission(
        request_id=request_id,
        submitted_by=submitted_by,
        submitted_at=now,
        raw_ocr_text=raw_ocr,
        claimed_category=category,
        claimed_amount=Money(Decimal(amount), Currency.BRL),
        attachments=(AttachmentReference(location=f"object://receipts/{request_id}/receipt.jpg"),),
    )
    extraction = ExtractionResult(
        request_id=request_id,
        status=ExtractionStatus.SUCCEEDED,
        trace=ModelInvocationTrace(
            provider="demo-ocr",
            model="receipt-fixture-v1",
            prompt_version="receipt-extraction-v3",
            prompt_hash="demo-prompt-sha256",
            input_hash=f"demo-input-{request_id}",
            raw_response=raw_ocr,
            invoked_at=now + timedelta(seconds=3),
            duration_ms=640,
            parameters={"temperature": 0},
        ),
        facts=ReceiptFacts(
            receipt_date=receipt_date,
            total=Money(Decimal(extracted_amount), Currency.BRL),
            category=category,
            merchant_name=merchant,
            tax_id="12.345.678/0001-90",
            evidence={"total": f"TOTAL R$ {extracted_amount}"},
            warnings=(problem_message,),
        ),
    )
    automated = AutomatedDecision(
        decision_id=f"auto-{request_id}",
        request_id=request_id,
        route=PolicyDecisionRoute.HUMAN_REVIEW,
        decided_at=now + timedelta(seconds=4),
        policy_version="expense-policy-2026.08",
        reasons=(
            DecisionReason(
                code=problem_code,
                message=problem_message,
                evidence={"claimed": amount, "extracted": extracted_amount},
            ),
        ),
        rule_evaluations=(
            RuleEvaluation(
                rule_id="receipt-total-matches-claim",
                rule_version="2.1.0",
                outcome=RuleOutcome.REVIEW,
                message=problem_message,
                facts={"claimed_amount": amount, "receipt_total": extracted_amount},
            ),
        ),
    )
    case = ReimbursementCase(submission=submission, opened_at=now)
    case.start_processing()
    case.record_automated_decision(automated)
    problems = (
        ReviewProblem(
            code=problem_code,
            message=problem_message,
            evidence={"source": "deterministic-policy"},
        ),
    )
    return case, extraction, problems


def run() -> None:
    path = os.environ.get(
        "EXPENSE_AGENT_DATABASE_PATH",
        "./data/expense-agent.sqlite3",
    )
    repository = SqliteReviewRepository(path)
    fixtures = (
        _build_case(
            request_id="RMB-2026-00041",
            submitted_by="ana.silva@example.com",
            amount="186.40",
            extracted_amount="168.40",
            category="client_meal",
            merchant="Bistrô Central",
            problem_code="AMOUNT_MISMATCH",
            problem_message="Claimed amount differs from the receipt total by BRL 18.00.",
            offset_minutes=47,
        ),
        _build_case(
            request_id="RMB-2026-00042",
            submitted_by="marcos.lima@example.com",
            amount="742.00",
            extracted_amount="742.00",
            category="lodging",
            merchant="Hotel Horizonte",
            problem_code="POLICY_LIMIT_EVIDENCE",
            problem_message="The lodging claim requires a project cost-center confirmation.",
            offset_minutes=19,
        ),
    )
    for case, extraction, problems in fixtures:
        try:
            repository.add_pending_case(case, extraction=extraction, problems=problems)
            print(f"Created demo case {case.request_id}")
        except ReviewConflictError:
            print(f"Demo case {case.request_id} already exists; kept existing record")


if __name__ == "__main__":
    run()
