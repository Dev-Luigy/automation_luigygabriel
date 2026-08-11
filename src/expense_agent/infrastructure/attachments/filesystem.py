"""Secure local-filesystem attachment store for assessment integration."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import stat
import struct
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO, Final
from uuid import uuid4

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
from expense_agent.domain.attachments import (
    AttachmentId,
    AttachmentMediaType,
    AttachmentMetadata,
    SafeAttachmentFilename,
    StoredAttachment,
)

_ENVELOPE_MAGIC: Final = b"EXPENSE-AGENT-ATTACHMENT-V1"
_LENGTH_BYTES: Final = 8
_MAX_METADATA_BYTES: Final = 4_096
_PREFIX_BYTES: Final = 64
_TAIL_BYTES: Final = 2_048
_PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"
_PNG_IEND: Final = b"\x00\x00\x00\x00IEND\xaeB`\x82"
_PDF_TRAILING_WHITESPACE: Final = b"\x00\x09\x0a\x0c\x0d\x20"


class FileSystemAttachmentStore(AttachmentStore):
    """Write immutable evidence atomically below a trusted local root.

    This is an assessment adapter. The production target remains a private,
    versioned S3 store with authorization, malware scanning, and access audit.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        max_bytes: int = 10 * 1024 * 1024,
        chunk_size: int = 64 * 1024,
        id_factory: Callable[[], AttachmentId] = AttachmentId.new,
    ) -> None:
        if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
            raise ValueError("max_bytes must be a positive integer")
        if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer")
        self._root = Path(root).expanduser().resolve()
        self._objects = self._root / "objects"
        self._staging = self._root / ".staging"
        self._max_bytes = max_bytes
        self._chunk_size = chunk_size
        self._id_factory = id_factory
        _ensure_private_directory(self._root, parents=True)
        _ensure_private_directory(self._objects)
        _ensure_private_directory(self._staging)

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    def store(
        self,
        source: BinaryIO,
        *,
        original_filename: str,
        declared_media_type: str | None = None,
    ) -> AttachmentMetadata:
        safe_filename = SafeAttachmentFilename(original_filename)
        declared = _parse_declared_media_type(declared_media_type)
        attachment_id = self._id_factory()
        if not isinstance(attachment_id, AttachmentId):
            raise TypeError("id_factory must return AttachmentId")

        staging_path = self._staging / f"{uuid4().hex}.pending"
        descriptor = _exclusive_file_descriptor(staging_path)
        metadata: AttachmentMetadata | None = None
        try:
            with os.fdopen(descriptor, "wb", buffering=0) as target:
                sha256 = hashlib.sha256()
                byte_size = 0
                prefix = b""
                tail = b""

                while True:
                    try:
                        chunk = source.read(self._chunk_size)
                    except Exception as exc:
                        raise InvalidAttachmentContent("attachment stream could not be read") from exc
                    if not isinstance(chunk, bytes):
                        raise InvalidAttachmentContent("attachment stream must return bytes")
                    if not chunk:
                        break
                    byte_size += len(chunk)
                    if byte_size > self._max_bytes:
                        raise AttachmentTooLarge(
                            f"attachment exceeds the {self._max_bytes}-byte limit"
                        )
                    sha256.update(chunk)
                    prefix = (prefix + chunk)[:_PREFIX_BYTES]
                    tail = (tail + chunk)[-_TAIL_BYTES:]
                    target.write(chunk)

                detected = _detect_media_type(prefix=prefix, tail=tail, byte_size=byte_size)
                if declared is not None and declared is not detected:
                    raise AttachmentMediaTypeMismatch(
                        f"declared {declared.value} but detected {detected.value}"
                    )
                metadata = AttachmentMetadata(
                    attachment_id=attachment_id,
                    sha256=sha256.hexdigest(),
                    byte_size=byte_size,
                    media_type=detected,
                    original_filename=safe_filename,
                )
                encoded_metadata = _encode_metadata(metadata)
                target.write(encoded_metadata)
                target.write(struct.pack(">Q", len(encoded_metadata)))
                target.write(_ENVELOPE_MAGIC)
                os.fchmod(target.fileno(), 0o400)
                os.fsync(target.fileno())

            final_path = self._path_for(attachment_id, create_shard=True)
            try:
                os.link(staging_path, final_path, follow_symlinks=False)
            except FileExistsError as exc:
                raise AttachmentAlreadyExists(
                    f"attachment ID collision for {attachment_id.value}"
                ) from exc
            _fsync_directory(final_path.parent)
            assert metadata is not None
            return metadata
        finally:
            staging_path.unlink(missing_ok=True)
            _fsync_directory(self._staging)

    def read(self, attachment_id: AttachmentId) -> StoredAttachment:
        if not isinstance(attachment_id, AttachmentId):
            raise TypeError("attachment_id must be an AttachmentId")
        path = self._path_for(attachment_id, create_shard=False)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
        except FileNotFoundError as exc:
            raise AttachmentNotFound(f"attachment not found: {attachment_id.value}") from exc
        except OSError as exc:
            raise AttachmentIntegrityError("attachment object could not be opened safely") from exc

        try:
            file_stat = os.fstat(descriptor)
            if not stat.S_ISREG(file_stat.st_mode):
                raise AttachmentIntegrityError("attachment object is not a regular file")
            with os.fdopen(descriptor, "rb", closefd=False) as source:
                metadata, content = self._read_envelope(source, file_stat.st_size, attachment_id)
            return StoredAttachment(metadata=metadata, content=content)
        finally:
            os.close(descriptor)

    def _path_for(self, attachment_id: AttachmentId, *, create_shard: bool) -> Path:
        shard = self._objects / attachment_id.value[4:6]
        if create_shard:
            _ensure_private_directory(shard)
        return shard / f"{attachment_id.value}.blob"

    def _read_envelope(
        self,
        source: BinaryIO,
        file_size: int,
        expected_id: AttachmentId,
    ) -> tuple[AttachmentMetadata, bytes]:
        minimum_size = len(_ENVELOPE_MAGIC) + _LENGTH_BYTES + 1
        if file_size < minimum_size:
            raise AttachmentIntegrityError("attachment envelope is truncated")
        source.seek(file_size - len(_ENVELOPE_MAGIC))
        if source.read(len(_ENVELOPE_MAGIC)) != _ENVELOPE_MAGIC:
            raise AttachmentIntegrityError("attachment envelope marker is invalid")
        source.seek(file_size - len(_ENVELOPE_MAGIC) - _LENGTH_BYTES)
        metadata_size = struct.unpack(">Q", source.read(_LENGTH_BYTES))[0]
        if metadata_size <= 0 or metadata_size > _MAX_METADATA_BYTES:
            raise AttachmentIntegrityError("attachment metadata length is invalid")
        content_size = file_size - len(_ENVELOPE_MAGIC) - _LENGTH_BYTES - metadata_size
        if content_size <= 0 or content_size > self._max_bytes:
            raise AttachmentIntegrityError("attachment content length is invalid")
        source.seek(content_size)
        encoded_metadata = source.read(metadata_size)
        metadata = _decode_metadata(encoded_metadata)
        if metadata.attachment_id != expected_id or metadata.byte_size != content_size:
            raise AttachmentIntegrityError("attachment identity or size metadata is inconsistent")

        source.seek(0)
        content = source.read(content_size)
        if len(content) != content_size:
            raise AttachmentIntegrityError("attachment content is truncated")
        if hashlib.sha256(content).hexdigest() != metadata.sha256:
            raise AttachmentIntegrityError("attachment checksum validation failed")
        try:
            detected = _detect_media_type(
                prefix=content[:_PREFIX_BYTES],
                tail=content[-_TAIL_BYTES:],
                byte_size=len(content),
            )
        except UnsupportedAttachmentMediaType as exc:
            raise AttachmentIntegrityError("attachment media signature is invalid") from exc
        if detected is not metadata.media_type:
            raise AttachmentIntegrityError("attachment media signature no longer matches metadata")
        return metadata, content


def _parse_declared_media_type(value: str | None) -> AttachmentMediaType | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise UnsupportedAttachmentMediaType("declared media type must be text")
    try:
        return AttachmentMediaType(value.strip().lower())
    except ValueError as exc:
        raise UnsupportedAttachmentMediaType("declared media type is not allowlisted") from exc


def _detect_media_type(*, prefix: bytes, tail: bytes, byte_size: int) -> AttachmentMediaType:
    if byte_size >= 6 and prefix.startswith(b"\xff\xd8\xff") and tail.endswith(b"\xff\xd9"):
        return AttachmentMediaType.JPEG
    if (
        byte_size >= 45
        and prefix.startswith(_PNG_SIGNATURE)
        and prefix[8:12] == b"\x00\x00\x00\x0d"
        and prefix[12:16] == b"IHDR"
        and tail.endswith(_PNG_IEND)
    ):
        return AttachmentMediaType.PNG
    stripped_pdf_tail = tail.rstrip(_PDF_TRAILING_WHITESPACE)
    if byte_size >= 12 and prefix.startswith(b"%PDF-") and stripped_pdf_tail.endswith(b"%%EOF"):
        return AttachmentMediaType.PDF
    raise UnsupportedAttachmentMediaType("attachment bytes are not a valid JPEG, PNG, or PDF")


def _encode_metadata(metadata: AttachmentMetadata) -> bytes:
    payload = {
        "attachment_id": metadata.attachment_id.value,
        "byte_size": metadata.byte_size,
        "format_version": 1,
        "media_type": metadata.media_type.value,
        "original_filename": metadata.original_filename.value,
        "sha256": metadata.sha256,
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    if len(encoded) > _MAX_METADATA_BYTES:
        raise InvalidAttachmentContent("attachment metadata exceeds its storage limit")
    return encoded


def _decode_metadata(encoded: bytes) -> AttachmentMetadata:
    try:
        payload = json.loads(encoded.decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("format_version") != 1:
            raise ValueError("unsupported metadata shape")
        if set(payload) != {
            "attachment_id",
            "byte_size",
            "format_version",
            "media_type",
            "original_filename",
            "sha256",
        }:
            raise ValueError("unexpected metadata fields")
        return AttachmentMetadata(
            attachment_id=AttachmentId(payload["attachment_id"]),
            sha256=payload["sha256"],
            byte_size=payload["byte_size"],
            media_type=AttachmentMediaType(payload["media_type"]),
            original_filename=SafeAttachmentFilename(payload["original_filename"]),
        )
    except (KeyError, TypeError, UnicodeDecodeError, ValueError) as exc:
        raise AttachmentIntegrityError("attachment metadata is invalid") from exc


def _exclusive_file_descriptor(path: Path) -> int:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(path, flags, 0o600)
    except OSError as exc:
        raise AttachmentIntegrityError("staging object could not be created safely") from exc


def _ensure_private_directory(path: Path, *, parents: bool = False) -> None:
    try:
        path.mkdir(mode=0o700, parents=parents)
    except FileExistsError:
        pass
    path_stat = path.lstat()
    if (
        not stat.S_ISDIR(path_stat.st_mode)
        or stat.S_ISLNK(path_stat.st_mode)
        or path_stat.st_uid != os.geteuid()
        or stat.S_IMODE(path_stat.st_mode) & 0o077
    ):
        raise AttachmentIntegrityError("attachment store directory is not trusted")


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        try:
            os.fsync(descriptor)
        except OSError as exc:
            if exc.errno not in {errno.EINVAL, errno.ENOTSUP}:
                raise
    finally:
        os.close(descriptor)
