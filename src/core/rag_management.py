"""
RAG Management Module - RAG Collection CRUD Operations.

This module provides functions for managing Retrieval Augmented Generation (RAG)
collections in the database. RAG collections are used to store and retrieve
contextual information for AI agents.

Providers:
    RAG_OPENAI: OpenAI Assistants API with file search
    RAG_CHROMADB: Self-hosted ChromaDB vector database

Functions:
    ensure_tables: Create database tables if not exists
    list_rags: List all RAG collections
    create_rag: Create a new RAG collection
    update_rag: Update an existing RAG collection
    delete_rag: Delete a RAG collection
    get_rag_by_id: Get RAG collection by database ID

Example:
    >>> from src.core.rag_management import create_rag, RAG_PROVIDER_CHROMADB
    >>> rag = await create_rag(
    ...     nome="Base de Conhecimento",
    ...     rag_id="knowledge-base",
    ...     provedor_rag=RAG_PROVIDER_CHROMADB
    ... )
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    and_,
    func,
    select,
    text,
)

from src.core.database import get_engine, get_sessionmaker
from src.core.db_schema import ensure_audit_columns

RAG_PROVIDER_OPENAI = "RAG_OPENAI"
RAG_PROVIDER_CHROMADB = "RAG_CHROMADB"
_VALID_PROVIDERS = {RAG_PROVIDER_OPENAI, RAG_PROVIDER_CHROMADB}

metadata = MetaData()

rags = Table(
    "rags",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("pk", String(64), unique=True, nullable=False),
    Column("nome", String(255), nullable=False),
    Column("rag_id", String(255), nullable=False),
    Column("descricao", Text, nullable=True),
    Column("ativo", Boolean, nullable=False, server_default=text("TRUE")),
    Column("provedor_rag", String(50), nullable=False),
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


def _normalize_text(value: str, field: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(f"Informe o {field}.")
    if len(cleaned) > 255:
        raise ValueError(f"O {field} deve ter no máximo 255 caracteres.")
    return cleaned


def _normalize_provider(provider: str) -> str:
    normalized = (provider or "").strip().upper()
    if normalized not in _VALID_PROVIDERS:
        raise ValueError("Provedor de RAG inválido.")
    return normalized


def _serialize(row: Any) -> dict[str, Any]:
    return dict(row)


async def ensure_tables() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_rags_pk ON rags (pk)"))
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_rags_provider_rag_id "
                "ON rags (lower(provedor_rag), lower(rag_id))"
            )
        )
    await ensure_audit_columns("rags")


async def list_rags(include_inactive: bool = True) -> list[dict[str, Any]]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        query = select(rags).order_by(rags.c.nome, rags.c.provedor_rag)
        if not include_inactive:
            query = query.where(rags.c.ativo.is_(True))
        result = await session.execute(query)
        return [_serialize(row) for row in result.mappings().all()]


async def get_rag_by_id(rag_db_id: int) -> dict[str, Any] | None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(select(rags).where(rags.c.id == rag_db_id))
        row = result.mappings().first()
        return _serialize(row) if row else None


async def _ensure_unique_rag(session, provedor_rag: str, rag_id: str, ignore_id: int | None = None) -> None:
    query = select(rags.c.id).where(
        and_(
            func.lower(rags.c.provedor_rag) == provedor_rag.lower(),
            func.lower(rags.c.rag_id) == rag_id.lower(),
        )
    )
    if ignore_id is not None:
        query = query.where(rags.c.id != ignore_id)
    exists = await session.execute(query)
    if exists.first():
        raise ValueError("Já existe um RAG com este provedor e RAG_ID.")


async def create_rag(
    *,
    nome: str,
    rag_id: str,
    descricao: str | None,
    ativo: bool = True,
    provedor_rag: str,
) -> dict[str, Any]:
    await ensure_tables()
    nome_clean = _normalize_text(nome, "nome")
    rag_id_clean = _normalize_text(rag_id, "RAG_ID")
    provedor_clean = _normalize_provider(provedor_rag)
    pk_value = uuid4().hex

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await _ensure_unique_rag(session, provedor_clean, rag_id_clean)
        result = await session.execute(
            rags.insert().values(
                pk=pk_value,
                nome=nome_clean,
                rag_id=rag_id_clean,
                descricao=(descricao or "").strip() or None,
                ativo=bool(ativo),
                provedor_rag=provedor_clean,
            )
        )
        await session.commit()
        inserted_id = result.inserted_primary_key[0] if result.inserted_primary_key else None
    if inserted_id is None:
        raise RuntimeError("Falha ao gerar identificadores do RAG.")
    created = await get_rag_by_id(int(inserted_id))
    if not created or not created.get("pk"):
        raise RuntimeError("Falha ao carregar o RAG criado.")
    return created


async def update_rag(
    rag_db_id: int,
    *,
    nome: str,
    rag_id: str,
    descricao: str | None,
    ativo: bool = True,
    provedor_rag: str,
) -> None:
    await ensure_tables()
    nome_clean = _normalize_text(nome, "nome")
    rag_id_clean = _normalize_text(rag_id, "RAG_ID")
    provedor_clean = _normalize_provider(provedor_rag)

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await _ensure_unique_rag(session, provedor_clean, rag_id_clean, ignore_id=rag_db_id)
        result = await session.execute(
            rags.update()
            .where(rags.c.id == rag_db_id)
            .values(
                nome=nome_clean,
                rag_id=rag_id_clean,
                descricao=(descricao or "").strip() or None,
                ativo=bool(ativo),
                provedor_rag=provedor_clean,
            )
        )
        if result.rowcount == 0:
            raise ValueError("RAG não encontrado.")
        await session.commit()


async def delete_rag(rag_db_id: int) -> None:
    await ensure_tables()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(rags.delete().where(rags.c.id == rag_db_id))
        if result.rowcount == 0:
            raise ValueError("RAG não encontrado.")
        await session.commit()
