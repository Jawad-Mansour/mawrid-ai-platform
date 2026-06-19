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
    n8n_base_url: str = "http://n8n:5678"
    n8n_service_token: str = "dev-n8n-service-token"
    n8n_api_key: str = ""
    mlflow_tracking_uri: str = "http://localhost:5000"
    # SendGrid sender identity — MUST be a verified sender in your SendGrid account,
    # otherwise SendGrid rejects the send. Set SENDGRID_FROM_EMAIL to your verified address.
    sendgrid_from_email: str = "noreply@mawrid.app"
    sendgrid_from_name: str = "Mawrid Platform"
    # Connect Gmail (OAuth). redirect URI must match the one registered in Google Cloud.
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    frontend_url: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
