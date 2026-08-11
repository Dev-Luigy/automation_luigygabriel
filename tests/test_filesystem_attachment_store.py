import hashlib
import io
import os
import stat

import pytest

from expense_agent.application.attachments import (
    AttachmentAlreadyExists,
    AttachmentIntegrityError,
    AttachmentMediaTypeMismatch,
    AttachmentNotFound,
    AttachmentStore,
    AttachmentTooLarge,
    UnsupportedAttachmentMediaType,
)
from expense_agent.domain.attachments import (
    AttachmentId,
    AttachmentMediaType,
    InvalidAttachmentFilename,
)
from expense_agent.infrastructure.attachments import FileSystemAttachmentStore

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00assessment-receipt\xff\xd9"
PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\x0dIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    b"\x00\x00\x00\x00"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)
PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\nstartxref\n0\n%%EOF\n"


@pytest.mark.parametrize(
    ("content", "filename", "declared", "expected"),
    [
        (JPEG, "receipt-01.jpg", "image/jpeg", AttachmentMediaType.JPEG),
        (PNG, "comprovante 02.png", "image/png", AttachmentMediaType.PNG),
        (PDF, "Nota_Fiscal-(03).pdf", "application/pdf", AttachmentMediaType.PDF),
    ],
)
def test_store_detects_allowlisted_media_and_reads_exact_bytes(
    tmp_path,
    content: bytes,
    filename: str,
    declared: str,
    expected: AttachmentMediaType,
) -> None:
    store = FileSystemAttachmentStore(tmp_path)

    metadata = store.store(
        io.BytesIO(content),
        original_filename=filename,
        declared_media_type=declared,
    )
    stored = store.read(metadata.attachment_id)

    assert isinstance(store, AttachmentStore)
    assert metadata.attachment_id.value.startswith("att_")
    assert len(metadata.attachment_id.value) == 36
    assert metadata.sha256 == hashlib.sha256(content).hexdigest()
    assert metadata.byte_size == len(content)
    assert metadata.media_type is expected
    assert metadata.original_filename.value == filename
    assert stored.metadata == metadata
    assert stored.content == content
    object_path = next((tmp_path / "objects").rglob("*.blob"))
    assert filename not in str(object_path)
    assert stat.S_IMODE(object_path.stat().st_mode) == 0o400


def test_store_creates_a_nested_private_root(tmp_path) -> None:
    root = tmp_path / "nested" / "evidence"
    store = FileSystemAttachmentStore(root)

    metadata = store.store(io.BytesIO(PDF), original_filename="receipt.pdf")

    assert store.read(metadata.attachment_id).content == PDF
    assert stat.S_IMODE(root.stat().st_mode) == 0o700


def test_store_rejects_an_existing_directory_visible_to_other_users(tmp_path) -> None:
    root = tmp_path / "unsafe-evidence"
    root.mkdir(mode=0o755)

    with pytest.raises(AttachmentIntegrityError, match="not trusted"):
        FileSystemAttachmentStore(root)


def test_store_accepts_an_explicit_access_point_owner_uid(monkeypatch, tmp_path) -> None:
    actual_owner = tmp_path.stat().st_uid
    simulated_process_uid = actual_owner + 1
    monkeypatch.setattr(os, "geteuid", lambda: simulated_process_uid)

    with pytest.raises(AttachmentIntegrityError, match="not trusted"):
        FileSystemAttachmentStore(tmp_path / "default-owner")

    store = FileSystemAttachmentStore(
        tmp_path / "access-point-owner",
        trusted_owner_uid=actual_owner,
    )
    metadata = store.store(io.BytesIO(PDF), original_filename="receipt.pdf")

    assert store.read(metadata.attachment_id).content == PDF


@pytest.mark.parametrize(
    "filename",
    [
        "../receipt.pdf",
        "..\\receipt.pdf",
        "/tmp/receipt.pdf",
        "receipt/other.pdf",
        "C:\\receipt.pdf",
        ".hidden.pdf",
        "receipt\x00.pdf",
        " padded.pdf",
        "x" * 256 + ".pdf",
    ],
)
def test_store_rejects_malicious_or_ambiguous_filenames(tmp_path, filename: str) -> None:
    store = FileSystemAttachmentStore(tmp_path)

    with pytest.raises(InvalidAttachmentFilename):
        store.store(io.BytesIO(PDF), original_filename=filename)

    assert list((tmp_path / "objects").rglob("*.blob")) == []
    assert list((tmp_path / ".staging").iterdir()) == []


def test_duplicate_bytes_receive_distinct_opaque_ids_without_content_deduplication(tmp_path) -> None:
    store = FileSystemAttachmentStore(tmp_path)

    first = store.store(io.BytesIO(PDF), original_filename="first.pdf")
    second = store.store(io.BytesIO(PDF), original_filename="second.pdf")

    assert first.attachment_id != second.attachment_id
    assert first.sha256 == second.sha256
    assert store.read(first.attachment_id).content == PDF
    assert store.read(second.attachment_id).content == PDF


class ChunkOnlyStream:
    def __init__(self, content: bytes) -> None:
        self._content = content
        self._offset = 0
        self.requested_sizes: list[int] = []

    def read(self, size: int = -1) -> bytes:
        if size <= 0:
            raise AssertionError("store must use bounded streaming reads")
        self.requested_sizes.append(size)
        chunk = self._content[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


def test_store_enforces_size_limit_while_streaming_and_cleans_staging(tmp_path) -> None:
    source = ChunkOnlyStream(PDF + b"overflow")
    store = FileSystemAttachmentStore(tmp_path, max_bytes=len(PDF), chunk_size=7)

    with pytest.raises(AttachmentTooLarge):
        store.store(source, original_filename="receipt.pdf")

    assert source.requested_sizes and set(source.requested_sizes) == {7}
    assert list((tmp_path / "objects").rglob("*.blob")) == []
    assert list((tmp_path / ".staging").iterdir()) == []


@pytest.mark.parametrize("content", [b"", b"GIF89a", b"%PDF-not-finished"])
def test_store_rejects_empty_or_invalid_media_signatures(tmp_path, content: bytes) -> None:
    store = FileSystemAttachmentStore(tmp_path)

    with pytest.raises(UnsupportedAttachmentMediaType):
        store.store(io.BytesIO(content), original_filename="receipt.pdf")


def test_store_rejects_unallowlisted_declared_type_and_signature_mismatch(tmp_path) -> None:
    store = FileSystemAttachmentStore(tmp_path)

    with pytest.raises(UnsupportedAttachmentMediaType):
        store.store(
            io.BytesIO(PDF),
            original_filename="receipt.pdf",
            declared_media_type="image/gif",
        )
    with pytest.raises(AttachmentMediaTypeMismatch):
        store.store(
            io.BytesIO(PDF),
            original_filename="receipt.pdf",
            declared_media_type="image/png",
        )


def test_opaque_id_collision_never_overwrites_existing_evidence(tmp_path) -> None:
    fixed_id = AttachmentId("att_0123456789abcdef0123456789abcdef")
    store = FileSystemAttachmentStore(tmp_path, id_factory=lambda: fixed_id)
    original = store.store(io.BytesIO(PDF), original_filename="original.pdf")

    with pytest.raises(AttachmentAlreadyExists):
        store.store(io.BytesIO(JPEG), original_filename="replacement.jpg")

    stored = store.read(fixed_id)
    assert stored.metadata == original
    assert stored.content == PDF
    assert len(list((tmp_path / "objects").rglob("*.blob"))) == 1


def test_attachment_id_cannot_contain_a_path() -> None:
    with pytest.raises(ValueError, match="application-generated"):
        AttachmentId("../../outside")


def test_read_detects_external_tampering_instead_of_returning_changed_bytes(tmp_path) -> None:
    store = FileSystemAttachmentStore(tmp_path)
    metadata = store.store(io.BytesIO(PDF), original_filename="receipt.pdf")
    object_path = next((tmp_path / "objects").rglob("*.blob"))
    os.chmod(object_path, 0o600)
    with object_path.open("r+b") as target:
        target.seek(0)
        target.write(b"!")

    with pytest.raises(AttachmentIntegrityError, match="checksum"):
        store.read(metadata.attachment_id)


def test_read_of_unknown_application_id_is_explicit(tmp_path) -> None:
    store = FileSystemAttachmentStore(tmp_path)

    with pytest.raises(AttachmentNotFound, match="not found"):
        store.read(AttachmentId("att_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"))
