import json

import pytest

from expense_agent.presentation.config import ReviewWebSettings
from expense_agent.presentation.security import SecurityConfigurationError, hash_password


def _configure_valid_environment(monkeypatch, tmp_path) -> None:
    reviewers = [
        {
            "username": "reviewer",
            "reviewer_id": "directory:7",
            "email": "reviewer@example.com",
            "display_name": "Finance Reviewer",
            "password_hash": hash_password("test-password", iterations=100_000),
        }
    ]
    monkeypatch.setenv("EXPENSE_AGENT_REVIEWERS_JSON", json.dumps(reviewers))
    monkeypatch.setenv("EXPENSE_AGENT_CSRF_SECRET", "x" * 32)
    monkeypatch.setenv("EXPENSE_AGENT_DATABASE_PATH", str(tmp_path / "reviews.db"))
    monkeypatch.setenv("EXPENSE_AGENT_REQUIRE_HTTPS", "false")
    monkeypatch.setenv("EXPENSE_AGENT_ALLOWED_HOSTS", "review.internal,localhost")
    monkeypatch.setenv("EXPENSE_AGENT_FORWARDED_ALLOW_IPS", "10.0.0.8")


def test_settings_load_explicit_security_boundaries(monkeypatch, tmp_path) -> None:
    _configure_valid_environment(monkeypatch, tmp_path)

    settings = ReviewWebSettings.from_environment()

    assert settings.database_path == tmp_path / "reviews.db"
    assert settings.sqlite_journal_mode == "WAL"
    assert settings.require_https is False
    assert settings.allowed_hosts == ("review.internal", "localhost")
    assert settings.forwarded_allow_ips == "10.0.0.8"
    assert settings.reviewers[0].reviewer_id == "directory:7"


@pytest.mark.parametrize(
    ("name", "value", "message"),
    (
        ("EXPENSE_AGENT_REQUIRE_HTTPS", "sometimes", "true or false"),
        ("EXPENSE_AGENT_ALLOWED_HOSTS", "*", "bare wildcard"),
        ("EXPENSE_AGENT_FORWARDED_ALLOW_IPS", "*", "must not be a wildcard"),
        ("EXPENSE_AGENT_SQLITE_JOURNAL_MODE", "MEMORY", "must be WAL or DELETE"),
    ),
)
def test_settings_fail_closed_on_unsafe_values(
    monkeypatch,
    tmp_path,
    name,
    value,
    message,
) -> None:
    _configure_valid_environment(monkeypatch, tmp_path)
    monkeypatch.setenv(name, value)

    with pytest.raises(SecurityConfigurationError, match=message):
        ReviewWebSettings.from_environment()
