"""
Bots Module - Bot and Bot-Agent Relationship Management.

This module provides functions for managing bots and their associated agents
in the database. A bot is a configured AI assistant that uses multiple
specialized agents for handling different types of requests.

Tables:
    bots: Bot configuration (name, description, persona, version)
    bot_agents: Many-to-many relationship between bots and agents

Functions:
    ensure_tables: Create database tables if not exists
    list_bots: List all bots
    create_bot: Create a new bot
    update_bot: Update an existing bot
    delete_bot: Delete a bot
    replace_bot_agents: Replace all agents linked to a bot
    list_bot_agents: List agents linked to a bot

Example:
    >>> from src.core.bots import create_bot, replace_bot_agents
    >>> bot_id = await create_bot(nome="Meu Bot", descricao="Bot de teste")
    >>> await replace_bot_agents(bot_id, agent_ids=[1, 2, 3], orchestrator_agent_id=1)
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
    MetaData,
    String,
    Table,
    Text,
    func,
    select,
    text,
)

from src.core.agents import agents as agents_table
from src.core.agents import ensure_tables as ensure_agents_tables
from src.core.database import get_engine, get_sessionmaker
from src.core.db_schema import ensure_audit_columns

metadata = MetaData()

bots = Table(
    "bots",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("pk", String(64), unique=True, nullable=False),
    Column("nome", String(255), nullable=False),
    Column("descricao", Text, nullable=True),
    Column("versao", Integer, nullable=False, server_default=text("1")),
    Column("ativo", Boolean, nullable=False, server_default=text("TRUE")),
    Column("persona", Text, nullable=True),
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

bot_agents = Table(
    "bot_agents",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("bot_id", Integer, ForeignKey("bots.id"), nullable=False),
    Column("agent_id", Integer, ForeignKey(agents_table.c.id), nullable=False),
    Column("role", String(64), nullable=False),
    Column("ativo", Boolean, nullable=False, server_default=text("TRUE")),
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
        raise ValueError("Informe o nome do bot.")
    if len(name) > 255:
        raise ValueError("O nome do bot deve ter no maximo 255 caracteres.")
    return name


def _normalize_version(value: int | float | None) -> int:
    if value is None:
        return 1
    if isinstance(value, float) and not value.is_integer():
        raise ValueError("A versao deve ser um numero inteiro.")
    version = int(value)
    if version < 1:
        raise ValueError("A versao deve ser maior ou igual a 1.")
    return version


def _normalize_role(value: str) -> str:
    role = (value or "").strip()
    roles = {"orquestrador", "vinculado"}
    if role not in roles:
        raise ValueError("Informe um papel de agente valido.")
    return role


async def ensure_tables() -> None:
    await ensure_agents_tables()
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        await conn.execute(
            text("ALTER TABLE bots ADD COLUMN IF NOT EXISTS versao INTEGER NOT NULL DEFAULT 1")
        )
        await conn.execute(text("UPDATE bots SET versao = 1 WHERE versao IS NULL"))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_bots_pk ON bots (pk)"))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_bots_name ON bots (lower(nome))"))
        await conn.execute(text("DROP INDEX IF EXISTS ux_bot_agents_role"))
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_bot_agents_bot_agent "
                "ON bot_agents (bot_id, agent_id)"
            )
        )
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_bot_agents_bot_id ON bot_agents (bot_id)"))
    await ensure_audit_columns("bots")
    await ensure_audit_columns("bot_agents")


async def list_bots(include_inactive: bool = True) -> list[dict[str, Any]]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        query = select(bots).order_by(bots.c.nome)
        if not include_inactive:
            query = query.where(bots.c.ativo.is_(True))
        result = await session.execute(query)
        return [dict(row) for row in result.mappings().all()]


async def list_bot_agent_counts() -> dict[int, int]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        query = select(bot_agents.c.bot_id, func.count().label("total")).group_by(bot_agents.c.bot_id)
        result = await session.execute(query)
        return {row.bot_id: int(row.total) for row in result}


async def _ensure_unique_name(session, nome: str, ignore_id: int | None = None) -> None:
    query = select(bots.c.id).where(func.lower(bots.c.nome) == nome.lower())
    if ignore_id is not None:
        query = query.where(bots.c.id != ignore_id)
    exists = await session.execute(query)
    if exists.first():
        raise ValueError("Ja existe um bot com este nome.")


async def _ensure_bot_exists(session, bot_id: int) -> None:
    result = await session.execute(select(bots.c.id).where(bots.c.id == bot_id))
    if result.first() is None:
        raise ValueError("Bot nao encontrado.")


async def _ensure_agents_exist(session, agent_ids: list[int]) -> None:
    if not agent_ids:
        return
    # This function still uses Core-style query for agents_table, needs to be updated to ORM if desired
    result = await session.execute(
        select(agents_table.c.id).where(agents_table.c.id.in_(agent_ids))
    )
    found = {row[0] for row in result.all()}
    missing = [agent_id for agent_id in agent_ids if agent_id not in found]
    if missing:
        raise ValueError("Agente nao encontrado.")


async def create_bot(
    *,
    nome: str,
    descricao: str | None,
    versao: int | float | None = None,
    ativo: bool = True,
    persona: str | None = None,
) -> int:
    await ensure_tables()
    nome_clean = _normalize_name(nome)
    versao_clean = _normalize_version(versao)
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await _ensure_unique_name(session, nome_clean)
        pk = uuid4().hex
        await session.execute(
            bots.insert().values(
                pk=pk,
                nome=nome_clean,
                descricao=(descricao or "").strip() or None,
                versao=versao_clean,
                ativo=bool(ativo),
                persona=persona,
            )
        )
        await session.commit()
        result = await session.execute(
            select(bots.c.id).where(bots.c.pk == pk)
        )
        return int(result.scalar_one())


async def update_bot(
    bot_id: int,
    *,
    nome: str | None = None,
    descricao: str | None = None,
    versao: int | float | None = None,
    ativo: bool | None = None,
    persona: str | None = None,
) -> None:
    await ensure_tables()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        current_bot = await session.execute(
            select(bots.c.versao, bots.c.nome).where(bots.c.id == bot_id)
        )
        bot_row = current_bot.first()
        if not bot_row:
            raise ValueError(f"Bot {bot_id} nao encontrado.")
        
        current_version = bot_row.versao
        current_name = bot_row.nome
        
        values = {}
        if nome is not None:
            nome_clean = _normalize_name(nome)
            if nome_clean.lower() != current_name.lower():
                await _ensure_unique_name(session, nome_clean, ignore_id=bot_id)
            values["nome"] = nome_clean
            
        if descricao is not None:
            values["descricao"] = (descricao or "").strip() or None
            
        if versao is not None:
            versao_clean = _normalize_version(versao)
            if versao_clean <= current_version:
                 raise ValueError(f"A versao deve ser maior que a atual ({current_version}).")
            values["versao"] = versao_clean
            
        if ativo is not None:
            values["ativo"] = bool(ativo)
            
        if persona is not None:
            values["persona"] = persona
            
        if not values:
            return

        await session.execute(
            bots.update().where(bots.c.id == bot_id).values(**values)
        )
        await session.commit()


async def delete_bot(bot_id: int) -> None:
    await ensure_tables()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await _ensure_bot_exists(session, bot_id)
        await session.execute(bot_agents.delete().where(bot_agents.c.bot_id == bot_id))
        await session.execute(bots.delete().where(bots.c.id == bot_id))
        await session.commit()


async def list_bot_agents(bot_id: int) -> list[dict[str, Any]]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        query = (
            select(
                bot_agents.c.id,
                bot_agents.c.role,
                bot_agents.c.ativo,
                agents_table.c.id.label("agent_id"),
                agents_table.c.nome.label("agent_nome"),
                agents_table.c.versao.label("agent_versao"),
                agents_table.c.ativo.label("agent_ativo"),
                agents_table.c.agente_orquestrador.label("agent_orquestrador"),
            )
            .select_from(bot_agents.join(agents_table, bot_agents.c.agent_id == agents_table.c.id))
            .where(bot_agents.c.bot_id == bot_id)
            .order_by(bot_agents.c.role, agents_table.c.nome)
        )
        result = await session.execute(query)
        return [dict(row) for row in result.mappings().all()]


async def replace_bot_agents(
    bot_id: int,
    agent_ids: list[int],
    orchestrator_agent_id: int,
) -> None:
    await ensure_tables()
    if orchestrator_agent_id is None:
        raise ValueError("Informe um agente orquestrador.")
    orchestrator_id = int(orchestrator_agent_id)
    unique_agent_ids = {int(agent_id) for agent_id in agent_ids}
    unique_agent_ids.add(orchestrator_id)

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await _ensure_bot_exists(session, bot_id)
        await _ensure_agents_exist(session, list(unique_agent_ids))
        await session.execute(bot_agents.delete().where(bot_agents.c.bot_id == bot_id))
        if unique_agent_ids:
            payload = []
            for agent_id in unique_agent_ids:
                role = "orquestrador" if agent_id == orchestrator_id else "vinculado"
                payload.append(
                    {
                        "bot_id": bot_id,
                        "agent_id": agent_id,
                        "role": _normalize_role(role),
                        "ativo": True,
                    }
                )
            if payload:
                await session.execute(bot_agents.insert().values(payload))
        await session.commit()
