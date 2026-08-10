"""Domain-specific exceptions."""


class DomainError(Exception):
    """Base error raised by the domain layer."""


class DomainValidationError(DomainError, ValueError):
    """Raised when an object would be created with invalid domain data."""


class InvalidStateTransition(DomainError):
    """Raised when an aggregate receives an operation invalid for its state."""
