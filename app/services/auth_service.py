"""Authentication service for the private web admin."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import verify_password
from app.db.models import AdminUser
from app.db.repositories import AdminUserRepository, LoginAttemptRepository


logger = get_logger(__name__)

MAX_FAILED_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15


@dataclass(frozen=True)
class AuthenticationResult:
    success: bool
    admin_user: AdminUser | None = None
    locked: bool = False
    message: str = "Invalid username or password."


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.admin_users = AdminUserRepository(session)
        self.login_attempts = LoginAttemptRepository(session)

    async def authenticate(
        self,
        *,
        username: str,
        password: str,
        ip_address: str,
    ) -> AuthenticationResult:
        if await self.is_ip_locked(ip_address):
            logger.warning("Login blocked by brute-force protection", extra={"ip_address": ip_address})
            await self.login_attempts.create(
                ip_address=ip_address,
                username=username,
                success=False,
            )
            return AuthenticationResult(
                success=False,
                locked=True,
                message="Too many failed login attempts. Try again later.",
            )

        admin_user = await self.admin_users.get_by_username(username)
        password_ok = bool(
            admin_user
            and admin_user.is_active
            and verify_password(password, admin_user.password_hash)
        )

        await self.login_attempts.create(
            ip_address=ip_address,
            username=username,
            success=password_ok,
        )

        if not password_ok:
            return AuthenticationResult(success=False)

        return AuthenticationResult(success=True, admin_user=admin_user, message="OK")

    async def is_ip_locked(self, ip_address: str) -> bool:
        since = datetime.now(UTC) - timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
        failed_count = await self.login_attempts.count_failed_since(
            ip_address=ip_address,
            since=since,
        )
        return failed_count >= MAX_FAILED_LOGIN_ATTEMPTS

    async def mark_login_success(self, admin_user_id: int) -> None:
        await self.admin_users.update_last_login(admin_user_id, datetime.now(UTC))
