import json

import pytest

from expense_agent.infrastructure.extraction import (
    DeterministicReceiptExtractor,
    HttpJsonReceiptExtractor,
)
from expense_agent.presentation.config import ExtractorMode, ReviewWebSettings
from expense_agent.presentation.main import create_receipt_extractor
from expense_agent.presentation.security import SecurityConfigurationError, hash_password

_EXTRACTOR_ENVIRONMENT = (
    "EXPENSE_AGENT_EXTRACTOR_MODE",
    "EXPENSE_AGENT_EXTRACTOR_ENDPOINT",
    "EXPENSE_AGENT_EXTRACTOR_PROVIDER",
    "EXPENSE_AGENT_EXTRACTOR_MODEL",
    "EXPENSE_AGENT_EXTRACTOR_API_KEY",
    "EXPENSE_AGENT_EXTRACTOR_TIMEOUT_SECONDS",
    "EXPENSE_AGENT_EXTRACTOR_MAX_RESPONSE_BYTES",
    "EXPENSE_AGENT_EXTRACTOR_PARAMETERS_JSON",
)


def _configure_valid_environment(monkeypatch, tmp_path) -> None:
    for name in _EXTRACTOR_ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)
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
    assert settings.extractor_mode is ExtractorMode.DETERMINISTIC
    assert settings.http_json_extractor_settings is None


def test_default_composition_remains_offline_and_deterministic(monkeypatch, tmp_path) -> None:
    _configure_valid_environment(monkeypatch, tmp_path)

    extractor = create_receipt_extractor(ReviewWebSettings.from_environment())

    assert isinstance(extractor, DeterministicReceiptExtractor)


def test_http_json_settings_are_strictly_parsed_composed_and_secret_safe(
    monkeypatch,
    tmp_path,
) -> None:
    _configure_valid_environment(monkeypatch, tmp_path)
    secret = "provider-key-that-must-not-appear"
    monkeypatch.setenv("EXPENSE_AGENT_EXTRACTOR_MODE", "http_json")
    monkeypatch.setenv(
        "EXPENSE_AGENT_EXTRACTOR_ENDPOINT",
        "https://extractor.example.test/v1/receipts",
    )
    monkeypatch.setenv("EXPENSE_AGENT_EXTRACTOR_PROVIDER", " provider-name ")
    monkeypatch.setenv("EXPENSE_AGENT_EXTRACTOR_MODEL", " model-2026-08 ")
    monkeypatch.setenv("EXPENSE_AGENT_EXTRACTOR_API_KEY", secret)
    monkeypatch.setenv("EXPENSE_AGENT_EXTRACTOR_TIMEOUT_SECONDS", "3.5")
    monkeypatch.setenv("EXPENSE_AGENT_EXTRACTOR_MAX_RESPONSE_BYTES", "4096")
    monkeypatch.setenv(
        "EXPENSE_AGENT_EXTRACTOR_PARAMETERS_JSON",
        '{"temperature":0,"seed":42,"strict":true,"label":null}',
    )

    settings = ReviewWebSettings.from_environment()
    extractor_settings = settings.http_json_extractor_settings
    extractor = create_receipt_extractor(settings)

    assert settings.extractor_mode is ExtractorMode.HTTP_JSON
    assert extractor_settings is not None
    assert extractor_settings.endpoint == "https://extractor.example.test/v1/receipts"
    assert extractor_settings.provider == "provider-name"
    assert extractor_settings.model == "model-2026-08"
    assert extractor_settings.api_key == secret
    assert extractor_settings.timeout_seconds == 3.5
    assert extractor_settings.max_response_bytes == 4096
    assert extractor_settings.parameters == {
        "temperature": 0,
        "seed": 42,
        "strict": True,
        "label": None,
    }
    assert isinstance(extractor, HttpJsonReceiptExtractor)
    assert extractor.provider == "provider-name"
    assert extractor.model == "model-2026-08"
    assert secret not in repr(extractor_settings)
    assert secret not in repr(settings)
    assert secret not in repr(extractor)


def test_deterministic_mode_rejects_silently_ignored_http_configuration(
    monkeypatch,
    tmp_path,
) -> None:
    _configure_valid_environment(monkeypatch, tmp_path)
    secret = "must-not-leak-from-failed-startup"
    monkeypatch.setenv("EXPENSE_AGENT_EXTRACTOR_API_KEY", secret)

    with pytest.raises(SecurityConfigurationError) as raised:
        ReviewWebSettings.from_environment()

    assert "only be set" in str(raised.value)
    assert secret not in str(raised.value)


@pytest.mark.parametrize(
    ("overrides", "message"),
    (
        ({"EXPENSE_AGENT_EXTRACTOR_MODE": "unknown"}, "must be deterministic or http_json"),
        ({"EXPENSE_AGENT_EXTRACTOR_MODE": "http_json"}, "EXTRACTOR_ENDPOINT is required"),
        (
            {
                "EXPENSE_AGENT_EXTRACTOR_MODE": "http_json",
                "EXPENSE_AGENT_EXTRACTOR_ENDPOINT": "http://extractor.example.test/v1",
                "EXPENSE_AGENT_EXTRACTOR_PROVIDER": "provider",
                "EXPENSE_AGENT_EXTRACTOR_MODEL": "model",
            },
            "absolute HTTPS URL",
        ),
        (
            {
                "EXPENSE_AGENT_EXTRACTOR_MODE": "http_json",
                "EXPENSE_AGENT_EXTRACTOR_ENDPOINT": "https://extractor.example.test/v1",
                "EXPENSE_AGENT_EXTRACTOR_PROVIDER": "provider",
                "EXPENSE_AGENT_EXTRACTOR_MODEL": "model",
                "EXPENSE_AGENT_EXTRACTOR_TIMEOUT_SECONDS": "NaN",
            },
            "finite number",
        ),
        (
            {
                "EXPENSE_AGENT_EXTRACTOR_MODE": "http_json",
                "EXPENSE_AGENT_EXTRACTOR_ENDPOINT": "https://extractor.example.test/v1",
                "EXPENSE_AGENT_EXTRACTOR_PROVIDER": "provider",
                "EXPENSE_AGENT_EXTRACTOR_MODEL": "model",
                "EXPENSE_AGENT_EXTRACTOR_MAX_RESPONSE_BYTES": "1023",
            },
            "between 1024 and 4194304",
        ),
        (
            {
                "EXPENSE_AGENT_EXTRACTOR_MODE": "http_json",
                "EXPENSE_AGENT_EXTRACTOR_ENDPOINT": "https://extractor.example.test/v1",
                "EXPENSE_AGENT_EXTRACTOR_PROVIDER": "provider",
                "EXPENSE_AGENT_EXTRACTOR_MODEL": "model",
                "EXPENSE_AGENT_EXTRACTOR_PARAMETERS_JSON": "[]",
            },
            "must contain a JSON object",
        ),
        (
            {
                "EXPENSE_AGENT_EXTRACTOR_MODE": "http_json",
                "EXPENSE_AGENT_EXTRACTOR_ENDPOINT": "https://extractor.example.test/v1",
                "EXPENSE_AGENT_EXTRACTOR_PROVIDER": "provider",
                "EXPENSE_AGENT_EXTRACTOR_MODEL": "model",
                "EXPENSE_AGENT_EXTRACTOR_PARAMETERS_JSON": '{"response":{"format":"json"}}',
            },
            "must be JSON scalar values",
        ),
        (
            {
                "EXPENSE_AGENT_EXTRACTOR_MODE": "http_json",
                "EXPENSE_AGENT_EXTRACTOR_ENDPOINT": "https://extractor.example.test/v1",
                "EXPENSE_AGENT_EXTRACTOR_PROVIDER": "provider",
                "EXPENSE_AGENT_EXTRACTOR_MODEL": "model",
                "EXPENSE_AGENT_EXTRACTOR_PARAMETERS_JSON": '{"seed":1,"seed":2}',
            },
            "must be strict JSON",
        ),
        (
            {
                "EXPENSE_AGENT_EXTRACTOR_MODE": "http_json",
                "EXPENSE_AGENT_EXTRACTOR_ENDPOINT": "https://extractor.example.test/v1",
                "EXPENSE_AGENT_EXTRACTOR_PROVIDER": "provider",
                "EXPENSE_AGENT_EXTRACTOR_MODEL": "model",
                "EXPENSE_AGENT_EXTRACTOR_PARAMETERS_JSON": '{"temperature":NaN}',
            },
            "must be strict JSON",
        ),
        (
            {
                "EXPENSE_AGENT_EXTRACTOR_MODE": "http_json",
                "EXPENSE_AGENT_EXTRACTOR_ENDPOINT": "https://extractor.example.test/v1",
                "EXPENSE_AGENT_EXTRACTOR_PROVIDER": "provider",
                "EXPENSE_AGENT_EXTRACTOR_MODEL": "model",
                "EXPENSE_AGENT_EXTRACTOR_API_KEY": "   ",
            },
            "must not be blank when set",
        ),
    ),
)
def test_extractor_settings_fail_fast_on_invalid_values(
    monkeypatch,
    tmp_path,
    overrides,
    message,
) -> None:
    _configure_valid_environment(monkeypatch, tmp_path)
    for name, value in overrides.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(SecurityConfigurationError, match=message):
        ReviewWebSettings.from_environment()


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
