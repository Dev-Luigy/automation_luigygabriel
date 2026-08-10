"""Interactive helper for generating a reviewer password hash."""

from getpass import getpass

from expense_agent.presentation.security import hash_password


def run() -> None:
    password = getpass("Reviewer password: ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    print(hash_password(password))


if __name__ == "__main__":
    run()
