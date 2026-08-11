import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from expense_agent.application import ReviewService
from expense_agent.domain.reimbursement import AttachmentReference, ReimbursementSubmission
from expense_agent.infrastructure.attachments import FileSystemAttachmentStore
from expense_agent.infrastructure.review import SqliteReviewRepository
from expense_agent.presentation.app import create_app
from expense_agent.presentation.demo_seed import _build_case
from expense_agent.presentation.security import (
    BasicAuthenticator,
    CsrfProtector,
    ReviewerCredential,
    hash_password,
)

ORIGIN = "https://testserver"
AUTHENTICATED_HEADERS = {
    "Authorization": "Basic cmV2aWV3ZXI6c2VjcmV0LXBhc3M="
}
PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


def _credential() -> ReviewerCredential:
    return ReviewerCredential(
        username="reviewer",
        reviewer_id="directory:42",
        email="reviewer@example.com",
        display_name="Evidence Reviewer",
        password_hash=hash_password("secret-pass", iterations=100_000),
    )


def _client(
    tmp_path: Path,
    *,
    max_bytes: int = 4 * 1024 * 1024,
) -> tuple[TestClient, SqliteReviewRepository, Path]:
    database_path = tmp_path / "attachment-http.sqlite3"
    repository = SqliteReviewRepository(database_path)
    attachment_store = FileSystemAttachmentStore(
        tmp_path / "private-evidence",
        max_bytes=max_bytes,
    )
    app = create_app(
        review_service=ReviewService(repository),
        authenticator=BasicAuthenticator((_credential(),)),
        csrf=CsrfProtector("test-csrf-secret-that-is-long-enough"),
        require_https=True,
        allowed_hosts=("testserver",),
        attachment_store=attachment_store,
        attachment_max_bytes=max_bytes,
    )
    return TestClient(app, base_url=ORIGIN), repository, database_path


def _mutation_headers(client: TestClient, *, filename: str = "receipt.pdf") -> dict[str, str]:
    session = client.get("/api/session", headers=AUTHENTICATED_HEADERS)
    assert session.status_code == 200
    return {
        **AUTHENTICATED_HEADERS,
        "Content-Type": "application/pdf",
        "Origin": ORIGIN,
        "X-Attachment-Filename": filename,
        "X-CSRF-Token": session.json()["csrf_token"],
        "X-Correlation-ID": "attachment-http-test",
    }


def _seed_case(
    repository: SqliteReviewRepository,
    *,
    request_id: str,
    attachments: tuple[str, ...],
) -> None:
    case, extraction, problems = _build_case(
        request_id=request_id,
        submitted_by="employee@example.com",
        amount="640.00",
        extracted_amount="640.00",
        category="lodging",
        merchant="Hotel Example",
        problem_code="POLICY_EVIDENCE_REQUIRED",
        problem_message="Supporting evidence requires human review.",
        offset_minutes=5,
    )
    submission = case.submission
    case.submission = ReimbursementSubmission(
        request_id=submission.request_id,
        submitted_by=submission.submitted_by,
        submitted_at=submission.submitted_at,
        raw_ocr_text=submission.raw_ocr_text,
        claimed_category=submission.claimed_category,
        claimed_amount=submission.claimed_amount,
        attachments=tuple(AttachmentReference(item) for item in attachments),
    )
    repository.add_pending_case(case, extraction=extraction, problems=problems)


def test_raw_upload_requires_authentication_same_origin_csrf_and_allowlisted_bytes(
    tmp_path: Path,
) -> None:
    client, _repository, _database_path = _client(tmp_path)
    headers = _mutation_headers(client)

    unauthenticated = client.post(
        "/api/attachments",
        headers={"Content-Type": "application/pdf"},
        content=PDF_BYTES,
    )
    missing_csrf = client.post(
        "/api/attachments",
        headers={key: value for key, value in headers.items() if key != "X-CSRF-Token"},
        content=PDF_BYTES,
    )
    cross_origin = client.post(
        "/api/attachments",
        headers={**headers, "Origin": "https://attacker.example"},
        content=PDF_BYTES,
    )
    wrong_content_type = client.post(
        "/api/attachments",
        headers={**headers, "Content-Type": "text/plain"},
        content=PDF_BYTES,
    )
    missing_filename = client.post(
        "/api/attachments",
        headers={
            key: value
            for key, value in headers.items()
            if key != "X-Attachment-Filename"
        },
        content=PDF_BYTES,
    )
    mismatched_signature = client.post(
        "/api/attachments",
        headers=headers,
        content=b"not a PDF despite its declared type",
    )
    unsafe_filename = client.post(
        "/api/attachments",
        headers={**headers, "X-Attachment-Filename": "../receipt.pdf"},
        content=PDF_BYTES,
    )

    assert unauthenticated.status_code == 401
    assert missing_csrf.status_code == 403
    assert cross_origin.status_code == 403
    assert wrong_content_type.status_code == 415
    assert missing_filename.status_code == 422
    assert mismatched_signature.status_code == 415
    assert unsafe_filename.status_code == 422


def test_streamed_upload_is_bounded_even_without_content_length(tmp_path: Path) -> None:
    client, _repository, _database_path = _client(tmp_path, max_bytes=64)
    headers = _mutation_headers(client)

    def chunks():
        yield b"x" * 40
        yield b"y" * 40

    response = client.post("/api/attachments", headers=headers, content=chunks())

    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"


def test_managed_evidence_is_projected_and_downloaded_only_through_its_case(
    tmp_path: Path,
) -> None:
    client, repository, database_path = _client(tmp_path)
    mutation_headers = _mutation_headers(client)
    uploaded = client.post(
        "/api/attachments",
        headers=mutation_headers,
        content=[PDF_BYTES[:12], PDF_BYTES[12:]],
    )

    assert uploaded.status_code == 201
    upload_payload = uploaded.json()
    assert upload_payload["reference"] == f'evidence:{upload_payload["attachment_id"]}'
    assert upload_payload["byte_size"] == len(PDF_BYTES)
    assert upload_payload["media_type"] == "application/pdf"
    assert upload_payload["original_filename"] == "receipt.pdf"
    assert "path" not in upload_payload
    assert str(tmp_path) not in uploaded.text

    managed_reference = upload_payload["reference"]
    _seed_case(
        repository,
        request_id="REQ-EVIDENCE-1",
        attachments=(managed_reference, "object://legacy/receipt-1.pdf"),
    )
    _seed_case(
        repository,
        request_id="REQ-EVIDENCE-2",
        attachments=("object://legacy/receipt-2.pdf",),
    )
    attachment_id = upload_payload["attachment_id"]
    download_url = f"/api/reviews/REQ-EVIDENCE-1/attachments/{attachment_id}"
    headers = AUTHENTICATED_HEADERS

    details = client.get("/api/reviews/REQ-EVIDENCE-1", headers=headers)
    unauthenticated = client.get(download_url)
    cross_case = client.get(
        f"/api/reviews/REQ-EVIDENCE-2/attachments/{attachment_id}",
        headers=headers,
    )
    downloaded = client.get(download_url, headers=headers)

    assert details.status_code == 200
    managed, legacy = details.json()["attachments"]
    assert managed == {
        "location": managed_reference,
        "kind": "managed_evidence",
        "attachment_id": attachment_id,
        "open_url": download_url,
    }
    assert legacy == {
        "location": "object://legacy/receipt-1.pdf",
        "kind": "legacy_reference",
    }
    assert unauthenticated.status_code == 401
    assert cross_case.status_code == 404
    assert downloaded.status_code == 200
    assert downloaded.content == PDF_BYTES
    assert downloaded.headers["content-type"] == "application/pdf"
    assert downloaded.headers["content-disposition"].startswith(
        'inline; filename="receipt.pdf"; filename*=UTF-8\'\'receipt.pdf'
    )
    assert downloaded.headers["x-content-sha256"] == upload_payload["sha256"]
    assert downloaded.headers["etag"] == f'"sha256-{upload_payload["sha256"]}"'
    assert downloaded.headers["cache-control"] == "no-store"
    assert downloaded.headers["content-length"] == str(len(PDF_BYTES))

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT operation_type, route, request_id, actor_id, status_code, metadata_json
            FROM operational_audit_events
            WHERE operation_type IN ('attachment_upload', 'review_attachment_read')
            ORDER BY rowid
            """
        ).fetchall()
    successful_upload = next(row for row in rows if row[0] == "attachment_upload")
    successful_download = next(
        row
        for row in rows
        if row[0] == "review_attachment_read"
        and row[2] == "REQ-EVIDENCE-1"
        and row[4] == 200
    )
    assert successful_upload[1] == "/api/attachments"
    assert successful_upload[2] is None
    assert successful_upload[3] == "directory:42"
    assert json.loads(successful_upload[5])["attachment_id"] == attachment_id
    assert successful_download[1] == (
        "/api/reviews/{request_id}/attachments/{attachment_id}"
    )
    assert successful_download[3] == "directory:42"
    assert json.loads(successful_download[5]) == {
        "attachment_id": attachment_id,
        "byte_size": len(PDF_BYTES),
        "correlation_source": "generated",
        "media_type": "application/pdf",
        "sha256": upload_payload["sha256"],
    }
