"""
Feature:  All features (cross-cutting — secrets management)
Layer:    Infra / Secrets
Module:   app.infra.secrets.vault
Purpose:  HashiCorp Vault client. Fetches all secrets at app startup via the
          KV v2 secrets engine. Backend refuses to start if Vault is unreachable.
          Provides: OpenAI key, JWT RS256 private/public keys, SendGrid key,
          Stripe key. Secrets are loaded once in lifespan and cached in module state.
Depends:  hvac, app.core.config
HITL:     None — infrastructure only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import hvac

from app.core.config import Settings


@dataclass(frozen=True)
class VaultSecrets:
    openai_api_key: str
    jwt_private_key: str
    jwt_public_key: str
    sendgrid_api_key: str
    stripe_secret_key: str
    langsmith_api_key: str
    icecat_api_key: str
    minio_access_key: str
    minio_secret_key: str
    minio_endpoint: str


# Module-level cache — set once by lifespan, read everywhere
_secrets: VaultSecrets | None = None


def get_secrets() -> VaultSecrets:
    if _secrets is None:
        raise RuntimeError("Vault secrets not loaded. Backend startup incomplete.")
    return _secrets


def _read_kv(client: Any, path: str, key: str) -> str:
    response: dict[str, Any] = client.secrets.kv.v2.read_secret_version(
        path=path, mount_point="secret"
    )
    return str(response["data"]["data"][key])


def load_secrets(settings: Settings) -> VaultSecrets:
    """Connect to Vault and load all secrets. Raises RuntimeError if unreachable."""
    global _secrets

    client = hvac.Client(url=settings.vault_addr, token=settings.vault_token)
    if not client.is_authenticated():
        raise RuntimeError(
            f"Cannot authenticate with Vault at {settings.vault_addr}. "
            "Ensure Vault is running and VAULT_TOKEN is correct."
        )

    try:
        openai_api_key = _read_kv(client, "mawrid/openai", "api_key")
        jwt_private_key = _read_kv(client, "mawrid/jwt", "private_key")
        jwt_public_key = _read_kv(client, "mawrid/jwt", "public_key")
        sendgrid_api_key = _read_kv(client, "mawrid/sendgrid", "api_key")
        stripe_secret_key = _read_kv(client, "mawrid/stripe", "secret_key")
        langsmith_api_key = _read_kv(client, "mawrid/langsmith", "api_key")
        icecat_api_key = _read_kv(client, "mawrid/icecat", "api_key")
        minio_access_key = _read_kv(client, "mawrid/minio", "access_key")
        minio_secret_key = _read_kv(client, "mawrid/minio", "secret_key")
        minio_endpoint = _read_kv(client, "mawrid/minio", "endpoint")
    except Exception as exc:
        raise RuntimeError(f"Failed to load secrets from Vault: {exc}") from exc

    _secrets = VaultSecrets(
        openai_api_key=openai_api_key,
        jwt_private_key=jwt_private_key,
        jwt_public_key=jwt_public_key,
        sendgrid_api_key=sendgrid_api_key,
        stripe_secret_key=stripe_secret_key,
        langsmith_api_key=langsmith_api_key,
        icecat_api_key=icecat_api_key,
        minio_access_key=minio_access_key,
        minio_secret_key=minio_secret_key,
        minio_endpoint=minio_endpoint,
    )
    return _secrets
