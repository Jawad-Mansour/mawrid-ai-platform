"""
Feature:  Platform Bootstrap (cross-cutting)
Layer:    Core / Config
Module:   app.core.config
Purpose:  Pydantic-Settings BaseSettings class. Reads environment variables
          injected by Docker Compose (or CI). Never reads secrets — secrets
          come from Vault via app.infra.secrets.vault at startup.
Depends:  pydantic-settings
HITL:     None.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="forbid")

    database_url: str = "postgresql+asyncpg://mawrid:password@localhost:5432/mawrid"
    redis_url: str = "redis://localhost:6379/0"
    vault_addr: str = "http://localhost:8200"
    vault_token: str = "root"
    environment: str = "development"
    allowed_origins: list[str] = []
    searxng_base_url: str = "http://searxng:8080"


@lru_cache
def get_settings() -> Settings:
    return Settings()
