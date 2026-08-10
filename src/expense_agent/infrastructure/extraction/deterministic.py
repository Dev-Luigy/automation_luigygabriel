"""Offline, deterministic extraction for the assessment OCR input shape."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from time import perf_counter_ns
from typing import Any

from expense_agent.domain import ExtractionResult, ExtractionStatus, ReimbursementSubmission
from expense_agent.infrastructure.extraction._support import (
    DEFAULT_PROMPT,
    PROMPT_VERSION,
    build_trace,
    canonical_json,
    parse_response_payload,
    sha256_text,
)

_DATE_LABELS = (
    ("DATE", re.compile(r"(?im)^\s*DATE\s*:?[ \t]*(\d{2}/\d{2}/\d{4})\s*$")),
    ("DATA", re.compile(r"(?im)^\s*DATA\s*:?[ \t]*(\d{2}/\d{2}/\d{4})\s*$")),
    (
        "CHECK-OUT",
        re.compile(r"(?im)^\s*CHECK[ -]?OUT\s*:?[ \t]*(\d{2}/\d{2}/\d{4})\s*$"),
    ),
    (
        "CHECK-IN",
        re.compile(r"(?im)^\s*CHECK[ -]?IN\s*:?[ \t]*(\d{2}/\d{2}/\d{4})\s*$"),
    ),
)
_TOTAL_PATTERN = re.compile(
    r"(?im)^\s*(TOTAL|FARE)\s*:?[ \t]*R\$\s*"
    r"(\d+(?:[.,]\d{3})*(?:[.,]\d{2})|\d+[.,]\d{2})\s*$"
)
_TAX_ID_PATTERN = re.compile(
    r"(?im)^\s*(?:TAX\s*ID|CNPJ|CPF)\s*:?[ \t]*([0-9./-]{11,20})\s*$"
)
_CATEGORY_MARKERS: dict[str, tuple[re.Pattern[str], ...]] = {
    "meals": (
        re.compile(r"(?i)\b(?:restaurant|meal|lunch|dinner|almo[cç]o|refei[cç][aã]o)\b"),
    ),
    "transportation": (
        re.compile(r"(?i)\b(?:taxi|fare|origin|destination|distance|corrida)\b"),
    ),
    "lodging": (
        re.compile(r"(?i)\b(?:hotel|check[ -]?in|check[ -]?out|nights?|room rate)\b"),
    ),
}


class DeterministicReceiptExtractor:
    """Parse explicit receipt labels without a network or model dependency."""

    provider = "offline-deterministic"
    model = "assessment-receipt-parser-v1"
    prompt_version = PROMPT_VERSION
    prompt = DEFAULT_PROMPT
    prompt_hash = sha256_text(prompt)

    def extract(self, submission: ReimbursementSubmission) -> ExtractionResult:
        request_id = submission.request_id
        raw_ocr_text = submission.raw_ocr_text
        invoked_at = datetime.now(UTC)
        started_ns = perf_counter_ns()
        raw_response = ""
        try:
            if not isinstance(raw_ocr_text, str) or not raw_ocr_text.strip():
                raw_response = canonical_json({"error": "raw_ocr_text is blank"})
                return self._failed(
                    request_id=request_id,
                    raw_ocr_text=raw_ocr_text if isinstance(raw_ocr_text, str) else "",
                    raw_response=raw_response,
                    invoked_at=invoked_at,
                    started_ns=started_ns,
                    error="receipt extraction input is blank",
                )

            payload = _extract_payload(raw_ocr_text)
            raw_response = canonical_json(payload)
            facts = parse_response_payload(payload)
            trace = build_trace(
                provider=self.provider,
                model=self.model,
                prompt_version=self.prompt_version,
                prompt=self.prompt,
                raw_ocr_text=raw_ocr_text,
                raw_response=raw_response,
                invoked_at=invoked_at,
                duration_ms=_elapsed_ms(started_ns),
                parameters={"deterministic": True, "network": False},
            )
            return ExtractionResult(
                request_id=request_id,
                status=ExtractionStatus.SUCCEEDED,
                trace=trace,
                facts=facts,
            )
        except (ArithmeticError, TypeError, ValueError):
            return self._failed(
                request_id=request_id,
                raw_ocr_text=raw_ocr_text if isinstance(raw_ocr_text, str) else "",
                raw_response=raw_response,
                invoked_at=invoked_at,
                started_ns=started_ns,
                error="receipt extraction failed",
            )

    def _failed(
        self,
        *,
        request_id: str,
        raw_ocr_text: str,
        raw_response: str,
        invoked_at: datetime,
        started_ns: int,
        error: str,
    ) -> ExtractionResult:
        trace = build_trace(
            provider=self.provider,
            model=self.model,
            prompt_version=self.prompt_version,
            prompt=self.prompt,
            raw_ocr_text=raw_ocr_text,
            raw_response=raw_response,
            invoked_at=invoked_at,
            duration_ms=_elapsed_ms(started_ns),
            parameters={"deterministic": True, "network": False},
        )
        return ExtractionResult(
            request_id=request_id,
            status=ExtractionStatus.FAILED,
            trace=trace,
            error=error,
        )


def _extract_payload(raw_ocr_text: str) -> dict[str, Any]:
    lines = [line.strip() for line in raw_ocr_text.splitlines() if line.strip()]
    warnings: list[str] = []
    evidence: dict[str, str] = {}

    merchant_name = lines[0] if lines else None
    if merchant_name:
        evidence["merchant_name"] = merchant_name

    tax_match = _TAX_ID_PATTERN.search(raw_ocr_text)
    tax_id = tax_match.group(1) if tax_match else None
    if tax_match:
        evidence["tax_id"] = tax_match.group(0).strip()

    receipt_date, date_evidence, date_warning = _extract_date(raw_ocr_text)
    if date_evidence:
        evidence["receipt_date"] = date_evidence
    if date_warning:
        warnings.append(date_warning)

    total_matches = list(_TOTAL_PATTERN.finditer(raw_ocr_text))
    total: dict[str, str] | None = None
    if total_matches:
        total_match = total_matches[-1]
        total = {"amount": _normalize_brl(total_match.group(2)), "currency": "BRL"}
        evidence["total"] = total_match.group(0).strip()

    category, category_evidence, category_warning = _extract_category(lines)
    if category_evidence:
        evidence["category"] = category_evidence
    if category_warning:
        warnings.append(category_warning)

    if merchant_name is None:
        warnings.append("merchant name was not found")
    if tax_id is None:
        warnings.append("tax ID was not found")

    return {
        "receipt_date": receipt_date,
        "total": total,
        "category": category,
        "merchant_name": merchant_name,
        "tax_id": tax_id,
        "evidence": evidence,
        "warnings": warnings,
    }


def _extract_date(raw_ocr_text: str) -> tuple[str | None, str | None, str | None]:
    for label, pattern in _DATE_LABELS:
        match = pattern.search(raw_ocr_text)
        if match is None:
            continue
        day, month, year = (int(part) for part in match.group(1).split("/"))
        parsed = date(year, month, day)
        warning = None
        if label in {"CHECK-IN", "CHECK-OUT"}:
            warning = f"receipt date used explicit {label} service date"
        return parsed.isoformat(), match.group(0).strip(), warning
    return None, None, None


def _extract_category(lines: list[str]) -> tuple[str | None, str | None, str | None]:
    matches: dict[str, str] = {}
    for category, patterns in _CATEGORY_MARKERS.items():
        for line in lines:
            if any(pattern.search(line) for pattern in patterns):
                matches[category] = line
                break
    if len(matches) == 1:
        category, line = next(iter(matches.items()))
        return category, line, None
    if len(matches) > 1:
        return None, None, "receipt category is ambiguous"
    return None, None, "receipt category was not found"


def _normalize_brl(value: str) -> str:
    decimal_separator = max(value.rfind("."), value.rfind(","))
    whole = re.sub(r"[.,]", "", value[:decimal_separator])
    fraction = value[decimal_separator + 1 :]
    return f"{whole}.{fraction}"


def _elapsed_ms(started_ns: int) -> int:
    return max(0, (perf_counter_ns() - started_ns) // 1_000_000)
