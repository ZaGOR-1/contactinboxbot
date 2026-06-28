"""Telegram API helper services."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from app.core.config import Settings, get_settings, is_placeholder_config_value
from app.core.logging import get_logger
from app.db.models import Message, User


logger = get_logger(__name__)

MAX_NOTIFICATION_TEXT_LENGTH = 3000


class BotLike(Protocol):
    async def send_message(self, chat_id: int | str, text: str) -> object:
        ...


class TelegramService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def notify_admin_about_new_message(
        self,
        *,
        bot: BotLike,
        user: User,
        message: Message,
    ) -> None:
        admin_telegram_id = self.settings.admin_telegram_id
        if is_placeholder_config_value(admin_telegram_id):
            logger.warning("ADMIN_TELEGRAM_ID is not configured; admin notification skipped")
            return

        notification_text = self.build_new_message_notification(user=user, message=message)
        await bot.send_message(chat_id=admin_telegram_id, text=notification_text)

    async def send_text_to_user(self, *, user: User, text: str) -> int | None:
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
            sent_message = await bot.send_message(chat_id=user.telegram_id, text=text)
            return getattr(sent_message, "message_id", None)
        finally:
            await bot.session.close()

    def build_new_message_notification(self, *, user: User, message: Message) -> str:
        user_name = self._display_name(user)
        username = f"@{user.username}" if user.username else "-"
        message_text = self._truncate(message.text)
        created_at = self._format_datetime(message.created_at)
        user_url = f"{self.settings.admin_panel_base_url}/users/{user.id}"

        return (
            "Нове повідомлення в Telegram Inbox Bot\n\n"
            f"Користувач: {user_name}\n"
            f"Username: {username}\n"
            f"Telegram ID: {user.telegram_id}\n"
            f"Дата: {created_at}\n\n"
            f"Текст:\n{message_text}\n\n"
            f"Адмінка:\n{user_url}"
        )

    def _display_name(self, user: User) -> str:
        parts = [part for part in [user.first_name, user.last_name] if part]
        if parts:
            return " ".join(parts)
        if user.username:
            return f"@{user.username}"
        return f"Telegram user {user.telegram_id}"

    def _truncate(self, text: str) -> str:
        if len(text) <= MAX_NOTIFICATION_TEXT_LENGTH:
            return text
        return f"{text[:MAX_NOTIFICATION_TEXT_LENGTH]}..."

    def _format_datetime(self, value: datetime | None) -> str:
        if value is None:
            value = datetime.now(UTC)
        return value.isoformat(sep=" ", timespec="seconds")
