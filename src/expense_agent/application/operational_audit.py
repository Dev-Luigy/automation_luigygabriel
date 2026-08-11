"""Application contract for sanitized service-operation audit records."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from expense_agent.domain._validation import require_aware_datetime, require_non_blank
from expense_agent.domain.exceptions import DomainValidationError

_OPERATION_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_HTTP_METHOD_PATTERN = re.compile(r"^[A-Z]{1,16}$")
_METADATA_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SENSITIVE_METADATA_KEY_PARTS = (
    "authorization",
    "body",
    "cookie",
    "credential",
    "ocr",
    "password",
    "query",
    "response",
    "secret",
    "token",
)
_MAX_METADATA_ENTRIES = 12
_MAX_METADATA_STRING_LENGTH = 256
_MAX_METADATA_JSON_BYTES = 4_096


class OperationalAuditOutcome(str, Enum):
    """Coarse HTTP outcome that does not copy response content."""

    SUCCEEDED = "succeeded"
    CLIENT_ERROR = "client_error"
    SERVER_ERROR = "server_error"


class OperationalAuthenticationOutcome(str, Enum):
    """Authentication result observed during one HTTP request."""

    NOT_ATTEMPTED = "not_attempted"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


OperationalMetadataValue = str | int | bool


@dataclass(frozen=True, slots=True)
class OperationalAuditEvent:
    """One bounded, privacy-aware record for a service request attempt."""

    event_id: str
    occurred_at: datetime
    correlation_id: str
    operation_type: str
    http_method: str
    route: str
    status_code: int
    outcome: OperationalAuditOutcome
    authentication: OperationalAuthenticationOutcome
    duration_ms: int
    request_id: str | None = None
    actor_type: str | None = None
    actor_id: str | None = None
    metadata: Mapping[str, OperationalMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name, maximum in (
            ("event_id", 64),
            ("correlation_id", 128),
            ("operation_type", 64),
            ("http_method", 16),
            ("route", 256),
        ):
            normalized = require_non_blank(getattr(self, field_name), field_name)
            if len(normalized) > maximum:
                raise DomainValidationError(f"{field_name} must contain at most {maximum} chars")
            object.__setattr__(self, field_name, normalized)

        require_aware_datetime(self.occurred_at, "occurred_at")
        if _OPERATION_TYPE_PATTERN.fullmatch(self.operation_type) is None:
            raise DomainValidationError("operation_type must be a stable lowercase identifier")
        if _HTTP_METHOD_PATTERN.fullmatch(self.http_method) is None:
            raise DomainValidationError("http_method must be uppercase ASCII letters")
        if any(character in self.route for character in ("?", "#", "\r", "\n")):
            raise DomainValidationError("route must be a template or bounded classification")
        if (
            not isinstance(self.status_code, int)
            or isinstance(self.status_code, bool)
            or not 100 <= self.status_code <= 599
        ):
            raise DomainValidationError("status_code must be an HTTP status code")
        if not isinstance(self.outcome, OperationalAuditOutcome):
            raise DomainValidationError("outcome must be an OperationalAuditOutcome")
        if not isinstance(self.authentication, OperationalAuthenticationOutcome):
            raise DomainValidationError(
                "authentication must be an OperationalAuthenticationOutcome"
            )
        if (
            not isinstance(self.duration_ms, int)
            or isinstance(self.duration_ms, bool)
            or self.duration_ms < 0
        ):
            raise DomainValidationError("duration_ms must be a non-negative integer")

        self._normalize_optional_identity()
        object.__setattr__(self, "metadata", MappingProxyType(self._normalize_metadata()))

    def _normalize_optional_identity(self) -> None:
        if self.request_id is not None:
            request_id = require_non_blank(self.request_id, "request_id")
            if len(request_id) > 128:
                raise DomainValidationError("request_id must contain at most 128 chars")
            object.__setattr__(self, "request_id", request_id)

        if (self.actor_type is None) != (self.actor_id is None):
            raise DomainValidationError("actor_type and actor_id must be supplied together")
        if self.actor_type is None:
            return
        actor_type = require_non_blank(self.actor_type, "actor_type")
        actor_id = require_non_blank(self.actor_id, "actor_id")
        if len(actor_type) > 64:
            raise DomainValidationError("actor_type must contain at most 64 chars")
        if len(actor_id) > 320:
            raise DomainValidationError("actor_id must contain at most 320 chars")
        object.__setattr__(self, "actor_type", actor_type)
        object.__setattr__(self, "actor_id", actor_id)

    def _normalize_metadata(self) -> dict[str, OperationalMetadataValue]:
        normalized = dict(self.metadata)
        if len(normalized) > _MAX_METADATA_ENTRIES:
            raise DomainValidationError(
                f"metadata must contain at most {_MAX_METADATA_ENTRIES} entries"
            )
        for key, value in normalized.items():
            if not isinstance(key, str) or _METADATA_KEY_PATTERN.fullmatch(key) is None:
                raise DomainValidationError("metadata keys must be stable lowercase identifiers")
            if any(part in key for part in _SENSITIVE_METADATA_KEY_PARTS):
                raise DomainValidationError("sensitive metadata keys are forbidden")
            if not isinstance(value, (str, int, bool)):
                raise DomainValidationError("metadata values must be scalar JSON values")
            if isinstance(value, str) and len(value) > _MAX_METADATA_STRING_LENGTH:
                raise DomainValidationError(
                    "metadata strings must contain at most "
                    f"{_MAX_METADATA_STRING_LENGTH} chars"
                )
        encoded = json.dumps(
            normalized,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        if len(encoded) > _MAX_METADATA_JSON_BYTES:
            raise DomainValidationError(
                f"metadata JSON must contain at most {_MAX_METADATA_JSON_BYTES} bytes"
            )
        return normalized


@runtime_checkable
class OperationalAuditRecorder(Protocol):
    """Append-only persistence boundary used by the HTTP adapter."""

    def record_operation(self, event: OperationalAuditEvent) -> None: ...


__all__ = [
    "OperationalAuditEvent",
    "OperationalAuditOutcome",
    "OperationalAuditRecorder",
    "OperationalAuthenticationOutcome",
    "OperationalMetadataValue",
]
