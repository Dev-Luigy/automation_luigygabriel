from datetime import UTC, datetime, timedelta

import pytest

from expense_agent.presentation.security import (
    BasicAuthenticator,
    CsrfProtector,
    ReviewerCredential,
    SecurityConfigurationError,
    hash_password,
    load_reviewer_credentials,
    verify_password,
)


def _credential() -> ReviewerCredential:
    return ReviewerCredential(
        username="reviewer",
        reviewer_id="directory:reviewer-7",
        email="reviewer@example.com",
        display_name="Finance Reviewer",
        password_hash=hash_password("correct horse", iterations=100_000),
    )


def test_password_hash_is_salted_and_verifiable() -> None:
    first = hash_password("correct horse", iterations=100_000)
    second = hash_password("correct horse", iterations=100_000)

    assert first != second
    assert "correct horse" not in first
    assert verify_password("correct horse", first)
    assert not verify_password("wrong password", first)
    assert not verify_password("correct horse", "malformed")


def test_authenticator_returns_only_configured_canonical_identity() -> None:
    credential = _credential()
    authenticator = BasicAuthenticator((credential,))

    principal = authenticator.authenticate("reviewer", "correct horse")

    assert principal is not None
    assert principal.reviewer_id == "directory:reviewer-7"
    assert authenticator.authenticate("reviewer", "wrong") is None
    assert authenticator.authenticate("forged-user", "correct horse") is None


def test_csrf_token_is_bound_to_identity_signature_and_expiry() -> None:
    now = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    protector = CsrfProtector("a" * 32, ttl=timedelta(minutes=15))
    token = protector.issue("directory:reviewer-7", now=now)

    assert protector.verify(token, "directory:reviewer-7", now=now)
    assert not protector.verify(token, "directory:another", now=now)
    assert not protector.verify(token + "tampered", "directory:reviewer-7", now=now)
    assert not protector.verify(
        token,
        "directory:reviewer-7",
        now=now + timedelta(minutes=16),
    )


def test_security_configuration_is_strict() -> None:
    with pytest.raises(SecurityConfigurationError, match="32 bytes"):
        CsrfProtector("too-short")
    with pytest.raises(SecurityConfigurationError, match="must be a list"):
        load_reviewer_credentials("{}")
    with pytest.raises(SecurityConfigurationError, match="exactly"):
        load_reviewer_credentials('[{"username":"reviewer"}]')
    malformed = _credential()
    malformed = ReviewerCredential(
        username=malformed.username,
        reviewer_id=malformed.reviewer_id,
        email=malformed.email,
        display_name=malformed.display_name,
        password_hash="not-a-password-hash",
    )
    with pytest.raises(SecurityConfigurationError, match="invalid PBKDF2"):
        BasicAuthenticator((malformed,))
