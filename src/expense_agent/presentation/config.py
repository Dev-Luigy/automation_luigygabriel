"""Environment-backed configuration for the review HTTP adapter."""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from urllib.parse import urlsplit

from expense_agent.application import ExecutionIdentity
from expense_agent.domain.exceptions import DomainValidationError
from expense_agent.presentation.security import (
    ReviewerCredential,
    SecurityConfigurationError,
    load_reviewer_credentials,
)

ExtractorParameter = str | int | float | bool | None

_HTTP_JSON_EXTRACTOR_ENVIRONMENT = (
    "EXPENSE_AGENT_EXTRACTOR_ENDPOINT",
    "EXPENSE_AGENT_EXTRACTOR_PROVIDER",
    "EXPENSE_AGENT_EXTRACTOR_MODEL",
    "EXPENSE_AGENT_EXTRACTOR_API_KEY",
    "EXPENSE_AGENT_EXTRACTOR_TIMEOUT_SECONDS",
    "EXPENSE_AGENT_EXTRACTOR_MAX_RESPONSE_BYTES",
    "EXPENSE_AGENT_EXTRACTOR_PARAMETERS_JSON",
)
_MAX_PARAMETERS_JSON_BYTES = 16 * 1024
_DEFAULT_ATTACHMENT_MAX_BYTES = 4 * 1024 * 1024
_MAX_ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024


class ExtractorMode(str, Enum):
    """Extractor implementations allowed at the environment trust boundary."""

    DETERMINISTIC = "deterministic"
    HTTP_JSON = "http_json"


@dataclass(frozen=True, slots=True)
class HttpJsonExtractorSettings:
    """Validated, secret-safe settings for the optional HTTPS JSON adapter."""

    endpoint: str
    provider: str
    model: str
    api_key: str | None = field(default=None, repr=False)
    timeout_seconds: float = 10.0
    max_response_bytes: int = 256 * 1024
    parameters: Mapping[str, ExtractorParameter] = field(default_factory=lambda: {"temperature": 0})

    def __post_init__(self) -> None:
        endpoint = self.endpoint
        if not isinstance(endpoint, str) or endpoint != endpoint.strip():
            raise SecurityConfigurationError("extractor endpoint must be an absolute HTTPS URL")
        if any(character.isspace() for character in endpoint):
            raise SecurityConfigurationError("extractor endpoint must be an absolute HTTPS URL")
        try:
            parsed = urlsplit(endpoint)
            hostname = parsed.hostname
            _port = parsed.port
        except ValueError as exc:
            raise SecurityConfigurationError(
                "extractor endpoint must be an absolute HTTPS URL"
            ) from exc
        if parsed.scheme != "https" or not hostname:
            raise SecurityConfigurationError("extractor endpoint must be an absolute HTTPS URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise SecurityConfigurationError(
                "extractor endpoint must not contain credentials, query, or fragment"
            )

        for field_name in ("provider", "model"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise SecurityConfigurationError(f"extractor {field_name} must not be blank")
            normalized = value.strip()
            if _contains_control_character(normalized):
                raise SecurityConfigurationError(
                    f"extractor {field_name} must not contain control characters"
                )
            object.__setattr__(self, field_name, normalized)

        if self.api_key is not None:
            if not isinstance(self.api_key, str) or not self.api_key.strip():
                raise SecurityConfigurationError("extractor API key must not be blank")
            normalized_key = self.api_key.strip()
            if any(character.isspace() for character in normalized_key):
                raise SecurityConfigurationError("extractor API key must not contain whitespace")
            object.__setattr__(self, "api_key", normalized_key)

        timeout = self.timeout_seconds
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or not 0 < timeout <= 120
        ):
            raise SecurityConfigurationError(
                "extractor timeout must be a finite number between 0 and 120 seconds"
            )
        object.__setattr__(self, "timeout_seconds", float(timeout))

        response_limit = self.max_response_bytes
        if (
            isinstance(response_limit, bool)
            or not isinstance(response_limit, int)
            or not 1_024 <= response_limit <= 4 * 1024 * 1024
        ):
            raise SecurityConfigurationError(
                "extractor response limit must be between 1024 and 4194304 bytes"
            )

        if not isinstance(self.parameters, Mapping):
            raise SecurityConfigurationError("extractor parameters must be a JSON object")
        normalized_parameters: dict[str, ExtractorParameter] = {}
        for key, value in self.parameters.items():
            if not isinstance(key, str) or not key.strip():
                raise SecurityConfigurationError(
                    "extractor parameter keys must be non-blank strings"
                )
            normalized_key = key.strip()
            if normalized_key in normalized_parameters:
                raise SecurityConfigurationError(
                    "extractor parameters contain duplicate normalized keys"
                )
            if _contains_control_character(normalized_key):
                raise SecurityConfigurationError(
                    "extractor parameter keys must not contain control characters"
                )
            if value is not None and not isinstance(value, (str, int, float, bool)):
                raise SecurityConfigurationError(
                    "extractor parameter values must be JSON scalar values"
                )
            if isinstance(value, float) and not math.isfinite(value):
                raise SecurityConfigurationError(
                    "extractor floating-point parameters must be finite"
                )
            normalized_parameters[normalized_key] = value
        object.__setattr__(self, "parameters", MappingProxyType(normalized_parameters))


@dataclass(frozen=True, slots=True)
class ReviewWebSettings:
    database_path: Path
    sqlite_journal_mode: str
    reviewers: tuple[ReviewerCredential, ...]
    csrf_secret: str
    require_https: bool
    allowed_hosts: tuple[str, ...]
    host: str
    port: int
    forwarded_allow_ips: str
    extractor_mode: ExtractorMode
    http_json_extractor_settings: HttpJsonExtractorSettings | None
    attachment_root: Path
    attachment_max_bytes: int
    build_id: str

    @property
    def configuration_hash(self) -> str:
        """Hash the complete effective configuration without persisting its secrets."""

        extractor = self.http_json_extractor_settings
        extractor_payload = (
            None
            if extractor is None
            else {
                "endpoint": extractor.endpoint,
                "provider": extractor.provider,
                "model": extractor.model,
                "api_key": extractor.api_key,
                "timeout_seconds": extractor.timeout_seconds,
                "max_response_bytes": extractor.max_response_bytes,
                "parameters": dict(extractor.parameters),
            }
        )
        payload = {
            "database_path": str(self.database_path),
            "sqlite_journal_mode": self.sqlite_journal_mode,
            "reviewers": [
                {
                    "username": credential.username,
                    "reviewer_id": credential.reviewer_id,
                    "email": credential.email,
                    "display_name": credential.display_name,
                    "password_hash": credential.password_hash,
                    "roles": sorted(role.value for role in credential.roles),
                }
                for credential in sorted(self.reviewers, key=lambda item: item.username)
            ],
            "csrf_secret": self.csrf_secret,
            "require_https": self.require_https,
            "allowed_hosts": list(self.allowed_hosts),
            "host": self.host,
            "port": self.port,
            "forwarded_allow_ips": self.forwarded_allow_ips,
            "extractor_mode": self.extractor_mode.value,
            "extractor": extractor_payload,
            "attachment_root": str(self.attachment_root),
            "attachment_max_bytes": self.attachment_max_bytes,
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @property
    def execution_identity(self) -> ExecutionIdentity:
        try:
            return ExecutionIdentity(
                build_id=self.build_id,
                configuration_hash=self.configuration_hash,
            )
        except DomainValidationError as exc:
            raise SecurityConfigurationError(
                "EXPENSE_AGENT_BUILD_ID is invalid"
            ) from exc

    @classmethod
    def from_environment(cls) -> ReviewWebSettings:
        reviewer_json = _required_environment("EXPENSE_AGENT_REVIEWERS_JSON")
        csrf_secret = _required_environment("EXPENSE_AGENT_CSRF_SECRET")
        database_path = Path(
            os.environ.get(
                "EXPENSE_AGENT_DATABASE_PATH",
                "./data/expense-agent.sqlite3",
            )
        )
        allowed_hosts = tuple(
            item.strip()
            for item in os.environ.get(
                "EXPENSE_AGENT_ALLOWED_HOSTS",
                "localhost,127.0.0.1",
            ).split(",")
            if item.strip()
        )
        if not allowed_hosts or "*" in allowed_hosts:
            raise SecurityConfigurationError(
                "allowed hosts must be explicit and must not contain a bare wildcard"
            )
        sqlite_journal_mode = (
            os.environ.get(
                "EXPENSE_AGENT_SQLITE_JOURNAL_MODE",
                "WAL",
            )
            .strip()
            .upper()
        )
        if sqlite_journal_mode not in {"WAL", "DELETE"}:
            raise SecurityConfigurationError(
                "EXPENSE_AGENT_SQLITE_JOURNAL_MODE must be WAL or DELETE"
            )
        try:
            port = int(os.environ.get("EXPENSE_AGENT_PORT", "8000"))
        except ValueError as exc:
            raise SecurityConfigurationError("EXPENSE_AGENT_PORT must be an integer") from exc
        if not 1 <= port <= 65_535:
            raise SecurityConfigurationError("EXPENSE_AGENT_PORT is outside the valid range")
        forwarded_allow_ips = os.environ.get(
            "EXPENSE_AGENT_FORWARDED_ALLOW_IPS",
            "127.0.0.1",
        ).strip()
        if not forwarded_allow_ips or forwarded_allow_ips == "*":
            raise SecurityConfigurationError(
                "forwarded proxy IPs must be explicit and must not be a wildcard"
            )
        extractor_mode, http_json_extractor_settings = _load_extractor_settings()
        attachment_root_raw = os.environ.get("EXPENSE_AGENT_ATTACHMENT_ROOT")
        if attachment_root_raw is None:
            attachment_root = database_path.parent / "attachments"
        elif not attachment_root_raw.strip():
            raise SecurityConfigurationError("EXPENSE_AGENT_ATTACHMENT_ROOT must not be blank")
        else:
            attachment_root = Path(attachment_root_raw.strip())
        attachment_max_bytes = _environment_int(
            "EXPENSE_AGENT_ATTACHMENT_MAX_BYTES",
            default=_DEFAULT_ATTACHMENT_MAX_BYTES,
        )
        if not 1_024 <= attachment_max_bytes <= _MAX_ATTACHMENT_MAX_BYTES:
            raise SecurityConfigurationError(
                "EXPENSE_AGENT_ATTACHMENT_MAX_BYTES must be between 1024 and 10485760 bytes"
            )
        settings = cls(
            database_path=database_path,
            sqlite_journal_mode=sqlite_journal_mode,
            reviewers=load_reviewer_credentials(reviewer_json),
            csrf_secret=csrf_secret,
            require_https=_environment_bool("EXPENSE_AGENT_REQUIRE_HTTPS", default=True),
            allowed_hosts=allowed_hosts,
            host=os.environ.get("EXPENSE_AGENT_HOST", "127.0.0.1"),
            port=port,
            forwarded_allow_ips=forwarded_allow_ips,
            extractor_mode=extractor_mode,
            http_json_extractor_settings=http_json_extractor_settings,
            attachment_root=attachment_root,
            attachment_max_bytes=attachment_max_bytes,
            build_id=os.environ.get(
                "EXPENSE_AGENT_BUILD_ID",
                "local-unversioned",
            ).strip(),
        )
        _execution_identity = settings.execution_identity
        return settings


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SecurityConfigurationError(f"{name} is required")
    return value


def _environment_bool(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise SecurityConfigurationError(f"{name} must be true or false")


def _load_extractor_settings() -> tuple[ExtractorMode, HttpJsonExtractorSettings | None]:
    raw_mode = os.environ.get("EXPENSE_AGENT_EXTRACTOR_MODE", ExtractorMode.DETERMINISTIC.value)
    try:
        mode = ExtractorMode(raw_mode.strip().lower())
    except ValueError as exc:
        raise SecurityConfigurationError(
            "EXPENSE_AGENT_EXTRACTOR_MODE must be deterministic or http_json"
        ) from exc

    if mode is ExtractorMode.DETERMINISTIC:
        unexpected = [name for name in _HTTP_JSON_EXTRACTOR_ENVIRONMENT if name in os.environ]
        if unexpected:
            names = ", ".join(unexpected)
            raise SecurityConfigurationError(
                f"{names} may only be set when EXPENSE_AGENT_EXTRACTOR_MODE=http_json"
            )
        return mode, None

    endpoint = _required_trimmed_environment("EXPENSE_AGENT_EXTRACTOR_ENDPOINT")
    provider = _required_trimmed_environment("EXPENSE_AGENT_EXTRACTOR_PROVIDER")
    model = _required_trimmed_environment("EXPENSE_AGENT_EXTRACTOR_MODEL")
    api_key = _optional_secret_environment("EXPENSE_AGENT_EXTRACTOR_API_KEY")
    timeout_seconds = _environment_float(
        "EXPENSE_AGENT_EXTRACTOR_TIMEOUT_SECONDS",
        default=10.0,
    )
    max_response_bytes = _environment_int(
        "EXPENSE_AGENT_EXTRACTOR_MAX_RESPONSE_BYTES",
        default=256 * 1024,
    )
    parameters = _environment_parameters()
    return mode, HttpJsonExtractorSettings(
        endpoint=endpoint,
        provider=provider,
        model=model,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
        parameters=parameters,
    )


def _required_trimmed_environment(name: str) -> str:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        raise SecurityConfigurationError(f"{name} is required for the http_json extractor")
    return raw.strip()


def _optional_secret_environment(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    if not raw.strip():
        raise SecurityConfigurationError(f"{name} must not be blank when set")
    return raw.strip()


def _environment_float(name: str, *, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise SecurityConfigurationError(f"{name} must be a number") from exc


def _environment_int(name: str, *, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise SecurityConfigurationError(f"{name} must be an integer") from exc


def _environment_parameters() -> Mapping[str, ExtractorParameter]:
    name = "EXPENSE_AGENT_EXTRACTOR_PARAMETERS_JSON"
    raw = os.environ.get(name, '{"temperature":0}')
    try:
        encoded_size = len(raw.encode("utf-8", errors="strict"))
    except UnicodeError as exc:
        raise SecurityConfigurationError(f"{name} must be valid UTF-8") from exc
    if encoded_size > _MAX_PARAMETERS_JSON_BYTES:
        raise SecurityConfigurationError(f"{name} exceeds the 16384-byte limit")
    try:
        decoded = json.loads(
            raw,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_non_finite_json_number,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise SecurityConfigurationError(f"{name} must be strict JSON") from exc
    if not isinstance(decoded, dict):
        raise SecurityConfigurationError(f"{name} must contain a JSON object")
    return decoded


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_non_finite_json_number(value: str) -> None:
    raise ValueError("non-finite JSON number")


def _contains_control_character(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)
