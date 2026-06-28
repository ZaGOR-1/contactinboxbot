"""Message-related business logic."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message, MessageDirection, MessageStatus, User
from app.db.repositories import MessageRepository


class MessageService:
    def __init__(self, session: AsyncSession) -> None:
        self.messages = MessageRepository(session)

    async def save_incoming_text(
        self,
        *,
        user: User,
        text: str,
        telegram_message_id: int | None,
    ) -> Message:
        return await self.messages.create(
            user_id=user.id,
            direction=MessageDirection.incoming,
            text=text,
            status=MessageStatus.new,
            telegram_message_id=telegram_message_id,
        )

    async def save_outgoing_text(
        self,
        *,
        user: User,
        text: str,
        status: MessageStatus,
        telegram_message_id: int | None = None,
        error_text: str | None = None,
    ) -> Message:
        return await self.messages.create(
            user_id=user.id,
            direction=MessageDirection.outgoing,
            text=text,
            status=status,
            telegram_message_id=telegram_message_id,
            error_text=error_text,
        )
