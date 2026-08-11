import base64
import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from expense_agent.application import ProcessingService, ReviewService
from expense_agent.infrastructure.attachments import FileSystemAttachmentStore
from expense_agent.infrastructure.extraction import DeterministicReceiptExtractor
from expense_agent.infrastructure.review import SqliteReviewRepository
from expense_agent.presentation.app import create_app
from expense_agent.presentation.security import (
    BasicAuthenticator,
    CsrfProtector,
    PrincipalRole,
    ReviewerCredential,
    hash_password,
)

ORIGIN = "https://testserver"
PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


def _credential(username: str, email: str, *roles: PrincipalRole) -> ReviewerCredential:
    return ReviewerCredential(
        username=username,
        reviewer_id=f"directory:{username}",
        email=email,
        display_name=username.title(),
        password_hash=hash_password(f"{username}-pass", iterations=100_000),
        roles=frozenset(roles),
    )


def _headers(username: str) -> dict[str, str]:
    encoded = base64.b64encode(f"{username}:{username}-pass".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def _write_headers(client: TestClient, username: str) -> dict[str, str]:
    headers = _headers(username)
    session = client.get("/api/session", headers=headers)
    assert session.status_code == 200
    return {
        **headers,
        "Origin": ORIGIN,
        "X-CSRF-Token": session.json()["csrf_token"],
    }


def _payload(request_id: str, submitted_by: str, amount: str = "93.50") -> dict[str, object]:
    return {
        "request_id": request_id,
        "submitted_by": submitted_by,
        "submitted_at": "2026-04-10T09:15:00Z",
        "raw_ocr_text": (
            "BOM SABOR RESTAURANT LTD\n"
            "TAX ID 12.345.678/0001-90\n"
            "DATE 09/04/2026\n"
            "BUSINESS LUNCH\n"
            f"TOTAL R$ {amount}"
        ),
        "claimed_category": "meals",
        "claimed_amount_brl": amount,
        "attachments": ["receipt.jpg"],
    }


def _client(tmp_path: Path) -> tuple[TestClient, Path]:
    database_path = tmp_path / "authorization.sqlite3"
    repository = SqliteReviewRepository(database_path)
    credentials = (
        _credential("alice", "alice@example.com", PrincipalRole.SUBMITTER),
        _credential("bob", "bob@example.com", PrincipalRole.SUBMITTER),
        _credential("reviewer", "reviewer@example.com", PrincipalRole.REVIEWER),
        _credential("auditor", "auditor@example.com", PrincipalRole.AUDITOR),
        _credential(
            "charlie",
            "charlie@example.com",
            PrincipalRole.SUBMITTER,
            PrincipalRole.REVIEWER,
        ),
        _credential("admin", "admin@example.com", PrincipalRole.ADMIN),
    )
    app = create_app(
        review_service=ReviewService(repository),
        processing_service=ProcessingService(repository, DeterministicReceiptExtractor()),
        authenticator=BasicAuthenticator(credentials),
        csrf=CsrfProtector("test-csrf-secret-that-is-long-enough"),
        require_https=True,
        allowed_hosts=("testserver",),
        attachment_store=FileSystemAttachmentStore(tmp_path / "evidence"),
    )
    return TestClient(app, base_url=ORIGIN), database_path


def test_roles_gate_surfaces_mutations_and_cross_submitter_results(tmp_path: Path) -> None:
    client, database_path = _client(tmp_path)
    alice_write = _write_headers(client, "alice")

    created = client.post(
        "/api/requests",
        headers=alice_write,
        json=_payload("REQ-ALICE-1", "alice@example.com"),
    )
    spoofed = client.post(
        "/api/requests",
        headers=alice_write,
        json=_payload("REQ-SPOOFED", "bob@example.com"),
    )

    assert created.status_code == 201
    assert spoofed.status_code == 403
    assert client.get("/api/requests/REQ-ALICE-1", headers=_headers("alice")).status_code == 200
    assert client.get("/api/requests/REQ-ALICE-1", headers=_headers("bob")).status_code == 404
    assert (
        client.get("/api/requests/REQ-ALICE-1", headers=_headers("reviewer")).status_code
        == 200
    )
    assert (
        client.get("/api/requests/REQ-ALICE-1", headers=_headers("auditor")).status_code
        == 200
    )

    assert client.get("/submit", headers=_headers("alice")).status_code == 200
    assert client.get("/reviews", headers=_headers("alice")).status_code == 403
    assert client.get("/reviews", headers=_headers("reviewer")).status_code == 200
    assert client.get("/reviews", headers=_headers("auditor")).status_code == 200

    reviewer_write = _write_headers(client, "reviewer")
    denied_submission = client.post(
        "/api/requests",
        headers=reviewer_write,
        json=_payload("REQ-REVIEWER", "reviewer@example.com"),
    )
    denied_upload = client.post(
        "/api/attachments",
        headers={
            **reviewer_write,
            "Content-Type": "application/pdf",
            "X-Attachment-Filename": "receipt.pdf",
        },
        content=PDF_BYTES,
    )
    assert denied_submission.status_code == 403
    assert denied_upload.status_code == 403

    session = client.get("/api/session", headers=_headers("auditor")).json()
    assert session["principal"]["roles"] == ["auditor"]
    assert session["reviewer"] == session["principal"]

    with sqlite3.connect(database_path) as connection:
        denied = connection.execute(
            """
            SELECT metadata_json FROM operational_audit_events
            WHERE status_code IN (403, 404)
            """
        ).fetchall()
    assert any(json.loads(row[0]).get("access_control") == "denied" for row in denied)


def test_decisions_require_reviewer_role_and_block_self_review(tmp_path: Path) -> None:
    client, _database_path = _client(tmp_path)
    charlie_write = _write_headers(client, "charlie")
    created = client.post(
        "/api/requests",
        headers=charlie_write,
        json=_payload("REQ-CHARLIE-1", "charlie@example.com", amount="640.00"),
    )
    assert created.status_code == 201
    assert created.json()["status"] == "pending_review"

    details = client.get(
        "/api/reviews/REQ-CHARLIE-1",
        headers=_headers("charlie"),
    )
    decision = {"outcome": "approved", "reason": "Evidence was checked."}
    self_review = client.post(
        "/api/reviews/REQ-CHARLIE-1/decisions",
        headers={
            **charlie_write,
            "If-Match": details.headers["etag"],
            "Idempotency-Key": "decision-key-charlie-self",
        },
        json=decision,
    )
    assert self_review.status_code == 403

    auditor_write = _write_headers(client, "auditor")
    auditor_decision = client.post(
        "/api/reviews/REQ-CHARLIE-1/decisions",
        headers={
            **auditor_write,
            "If-Match": details.headers["etag"],
            "Idempotency-Key": "decision-key-auditor",
        },
        json=decision,
    )
    assert auditor_decision.status_code == 403

    reviewer_write = _write_headers(client, "reviewer")
    reviewed = client.post(
        "/api/reviews/REQ-CHARLIE-1/decisions",
        headers={
            **reviewer_write,
            "If-Match": details.headers["etag"],
            "Idempotency-Key": "decision-key-reviewer",
        },
        json=decision,
    )
    assert reviewed.status_code == 201
    assert reviewed.json()["status"] == "approved_after_review"


def test_admin_can_submit_on_behalf_but_still_cannot_self_review(tmp_path: Path) -> None:
    client, _database_path = _client(tmp_path)
    admin_write = _write_headers(client, "admin")

    on_behalf = client.post(
        "/api/requests",
        headers=admin_write,
        json=_payload("REQ-ADMIN-BEHALF", "employee@example.com"),
    )
    own = client.post(
        "/api/requests",
        headers=admin_write,
        json=_payload("REQ-ADMIN-OWN", "admin@example.com", amount="640.00"),
    )

    assert on_behalf.status_code == 201
    assert own.status_code == 201
    details = client.get("/api/reviews/REQ-ADMIN-OWN", headers=_headers("admin"))
    denied = client.post(
        "/api/reviews/REQ-ADMIN-OWN/decisions",
        headers={
            **admin_write,
            "If-Match": details.headers["etag"],
            "Idempotency-Key": "decision-key-admin-self",
        },
        json={"outcome": "rejected", "reason": "Self-review must remain blocked."},
    )
    assert denied.status_code == 403


def test_managed_attachment_must_exist_and_pass_integrity_before_intake(
    tmp_path: Path,
) -> None:
    client, _database_path = _client(tmp_path)
    alice_write = _write_headers(client, "alice")
    uploaded = client.post(
        "/api/attachments",
        headers={
            **alice_write,
            "Content-Type": "application/pdf",
            "X-Attachment-Filename": "receipt.pdf",
        },
        content=PDF_BYTES,
    )
    assert uploaded.status_code == 201

    valid_payload = _payload("REQ-MANAGED-VALID", "alice@example.com")
    valid_payload["attachments"] = [uploaded.json()["reference"]]
    accepted = client.post("/api/requests", headers=alice_write, json=valid_payload)

    missing_payload = _payload("REQ-MANAGED-MISSING", "alice@example.com")
    missing_payload["attachments"] = [f"evidence:att_{'0' * 32}"]
    missing = client.post("/api/requests", headers=alice_write, json=missing_payload)

    malformed_payload = _payload("REQ-MANAGED-MALFORMED", "alice@example.com")
    malformed_payload["attachments"] = ["evidence:not-an-opaque-id"]
    malformed = client.post("/api/requests", headers=alice_write, json=malformed_payload)

    assert accepted.status_code == 201
    assert missing.status_code == 422
    assert missing.json()["detail"] == "Managed attachment reference does not exist"
    assert malformed.status_code == 422
    assert malformed.json()["detail"] == "Managed attachment reference is invalid"
