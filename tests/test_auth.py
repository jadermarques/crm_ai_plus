from __future__ import annotations

import pytest
from sqlalchemy import text

from src.core.auth import (
    count_users,
    create_user,
    ensure_users_table,
    list_users,
    set_user_status,
    update_password,
    update_user,
    verify_credentials,
)
from src.core.database import get_sessionmaker


@pytest.mark.asyncio
async def test_create_and_verify_user() -> None:
    await ensure_users_table()
    await create_user("alice", "secret1", full_name="Alice Doe", email="alice@example.com")

    ok, user = await verify_credentials("alice", "secret1")
    assert ok is True
    assert user is not None
    assert user["username"] == "alice"
    assert user["role"] == "USER"
    assert user["is_active"] is True

    ok_fail, _ = await verify_credentials("alice", "wrong")
    assert ok_fail is False
    ok_missing, _ = await verify_credentials("ghost", "secret1")
    assert ok_missing is False


@pytest.mark.asyncio
async def test_update_password() -> None:
    await ensure_users_table()
    await create_user("bob", "secret1", full_name="Bob Test", email="bob@example.com")

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
        await create_user("shorty", "123", full_name="Short User", email="short@example.com")


@pytest.mark.asyncio
async def test_update_password_nonexistent_user() -> None:
    await ensure_users_table()
    with pytest.raises(ValueError):
        await update_password("nobody", "newpass")


@pytest.mark.asyncio
async def test_duplicate_username_or_email() -> None:
    await ensure_users_table()
    await create_user("carol", "secret1", full_name="Carol A", email="carol@example.com")
    with pytest.raises(ValueError):
        await create_user("carol", "secret1", full_name="Carol B", email="carol2@example.com")
    with pytest.raises(ValueError):
        await create_user("carol2", "secret1", full_name="Carol C", email="carol@example.com")


@pytest.mark.asyncio
async def test_disable_user_blocks_login() -> None:
    await ensure_users_table()
    await create_user("dave", "secret1", full_name="Dave", email="dave@example.com")
    users = await list_users()
    dave_id = next(u["id"] for u in users if u["username"] == "dave")
    await set_user_status(dave_id, False)

    ok, user = await verify_credentials("dave", "secret1")
    assert ok is False
    assert user is None


@pytest.mark.asyncio
async def test_update_user_fields_and_count_active() -> None:
    await ensure_users_table()
    await create_user("erin", "secret1", full_name="Erin", email="erin@example.com")
    await create_user("frank", "secret1", full_name="Frank", email="frank@example.com")
    users = await list_users()
    erin_id = next(u["id"] for u in users if u["username"] == "erin")

    await update_user(
        erin_id,
        username="erin_1",
        full_name="Erin Updated",
        email="erin@sample.com",
        password=None,
        is_active=False,
        role="ADMIN",
    )
    users = await list_users()
    updated = next(u for u in users if u["id"] == erin_id)
    assert updated["username"] == "erin_1"
    assert updated["email"] == "erin@sample.com"
    assert updated["role"] == "ADMIN"
    assert updated["is_active"] is False

    active_count = await count_users()
    assert active_count == 1


@pytest.mark.asyncio
async def test_invalid_role_rejected() -> None:
    await ensure_users_table()
    with pytest.raises(ValueError):
        await create_user(
            "greg",
            "secret1",
            full_name="Greg",
            email="greg@example.com",
            role="OWNER",
        )


@pytest.mark.asyncio
async def test_reuse_session_between_calls() -> None:
    """Smoke check that sessionmaker works across calls in same loop."""
    await ensure_users_table()
    sm = get_sessionmaker()
    async with sm() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_invalid_email_rejected() -> None:
    await ensure_users_table()
    with pytest.raises(ValueError):
        await create_user("helen", "secret1", full_name="Helen", email="helensemail")
    with pytest.raises(ValueError):
        await create_user("irene", "secret1", full_name="Irene", email="irene@invalid")


@pytest.mark.asyncio
async def test_username_length_and_lowercase() -> None:
    await ensure_users_table()
    with pytest.raises(ValueError):
        await create_user("ab", "secret1", full_name="Too Short", email="short@example.com")
    with pytest.raises(ValueError):
        await create_user("thisusernameiswaytoolong", "secret1", full_name="Too Long", email="long@example.com")

    await create_user("MiXeDCase", "secret1", full_name="Mixed", email="mixed@example.com")
    users = await list_users()
    mixed = next(u for u in users if u["email"] == "mixed@example.com")
    assert mixed["username"] == "mixedcase"
