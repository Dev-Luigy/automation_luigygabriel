"""Create a minimal, deterministic SAM source tree outside the Git artifact set."""

from __future__ import annotations

import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AWS_DIRECTORY = PROJECT_ROOT / "deploy" / "aws"
BUILD_ROOT = AWS_DIRECTORY / ".build"
LAMBDA_SOURCE = BUILD_ROOT / "lambda"


def main() -> None:
    if LAMBDA_SOURCE.exists():
        shutil.rmtree(LAMBDA_SOURCE)
    LAMBDA_SOURCE.mkdir(parents=True)
    shutil.copytree(PROJECT_ROOT / "src" / "expense_agent", LAMBDA_SOURCE / "expense_agent")
    shutil.copy2(AWS_DIRECTORY / "requirements.lock", LAMBDA_SOURCE / "requirements.txt")
    print(f"Prepared Lambda source at {LAMBDA_SOURCE}")


if __name__ == "__main__":
    main()
