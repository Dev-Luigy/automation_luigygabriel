import json
from datetime import UTC, datetime, timedelta

import pytest

from expense_agent.presentation.security import (
    BasicAuthenticator,
    CsrfProtector,
    PrincipalCapability,
    PrincipalRole,
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
    assert principal.email == "reviewer@example.com"
    assert principal.roles == frozenset({PrincipalRole.SUBMITTER, PrincipalRole.REVIEWER})
    assert principal.has_role("submitter")
    assert principal.has_role(PrincipalRole.REVIEWER)
    assert principal.can("submit")
    assert principal.can(PrincipalCapability.REVIEW)
    assert not principal.can("audit")
    assert not principal.can("unknown")
    assert not principal.has_role("admin")
    assert authenticator.authenticate("reviewer", "wrong") is None
    assert authenticator.authenticate("forged-user", "correct horse") is None


def test_explicit_roles_are_immutable_and_grant_only_closed_capabilities() -> None:
    password_hash = hash_password("correct horse", iterations=100_000)
    credential = ReviewerCredential(
        username="auditor",
        reviewer_id="directory:auditor-8",
        email="auditor@example.com",
        display_name="Finance Auditor",
        password_hash=password_hash,
        roles=["auditor"],
    )

    principal = BasicAuthenticator((credential,)).authenticate("auditor", "correct horse")

    assert principal is not None
    assert isinstance(principal.roles, frozenset)
    assert principal.roles == frozenset({PrincipalRole.AUDITOR})
    assert principal.can("audit")
    assert not principal.can("review")
    assert not principal.can("submit")
    assert password_hash not in repr(credential)
    assert password_hash not in repr(principal)


def test_admin_role_can_use_every_assessment_capability_without_aliasing_roles() -> None:
    credential = ReviewerCredential(
        username="admin",
        reviewer_id="directory:admin-1",
        email="admin@example.com",
        display_name="Expense Administrator",
        password_hash=hash_password("correct horse", iterations=100_000),
        roles=frozenset({PrincipalRole.ADMIN}),
    )

    principal = credential.principal

    assert all(principal.can(capability) for capability in PrincipalCapability)
    assert principal.has_role("admin")
    assert not principal.has_role("reviewer")


def test_credential_loader_accepts_legacy_and_explicit_role_shapes() -> None:
    password_hash = hash_password("correct horse", iterations=100_000)
    legacy = {
        "username": "legacy",
        "reviewer_id": "directory:legacy-1",
        "email": "legacy@example.com",
        "display_name": "Legacy Reviewer",
        "password_hash": password_hash,
    }
    auditor = {
        "username": "auditor",
        "reviewer_id": "directory:auditor-1",
        "email": "auditor@example.com",
        "display_name": "Finance Auditor",
        "password_hash": password_hash,
        "roles": ["auditor"],
    }

    credentials = load_reviewer_credentials(json.dumps([legacy, auditor]))

    assert credentials[0].roles == frozenset({PrincipalRole.SUBMITTER, PrincipalRole.REVIEWER})
    assert credentials[1].roles == frozenset({PrincipalRole.AUDITOR})


@pytest.mark.parametrize(
    ("roles_fragment", "message"),
    (
        ('"roles":[]', "must not be empty"),
        ('"roles":["owner"]', "unknown role"),
        ('"roles":["reviewer","reviewer"]', "must not contain duplicates"),
        ('"roles":"reviewer"', "must be a JSON list"),
        ('"roles":[1]', "must contain only strings"),
    ),
)
def test_credential_loader_rejects_invalid_explicit_roles(roles_fragment, message) -> None:
    password_hash = hash_password("correct horse", iterations=100_000)
    raw = (
        '[{"username":"reviewer","reviewer_id":"directory:reviewer-7",'
        '"email":"reviewer@example.com","display_name":"Finance Reviewer",'
        f'"password_hash":"{password_hash}",{roles_fragment}}}]'
    )

    with pytest.raises(SecurityConfigurationError, match=message):
        load_reviewer_credentials(raw)


def test_credential_loader_rejects_arbitrary_and_duplicate_json_fields() -> None:
    password_hash = hash_password("correct horse", iterations=100_000)
    unexpected = (
        '[{"username":"reviewer","reviewer_id":"directory:reviewer-7",'
        '"email":"reviewer@example.com","display_name":"Finance Reviewer",'
        f'"password_hash":"{password_hash}","roles":["reviewer"],"team":"finance"}}]'
    )
    duplicate = (
        '[{"username":"reviewer","username":"forged",'
        '"reviewer_id":"directory:reviewer-7","email":"reviewer@example.com",'
        '"display_name":"Finance Reviewer",'
        f'"password_hash":"{password_hash}"}}]'
    )

    with pytest.raises(SecurityConfigurationError, match="exactly"):
        load_reviewer_credentials(unexpected)
    with pytest.raises(SecurityConfigurationError, match="JSON is invalid"):
        load_reviewer_credentials(duplicate)


def test_authenticator_rejects_duplicate_canonical_reviewer_id() -> None:
    first = _credential()
    second = ReviewerCredential(
        username="another-reviewer",
        reviewer_id=f" {first.reviewer_id} ",
        email="another-reviewer@example.com",
        display_name="Another Finance Reviewer",
        password_hash=hash_password("another password", iterations=100_000),
    )

    with pytest.raises(SecurityConfigurationError, match="duplicate reviewer_id"):
        BasicAuthenticator((first, second))


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
