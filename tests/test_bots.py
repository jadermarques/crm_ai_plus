from __future__ import annotations

import logging

import pytest

from src.core.agents import create_agent, list_agents
from src.core.bots import (
    create_bot,
    delete_bot,
    ensure_tables,
    list_bot_agents,
    list_bots,
    replace_bot_agents,
    update_bot,
)

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_create_and_update_bot() -> None:
    await ensure_tables()
    logger.info("Criando bot para validar cadastro")
    bot_id = await create_bot(
        nome="Bot Atendimento",
        descricao="Bot principal",
        versao=1,
        ativo=True,
    )
    bots = await list_bots()
    created = next(b for b in bots if b["id"] == bot_id)
    assert created["nome"] == "Bot Atendimento"
    assert created["versao"] == 1

    logger.info("Nome duplicado deve falhar")
    with pytest.raises(ValueError):
        await create_bot(nome="bot atendimento", descricao="Duplicado", versao=1, ativo=True)

    logger.info("Atualizar com versao igual deve falhar")
    with pytest.raises(ValueError):
        await update_bot(
            bot_id,
            nome="Bot Atendimento",
            descricao="Sem alteracao",
            versao=1,
            ativo=True,
        )

    logger.info("Atualizando bot")
    await update_bot(
        bot_id,
        nome="Bot Atendimento 2",
        descricao="Atualizado",
        versao=2,
        ativo=False,
    )
    updated = next(b for b in await list_bots() if b["id"] == bot_id)
    assert updated["nome"] == "Bot Atendimento 2"
    assert updated["ativo"] is False
    assert updated["versao"] == 2


@pytest.mark.asyncio
async def test_replace_bot_agents() -> None:
    await ensure_tables()
    logger.info("Criando agentes para vinculo")
    await create_agent(
        nome="Agente Triagem Teste",
        descricao="Triagem",
        system_prompt="Triagem",
        ativo=True,
        agente_orquestrador=True,
        model="gpt-4o-mini",
        papel="triagem",
    )
    await create_agent(
        nome="Agente Comercial Teste",
        descricao="Comercial",
        system_prompt="Comercial",
        ativo=True,
        model="gpt-4o-mini",
        papel="comercial",
    )

    bots_id = await create_bot(
        nome="Bot Vendas",
        descricao="Bot vendas",
        versao=1,
        ativo=True,
    )
    agents = await list_bot_agents(bots_id)
    assert agents == []

    logger.info("Vinculando agentes ao bot")
    agents_data = await list_agents()
    triagem_id = next(a for a in agents_data if a["nome"] == "Agente Triagem Teste")["id"]
    comercial_id = next(a for a in agents_data if a["nome"] == "Agente Comercial Teste")["id"]

    await replace_bot_agents(
        bots_id,
        [comercial_id],
        triagem_id,
    )
    links = await list_bot_agents(bots_id)
    assert len(links) == 2
    roles = {link["role"] for link in links}
    assert "orquestrador" in roles
    assert "vinculado" in roles
    linked_ids = {link["agent_id"] for link in links}
    assert triagem_id in linked_ids
    assert comercial_id in linked_ids

    logger.info("Vinculo com agente inexistente deve falhar")
    with pytest.raises(ValueError):
        await replace_bot_agents(bots_id, [9999], triagem_id)

    logger.info("Vinculo sem orquestrador deve falhar")
    with pytest.raises(ValueError):
        await replace_bot_agents(bots_id, [comercial_id], None)


@pytest.mark.asyncio
async def test_delete_bot() -> None:
    await ensure_tables()
    logger.info("Criando bot para exclusao")
    bot_id = await create_bot(nome="Bot Temporario", descricao="Teste", versao=1, ativo=True)

    logger.info("Excluindo bot")
    await delete_bot(bot_id)
    bots = await list_bots()
    assert all(b["id"] != bot_id for b in bots)

    logger.info("Excluindo bot inexistente deve falhar")
    with pytest.raises(ValueError):
        await delete_bot(9999)
