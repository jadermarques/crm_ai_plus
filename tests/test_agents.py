from __future__ import annotations

import logging

import pytest

from src.core.agents import (
    create_agent,
    delete_agent,
    ensure_tables,
    ensure_default_agents,
    list_agents,
    update_agent,
)
from src.core.agent_architecture import DEFAULT_AGENT_ORDER
from src.core.rag_management import RAG_PROVIDER_OPENAI, create_rag

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_create_agent_and_unique_name() -> None:
    await ensure_tables()
    logger.info("Criando agente base para validar cadastro")
    await create_agent(
        nome="Agente de Suporte",
        descricao="Atendimento inicial",
        system_prompt="Ajude o cliente com triagem.",
        ativo=True,
        model="gpt-4o-mini",
        papel="triagem",
        rag_id=None,
    )

    agents = await list_agents()
    created = next(a for a in agents if a["nome"] == "Agente de Suporte")
    assert created["versao"] == 1
    assert created["agente_orquestrador"] is False
    assert created["papel"] == "triagem"

    logger.info("Tentando criar agente com nome duplicado deve falhar")
    with pytest.raises(ValueError):
        await create_agent(
            nome="agente de suporte",
            descricao="Duplicado",
            system_prompt="Outro prompt",
            ativo=True,
            model="gpt-4o-mini",
            papel="triagem",
        )

    logger.info("Papel invalido deve falhar")
    with pytest.raises(ValueError):
        await create_agent(
            nome="Agente Invalido",
            descricao="Papel invalido",
            system_prompt="Prompt",
            ativo=True,
            model="gpt-4o-mini",
            papel="invalido",
        )


@pytest.mark.asyncio
async def test_agent_rag_link_and_validation() -> None:
    await ensure_tables()
    logger.info("Criando RAG para associar ao agente")
    rag = await create_rag(
        nome="Base Atendimento",
        rag_id="vs_support",
        descricao="Base de conhecimento",
        ativo=True,
        provedor_rag=RAG_PROVIDER_OPENAI,
    )

    logger.info("Criando agente com RAG associado")
    await create_agent(
        nome="Agente FAQ",
        descricao="FAQ com RAG",
        system_prompt="Responda usando a base.",
        ativo=True,
        model="gpt-4o-mini",
        rag_id=rag["id"],
        agente_orquestrador=True,
        papel="guia_unidades",
    )
    agents = await list_agents()
    agent = next(a for a in agents if a["nome"] == "Agente FAQ")
    assert agent["rag_id"] == rag["id"]
    assert agent["rag_nome"] == "Base Atendimento"
    assert agent["versao"] == 1
    assert agent["agente_orquestrador"] is True
    assert agent["papel"] == "guia_unidades"

    logger.info("RAG inexistente deve falhar")
    with pytest.raises(ValueError):
        await create_agent(
            nome="Agente Invalido",
            descricao="RAG inexistente",
            system_prompt="Prompt",
            ativo=True,
            model="gpt-4o-mini",
            papel="triagem",
            rag_id=999,
        )


@pytest.mark.asyncio
async def test_update_agent_and_temperature_validation() -> None:
    await ensure_tables()
    logger.info("Criando agentes para validar update")
    await create_agent(
        nome="Agente A",
        descricao="Primeiro",
        system_prompt="Prompt A",
        ativo=True,
        model="gpt-4o-mini",
        papel="triagem",
    )
    await create_agent(
        nome="Agente B",
        descricao="Segundo",
        system_prompt="Prompt B",
        ativo=True,
        model="gpt-4o-mini",
        papel="comercial",
    )

    agents = await list_agents()
    agent_b = next(a for a in agents if a["nome"] == "Agente B")

    logger.info("Atualizar com versão igual deve falhar")
    with pytest.raises(ValueError):
        await update_agent(
            agent_b["id"],
            nome="Agente B",
            descricao="Sem alteração",
            system_prompt="Prompt B",
            model="gpt-4o-mini",
            versao=1,
            ativo=True,
            papel="comercial",
        )

    logger.info("Atualizar com nome duplicado deve falhar")
    with pytest.raises(ValueError):
        await update_agent(
            agent_b["id"],
            nome="Agente A",
            descricao="Duplicado",
            system_prompt="Prompt B",
            model="gpt-4o-mini",
            versao=2,
            ativo=True,
            papel="comercial",
        )

    logger.info("Modelo obrigatório deve ser validado")
    with pytest.raises(ValueError):
        await create_agent(
            nome="Agente Sem Modelo",
            descricao="Invalido",
            system_prompt="Prompt",
            ativo=True,
            model="",
            papel="comercial",
        )

    logger.info("Papel inválido no update deve falhar")
    with pytest.raises(ValueError):
        await update_agent(
            agent_b["id"],
            nome="Agente B",
            descricao="Sem alteração",
            system_prompt="Prompt B",
            model="gpt-4o-mini",
            versao=2,
            ativo=True,
            papel="invalido",
        )

    logger.info("Atualizando agente com modelo obrigatório")
    await update_agent(
        agent_b["id"],
        nome="Agente B Atualizado",
        descricao="Atualizado",
        system_prompt="Prompt atualizado",
        model="gpt-4o-mini",
        versao=2,
        ativo=False,
        papel="comercial",
    )
    updated = next(a for a in (await list_agents()) if a["id"] == agent_b["id"])
    assert updated["nome"] == "Agente B Atualizado"
    assert updated["ativo"] is False
    assert updated["versao"] == 2


@pytest.mark.asyncio
async def test_delete_agent() -> None:
    await ensure_tables()
    logger.info("Criando agente para exclusao")
    await create_agent(
        nome="Agente Temporario",
        descricao="Apenas para teste",
        system_prompt="Prompt",
        ativo=True,
        model="gpt-4o-mini",
        papel="triagem",
    )
    agents = await list_agents()
    agent = next(a for a in agents if a["nome"] == "Agente Temporario")

    logger.info("Excluindo agente existente")
    await delete_agent(agent["id"])
    agents_after = await list_agents()
    assert all(a["id"] != agent["id"] for a in agents_after)

    logger.info("Excluindo agente inexistente deve falhar")
    with pytest.raises(ValueError):
        await delete_agent(9999)


@pytest.mark.asyncio
async def test_ensure_default_agents_creates_roles() -> None:
    await ensure_tables()
    logger.info("Garantindo agentes padrao com papeis definidos")
    await ensure_default_agents("gpt-4o-mini")
    agents = await list_agents()
    roles = {agent.get("papel") for agent in agents}
    for role in DEFAULT_AGENT_ORDER:
        assert role.value in roles
