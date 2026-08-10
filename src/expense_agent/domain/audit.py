"""Append-only audit event contract."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from expense_agent.domain._validation import require_aware_datetime, require_non_blank


@dataclass(frozen=True, slots=True)
class AuditActor:
    actor_type: str
    actor_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "actor_type",
            require_non_blank(self.actor_type, "actor_type"),
        )
        object.__setattr__(self, "actor_id", require_non_blank(self.actor_id, "actor_id"))


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Immutable fact to persist in an append-only audit store."""

    event_id: str
    request_id: str
    event_type: str
    occurred_at: datetime
    actor: AuditActor
    correlation_id: str
    payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("event_id", "request_id", "event_type", "correlation_id"):
            object.__setattr__(
                self,
                field_name,
                require_non_blank(getattr(self, field_name), field_name),
            )
        require_aware_datetime(self.occurred_at, "occurred_at")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))
