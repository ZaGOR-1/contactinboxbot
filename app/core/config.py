"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

try:
    from pydantic import Field, SecretStr, field_validator, model_validator
    from pydantic_settings import BaseSettings, SettingsConfigDict
except (ImportError, ModuleNotFoundError):
    BaseSettings = object  # type: ignore[assignment]
    Field = None  # type: ignore[assignment]
    SecretStr = None  # type: ignore[assignment]
    SettingsConfigDict = None  # type: ignore[assignment]
    field_validator = None  # type: ignore[assignment]
    model_validator = None  # type: ignore[assignment]
    PYDANTIC_AVAILABLE = False
else:
    PYDANTIC_AVAILABLE = True


AppEnv = Literal["development", "dev", "local", "test", "production"]
SameSitePolicy = Literal["lax", "strict", "none"]


class PlainSecret:
    """Small fallback for pydantic's SecretStr when dependencies are absent."""

    def __init__(self, value: str) -> None:
        self._value = value

    def get_secret_value(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "**********"

    __str__ = __repr__


def _read_dotenv(path: Path = Path(".env")) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _env_value(name: str, default: str | None = None) -> str:
    dotenv_values = _read_dotenv()
    if name in os.environ:
        return os.environ[name]
    if name in dotenv_values:
        return dotenv_values[name]
    if default is not None:
        return default
    raise RuntimeError(f"Missing required environment variable: {name}")


def _env_bool(name: str, default: bool) -> bool:
    value = _env_value(name, str(default)).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _normalize_app_env(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"development", "dev", "local", "test", "production"}:
        return normalized
    raise ValueError("APP_ENV must be development, dev, local, test, or production")


def _validate_sqlite_is_not_production(app_env: str, database_url: str) -> None:
    if app_env == "production" and database_url.startswith("sqlite"):
        raise ValueError("SQLite is allowed only outside production")


if PYDANTIC_AVAILABLE:

    class Settings(BaseSettings):  # type: ignore[misc]
        """Typed runtime configuration.

        Values are loaded from environment variables and optionally from a local
        `.env` file. Secret values use `SecretStr` so accidental repr/logging
        does not reveal their contents.
        """

        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=True,
            extra="ignore",
        )

        app_env: AppEnv = Field(default="production", alias="APP_ENV")
        app_name: str = Field(default="Telegram Inbox Bot", alias="APP_NAME")
        app_version: str = Field(default="1.0.0", alias="APP_VERSION")

        database_url: SecretStr = Field(alias="DATABASE_URL")

        telegram_bot_token: SecretStr = Field(alias="TELEGRAM_BOT_TOKEN")
        admin_telegram_id: str = Field(alias="ADMIN_TELEGRAM_ID")

        secret_key: SecretStr = Field(alias="SECRET_KEY")
        session_cookie_name: str = Field(
            default="telegram_inbox_session",
            alias="SESSION_COOKIE_NAME",
        )
        session_cookie_secure: bool = Field(default=True, alias="SESSION_COOKIE_SECURE")
        session_cookie_httponly: bool = Field(default=True, alias="SESSION_COOKIE_HTTPONLY")
        session_cookie_samesite: SameSitePolicy = Field(
            default="lax",
            alias="SESSION_COOKIE_SAMESITE",
        )

        admin_panel_base_url: str = Field(
            default="https://admintextbot.hotzagor.tech",
            alias="ADMIN_PANEL_BASE_URL",
        )

        enable_telegram_2fa: bool = Field(default=True, alias="ENABLE_TELEGRAM_2FA")
        enable_ip_allowlist: bool = Field(default=False, alias="ENABLE_IP_ALLOWLIST")
        allowed_admin_ips: str = Field(default="", alias="ALLOWED_ADMIN_IPS")
        trusted_proxy_ips: str = Field(default="127.0.0.1,::1", alias="TRUSTED_PROXY_IPS")

        rate_limit_messages_per_minute: int = Field(
            default=5,
            ge=1,
            alias="RATE_LIMIT_MESSAGES_PER_MINUTE",
        )

        log_level: str = Field(default="INFO", alias="LOG_LEVEL")

        @field_validator("app_env", mode="before")
        @classmethod
        def normalize_app_env(cls, value: str) -> str:
            return _normalize_app_env(str(value))

        @field_validator("session_cookie_samesite", mode="before")
        @classmethod
        def normalize_samesite(cls, value: str) -> str:
            return str(value).strip().lower()

        @field_validator("log_level", mode="before")
        @classmethod
        def normalize_log_level(cls, value: str) -> str:
            return str(value).strip().upper()

        @field_validator("admin_panel_base_url")
        @classmethod
        def trim_trailing_slash(cls, value: str) -> str:
            return value.rstrip("/")

        @model_validator(mode="after")
        def validate_production_database(self) -> "Settings":
            _validate_sqlite_is_not_production(
                self.app_env,
                self.database_url.get_secret_value(),
            )
            return self

        @property
        def is_production(self) -> bool:
            return self.app_env == "production"

        @property
        def is_development(self) -> bool:
            return self.app_env in {"development", "dev", "local"}

        @property
        def docs_url(self) -> str | None:
            return None if self.is_production else "/docs"

        @property
        def redoc_url(self) -> str | None:
            return None if self.is_production else "/redoc"

        @property
        def openapi_url(self) -> str | None:
            return None if self.is_production else "/openapi.json"

        @property
        def allowed_admin_ip_list(self) -> list[str]:
            return [
                ip.strip()
                for ip in self.allowed_admin_ips.split(",")
                if ip.strip()
            ]

        @property
        def trusted_proxy_ip_list(self) -> list[str]:
            return [
                ip.strip()
                for ip in self.trusted_proxy_ips.split(",")
                if ip.strip()
            ]

        def safe_summary(self) -> dict[str, object]:
            return _safe_summary(self)

else:

    @dataclass(frozen=True)
    class Settings:
        """Fallback settings loader used before dependencies are installed."""

        app_env: str
        app_name: str
        app_version: str
        database_url: PlainSecret
        telegram_bot_token: PlainSecret
        admin_telegram_id: str
        secret_key: PlainSecret
        session_cookie_name: str
        session_cookie_secure: bool
        session_cookie_httponly: bool
        session_cookie_samesite: str
        admin_panel_base_url: str
        enable_telegram_2fa: bool
        enable_ip_allowlist: bool
        allowed_admin_ips: str
        trusted_proxy_ips: str
        rate_limit_messages_per_minute: int
        log_level: str

        def __init__(self) -> None:
            app_env = _normalize_app_env(_env_value("APP_ENV", "production"))
            database_url = _env_value("DATABASE_URL")
            _validate_sqlite_is_not_production(app_env, database_url)

            object.__setattr__(self, "app_env", app_env)
            object.__setattr__(self, "app_name", _env_value("APP_NAME", "Telegram Inbox Bot"))
            object.__setattr__(self, "app_version", _env_value("APP_VERSION", "1.0.0"))
            object.__setattr__(self, "database_url", PlainSecret(database_url))
            object.__setattr__(self, "telegram_bot_token", PlainSecret(_env_value("TELEGRAM_BOT_TOKEN")))
            object.__setattr__(self, "admin_telegram_id", _env_value("ADMIN_TELEGRAM_ID"))
            object.__setattr__(self, "secret_key", PlainSecret(_env_value("SECRET_KEY")))
            object.__setattr__(self, "session_cookie_name", _env_value("SESSION_COOKIE_NAME", "telegram_inbox_session"))
            object.__setattr__(self, "session_cookie_secure", _env_bool("SESSION_COOKIE_SECURE", True))
            object.__setattr__(self, "session_cookie_httponly", _env_bool("SESSION_COOKIE_HTTPONLY", True))
            object.__setattr__(self, "session_cookie_samesite", _env_value("SESSION_COOKIE_SAMESITE", "lax").strip().lower())
            object.__setattr__(self, "admin_panel_base_url", _env_value("ADMIN_PANEL_BASE_URL", "https://admintextbot.hotzagor.tech").rstrip("/"))
            object.__setattr__(self, "enable_telegram_2fa", _env_bool("ENABLE_TELEGRAM_2FA", True))
            object.__setattr__(self, "enable_ip_allowlist", _env_bool("ENABLE_IP_ALLOWLIST", False))
            object.__setattr__(self, "allowed_admin_ips", _env_value("ALLOWED_ADMIN_IPS", ""))
            object.__setattr__(self, "trusted_proxy_ips", _env_value("TRUSTED_PROXY_IPS", "127.0.0.1,::1"))
            object.__setattr__(self, "rate_limit_messages_per_minute", int(_env_value("RATE_LIMIT_MESSAGES_PER_MINUTE", "5")))
            object.__setattr__(self, "log_level", _env_value("LOG_LEVEL", "INFO").strip().upper())

        @property
        def is_production(self) -> bool:
            return self.app_env == "production"

        @property
        def is_development(self) -> bool:
            return self.app_env in {"development", "dev", "local"}

        @property
        def docs_url(self) -> str | None:
            return None if self.is_production else "/docs"

        @property
        def redoc_url(self) -> str | None:
            return None if self.is_production else "/redoc"

        @property
        def openapi_url(self) -> str | None:
            return None if self.is_production else "/openapi.json"

        @property
        def allowed_admin_ip_list(self) -> list[str]:
            return [
                ip.strip()
                for ip in self.allowed_admin_ips.split(",")
                if ip.strip()
            ]

        @property
        def trusted_proxy_ip_list(self) -> list[str]:
            return [
                ip.strip()
                for ip in self.trusted_proxy_ips.split(",")
                if ip.strip()
            ]

        def safe_summary(self) -> dict[str, object]:
            return _safe_summary(self)


def _safe_summary(settings: Settings) -> dict[str, object]:
    """Return non-secret values that are safe to include in logs."""

    return {
        "app_env": settings.app_env,
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "admin_panel_base_url": settings.admin_panel_base_url,
        "enable_telegram_2fa": settings.enable_telegram_2fa,
        "enable_ip_allowlist": settings.enable_ip_allowlist,
        "allowed_admin_ips_count": len(settings.allowed_admin_ip_list),
        "trusted_proxy_ips_count": len(settings.trusted_proxy_ip_list),
        "rate_limit_messages_per_minute": settings.rate_limit_messages_per_minute,
        "log_level": settings.log_level,
        "docs_enabled": settings.docs_url is not None,
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
