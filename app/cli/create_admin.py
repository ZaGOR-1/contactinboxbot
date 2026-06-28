"""Create the first admin user for the private web admin panel."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from dataclasses import dataclass

from app.core.security import hash_password


MIN_PASSWORD_LENGTH = 8


@dataclass(frozen=True)
class AdminInput:
    username: str
    password: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli.create_admin",
        description="Create the first admin user for Telegram Inbox Bot.",
    )
    parser.add_argument(
        "--username",
        help="Admin username. If omitted, the command prompts for it.",
    )
    parser.add_argument(
        "--allow-additional",
        action="store_true",
        help="Allow creating an additional admin when one already exists.",
    )
    parser.add_argument(
        "--replace-password",
        action="store_true",
        help="Replace password for an existing username instead of creating a new admin.",
    )
    return parser


def prompt_admin_input(username: str | None) -> AdminInput:
    if not sys.stdin.isatty():
        raise RuntimeError(
            "Interactive terminal is required because the password is entered securely."
        )

    resolved_username = (username or input("Username: ")).strip()
    if not resolved_username:
        raise ValueError("Username cannot be empty.")

    password = getpass.getpass("Password: ")
    repeated_password = getpass.getpass("Repeat password: ")

    if password != repeated_password:
        raise ValueError("Passwords do not match.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")

    return AdminInput(username=resolved_username, password=password)


async def create_or_update_admin(
    *,
    admin_input: AdminInput,
    allow_additional: bool,
    replace_password: bool,
) -> str:
    try:
        from sqlalchemy.exc import IntegrityError

        from app.db.database import get_session_maker
        from app.db.repositories import AdminUserRepository
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            "Database dependencies are not installed. Run: pip install -r requirements.txt"
        ) from exc

    session_maker = get_session_maker()
    async with session_maker() as session:
        repo = AdminUserRepository(session)
        existing_count = await repo.count()
        existing_user = await repo.get_by_username(admin_input.username)

        if replace_password:
            if existing_user is None:
                raise ValueError(
                    f"Admin user '{admin_input.username}' does not exist; cannot replace password."
                )
            await repo.update_password_hash(
                existing_user.id,
                hash_password(admin_input.password),
            )
            await session.commit()
            return f"Password replaced for admin user '{admin_input.username}'."

        if existing_count > 0 and not allow_additional:
            raise ValueError(
                "An admin user already exists. Refusing to create another without "
                "--allow-additional."
            )

        if existing_user is not None:
            raise ValueError(
                f"Admin user '{admin_input.username}' already exists. Use "
                "--replace-password to update its password."
            )

        try:
            await repo.create(
                username=admin_input.username,
                password_hash=hash_password(admin_input.password),
            )
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise ValueError(
                f"Admin user '{admin_input.username}' already exists."
            ) from exc

    return f"Admin user '{admin_input.username}' created."


async def async_main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        admin_input = prompt_admin_input(args.username)
        message = await create_or_update_admin(
            admin_input=admin_input,
            allow_additional=args.allow_additional,
            replace_password=args.replace_password,
        )
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(message)
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
