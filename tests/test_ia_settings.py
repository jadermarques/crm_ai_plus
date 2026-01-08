from __future__ import annotations

import pytest

from src.core.ia_settings import (
    create_model,
    create_provider,
    delete_model,
    ensure_tables,
    list_models,
    list_providers,
    test_model_connection,
    update_provider,
)


@pytest.mark.asyncio
async def test_create_and_update_provider() -> None:
    await ensure_tables()
    await create_provider("OpenAI", is_active=True)
    providers = await list_providers()
    assert providers[0]["name"] == "OpenAI"

    with pytest.raises(ValueError):
        await create_provider("OpenAI", is_active=True)

    await update_provider(providers[0]["id"], name="OpenAI Inc", is_active=False)
    updated = await list_providers(include_inactive=True)
    assert updated[0]["name"] == "OpenAI Inc"
    assert updated[0]["is_active"] is False


@pytest.mark.asyncio
async def test_create_model_requires_provider_and_unique() -> None:
    await ensure_tables()
    await create_provider("Anthropic", is_active=True)
    providers = await list_providers()
    provider_id = providers[0]["id"]

    await create_model(
        provider_id=provider_id,
        name="claude-3",
        is_active=True,
        cost_input=1.5,
        cost_output=2.0,
    )
    models = await list_models()
    assert models[0]["name"] == "claude-3"
    assert float(models[0]["cost_input"]) == 1.5

    with pytest.raises(ValueError):
        await create_model(provider_id=provider_id, name="claude-3", is_active=True)

    with pytest.raises(ValueError):
        await create_model(provider_id=999, name="ghost", is_active=True)


@pytest.mark.asyncio
async def test_delete_model() -> None:
    await ensure_tables()
    await create_provider("Mistral", is_active=True)
    provider_id = (await list_providers())[0]["id"]

    await create_model(
        provider_id=provider_id,
        name="mistral-small",
        is_active=True,
        cost_input=0.5,
        cost_output=0.7,
    )
    models = await list_models()
    model_id = models[0]["id"]

    await delete_model(model_id)
    assert await list_models() == []

    with pytest.raises(ValueError):
        await delete_model(999)


@pytest.mark.asyncio
async def test_model_connection_requires_key() -> None:
    ok, detail = await test_model_connection("Google", "gemini-1.5-flash")
    assert ok is False
    assert "GOOGLE_API_KEY" in detail
