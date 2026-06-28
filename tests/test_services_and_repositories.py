from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("aiosqlite")
pytest.importorskip("sqlalchemy")

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.models import (
    AdminUser,
    Base,
    Message,
    MessageDirection,
    MessageStatus,
    User,
)
from app.db.repositories import (
    AdminUserRepository,
    LoginAttemptRepository,
    MessageRepository,
    TwoFactorCodeRepository,
    UserRepository,
)
from app.services.auth_service import AuthService
from app.services.message_service import MessageService
from app.services.rate_limit_service import RateLimitService
from app.services.telegram_service import TelegramService
from app.services.two_factor_service import TwoFactorService
from app.services.user_service import UserService
from tests.helpers import TestSettings


class TelegramUser:
    id = 101
    username = "alice"
    first_name = "Alice"
    last_name = "Example"
    language_code = "uk"


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[tuple[int | str, str]] = []

    async def send_message(self, chat_id: int | str, text: str) -> object:
        self.messages.append((chat_id, text))
        return object()


@pytest.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_start_like_upsert_creates_and_updates_user(db_session) -> None:
    service = UserService(db_session)

    created = await service.upsert_from_telegram(TelegramUser())
    await db_session.commit()

    assert created.telegram_id == TelegramUser.id
    assert created.username == "alice"
    assert created.last_message_at is None

    TelegramUser.username = "alice_new"
    updated = await service.upsert_from_telegram(TelegramUser(), touch_last_message_at=True)
    await db_session.commit()

    assert updated.id == created.id
    assert updated.username == "alice_new"
    assert updated.last_message_at is not None


@pytest.mark.asyncio
async def test_incoming_message_search_filters_and_mark_read(db_session) -> None:
    user = await UserRepository(db_session).create_or_update_from_telegram(
        telegram_id=202,
        username="bob",
        first_name="Bob",
        last_name=None,
        language_code="en",
    )
    incoming = await MessageService(db_session).save_incoming_text(
        user=user,
        text="Need help with invoices",
        telegram_message_id=777,
    )
    await MessageService(db_session).save_outgoing_text(
        user=user,
        text="We are checking this",
        status=MessageStatus.answered,
        telegram_message_id=778,
    )
    await db_session.commit()

    messages = MessageRepository(db_session)
    found = await messages.search_messages(
        search="invoice",
        direction=MessageDirection.incoming,
        status=MessageStatus.new,
    )

    assert [message.id for message in found] == [incoming.id]

    marked = await messages.mark_as_read(incoming.id)
    await db_session.commit()

    assert marked is not None
    assert marked.status == MessageStatus.read
    assert await messages.count(status=MessageStatus.read) == 1


@pytest.mark.asyncio
async def test_users_search_filter_and_blocked_flow(db_session) -> None:
    users = UserRepository(db_session)
    active = await users.create_or_update_from_telegram(
        telegram_id=303,
        username="charlie",
        first_name="Charlie",
        last_name=None,
        language_code="en",
    )
    blocked = await users.create_or_update_from_telegram(
        telegram_id=404,
        username="dana",
        first_name="Dana",
        last_name=None,
        language_code="uk",
    )
    await users.set_blocked(blocked.id, True)
    await db_session.commit()

    assert await users.count(is_blocked=False) == 1
    assert await users.count(is_blocked=True) == 1
    assert [user.id for user in await users.list_users(search="char")] == [active.id]


@pytest.mark.asyncio
async def test_rate_limit_blocks_after_configured_window_count(db_session) -> None:
    user = await UserRepository(db_session).create_or_update_from_telegram(
        telegram_id=505,
        username="eve",
        first_name="Eve",
        last_name=None,
        language_code="en",
    )
    messages = MessageService(db_session)
    for index in range(5):
        await messages.save_incoming_text(
            user=user,
            text=f"message {index}",
            telegram_message_id=index,
        )
    await db_session.commit()

    result = await RateLimitService(db_session, TestSettings(rate_limit_messages_per_minute=5)).check_user_message_limit(user)

    assert result.allowed is False
    assert result.used == 5
    assert result.retry_after_seconds == 60


@pytest.mark.asyncio
async def test_bruteforce_lockout_after_five_failed_attempts(db_session) -> None:
    password_hash = hash_password("good-password")
    admin = await AdminUserRepository(db_session).create(username="admin", password_hash=password_hash)
    await db_session.commit()

    auth = AuthService(db_session)
    for _ in range(5):
        result = await auth.authenticate(
            username=admin.username,
            password="wrong-password",
            ip_address="203.0.113.10",
        )
        assert result.success is False
    await db_session.commit()

    locked = await auth.authenticate(
        username=admin.username,
        password="good-password",
        ip_address="203.0.113.10",
    )

    assert locked.success is False
    assert locked.locked is True


@pytest.mark.asyncio
async def test_two_factor_codes_are_hashed_expiring_and_single_use(db_session) -> None:
    admin = await AdminUserRepository(db_session).create(
        username="admin",
        password_hash=hash_password("password"),
    )
    code = "123456"
    stored = await TwoFactorCodeRepository(db_session).create(
        admin_user_id=admin.id,
        code_hash=hash_password(code),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    await db_session.commit()

    assert stored.code_hash != code

    service = TwoFactorService(db_session, TestSettings())
    result = await service.verify_code(admin_user_id=admin.id, submitted_code=code)
    await db_session.commit()

    assert result.success is True
    assert stored.used_at is not None

    reused = await service.verify_code(admin_user_id=admin.id, submitted_code=code)
    assert reused.success is False


@pytest.mark.asyncio
async def test_failed_telegram_reply_is_saved_as_failed_outgoing(db_session) -> None:
    user = await UserRepository(db_session).create_or_update_from_telegram(
        telegram_id=606,
        username="frank",
        first_name="Frank",
        last_name=None,
        language_code="en",
    )

    saved = await MessageService(db_session).save_outgoing_text(
        user=user,
        text="Reply text",
        status=MessageStatus.failed,
        error_text="Telegram API failed",
    )
    await db_session.commit()

    message = await MessageRepository(db_session).get_by_id(saved.id)
    assert message is not None
    assert message.direction == MessageDirection.outgoing
    assert message.status == MessageStatus.failed
    assert message.error_text == "Telegram API failed"


@pytest.mark.asyncio
async def test_admin_notification_contains_user_link_and_uses_admin_id() -> None:
    user = User(
        id=9,
        telegram_id=707,
        username="grace",
        first_name="Grace",
        last_name="Hopper",
    )
    message = Message(
        id=11,
        user_id=9,
        direction=MessageDirection.incoming,
        text="Hello from Telegram",
        status=MessageStatus.new,
        created_at=datetime(2026, 6, 28, tzinfo=UTC),
    )
    bot = FakeBot()

    await TelegramService(TestSettings(admin_telegram_id="999")).notify_admin_about_new_message(
        bot=bot,
        user=user,
        message=message,
    )

    assert bot.messages
    chat_id, text = bot.messages[0]
    assert chat_id == "999"
    assert "https://admintextbot.hotzagor.tech/users/9" in text
    assert "Hello from Telegram" in text


@pytest.mark.asyncio
async def test_admin_notification_skips_unconfigured_admin_id() -> None:
    user = User(id=10, telegram_id=808, username="heidi")
    message = Message(
        id=12,
        user_id=10,
        direction=MessageDirection.incoming,
        text="Ping",
        status=MessageStatus.new,
        created_at=datetime.now(UTC),
    )
    bot = FakeBot()

    settings = replace(TestSettings(), admin_telegram_id="CHANGE_ME")
    await TelegramService(settings).notify_admin_about_new_message(bot=bot, user=user, message=message)

    assert bot.messages == []
