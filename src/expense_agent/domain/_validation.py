"""Small validation helpers shared by domain objects."""

from datetime import datetime

from expense_agent.domain.exceptions import DomainValidationError


def require_non_blank(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DomainValidationError(f"{field_name} must not be blank")
    return value.strip()


def require_aware_datetime(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise DomainValidationError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise DomainValidationError(f"{field_name} must include timezone information")
    return value
