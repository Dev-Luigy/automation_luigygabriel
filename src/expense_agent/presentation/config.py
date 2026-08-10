"""Environment-backed configuration for the review HTTP adapter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from expense_agent.presentation.security import (
    ReviewerCredential,
    SecurityConfigurationError,
    load_reviewer_credentials,
)


@dataclass(frozen=True, slots=True)
class ReviewWebSettings:
    database_path: Path
    reviewers: tuple[ReviewerCredential, ...]
    csrf_secret: str
    require_https: bool
    allowed_hosts: tuple[str, ...]
    host: str
    port: int
    forwarded_allow_ips: str

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
        return cls(
            database_path=database_path,
            reviewers=load_reviewer_credentials(reviewer_json),
            csrf_secret=csrf_secret,
            require_https=_environment_bool("EXPENSE_AGENT_REQUIRE_HTTPS", default=True),
            allowed_hosts=allowed_hosts,
            host=os.environ.get("EXPENSE_AGENT_HOST", "127.0.0.1"),
            port=port,
            forwarded_allow_ips=forwarded_allow_ips,
        )


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
