"""Value objects used throughout the reimbursement domain."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from expense_agent.domain.exceptions import DomainValidationError


class Currency(str, Enum):
    BRL = "BRL"


@dataclass(frozen=True, slots=True)
class Money:
    """An exact monetary amount.

    The domain accepts ``Decimal`` only so a binary floating-point value cannot
    silently enter a financial decision. Conversion from JSON strings or
    numbers belongs to the API boundary.
    """

    amount: Decimal
    currency: Currency = Currency.BRL

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise DomainValidationError("Money.amount must be a Decimal")
        if not self.amount.is_finite():
            raise DomainValidationError("Money.amount must be finite")
        if self.amount < Decimal(0):
            raise DomainValidationError("Money.amount must not be negative")
        if self.amount.as_tuple().exponent < -2:
            raise DomainValidationError("Money.amount must have at most two decimal places")
        if not isinstance(self.currency, Currency):
            raise DomainValidationError("Money.currency must be a supported Currency")

    @classmethod
    def brl(cls, amount: str) -> "Money":
        """Create BRL safely from a decimal string."""

        try:
            decimal_amount = Decimal(amount)
        except Exception as exc:  # Decimal exposes multiple conversion failures.
            raise DomainValidationError("amount must be a valid decimal string") from exc
        return cls(amount=decimal_amount, currency=Currency.BRL)

    def __str__(self) -> str:
        return f"{self.currency.value} {self.amount.quantize(Decimal('0.01'))}"
