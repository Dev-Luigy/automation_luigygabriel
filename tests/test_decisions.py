from datetime import UTC, datetime

import pytest

from expense_agent.domain import (
    AutomatedDecision,
    DomainValidationError,
    PolicyDecisionRoute,
)


def test_automated_decision_requires_explanation_and_rule_trace() -> None:
    with pytest.raises(DomainValidationError, match="at least one reason"):
        AutomatedDecision(
            decision_id="DEC-0001",
            request_id="REQ-0001",
            route=PolicyDecisionRoute.AUTO_APPROVED,
            decided_at=datetime(2026, 4, 10, tzinfo=UTC),
            policy_version="baseline-v1",
            reasons=(),
            rule_evaluations=(),
        )
