"""Application port for immutable attachment evidence storage."""

from __future__ import annotations

from typing import BinaryIO, Protocol, runtime_checkable

from expense_agent.domain.attachments import AttachmentId, AttachmentMetadata, StoredAttachment


class AttachmentStoreError(Exception):
    """Base error raised by an attachment storage adapter."""


class AttachmentTooLarge(AttachmentStoreError):
    """Raised after a streaming upload crosses the configured byte limit."""


class InvalidAttachmentContent(AttachmentStoreError):
    """Raised when a source does not provide a valid binary stream."""


class UnsupportedAttachmentMediaType(AttachmentStoreError):
    """Raised when bytes do not match an allowlisted media signature."""


class AttachmentMediaTypeMismatch(AttachmentStoreError):
    """Raised when the declared and detected media types disagree."""


class AttachmentAlreadyExists(AttachmentStoreError):
    """Raised on an opaque-ID collision instead of overwriting evidence."""


class AttachmentNotFound(AttachmentStoreError):
    """Raised when exact evidence cannot be found by its opaque identity."""


class AttachmentIntegrityError(AttachmentStoreError):
    """Raised when stored bytes and immutable metadata no longer agree."""


@runtime_checkable
class AttachmentStore(Protocol):
    """Persist and retrieve exact receipt bytes without exposing storage paths."""

    def store(
        self,
        source: BinaryIO,
        *,
        original_filename: str,
        declared_media_type: str | None = None,
    ) -> AttachmentMetadata:
        """Stream one immutable attachment and return application-owned metadata."""

    def read(self, attachment_id: AttachmentId) -> StoredAttachment:
        """Return the exact stored bytes after validating their integrity."""
