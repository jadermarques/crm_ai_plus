from __future__ import annotations

import pytest

from src.core.auth import create_user, ensure_users_table
from src.core.management import (
    create_application,
    create_module,
    create_permission,
    ensure_management_tables,
    list_applications,
    list_modules,
    list_permissions,
)


@pytest.mark.asyncio
async def test_create_module_and_duplicate() -> None:
    await ensure_management_tables()
    await create_module("Financeiro", "Módulo financeiro", is_active=True)
    modules = await list_modules()
    fin = next(m for m in modules if m["name"] == "Financeiro")
    assert fin["name"] == "Financeiro"

    with pytest.raises(ValueError):
        await create_module("Financeiro", "Duplicado", is_active=True)


@pytest.mark.asyncio
async def test_create_application_requires_module_and_unique() -> None:
    await ensure_management_tables()
    await create_module("Operacional", "Controle operacional", is_active=True)
    modules = await list_modules()
    module_id = next(m["id"] for m in modules if m["name"] == "Operacional")

    await create_application("Faturas", "Gestão de faturas", module_id=module_id, is_active=True)
    apps = await list_applications()
    assert apps[0]["module_id"] == module_id

    with pytest.raises(ValueError):
        await create_application("Faturas", "Duplicada", module_id=module_id, is_active=True)

    with pytest.raises(ValueError):
        await create_application("SemModulo", "Sem módulo", module_id=999, is_active=True)


@pytest.mark.asyncio
async def test_permissions_rules_and_admin_skip() -> None:
    await ensure_users_table()
    await ensure_management_tables()
    await create_module("Operações", "Ops", is_active=True)
    modules = await list_modules()
    module_id = modules[0]["id"]
    await create_application("Painel Ops", "Dashboard", module_id=module_id, is_active=True)
    apps = await list_applications()
    app_id = apps[0]["id"]

    # Usuário comum recebe permissão
    await create_user("joao", "secret1", full_name="Joao", email="joao@example.com", role="USER")
    users_perm_msg = await create_permission(user_id=1, module_id=module_id, application_id=app_id)
    assert users_perm_msg is None
    perms = await list_permissions()
    assert len(perms) == 1

    # Duplicada deve falhar
    with pytest.raises(ValueError):
        await create_permission(user_id=1, module_id=module_id, application_id=app_id)

    # Usuário ADMIN não precisa de permissão (retorna mensagem)
    await create_user("maria", "secret1", full_name="Maria", email="maria@example.com", role="ADMIN")
    msg = await create_permission(user_id=2, module_id=module_id, application_id=app_id)
    assert msg is not None and "ADMIN" in msg

    # Aplicação deve pertencer ao módulo
    await create_module("Outro", "", is_active=True)
    other_module = (await list_modules())[-1]["id"]
    with pytest.raises(ValueError):
        await create_permission(user_id=1, module_id=other_module, application_id=app_id)
