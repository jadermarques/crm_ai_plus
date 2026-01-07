from __future__ import annotations

from typing import Any

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, func, select, update
from sqlalchemy.dialects.postgresql import VARCHAR

from src.core.database import get_engine, get_sessionmaker
from src.core.db_schema import ensure_audit_columns

metadata = MetaData()

chatwoot_params = Table(
    "chatwoot_params",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("chatwoot_url", String(500), nullable=False),
    Column("chatwoot_api_token", VARCHAR(500), nullable=False),
    Column("chatwoot_account_id", Integer, nullable=False),
    Column("chatwoot_version", String(100), nullable=False),
    Column(
        "data_hora_inclusao",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "data_hora_alteracao",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
)


async def ensure_table() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    await ensure_audit_columns("chatwoot_params")


async def get_params() -> dict[str, Any] | None:
    await ensure_table()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(select(chatwoot_params).limit(1))
        row = result.mappings().first()
        return dict(row) if row else None


async def upsert_params(
    *,
    chatwoot_url: str,
    chatwoot_api_token: str,
    chatwoot_account_id: int,
    chatwoot_version: str,
) -> None:
    if not (chatwoot_url and chatwoot_api_token and chatwoot_version):
        raise ValueError("Todos os campos são obrigatórios.")
    await ensure_table()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        existing = await session.execute(select(chatwoot_params.c.id).limit(1))
        row = existing.first()
        if row:
            await session.execute(
                update(chatwoot_params)
                .where(chatwoot_params.c.id == row.id)
                .values(
                    chatwoot_url=chatwoot_url,
                    chatwoot_api_token=chatwoot_api_token,
                    chatwoot_account_id=chatwoot_account_id,
                    chatwoot_version=chatwoot_version,
                )
            )
        else:
            await session.execute(
                chatwoot_params.insert().values(
                    chatwoot_url=chatwoot_url,
                    chatwoot_api_token=chatwoot_api_token,
                    chatwoot_account_id=chatwoot_account_id,
                    chatwoot_version=chatwoot_version,
                )
            )
        await session.commit()
