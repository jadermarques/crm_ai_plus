from __future__ import annotations

import asyncio
from typing import Any

from passlib.hash import pbkdf2_sha256
from sqlalchemy import Column, DateTime, Integer, MetaData, String, func, select
from sqlalchemy.dialects.postgresql import VARCHAR

from src.core.database import get_engine, get_sessionmaker

metadata = MetaData()

users = metadata.tables.get("users") or None

if users is None:
    from sqlalchemy import Table

    users = Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("username", String(255), unique=True, nullable=False),
        Column("password_hash", VARCHAR(255), nullable=False),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
    )


async def ensure_users_table() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


async def count_users() -> int:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(select(func.count()).select_from(users))
        return int(result.scalar_one())


async def get_user_by_username(username: str) -> dict[str, Any] | None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(select(users).where(users.c.username == username))
        row = result.mappings().first()
        return dict(row) if row else None


async def create_user(username: str, password: str) -> None:
    if len(password) < 6:
        raise ValueError("A senha deve ter pelo menos 6 caracteres.")
    password_hash = pbkdf2_sha256.hash(password)
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(
            users.insert().values(username=username, password_hash=password_hash)
        )
        await session.commit()


async def update_password(username: str, password: str) -> None:
    if len(password) < 6:
        raise ValueError("A senha deve ter pelo menos 6 caracteres.")
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(select(users.c.id).where(users.c.username == username))
        row = result.first()
        if not row:
            raise ValueError("Usuário não encontrado.")
        password_hash = pbkdf2_sha256.hash(password)
        await session.execute(
            users.update()
            .where(users.c.username == username)
            .values(password_hash=password_hash)
        )
        await session.commit()


async def verify_credentials(username: str, password: str) -> tuple[bool, dict[str, Any] | None]:
    user = await get_user_by_username(username)
    if not user:
        return False, None
    if not pbkdf2_sha256.verify(password, user["password_hash"]):
        return False, None
    return True, user


def run_async(coro):
    """Helper to run async coroutines from Streamlit."""
    return asyncio.run(coro)
