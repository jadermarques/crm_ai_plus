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
        await conn.execute(text("UPDATE agents SET versao = 1 WHERE versao IS NULL"))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_agents_pk ON agents (pk)"))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_agents_name ON agents (lower(nome))"))
        await conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ux_agents_name_version ON agents (lower(nome), versao)")
        )
    await ensure_audit_columns("agents")


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
                agents.c.model,
                agents.c.rag_id,
                rags.c.nome.label("rag_nome"),
                rags.c.provedor_rag.label("rag_provedor"),
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
    rag_id: int | None = None,
) -> None:
    await ensure_tables()
    nome_clean = _normalize_name(nome)
    prompt_clean = _normalize_prompt(system_prompt)
    versao_clean = _normalize_version(versao)
    model_clean = _normalize_model(model)
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
                model=model_clean,
                rag_id=rag_id,
            )
        )
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
    rag_id: int | None = None,
) -> None:
    await ensure_tables()
    nome_clean = _normalize_name(nome)
    prompt_clean = _normalize_prompt(system_prompt)
    versao_clean = _normalize_version(versao)
    model_clean = _normalize_model(model)

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
                model=model_clean,
                rag_id=rag_id,
            )
        )
        await session.commit()
