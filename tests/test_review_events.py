import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from expense_agent.application.review import (
    ReviewBusinessEvent,
    ReviewEventQuery,
    ReviewNotFoundError,
    ReviewQueueQuery,
    ReviewService,
)
from expense_agent.domain.audit import AuditActor
from expense_agent.domain.exceptions import DomainValidationError
from expense_agent.infrastructure.review import SqliteReviewRepository
from expense_agent.presentation.app import create_app
from expense_agent.presentation.demo_seed import _build_case
from expense_agent.presentation.security import (
    BasicAuthenticator,
    CsrfProtector,
    ReviewerCredential,
    hash_password,
)

AUTHORIZATION = {"Authorization": "Basic cmV2aWV3ZXI6c2VjcmV0LXBhc3M="}


def test_business_event_rejects_non_scalar_payload_from_any_adapter() -> None:
    with pytest.raises(DomainValidationError, match="scalar business data"):
        ReviewBusinessEvent(
            event_id="EVENT-UNSAFE",
            request_id="REQ-UNSAFE",
            event_type="review_case_enqueued",
            occurred_at=datetime.now(UTC),
            actor=AuditActor(actor_type="system", actor_id="policy-engine"),
            correlation_id="corr-unsafe",
            payload={"policy_version": {"token": "must-not-cross-boundary"}},
        )


def _seed_case(repository: SqliteReviewRepository, request_id: str) -> None:
    case, extraction, problems = _build_case(
        request_id=request_id,
        submitted_by=f"{request_id.lower()}@example.com",
        amount="93.50",
        extracted_amount="89.50",
        category="meals",
        merchant="Timeline Merchant",
        problem_code="TOTAL_MISMATCH",
        problem_message="Claimed and extracted totals differ.",
        offset_minutes=10,
    )
    repository.add_pending_case(
        case,
        extraction=extraction,
        problems=problems,
        correlation_id=f"ingest:{request_id}",
    )


def _append_timeline_fixtures(repository: SqliteReviewRepository, request_id: str) -> None:
    with sqlite3.connect(repository.database_path) as connection:
        initial_raw = connection.execute(
            "SELECT MAX(occurred_at) FROM audit_events WHERE request_id = ?",
            (request_id,),
        ).fetchone()[0]
        initial = datetime.fromisoformat(initial_raw).astimezone(UTC)
        tied_at = (initial + timedelta(seconds=1)).isoformat(timespec="microseconds")
        later_at = (initial + timedelta(seconds=2)).isoformat(timespec="microseconds")
        last_at = (initial + timedelta(seconds=3)).isoformat(timespec="microseconds")
        connection.executemany(
            """
            INSERT INTO audit_events (
                event_id, request_id, event_type, occurred_at, actor_type,
                actor_id, correlation_id, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    "EVENT-TIED-A",
                    request_id,
                    "review_case_enqueued",
                    tied_at,
                    "system",
                    "policy-engine",
                    "corr-tied-a",
                    json.dumps(
                        {
                            "attachment_count": 7,
                            "policy_version": {
                                "raw_response": "nested-must-not-leak"
                            },
                            "raw_response": "must-not-leak",
                            "access_token": "must-not-leak",
                            "location": "private://must-not-leak",
                        }
                    ),
                ),
                (
                    "EVENT-TIED-B",
                    request_id,
                    "review_case_enqueued",
                    tied_at,
                    "system",
                    "policy-engine",
                    "corr-tied-b",
                    json.dumps({"policy_version": "policy-v1"}),
                ),
                (
                    "EVENT-DECIDED",
                    request_id,
                    "human_review_decided",
                    later_at,
                    "reviewer",
                    "directory:42",
                    "corr-decided",
                    json.dumps(
                        {
                            "decision_id": "DECISION-1",
                            "from_status": "pending_review",
                            "outcome": "approved",
                            "reason": "Receipt verified.",
                            "request_version": 1,
                            "to_status": "approved_after_review",
                            "raw_response": "must-not-leak",
                        }
                    ),
                ),
                (
                    "EVENT-UNKNOWN",
                    request_id,
                    "future_internal_event",
                    last_at,
                    "system",
                    "future-component",
                    "corr-unknown",
                    json.dumps(
                        {
                            "raw_response": "must-not-leak",
                            "token": "must-not-leak",
                        }
                    ),
                ),
            ),
        )


def _web_client(repository: SqliteReviewRepository) -> TestClient:
    credential = ReviewerCredential(
        username="reviewer",
        reviewer_id="directory:42",
        email="reviewer@example.com",
        display_name="Review Manager",
        password_hash=hash_password("secret-pass", iterations=100_000),
    )
    app = create_app(
        review_service=ReviewService(repository),
        authenticator=BasicAuthenticator((credential,)),
        csrf=CsrfProtector("test-csrf-secret-that-is-long-enough"),
        require_https=True,
        allowed_hosts=("testserver",),
    )
    return TestClient(app, base_url="https://testserver")


def test_business_events_are_sanitized_stable_and_cursor_paginated(tmp_path) -> None:
    database_path = tmp_path / "events.db"
    repository = SqliteReviewRepository(database_path)
    _seed_case(repository, "REQ-EVENTS-1")
    _seed_case(repository, "REQ-EVENTS-2")
    _append_timeline_fixtures(repository, "REQ-EVENTS-1")
    service = ReviewService(repository)
    query = ReviewEventQuery(page_size=2)

    first = service.list_events("REQ-EVENTS-1", query)

    assert first.has_more is True
    assert first.next_cursor is not None
    event_ids = [event.event_id for event in first.items]

    # The purpose-separated HMAC key is derived from persisted metadata, so a
    # cursor remains usable after an adapter restart.
    restarted = ReviewService(SqliteReviewRepository(database_path))
    cursor = first.next_cursor
    while cursor is not None:
        page = restarted.list_events(
            "REQ-EVENTS-1",
            ReviewEventQuery(page_size=2, cursor=cursor),
        )
        event_ids.extend(event.event_id for event in page.items)
        cursor = page.next_cursor

    with sqlite3.connect(database_path) as connection:
        expected_ids = [
            row[0]
            for row in connection.execute(
                """
                SELECT event_id FROM audit_events
                WHERE request_id = 'REQ-EVENTS-1'
                ORDER BY occurred_at ASC, event_id ASC
                """
            ).fetchall()
        ]
    assert event_ids == expected_ids
    assert len(event_ids) == len(set(event_ids))
    assert event_ids.index("EVENT-TIED-A") < event_ids.index("EVENT-TIED-B")

    all_events = {
        event.event_id: event
        for event in service.list_events(
            "REQ-EVENTS-1",
            ReviewEventQuery(page_size=100),
        ).items
    }
    assert dict(all_events["EVENT-TIED-A"].payload) == {"attachment_count": 7}
    assert dict(all_events["EVENT-DECIDED"].payload) == {
        "decision_id": "DECISION-1",
        "from_status": "pending_review",
        "outcome": "approved",
        "reason": "Receipt verified.",
        "request_version": 1,
        "to_status": "approved_after_review",
    }
    assert dict(all_events["EVENT-UNKNOWN"].payload) == {}
    serialized = json.dumps(
        [dict(event.payload) for event in all_events.values()],
        sort_keys=True,
    )
    for forbidden in ("raw_response", "access_token", "location", "token"):
        assert forbidden not in serialized


def test_event_cursor_is_tamper_proof_and_bound_to_request_limit_and_purpose(tmp_path) -> None:
    repository = SqliteReviewRepository(tmp_path / "event-cursor.db")
    _seed_case(repository, "REQ-CURSOR-1")
    _seed_case(repository, "REQ-CURSOR-2")
    _append_timeline_fixtures(repository, "REQ-CURSOR-1")
    service = ReviewService(repository)
    first = service.list_events("REQ-CURSOR-1", ReviewEventQuery(page_size=2))
    assert first.next_cursor is not None
    cursor = first.next_cursor

    with pytest.raises(DomainValidationError, match="cursor"):
        service.list_events(
            "REQ-CURSOR-2",
            ReviewEventQuery(page_size=2, cursor=cursor),
        )
    with pytest.raises(DomainValidationError, match="cursor"):
        service.list_events(
            "REQ-CURSOR-1",
            ReviewEventQuery(page_size=3, cursor=cursor),
        )

    encoded, signature = cursor.split(".")
    tampered_signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    with pytest.raises(DomainValidationError, match="cursor"):
        service.list_events(
            "REQ-CURSOR-1",
            ReviewEventQuery(page_size=2, cursor=f"{encoded}.{tampered_signature}"),
        )

    # A valid event cursor must not be accepted by the queue cursor decoder.
    with pytest.raises(DomainValidationError, match="cursor"):
        repository.search_pending(
            ReviewQueueQuery(page_size=10, cursor=cursor),
            as_of=datetime.now(UTC),
        )


def test_event_service_returns_not_found_for_an_unknown_request(tmp_path) -> None:
    service = ReviewService(SqliteReviewRepository(tmp_path / "missing.db"))

    with pytest.raises(ReviewNotFoundError):
        service.list_events("REQ-MISSING", ReviewEventQuery())


def test_business_event_http_contract_auth_pagination_and_errors(tmp_path) -> None:
    repository = SqliteReviewRepository(tmp_path / "event-web.db")
    _seed_case(repository, "REQ-WEB-EVENTS")
    _append_timeline_fixtures(repository, "REQ-WEB-EVENTS")
    client = _web_client(repository)

    unauthorized = client.get("/api/reviews/REQ-WEB-EVENTS/events", params={"limit": 2})
    first = client.get(
        "/api/reviews/REQ-WEB-EVENTS/events",
        params={"limit": 2},
        headers=AUTHORIZATION,
    )

    assert unauthorized.status_code == 401
    assert first.status_code == 200
    payload = first.json()
    assert payload["request_id"] == "REQ-WEB-EVENTS"
    assert payload["kind"] == "business_audit"
    assert payload["page"]["limit"] == 2
    assert payload["page"]["sort"] == "occurred_at_asc"
    assert payload["page"]["has_more"] is True
    assert payload["page"]["next_cursor"]
    assert set(payload["items"][0]) == {
        "event_id",
        "event_type",
        "occurred_at",
        "actor",
        "correlation_id",
        "payload",
    }
    assert set(payload["items"][0]["actor"]) == {"type", "id"}
    assert "raw_response" not in json.dumps(payload)

    second = client.get(
        "/api/reviews/REQ-WEB-EVENTS/events",
        params={"limit": 2, "cursor": payload["page"]["next_cursor"]},
        headers=AUTHORIZATION,
    )
    assert second.status_code == 200
    assert {
        item["event_id"] for item in payload["items"]
    }.isdisjoint(item["event_id"] for item in second.json()["items"])

    encoded, signature = payload["page"]["next_cursor"].split(".")
    tampered_signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    tampered = client.get(
        "/api/reviews/REQ-WEB-EVENTS/events",
        params={"limit": 2, "cursor": f"{encoded}.{tampered_signature}"},
        headers=AUTHORIZATION,
    )
    missing = client.get(
        "/api/reviews/REQ-NOT-FOUND/events",
        headers=AUTHORIZATION,
    )

    assert tampered.status_code == 422
    assert missing.status_code == 404
    for invalid_params in (
        {"limit": 0},
        {"limit": 101},
        {"cursor": "not-a-signed-cursor"},
        {"unknown": "value"},
    ):
        invalid = client.get(
            "/api/reviews/REQ-WEB-EVENTS/events",
            params=invalid_params,
            headers=AUTHORIZATION,
        )
        assert invalid.status_code == 422, (invalid_params, invalid.text)
