"""
IA Settings Module - AI Provider and Model Management.

This module provides functions for managing AI providers (e.g., OpenAI, Google)
and their associated models. Used to configure and test which AI models are
available for use in the system.

Tables:
    ia_providers: AI provider configurations (OpenAI, Google, etc.)
    ia_models: Available models per provider with cost information

Functions:
    ensure_tables: Create database tables if not exists
    list_providers: List all AI providers
    create_provider: Create a new provider
    update_provider: Update a provider
    list_models: List all models
    create_model: Create a new model
    update_model: Update a model
    delete_model: Delete a model
    test_model_connection: Test if model is reachable

Example:
    >>> from src.core.ia_settings import list_models, create_model
    >>> models = await list_models()
    >>> await create_model(provider_id=1, name="gpt-4o-mini")
"""
from __future__ import annotations

from typing import Any
import os

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

from pydantic_ai import Agent

from src.core.config import get_settings
from src.core.database import get_engine, get_sessionmaker
from src.core.db_schema import ensure_audit_columns
from src.core.debug_logger import log_llm_interaction


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


async def delete_model(model_id: int) -> None:
    await ensure_tables()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(models.delete().where(models.c.id == model_id))
        if result.rowcount == 0:
            raise ValueError("Modelo não encontrado.")
        await session.commit()


def _detect_provider_kind(provider_name: str) -> str:
    normalized = (provider_name or "").strip().lower()
    if "openai" in normalized:
        return "openai"
    if "google" in normalized or "gemini" in normalized:
        return "gemini"
    if "vertex" in normalized:
        return "vertex"
    if "anthropic" in normalized:
        return "anthropic"
    if "groq" in normalized:
        return "groq"
    if "mistral" in normalized:
        return "mistral"
    if "cohere" in normalized:
        return "cohere"
    return "unknown"


def _get_provider_api_key(provider_kind: str) -> tuple[str | None, str | None]:
    settings = get_settings()
    if provider_kind == "openai":
        return settings.OPENAI_API_KEY, "OPENAI_API_KEY"
    if provider_kind == "gemini":
        api_key = settings.GOOGLE_API_KEY or settings.GEMINI_API_KEY or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        return api_key or None, "GOOGLE_API_KEY"
    if provider_kind == "anthropic":
        api_key = settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY")
        return api_key or None, "ANTHROPIC_API_KEY"
    if provider_kind == "groq":
        api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
        return api_key or None, "GROQ_API_KEY"
    if provider_kind == "mistral":
        api_key = settings.MISTRAL_API_KEY or os.getenv("MISTRAL_API_KEY")
        return api_key or None, "MISTRAL_API_KEY"
    if provider_kind == "cohere":
        api_key = settings.COHERE_API_KEY or os.getenv("COHERE_API_KEY")
        return api_key or None, "COHERE_API_KEY"
    return None, None


def get_provider_key_suffix(provider_name: str) -> tuple[str | None, str | None]:
    provider_kind = _detect_provider_kind(provider_name)
    api_key, env_name = _get_provider_api_key(provider_kind)
    if not api_key:
        return None, env_name
    cleaned = api_key.strip()
    if not cleaned:
        return None, env_name
    suffix = cleaned[-4:] if len(cleaned) > 4 else cleaned
    return suffix, env_name


async def test_model_connection(provider_name: str, model_name: str) -> tuple[bool, str]:
    provider_kind = _detect_provider_kind(provider_name)
    if provider_kind == "vertex":
        return False, "Teste de Vertex AI requer credenciais do Google Cloud."
    if provider_kind == "unknown":
        return False, "Provedor sem teste automatico implementado."

    api_key, env_name = _get_provider_api_key(provider_kind)
    if not api_key:
        env_display = env_name or "API_KEY"
        return False, f"Defina {env_display} no .env para testar este provedor."

    try:
        if provider_kind == "openai":
            from pydantic_ai.models.openai import OpenAIModel

            model = OpenAIModel(model_name, api_key=api_key)
        elif provider_kind == "gemini":
            from pydantic_ai.models.gemini import GeminiModel

            model = GeminiModel(model_name, api_key=api_key)
        elif provider_kind == "anthropic":
            from pydantic_ai.models.anthropic import AnthropicModel

            model = AnthropicModel(model_name, api_key=api_key)
        elif provider_kind == "groq":
            from pydantic_ai.models.groq import GroqModel

            model = GroqModel(model_name, api_key=api_key)
        elif provider_kind == "mistral":
            from pydantic_ai.models.mistral import MistralModel

            model = MistralModel(model_name, api_key=api_key)
        elif provider_kind == "cohere":
            try:
                from pydantic_ai.models.cohere import CohereModel
            except ImportError as exc:
                return False, f"Cohere nao disponivel neste ambiente: {exc}"

            model = CohereModel(model_name, api_key=api_key)
        else:
            return False, "Provedor sem teste automatico implementado."
    except Exception as exc:
        return False, f"Falha ao preparar modelo: {exc}"

    agent = Agent(model, result_type=str, defer_model_check=True)
    try:
        result = await agent.run(
            "Teste de conexao.",
            model_settings={"max_tokens": 8, "temperature": 0},
        )
    except Exception as exc:
        return False, f"Falha ao conectar: {exc}"

    if not (result.data or "").strip():
        return False, "Conexao estabelecida, mas sem resposta valida."

    # LOG: Global History for Connection Test
    log_llm_interaction(
        agent_name="System_ModelTester",
        model=model_name,
        system_prompt="(System Connectivity Test)",
        user_prompt="Teste de conexao.",
        response=str(result.data),
        usage={"input": result.usage().request_tokens, "output": result.usage().response_tokens, "total": result.usage().total_tokens} if hasattr(result, "usage") else None
    )

    return True, "Conexao realizada com sucesso."
