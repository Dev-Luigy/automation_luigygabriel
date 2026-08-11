"""Validated deployment identity carried through auditable service operations."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from expense_agent.domain._validation import require_non_blank
from expense_agent.domain.exceptions import DomainValidationError

_BUILD_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@+-]{0,191}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_UNVERSIONED_CONFIGURATION_HASH = hashlib.sha256(
    b"expense-agent:unconfigured"
).hexdigest()


@dataclass(frozen=True, slots=True)
class ExecutionIdentity:
    """Immutable code/configuration identity used for reproducibility."""

    build_id: str = "local-unversioned"
    configuration_hash: str = _UNVERSIONED_CONFIGURATION_HASH

    def __post_init__(self) -> None:
        build_id = require_non_blank(self.build_id, "build_id")
        configuration_hash = require_non_blank(
            self.configuration_hash,
            "configuration_hash",
        )
        if _BUILD_ID_PATTERN.fullmatch(build_id) is None:
            raise DomainValidationError(
                "build_id must be 1-192 characters from the portable identity alphabet"
            )
        if _SHA256_PATTERN.fullmatch(configuration_hash) is None:
            raise DomainValidationError(
                "configuration_hash must be a lowercase SHA-256 digest"
            )
        object.__setattr__(self, "build_id", build_id)
        object.__setattr__(self, "configuration_hash", configuration_hash)

    def pipeline_version(self, policy_version: str) -> str:
        """Bind a processing run to policy, executable, and effective configuration."""

        normalized_policy = require_non_blank(policy_version, "policy_version")
        return (
            f"{normalized_policy};build={self.build_id};"
            f"config={self.configuration_hash}"
        )


__all__ = ["ExecutionIdentity"]
