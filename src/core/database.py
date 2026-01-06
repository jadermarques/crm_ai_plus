from __future__ import annotations

import asyncio
import weakref
from functools import lru_cache
from typing import AsyncGenerator

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import get_settings


def _ensure_async_driver(db_url: str) -> str | URL:
    """Normalize Postgres URLs to a valid async driver name."""
    try:
        parsed_url = make_url(db_url)
    except ArgumentError:
        return db_url

    backend = parsed_url.get_backend_name()
    driver = parsed_url.get_driver_name()

    if backend in {"postgres", "postgresql"}:
        target_driver = driver or "asyncpg"
        drivername = f"postgresql+{target_driver}"
        return parsed_url.set(drivername=drivername)

    return parsed_url


_ENGINES: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, AsyncEngine] = (
    weakref.WeakKeyDictionary()
)
_SESSIONMAKERS: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, async_sessionmaker[AsyncSession]
] = weakref.WeakKeyDictionary()


def _current_loop() -> asyncio.AbstractEventLoop:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.get_event_loop()


def get_engine() -> AsyncEngine:
    loop = _current_loop()
    engine = _ENGINES.get(loop)
    if engine is not None:
        return engine
    settings = get_settings()
    normalized_url = _ensure_async_driver(settings.DATABASE_URL)
    engine = create_async_engine(normalized_url, pool_pre_ping=True)
    _ENGINES[loop] = engine
    return engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    loop = _current_loop()
    sm = _SESSIONMAKERS.get(loop)
    if sm is not None:
        return sm
    sm = async_sessionmaker(get_engine(), expire_on_commit=False)
    _SESSIONMAKERS[loop] = sm
    return sm


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        yield session
