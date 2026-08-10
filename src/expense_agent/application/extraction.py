"""Application port for probabilistic or deterministic receipt extraction."""

from typing import Protocol, runtime_checkable

from expense_agent.domain import ExtractionResult, ReimbursementSubmission


@runtime_checkable
class ReceiptExtractor(Protocol):
    """Extract auditable receipt facts without owning financial policy decisions."""

    @property
    def provider(self) -> str:
        """Stable, non-secret provider identifier available before invocation."""

    @property
    def model(self) -> str:
        """Exact model/parser identifier available before invocation."""

    @property
    def prompt_version(self) -> str:
        """Version of the extraction instruction contract."""

    @property
    def prompt_hash(self) -> str:
        """SHA-256 of the exact extraction prompt without exposing its contents."""

    def extract(self, submission: ReimbursementSubmission) -> ExtractionResult:
        """Return extracted evidence or a traced failure for one reimbursement."""
