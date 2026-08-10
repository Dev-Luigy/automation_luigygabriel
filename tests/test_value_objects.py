from decimal import Decimal

import pytest

from expense_agent.domain import DomainValidationError, Money


def test_money_preserves_exact_brl_amount() -> None:
    money = Money.brl("93.50")

    assert money.amount == Decimal("93.50")
    assert str(money) == "BRL 93.50"


@pytest.mark.parametrize("value", [93.50, 93, "93.50"])
def test_money_rejects_non_decimal_constructor_values(value: object) -> None:
    with pytest.raises(DomainValidationError, match="must be a Decimal"):
        Money(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["-0.01", "10.001", "NaN", "Infinity"])
def test_money_rejects_invalid_financial_values(value: str) -> None:
    with pytest.raises(DomainValidationError):
        Money(amount=Decimal(value))
