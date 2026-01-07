from __future__ import annotations

import asyncio
import re
from typing import Any

from passlib.hash import pbkdf2_sha256
from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, String, func, or_, select, text
from sqlalchemy.dialects.postgresql import VARCHAR

from src.core.database import get_engine, get_sessionmaker
from src.core.db_schema import ensure_audit_columns

metadata = MetaData()
_ALLOWED_ROLES = {"ADMIN", "USER"}
_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}(?:\.[^@\s]{2,})?$")

users = metadata.tables.get("users") or None

if users is None:
    from sqlalchemy import Table

    users = Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("username", String(255), unique=True, nullable=False),
        Column("full_name", String(255), nullable=True),
        Column("email", String(255), unique=True, nullable=True),
        Column("password_hash", VARCHAR(255), nullable=False),
        Column("role", String(20), nullable=False, server_default=text("'USER'")),
        Column("is_active", Boolean, nullable=False, server_default=text("TRUE")),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
        Column(
            "data_hora_inclusao",
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
        Column(
            "data_hora_alteracao",
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )


async def ensure_users_table() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        alter_statements = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(255)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now()",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'USER'",
        ]
        for statement in alter_statements:
            await conn.execute(text(statement))
        await conn.execute(text("UPDATE users SET is_active = TRUE WHERE is_active IS NULL"))
        await conn.execute(text("UPDATE users SET role = 'USER' WHERE role IS NULL"))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_users_username ON users (username)"))
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email ON users (email) WHERE email IS NOT NULL"
            )
        )
    await ensure_audit_columns("users")


async def count_users(only_active: bool = True) -> int:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        query = select(func.count()).select_from(users)
        if only_active and "is_active" in users.c:
            query = query.where(users.c.is_active.is_(True))
        result = await session.execute(query)
        return int(result.scalar_one())


def _serialize_user(row: Any) -> dict[str, Any]:
    data = dict(row)
    data.pop("password_hash", None)
    return data


async def get_user_by_username(username: str) -> dict[str, Any] | None:
    username = _normalize_username(username)
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(select(users).where(users.c.username == username))
        row = result.mappings().first()
        return _serialize_user(row) if row else None


async def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(select(users).where(users.c.id == user_id))
        row = result.mappings().first()
        return _serialize_user(row) if row else None


def _normalize_username(username: str) -> str:
    value = username.strip().lower()
    if len(value) < 3 or len(value) > 20:
        raise ValueError("O usuário deve ter entre 3 e 20 caracteres.")
    return value


def _normalize_email(email: str) -> str:
    value = email.strip().lower()
    if not value or not _EMAIL_REGEX.match(value):
        raise ValueError("Informe um e-mail válido.")
    return value


def _validate_password(password: str) -> None:
    if len(password) < 6:
        raise ValueError("A senha deve ter pelo menos 6 caracteres.")


def _validate_role(role: str) -> str:
    role_clean = role.strip().upper()
    if role_clean not in _ALLOWED_ROLES:
        raise ValueError("Tipo de usuário inválido. Use ADMIN ou USER.")
    return role_clean


async def list_users(include_inactive: bool = True) -> list[dict[str, Any]]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        query = select(users).order_by(users.c.username)
        if not include_inactive and "is_active" in users.c:
            query = query.where(users.c.is_active.is_(True))
        result = await session.execute(query)
        return [_serialize_user(row) for row in result.mappings().all()]


async def create_user(
    username: str, password: str, *, full_name: str, email: str, role: str = "USER"
) -> None:
    _validate_password(password)
    username = _normalize_username(username)
    email = _normalize_email(email)
    full_name = full_name.strip()
    role_clean = _validate_role(role)
    if not username:
        raise ValueError("Informe um usuário válido.")
    if not full_name:
        raise ValueError("Informe o nome completo.")
    if not email:
        raise ValueError("Informe um e-mail válido.")

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        exists = await session.execute(
            select(users.c.id).where(or_(users.c.username == username, users.c.email == email))
        )
        if exists.first():
            raise ValueError("Usuário ou e-mail já existe.")

        password_hash = pbkdf2_sha256.hash(password)
        await session.execute(
            users.insert().values(
                username=username,
                full_name=full_name,
                email=email,
                password_hash=password_hash,
                role=role_clean,
                is_active=True,
            )
        )
        await session.commit()


async def update_user(
    user_id: int,
    *,
    username: str,
    full_name: str,
    email: str,
    password: str | None = None,
    is_active: bool | None = None,
    role: str | None = None,
) -> None:
    username = _normalize_username(username)
    email = _normalize_email(email)
    full_name = full_name.strip()
    role_clean = _validate_role(role) if role is not None else None
    if password is not None:
        _validate_password(password)
    if not username:
        raise ValueError("Informe um usuário válido.")
    if not full_name:
        raise ValueError("Informe o nome completo.")
    if not email:
        raise ValueError("Informe um e-mail válido.")

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        existing = await session.execute(
            select(users.c.id).where(
                or_(users.c.username == username, users.c.email == email),
                users.c.id != user_id,
            )
        )
        if existing.first():
            raise ValueError("Usuário ou e-mail já existe.")

    values: dict[str, Any] = {
        "username": username,
        "full_name": full_name,
        "email": email,
    }
    if password is not None:
        values["password_hash"] = pbkdf2_sha256.hash(password)
    if is_active is not None and "is_active" in users.c:
        values["is_active"] = is_active
    if role_clean is not None:
        values["role"] = role_clean

    result = await session.execute(users.update().where(users.c.id == user_id).values(**values))
    if result.rowcount == 0:
        raise ValueError("Usuário não encontrado.")
    await session.commit()


async def update_password(username: str, password: str) -> None:
    _validate_password(password)
    username = _normalize_username(username)
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


async def set_user_status(user_id: int, is_active: bool) -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(
            users.update().where(users.c.id == user_id).values(is_active=is_active)
        )
        if result.rowcount == 0:
            raise ValueError("Usuário não encontrado.")
        await session.commit()


async def verify_credentials(username: str, password: str) -> tuple[bool, dict[str, Any] | None]:
    username = _normalize_username(username)
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(select(users).where(users.c.username == username))
        row = result.mappings().first()
        if not row:
            return False, None
        data = dict(row)
        if not data.get("is_active", True):
            return False, None
        if not pbkdf2_sha256.verify(password, data["password_hash"]):
            return False, None
        data.pop("password_hash", None)
        return True, data


def run_async(coro):
    """Helper to run async coroutines from Streamlit."""
    return asyncio.run(coro)
