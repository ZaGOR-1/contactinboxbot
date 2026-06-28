"""Async SQLAlchemy database setup."""

from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings


_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def create_engine(settings: Settings | None = None) -> AsyncEngine:
    app_settings = settings or get_settings()
    database_url = app_settings.database_url.get_secret_value()
    database_url, connect_args = normalize_database_url(database_url)

    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_async_engine(
        database_url,
        echo=app_settings.is_development and app_settings.log_level == "DEBUG",
        pool_pre_ping=True,
        connect_args=connect_args,
    )


def normalize_database_url(database_url: str) -> tuple[str, dict[str, object]]:
    """Return SQLAlchemy URL plus driver-specific connect args.

    asyncpg does not accept libpq-style `sslmode=disable` as a keyword
    argument. Keep `.env` operator-friendly and translate it to `ssl=False`.
    """

    connect_args: dict[str, object] = {}
    if not database_url.startswith("postgresql+asyncpg://"):
        return database_url, connect_args

    parsed = urlsplit(database_url)
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    kept_query_items: list[tuple[str, str]] = []

    for key, value in query_items:
        if key == "sslmode" and value.lower() == "disable":
            connect_args["ssl"] = False
            continue
        kept_query_items.append((key, value))

    normalized_url = urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(kept_query_items),
            parsed.fragment,
        )
    )
    return normalized_url, connect_args


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_maker


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an async database session."""

    async with get_session_maker()() as session:
        yield session


async def dispose_engine() -> None:
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_maker = None
