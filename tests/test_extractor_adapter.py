import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from urllib.request import Request

import pytest

from expense_agent.application.extraction import ReceiptExtractor
from expense_agent.domain import ExtractionStatus, Money, ReimbursementSubmission
from expense_agent.infrastructure.extraction import (
    DeterministicReceiptExtractor,
    HttpJsonExtractorConfig,
    HttpJsonReceiptExtractor,
    http_json,
)

SAMPLE_OCR = {
    "REQ-0001": (
        "BOM SABOR RESTAURANT LTD\n"
        "TAX ID 12.345.678/0001-90\n"
        "DATE 09/04/2026\n"
        "BUSINESS LUNCH\n"
        "2 X EXECUTIVE MEAL R$ 42.50\n"
        "SUBTOTAL R$ 85.00\n"
        "SERVICE 10% R$ 8.50\n"
        "TOTAL R$ 93.50"
    ),
    "REQ-0002": (
        "URBAN TAXI SERVICES\n"
        "TAX ID 23.456.789/0001-12\n"
        "DATE 11/04/2026\n"
        "ORIGIN: COMPANY HQ\n"
        "DESTINATION: AIRPORT TERMINAL 3\n"
        "DISTANCE: 18.4 KM\n"
        "FARE R$ 64.80"
    ),
    "REQ-0003": (
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
}


def _submission(request_id: str, raw_ocr_text: str) -> ReimbursementSubmission:
    return ReimbursementSubmission(
        request_id=request_id,
        submitted_by="employee@example.com",
        submitted_at=datetime(2026, 4, 13, tzinfo=UTC),
        raw_ocr_text=raw_ocr_text,
        claimed_category="test-category",
        claimed_amount=Money.brl("1.00"),
    )


@pytest.mark.parametrize(
    ("request_id", "expected_date", "expected_total", "category", "merchant", "tax_id"),
    [
        (
            "REQ-0001",
            date(2026, 4, 9),
            Decimal("93.50"),
            "meals",
            "BOM SABOR RESTAURANT LTD",
            "12.345.678/0001-90",
        ),
        (
            "REQ-0002",
            date(2026, 4, 11),
            Decimal("64.80"),
            "transportation",
            "URBAN TAXI SERVICES",
            "23.456.789/0001-12",
        ),
        (
            "REQ-0003",
            date(2026, 4, 12),
            Decimal("640.00"),
            "lodging",
            "GRAND PLAZA HOTEL",
            "45.678.901/0001-56",
        ),
    ],
)
def test_deterministic_extractor_covers_assignment_samples(
    request_id: str,
    expected_date: date,
    expected_total: Decimal,
    category: str,
    merchant: str,
    tax_id: str,
) -> None:
    extractor = DeterministicReceiptExtractor()

    result = extractor.extract(_submission(request_id, SAMPLE_OCR[request_id]))

    assert isinstance(extractor, ReceiptExtractor)
    assert result.status is ExtractionStatus.SUCCEEDED
    assert result.facts is not None
    assert result.facts.receipt_date == expected_date
    assert result.facts.total is not None
    assert result.facts.total.amount == expected_total
    assert result.facts.category == category
    assert result.facts.merchant_name == merchant
    assert result.facts.tax_id == tax_id
    assert set(result.facts.evidence) >= {
        "merchant_name",
        "tax_id",
        "receipt_date",
        "total",
        "category",
    }

    trace = result.trace
    assert extractor.provider == trace.provider
    assert extractor.model == trace.model
    assert extractor.prompt_version == trace.prompt_version
    assert extractor.prompt_hash == trace.prompt_hash
    assert trace.provider == "offline-deterministic"
    assert trace.model == "assessment-receipt-parser-v1"
    assert trace.prompt_version == "receipt-extraction-v1"
    assert trace.input_hash == hashlib.sha256(SAMPLE_OCR[request_id].encode()).hexdigest()
    assert len(trace.prompt_hash) == 64
    assert trace.invoked_at.utcoffset() is not None
    assert trace.duration_ms >= 0
    assert trace.parameters == {"deterministic": True, "network": False}
    assert json.loads(trace.raw_response)["merchant_name"] == merchant


def test_deterministic_extractor_preserves_missing_facts_instead_of_guessing() -> None:
    raw_ocr_text = "UNKNOWN SHOP\nTAX ID 12.345.678/0001-90\nDESCRIPTION ONLY"

    result = DeterministicReceiptExtractor().extract(_submission("REQ-PARTIAL", raw_ocr_text))

    assert result.status is ExtractionStatus.SUCCEEDED
    assert result.facts is not None
    assert result.facts.receipt_date is None
    assert result.facts.total is None
    assert result.facts.category is None
    assert "receipt date was not found" in result.facts.warnings
    assert "receipt total was not found" in result.facts.warnings
    assert "receipt category was not found" in result.facts.warnings


def test_deterministic_extractor_returns_traced_failure_for_invalid_explicit_date() -> None:
    raw_ocr_text = "SHOP\nDATE 31/02/2026\nTOTAL R$ 10.00"

    result = DeterministicReceiptExtractor().extract(_submission("REQ-BAD-DATE", raw_ocr_text))

    assert result.status is ExtractionStatus.FAILED
    assert result.error == "receipt extraction failed"
    assert result.facts is None
    assert result.trace.input_hash == hashlib.sha256(raw_ocr_text.encode()).hexdigest()


class StubResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def read(self, amount: int = -1) -> bytes:
        return self.body if amount < 0 else self.body[:amount]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


class RecordingTransport:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.request: Request | None = None
        self.timeout: float | None = None

    def __call__(self, request: Request, timeout: float) -> StubResponse:
        self.request = request
        self.timeout = timeout
        return StubResponse(self.body)


def _valid_provider_payload() -> dict[str, object]:
    return {
        "receipt_date": "2026-04-09",
        "total": {"amount": "93.50", "currency": "BRL"},
        "category": "meals",
        "merchant_name": "BOM SABOR RESTAURANT LTD",
        "tax_id": "12.345.678/0001-90",
        "evidence": {"total": "TOTAL R$ 93.50"},
        "warnings": [],
    }


def test_http_adapter_sends_bounded_configured_request_and_builds_complete_trace() -> None:
    secret = "never-print-this-secret"
    raw_response = json.dumps(_valid_provider_payload())
    transport = RecordingTransport(raw_response.encode())
    config = HttpJsonExtractorConfig(
        endpoint="https://extractor.example.test/v1/extract",
        provider="configured-provider",
        model="receipt-model-2026-04",
        api_key=secret,
        timeout_seconds=3.5,
        parameters={"temperature": 0, "seed": 42},
    )

    extractor = HttpJsonReceiptExtractor(config, transport=transport)
    assert isinstance(extractor, ReceiptExtractor)
    result = extractor.extract(_submission("REQ-HTTP", SAMPLE_OCR["REQ-0001"]))

    assert secret not in repr(config)
    assert result.status is ExtractionStatus.SUCCEEDED
    assert result.facts is not None
    assert result.facts.total is not None
    assert result.facts.total.amount == Decimal("93.50")
    assert result.trace.raw_response == raw_response
    assert result.trace.provider == "configured-provider"
    assert result.trace.model == "receipt-model-2026-04"
    assert result.trace.parameters == {"temperature": 0, "seed": 42}
    assert extractor.provider == result.trace.provider
    assert extractor.model == result.trace.model
    assert extractor.prompt_version == result.trace.prompt_version
    assert extractor.prompt_hash == result.trace.prompt_hash

    assert transport.request is not None
    assert transport.timeout == 3.5
    assert transport.request.method == "POST"
    assert transport.request.get_header("Authorization") == f"Bearer {secret}"
    sent = json.loads(transport.request.data or b"")
    assert sent["request_id"] == "REQ-HTTP"
    assert sent["raw_ocr_text"] == SAMPLE_OCR["REQ-0001"]
    assert sent["prompt_version"] == "receipt-extraction-v1"
    assert sent["parameters"] == {"temperature": 0, "seed": 42}


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"not-json", "response must be valid JSON"),
        (
            json.dumps({**_valid_provider_payload(), "unexpected": True}).encode(),
            "response contains unexpected keys",
        ),
        (
            json.dumps({**_valid_provider_payload(), "total": 93.5}).encode(),
            "total must contain only amount and currency",
        ),
        (
            (
                b'{"receipt_date":null,"receipt_date":null,"total":null,'
                b'"category":null,"merchant_name":null,"tax_id":null,'
                b'"evidence":{},"warnings":[]}'
            ),
            "response contains a duplicate key",
        ),
        (
            json.dumps(
                {**_valid_provider_payload(), "total": {"amount": "9.35e1", "currency": "BRL"}}
            ).encode(),
            "total.amount must use a plain non-negative decimal string",
        ),
    ],
)
def test_http_adapter_rejects_malformed_or_schema_invalid_provider_json(
    body: bytes,
    message: str,
) -> None:
    extractor = HttpJsonReceiptExtractor(
        HttpJsonExtractorConfig(
            endpoint="https://extractor.example.test/v1/extract",
            provider="provider",
            model="model",
        ),
        transport=RecordingTransport(body),
    )

    result = extractor.extract(_submission("REQ-INVALID", "TOTAL R$ 1.00"))

    assert result.status is ExtractionStatus.FAILED
    assert result.facts is None
    assert result.error is not None
    assert result.error.startswith("provider response validation failed:")
    assert message in result.error
    assert result.trace.raw_response == body.decode()


def test_http_adapter_bounds_provider_response_without_retaining_partial_body() -> None:
    extractor = HttpJsonReceiptExtractor(
        HttpJsonExtractorConfig(
            endpoint="https://extractor.example.test/v1/extract",
            provider="provider",
            model="model",
            max_response_bytes=1_024,
        ),
        transport=RecordingTransport(b"x" * 1_025),
    )

    result = extractor.extract(_submission("REQ-LARGE", "TOTAL R$ 1.00"))

    assert result.status is ExtractionStatus.FAILED
    assert result.error == "provider response exceeds configured byte limit"
    assert result.trace.raw_response == ""


def test_http_adapter_turns_timeout_into_failure_and_never_exposes_secret() -> None:
    secret = "provider-key-must-stay-private"

    def timeout_transport(request: Request, timeout: float) -> StubResponse:
        raise TimeoutError("details that must not escape")

    config = HttpJsonExtractorConfig(
        endpoint="https://extractor.example.test/v1/extract",
        provider="provider",
        model="model",
        api_key=secret,
    )

    result = HttpJsonReceiptExtractor(config, transport=timeout_transport).extract(
        _submission("REQ-TIMEOUT", "TOTAL R$ 1.00")
    )

    assert result.status is ExtractionStatus.FAILED
    assert result.error == "provider request timed out"
    assert secret not in repr(config)
    assert secret not in (result.error or "")
    assert secret not in result.trace.raw_response


def test_default_http_transport_rejects_redirects_before_authorization_can_move(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = StubResponse(b"{}")
    installed_handlers: list[object] = []

    class StubOpener:
        def open(self, request: Request, *, timeout: float) -> StubResponse:
            assert request.full_url == "https://extractor.example.test/v1/extract"
            assert timeout == 3.5
            return response

    def build_opener(*handlers: object) -> StubOpener:
        installed_handlers.extend(handlers)
        return StubOpener()

    monkeypatch.setattr(http_json, "build_opener", build_opener)
    request = Request(
        "https://extractor.example.test/v1/extract",
        headers={"Authorization": "Bearer must-not-move"},
    )

    assert http_json._urlopen(request, 3.5) is response
    redirect_handler = next(
        handler
        for handler in installed_handlers
        if isinstance(handler, http_json._RejectRedirects)
    )
    with pytest.raises(http_json.HTTPError, match="redirects are not allowed"):
        redirect_handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://attacker.example.test/capture",
        )


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://extractor.example.test/v1/extract",
        "https://user:password@extractor.example.test/v1/extract",
        "https://extractor.example.test/v1/extract?api_key=secret",
    ],
)
def test_http_config_rejects_insecure_or_secret_bearing_endpoint(endpoint: str) -> None:
    with pytest.raises(ValueError):
        HttpJsonExtractorConfig(endpoint=endpoint, provider="provider", model="model")


def test_http_descriptor_is_normalized_before_an_invocation_is_registered() -> None:
    config = HttpJsonExtractorConfig(
        endpoint="https://extractor.example.test/v1/extract",
        provider=" configured-provider ",
        model=" model-v1 ",
        prompt_version=" prompt-v1 ",
    )
    extractor = HttpJsonReceiptExtractor(config, transport=RecordingTransport(b"{}"))

    assert extractor.provider == "configured-provider"
    assert extractor.model == "model-v1"
    assert extractor.prompt_version == "prompt-v1"
    assert len(extractor.prompt_hash) == 64
