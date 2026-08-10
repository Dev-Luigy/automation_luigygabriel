"""FastAPI adapter for the non-technical, same-origin review screen."""

import hashlib
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from expense_agent.application.review import (
    PendingAgeBucket,
    ReviewCaseDetails,
    ReviewConflictError,
    ReviewerIdentity,
    ReviewEventPage,
    ReviewEventQuery,
    ReviewNotFoundError,
    ReviewQueueItem,
    ReviewQueuePage,
    ReviewQueueQuery,
    ReviewQueueSort,
    ReviewService,
)
from expense_agent.domain.decisions import ReviewOutcome
from expense_agent.domain.exceptions import DomainValidationError
from expense_agent.domain.extraction import ExtractionResult, ReceiptFacts
from expense_agent.domain.value_objects import Money
from expense_agent.presentation.security import (
    BasicAuthenticator,
    CsrfProtector,
    ReviewerPrincipal,
)

STATIC_DIRECTORY = Path(__file__).with_name("static")
CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
CONTENT_SECURITY_POLICY = (
    "default-src 'none'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: ReviewOutcome
    reason: str = Field(min_length=1, max_length=2_000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("reason must not be blank")
        return normalized


class ReviewQueueRequest(BaseModel):
    """Bounded, language-neutral HTTP query contract for the reviewer queue."""

    model_config = ConfigDict(extra="forbid")

    search: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=200)
    problem_code: str | None = Field(default=None, min_length=1, max_length=200)
    min_amount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=18,
        decimal_places=2,
    )
    max_amount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=18,
        decimal_places=2,
    )
    submitted_from: datetime | None = None
    submitted_to: datetime | None = None
    pending_before: datetime | None = None
    age_bucket: PendingAgeBucket | None = None
    sort: ReviewQueueSort = ReviewQueueSort.PENDING_OLDEST
    limit: int = Field(default=25, ge=10, le=100)
    cursor: str | None = Field(default=None, min_length=1, max_length=4096)

    @field_validator("search", "category", "problem_code", "cursor")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("submitted_from", "submitted_to", "pending_before")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("datetime must include timezone information")
        return value

    @model_validator(mode="after")
    def validate_ranges(self) -> "ReviewQueueRequest":
        if (
            self.min_amount is not None
            and self.max_amount is not None
            and self.min_amount > self.max_amount
        ):
            raise ValueError("min_amount must not exceed max_amount")
        if (
            self.submitted_from is not None
            and self.submitted_to is not None
            and self.submitted_from > self.submitted_to
        ):
            raise ValueError("submitted_from must not be after submitted_to")
        if self.pending_before is not None and self.age_bucket is not None:
            raise ValueError("pending_before and age_bucket cannot be combined")
        return self

    def to_query(self) -> ReviewQueueQuery:
        return ReviewQueueQuery(
            search=self.search,
            category=self.category,
            problem_code=self.problem_code,
            min_amount=Money(self.min_amount) if self.min_amount is not None else None,
            max_amount=Money(self.max_amount) if self.max_amount is not None else None,
            submitted_from=self.submitted_from,
            submitted_to=self.submitted_to,
            pending_before=self.pending_before,
            age_bucket=self.age_bucket,
            sort=self.sort,
            page_size=self.limit,
            cursor=self.cursor,
        )


class ReviewEventRequest(BaseModel):
    """Bounded HTTP query for a sanitized business-event timeline."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=25, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=1, max_length=4096)

    @field_validator("cursor")
    @classmethod
    def normalize_cursor(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("cursor must not be blank")
        return normalized

    def to_query(self) -> ReviewEventQuery:
        return ReviewEventQuery(page_size=self.limit, cursor=self.cursor)


def create_app(
    *,
    review_service: ReviewService,
    authenticator: BasicAuthenticator,
    csrf: CsrfProtector,
    require_https: bool,
    allowed_hosts: tuple[str, ...],
) -> FastAPI:
    """Create an HTTP adapter around injected application/security ports."""

    app = FastAPI(
        title="Expense Agent human review",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(allowed_hosts))
    app.mount("/assets", StaticFiles(directory=STATIC_DIRECTORY), name="assets")
    basic = HTTPBasic(auto_error=False)

    @app.middleware("http")
    async def transport_and_browser_security(request: Request, call_next):
        if require_https and request.url.scheme != "https":
            response = JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "HTTPS is required"},
            )
        else:
            response = await call_next(request)
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    def current_reviewer(
        credentials: Annotated[HTTPBasicCredentials | None, Depends(basic)],
    ) -> ReviewerPrincipal:
        principal = None
        if credentials is not None:
            principal = authenticator.authenticate(
                credentials.username,
                credentials.password,
            )
        if principal is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Valid reviewer credentials are required",
                headers={"WWW-Authenticate": 'Basic realm="Expense Agent review", charset="UTF-8"'},
            )
        return principal

    def require_csrf_and_same_origin(
        request: Request,
        reviewer: Annotated[ReviewerPrincipal, Depends(current_reviewer)],
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> ReviewerPrincipal:
        content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type != "application/json":
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Content-Type must be application/json",
            )
        if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
            raise HTTPException(status_code=403, detail="Cross-site request blocked")
        origin = request.headers.get("origin")
        expected_origin = str(request.base_url).rstrip("/")
        if origin is None or origin.rstrip("/") != expected_origin:
            raise HTTPException(status_code=403, detail="Same-origin request required")
        if csrf_token is None or not csrf.verify(csrf_token, reviewer.reviewer_id):
            raise HTTPException(status_code=403, detail="Invalid or expired CSRF token")
        return reviewer

    @app.exception_handler(ReviewNotFoundError)
    async def review_not_found_handler(_request: Request, _exc: ReviewNotFoundError):
        return JSONResponse(status_code=404, content={"detail": "Review case not found"})

    @app.exception_handler(ReviewConflictError)
    async def review_conflict_handler(_request: Request, _exc: ReviewConflictError):
        return JSONResponse(
            status_code=409,
            content={"detail": "Review case is no longer pending at that version"},
        )

    @app.exception_handler(DomainValidationError)
    async def domain_validation_handler(_request: Request, exc: DomainValidationError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/reviews", status_code=307)

    @app.get("/reviews", include_in_schema=False)
    def reviews_page(
        _reviewer: Annotated[ReviewerPrincipal, Depends(current_reviewer)],
    ) -> FileResponse:
        return FileResponse(STATIC_DIRECTORY / "reviews.html", media_type="text/html")

    @app.get("/api/session")
    def session(
        reviewer: Annotated[ReviewerPrincipal, Depends(current_reviewer)],
    ) -> dict[str, Any]:
        return {
            "reviewer": {
                "reviewer_id": reviewer.reviewer_id,
                "email": reviewer.email,
                "display_name": reviewer.display_name,
            },
            "csrf_token": csrf.issue(reviewer.reviewer_id),
        }

    @app.get("/api/reviews")
    def pending_reviews(
        query: Annotated[ReviewQueueRequest, Query()],
        _reviewer: Annotated[ReviewerPrincipal, Depends(current_reviewer)],
    ) -> dict[str, Any]:
        return _queue_page(review_service.search_pending(query.to_query()))

    @app.get("/api/reviews/{request_id}")
    def review_details(
        request_id: str,
        _reviewer: Annotated[ReviewerPrincipal, Depends(current_reviewer)],
    ) -> JSONResponse:
        details = review_service.get(request_id)
        return JSONResponse(
            content=_case_details(details),
            headers={"ETag": _etag(details)},
        )

    @app.get("/api/reviews/{request_id}/events")
    def review_events(
        request_id: str,
        query: Annotated[ReviewEventRequest, Query()],
        _reviewer: Annotated[ReviewerPrincipal, Depends(current_reviewer)],
    ) -> dict[str, Any]:
        return _event_page(request_id, review_service.list_events(request_id, query.to_query()))

    @app.post("/api/reviews/{request_id}/decisions", status_code=201)
    def decide(
        request: Request,
        request_id: str,
        command: DecisionRequest,
        reviewer: Annotated[ReviewerPrincipal, Depends(require_csrf_and_same_origin)],
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> JSONResponse:
        if if_match is None:
            raise HTTPException(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                detail="If-Match is required",
            )
        details = review_service.get(request_id)
        if if_match != _etag(details):
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail="The review case version has changed",
            )
        supplied_correlation_id = request.headers.get("X-Correlation-ID", "")
        correlation_id = (
            supplied_correlation_id
            if CORRELATION_ID_PATTERN.fullmatch(supplied_correlation_id)
            else uuid4().hex
        )
        result = review_service.decide(
            request_id=request_id,
            outcome=command.outcome,
            reason=command.reason,
            reviewer=ReviewerIdentity(
                reviewer_id=reviewer.reviewer_id,
                email=reviewer.email,
                display_name=reviewer.display_name,
            ),
            expected_version=details.version,
            correlation_id=correlation_id,
        )
        return JSONResponse(
            status_code=201,
            content={
                "decision_id": result.decision.decision_id,
                "request_id": result.decision.request_id,
                "outcome": result.decision.outcome.value,
                "status": result.resulting_status.value,
                "version": result.version,
                "audit_event_id": result.audit_event_id,
                "decided_at": _timestamp(result.decision.decided_at),
            },
            headers={
                "ETag": _etag_for(request_id, result.version),
                "X-Correlation-ID": correlation_id,
            },
        )

    return app


def _queue_item(item: ReviewQueueItem) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "request_id": item.request_id,
        "submitted_by": item.submitted_by,
        "submitted_at": _timestamp(item.submitted_at),
        "claimed_category": item.claimed_category,
        "claimed_amount": _money(item.claimed_amount),
        "pending_since": _timestamp(item.pending_since),
        "version": item.version,
        "merchant_name": item.merchant_name,
        "extracted_amount": (
            _money(item.extracted_amount) if item.extracted_amount is not None else None
        ),
        "problem_codes": list(item.problem_codes),
    }
    if item.primary_problem is None:
        payload["primary_problem"] = None
    else:
        payload["primary_problem"] = {
            "code": item.primary_problem.code,
            "message": item.primary_problem.message,
        }
    return payload


def _queue_page(page: ReviewQueuePage) -> dict[str, Any]:
    return {
        "items": [_queue_item(item) for item in page.items],
        "page": {
            "limit": page.page_size,
            "sort": page.sort.value,
            "has_more": page.has_more,
            "next_cursor": page.next_cursor,
        },
        "summary": {
            "scope": "all_pending",
            "total_pending": page.summary.total_pending,
            "over_24h": page.summary.over_24h,
            "high_value": page.summary.high_value,
            "amount_mismatch": page.summary.amount_mismatch,
            "high_value_threshold": _money(page.summary.high_value_threshold),
            "as_of": _timestamp(page.summary.as_of),
        },
    }


def _event_page(request_id: str, page: ReviewEventPage) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "kind": "business_audit",
        "items": [
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "occurred_at": _timestamp(event.occurred_at),
                "actor": {
                    "type": event.actor.actor_type,
                    "id": event.actor.actor_id,
                },
                "correlation_id": event.correlation_id,
                "payload": dict(event.payload),
            }
            for event in page.items
        ],
        "page": {
            "limit": page.page_size,
            "sort": "occurred_at_asc",
            "has_more": page.has_more,
            "next_cursor": page.next_cursor,
        },
    }


def _case_details(details: ReviewCaseDetails) -> dict[str, Any]:
    automated = details.automated_decision
    payload: dict[str, Any] = {
        "request_id": details.request_id,
        "submitted_by": details.submission.submitted_by,
        "submitted_at": _timestamp(details.submission.submitted_at),
        "opened_at": _timestamp(details.opened_at),
        "pending_since": _timestamp(details.pending_since),
        "raw_ocr_text": details.raw_ocr_text,
        "claimed_category": details.submission.claimed_category,
        "claimed_amount": _money(details.submission.claimed_amount),
        "status": details.status.value,
        "review_status": details.review_status.value,
        "version": details.version,
        "attachments": [{"location": attachment.location} for attachment in details.attachments],
        "extraction": _extraction(details.extraction),
        "problems": [
            {
                "code": problem.code,
                "message": problem.message,
                "evidence": dict(problem.evidence),
            }
            for problem in details.problems
        ],
        "automated_decision": {
            "decision_id": automated.decision_id,
            "route": automated.route.value,
            "decided_at": _timestamp(automated.decided_at),
            "policy_version": automated.policy_version,
            "reasons": [
                {
                    "code": reason.code,
                    "message": reason.message,
                    "evidence": dict(reason.evidence),
                }
                for reason in automated.reasons
            ],
            "rule_evaluations": [
                {
                    "rule_id": evaluation.rule_id,
                    "rule_version": evaluation.rule_version,
                    "outcome": evaluation.outcome.value,
                    "message": evaluation.message,
                    "facts": dict(evaluation.facts),
                }
                for evaluation in automated.rule_evaluations
            ],
        },
    }
    if details.human_decision is not None and details.reviewed_by is not None:
        payload["human_decision"] = {
            "decision_id": details.human_decision.decision_id,
            "outcome": details.human_decision.outcome.value,
            "reason": details.human_decision.reason,
            "decided_at": _timestamp(details.human_decision.decided_at),
            "reviewer": {
                "reviewer_id": details.reviewed_by.reviewer_id,
                "email": details.reviewed_by.email,
                "display_name": details.reviewed_by.display_name,
            },
        }
    else:
        payload["human_decision"] = None
    return payload


def _extraction(extraction: ExtractionResult | None) -> dict[str, Any] | None:
    if extraction is None:
        return None
    trace = extraction.trace
    return {
        "status": extraction.status.value,
        "error": extraction.error,
        "facts": _receipt_facts(extraction.facts),
        "trace": {
            "provider": trace.provider,
            "model": trace.model,
            "prompt_version": trace.prompt_version,
            "prompt_hash": trace.prompt_hash,
            "input_hash": trace.input_hash,
            "invoked_at": _timestamp(trace.invoked_at),
            "duration_ms": trace.duration_ms,
            "parameters": dict(trace.parameters),
        },
    }


def _receipt_facts(facts: ReceiptFacts | None) -> dict[str, Any] | None:
    if facts is None:
        return None
    return {
        "receipt_date": facts.receipt_date.isoformat() if facts.receipt_date else None,
        "total": _money(facts.total) if facts.total else None,
        "category": facts.category,
        "merchant_name": facts.merchant_name,
        "tax_id": facts.tax_id,
        "evidence": dict(facts.evidence),
        "warnings": list(facts.warnings),
    }


def _money(money: Money) -> dict[str, str]:
    return {"amount": format(money.amount, "f"), "currency": money.currency.value}


def _timestamp(value: datetime) -> str:
    return value.isoformat()


def _etag(details: ReviewCaseDetails) -> str:
    return _etag_for(details.request_id, details.version)


def _etag_for(request_id: str, version: int) -> str:
    request_hash = hashlib.sha256(request_id.encode("utf-8")).hexdigest()[:16]
    return f'"review-{request_hash}-v{version}"'
