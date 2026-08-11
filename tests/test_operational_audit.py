import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from expense_agent.application import (
    OperationalAuditEvent,
    OperationalAuditOutcome,
    OperationalAuthenticationOutcome,
    ReviewService,
)
from expense_agent.domain.exceptions import DomainValidationError
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


def _credential() -> ReviewerCredential:
    return ReviewerCredential(
        username="reviewer",
        reviewer_id="directory:42",
        email="reviewer@example.com",
        display_name="Review Manager",
        password_hash=hash_password("secret-pass", iterations=100_000),
    )


def _client(
    tmp_path: Path,
    *,
    processing_service: object | None = None,
    raise_server_exceptions: bool = True,
) -> tuple[TestClient, Path]:
    database_path = tmp_path / "operational-audit.sqlite3"
    repository = SqliteReviewRepository(database_path)
    app = create_app(
        review_service=ReviewService(repository),
        processing_service=processing_service,  # type: ignore[arg-type]
        authenticator=BasicAuthenticator((_credential(),)),
        csrf=CsrfProtector("test-csrf-secret-that-is-long-enough"),
        require_https=True,
        allowed_hosts=("testserver",),
    )
    return (
        TestClient(
            app,
            base_url=ORIGIN,
            raise_server_exceptions=raise_server_exceptions,
        ),
        database_path,
    )


def _rows(database_path: Path) -> list[sqlite3.Row]:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            "SELECT * FROM operational_audit_events ORDER BY rowid"
        ).fetchall()


def test_repository_migrates_append_only_operational_audit_table(tmp_path) -> None:
    database_path = tmp_path / "migration.sqlite3"
    repository = SqliteReviewRepository(database_path)
    event = OperationalAuditEvent(
        event_id="OP-1",
        occurred_at=datetime(2026, 8, 11, 12, tzinfo=UTC),
        correlation_id="corr-1",
        operation_type="review_queue_search",
        http_method="GET",
        route="/api/reviews",
        status_code=200,
        outcome=OperationalAuditOutcome.SUCCEEDED,
        authentication=OperationalAuthenticationOutcome.SUCCEEDED,
        duration_ms=7,
        actor_type="reviewer",
        actor_id="directory:42",
        metadata={"correlation_source": "client"},
    )

    repository.record_operation(event)
    SqliteReviewRepository(database_path)

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT event_id, request_id, actor_id, route, status_code, outcome,
                   authentication, metadata_json
            FROM operational_audit_events
            """
        ).fetchone()
        assert row == (
            "OP-1",
            None,
            "directory:42",
            "/api/reviews",
            200,
            "succeeded",
            "succeeded",
            '{"correlation_source":"client"}',
        )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE operational_audit_events SET status_code = 201 WHERE event_id = 'OP-1'"
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM operational_audit_events WHERE event_id = 'OP-1'")

    with pytest.raises(DomainValidationError, match="sensitive metadata"):
        OperationalAuditEvent(
            event_id="OP-SECRET",
            occurred_at=datetime.now(UTC),
            correlation_id="corr-2",
            operation_type="http_request",
            http_method="GET",
            route="unmatched",
            status_code=400,
            outcome=OperationalAuditOutcome.CLIENT_ERROR,
            authentication=OperationalAuthenticationOutcome.NOT_ATTEMPTED,
            duration_ms=0,
            metadata={"authorization_value": "must-not-be-stored"},
        )


def test_every_http_attempt_records_one_sanitized_operation(tmp_path) -> None:
    client, database_path = _client(tmp_path)
    query_secret = "private-search-value"
    path_secret = "private-unmatched-path"

    responses = [
        client.get("/api/reviews"),
        client.get(
            "/api/session",
            headers={**AUTHENTICATED_HEADERS, "X-Correlation-ID": "client-correlation"},
        ),
        client.get(
            "/api/reviews",
            params={"search": query_secret},
            headers=AUTHENTICATED_HEADERS,
        ),
        client.get(
            "/api/reviews",
            params={"limit": "999", "search": query_secret},
            headers=AUTHENTICATED_HEADERS,
        ),
        client.get("/api/reviews/REQ-MISSING", headers=AUTHENTICATED_HEADERS),
        client.get(f"/{path_secret}", params={"access_token": "query-token-secret"}),
    ]
    http_client = TestClient(client.app, base_url="http://testserver")
    responses.append(http_client.get("/reviews", headers=AUTHENTICATED_HEADERS))

    assert [response.status_code for response in responses] == [401, 200, 200, 422, 404, 404, 400]
    assert responses[1].headers["x-correlation-id"] == "client-correlation"

    rows = _rows(database_path)
    assert len(rows) == len(responses)
    assert len({row["event_id"] for row in rows}) == len(rows)

    assert (
        rows[0]["operation_type"],
        rows[0]["route"],
        rows[0]["authentication"],
        rows[0]["actor_id"],
    ) == ("review_queue_search", "/api/reviews", "failed", None)
    assert (
        rows[1]["correlation_id"],
        rows[1]["authentication"],
        rows[1]["actor_id"],
    ) == ("client-correlation", "succeeded", "directory:42")
    assert rows[2]["operation_type"] == "review_queue_search"
    assert rows[3]["status_code"] == 422
    assert json.loads(rows[3]["metadata_json"])["error_kind"] == "request_validation"
    assert rows[4]["request_id"] == "REQ-MISSING"
    assert rows[4]["actor_id"] == "directory:42"
    assert rows[5]["route"] == "unmatched"
    assert rows[5]["operation_type"] == "unmatched_route"
    assert rows[6]["route"] == "transport_rejected"
    assert rows[6]["authentication"] == "not_attempted"

    serialized_rows = json.dumps([dict(row) for row in rows], sort_keys=True)
    for forbidden in (
        AUTHORIZATION,
        "secret-pass",
        query_secret,
        path_secret,
        "query-token-secret",
    ):
        assert forbidden not in serialized_rows


class ExplodingProcessingService:
    def process(self, *_args, **_kwargs):
        raise RuntimeError("TOP-SECRET-OCR must never reach operational audit")


def test_unhandled_orchestration_failure_is_recorded_once_without_error_message(
    tmp_path,
) -> None:
    client, database_path = _client(
        tmp_path,
        processing_service=ExplodingProcessingService(),
        raise_server_exceptions=False,
    )
    session = client.get("/api/session", headers=AUTHENTICATED_HEADERS)
    token = session.json()["csrf_token"]
    payload = {
        "request_id": "REQ-FAIL-1",
        "submitted_by": "employee@example.com",
        "submitted_at": "2026-08-11T12:00:00Z",
        "raw_ocr_text": "TOP-SECRET-OCR",
        "claimed_category": "meals",
        "claimed_amount_brl": "10.00",
        "attachments": ["private-original.jpg"],
    }

    response = client.post(
        "/api/requests",
        headers={
            **AUTHENTICATED_HEADERS,
            "Origin": ORIGIN,
            "X-CSRF-Token": token,
            "X-Correlation-ID": "failure-correlation",
        },
        json=payload,
    )

    assert response.status_code == 500
    rows = _rows(database_path)
    assert len(rows) == 2  # Session plus the failed submission attempt.
    failure = rows[-1]
    assert failure["operation_type"] == "reimbursement_submit"
    assert failure["route"] == "/api/requests"
    assert failure["status_code"] == 500
    assert failure["outcome"] == "server_error"
    assert failure["authentication"] == "succeeded"
    assert failure["actor_id"] == "directory:42"
    assert failure["request_id"] is None
    assert failure["correlation_id"] == "failure-correlation"
    metadata = json.loads(failure["metadata_json"])
    assert metadata["error_kind"] == "unhandled_exception"
    assert metadata["exception_type"] == "RuntimeError"
    serialized = json.dumps(dict(failure), sort_keys=True)
    assert "TOP-SECRET-OCR" not in serialized
    assert "private-original.jpg" not in serialized
