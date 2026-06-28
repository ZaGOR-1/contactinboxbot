"""Rate limiting for Telegram inbox messages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.models import User
from app.db.repositories import MessageRepository


logger = get_logger(__name__)

RATE_LIMIT_WINDOW_SECONDS = 60


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    used: int
    retry_after_seconds: int


class RateLimitService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        self.messages = MessageRepository(session)
        self.settings = settings or get_settings()

    async def check_user_message_limit(self, user: User) -> RateLimitResult:
        limit = self.settings.rate_limit_messages_per_minute
        since = datetime.now(UTC) - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
        used = await self.messages.count_recent_incoming_by_user(
            user_id=user.id,
            since=since,
        )
        allowed = used < limit
        retry_after_seconds = 0 if allowed else RATE_LIMIT_WINDOW_SECONDS

        if not allowed:
            logger.warning(
                "Telegram message rate limit exceeded",
                extra={
                    "telegram_user_id": user.telegram_id,
                    "user_id": user.id,
                    "limit": limit,
                    "used": used,
                    "window_seconds": RATE_LIMIT_WINDOW_SECONDS,
                },
            )

        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            used=used,
            retry_after_seconds=retry_after_seconds,
        )
