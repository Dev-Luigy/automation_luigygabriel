"""Shared schema, hashing, and trace helpers for extraction adapters."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from expense_agent.domain import ModelInvocationTrace, Money, ReceiptFacts

PROMPT_VERSION = "receipt-extraction-v1"
DEFAULT_PROMPT = """Extract receipt facts from the supplied OCR text.
Return exactly one JSON object with these keys: receipt_date, total, category,
merchant_name, tax_id, evidence, warnings. receipt_date is YYYY-MM-DD or null.
total is null or {"amount": "decimal string", "currency": "BRL"}. The other
fact fields are strings or null, evidence is a string-to-string object, and
warnings is an array of strings. Never infer a fact that is absent or ambiguous.
"""

_REQUIRED_KEYS = {
    "receipt_date",
    "total",
    "category",
    "merchant_name",
    "tax_id",
    "evidence",
    "warnings",
}
_MAX_TEXT_LENGTH = 500
_MAX_EVIDENCE_ENTRIES = 32
_MAX_WARNINGS = 32
_DECIMAL_AMOUNT = re.compile(r"(?:0|[1-9]\d{0,15})(?:\.\d{1,2})?")


class ResponseValidationError(ValueError):
    """Raised when a provider response does not match the extraction schema."""


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def build_trace(
    *,
    provider: str,
    model: str,
    prompt_version: str,
    prompt: str,
    raw_ocr_text: str,
    raw_response: str,
    invoked_at: datetime,
    duration_ms: int,
    parameters: Mapping[str, str | int | float | bool | None],
) -> ModelInvocationTrace:
    return ModelInvocationTrace(
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        prompt_hash=sha256_text(prompt),
        input_hash=sha256_text(raw_ocr_text),
        raw_response=raw_response,
        invoked_at=invoked_at,
        duration_ms=duration_ms,
        parameters=parameters,
    )


def parse_response_json(raw_response: str) -> ReceiptFacts:
    try:
        payload = json.loads(raw_response, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, RecursionError, UnicodeError) as exc:
        raise ResponseValidationError("response must be valid JSON") from exc
    return parse_response_payload(payload)


def parse_response_payload(payload: object) -> ReceiptFacts:
    if not isinstance(payload, dict):
        raise ResponseValidationError("response must be a JSON object")
    keys = set(payload)
    if keys != _REQUIRED_KEYS:
        missing = sorted(_REQUIRED_KEYS - keys)
        unexpected = sorted(keys - _REQUIRED_KEYS)
        details: list[str] = []
        if missing:
            details.append(f"missing keys: {', '.join(missing)}")
        if unexpected:
            details.append("response contains unexpected keys")
        raise ResponseValidationError("; ".join(details))

    receipt_date = _optional_date(payload["receipt_date"])
    total = _optional_money(payload["total"])
    category = _optional_text(payload["category"], "category")
    merchant_name = _optional_text(payload["merchant_name"], "merchant_name")
    tax_id = _optional_text(payload["tax_id"], "tax_id")
    evidence = _evidence(payload["evidence"])
    warnings = list(_warnings(payload["warnings"]))

    if receipt_date is None and "receipt date was not found" not in warnings:
        warnings.append("receipt date was not found")
    if total is None and "receipt total was not found" not in warnings:
        warnings.append("receipt total was not found")

    return ReceiptFacts(
        receipt_date=receipt_date,
        total=total,
        category=category,
        merchant_name=merchant_name,
        tax_id=tax_id,
        evidence=evidence,
        warnings=tuple(warnings),
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ResponseValidationError("response contains a duplicate key")
        result[key] = value
    return result


def _optional_date(value: object) -> date | None:
    if value is None:
        return None
    text = _required_text(value, "receipt_date", max_length=10)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ResponseValidationError("receipt_date must use YYYY-MM-DD") from exc
    if parsed.isoformat() != text:
        raise ResponseValidationError("receipt_date must use YYYY-MM-DD")
    return parsed


def _optional_money(value: object) -> Money | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"amount", "currency"}:
        raise ResponseValidationError("total must contain only amount and currency")
    if value["currency"] != "BRL":
        raise ResponseValidationError("total.currency must be BRL")
    amount_text = _required_text(value["amount"], "total.amount", max_length=40)
    if _DECIMAL_AMOUNT.fullmatch(amount_text) is None:
        raise ResponseValidationError(
            "total.amount must use a plain non-negative decimal string with at most two decimals"
        )
    try:
        amount = Decimal(amount_text)
    except (InvalidOperation, ValueError) as exc:
        raise ResponseValidationError("total.amount must be a decimal string") from exc
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
        raise ResponseValidationError(
            "total.amount must be a non-negative finite value with at most two decimals"
        )
    return Money(amount=amount)


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, field_name)


def _required_text(value: object, field_name: str, *, max_length: int = _MAX_TEXT_LENGTH) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResponseValidationError(f"{field_name} must be a non-blank string or null")
    text = value.strip()
    if len(text) > max_length:
        raise ResponseValidationError(f"{field_name} exceeds {max_length} characters")
    return text


def _evidence(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ResponseValidationError("evidence must be an object")
    if len(value) > _MAX_EVIDENCE_ENTRIES:
        raise ResponseValidationError("evidence has too many entries")
    result: dict[str, str] = {}
    for key, item in value.items():
        normalized_key = _required_text(key, "evidence key", max_length=100)
        result[normalized_key] = _required_text(item, "evidence value", max_length=2_000)
    return result


def _warnings(value: object) -> Sequence[str]:
    if not isinstance(value, list):
        raise ResponseValidationError("warnings must be an array")
    if len(value) > _MAX_WARNINGS:
        raise ResponseValidationError("warnings has too many entries")
    return tuple(_required_text(item, "warning", max_length=500) for item in value)
