import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from expense_agent.application.review import ReviewService
from expense_agent.infrastructure.review import SqliteReviewRepository
from expense_agent.presentation.app import create_app
from expense_agent.presentation.demo_seed import _build_case
from expense_agent.presentation.security import (
    BasicAuthenticator,
    CsrfProtector,
    ReviewerCredential,
    hash_password,
)


def _web_client(tmp_path: Path, *, require_https: bool = True) -> tuple[TestClient, Path]:
    database_path = tmp_path / "reviews.sqlite3"
    repository = SqliteReviewRepository(database_path)
    case, extraction, problems = _build_case(
        request_id="REQ-WEB-1",
        submitted_by="employee@example.com",
        amount="93.50",
        extracted_amount="89.50",
        category="meals",
        merchant="<img src=x onerror=alert(1)>",
        problem_code="TOTAL_MISMATCH",
        problem_message="Claimed and extracted totals differ.",
        offset_minutes=10,
    )
    repository.add_pending_case(case, extraction=extraction, problems=problems)
    credential = ReviewerCredential(
        username="reviewer",
        reviewer_id="directory:42",
        email="manager@example.com",
        display_name="Review Manager",
        password_hash=hash_password("secret-pass", iterations=100_000),
    )
    app = create_app(
        review_service=ReviewService(repository),
        authenticator=BasicAuthenticator((credential,)),
        csrf=CsrfProtector("test-csrf-secret-that-is-long-enough"),
        require_https=require_https,
        allowed_hosts=("testserver",),
    )
    return TestClient(app, base_url="https://testserver"), database_path


def _authenticated_headers() -> dict[str, str]:
    return {"Authorization": "Basic cmV2aWV3ZXI6c2VjcmV0LXBhc3M="}


def _session(client: TestClient) -> tuple[dict[str, str], str]:
    headers = _authenticated_headers()
    response = client.get("/api/session", headers=headers)
    assert response.status_code == 200
    return headers, response.json()["csrf_token"]


def test_review_page_requires_authentication_and_emits_security_headers(tmp_path) -> None:
    client, _database_path = _web_client(tmp_path)

    unauthorized = client.get("/reviews")
    authorized = client.get("/reviews", headers=_authenticated_headers())

    assert unauthorized.status_code == 401
    assert unauthorized.headers["www-authenticate"].startswith("Basic")
    assert authorized.status_code == 200
    assert "Human review workspace" in authorized.text
    assert "default-src 'none'" in authorized.headers["content-security-policy"]
    assert authorized.headers["strict-transport-security"].startswith("max-age=")
    assert authorized.headers["x-frame-options"] == "DENY"
    assert authorized.headers["cache-control"] == "no-store"
    assert "access-control-allow-origin" not in authorized.headers


def test_queue_and_detail_expose_required_evidence_with_version_etag(tmp_path) -> None:
    client, _database_path = _web_client(tmp_path)
    headers, _token = _session(client)

    queue = client.get("/api/reviews", headers=headers)
    details = client.get("/api/reviews/REQ-WEB-1", headers=headers)

    assert queue.status_code == 200
    assert queue.json()["items"][0]["request_id"] == "REQ-WEB-1"
    assert queue.json()["items"][0]["claimed_amount"] == {
        "amount": "93.50",
        "currency": "BRL",
    }
    assert details.status_code == 200
    assert details.headers["etag"].endswith('-v1"')
    payload = details.json()
    assert payload["raw_ocr_text"]
    assert payload["attachments"][0]["location"].endswith("receipt.jpg")
    assert payload["extraction"]["facts"]["total"]["amount"] == "89.50"
    assert payload["problems"][0]["code"] == "TOTAL_MISMATCH"
    assert payload["automated_decision"]["rule_evaluations"][0]["outcome"] == "review"
    assert "raw_response" not in payload["extraction"]["trace"]


def test_decision_rejects_missing_csrf_cross_origin_and_stale_version(tmp_path) -> None:
    client, _database_path = _web_client(tmp_path)
    headers, token = _session(client)
    etag = client.get("/api/reviews/REQ-WEB-1", headers=headers).headers["etag"]
    body = {"outcome": "approved", "reason": "Evidence verified."}

    no_csrf = client.post(
        "/api/reviews/REQ-WEB-1/decisions",
        headers={
            **headers,
            "Origin": "https://testserver",
            "If-Match": etag,
            "Idempotency-Key": "decision-key-no-csrf",
        },
        json=body,
    )
    cross_origin = client.post(
        "/api/reviews/REQ-WEB-1/decisions",
        headers={
            **headers,
            "Origin": "https://attacker.example",
            "X-CSRF-Token": token,
            "If-Match": etag,
            "Idempotency-Key": "decision-key-cross-origin",
        },
        json=body,
    )
    stale = client.post(
        "/api/reviews/REQ-WEB-1/decisions",
        headers={
            **headers,
            "Origin": "https://testserver",
            "X-CSRF-Token": token,
            "If-Match": '"stale"',
            "Idempotency-Key": "decision-key-stale-etag",
        },
        json=body,
    )

    assert no_csrf.status_code == 403
    assert cross_origin.status_code == 403
    assert stale.status_code == 412


def test_review_paths_reject_unbounded_or_invalid_request_ids(tmp_path) -> None:
    client, _database_path = _web_client(tmp_path)
    headers, token = _session(client)
    write_headers = {
        **headers,
        "Origin": "https://testserver",
        "X-CSRF-Token": token,
        "If-Match": '"unused"',
        "Idempotency-Key": "decision-key-invalid-path",
    }

    for request_id in ("!invalid", "A" * 129):
        assert client.get(f"/api/reviews/{request_id}", headers=headers).status_code == 422
        assert (
            client.get(f"/api/reviews/{request_id}/events", headers=headers).status_code
            == 422
        )
        assert (
            client.post(
                f"/api/reviews/{request_id}/decisions",
                headers=write_headers,
                json={"outcome": "rejected", "reason": "Invalid path."},
            ).status_code
            == 422
        )


def test_decision_identity_is_server_derived_and_writes_one_atomic_audit(tmp_path) -> None:
    client, database_path = _web_client(tmp_path)
    headers, token = _session(client)
    etag = client.get("/api/reviews/REQ-WEB-1", headers=headers).headers["etag"]
    write_headers = {
        **headers,
        "Origin": "https://testserver",
        "X-CSRF-Token": token,
        "If-Match": etag,
        "X-Correlation-ID": "web-test-42",
        "Idempotency-Key": "decision-key-web-record",
    }

    forged = client.post(
        "/api/reviews/REQ-WEB-1/decisions",
        headers=write_headers,
        json={
            "outcome": "approved",
            "reason": "Verified.",
            "reviewer_id": "forged-user",
        },
    )
    recorded = client.post(
        "/api/reviews/REQ-WEB-1/decisions",
        headers=write_headers,
        json={"outcome": "approved", "reason": "  Evidence verified against receipt.  "},
    )
    replayed = client.post(
        "/api/reviews/REQ-WEB-1/decisions",
        headers=write_headers,
        json={"outcome": "approved", "reason": "Evidence verified against receipt."},
    )
    conflicting_reuse = client.post(
        "/api/reviews/REQ-WEB-1/decisions",
        headers=write_headers,
        json={"outcome": "approved", "reason": "A different command binding."},
    )
    stale_new_command = client.post(
        "/api/reviews/REQ-WEB-1/decisions",
        headers={**write_headers, "Idempotency-Key": "decision-key-new-after-final"},
        json={"outcome": "approved", "reason": "Evidence verified against receipt."},
    )

    assert forged.status_code == 422
    assert recorded.status_code == 201
    assert recorded.json()["replayed"] is False
    assert recorded.json()["status"] == "approved_after_review"
    assert recorded.headers["x-correlation-id"] == "web-test-42"
    assert replayed.status_code == 200
    assert replayed.json()["replayed"] is True
    assert replayed.json()["decision_id"] == recorded.json()["decision_id"]
    assert replayed.json()["audit_event_id"] == recorded.json()["audit_event_id"]
    assert replayed.json()["version"] == recorded.json()["version"]
    assert conflicting_reuse.status_code == 409
    assert stale_new_command.status_code == 412
    assert client.get("/api/reviews", headers=headers).json()["items"] == []

    timeline = client.get("/api/reviews/REQ-WEB-1/events", headers=headers)
    assert timeline.status_code == 200
    timeline_payload = timeline.json()
    assert [item["event_type"] for item in timeline_payload["items"]] == [
        "review_case_enqueued",
        "human_review_decided",
    ]
    decided_event = timeline_payload["items"][-1]
    assert decided_event["actor"] == {"type": "reviewer", "id": "directory:42"}
    assert decided_event["correlation_id"] == "web-test-42"
    assert decided_event["payload"]["outcome"] == "approved"
    assert decided_event["payload"]["reason"] == "Evidence verified against receipt."
    assert "raw_response" not in str(timeline_payload)

    with sqlite3.connect(database_path) as connection:
        human = connection.execute("SELECT reviewer_id, reason FROM human_decisions").fetchall()
        audit = connection.execute(
            """
            SELECT actor_id, correlation_id FROM audit_events
            WHERE event_type = 'human_review_decided'
            """
        ).fetchall()
        reimbursement = connection.execute("SELECT status, version FROM reimbursements").fetchone()
    assert human == [("directory:42", "Evidence verified against receipt.")]
    assert audit == [("directory:42", "web-test-42")]
    assert reimbursement == ("approved_after_review", 2)


def test_missing_or_malformed_command_preconditions_fail_without_mutation(tmp_path) -> None:
    client, database_path = _web_client(tmp_path)
    headers, token = _session(client)
    etag = client.get("/api/reviews/REQ-WEB-1", headers=headers).headers["etag"]
    base = {
        **headers,
        "Origin": "https://testserver",
        "X-CSRF-Token": token,
        "Idempotency-Key": "decision-key-precondition",
    }

    missing_precondition = client.post(
        "/api/reviews/REQ-WEB-1/decisions",
        headers=base,
        json={"outcome": "rejected", "reason": "Invalid receipt."},
    )
    missing_idempotency = client.post(
        "/api/reviews/REQ-WEB-1/decisions",
        headers={
            **headers,
            "Origin": "https://testserver",
            "X-CSRF-Token": token,
            "If-Match": etag,
        },
        json={"outcome": "rejected", "reason": "Invalid receipt."},
    )
    malformed_idempotency = client.post(
        "/api/reviews/REQ-WEB-1/decisions",
        headers={
            **headers,
            "Origin": "https://testserver",
            "X-CSRF-Token": token,
            "If-Match": etag,
            "Idempotency-Key": "bad key",
        },
        json={"outcome": "rejected", "reason": "Invalid receipt."},
    )
    non_json = client.post(
        "/api/reviews/REQ-WEB-1/decisions",
        headers={**base, "If-Match": '"anything"', "Content-Type": "text/plain"},
        content="not-json",
    )

    assert missing_precondition.status_code == 428
    assert missing_idempotency.status_code == 428
    assert malformed_idempotency.status_code == 422
    assert non_json.status_code == 415
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM human_decisions").fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM review_decision_idempotency"
        ).fetchone()[0] == 0


def test_concurrent_identical_http_decisions_return_one_create_and_one_replay(
    tmp_path,
) -> None:
    first_client, database_path = _web_client(tmp_path)
    second_client = TestClient(first_client.app, base_url="https://testserver")
    headers, token = _session(first_client)
    etag = first_client.get(
        "/api/reviews/REQ-WEB-1",
        headers=headers,
    ).headers["etag"]
    barrier = threading.Barrier(2)

    def decide(client_and_correlation):
        client, correlation_id = client_and_correlation
        barrier.wait(timeout=5)
        return client.post(
            "/api/reviews/REQ-WEB-1/decisions",
            headers={
                **headers,
                "Origin": "https://testserver",
                "X-CSRF-Token": token,
                "If-Match": etag,
                "Idempotency-Key": "decision-key-http-concurrent",
                "X-Correlation-ID": correlation_id,
            },
            json={"outcome": "rejected", "reason": "Evidence is inconsistent."},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = tuple(
            executor.map(
                decide,
                (
                    (first_client, "corr-http-one"),
                    (second_client, "corr-http-two"),
                ),
            )
        )

    assert sorted(response.status_code for response in responses) == [200, 201]
    assert sorted(response.json()["replayed"] for response in responses) == [False, True]
    assert len({response.json()["decision_id"] for response in responses}) == 1
    assert len({response.json()["audit_event_id"] for response in responses}) == 1
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM human_decisions").fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM audit_events WHERE event_type = 'human_review_decided'"
        ).fetchone()[0] == 1


def test_http_is_blocked_when_https_is_required(tmp_path) -> None:
    client, _database_path = _web_client(tmp_path, require_https=True)
    http_client = TestClient(client.app, base_url="http://testserver")

    response = http_client.get("/reviews", headers=_authenticated_headers())

    assert response.status_code == 400
    assert response.json()["detail"] == "HTTPS is required"


def test_browser_code_uses_safe_dom_operations_and_no_sensitive_storage() -> None:
    javascript = (
        Path(__file__).parents[1]
        / "src"
        / "expense_agent"
        / "presentation"
        / "static"
        / "reviews.js"
    ).read_text(encoding="utf-8")

    assert "textContent" in javascript
    assert "innerHTML" not in javascript
    assert "localStorage" not in javascript
    assert "sessionStorage" not in javascript
