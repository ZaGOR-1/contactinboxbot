"""Shared test helpers with no third-party dependencies."""

from __future__ import annotations

from dataclasses import dataclass


class TestSecret:
    def __init__(self, value: str) -> None:
        self.value = value

    def get_secret_value(self) -> str:
        return self.value


@dataclass(frozen=True)
class TestSettings:
    app_env: str = "production"
    app_name: str = "Telegram Inbox Bot"
    app_version: str = "test"
    database_url: TestSecret = TestSecret("sqlite+aiosqlite:///:memory:")
    telegram_bot_token: TestSecret = TestSecret("123456789:TEST_TOKEN_PLACEHOLDER")
    admin_telegram_id: str = "123456789"
    secret_key: TestSecret = TestSecret("test-secret-key-with-enough-entropy")
    session_cookie_name: str = "telegram_inbox_session"
    session_cookie_secure: bool = True
    session_cookie_httponly: bool = True
    session_cookie_samesite: str = "lax"
    admin_panel_base_url: str = "https://admintextbot.hotzagor.tech"
    enable_telegram_2fa: bool = True
    enable_ip_allowlist: bool = False
    allowed_admin_ips: str = ""
    rate_limit_messages_per_minute: int = 5
    log_level: str = "INFO"

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
        return [ip.strip() for ip in self.allowed_admin_ips.split(",") if ip.strip()]


class CookieRecorder:
    def __init__(self) -> None:
        self.cookies: list[tuple[str, str, dict[str, object]]] = []
        self.deleted: list[tuple[str, dict[str, object]]] = []

    def set_cookie(self, key: str, value: str, **kwargs: object) -> None:
        self.cookies.append((key, value, kwargs))

    def delete_cookie(self, key: str, **kwargs: object) -> None:
        self.deleted.append((key, kwargs))
