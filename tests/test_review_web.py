import sqlite3
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
        headers={**headers, "Origin": "https://testserver", "If-Match": etag},
        json=body,
    )
    cross_origin = client.post(
        "/api/reviews/REQ-WEB-1/decisions",
        headers={
            **headers,
            "Origin": "https://attacker.example",
            "X-CSRF-Token": token,
            "If-Match": etag,
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
        },
        json=body,
    )

    assert no_csrf.status_code == 403
    assert cross_origin.status_code == 403
    assert stale.status_code == 412


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

    assert forged.status_code == 422
    assert recorded.status_code == 201
    assert recorded.json()["status"] == "approved_after_review"
    assert recorded.headers["x-correlation-id"] == "web-test-42"
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


def test_missing_if_match_and_non_json_body_are_rejected(tmp_path) -> None:
    client, _database_path = _web_client(tmp_path)
    headers, token = _session(client)
    base = {
        **headers,
        "Origin": "https://testserver",
        "X-CSRF-Token": token,
    }

    missing_precondition = client.post(
        "/api/reviews/REQ-WEB-1/decisions",
        headers=base,
        json={"outcome": "rejected", "reason": "Invalid receipt."},
    )
    non_json = client.post(
        "/api/reviews/REQ-WEB-1/decisions",
        headers={**base, "If-Match": '"anything"', "Content-Type": "text/plain"},
        content="not-json",
    )

    assert missing_precondition.status_code == 428
    assert non_json.status_code == 415


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
