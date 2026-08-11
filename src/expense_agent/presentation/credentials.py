"""Interactive helper for generating a reviewer password hash."""

import argparse
import sys
from getpass import getpass

from expense_agent.presentation.security import hash_password


def run(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate an Expense Agent PBKDF2 reviewer password hash.",
    )
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="read one password line from standard input for deployment automation",
    )
    arguments = parser.parse_args(argv)
    if arguments.password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
    else:
        password = getpass("Reviewer password: ")
        confirmation = getpass("Confirm password: ")
        if password != confirmation:
            raise SystemExit("Passwords do not match.")
    if not password:
        raise SystemExit("Password must not be empty.")
    print(hash_password(password))


if __name__ == "__main__":
    run()
