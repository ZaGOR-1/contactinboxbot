"""Telegram bot message handlers."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.message_service import MessageService
from app.services.rate_limit_service import RateLimitService
from app.services.telegram_service import TelegramService
from app.services.user_service import UserService
from app.core.logging import get_logger


router = Router(name="telegram_inbox_bot")
logger = get_logger(__name__)

WELCOME_TEXT = (
    "Вітаю! Напишіть сюди повідомлення власнику сайту. "
    "Він побачить його в приватній адмінці та відповість вам через цього бота."
)

MESSAGE_RECEIVED_TEXT = "Дякую, повідомлення отримано. Відповідь прийде тут, у цьому боті."
BLOCKED_TEXT = "Надсилання повідомлень наразі недоступне."
RATE_LIMIT_TEXT = "Забагато повідомлень за короткий час. Будь ласка, зачекайте хвилину."
UNSUPPORTED_ATTACHMENT_TEXT = (
    "Файли поки не підтримуються. Напишіть, будь ласка, повідомлення текстом."
)


@router.message(CommandStart())
async def handle_start(message: Message, db_session: AsyncSession) -> None:
    if message.from_user is None:
        return

    user_service = UserService(db_session)
    user = await user_service.upsert_from_telegram(message.from_user)

    if user.is_blocked:
        await message.answer(BLOCKED_TEXT)
        return

    await message.answer(WELCOME_TEXT)


@router.message(F.text)
async def handle_text_message(
    message: Message,
    db_session: AsyncSession,
    bot: Bot,
) -> None:
    if message.from_user is None or message.text is None:
        return

    user_service = UserService(db_session)
    user = await user_service.upsert_from_telegram(
        message.from_user,
        touch_last_message_at=True,
    )

    if user.is_blocked:
        await message.answer(BLOCKED_TEXT)
        return

    rate_limit = await RateLimitService(db_session).check_user_message_limit(user)
    if not rate_limit.allowed:
        await message.answer(RATE_LIMIT_TEXT)
        return

    message_service = MessageService(db_session)
    saved_message = await message_service.save_incoming_text(
        user=user,
        text=message.text,
        telegram_message_id=message.message_id,
    )

    try:
        await TelegramService().notify_admin_about_new_message(
            bot=bot,
            user=user,
            message=saved_message,
        )
    except Exception:
        logger.exception(
            "Failed to send admin notification",
            extra={
                "telegram_user_id": user.telegram_id,
                "user_id": user.id,
                "message_id": saved_message.id,
            },
        )

    await message.answer(MESSAGE_RECEIVED_TEXT)


@router.message()
async def handle_unsupported_message(message: Message, db_session: AsyncSession) -> None:
    if message.from_user is None:
        return

    user_service = UserService(db_session)
    user = await user_service.upsert_from_telegram(message.from_user)

    if user.is_blocked:
        await message.answer(BLOCKED_TEXT)
        return

    await message.answer(UNSUPPORTED_ATTACHMENT_TEXT)
