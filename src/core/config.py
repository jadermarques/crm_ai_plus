from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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
        return self.CHATWOOT_API_ACCESS_TOKEN or (self.CHATWOOT_ACCESS_TOKEN or "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
