"""
Agents Module - Agent CRUD Operations.

This module provides functions for managing AI agents in the database,
including creation, update, deletion, and listing operations.

Functions:
    ensure_tables: Create database tables if not exists
    ensure_default_agents: Create default system agents
    list_agents: List all agents
    create_agent: Create a new agent
    update_agent: Update an existing agent
    delete_agent: Delete an agent

Example:
    >>> from src.core.agents import list_agents, create_agent
    >>> agents = await list_agents()
    >>> new_agent = await create_agent(
    ...     nome="Novo Agente",
    ...     system_prompt="Prompt...",
    ...     model="gpt-4o-mini"
    ... )
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
    select,
    text,
)

from src.core.agent_architecture import (
    AGENT_DESCRIPTIONS,
    AGENT_DISPLAY_NAMES,
    AGENT_SYSTEM_PROMPTS,
    DEFAULT_AGENT_ORDER,
    AgentRole,
    resolve_role_label,
)
from src.core.database import get_engine, get_sessionmaker
from src.core.db_schema import ensure_audit_columns
from src.core.rag_management import ensure_tables as ensure_rags_tables
from src.core.rag_management import rags

metadata = rags.metadata

agents = Table(

    "agents",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("pk", String(64), unique=True, nullable=False),
    Column("nome", String(255), nullable=False),
    Column("descricao", Text, nullable=True),
    Column("system_prompt", Text, nullable=False),
    Column("versao", Integer, nullable=False, server_default=text("1")),
    Column("ativo", Boolean, nullable=False, server_default=text("TRUE")),
    Column("agente_orquestrador", Boolean, nullable=False, server_default=text("FALSE")),
    Column("papel", String(50), nullable=True),
    Column("model", String(255), nullable=False),
    Column("rag_id", Integer, ForeignKey("rags.id"), nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("data_hora_inclusao", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column(
        "data_hora_alteracao",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
)


def _normalize_name(value: str) -> str:
    name = (value or "").strip()
    if not name:
        raise ValueError("Informe o nome do agente.")
    if len(name) > 255:
        raise ValueError("O nome do agente deve ter no máximo 255 caracteres.")
    return name


def _normalize_prompt(value: str) -> str:
    prompt = (value or "").strip()
    if not prompt:
        raise ValueError("Informe o prompt do agente.")
    return prompt


def _normalize_model(value: str) -> str:
    model = (value or "").strip()
    if not model:
        raise ValueError("Informe o modelo do agente.")
    if len(model) > 255:
        raise ValueError("O modelo deve ter no máximo 255 caracteres.")
    return model


def _normalize_role(value: str | AgentRole | None) -> str:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError("Informe o papel do agente.")
    if isinstance(value, AgentRole):
        return value.value
    role = resolve_role_label(value)
    if role is None:
        raise ValueError("Papel do agente inválido.")
    return role.value


def _normalize_version(value: int | float | None) -> int:
    if value is None:
        return 1
    if isinstance(value, float) and not value.is_integer():
        raise ValueError("A versão deve ser um número inteiro.")
    version = int(value)
    if version < 1:
        raise ValueError("A versão deve ser maior ou igual a 1.")
    return version


async def ensure_tables() -> None:
    await ensure_rags_tables()
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        await conn.execute(
            text("ALTER TABLE agents ADD COLUMN IF NOT EXISTS model VARCHAR(255)")
        )
        await conn.execute(
            text("ALTER TABLE agents ADD COLUMN IF NOT EXISTS versao INTEGER NOT NULL DEFAULT 1")
        )
        await conn.execute(
            text(
                "ALTER TABLE agents ADD COLUMN IF NOT EXISTS agente_orquestrador "
                "BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
        await conn.execute(
            text("ALTER TABLE agents ADD COLUMN IF NOT EXISTS papel VARCHAR(50)")
        )
        await conn.execute(text("UPDATE agents SET versao = 1 WHERE versao IS NULL"))
        await conn.execute(
            text("UPDATE agents SET agente_orquestrador = FALSE WHERE agente_orquestrador IS NULL")
        )
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_agents_pk ON agents (pk)"))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_agents_name ON agents (lower(nome))"))
        await conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ux_agents_name_version ON agents (lower(nome), versao)")
        )
    await ensure_audit_columns("agents")
    await _backfill_agent_roles()


async def _backfill_agent_roles() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(
            select(agents.c.id, agents.c.nome, agents.c.papel)
        )
        updates: list[dict[str, Any]] = []
        for row in result.mappings().all():
            if (row.get("papel") or "").strip():
                continue
            role = resolve_role_label(row.get("nome"))
            if role is None:
                continue
            updates.append({"id": row["id"], "papel": role.value})

        # Otimizacao: Se houver muitos updates, usar executemany ou similar.
        # Como depende de logica python por linha, mantemos loop de updates
        # mas compartilham a mesma transacao.
        for update in updates:
            await session.execute(
                agents.update()
                .where(agents.c.id == update["id"])
                .values(papel=update["papel"])
            )
        if updates:
            await session.commit()


async def ensure_default_agents(model_name: str | None) -> None:
    await ensure_tables()
    if not model_name:
        return
    model_value = _normalize_model(model_name)

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(select(agents.c.id, agents.c.nome, agents.c.papel))
        rows = result.mappings().all()
        existing_roles = {row["papel"] for row in rows if (row.get("papel") or "").strip()}
        existing_names = {row["nome"].lower(): row for row in rows if row.get("nome")}

        updates = 0
        payloads = []
        for role in DEFAULT_AGENT_ORDER:
            if role.value in existing_roles:
                continue
            display_name = AGENT_DISPLAY_NAMES[role]
            existing_row = existing_names.get(display_name.lower())
            if existing_row and not (existing_row.get("papel") or "").strip():
                await session.execute(
                    agents.update()
                    .where(agents.c.id == existing_row["id"])
                    .values(papel=role.value)
                )
                existing_roles.add(role.value)
                updates += 1
                continue
            if existing_row:
                continue
            payloads.append(
                {
                    "pk": uuid4().hex,
                    "nome": _normalize_name(display_name),
                    "descricao": (AGENT_DESCRIPTIONS.get(role) or "").strip() or None,
                    "system_prompt": _normalize_prompt(AGENT_SYSTEM_PROMPTS[role]),
                    "versao": 1,
                    "ativo": True,
                    "agente_orquestrador": role == AgentRole.TRIAGEM,
                    "papel": role.value,
                    "model": model_value,
                    "rag_id": None,
                }
            )

        if payloads:
            await session.execute(agents.insert().values(payloads))
        if payloads or updates:
            await session.commit()


async def list_agents(include_inactive: bool = True) -> list[dict[str, Any]]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        j = agents.outerjoin(rags, agents.c.rag_id == rags.c.id)
        query = (
            select(
                agents.c.id,
                agents.c.pk,
                agents.c.nome,
                agents.c.descricao,
                agents.c.system_prompt,
                agents.c.versao,
                agents.c.ativo,
                agents.c.agente_orquestrador,
                agents.c.papel,
                agents.c.model,
                agents.c.rag_id,
                rags.c.nome.label("rag_nome"),
                rags.c.rag_id.label("rag_identificador"),
                rags.c.provedor_rag.label("rag_provedor"),
                rags.c.data_hora_alteracao.label("rag_last_sync"),
            )
            .select_from(j)
            .order_by(agents.c.nome)
        )
        if not include_inactive:
            query = query.where(agents.c.ativo.is_(True))
        result = await session.execute(query)
        return [dict(row) for row in result.mappings().all()]


async def _ensure_unique_name(session, nome: str, ignore_id: int | None = None) -> None:
    query = select(agents.c.id).where(func.lower(agents.c.nome) == nome.lower())
    if ignore_id is not None:
        query = query.where(agents.c.id != ignore_id)
    exists = await session.execute(query)
    if exists.first():
        raise ValueError("Já existe um agente com este nome.")


async def _ensure_rag_exists(session, rag_id: int | None) -> None:
    if rag_id is None:
        return
    result = await session.execute(select(rags.c.id).where(rags.c.id == rag_id))
    if result.first() is None:
        raise ValueError("RAG não encontrado.")


async def create_agent(
    *,
    nome: str,
    descricao: str | None,
    system_prompt: str,
    model: str,
    versao: int | float | None = None,
    ativo: bool = True,
    agente_orquestrador: bool = False,
    papel: str | AgentRole | None = None,
    rag_id: int | None = None,
) -> None:
    await ensure_tables()
    nome_clean = _normalize_name(nome)
    prompt_clean = _normalize_prompt(system_prompt)
    versao_clean = _normalize_version(versao)
    model_clean = _normalize_model(model)
    papel_clean = _normalize_role(papel)
    pk_value = uuid4().hex

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await _ensure_unique_name(session, nome_clean)
        await _ensure_rag_exists(session, rag_id)
        await session.execute(
            agents.insert().values(
                pk=pk_value,
                nome=nome_clean,
                descricao=(descricao or "").strip() or None,
                system_prompt=prompt_clean,
                versao=versao_clean,
                ativo=bool(ativo),
                agente_orquestrador=bool(agente_orquestrador),
                papel=papel_clean,
                model=model_clean,
                rag_id=rag_id,
            )
        )
        await session.commit()


async def delete_agent(agent_id: int) -> None:
    await ensure_tables()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(select(agents.c.id).where(agents.c.id == agent_id))
        if result.first() is None:
            raise ValueError("Agente não encontrado.")
        await session.execute(agents.delete().where(agents.c.id == agent_id))
        await session.commit()


async def update_agent(
    agent_id: int,
    *,
    nome: str,
    descricao: str | None,
    system_prompt: str,
    model: str,
    versao: int | float | None,
    ativo: bool = True,
    agente_orquestrador: bool = False,
    papel: str | AgentRole | None = None,
    rag_id: int | None = None,
) -> None:
    await ensure_tables()
    nome_clean = _normalize_name(nome)
    prompt_clean = _normalize_prompt(system_prompt)
    versao_clean = _normalize_version(versao)
    model_clean = _normalize_model(model)
    papel_clean = _normalize_role(papel)

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        current_version_result = await session.execute(
            select(agents.c.versao).where(agents.c.id == agent_id)
        )
        current_version = current_version_result.scalar_one_or_none()
        if current_version is None:
            raise ValueError("Agente não encontrado.")
        if versao_clean <= current_version:
            raise ValueError(f"A versão deve ser maior que a atual ({current_version}).")
        await _ensure_unique_name(session, nome_clean, ignore_id=agent_id)
        await _ensure_rag_exists(session, rag_id)
        await session.execute(
            agents.update()
            .where(agents.c.id == agent_id)
            .values(
                nome=nome_clean,
                descricao=(descricao or "").strip() or None,
                system_prompt=prompt_clean,
                versao=versao_clean,
                ativo=bool(ativo),
                agente_orquestrador=bool(agente_orquestrador),
                papel=papel_clean,
                model=model_clean,
                rag_id=rag_id,
            )
        )
        await session.commit()
