from __future__ import annotations

from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    func,
    select,
    text,
)

from src.core.database import get_engine, get_sessionmaker
from src.core.db_schema import ensure_audit_columns

metadata = MetaData()

providers = Table(
    "ia_providers",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(255), unique=True, nullable=False),
    Column("is_active", Boolean, nullable=False, server_default=text("TRUE")),
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

models = Table(
    "ia_models",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("provider_id", Integer, ForeignKey("ia_providers.id"), nullable=False),
    Column("name", String(255), nullable=False),
    Column("is_active", Boolean, nullable=False, server_default=text("TRUE")),
    Column("cost_input", Numeric(18, 6), nullable=True),
    Column("cost_output", Numeric(18, 6), nullable=True),
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


async def ensure_tables() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_ia_providers_name ON ia_providers (lower(name))"))
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_ia_models_provider_name "
                "ON ia_models (provider_id, lower(name))"
            )
        )
    await ensure_audit_columns("ia_providers")
    await ensure_audit_columns("ia_models")


def _validate_name(value: str, field: str) -> str:
    name = (value or "").strip()
    if not name:
        raise ValueError(f"Informe o {field}.")
    if len(name) > 255:
        raise ValueError(f"O {field} deve ter no máximo 255 caracteres.")
    return name


async def list_providers(include_inactive: bool = True) -> list[dict[str, Any]]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        query = select(providers).order_by(providers.c.name)
        if not include_inactive:
            query = query.where(providers.c.is_active.is_(True))
        result = await session.execute(query)
        return [dict(row) for row in result.mappings().all()]


async def create_provider(name: str, is_active: bool = True) -> None:
    await ensure_tables()
    name_clean = _validate_name(name, "nome do provedor")
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        exists = await session.execute(
            select(providers.c.id).where(func.lower(providers.c.name) == name_clean.lower())
        )
        if exists.first():
            raise ValueError("Provedor já existe.")
        await session.execute(
            providers.insert().values(
                name=name_clean,
                is_active=bool(is_active),
            )
        )
        await session.commit()


async def update_provider(provider_id: int, *, name: str, is_active: bool = True) -> None:
    await ensure_tables()
    name_clean = _validate_name(name, "nome do provedor")
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        exists = await session.execute(
            select(providers.c.id).where(
                func.lower(providers.c.name) == name_clean.lower(),
                providers.c.id != provider_id,
            )
        )
        if exists.first():
            raise ValueError("Provedor já existe.")
        result = await session.execute(
            providers.update()
            .where(providers.c.id == provider_id)
            .values(
                name=name_clean,
                is_active=bool(is_active),
            )
        )
        if result.rowcount == 0:
            raise ValueError("Provedor não encontrado.")
        await session.commit()


async def list_models(include_inactive: bool = True) -> list[dict[str, Any]]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        query = (
            select(
                models.c.id,
                models.c.name,
                models.c.is_active,
                models.c.cost_input,
                models.c.cost_output,
                models.c.provider_id,
                providers.c.name.label("provider_name"),
            )
            .select_from(models.join(providers, models.c.provider_id == providers.c.id))
            .order_by(providers.c.name, models.c.name)
        )
        if not include_inactive:
            query = query.where(models.c.is_active.is_(True), providers.c.is_active.is_(True))
        result = await session.execute(query)
        return [dict(row) for row in result.mappings().all()]


async def _get_provider(session, provider_id: int) -> dict[str, Any] | None:
    result = await session.execute(select(providers).where(providers.c.id == provider_id))
    row = result.mappings().first()
    return dict(row) if row else None


async def create_model(
    *,
    provider_id: int,
    name: str,
    is_active: bool = True,
    cost_input: float | None = None,
    cost_output: float | None = None,
) -> None:
    await ensure_tables()
    name_clean = _validate_name(name, "nome do modelo")
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        provider_row = await _get_provider(session, provider_id)
        if provider_row is None:
            raise ValueError("Provedor não encontrado.")

        exists = await session.execute(
            select(models.c.id).where(
                models.c.provider_id == provider_id,
                func.lower(models.c.name) == name_clean.lower(),
            )
        )
        if exists.first():
            raise ValueError("Modelo já existe para este provedor.")

        await session.execute(
            models.insert().values(
                provider_id=provider_id,
                name=name_clean,
                is_active=bool(is_active),
                cost_input=cost_input,
                cost_output=cost_output,
            )
        )
        await session.commit()


async def update_model(
    model_id: int,
    *,
    provider_id: int,
    name: str,
    is_active: bool = True,
    cost_input: float | None = None,
    cost_output: float | None = None,
) -> None:
    await ensure_tables()
    name_clean = _validate_name(name, "nome do modelo")
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        provider_row = await _get_provider(session, provider_id)
        if provider_row is None:
            raise ValueError("Provedor não encontrado.")

        exists = await session.execute(
            select(models.c.id).where(
                models.c.provider_id == provider_id,
                func.lower(models.c.name) == name_clean.lower(),
                models.c.id != model_id,
            )
        )
        if exists.first():
            raise ValueError("Modelo já existe para este provedor.")

        result = await session.execute(
            models.update()
            .where(models.c.id == model_id)
            .values(
                provider_id=provider_id,
                name=name_clean,
                is_active=bool(is_active),
                cost_input=cost_input,
                cost_output=cost_output,
            )
        )
        if result.rowcount == 0:
            raise ValueError("Modelo não encontrado.")
        await session.commit()
