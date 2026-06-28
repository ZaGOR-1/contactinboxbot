"""Repository helpers for common database operations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, String, cast, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    AdminUser,
    LoginAttempt,
    Message,
    MessageDirection,
    MessageStatus,
    Settings,
    TwoFactorCode,
    User,
)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def create_or_update_from_telegram(
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        language_code: str | None,
        last_message_at: datetime | None = None,
    ) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user is None:
            user = User(telegram_id=telegram_id)
            self.session.add(user)

        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.language_code = language_code
        if last_message_at is not None:
            user.last_message_at = last_message_at

        await self.session.flush()
        return user

    async def set_blocked(self, user_id: int, is_blocked: bool) -> User | None:
        user = await self.get_by_id(user_id)
        if user is None:
            return None
        user.is_blocked = is_blocked
        await self.session.flush()
        return user

    async def list_users(
        self,
        *,
        search: str | None = None,
        is_blocked: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[User]:
        statement: Select[tuple[User]] = select(User)
        if search:
            like = f"%{search}%"
            statement = statement.where(
                User.username.ilike(like)
                | User.first_name.ilike(like)
                | User.last_name.ilike(like)
                | cast(User.telegram_id, String).ilike(like)
            )
        if is_blocked is not None:
            statement = statement.where(User.is_blocked == is_blocked)

        statement = statement.order_by(User.last_message_at.desc().nullslast()).limit(limit).offset(offset)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def list_users_with_message_counts(
        self,
        *,
        search: str | None = None,
        is_blocked: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[tuple[User, int]]:
        statement = (
            select(User, func.count(Message.id))
            .outerjoin(Message, Message.user_id == User.id)
            .group_by(User.id)
        )
        statement = self._apply_user_filters(
            statement,
            search=search,
            is_blocked=is_blocked,
        )
        statement = (
            statement.order_by(User.last_message_at.desc().nullslast(), User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(statement)
        return [(user, int(count)) for user, count in result.all()]

    async def count(
        self,
        *,
        is_blocked: bool | None = None,
        search: str | None = None,
    ) -> int:
        statement = select(func.count(User.id))
        statement = self._apply_user_filters(
            statement,
            search=search,
            is_blocked=is_blocked,
        )
        result = await self.session.execute(statement)
        return int(result.scalar_one())

    def _apply_user_filters(
        self,
        statement: Select,
        *,
        search: str | None,
        is_blocked: bool | None,
    ) -> Select:
        if search:
            like = f"%{search}%"
            statement = statement.where(
                or_(
                    User.username.ilike(like),
                    User.first_name.ilike(like),
                    User.last_name.ilike(like),
                    cast(User.telegram_id, String).ilike(like),
                )
            )
        if is_blocked is not None:
            statement = statement.where(User.is_blocked == is_blocked)
        return statement


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, message_id: int) -> Message | None:
        result = await self.session.execute(
            select(Message)
            .options(selectinload(Message.user))
            .where(Message.id == message_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        user_id: int,
        direction: MessageDirection,
        text: str,
        status: MessageStatus,
        telegram_message_id: int | None = None,
        error_text: str | None = None,
    ) -> Message:
        message = Message(
            user_id=user_id,
            direction=direction,
            text=text,
            status=status,
            telegram_message_id=telegram_message_id,
            error_text=error_text,
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def list_messages(
        self,
        *,
        user_id: int | None = None,
        direction: MessageDirection | None = None,
        status: MessageStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Message]:
        statement = select(Message).options(selectinload(Message.user))
        if user_id is not None:
            statement = statement.where(Message.user_id == user_id)
        if direction is not None:
            statement = statement.where(Message.direction == direction)
        if status is not None:
            statement = statement.where(Message.status == status)

        statement = statement.order_by(Message.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def search_messages(
        self,
        *,
        search: str | None = None,
        direction: MessageDirection | None = None,
        status: MessageStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Message]:
        statement = self._filtered_messages_statement(
            search=search,
            direction=direction,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )
        statement = (
            statement.options(selectinload(Message.user))
            .order_by(Message.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def count_filtered_messages(
        self,
        *,
        search: str | None = None,
        direction: MessageDirection | None = None,
        status: MessageStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> int:
        statement = self._filtered_messages_statement(
            search=search,
            direction=direction,
            status=status,
            date_from=date_from,
            date_to=date_to,
            count=True,
        )
        result = await self.session.execute(statement)
        return int(result.scalar_one())

    def _filtered_messages_statement(
        self,
        *,
        search: str | None,
        direction: MessageDirection | None,
        status: MessageStatus | None,
        date_from: datetime | None,
        date_to: datetime | None,
        count: bool = False,
    ) -> Select[tuple[Message]] | Select[tuple[int]]:
        columns = func.count(Message.id) if count else Message
        statement = select(columns).join(User, Message.user_id == User.id)

        if search:
            like = f"%{search}%"
            statement = statement.where(
                or_(
                    Message.text.ilike(like),
                    User.username.ilike(like),
                    User.first_name.ilike(like),
                    User.last_name.ilike(like),
                    cast(User.telegram_id, String).ilike(like),
                )
            )
        if direction is not None:
            statement = statement.where(Message.direction == direction)
        if status is not None:
            statement = statement.where(Message.status == status)
        if date_from is not None:
            statement = statement.where(Message.created_at >= date_from)
        if date_to is not None:
            statement = statement.where(Message.created_at <= date_to)

        return statement

    async def mark_as_read(self, message_id: int) -> Message | None:
        message = await self.get_by_id(message_id)
        if message is None:
            return None
        message.status = MessageStatus.read
        await self.session.flush()
        return message

    async def mark_user_incoming_as_answered(self, user_id: int) -> None:
        await self.session.execute(
            update(Message)
            .where(
                Message.user_id == user_id,
                Message.direction == MessageDirection.incoming,
                Message.status.in_([MessageStatus.new, MessageStatus.read]),
            )
            .values(status=MessageStatus.answered)
        )

    async def mark_user_incoming_as_read(self, user_id: int) -> None:
        await self.session.execute(
            update(Message)
            .where(
                Message.user_id == user_id,
                Message.direction == MessageDirection.incoming,
                Message.status == MessageStatus.new,
            )
            .values(status=MessageStatus.read)
        )

    async def list_user_conversation(self, *, user_id: int) -> list[Message]:
        result = await self.session.execute(
            select(Message)
            .where(Message.user_id == user_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        return list(result.scalars().all())

    async def count(
        self,
        *,
        status: MessageStatus | None = None,
        direction: MessageDirection | None = None,
    ) -> int:
        statement = select(func.count(Message.id))
        if status is not None:
            statement = statement.where(Message.status == status)
        if direction is not None:
            statement = statement.where(Message.direction == direction)
        result = await self.session.execute(statement)
        return int(result.scalar_one())

    async def latest_messages(self, *, limit: int = 10) -> list[Message]:
        result = await self.session.execute(
            select(Message)
            .options(selectinload(Message.user))
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_recent_incoming_by_user(
        self,
        *,
        user_id: int,
        since: datetime,
    ) -> int:
        result = await self.session.execute(
            select(func.count(Message.id)).where(
                Message.user_id == user_id,
                Message.direction == MessageDirection.incoming,
                Message.created_at >= since,
            )
        )
        return int(result.scalar_one())


class AdminUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, admin_user_id: int) -> AdminUser | None:
        return await self.session.get(AdminUser, admin_user_id)

    async def get_by_username(self, username: str) -> AdminUser | None:
        result = await self.session.execute(
            select(AdminUser).where(AdminUser.username == username)
        )
        return result.scalar_one_or_none()

    async def create(self, *, username: str, password_hash: str) -> AdminUser:
        admin_user = AdminUser(username=username, password_hash=password_hash)
        self.session.add(admin_user)
        await self.session.flush()
        return admin_user

    async def update_password_hash(
        self,
        admin_user_id: int,
        password_hash: str,
    ) -> AdminUser | None:
        admin_user = await self.get_by_id(admin_user_id)
        if admin_user is None:
            return None
        admin_user.password_hash = password_hash
        await self.session.flush()
        return admin_user

    async def count(self) -> int:
        result = await self.session.execute(select(func.count(AdminUser.id)))
        return int(result.scalar_one())

    async def update_last_login(self, admin_user_id: int, when: datetime) -> None:
        await self.session.execute(
            update(AdminUser)
            .where(AdminUser.id == admin_user_id)
            .values(last_login_at=when)
        )


class LoginAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        ip_address: str,
        username: str | None,
        success: bool,
    ) -> LoginAttempt:
        attempt = LoginAttempt(
            ip_address=ip_address,
            username=username,
            success=success,
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def count_failed_since(
        self,
        *,
        ip_address: str,
        since: datetime,
    ) -> int:
        result = await self.session.execute(
            select(func.count(LoginAttempt.id)).where(
                LoginAttempt.ip_address == ip_address,
                LoginAttempt.success.is_(False),
                LoginAttempt.created_at >= since,
            )
        )
        return int(result.scalar_one())


class TwoFactorCodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        admin_user_id: int,
        code_hash: str,
        expires_at: datetime,
    ) -> TwoFactorCode:
        code = TwoFactorCode(
            admin_user_id=admin_user_id,
            code_hash=code_hash,
            expires_at=expires_at,
        )
        self.session.add(code)
        await self.session.flush()
        return code

    async def get_active_for_admin(
        self,
        *,
        admin_user_id: int,
        now: datetime,
    ) -> TwoFactorCode | None:
        result = await self.session.execute(
            select(TwoFactorCode)
            .where(
                TwoFactorCode.admin_user_id == admin_user_id,
                TwoFactorCode.used_at.is_(None),
                TwoFactorCode.expires_at > now,
            )
            .order_by(TwoFactorCode.created_at.desc())
        )
        return result.scalars().first()

    async def mark_used(self, code_id: int, used_at: datetime) -> None:
        await self.session.execute(
            update(TwoFactorCode)
            .where(TwoFactorCode.id == code_id)
            .values(used_at=used_at)
        )


class SettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, key: str) -> Settings | None:
        result = await self.session.execute(select(Settings).where(Settings.key == key))
        return result.scalar_one_or_none()

    async def set(self, key: str, value: str | None) -> Settings:
        setting = await self.get(key)
        if setting is None:
            setting = Settings(key=key)
            self.session.add(setting)
        setting.value = value
        await self.session.flush()
        return setting
