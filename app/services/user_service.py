"""User-related business logic."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.repositories import UserRepository


class TelegramUserLike(Protocol):
    id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    language_code: str | None


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.users = UserRepository(session)

    async def upsert_from_telegram(
        self,
        telegram_user: TelegramUserLike,
        *,
        touch_last_message_at: bool = False,
    ) -> User:
        last_message_at = datetime.now(UTC) if touch_last_message_at else None
        return await self.users.create_or_update_from_telegram(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
            language_code=telegram_user.language_code,
            last_message_at=last_message_at,
        )

    async def is_blocked(self, telegram_user: TelegramUserLike) -> bool:
        user = await self.users.get_by_telegram_id(telegram_user.id)
        return bool(user and user.is_blocked)
