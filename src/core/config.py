"""Módulo de Configurações da Aplicação.

Este módulo gerencia as configurações da aplicação usando Pydantic Settings.
Carrega variáveis de ambiente do arquivo .env e fornece acesso tipado.

Attributes:
    Settings: Classe de configurações com validação Pydantic.
    get_settings: Função para obter instância cacheada das configurações.

Example:
    >>> from src.core.config import get_settings
    >>> settings = get_settings()
    >>> print(settings.DATABASE_URL)
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação carregadas de variáveis de ambiente.

    Attributes:
        DATABASE_URL: URL de conexão do banco de dados PostgreSQL.
        REDIS_URL: URL de conexão do Redis.
        CHROMA_HOST: Host do servidor ChromaDB.
        CHATWOOT_BASE_URL: URL base da instância Chatwoot.
        CHATWOOT_ACCOUNT_ID: ID da conta Chatwoot.
        CHATWOOT_API_ACCESS_TOKEN: Token de acesso da API Chatwoot.
        OPENAI_API_KEY: Chave de API da OpenAI.
        GOOGLE_API_KEY: Chave de API do Google.
        GEMINI_API_KEY: Chave de API do Google Gemini.
        ANTHROPIC_API_KEY: Chave de API da Anthropic.
        GROQ_API_KEY: Chave de API da Groq.
        MISTRAL_API_KEY: Chave de API da Mistral.
        COHERE_API_KEY: Chave de API da Cohere.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str
    REDIS_URL: str
    CHROMA_HOST: str
    CHATWOOT_BASE_URL: str | None = None
    CHATWOOT_ACCOUNT_ID: int | None = None
    CHATWOOT_API_ACCESS_TOKEN: str | None = None
    CHATWOOT_ACCESS_TOKEN: str | None = None
    OPENAI_API_KEY: str
    GOOGLE_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    MISTRAL_API_KEY: str | None = None
    COHERE_API_KEY: str | None = None

    @property
    def chatwoot_token(self) -> str:
        """Retorna o token de acesso do Chatwoot.

        Returns:
            Token de acesso preferindo CHATWOOT_API_ACCESS_TOKEN sobre CHATWOOT_ACCESS_TOKEN.
        """
        return self.CHATWOOT_API_ACCESS_TOKEN or (self.CHATWOOT_ACCESS_TOKEN or "")


@lru_cache
def get_settings() -> Settings:
    """Obtém instância cacheada das configurações.

    Usa lru_cache para garantir que as configurações são carregadas
    apenas uma vez durante a execução da aplicação.

    Returns:
        Instância de Settings com todas as configurações carregadas.
    """
    return Settings()

