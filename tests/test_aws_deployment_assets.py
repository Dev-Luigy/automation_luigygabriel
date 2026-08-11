import os
import runpy
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[1]
AWS_DEPLOY = PROJECT_ROOT / "deploy" / "aws"


def test_lambda_requirements_are_exact_pins_present_in_uv_lock() -> None:
    lock = tomllib.loads((PROJECT_ROOT / "uv.lock").read_text(encoding="utf-8"))
    locked_versions = {
        (package["name"], package["version"])
        for package in lock["package"]
        if "version" in package
    }
    requirements = [
        line.strip()
        for line in (AWS_DEPLOY / "requirements.lock").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    assert requirements
    assert "mangum==0.21.0" in requirements
    for requirement in requirements:
        name, version = requirement.split("==", 1)
        assert (name, version) in locked_versions


def test_sam_sandbox_keeps_secrets_out_of_source_and_marks_safety_boundary() -> None:
    template = (AWS_DEPLOY / "template.yaml").read_text(encoding="utf-8")

    assert template.count("NoEcho: true") == 2
    assert "Encrypted: true" in template
    assert template.count("DeletionPolicy: Retain") == 1
    assert "EXPENSE_AGENT_SQLITE_JOURNAL_MODE: DELETE" in template
    assert "ReservedConcurrentExecutions: 4" in template
    assert "ASSESSMENT SANDBOX ONLY" in template
    assert "password_hash\":\"${ReviewerPasswordHash}" in template
    assert "Runtime: python3.12" in template
    assert "Handler: expense_agent.presentation.lambda_handler.handler" in template
    assert "CodeUri: .build/lambda" in template
    assert os.access(AWS_DEPLOY / "deploy.sh", os.X_OK)


def test_deploy_script_has_valid_bash_syntax() -> None:
    subprocess.run(
        ["bash", "-n", str(AWS_DEPLOY / "deploy.sh")],
        check=True,
        capture_output=True,
        text=True,
    )


def test_build_preparation_copies_only_runtime_source_and_locked_requirements() -> None:
    subprocess.run(
        [sys.executable, str(AWS_DEPLOY / "prepare_build.py")],
        check=True,
        capture_output=True,
        text=True,
    )
    build_root = AWS_DEPLOY / ".build" / "lambda"

    assert (build_root / "expense_agent" / "presentation" / "lambda_handler.py").is_file()
    assert (build_root / "requirements.txt").read_bytes() == (
        AWS_DEPLOY / "requirements.lock"
    ).read_bytes()
    assert not (build_root / ".venv").exists()


def test_seed_helper_requires_a_bare_https_origin() -> None:
    namespace = runpy.run_path(str(AWS_DEPLOY / "seed_demo.py"))
    validate = namespace["_validated_base_url"]

    assert validate("https://abc.execute-api.sa-east-1.amazonaws.com/") == (
        "https://abc.execute-api.sa-east-1.amazonaws.com"
    )
    with pytest.raises(SystemExit, match="HTTPS origin"):
        validate("http://example.com/api")
