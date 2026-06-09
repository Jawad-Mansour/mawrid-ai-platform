"""
Feature:  All features (cross-cutting — secrets management)
Layer:    Infra / Secrets
Module:   app.infra.secrets.vault
Purpose:  HashiCorp Vault client. Fetches all secrets at app startup via the
          KV v2 secrets engine. Backend refuses to start if Vault is unreachable.
          Provides: OpenAI key, JWT RS256 private key, payment gateway keys,
          SendGrid key, Twilio key. Never reads from environment variables
          directly in production — Vault is the only source of truth for secrets.
Depends:  hvac (HashiCorp Vault Python client)
HITL:     None — infrastructure only.
"""
