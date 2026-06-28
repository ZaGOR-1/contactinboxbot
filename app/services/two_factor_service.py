"""Telegram two-factor authentication service."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings, is_placeholder_config_value
from app.core.logging import get_logger
from app.core.security import hash_password, verify_password
from app.db.models import AdminUser
from app.db.repositories import TwoFactorCodeRepository


logger = get_logger(__name__)

TWO_FACTOR_CODE_MINUTES = 5


@dataclass(frozen=True)
class TwoFactorVerificationResult:
    success: bool
    message: str = "Invalid or expired code."


class TwoFactorService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        self.codes = TwoFactorCodeRepository(session)
        self.settings = settings or get_settings()

    async def create_and_send_code(self, admin_user: AdminUser) -> None:
        code = self.generate_code()
        now = datetime.now(UTC)
        await self.codes.mark_active_used_for_admin(admin_user_id=admin_user.id, used_at=now)
        expires_at = now + timedelta(minutes=TWO_FACTOR_CODE_MINUTES)
        await self.codes.create(
            admin_user_id=admin_user.id,
            code_hash=hash_password(code),
            expires_at=expires_at,
        )
        await self.send_code(code=code, username=admin_user.username)

    async def verify_code(
        self,
        *,
        admin_user_id: int,
        submitted_code: str,
    ) -> TwoFactorVerificationResult:
        normalized_code = submitted_code.strip()
        if not normalized_code:
            return TwoFactorVerificationResult(success=False)

        active_code = await self.codes.get_active_for_admin(
            admin_user_id=admin_user_id,
            now=datetime.now(UTC),
        )
        if active_code is None:
            return TwoFactorVerificationResult(success=False)

        if not verify_password(normalized_code, active_code.code_hash):
            return TwoFactorVerificationResult(success=False)

        await self.codes.mark_used(active_code.id, datetime.now(UTC))
        return TwoFactorVerificationResult(success=True, message="OK")

    def generate_code(self) -> str:
        return f"{secrets.randbelow(1_000_000):06d}"

    async def send_code(self, *, code: str, username: str) -> None:
        admin_telegram_id = self.settings.admin_telegram_id
        if is_placeholder_config_value(admin_telegram_id):
            raise RuntimeError("ADMIN_TELEGRAM_ID is not configured.")

        token = self.settings.telegram_bot_token.get_secret_value()
        if is_placeholder_config_value(token):
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")

        try:
            from aiogram import Bot
        except (ImportError, ModuleNotFoundError) as exc:
            raise RuntimeError(
                "Telegram dependencies are not installed. Run: pip install -r requirements.txt"
            ) from exc

        bot = Bot(token=token)
        try:
            await bot.send_message(
                chat_id=admin_telegram_id,
                text=(
                    "Telegram Inbox Bot login code\n\n"
                    f"Admin: {username}\n"
                    f"Code: {code}\n"
                    f"Valid for {TWO_FACTOR_CODE_MINUTES} minutes."
                ),
            )
        finally:
            await bot.session.close()
