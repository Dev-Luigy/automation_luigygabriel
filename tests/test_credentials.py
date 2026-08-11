import io

import pytest

from expense_agent.presentation import credentials
from expense_agent.presentation.security import verify_password


def test_hash_password_cli_can_read_automation_secret_from_stdin(monkeypatch, capsys) -> None:
    monkeypatch.setattr(credentials.sys, "stdin", io.StringIO("deployment-secret\n"))

    credentials.run(["--password-stdin"])

    encoded = capsys.readouterr().out.strip()
    assert verify_password("deployment-secret", encoded)


def test_hash_password_cli_rejects_empty_stdin(monkeypatch) -> None:
    monkeypatch.setattr(credentials.sys, "stdin", io.StringIO(""))

    with pytest.raises(SystemExit, match="Password must not be empty"):
        credentials.run(["--password-stdin"])
