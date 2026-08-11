"""Small, replaceable authentication and CSRF adapters for the assessment UI."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000
SALT_BYTES = 16


class SecurityConfigurationError(ValueError):
    """Raised when security configuration is missing or malformed."""


class PrincipalRole(str, Enum):
    """Closed assessment role vocabulary supplied by trusted configuration."""

    SUBMITTER = "submitter"
    REVIEWER = "reviewer"
    AUDITOR = "auditor"
    ADMIN = "admin"


class PrincipalCapability(str, Enum):
    """Closed action vocabulary used by assessment authorization checks."""

    SUBMIT = "submit"
    REVIEW = "review"
    AUDIT = "audit"
    ADMIN = "admin"


_ROLE_CAPABILITIES = {
    PrincipalRole.SUBMITTER: frozenset({PrincipalCapability.SUBMIT}),
    PrincipalRole.REVIEWER: frozenset({PrincipalCapability.REVIEW}),
    PrincipalRole.AUDITOR: frozenset({PrincipalCapability.AUDIT}),
    PrincipalRole.ADMIN: frozenset(PrincipalCapability),
}


def _legacy_roles() -> frozenset[PrincipalRole]:
    # Before roles were configurable, each assessment account could use both
    # intake and review endpoints. Preserve that executable behavior.
    return frozenset({PrincipalRole.SUBMITTER, PrincipalRole.REVIEWER})


@dataclass(frozen=True, slots=True)
class ReviewerPrincipal:
    """Canonical identity established by an authentication adapter."""

    reviewer_id: str
    email: str
    display_name: str
    roles: frozenset[PrincipalRole] = field(default_factory=_legacy_roles)

    def __post_init__(self) -> None:
        object.__setattr__(self, "roles", _normalize_roles(self.roles))

    def has_role(self, role: PrincipalRole | str) -> bool:
        """Return exact role membership; administrator is not an identity alias."""

        try:
            normalized = PrincipalRole(role)
        except (TypeError, ValueError):
            return False
        return normalized in self.roles

    def can(self, capability: PrincipalCapability | str) -> bool:
        """Return whether any configured role grants a closed assessment action."""

        try:
            normalized = PrincipalCapability(capability)
        except (TypeError, ValueError):
            return False
        return any(normalized in _ROLE_CAPABILITIES[role] for role in self.roles)


@dataclass(frozen=True, slots=True)
class ReviewerCredential:
    username: str
    reviewer_id: str
    email: str
    display_name: str
    password_hash: str = field(repr=False)
    roles: frozenset[PrincipalRole] = field(default_factory=_legacy_roles)

    def __post_init__(self) -> None:
        object.__setattr__(self, "roles", _normalize_roles(self.roles))

    @property
    def principal(self) -> ReviewerPrincipal:
        return ReviewerPrincipal(
            reviewer_id=self.reviewer_id,
            email=self.email,
            display_name=self.display_name,
            roles=self.roles,
        )


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> str:
    """Return a self-describing PBKDF2 hash; plaintext is never persisted."""

    if not password:
        raise ValueError("password must not be empty")
    if not 100_000 <= iterations <= 2_000_000:
        raise ValueError("iterations must be between 100000 and 2000000")
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return f"{PBKDF2_ALGORITHM}${iterations}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    """Verify a password without exposing parsing errors to authentication callers."""

    parsed = _parse_password_hash(encoded)
    if parsed is None or len(password.encode("utf-8")) > 1_024:
        return False
    iterations, salt, expected = parsed
    try:
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )
    except (UnicodeError, ValueError):
        return False
    return hmac.compare_digest(actual, expected)


def _parse_password_hash(encoded: str) -> tuple[int, bytes, bytes] | None:
    try:
        algorithm, raw_iterations, raw_salt, raw_digest = encoded.split("$", 3)
        iterations = int(raw_iterations)
        salt = _b64decode(raw_salt)
        digest = _b64decode(raw_digest)
    except (UnicodeError, ValueError):
        return None
    if algorithm != PBKDF2_ALGORITHM or not 100_000 <= iterations <= 2_000_000:
        return None
    if len(salt) < SALT_BYTES or len(digest) != hashlib.sha256().digest_size:
        return None
    return iterations, salt, digest


class BasicAuthenticator:
    """HTTP Basic identity adapter used only by this self-contained assessment."""

    def __init__(self, credentials: tuple[ReviewerCredential, ...]) -> None:
        if not credentials:
            raise SecurityConfigurationError("at least one reviewer is required")
        by_username: dict[str, ReviewerCredential] = {}
        reviewer_ids: set[str] = set()
        for credential in credentials:
            username = credential.username.strip()
            reviewer_id = credential.reviewer_id.strip()
            email = credential.email.strip()
            display_name = credential.display_name.strip()
            password_hash = credential.password_hash.strip()
            if not username:
                raise SecurityConfigurationError("reviewer username must not be blank")
            if username in by_username:
                raise SecurityConfigurationError(f"duplicate reviewer username: {username}")
            if not all((reviewer_id, email, display_name, password_hash)):
                raise SecurityConfigurationError("reviewer fields must not be blank")
            if _parse_password_hash(password_hash) is None:
                raise SecurityConfigurationError(
                    f"reviewer {username!r} has an invalid PBKDF2 password hash"
                )
            if reviewer_id in reviewer_ids:
                raise SecurityConfigurationError(f"duplicate reviewer_id: {reviewer_id}")
            by_username[username] = ReviewerCredential(
                username=username,
                reviewer_id=reviewer_id,
                email=email,
                display_name=display_name,
                password_hash=password_hash,
                roles=credential.roles,
            )
            reviewer_ids.add(reviewer_id)
        self._credentials = by_username
        self._dummy_hash = hash_password(secrets.token_urlsafe(32))

    def authenticate(self, username: str, password: str) -> ReviewerPrincipal | None:
        if len(username) > 256 or len(password.encode("utf-8")) > 1_024:
            return None
        credential = self._credentials.get(username)
        encoded = credential.password_hash if credential is not None else self._dummy_hash
        valid = verify_password(password, encoded)
        if credential is None or not valid:
            return None
        return credential.principal


def load_reviewer_credentials(raw_json: str) -> tuple[ReviewerCredential, ...]:
    """Parse a strict reviewer list supplied by a secret/configuration provider."""

    try:
        decoded = json.loads(raw_json, object_pairs_hook=_unique_json_object)
    except (json.JSONDecodeError, ValueError) as exc:
        raise SecurityConfigurationError("reviewer JSON is invalid") from exc
    if not isinstance(decoded, list):
        raise SecurityConfigurationError("reviewer JSON must be a list")

    required = {"username", "reviewer_id", "email", "display_name", "password_hash"}
    with_roles = required | {"roles"}
    credentials: list[ReviewerCredential] = []
    for item in decoded:
        item_keys = frozenset(item) if isinstance(item, dict) else frozenset()
        if not isinstance(item, dict) or item_keys not in {
            frozenset(required),
            frozenset(with_roles),
        }:
            raise SecurityConfigurationError(
                "each reviewer must contain exactly username, reviewer_id, email, "
                "display_name, password_hash, and optional roles"
            )
        if not all(isinstance(item[key], str) for key in required):
            raise SecurityConfigurationError("all reviewer fields must be strings")
        roles = _legacy_roles()
        if "roles" in item:
            raw_roles = item["roles"]
            if not isinstance(raw_roles, list):
                raise SecurityConfigurationError("reviewer roles must be a JSON list")
            roles = _normalize_roles(raw_roles)
        credentials.append(
            ReviewerCredential(
                username=item["username"],
                reviewer_id=item["reviewer_id"],
                email=item["email"],
                display_name=item["display_name"],
                password_hash=item["password_hash"],
                roles=roles,
            )
        )
    return tuple(credentials)


def _normalize_roles(raw_roles: object) -> frozenset[PrincipalRole]:
    if isinstance(raw_roles, (str, bytes)) or not isinstance(
        raw_roles,
        (list, tuple, set, frozenset),
    ):
        raise SecurityConfigurationError("reviewer roles must be a collection")
    if not raw_roles:
        raise SecurityConfigurationError("reviewer roles must not be empty")

    normalized: set[PrincipalRole] = set()
    for raw_role in raw_roles:
        if not isinstance(raw_role, str):
            raise SecurityConfigurationError("reviewer roles must contain only strings")
        try:
            role = PrincipalRole(raw_role)
        except ValueError as exc:
            raise SecurityConfigurationError("reviewer roles contain an unknown role") from exc
        if role in normalized:
            raise SecurityConfigurationError("reviewer roles must not contain duplicates")
        normalized.add(role)
    return frozenset(normalized)


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


class CsrfProtector:
    """Issue short-lived reviewer-bound HMAC tokens for state-changing requests."""

    def __init__(self, secret: str, *, ttl: timedelta = timedelta(hours=1)) -> None:
        if len(secret.encode("utf-8")) < 32:
            raise SecurityConfigurationError("CSRF secret must contain at least 32 bytes")
        if ttl <= timedelta(0):
            raise SecurityConfigurationError("CSRF token lifetime must be positive")
        self._secret = secret.encode("utf-8")
        self._ttl = ttl

    def issue(self, reviewer_id: str, *, now: datetime | None = None) -> str:
        if not reviewer_id.strip():
            raise ValueError("reviewer_id must not be blank")
        current = _aware_utc(now)
        payload = json.dumps(
            {
                "sub": reviewer_id,
                "exp": int((current + self._ttl).timestamp()),
                "nonce": secrets.token_urlsafe(16),
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        encoded_payload = _b64encode(payload)
        signature = hmac.new(
            self._secret,
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        return f"{encoded_payload}.{_b64encode(signature)}"

    def verify(
        self,
        token: str,
        reviewer_id: str,
        *,
        now: datetime | None = None,
    ) -> bool:
        if len(token) > 4_096:
            return False
        try:
            encoded_payload, encoded_signature = token.split(".", 1)
            expected = hmac.new(
                self._secret,
                encoded_payload.encode("ascii"),
                hashlib.sha256,
            ).digest()
            supplied = _b64decode(encoded_signature)
            if not hmac.compare_digest(expected, supplied):
                return False
            payload = json.loads(_b64decode(encoded_payload))
            if set(payload) != {"sub", "exp", "nonce"}:
                return False
            if (
                not isinstance(payload["sub"], str)
                or type(payload["exp"]) is not int
                or not isinstance(payload["nonce"], str)
                or not payload["nonce"]
            ):
                return False
            if payload["sub"] != reviewer_id:
                return False
            return payload["exp"] >= int(_aware_utc(now).timestamp())
        except (TypeError, UnicodeError, ValueError, json.JSONDecodeError):
            return False


def _aware_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)
