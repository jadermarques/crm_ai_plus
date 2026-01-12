"""Módulo de Conexão com Banco de Dados.

Este módulo fornece funções para criar e gerenciar conexões assíncronas
com o banco de dados PostgreSQL usando SQLAlchemy.

Attributes:
    _ENGINES: Cache de engines por event loop.
    _SESSIONMAKERS: Cache de sessionmakers por event loop.

Functions:
    get_engine: Obtém engine assíncrona do banco de dados.
    get_sessionmaker: Obtém factory de sessões assíncronas.
    get_db: Generator assíncrono de sessões para injeção de dependência.

Example:
    >>> from src.core.database import get_engine, get_sessionmaker
    >>> engine = get_engine()
    >>> session_factory = get_sessionmaker()
"""
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
    """Normaliza URLs de Postgres para usar driver assíncrono.

    Args:
        db_url: URL de conexão do banco de dados.

    Returns:
        URL normalizada com driver asyncpg para PostgreSQL.
    """
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
    """Obtém o event loop atual.

    Returns:
        Event loop em execução ou padrão.
    """
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.get_event_loop()


def get_engine() -> AsyncEngine:
    """Obtém engine assíncrona do banco de dados.

    Cria ou retorna engine existente cacheada por event loop.

    Returns:
        AsyncEngine configurada para PostgreSQL com asyncpg.
    """
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
    """Obtém factory de sessões assíncronas.

    Cria ou retorna sessionmaker existente cacheado por event loop.

    Returns:
        async_sessionmaker configurado com a engine atual.
    """
    loop = _current_loop()
    sm = _SESSIONMAKERS.get(loop)
    if sm is not None:
        return sm
    sm = async_sessionmaker(get_engine(), expire_on_commit=False)
    _SESSIONMAKERS[loop] = sm
    return sm


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Generator assíncrono de sessões para injeção de dependência.

    Yields:
        AsyncSession para uso em endpoints FastAPI.
    """
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        yield session

