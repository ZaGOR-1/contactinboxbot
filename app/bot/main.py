"""Telegram bot entrypoint."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from app.core.config import get_settings, is_placeholder_config_value
from app.core.logging import configure_logging, get_logger


logger = get_logger(__name__)


def create_dispatcher() -> Any:
    from aiogram import Dispatcher

    from app.bot.handlers import router
    from app.bot.middlewares import DbSessionMiddleware

    dispatcher = Dispatcher()
    dispatcher.message.middleware(DbSessionMiddleware())
    dispatcher.include_router(router)
    return dispatcher


def create_bot() -> Any:
    from aiogram import Bot

    settings = get_settings()
    token = settings.telegram_bot_token.get_secret_value()
    if is_placeholder_config_value(token):
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")
    return Bot(token=token)


async def run_bot() -> None:
    settings = get_settings()
    configure_logging(settings)

    dispatcher = create_dispatcher()
    bot = create_bot()

    logger.info("Starting Telegram bot polling")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot)
    finally:
        from app.db.database import dispose_engine

        await bot.session.close()
        await dispose_engine()


def main() -> int:
    try:
        asyncio.run(run_bot())
    except (ImportError, ModuleNotFoundError) as exc:
        print(
            f"Bot dependencies are not installed: {exc}. "
            "Run: pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1
    except RuntimeError as exc:
        print(f"Bot startup error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
