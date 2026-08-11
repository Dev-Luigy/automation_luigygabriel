"""Value objects for immutable receipt evidence."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

from expense_agent.domain.exceptions import DomainValidationError

_ATTACHMENT_ID_PATTERN = re.compile(r"att_[0-9a-f]{32}\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_FILENAME_PUNCTUATION = frozenset(" ._()-")
_MAX_FILENAME_BYTES = 255


class InvalidAttachmentId(DomainValidationError):
    """Raised when an attachment identifier is not application-generated shape."""


class InvalidAttachmentFilename(DomainValidationError):
    """Raised when original filename metadata is unsafe to retain."""


class AttachmentMediaType(str, Enum):
    """Media types accepted by the assessment evidence boundary."""

    JPEG = "image/jpeg"
    PNG = "image/png"
    PDF = "application/pdf"


@dataclass(frozen=True, slots=True)
class AttachmentId:
    """Opaque server-generated identity that is safe to use as a storage key."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or _ATTACHMENT_ID_PATTERN.fullmatch(self.value) is None:
            raise InvalidAttachmentId("attachment_id must be an opaque application-generated ID")

    @classmethod
    def new(cls) -> AttachmentId:
        """Generate an identity without using client data, filenames, or content hashes."""

        return cls(f"att_{uuid4().hex}")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class SafeAttachmentFilename:
    """Validated original filename metadata that is never used as a path."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidAttachmentFilename("original filename must be text")
        normalized = unicodedata.normalize("NFC", self.value)
        if not normalized or normalized != normalized.strip():
            raise InvalidAttachmentFilename("original filename must not be empty or padded")
        if normalized in {".", ".."} or normalized.startswith("."):
            raise InvalidAttachmentFilename("original filename must not be hidden or relative")
        if normalized.endswith((".", " ")):
            raise InvalidAttachmentFilename("original filename has an unsafe suffix")
        if len(normalized.encode("utf-8")) > _MAX_FILENAME_BYTES:
            raise InvalidAttachmentFilename("original filename is too long")
        if any(
            not (character.isalnum() or character in _SAFE_FILENAME_PUNCTUATION)
            for character in normalized
        ):
            raise InvalidAttachmentFilename("original filename contains unsafe characters")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class AttachmentMetadata:
    """Immutable facts bound to the exact stored attachment bytes."""

    attachment_id: AttachmentId
    sha256: str
    byte_size: int
    media_type: AttachmentMediaType
    original_filename: SafeAttachmentFilename

    def __post_init__(self) -> None:
        if not isinstance(self.attachment_id, AttachmentId):
            raise DomainValidationError("attachment metadata requires an AttachmentId")
        if not isinstance(self.sha256, str) or _SHA256_PATTERN.fullmatch(self.sha256) is None:
            raise DomainValidationError("attachment sha256 must be lowercase hexadecimal")
        if not isinstance(self.byte_size, int) or isinstance(self.byte_size, bool):
            raise DomainValidationError("attachment byte_size must be an integer")
        if self.byte_size <= 0:
            raise DomainValidationError("attachment byte_size must be positive")
        if not isinstance(self.media_type, AttachmentMediaType):
            raise DomainValidationError("attachment media_type must be allowlisted")
        if not isinstance(self.original_filename, SafeAttachmentFilename):
            raise DomainValidationError("attachment original_filename must be validated")


@dataclass(frozen=True, slots=True)
class StoredAttachment:
    """Exact bytes returned with the immutable metadata that identifies them."""

    metadata: AttachmentMetadata
    content: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.content, bytes):
            raise DomainValidationError("stored attachment content must be bytes")
        if len(self.content) != self.metadata.byte_size:
            raise DomainValidationError("stored attachment content size does not match metadata")
