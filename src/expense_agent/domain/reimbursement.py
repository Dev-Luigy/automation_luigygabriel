"""The reimbursement aggregate and its state transitions."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from expense_agent.domain._validation import require_aware_datetime, require_non_blank
from expense_agent.domain.decisions import (
    AutomatedDecision,
    HumanDecision,
    PolicyDecisionRoute,
    ReviewOutcome,
)
from expense_agent.domain.exceptions import (
    DomainValidationError,
    InvalidStateTransition,
)
from expense_agent.domain.value_objects import Money


class ReimbursementStatus(str, Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    AUTO_APPROVED = "auto_approved"
    PENDING_REVIEW = "pending_review"
    APPROVED_AFTER_REVIEW = "approved_after_review"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class AttachmentReference:
    """A stable reference to an attachment stored outside the domain model."""

    location: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "location", require_non_blank(self.location, "location"))


@dataclass(frozen=True, slots=True)
class ReimbursementSubmission:
    """The immutable input snapshot received from an employee."""

    request_id: str
    submitted_by: str
    submitted_at: datetime
    raw_ocr_text: str
    claimed_category: str
    claimed_amount: Money
    attachments: tuple[AttachmentReference, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("request_id", "submitted_by", "raw_ocr_text", "claimed_category"):
            object.__setattr__(
                self,
                field_name,
                require_non_blank(getattr(self, field_name), field_name),
            )
        require_aware_datetime(self.submitted_at, "submitted_at")
        if not isinstance(self.claimed_amount, Money):
            raise DomainValidationError("claimed_amount must be Money")
        if self.claimed_amount.amount <= 0:
            raise DomainValidationError("claimed_amount must be greater than zero")
        object.__setattr__(self, "attachments", tuple(self.attachments))
        if not all(isinstance(item, AttachmentReference) for item in self.attachments):
            raise DomainValidationError("attachments must contain AttachmentReference values")


DecisionRecord = AutomatedDecision | HumanDecision


@dataclass(slots=True)
class ReimbursementCase:
    """Aggregate root controlling the reimbursement workflow.

    Decisions are append-only. Callers cannot replace the history or skip the
    human-review gate through a direct status assignment.
    """

    submission: ReimbursementSubmission
    opened_at: datetime
    _status: ReimbursementStatus = field(
        default=ReimbursementStatus.RECEIVED,
        init=False,
        repr=False,
    )
    _decisions: list[DecisionRecord] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.submission, ReimbursementSubmission):
            raise DomainValidationError("submission must be a ReimbursementSubmission")
        require_aware_datetime(self.opened_at, "opened_at")

    @property
    def request_id(self) -> str:
        return self.submission.request_id

    @property
    def status(self) -> ReimbursementStatus:
        return self._status

    @property
    def decisions(self) -> tuple[DecisionRecord, ...]:
        return tuple(self._decisions)

    def start_processing(self) -> None:
        self._require_status(ReimbursementStatus.RECEIVED)
        self._status = ReimbursementStatus.PROCESSING

    def record_automated_decision(self, decision: AutomatedDecision) -> None:
        self._require_status(ReimbursementStatus.PROCESSING)
        self._require_matching_request(decision.request_id)

        next_status = {
            PolicyDecisionRoute.AUTO_APPROVED: ReimbursementStatus.AUTO_APPROVED,
            PolicyDecisionRoute.HUMAN_REVIEW: ReimbursementStatus.PENDING_REVIEW,
            PolicyDecisionRoute.REJECTED: ReimbursementStatus.REJECTED,
        }[decision.route]

        self._decisions.append(decision)
        self._status = next_status

    def record_human_decision(self, decision: HumanDecision) -> None:
        self._require_status(ReimbursementStatus.PENDING_REVIEW)
        self._require_matching_request(decision.request_id)

        next_status = {
            ReviewOutcome.APPROVED: ReimbursementStatus.APPROVED_AFTER_REVIEW,
            ReviewOutcome.REJECTED: ReimbursementStatus.REJECTED,
        }[decision.outcome]

        self._decisions.append(decision)
        self._status = next_status

    def _require_status(self, expected: ReimbursementStatus) -> None:
        if self._status is not expected:
            raise InvalidStateTransition(
                f"operation requires status {expected.value}; current status is {self._status.value}"
            )

    def _require_matching_request(self, decision_request_id: str) -> None:
        if decision_request_id != self.request_id:
            raise DomainValidationError("decision request_id does not match the case")
