from datetime import UTC, datetime

import pytest

from expense_agent.domain import (
    DomainValidationError,
    ExtractionResult,
    ExtractionStatus,
    ModelInvocationTrace,
    ReceiptFacts,
)


def trace() -> ModelInvocationTrace:
    return ModelInvocationTrace(
        provider="test-provider",
        model="test-model-v1",
        prompt_version="receipt-extraction-v1",
        prompt_hash="prompt-sha256",
        input_hash="input-sha256",
        raw_response="{}",
        invoked_at=datetime(2026, 4, 10, tzinfo=UTC),
        duration_ms=12,
        parameters={"temperature": 0},
    )


def test_partial_facts_are_a_valid_successful_extraction() -> None:
    result = ExtractionResult(
        request_id="REQ-0001",
        status=ExtractionStatus.SUCCEEDED,
        trace=trace(),
        facts=ReceiptFacts(warnings=("total was not found",)),
    )

    assert result.facts is not None
    assert result.facts.total is None


def test_failed_extraction_cannot_contain_facts() -> None:
    with pytest.raises(DomainValidationError, match="failed extraction"):
        ExtractionResult(
            request_id="REQ-0001",
            status=ExtractionStatus.FAILED,
            trace=trace(),
            facts=ReceiptFacts(),
            error="model timeout",
        )
