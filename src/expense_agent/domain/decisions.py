"""Immutable automated and human decision records."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType

from expense_agent.domain._validation import require_aware_datetime, require_non_blank
from expense_agent.domain.exceptions import DomainValidationError


class PolicyDecisionRoute(str, Enum):
    AUTO_APPROVED = "auto_approved"
    HUMAN_REVIEW = "human_review"
    REJECTED = "rejected"


class RuleOutcome(str, Enum):
    PASS = "pass"
    REVIEW = "review"
    REJECT = "reject"


class ReviewOutcome(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class DecisionReason:
    code: str
    message: str
    evidence: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", require_non_blank(self.code, "reason code"))
        object.__setattr__(self, "message", require_non_blank(self.message, "reason message"))
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))


@dataclass(frozen=True, slots=True)
class RuleEvaluation:
    rule_id: str
    rule_version: str
    outcome: RuleOutcome
    message: str
    facts: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", require_non_blank(self.rule_id, "rule_id"))
        object.__setattr__(
            self,
            "rule_version",
            require_non_blank(self.rule_version, "rule_version"),
        )
        object.__setattr__(self, "message", require_non_blank(self.message, "message"))
        if not isinstance(self.outcome, RuleOutcome):
            raise DomainValidationError("outcome must be a RuleOutcome")
        object.__setattr__(self, "facts", MappingProxyType(dict(self.facts)))


@dataclass(frozen=True, slots=True)
class AutomatedDecision:
    decision_id: str
    request_id: str
    route: PolicyDecisionRoute
    decided_at: datetime
    policy_version: str
    reasons: tuple[DecisionReason, ...]
    rule_evaluations: tuple[RuleEvaluation, ...]

    def __post_init__(self) -> None:
        for field_name in ("decision_id", "request_id", "policy_version"):
            object.__setattr__(
                self,
                field_name,
                require_non_blank(getattr(self, field_name), field_name),
            )
        require_aware_datetime(self.decided_at, "decided_at")
        if not isinstance(self.route, PolicyDecisionRoute):
            raise DomainValidationError("route must be a PolicyDecisionRoute")
        object.__setattr__(self, "reasons", tuple(self.reasons))
        object.__setattr__(self, "rule_evaluations", tuple(self.rule_evaluations))
        if not self.reasons:
            raise DomainValidationError("an automated decision requires at least one reason")
        if not self.rule_evaluations:
            raise DomainValidationError(
                "an automated decision requires at least one rule evaluation"
            )


@dataclass(frozen=True, slots=True)
class HumanDecision:
    decision_id: str
    request_id: str
    outcome: ReviewOutcome
    reviewer: str
    reason: str
    decided_at: datetime

    def __post_init__(self) -> None:
        for field_name in ("decision_id", "request_id", "reviewer", "reason"):
            object.__setattr__(
                self,
                field_name,
                require_non_blank(getattr(self, field_name), field_name),
            )
        require_aware_datetime(self.decided_at, "decided_at")
        if not isinstance(self.outcome, ReviewOutcome):
            raise DomainValidationError("outcome must be a ReviewOutcome")
