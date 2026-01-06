from __future__ import annotations

import pytest

from src.core.auth import (
    create_user,
    ensure_users_table,
    update_password,
    verify_credentials,
)
from src.core.database import get_sessionmaker


@pytest.mark.asyncio
async def test_create_and_verify_user() -> None:
    await ensure_users_table()
    await create_user("alice", "secret1")

    ok, user = await verify_credentials("alice", "secret1")
    assert ok is True
    assert user is not None
    assert user["username"] == "alice"

    ok_fail, _ = await verify_credentials("alice", "wrong")
    assert ok_fail is False
    ok_missing, _ = await verify_credentials("ghost", "secret1")
    assert ok_missing is False


@pytest.mark.asyncio
async def test_update_password() -> None:
    await ensure_users_table()
    await create_user("bob", "secret1")

    await update_password("bob", "newpass")
    ok_old, _ = await verify_credentials("bob", "secret1")
    ok_new, user = await verify_credentials("bob", "newpass")

    assert ok_old is False
    assert ok_new is True
    assert user is not None
    assert user["username"] == "bob"


@pytest.mark.asyncio
async def test_password_min_length() -> None:
    await ensure_users_table()
    with pytest.raises(ValueError):
        await create_user("shorty", "123")


@pytest.mark.asyncio
async def test_update_password_nonexistent_user() -> None:
    await ensure_users_table()
    with pytest.raises(ValueError):
        await update_password("nobody", "newpass")


@pytest.mark.asyncio
async def test_reuse_session_between_calls() -> None:
    """Smoke check that sessionmaker works across calls in same loop."""
    await ensure_users_table()
    sm = get_sessionmaker()
    async with sm() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1
from sqlalchemy import text
