"""Módulo de Autenticação - Gerenciamento de Usuários e Autenticação.

Este módulo fornece funções para autenticação de usuários, incluindo
verificação de credenciais, criação/atualização de usuários e gerenciamento
de senhas. Usa PBKDF2-SHA256 para hash seguro de senhas.

Security:
    - Senhas são hasheadas usando PBKDF2-SHA256
    - Nomes de usuário são normalizados para minúsculas
    - Validação de e-mail é realizada

Functions:
    ensure_users_table: Cria tabela no banco se não existir.
    list_users: Lista todos os usuários.
    create_user: Cria um novo usuário.
    update_user: Atualiza um usuário existente.
    verify_credentials: Verifica credenciais de login.
    update_password: Atualiza senha do usuário.
    set_user_status: Ativa/desativa usuário.

Roles:
    ADMIN: Acesso total ao sistema.
    USER: Acesso de usuário padrão.

Example:
    >>> from src.core.auth import verify_credentials, create_user
    >>> await create_user("admin", "password123", full_name="Admin", email="admin@test.com")
    >>> is_valid, user = await verify_credentials("admin", "password123")
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

from passlib.hash import pbkdf2_sha256
from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, String, func, or_, select, text
from sqlalchemy.dialects.postgresql import VARCHAR

from sqlalchemy.ext.asyncio import AsyncSession
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


async def count_users(
    only_active: bool = True, session: AsyncSession | None = None
) -> int:
    if session:
        return await _count_users_impl(session, only_active)
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        return await _count_users_impl(session, only_active)


async def _count_users_impl(session: AsyncSession, only_active: bool) -> int:
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


async def list_users(
    include_inactive: bool = True, session: AsyncSession | None = None
) -> list[dict[str, Any]]:
    if session:
        return await _list_users_impl(session, include_inactive)
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        return await _list_users_impl(session, include_inactive)


async def _list_users_impl(
    session: AsyncSession, include_inactive: bool
) -> list[dict[str, Any]]:
    query = select(users).order_by(users.c.username)
    if not include_inactive and "is_active" in users.c:
        query = query.where(users.c.is_active.is_(True))
    result = await session.execute(query)
    return [_serialize_user(row) for row in result.mappings().all()]


async def create_user(
    username: str,
    password: str,
    *,
    full_name: str,
    email: str,
    role: str = "USER",
    session: AsyncSession | None = None,
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

    if session:
        return await _create_user_impl(
            session, username, password, full_name, email, role_clean
        )
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await _create_user_impl(
            session, username, password, full_name, email, role_clean
        )
        await session.commit()


async def _create_user_impl(
    session: AsyncSession,
    username: str,
    password: str,
    full_name: str,
    email: str,
    role: str,
) -> None:
    exists = await session.execute(
        select(users.c.id).where(
            or_(users.c.username == username, users.c.email == email)
        )
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
            role=role,
            is_active=True,
        )
    )


async def update_user(
    user_id: int,
    *,
    username: str,
    full_name: str,
    email: str,
    password: str | None = None,
    is_active: bool | None = None,
    role: str | None = None,
    session: AsyncSession | None = None,
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

    if session:
        return await _update_user_impl(
            session,
            user_id,
            username,
            full_name,
            email,
            password,
            is_active,
            role_clean,
        )
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await _update_user_impl(
            session,
            user_id,
            username,
            full_name,
            email,
            password,
            is_active,
            role_clean,
        )
        await session.commit()


async def _update_user_impl(
    session: AsyncSession,
    user_id: int,
    username: str,
    full_name: str,
    email: str,
    password: str | None,
    is_active: bool | None,
    role: str | None,
) -> None:
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
    if role is not None:
        values["role"] = role

    result = await session.execute(
        users.update().where(users.c.id == user_id).values(**values)
    )
    if result.rowcount == 0:
        raise ValueError("Usuário não encontrado.")


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
