"""FastAPI adapter for auditable intake and the same-origin review screen."""

import hashlib
import hmac
import re
import tempfile
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from time import monotonic_ns
from typing import Annotated, Any
from urllib.parse import quote
from uuid import uuid4

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi import Path as ApiPath
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from expense_agent.application import (
    ExtractionSnapshot,
    OperationalAuditEvent,
    OperationalAuditOutcome,
    OperationalAuditRecorder,
    OperationalAuthenticationOutcome,
    PendingAgeBucket,
    ProcessingService,
    RequestConflictError,
    RequestNotFoundError,
    RequestResult,
    ReviewCaseDetails,
    ReviewConflictError,
    ReviewDecisionResult,
    ReviewerIdentity,
    ReviewEventPage,
    ReviewEventQuery,
    ReviewNotFoundError,
    ReviewPreconditionError,
    ReviewQueueItem,
    ReviewQueuePage,
    ReviewQueueQuery,
    ReviewQueueSort,
    ReviewService,
)
from expense_agent.application.attachments import (
    AttachmentAlreadyExists,
    AttachmentIntegrityError,
    AttachmentMediaTypeMismatch,
    AttachmentNotFound,
    AttachmentStore,
    AttachmentTooLarge,
    InvalidAttachmentContent,
    UnsupportedAttachmentMediaType,
)
from expense_agent.domain.attachments import AttachmentId, SafeAttachmentFilename
from expense_agent.domain.audit import AuditActor
from expense_agent.domain.decisions import AutomatedDecision, ReviewOutcome
from expense_agent.domain.exceptions import DomainValidationError
from expense_agent.domain.extraction import ExtractionResult, ReceiptFacts
from expense_agent.domain.reimbursement import AttachmentReference, ReimbursementSubmission
from expense_agent.domain.value_objects import Money
from expense_agent.presentation.security import (
    BasicAuthenticator,
    CsrfProtector,
    ReviewerPrincipal,
)

STATIC_DIRECTORY = Path(__file__).with_name("static")
CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ATTACHMENT_ID_PATTERN = re.compile(r"^att_[0-9a-f]{32}$")
REVIEW_ETAG_PATTERN = re.compile(r'^"review-([0-9a-f]{16})-v([1-9][0-9]*)"$')
MANAGED_ATTACHMENT_PREFIX = "evidence:"
ALLOWED_ATTACHMENT_MEDIA_TYPES = frozenset(
    {"application/pdf", "image/jpeg", "image/png"}
)
SUBMITTER_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DECIMAL_AMOUNT_PATTERN = re.compile(r"^(?:0|[1-9]\d{0,15})(?:\.\d{1,2})?$")
# Below 2**46 a binary64 ULP is at most 0.0078125, so rounding error remains
# below half a cent and a value with at most two decimal places can be recovered
# by the Decimal quantization below. At and above this binade, distinct cent
# amounts can collapse to the same JSON float and must arrive as strings.
JSON_FLOAT_EXACT_CENTS_LIMIT = 2**46
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
OPERATION_TYPES = {
    ("GET", "/"): "root_redirect",
    ("GET", "/submit"): "submitter_page_read",
    ("GET", "/reviews"): "reviewer_page_read",
    ("GET", "/api/session"): "reviewer_session_read",
    ("POST", "/api/attachments"): "attachment_upload",
    ("POST", "/api/requests"): "reimbursement_submit",
    ("GET", "/api/requests/{request_id}"): "reimbursement_result_read",
    ("GET", "/api/reviews"): "review_queue_search",
    ("GET", "/api/reviews/{request_id}"): "review_case_read",
    (
        "GET",
        "/api/reviews/{request_id}/attachments/{attachment_id}",
    ): "review_attachment_read",
    ("GET", "/api/reviews/{request_id}/events"): "review_timeline_read",
    ("POST", "/api/reviews/{request_id}/decisions"): "review_decision_submit",
}


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


class IntakeRequest(BaseModel):
    """Strict business input; the authoritative audit actor is not accepted here."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=128)
    submitted_by: str = Field(min_length=3, max_length=320)
    submitted_at: datetime
    raw_ocr_text: str = Field(min_length=1, max_length=250_000)
    claimed_category: str = Field(min_length=1, max_length=200)
    claimed_amount_brl: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    attachments: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("request_id")
    @classmethod
    def normalize_request_id(cls, value: str) -> str:
        normalized = value.strip()
        if REQUEST_ID_PATTERN.fullmatch(normalized) is None:
            raise ValueError("request_id contains unsupported characters")
        return normalized

    @field_validator("submitted_by")
    @classmethod
    def normalize_submitter(cls, value: str) -> str:
        normalized = value.strip()
        if SUBMITTER_PATTERN.fullmatch(normalized) is None:
            raise ValueError("submitted_by must be a bounded email address")
        return normalized

    @field_validator("submitted_at", mode="before")
    @classmethod
    def require_timestamp_string(cls, value: object) -> object:
        if not isinstance(value, str) or len(value) > 64:
            raise ValueError("submitted_at must be an ISO 8601 string")
        return value

    @field_validator("submitted_at")
    @classmethod
    def require_timestamp_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("submitted_at must include timezone information")
        return value

    @field_validator("raw_ocr_text", "claimed_category")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("claimed_amount_brl", mode="before")
    @classmethod
    def parse_exact_brl_amount(cls, value: object) -> object:
        if isinstance(value, bool):
            # Pydantic converts ValueError (but intentionally not TypeError) into HTTP 422.
            raise ValueError("claimed_amount_brl must not be a boolean")  # noqa: TRY004
        if isinstance(value, float) and abs(value) >= JSON_FLOAT_EXACT_CENTS_LIMIT:
            raise ValueError(
                "claimed_amount_brl exceeds the safe JSON-number precision limit; "
                "use a decimal string"
            )
        if not isinstance(value, (str, int, float, Decimal)):
            return value
        text = str(value)
        if DECIMAL_AMOUNT_PATTERN.fullmatch(text) is None:
            raise ValueError(
                "claimed_amount_brl must use plain decimal notation with at most two decimals"
            )
        try:
            amount = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError("claimed_amount_brl must be a valid decimal") from exc
        return amount.quantize(Decimal("0.01"))

    @field_validator("attachments")
    @classmethod
    def normalize_attachments(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for attachment in value:
            item = attachment.strip()
            if not item or len(item) > 2_048:
                raise ValueError("attachment references must contain 1 to 2048 characters")
            normalized.append(item)
        if len(set(normalized)) != len(normalized):
            raise ValueError("attachment references must be unique")
        return normalized

    def to_submission(self) -> ReimbursementSubmission:
        return ReimbursementSubmission(
            request_id=self.request_id,
            submitted_by=self.submitted_by,
            submitted_at=self.submitted_at,
            raw_ocr_text=self.raw_ocr_text,
            claimed_category=self.claimed_category,
            claimed_amount=Money(amount=self.claimed_amount_brl),
            attachments=tuple(AttachmentReference(item) for item in self.attachments),
        )


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
    processing_service: ProcessingService | None = None,
    operational_audit_recorder: OperationalAuditRecorder | None = None,
    attachment_store: AttachmentStore | None = None,
    attachment_max_bytes: int = 4 * 1024 * 1024,
) -> FastAPI:
    """Create an HTTP adapter around injected application/security ports."""

    app = FastAPI(
        title="Expense Agent",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(allowed_hosts))
    app.mount("/assets", StaticFiles(directory=STATIC_DIRECTORY), name="assets")
    basic = HTTPBasic(auto_error=False)
    audit_recorder = operational_audit_recorder or review_service.operational_audit_recorder
    if audit_recorder is None:
        raise ValueError("create_app requires a durable operational audit recorder")
    if (
        not isinstance(attachment_max_bytes, int)
        or isinstance(attachment_max_bytes, bool)
        or attachment_max_bytes <= 0
    ):
        raise ValueError("attachment_max_bytes must be a positive integer")

    @app.middleware("http")
    async def transport_and_browser_security(request: Request, call_next):
        started_ns = monotonic_ns()
        correlation_id = _correlation_id(request)
        request.state.operational_authentication = (
            OperationalAuthenticationOutcome.NOT_ATTEMPTED
        )
        response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        raised: BaseException | None = None
        try:
            if require_https and request.url.scheme != "https":
                request.state.operational_route_classification = "transport_rejected"
                _mark_operational_error(request, "transport_policy")
                response = JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "HTTPS is required"},
                )
            else:
                response = await call_next(request)
            response_status = response.status_code
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
            response.headers["X-Correlation-ID"] = correlation_id
            if request.url.scheme == "https":
                response.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains"
                )
            return response
        except BaseException as exc:
            raised = exc
            _mark_operational_error(request, "unhandled_exception")
            raise
        finally:
            actor_type, actor_id = _operational_actor(request)
            authentication = _operational_authentication(request, response_status)
            route, operation_type = _operational_route(request)
            metadata = _operational_metadata(request, raised)
            audit_recorder.record_operation(
                OperationalAuditEvent(
                    event_id=uuid4().hex,
                    occurred_at=datetime.now(UTC),
                    correlation_id=correlation_id,
                    operation_type=operation_type,
                    http_method=request.method.upper(),
                    route=route,
                    status_code=response_status,
                    outcome=_operational_outcome(response_status),
                    authentication=authentication,
                    duration_ms=max(0, (monotonic_ns() - started_ns) // 1_000_000),
                    request_id=_operational_request_id(request),
                    actor_type=actor_type,
                    actor_id=actor_id,
                    metadata=metadata,
                )
            )

    def current_principal(
        request: Request,
        credentials: Annotated[HTTPBasicCredentials | None, Depends(basic)],
    ) -> ReviewerPrincipal:
        principal = None
        if credentials is not None:
            principal = authenticator.authenticate(
                credentials.username,
                credentials.password,
            )
        if principal is None:
            request.state.operational_authentication = OperationalAuthenticationOutcome.FAILED
            _mark_operational_error(request, "authentication_failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Valid Expense Agent credentials are required",
                headers={"WWW-Authenticate": 'Basic realm="Expense Agent", charset="UTF-8"'},
            )
        request.state.operational_authentication = OperationalAuthenticationOutcome.SUCCEEDED
        request.state.operational_actor = ("authenticated_principal", principal.reviewer_id)
        return principal

    def require_capabilities(
        request: Request,
        principal: ReviewerPrincipal,
        *capabilities: str,
    ) -> ReviewerPrincipal:
        if any(principal.can(capability) for capability in capabilities):
            _add_operational_metadata(request, access_control="granted")
            return principal
        _mark_operational_error(request, "authorization_denied")
        _add_operational_metadata(request, access_control="denied")
        raise HTTPException(status_code=403, detail="Insufficient permission")

    def current_submitter(
        request: Request,
        principal: Annotated[ReviewerPrincipal, Depends(current_principal)],
    ) -> ReviewerPrincipal:
        return require_capabilities(request, principal, "submit")

    def current_review_reader(
        request: Request,
        principal: Annotated[ReviewerPrincipal, Depends(current_principal)],
    ) -> ReviewerPrincipal:
        return require_capabilities(request, principal, "review", "audit")

    def current_reviewer(
        request: Request,
        principal: Annotated[ReviewerPrincipal, Depends(current_principal)],
    ) -> ReviewerPrincipal:
        return require_capabilities(request, principal, "review")

    def enforce_csrf_and_same_origin(
        request: Request,
        reviewer: ReviewerPrincipal,
        csrf_token: str | None,
    ) -> ReviewerPrincipal:
        if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
            _mark_operational_error(request, "cross_site_rejected")
            raise HTTPException(status_code=403, detail="Cross-site request blocked")
        origin = request.headers.get("origin")
        expected_origin = str(request.base_url).rstrip("/")
        if origin is None or origin.rstrip("/") != expected_origin:
            _mark_operational_error(request, "same_origin_rejected")
            raise HTTPException(status_code=403, detail="Same-origin request required")
        if csrf_token is None or not csrf.verify(csrf_token, reviewer.reviewer_id):
            _mark_operational_error(request, "csrf_rejected")
            raise HTTPException(status_code=403, detail="Invalid or expired CSRF token")
        return reviewer

    def require_csrf_and_same_origin(
        request: Request,
        reviewer: Annotated[ReviewerPrincipal, Depends(current_reviewer)],
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> ReviewerPrincipal:
        content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type != "application/json":
            _mark_operational_error(request, "unsupported_media_type")
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Content-Type must be application/json",
            )
        return enforce_csrf_and_same_origin(request, reviewer, csrf_token)

    def require_submitter_csrf_and_same_origin(
        request: Request,
        submitter: Annotated[ReviewerPrincipal, Depends(current_submitter)],
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> ReviewerPrincipal:
        content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type != "application/json":
            _mark_operational_error(request, "unsupported_media_type")
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Content-Type must be application/json",
            )
        return enforce_csrf_and_same_origin(request, submitter, csrf_token)

    def require_attachment_csrf_and_same_origin(
        request: Request,
        submitter: Annotated[ReviewerPrincipal, Depends(current_submitter)],
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> ReviewerPrincipal:
        content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type not in ALLOWED_ATTACHMENT_MEDIA_TYPES:
            _mark_operational_error(request, "unsupported_media_type")
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Content-Type must be image/jpeg, image/png, or application/pdf",
            )
        return enforce_csrf_and_same_origin(request, submitter, csrf_token)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        _mark_operational_error(request, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )

    @app.exception_handler(ReviewNotFoundError)
    async def review_not_found_handler(request: Request, _exc: ReviewNotFoundError):
        _mark_operational_error(request, "not_found")
        return JSONResponse(status_code=404, content={"detail": "Review case not found"})

    @app.exception_handler(ReviewConflictError)
    async def review_conflict_handler(request: Request, _exc: ReviewConflictError):
        _mark_operational_error(request, "conflict")
        return JSONResponse(
            status_code=409,
            content={"detail": "Review case is no longer pending at that version"},
        )

    @app.exception_handler(ReviewPreconditionError)
    async def review_precondition_handler(request: Request, _exc: ReviewPreconditionError):
        _mark_operational_error(request, "stale_precondition")
        return JSONResponse(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            content={"detail": "The review case version has changed"},
        )

    @app.exception_handler(DomainValidationError)
    async def domain_validation_handler(request: Request, exc: DomainValidationError):
        _mark_operational_error(request, "domain_validation")
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError):
        _mark_operational_error(request, "request_validation")
        # Never reflect raw OCR, credentials, or non-finite values from invalid input.
        errors = [
            {
                "type": error["type"],
                "loc": list(error["loc"]),
                "msg": error["msg"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.exception_handler(RequestNotFoundError)
    async def request_not_found_handler(request: Request, _exc: RequestNotFoundError):
        _mark_operational_error(request, "not_found")
        return JSONResponse(status_code=404, content={"detail": "Request not found"})

    @app.exception_handler(RequestConflictError)
    async def request_conflict_handler(request: Request, _exc: RequestConflictError):
        _mark_operational_error(request, "conflict")
        return JSONResponse(
            status_code=409,
            content={"detail": "Request ID already exists with a different payload"},
        )

    @app.get("/", include_in_schema=False)
    def root(
        request: Request,
        principal: Annotated[ReviewerPrincipal, Depends(current_principal)],
    ) -> RedirectResponse:
        if principal.can("review") or principal.can("audit"):
            _add_operational_metadata(request, access_control="granted")
            return RedirectResponse(url="/reviews", status_code=307)
        require_capabilities(request, principal, "submit")
        return RedirectResponse(url="/submit", status_code=307)

    @app.get("/submit", include_in_schema=False)
    def submitter_page(
        _submitter: Annotated[ReviewerPrincipal, Depends(current_submitter)],
    ) -> FileResponse:
        return FileResponse(STATIC_DIRECTORY / "submit.html", media_type="text/html")

    @app.get("/reviews", include_in_schema=False)
    def reviews_page(
        _reader: Annotated[ReviewerPrincipal, Depends(current_review_reader)],
    ) -> FileResponse:
        return FileResponse(STATIC_DIRECTORY / "reviews.html", media_type="text/html")

    @app.get("/api/session")
    def session(
        request: Request,
        principal: Annotated[ReviewerPrincipal, Depends(current_principal)],
    ) -> dict[str, Any]:
        _add_operational_metadata(request, access_control="granted")
        identity = {
            "reviewer_id": principal.reviewer_id,
            "email": principal.email,
            "display_name": principal.display_name,
            "roles": sorted(role.value for role in principal.roles),
        }
        return {
            "principal": identity,
            "reviewer": identity,
            "csrf_token": csrf.issue(principal.reviewer_id),
        }

    @app.post("/api/attachments", status_code=201)
    async def upload_attachment(
        request: Request,
        _actor: Annotated[
            ReviewerPrincipal,
            Depends(require_attachment_csrf_and_same_origin),
        ],
        original_filename: Annotated[
            str | None,
            Header(alias="X-Attachment-Filename"),
        ] = None,
    ) -> JSONResponse:
        store = _require_attachment_store(attachment_store)
        if original_filename is None:
            _mark_operational_error(request, "missing_filename")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="X-Attachment-Filename is required",
            )
        validated_filename = SafeAttachmentFilename(original_filename).value

        declared_length = request.headers.get("content-length")
        if declared_length is not None:
            try:
                content_length = int(declared_length)
            except ValueError as exc:
                _mark_operational_error(request, "invalid_content_length")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Content-Length must be a non-negative integer",
                ) from exc
            if content_length < 0:
                _mark_operational_error(request, "invalid_content_length")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Content-Length must be a non-negative integer",
                )
            if content_length > attachment_max_bytes:
                _mark_operational_error(request, "attachment_too_large")
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="Attachment exceeds the configured byte limit",
                )

        declared_media_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
        with tempfile.SpooledTemporaryFile(
            max_size=min(1024 * 1024, attachment_max_bytes),
            mode="w+b",
        ) as staged:
            received = 0
            async for chunk in request.stream():
                received += len(chunk)
                if received > attachment_max_bytes:
                    _mark_operational_error(request, "attachment_too_large")
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="Attachment exceeds the configured byte limit",
                    )
                staged.write(chunk)
            staged.seek(0)
            try:
                metadata = await run_in_threadpool(
                    store.store,
                    staged,
                    original_filename=validated_filename,
                    declared_media_type=declared_media_type,
                )
            except AttachmentTooLarge as exc:
                _mark_operational_error(request, "attachment_too_large")
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="Attachment exceeds the configured byte limit",
                ) from exc
            except (UnsupportedAttachmentMediaType, AttachmentMediaTypeMismatch) as exc:
                _mark_operational_error(request, "unsupported_attachment")
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Attachment bytes do not match an allowlisted media type",
                ) from exc
            except InvalidAttachmentContent as exc:
                _mark_operational_error(request, "invalid_attachment")
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Attachment content is invalid",
                ) from exc
            except AttachmentAlreadyExists as exc:
                _mark_operational_error(request, "attachment_conflict")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Attachment identity collision",
                ) from exc
            except AttachmentIntegrityError as exc:
                _mark_operational_error(request, "attachment_storage_failure")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Attachment could not be stored safely",
                ) from exc

        _set_operational_metadata(
            request,
            attachment_id=metadata.attachment_id.value,
            byte_size=metadata.byte_size,
            media_type=metadata.media_type.value,
            sha256=metadata.sha256,
        )
        reference = f"{MANAGED_ATTACHMENT_PREFIX}{metadata.attachment_id.value}"
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "attachment_id": metadata.attachment_id.value,
                "reference": reference,
                "sha256": metadata.sha256,
                "byte_size": metadata.byte_size,
                "media_type": metadata.media_type.value,
                "original_filename": metadata.original_filename.value,
            },
        )

    @app.post("/api/requests")
    def submit_request(
        request: Request,
        command: IntakeRequest,
        actor: Annotated[
            ReviewerPrincipal,
            Depends(require_submitter_csrf_and_same_origin),
        ],
    ) -> JSONResponse:
        service = _require_processing_service(processing_service)
        if not actor.can("admin") and command.submitted_by.casefold() != actor.email.casefold():
            _mark_operational_error(request, "submitter_identity_mismatch")
            _add_operational_metadata(request, access_control="denied")
            raise HTTPException(
                status_code=403,
                detail="submitted_by must match the authenticated principal",
            )
        submission = command.to_submission()
        _verify_managed_attachments(request, submission, attachment_store)
        correlation_id = _correlation_id(request)
        outcome = service.process(
            submission,
            actor=AuditActor(
                actor_type="submitter",
                actor_id=actor.reviewer_id,
            ),
            correlation_id=correlation_id,
        )
        content = _request_result(outcome.result)
        content["created"] = outcome.created
        content["recovered"] = outcome.recovered
        content["replayed"] = outcome.replayed
        return JSONResponse(
            status_code=201 if outcome.created else 200,
            content=content,
            headers={
                "Location": f"/api/requests/{outcome.result.request_id}",
                "X-Correlation-ID": correlation_id,
            },
        )

    @app.get("/api/requests/{request_id}")
    def request_result(
        request: Request,
        request_id: Annotated[
            str,
            ApiPath(min_length=1, max_length=128, pattern=REQUEST_ID_PATTERN.pattern),
        ],
        principal: Annotated[ReviewerPrincipal, Depends(current_principal)],
    ) -> dict[str, Any]:
        service = _require_processing_service(processing_service)
        result = service.get_result(request_id)
        if not (
            principal.can("review")
            or principal.can("audit")
            or result.submission.submitted_by.casefold() == principal.email.casefold()
        ):
            _mark_operational_error(request, "object_authorization_denied")
            _add_operational_metadata(request, access_control="denied")
            # Do not reveal whether another submitter's opaque request ID exists.
            raise HTTPException(status_code=404, detail="Request not found")
        _add_operational_metadata(request, access_control="granted")
        return _request_result(result)

    @app.get("/api/reviews")
    def pending_reviews(
        query: Annotated[ReviewQueueRequest, Query()],
        _reader: Annotated[ReviewerPrincipal, Depends(current_review_reader)],
    ) -> dict[str, Any]:
        return _queue_page(review_service.search_pending(query.to_query()))

    @app.get("/api/reviews/{request_id}")
    def review_details(
        request_id: str,
        _reader: Annotated[ReviewerPrincipal, Depends(current_review_reader)],
    ) -> JSONResponse:
        details = review_service.get(request_id)
        return JSONResponse(
            content=_case_details(details),
            headers={"ETag": _etag(details)},
        )

    @app.get("/api/reviews/{request_id}/attachments/{attachment_id}")
    def review_attachment(
        request: Request,
        request_id: Annotated[
            str,
            ApiPath(min_length=1, max_length=128, pattern=REQUEST_ID_PATTERN.pattern),
        ],
        attachment_id: Annotated[
            str,
            ApiPath(pattern=ATTACHMENT_ID_PATTERN.pattern),
        ],
        _reader: Annotated[ReviewerPrincipal, Depends(current_review_reader)],
    ) -> Response:
        store = _require_attachment_store(attachment_store)
        details = review_service.get(request_id)
        evidence_reference = f"{MANAGED_ATTACHMENT_PREFIX}{attachment_id}"
        _set_operational_metadata(request, attachment_id=attachment_id)
        if not any(
            attachment.location == evidence_reference for attachment in details.attachments
        ):
            _mark_operational_error(request, "attachment_not_in_case")
            raise HTTPException(status_code=404, detail="Attachment not found for review case")
        try:
            stored = store.read(AttachmentId(attachment_id))
        except AttachmentNotFound as exc:
            _mark_operational_error(request, "attachment_not_found")
            raise HTTPException(status_code=404, detail="Attachment not found for review case") from exc
        except AttachmentIntegrityError as exc:
            _mark_operational_error(request, "attachment_integrity_failure")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Attachment integrity verification failed",
            ) from exc

        metadata = stored.metadata
        _set_operational_metadata(
            request,
            attachment_id=metadata.attachment_id.value,
            byte_size=metadata.byte_size,
            media_type=metadata.media_type.value,
            sha256=metadata.sha256,
        )
        return Response(
            content=stored.content,
            media_type=metadata.media_type.value,
            headers={
                "Content-Disposition": _content_disposition(
                    metadata.original_filename.value
                ),
                "ETag": f'"sha256-{metadata.sha256}"',
                "X-Content-SHA256": metadata.sha256,
            },
        )

    @app.get("/api/reviews/{request_id}/events")
    def review_events(
        request_id: str,
        query: Annotated[ReviewEventRequest, Query()],
        _reader: Annotated[ReviewerPrincipal, Depends(current_review_reader)],
    ) -> dict[str, Any]:
        return _event_page(request_id, review_service.list_events(request_id, query.to_query()))

    @app.post("/api/reviews/{request_id}/decisions", status_code=201)
    def decide(
        request: Request,
        request_id: str,
        command: DecisionRequest,
        reviewer: Annotated[ReviewerPrincipal, Depends(require_csrf_and_same_origin)],
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> JSONResponse:
        if idempotency_key is None:
            raise HTTPException(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                detail="Idempotency-Key is required",
            )
        if if_match is None:
            raise HTTPException(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                detail="If-Match is required",
            )
        expected_version = _expected_version_from_etag(request_id, if_match)
        reviewer_identity = ReviewerIdentity(
            reviewer_id=reviewer.reviewer_id,
            email=reviewer.email,
            display_name=reviewer.display_name,
        )
        replay = review_service.find_decision_replay(
            request_id=request_id,
            outcome=command.outcome,
            reason=command.reason,
            reviewer=reviewer_identity,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
        )
        if replay is not None:
            _add_operational_metadata(request, decision_replayed=True)
            return _decision_response(replay, correlation_id=_correlation_id(request))

        details = review_service.get(request_id)
        if details.submission.submitted_by.casefold() == reviewer.email.casefold():
            _mark_operational_error(request, "self_review_denied")
            _add_operational_metadata(request, access_control="denied")
            raise HTTPException(
                status_code=403,
                detail="A submitter cannot decide their own reimbursement",
            )
        correlation_id = _correlation_id(request)
        result = review_service.decide(
            request_id=request_id,
            outcome=command.outcome,
            reason=command.reason,
            reviewer=reviewer_identity,
            expected_version=expected_version,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        _add_operational_metadata(request, decision_replayed=result.replayed)
        return _decision_response(result, correlation_id=correlation_id)

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
        "attachments": [
            _attachment_projection(details.request_id, attachment)
            for attachment in details.attachments
        ],
        "extraction": _extraction(details.extraction),
        "problems": [
            {
                "code": problem.code,
                "message": problem.message,
                "evidence": dict(problem.evidence),
            }
            for problem in details.problems
        ],
        "automated_decision": _automated_decision(automated),
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


def _attachment_projection(
    request_id: str,
    attachment: AttachmentReference,
) -> dict[str, str]:
    location = attachment.location
    if location.startswith(MANAGED_ATTACHMENT_PREFIX):
        attachment_id = location.removeprefix(MANAGED_ATTACHMENT_PREFIX)
        if ATTACHMENT_ID_PATTERN.fullmatch(attachment_id) is not None:
            return {
                "location": location,
                "kind": "managed_evidence",
                "attachment_id": attachment_id,
                "open_url": (
                    f"/api/reviews/{quote(request_id, safe='')}/attachments/{attachment_id}"
                ),
            }
    return {"location": location, "kind": "legacy_reference"}


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


def _request_result(result: RequestResult) -> dict[str, Any]:
    """Return business-safe request state without storage or technical trace internals."""

    review: dict[str, Any] | None = None
    if result.review_status is not None and result.pending_since is not None:
        review = {
            "status": result.review_status.value,
            "pending_since": _timestamp(result.pending_since),
            "human_decision": None,
        }
        if result.human_decision is not None:
            review["human_decision"] = {
                "decision_id": result.human_decision.decision_id,
                "outcome": result.human_decision.outcome.value,
                "reason": result.human_decision.reason,
                "decided_at": _timestamp(result.human_decision.decided_at),
            }

    return {
        "request_id": result.request_id,
        "submitted_by": result.submission.submitted_by,
        "submitted_at": _timestamp(result.submission.submitted_at),
        "opened_at": _timestamp(result.opened_at),
        "claimed_category": result.submission.claimed_category,
        "claimed_amount": _money(result.submission.claimed_amount),
        "status": result.status.value,
        "version": result.version,
        "extraction": _extraction_snapshot(result.extraction),
        "problems": [
            {
                "code": problem.code,
                "message": problem.message,
                "evidence": dict(problem.evidence),
            }
            for problem in result.problems
        ],
        "automated_decision": (
            _automated_decision(result.automated_decision)
            if result.automated_decision is not None
            else None
        ),
        "review": review,
    }


def _extraction_snapshot(extraction: ExtractionSnapshot | None) -> dict[str, Any] | None:
    if extraction is None:
        return None
    return {
        "status": extraction.status.value,
        "error": extraction.error,
        "facts": _receipt_facts(extraction.facts),
    }


def _automated_decision(decision: AutomatedDecision) -> dict[str, Any]:
    return {
        "decision_id": decision.decision_id,
        "route": decision.route.value,
        "decided_at": _timestamp(decision.decided_at),
        "policy_version": decision.policy_version,
        "reasons": [
            {
                "code": reason.code,
                "message": reason.message,
                "evidence": dict(reason.evidence),
            }
            for reason in decision.reasons
        ],
        "rule_evaluations": [
            {
                "rule_id": evaluation.rule_id,
                "rule_version": evaluation.rule_version,
                "outcome": evaluation.outcome.value,
                "message": evaluation.message,
                "facts": dict(evaluation.facts),
            }
            for evaluation in decision.rule_evaluations
        ],
    }


def _require_processing_service(
    processing_service: ProcessingService | None,
) -> ProcessingService:
    if processing_service is None:
        raise HTTPException(status_code=503, detail="Request processing is not configured")
    return processing_service


def _correlation_id(request: Request) -> str:
    existing = getattr(request.state, "operational_correlation_id", None)
    if isinstance(existing, str):
        return existing
    supplied = request.headers.get("X-Correlation-ID", "")
    if CORRELATION_ID_PATTERN.fullmatch(supplied):
        correlation_id = supplied
        request.state.operational_correlation_source = "client"
    else:
        correlation_id = uuid4().hex
        request.state.operational_correlation_source = "generated"
    request.state.operational_correlation_id = correlation_id
    return correlation_id


def _mark_operational_error(request: Request, error_kind: str) -> None:
    if not hasattr(request.state, "operational_error_kind"):
        request.state.operational_error_kind = error_kind


def _operational_actor(request: Request) -> tuple[str | None, str | None]:
    actor = getattr(request.state, "operational_actor", None)
    if (
        isinstance(actor, tuple)
        and len(actor) == 2
        and all(isinstance(value, str) and value.strip() for value in actor)
    ):
        return actor
    return None, None


def _operational_authentication(
    request: Request,
    response_status: int,
) -> OperationalAuthenticationOutcome:
    if response_status == status.HTTP_401_UNAUTHORIZED:
        return OperationalAuthenticationOutcome.FAILED
    observed = getattr(request.state, "operational_authentication", None)
    if isinstance(observed, OperationalAuthenticationOutcome):
        return observed
    return OperationalAuthenticationOutcome.NOT_ATTEMPTED


def _operational_route(request: Request) -> tuple[str, str]:
    classification = getattr(request.state, "operational_route_classification", None)
    if classification == "transport_rejected":
        return "transport_rejected", "transport_rejected"

    route_object = request.scope.get("route")
    route = getattr(route_object, "path", None)
    if (
        not isinstance(route, str)
        or not route.strip()
        or len(route) > 256
        or any(character in route for character in ("?", "#", "\r", "\n"))
    ):
        return "unmatched", "unmatched_route"
    if route == "/assets" or route.startswith("/assets/"):
        return route, "static_asset_read"
    return route, OPERATION_TYPES.get((request.method.upper(), route), "http_request")


def _operational_request_id(request: Request) -> str | None:
    request_id = request.path_params.get("request_id")
    if (
        isinstance(request_id, str)
        and len(request_id) <= 128
        and REQUEST_ID_PATTERN.fullmatch(request_id) is not None
    ):
        return request_id
    return None


def _operational_outcome(response_status: int) -> OperationalAuditOutcome:
    if response_status >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        return OperationalAuditOutcome.SERVER_ERROR
    if response_status >= status.HTTP_400_BAD_REQUEST:
        return OperationalAuditOutcome.CLIENT_ERROR
    return OperationalAuditOutcome.SUCCEEDED


def _operational_metadata(
    request: Request,
    raised: BaseException | None,
) -> dict[str, str | int | bool]:
    metadata = {
        "correlation_source": getattr(
            request.state,
            "operational_correlation_source",
            "generated",
        )
    }
    error_kind = getattr(request.state, "operational_error_kind", None)
    if isinstance(error_kind, str):
        metadata["error_kind"] = error_kind[:256]
    if raised is not None:
        exception_type = re.sub(r"[^A-Za-z0-9_.-]", "_", type(raised).__name__)
        metadata["exception_type"] = (exception_type or "Exception")[:256]
    additional = getattr(request.state, "operational_metadata", None)
    if isinstance(additional, dict):
        for key, value in additional.items():
            if isinstance(key, str) and isinstance(value, (str, int, bool)):
                metadata[key] = value
    return metadata


def _set_operational_metadata(
    request: Request,
    **metadata: str | int | bool,
) -> None:
    _add_operational_metadata(request, **metadata)


def _add_operational_metadata(
    request: Request,
    **metadata: str | int | bool,
) -> None:
    existing = getattr(request.state, "operational_metadata", None)
    merged = dict(existing) if isinstance(existing, dict) else {}
    merged.update(metadata)
    request.state.operational_metadata = merged


def _verify_managed_attachments(
    request: Request,
    submission: ReimbursementSubmission,
    store: AttachmentStore | None,
) -> None:
    references = tuple(attachment.location for attachment in submission.attachments)
    if not references:
        return

    if any(not reference.startswith(MANAGED_ATTACHMENT_PREFIX) for reference in references):
        _mark_operational_error(request, "unmanaged_attachment_reference")
        _add_operational_metadata(request, attachment_reference_policy="managed_only")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Attachment references must use managed evidence IDs",
        )

    managed_store = _require_attachment_store(store)
    for reference in references:
        attachment_id = reference.removeprefix(MANAGED_ATTACHMENT_PREFIX)
        if ATTACHMENT_ID_PATTERN.fullmatch(attachment_id) is None:
            _mark_operational_error(request, "invalid_managed_attachment_reference")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Managed attachment reference is invalid",
            )
        try:
            managed_store.read(AttachmentId(attachment_id))
        except AttachmentNotFound as exc:
            _mark_operational_error(request, "managed_attachment_not_found")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Managed attachment reference does not exist",
            ) from exc
        except AttachmentIntegrityError as exc:
            _mark_operational_error(request, "attachment_integrity_failure")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Attachment integrity verification failed",
            ) from exc
    _add_operational_metadata(
        request,
        managed_attachment_count=len(references),
    )


def _require_attachment_store(store: AttachmentStore | None) -> AttachmentStore:
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Attachment evidence storage is unavailable",
        )
    return store


def _content_disposition(filename: str) -> str:
    ascii_filename = (
        unicodedata.normalize("NFKD", filename)
        .encode("ascii", errors="ignore")
        .decode("ascii")
    )
    ascii_filename = re.sub(r"[^A-Za-z0-9 ._()-]", "_", ascii_filename).strip()
    if not ascii_filename:
        ascii_filename = "attachment"
    encoded_filename = quote(filename, safe="")
    return (
        f'inline; filename="{ascii_filename}"; '
        f"filename*=UTF-8''{encoded_filename}"
    )


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


def _expected_version_from_etag(request_id: str, raw_etag: str) -> int:
    if len(raw_etag) > 128:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="The review precondition is invalid",
        )
    match = REVIEW_ETAG_PATTERN.fullmatch(raw_etag)
    expected_request_hash = hashlib.sha256(request_id.encode("utf-8")).hexdigest()[:16]
    if match is None or not hmac.compare_digest(match.group(1), expected_request_hash):
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="The review precondition is invalid",
        )
    return int(match.group(2))


def _decision_response(
    result: ReviewDecisionResult,
    *,
    correlation_id: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=200 if result.replayed else 201,
        content={
            "decision_id": result.decision.decision_id,
            "request_id": result.decision.request_id,
            "outcome": result.decision.outcome.value,
            "status": result.resulting_status.value,
            "version": result.version,
            "audit_event_id": result.audit_event_id,
            "decided_at": _timestamp(result.decision.decided_at),
            "replayed": result.replayed,
        },
        headers={
            "ETag": _etag_for(result.decision.request_id, result.version),
            "X-Correlation-ID": correlation_id,
        },
    )
