import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from expense_agent.application.review import ReviewCaseStatus, ReviewProblem, ReviewService
from expense_agent.application.workflow import (
    ExtractionSnapshot,
    InvocationStatus,
    InvocationSummary,
    ProcessingOutcome,
    ProcessingService,
    RequestConflictError,
    RequestNotFoundError,
    RequestResult,
    submission_fingerprint,
)
from expense_agent.domain import (
    AuditActor,
    BaselinePolicy,
    PolicyDecisionRoute,
    ReimbursementStatus,
    ReimbursementSubmission,
)
from expense_agent.infrastructure.extraction import DeterministicReceiptExtractor
from expense_agent.infrastructure.review import SqliteReviewRepository
from expense_agent.presentation.app import create_app
from expense_agent.presentation.security import (
    BasicAuthenticator,
    CsrfProtector,
    ReviewerCredential,
    hash_password,
)

AUTHORIZATION = "Basic cmV2aWV3ZXI6c2VjcmV0LXBhc3M="
AUTHENTICATED_HEADERS = {"Authorization": AUTHORIZATION}
ORIGIN = "https://testserver"
SECRET_PARAMETER = "provider-secret-must-not-leave-the-technical-boundary"


class InMemoryProcessingService:
    def __init__(self) -> None:
        self.results: dict[str, tuple[str, RequestResult]] = {}
        self.actors: list[AuditActor] = []
        self.submissions: list[ReimbursementSubmission] = []

    def process(
        self,
        submission: ReimbursementSubmission,
        *,
        actor: AuditActor,
        correlation_id: str,
    ) -> ProcessingOutcome:
        fingerprint = submission_fingerprint(submission)
        existing = self.results.get(submission.request_id)
        if existing is not None:
            if existing[0] != fingerprint:
                raise RequestConflictError("request ID payload differs")
            return ProcessingOutcome(created=False, result=existing[1])

        self.actors.append(actor)
        self.submissions.append(submission)
        extraction = DeterministicReceiptExtractor().extract(submission)
        decision = BaselinePolicy().evaluate(
            submission,
            extraction,
            decision_id=f"DEC-{submission.request_id}",
            decided_at=submission.submitted_at,
        )
        status = {
            PolicyDecisionRoute.AUTO_APPROVED: ReimbursementStatus.AUTO_APPROVED,
            PolicyDecisionRoute.HUMAN_REVIEW: ReimbursementStatus.PENDING_REVIEW,
            PolicyDecisionRoute.REJECTED: ReimbursementStatus.REJECTED,
        }[decision.route]
        trace = extraction.trace
        invocation = InvocationSummary(
            invocation_id=f"INV-{submission.request_id}",
            processing_run_id=f"RUN-{submission.request_id}",
            stage="primary_extractor",
            attempt=1,
            status=InvocationStatus.SUCCEEDED,
            provider=trace.provider,
            model=trace.model,
            prompt_version=trace.prompt_version,
            prompt_hash=trace.prompt_hash,
            input_hash=trace.input_hash,
            output_hash=hashlib.sha256(trace.raw_response.encode()).hexdigest(),
            invoked_at=trace.invoked_at,
            completed_at=trace.invoked_at,
            duration_ms=trace.duration_ms,
            parameters={"secret": SECRET_PARAMETER},
        )
        problems = (
            tuple(
                ReviewProblem(
                    code=reason.code,
                    message=reason.message,
                    evidence=reason.evidence,
                )
                for reason in decision.reasons
            )
            if decision.route is PolicyDecisionRoute.HUMAN_REVIEW
            else ()
        )
        result = RequestResult(
            submission=submission,
            opened_at=submission.submitted_at,
            status=status,
            version=3,
            extraction=ExtractionSnapshot(
                status=extraction.status,
                facts=extraction.facts,
                error=extraction.error,
                invocation=invocation,
            ),
            automated_decision=decision,
            problems=problems,
            review_status=(
                ReviewCaseStatus.PENDING
                if status is ReimbursementStatus.PENDING_REVIEW
                else None
            ),
            pending_since=(
                submission.submitted_at
                if status is ReimbursementStatus.PENDING_REVIEW
                else None
            ),
        )
        self.results[submission.request_id] = (fingerprint, result)
        return ProcessingOutcome(created=True, result=result)

    def get_result(self, request_id: str) -> RequestResult:
        existing = self.results.get(request_id)
        if existing is None:
            raise RequestNotFoundError(request_id)
        return existing[1]


def _client() -> tuple[TestClient, InMemoryProcessingService]:
    processing_service = InMemoryProcessingService()
    app = create_app(
        review_service=ReviewService(object()),  # Review routes are outside this focused test.
        processing_service=processing_service,  # type: ignore[arg-type]
        authenticator=BasicAuthenticator((_credential(),)),
        csrf=CsrfProtector("test-csrf-secret-that-is-long-enough"),
        require_https=True,
        allowed_hosts=("testserver",),
    )
    return TestClient(app, base_url=ORIGIN), processing_service


def _credential() -> ReviewerCredential:
    return ReviewerCredential(
        username="reviewer",
        reviewer_id="directory:42",
        email="authenticated.employee@example.com",
        display_name="Authenticated Employee",
        password_hash=hash_password("secret-pass", iterations=100_000),
    )


def _real_client(tmp_path: Path) -> tuple[TestClient, Path]:
    database_path = tmp_path / "intake.sqlite3"
    repository = SqliteReviewRepository(database_path)
    app = create_app(
        review_service=ReviewService(repository),
        processing_service=ProcessingService(repository, DeterministicReceiptExtractor()),
        authenticator=BasicAuthenticator((_credential(),)),
        csrf=CsrfProtector("test-csrf-secret-that-is-long-enough"),
        require_https=True,
        allowed_hosts=("testserver",),
    )
    return TestClient(app, base_url=ORIGIN), database_path


def _write_headers(client: TestClient) -> dict[str, str]:
    session = client.get("/api/session", headers=AUTHENTICATED_HEADERS)
    assert session.status_code == 200
    return {
        **AUTHENTICATED_HEADERS,
        "Origin": ORIGIN,
        "X-CSRF-Token": session.json()["csrf_token"],
        "X-Correlation-ID": "intake-http-test",
    }


def _payload(
    *,
    request_id: str = "REQ-HTTP-0001",
    amount: object = "93.50",
    submitted_at: object = "2026-04-10T09:15:00Z",
) -> dict[str, object]:
    return {
        "request_id": request_id,
        "submitted_by": "ana.silva@company.com",
        "submitted_at": submitted_at,
        "raw_ocr_text": (
            "BOM SABOR RESTAURANT LTD\n"
            "TAX ID 12.345.678/0001-90\n"
            "DATE 09/04/2026\n"
            "BUSINESS LUNCH\n"
            f"TOTAL R$ {amount}"
        ),
        "claimed_category": "meals",
        "claimed_amount_brl": amount,
        "attachments": ["receipt_0001.jpg"],
    }


def test_intake_requires_authentication_csrf_same_origin_and_json() -> None:
    client, _service = _client()
    payload = _payload()
    write_headers = _write_headers(client)

    unauthenticated = client.post(
        "/api/requests",
        headers={"Origin": ORIGIN},
        json=payload,
    )
    missing_csrf = client.post(
        "/api/requests",
        headers={**AUTHENTICATED_HEADERS, "Origin": ORIGIN},
        json=payload,
    )
    cross_origin = client.post(
        "/api/requests",
        headers={**write_headers, "Origin": "https://attacker.example"},
        json=payload,
    )
    non_json = client.post(
        "/api/requests",
        headers={**write_headers, "Content-Type": "text/plain"},
        content="not-json",
    )

    assert unauthenticated.status_code == 401
    assert missing_csrf.status_code == 403
    assert cross_origin.status_code == 403
    assert non_json.status_code == 415


def test_intake_preserves_submitter_derives_audit_actor_and_returns_safe_result() -> None:
    client, service = _client()
    write_headers = _write_headers(client)

    created = client.post(
        "/api/requests",
        headers=write_headers,
        json=_payload(),
    )
    fetched = client.get("/api/requests/REQ-HTTP-0001", headers=AUTHENTICATED_HEADERS)

    assert created.status_code == 201
    assert created.headers["location"] == "/api/requests/REQ-HTTP-0001"
    assert created.headers["x-correlation-id"] == "intake-http-test"
    assert created.json()["created"] is True
    assert created.json()["replayed"] is False
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "auto_approved"
    assert fetched.json()["claimed_amount"] == {"amount": "93.50", "currency": "BRL"}
    assert fetched.json()["automated_decision"]["route"] == "auto_approved"

    assert service.submissions[0].submitted_by == "ana.silva@company.com"
    assert service.actors == [AuditActor(actor_type="submitter", actor_id="directory:42")]
    serialized = created.text + fetched.text
    assert "raw_ocr_text" not in serialized
    assert "receipt_0001.jpg" not in serialized
    assert "raw_response" not in serialized
    assert "processing_run" not in serialized
    assert "invocation" not in serialized
    assert SECRET_PARAMETER not in serialized

    pending = client.post(
        "/api/requests",
        headers=write_headers,
        json={
            **_payload(request_id="REQ-HTTP-PENDING", amount="640.00"),
            "raw_ocr_text": (
                "GRAND PLAZA HOTEL\n"
                "TAX ID 45.678.901/0001-56\n"
                "CHECK-IN: 10/04/2026\n"
                "CHECK-OUT: 12/04/2026\n"
                "NIGHTS: 2\n"
                "TOTAL R$ 640.00"
            ),
            "claimed_category": "lodging",
        },
    )
    pending_lookup = client.get(
        "/api/requests/REQ-HTTP-PENDING",
        headers=AUTHENTICATED_HEADERS,
    )
    assert pending.status_code == 201
    assert pending_lookup.status_code == 200
    assert pending_lookup.json()["status"] == "pending_review"
    assert pending_lookup.json()["review"]["status"] == "pending"


def test_exact_replay_is_200_but_same_id_with_different_payload_is_409() -> None:
    client, service = _client()
    headers = _write_headers(client)
    numeric = _payload(request_id="REQ-IDEMPOTENT", amount=0.1)
    canonical_string = {**numeric, "claimed_amount_brl": "0.10"}

    created = client.post("/api/requests", headers=headers, json=numeric)
    replayed = client.post("/api/requests", headers=headers, json=canonical_string)
    divergent = client.post(
        "/api/requests",
        headers=headers,
        json={**canonical_string, "claimed_category": "lodging"},
    )

    assert created.status_code == 201
    assert created.json()["claimed_amount"] == {"amount": "0.10", "currency": "BRL"}
    assert replayed.status_code == 200
    assert replayed.json()["created"] is False
    assert replayed.json()["replayed"] is True
    assert divergent.status_code == 409
    assert len(service.submissions) == 1


@pytest.mark.parametrize(
    "amount",
    ["1e2", "NaN", "1.001", 1.001, True, "0.00", "-1.00"],
)
def test_intake_rejects_non_plain_or_invalid_money(amount: object) -> None:
    client, _service = _client()

    response = client.post(
        "/api/requests",
        headers=_write_headers(client),
        json=_payload(amount=amount),
    )

    assert response.status_code == 422


def test_intake_rejects_nonstandard_json_nan_if_the_parser_accepts_it() -> None:
    client, _service = _client()
    payload = _payload()
    payload["claimed_amount_brl"] = float("nan")

    response = client.post(
        "/api/requests",
        headers={**_write_headers(client), "Content-Type": "application/json"},
        content=json.dumps(payload),
    )

    assert response.status_code == 422
    assert "input" not in response.text
    assert "NaN" not in response.text


@pytest.mark.parametrize(
    "mutation",
    [
        {"submitted_at": "2026-04-10T09:15:00"},
        {"submitted_at": 1_776_000_000},
        {"submitted_by": "not-an-email"},
        {"unexpected": "field"},
        {"attachments": ["same.jpg", "same.jpg"]},
    ],
)
def test_intake_rejects_naive_timestamp_invalid_submitter_and_unknown_fields(
    mutation: dict[str, object],
) -> None:
    client, _service = _client()

    response = client.post(
        "/api/requests",
        headers=_write_headers(client),
        json={**_payload(), **mutation},
    )

    assert response.status_code == 422


def test_request_lookup_requires_authentication_and_returns_404() -> None:
    client, _service = _client()

    unauthenticated = client.get("/api/requests/UNKNOWN")
    missing = client.get("/api/requests/UNKNOWN", headers=AUTHENTICATED_HEADERS)
    invalid = client.get("/api/requests/INVALID!", headers=AUTHENTICATED_HEADERS)
    oversized = client.get(
        f"/api/requests/{'R' * 129}",
        headers=AUTHENTICATED_HEADERS,
    )

    assert unauthenticated.status_code == 401
    assert missing.status_code == 404
    assert invalid.status_code == 422
    assert oversized.status_code == 422


def test_request_routes_fail_closed_when_processing_is_not_composed() -> None:
    app = create_app(
        review_service=ReviewService(object()),
        authenticator=BasicAuthenticator((_credential(),)),
        csrf=CsrfProtector("test-csrf-secret-that-is-long-enough"),
        require_https=True,
        allowed_hosts=("testserver",),
    )
    client = TestClient(app, base_url=ORIGIN)

    response = client.get("/api/requests/UNKNOWN", headers=AUTHENTICATED_HEADERS)

    assert response.status_code == 503


def test_real_sqlite_http_pipeline_is_idempotent_audited_and_queryable(tmp_path: Path) -> None:
    client, database_path = _real_client(tmp_path)
    headers = _write_headers(client)
    payload = _payload(request_id="REQ-REAL-PIPELINE")

    created = client.post("/api/requests", headers=headers, json=payload)
    replayed = client.post("/api/requests", headers=headers, json=payload)
    conflict = client.post(
        "/api/requests",
        headers=headers,
        json={**payload, "claimed_category": "lodging"},
    )
    fetched = client.get(
        "/api/requests/REQ-REAL-PIPELINE",
        headers=AUTHENTICATED_HEADERS,
    )

    assert created.status_code == 201
    assert created.json()["status"] == "auto_approved"
    assert replayed.status_code == 200
    assert replayed.json()["replayed"] is True
    assert conflict.status_code == 409
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "auto_approved"
    assert "raw_response" not in fetched.text

    with sqlite3.connect(database_path) as connection:
        reimbursement = connection.execute(
            "SELECT submitted_by, status, version FROM reimbursements"
        ).fetchone()
        received_actor = connection.execute(
            """
            SELECT actor_type, actor_id FROM audit_events
            WHERE event_type = 'reimbursement_received'
            """
        ).fetchone()
        attempts = connection.execute(
            "SELECT COUNT(*), MIN(length(raw_response)) FROM processing_invocation_attempts"
        ).fetchone()
        replay_events = connection.execute(
            """
            SELECT event_type FROM audit_events
            WHERE event_type IN (
                'reimbursement_intake_replayed',
                'reimbursement_intake_conflict_rejected'
            )
            ORDER BY occurred_at, event_type
            """
        ).fetchall()
    assert reimbursement == ("ana.silva@company.com", "auto_approved", 3)
    assert received_actor == ("submitter", "directory:42")
    assert attempts is not None and attempts[0] == 1 and attempts[1] > 0
    assert {row[0] for row in replay_events} == {
        "reimbursement_intake_replayed",
        "reimbursement_intake_conflict_rejected",
    }
