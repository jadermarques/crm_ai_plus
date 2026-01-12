"""Módulo de Configuração da Integração Chatwoot-Meta.

Este módulo fornece funções para armazenar e recuperar a configuração
da integração Chatwoot-Meta, que recebe webhooks do Chatwoot e atualiza
os atributos customizados da conversa com dados de referência de anúncios Meta.

Attributes:
    metadata: Instância SQLAlchemy MetaData para definições de tabelas.
    integration_chatwoot_meta_config: Tabela SQLAlchemy para armazenar configurações.

Functions:
    ensure_table: Cria a tabela no banco de dados se não existir.
    get_config: Obtém a configuração atual.
    upsert_config: Atualiza ou insere a configuração.

Example:
    >>> from src.core.integration_chatwoot_meta import get_config, upsert_config
    >>> import asyncio
    >>> asyncio.run(upsert_config(
    ...     chatwoot_base_url="https://app.chatwoot.com",
    ...     chatwoot_api_token="seu_token",
    ...     is_active=True
    ... ))
    >>> config = asyncio.run(get_config())
    >>> print(config["chatwoot_base_url"])
    https://app.chatwoot.com
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    func,
    select,
    text,
    update,
)

from src.core.database import get_engine, get_sessionmaker
from src.core.db_schema import ensure_audit_columns

metadata = MetaData()

integration_chatwoot_meta_config = Table(
    "integration_chatwoot_meta_config",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("chatwoot_base_url", String(500), nullable=False),
    Column("chatwoot_api_token", String(500), nullable=False),
    Column("webhook_external_url", String(500), nullable=True),
    Column("webhook_path", String(200), nullable=True, server_default=text("'/api/v1/webhooks/chatwoot-meta'")),
    Column("is_active", Boolean, nullable=False, server_default=text("TRUE")),
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
    """Cria a tabela de configuração se não existir.

    Cria a tabela `integration_chatwoot_meta_config` no banco de dados,
    adiciona colunas de migração e as colunas de auditoria.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        # Migração: adiciona colunas se não existirem
        await conn.execute(
            text(
                "ALTER TABLE integration_chatwoot_meta_config "
                "ADD COLUMN IF NOT EXISTS webhook_external_url VARCHAR(500)"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE integration_chatwoot_meta_config "
                "ADD COLUMN IF NOT EXISTS webhook_path VARCHAR(200) DEFAULT '/api/v1/webhooks/chatwoot-meta'"
            )
        )
    await ensure_audit_columns("integration_chatwoot_meta_config")


async def get_config() -> dict[str, Any] | None:
    """Obtém a configuração atual da integração.

    Returns:
        Dicionário com a configuração ou None se não configurado.
    """
    await ensure_table()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(
            select(integration_chatwoot_meta_config).limit(1)
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def upsert_config(
    *,
    chatwoot_base_url: str,
    chatwoot_api_token: str,
    webhook_external_url: str | None = None,
    webhook_path: str | None = None,
    is_active: bool = True,
) -> None:
    """Atualiza ou insere a configuração da integração.

    Args:
        chatwoot_base_url: URL base da API Chatwoot (ex: https://app.chatwoot.com).
        chatwoot_api_token: Token de acesso da API Chatwoot.
        webhook_external_url: URL externa do webhook (ex: https://meusite.com.br).
        webhook_path: Path do endpoint do webhook (ex: /api/v1/webhooks/chatwoot-meta).
        is_active: Se a integração está ativa.

    Raises:
        ValueError: Se campos obrigatórios estiverem faltando.
    """
    if not chatwoot_base_url or not chatwoot_api_token:
        raise ValueError("URL e Token são obrigatórios.")

    # Normaliza URLs e paths
    chatwoot_base_url = chatwoot_base_url.strip().rstrip("/")
    chatwoot_api_token = chatwoot_api_token.strip()
    if webhook_external_url:
        webhook_external_url = webhook_external_url.strip().rstrip("/")
    if webhook_path:
        webhook_path = webhook_path.strip()
        if not webhook_path.startswith("/"):
            webhook_path = "/" + webhook_path

    await ensure_table()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        existing = await session.execute(
            select(integration_chatwoot_meta_config.c.id).limit(1)
        )
        row = existing.first()
        if row:
            await session.execute(
                update(integration_chatwoot_meta_config)
                .where(integration_chatwoot_meta_config.c.id == row.id)
                .values(
                    chatwoot_base_url=chatwoot_base_url,
                    chatwoot_api_token=chatwoot_api_token,
                    webhook_external_url=webhook_external_url,
                    webhook_path=webhook_path or "/api/v1/webhooks/chatwoot-meta",
                    is_active=is_active,
                )
            )
        else:
            await session.execute(
                integration_chatwoot_meta_config.insert().values(
                    chatwoot_base_url=chatwoot_base_url,
                    chatwoot_api_token=chatwoot_api_token,
                    webhook_external_url=webhook_external_url,
                    webhook_path=webhook_path or "/api/v1/webhooks/chatwoot-meta",
                    is_active=is_active,
                )
            )
        await session.commit()


