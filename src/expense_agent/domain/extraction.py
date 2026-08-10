"""Objects produced by the probabilistic receipt extraction boundary."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from types import MappingProxyType

from expense_agent.domain._validation import require_aware_datetime, require_non_blank
from expense_agent.domain.exceptions import DomainValidationError
from expense_agent.domain.value_objects import Money


class ExtractionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ReceiptFacts:
    """Facts extracted from OCR text.

    Critical fields are optional because an uncertain or incomplete extraction
    is a valid outcome that should normally route the request to human review.
    """

    receipt_date: date | None = None
    total: Money | None = None
    category: str | None = None
    merchant_name: str | None = None
    tax_id: str | None = None
    evidence: Mapping[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.category is not None:
            object.__setattr__(self, "category", require_non_blank(self.category, "category"))
        if self.merchant_name is not None:
            object.__setattr__(
                self,
                "merchant_name",
                require_non_blank(self.merchant_name, "merchant_name"),
            )
        if self.tax_id is not None:
            object.__setattr__(self, "tax_id", require_non_blank(self.tax_id, "tax_id"))

        normalized_evidence: dict[str, str] = {}
        for key, value in self.evidence.items():
            normalized_key = require_non_blank(key, "evidence key")
            normalized_evidence[normalized_key] = require_non_blank(value, "evidence value")
        object.__setattr__(self, "evidence", MappingProxyType(normalized_evidence))
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True, slots=True)
class ModelInvocationTrace:
    """Reproducibility metadata for one model invocation."""

    provider: str
    model: str
    prompt_version: str
    prompt_hash: str
    input_hash: str
    raw_response: str
    invoked_at: datetime
    duration_ms: int
    parameters: Mapping[str, str | int | float | bool | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("provider", "model", "prompt_version", "prompt_hash", "input_hash"):
            object.__setattr__(
                self,
                field_name,
                require_non_blank(getattr(self, field_name), field_name),
            )
        require_aware_datetime(self.invoked_at, "invoked_at")
        if self.duration_ms < 0:
            raise DomainValidationError("duration_ms must not be negative")
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Success or failure returned by a receipt extractor."""

    request_id: str
    status: ExtractionStatus
    trace: ModelInvocationTrace
    facts: ReceiptFacts | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_blank(self.request_id, "request_id"))
        if self.status is ExtractionStatus.SUCCEEDED:
            if self.facts is None or self.error is not None:
                raise DomainValidationError(
                    "a successful extraction requires facts and must not contain an error"
                )
        elif self.status is ExtractionStatus.FAILED:
            if self.facts is not None or self.error is None:
                raise DomainValidationError(
                    "a failed extraction requires an error and must not contain facts"
                )
            object.__setattr__(self, "error", require_non_blank(self.error, "error"))
        else:
            raise DomainValidationError("unsupported extraction status")
