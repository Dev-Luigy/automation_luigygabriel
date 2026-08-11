"""Acceptance checks against the three requests supplied in the assignment."""

import json
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from expense_agent.domain import (
    AttachmentReference,
    BaselinePolicy,
    ExtractionStatus,
    Money,
    PolicyDecisionRoute,
    ReimbursementSubmission,
)
from expense_agent.infrastructure.extraction import DeterministicReceiptExtractor

SAMPLE_DATASET = Path(__file__).parents[1] / "examples" / "sample_requests.json"
INPUT_FIELDS = {
    "request_id",
    "submitted_by",
    "submitted_at",
    "raw_ocr_text",
    "claimed_category",
    "claimed_amount_brl",
    "attachments",
}


def _load_samples() -> list[dict[str, object]]:
    with SAMPLE_DATASET.open(encoding="utf-8") as stream:
        payload = json.load(stream, parse_float=Decimal)
    assert isinstance(payload, list)
    return payload


def _submission(payload: Mapping[str, object]) -> ReimbursementSubmission:
    request_id = payload["request_id"]
    submitted_by = payload["submitted_by"]
    submitted_at = payload["submitted_at"]
    raw_ocr_text = payload["raw_ocr_text"]
    claimed_category = payload["claimed_category"]
    claimed_amount = payload["claimed_amount_brl"]
    attachments = payload["attachments"]
    assert isinstance(request_id, str)
    assert isinstance(submitted_by, str)
    assert isinstance(submitted_at, str)
    assert isinstance(raw_ocr_text, str)
    assert isinstance(claimed_category, str)
    assert isinstance(claimed_amount, Decimal)
    assert isinstance(attachments, list)
    assert all(isinstance(item, str) for item in attachments)
    return ReimbursementSubmission(
        request_id=request_id,
        submitted_by=submitted_by,
        submitted_at=datetime.fromisoformat(submitted_at),
        raw_ocr_text=raw_ocr_text,
        claimed_category=claimed_category,
        claimed_amount=Money(amount=claimed_amount),
        attachments=tuple(AttachmentReference(item) for item in attachments),
    )


def _extract_and_decide(
    submission: ReimbursementSubmission,
    *,
    decided_at: datetime | None = None,
):
    extraction = DeterministicReceiptExtractor().extract(submission)
    decision = BaselinePolicy().evaluate(
        submission,
        extraction,
        decision_id=f"DEC-{submission.request_id}",
        decided_at=decided_at or submission.submitted_at + timedelta(seconds=1),
    )
    return extraction, decision


def _boundary_submission(
    *,
    request_id: str,
    amount: str,
    receipt_date: date,
) -> ReimbursementSubmission:
    raw_ocr_text = "\n".join(
        (
            "BOUNDARY RESTAURANT LTD",
            "TAX ID 12.345.678/0001-90",
            f"DATE {receipt_date.strftime('%d/%m/%Y')}",
            "BUSINESS LUNCH",
            f"TOTAL R$ {amount}",
        )
    )
    return ReimbursementSubmission(
        request_id=request_id,
        submitted_by="boundary@example.com",
        submitted_at=datetime.fromisoformat("2026-04-10T09:15:00+00:00"),
        raw_ocr_text=raw_ocr_text,
        claimed_category="meals",
        claimed_amount=Money.brl(amount),
        attachments=(AttachmentReference(f"{request_id}.jpg"),),
    )


def test_sample_dataset_matches_the_pdf_input_objects_exactly() -> None:
    samples = _load_samples()

    assert samples == [
        {
            "request_id": "REQ-0001",
            "submitted_by": "ana.silva@company.com",
            "submitted_at": "2026-04-10T09:15:00Z",
            "raw_ocr_text": (
                "BOM SABOR RESTAURANT LTD\n"
                "TAX ID 12.345.678/0001-90\n"
                "DATE 09/04/2026\n"
                "BUSINESS LUNCH\n"
                "2 X EXECUTIVE MEAL R$ 42.50\n"
                "SUBTOTAL R$ 85.00\n"
                "SERVICE 10% R$ 8.50\n"
                "TOTAL R$ 93.50"
            ),
            "claimed_category": "meals",
            "claimed_amount_brl": Decimal("93.50"),
            "attachments": ["receipt_0001.jpg"],
        },
        {
            "request_id": "REQ-0002",
            "submitted_by": "carlos.mendes@company.com",
            "submitted_at": "2026-04-11T14:20:00Z",
            "raw_ocr_text": (
                "URBAN TAXI SERVICES\n"
                "TAX ID 23.456.789/0001-12\n"
                "DATE 11/04/2026\n"
                "ORIGIN: COMPANY HQ\n"
                "DESTINATION: AIRPORT TERMINAL 3\n"
                "DISTANCE: 18.4 KM\n"
                "FARE R$ 64.80"
            ),
            "claimed_category": "transportation",
            "claimed_amount_brl": Decimal("64.80"),
            "attachments": ["receipt_0002.jpg"],
        },
        {
            "request_id": "REQ-0003",
            "submitted_by": "rafael.costa@company.com",
            "submitted_at": "2026-04-13T08:45:00Z",
            "raw_ocr_text": (
                "GRAND PLAZA HOTEL\n"
                "TAX ID 45.678.901/0001-56\n"
                "GUEST: RAFAEL COSTA\n"
                "CHECK-IN: 10/04/2026\n"
                "CHECK-OUT: 12/04/2026\n"
                "NIGHTS: 2\n"
                "ROOM RATE: R$ 320.00 X 2\n"
                "BREAKFAST INCLUDED\n"
                "TOTAL R$ 640.00"
            ),
            "claimed_category": "lodging",
            "claimed_amount_brl": Decimal("640.00"),
            "attachments": ["receipt_0003.pdf"],
        },
    ]
    assert all(set(sample) == INPUT_FIELDS for sample in samples)


@pytest.mark.parametrize(
    ("request_id", "expected_route", "expected_date", "expected_total", "expected_category"),
    [
        ("REQ-0001", PolicyDecisionRoute.AUTO_APPROVED, date(2026, 4, 9), "93.50", "meals"),
        (
            "REQ-0002",
            PolicyDecisionRoute.AUTO_APPROVED,
            date(2026, 4, 11),
            "64.80",
            "transportation",
        ),
        (
            "REQ-0003",
            PolicyDecisionRoute.HUMAN_REVIEW,
            date(2026, 4, 12),
            "640.00",
            "lodging",
        ),
    ],
)
def test_assignment_samples_pass_through_extractor_and_policy(
    request_id: str,
    expected_route: PolicyDecisionRoute,
    expected_date: date,
    expected_total: str,
    expected_category: str,
) -> None:
    sample = next(item for item in _load_samples() if item["request_id"] == request_id)
    submission = _submission(sample)

    extraction, decision = _extract_and_decide(submission)

    assert extraction.status is ExtractionStatus.SUCCEEDED
    assert extraction.facts is not None
    assert extraction.facts.receipt_date == expected_date
    assert extraction.facts.total == Money.brl(expected_total)
    assert extraction.facts.category == expected_category
    assert decision.request_id == request_id
    assert decision.route is expected_route
    if request_id == "REQ-0003":
        assert extraction.facts.warnings == (
            "receipt date used explicit CHECK-OUT service date",
        )
        assert "EXTRACTION_UNCERTAIN" in {reason.code for reason in decision.reasons}
    else:
        assert extraction.facts.warnings == ()


@pytest.mark.parametrize(
    ("amount", "expected_route"),
    [
        ("200.00", PolicyDecisionRoute.AUTO_APPROVED),
        ("200.01", PolicyDecisionRoute.HUMAN_REVIEW),
        ("2000.00", PolicyDecisionRoute.HUMAN_REVIEW),
        ("2000.01", PolicyDecisionRoute.HUMAN_REVIEW),
    ],
)
def test_critical_amount_boundaries_use_extracted_evidence(
    amount: str,
    expected_route: PolicyDecisionRoute,
) -> None:
    submission = _boundary_submission(
        request_id=f"BOUNDARY-AMOUNT-{amount}",
        amount=amount,
        receipt_date=date(2026, 4, 10),
    )

    extraction, decision = _extract_and_decide(submission)

    assert extraction.status is ExtractionStatus.SUCCEEDED
    assert extraction.facts is not None
    assert extraction.facts.warnings == ()
    assert decision.route is expected_route


def test_90_day_boundary_and_non_bypassable_high_value_gate_use_submission_date() -> None:
    exactly_90_days = _boundary_submission(
        request_id="BOUNDARY-AGE-90",
        amount="200.00",
        receipt_date=date(2026, 1, 10),
    )
    old_high_value = _boundary_submission(
        request_id="BOUNDARY-AGE-91",
        amount="2000.01",
        receipt_date=date(2026, 1, 9),
    )

    valid_extraction, valid_decision = _extract_and_decide(
        exactly_90_days,
        decided_at=exactly_90_days.submitted_at + timedelta(days=180),
    )
    old_extraction, old_decision = _extract_and_decide(old_high_value)

    assert valid_extraction.status is ExtractionStatus.SUCCEEDED
    assert valid_decision.route is PolicyDecisionRoute.AUTO_APPROVED
    assert old_extraction.status is ExtractionStatus.SUCCEEDED
    assert old_decision.route is PolicyDecisionRoute.HUMAN_REVIEW
    assert "RECEIPT_TOO_OLD" in {reason.code for reason in old_decision.reasons}
    assert "HIGH_VALUE_REVIEW_REQUIRED" in {
        reason.code for reason in old_decision.reasons
    }
