"""Centralized logging configuration."""

import logging
import logging.config
from collections.abc import MutableMapping
from typing import Any

from app.core.config import Settings


SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "database_url",
    "password",
    "secret",
    "secret_key",
    "session",
    "telegram_bot_token",
    "token",
}


class RedactSecretsFilter(logging.Filter):
    """Best-effort redaction for accidental secret values in log records."""

    redacted_value = "[REDACTED]"

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._redact(record.msg)
        if record.args:
            record.args = self._redact(record.args)
        return True

    def _redact(self, value: Any) -> Any:
        if isinstance(value, MutableMapping):
            return {
                key: self.redacted_value if self._is_sensitive_key(key) else self._redact(item)
                for key, item in value.items()
            }
        if isinstance(value, tuple):
            return tuple(self._redact(item) for item in value)
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        return value

    def _is_sensitive_key(self, key: object) -> bool:
        normalized = str(key).lower()
        return any(marker in normalized for marker in SENSITIVE_KEYS)


def configure_logging(settings: Settings) -> None:
    """Configure application logging without exposing secret values."""

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "redact_secrets": {
                    "()": RedactSecretsFilter,
                },
            },
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "filters": ["redact_secrets"],
                },
            },
            "root": {
                "level": settings.log_level,
                "handlers": ["console"],
            },
            "loggers": {
                "aiogram": {"level": settings.log_level},
                "sqlalchemy.engine": {"level": "WARNING"},
                "uvicorn.access": {"level": "INFO"},
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
