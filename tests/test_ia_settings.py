from __future__ import annotations

import pytest

from src.core.ia_settings import (
    create_model,
    create_provider,
    ensure_tables,
    list_models,
    list_providers,
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
