#!/usr/bin/env bash
# Purpose: Seed HashiCorp Vault (dev mode) with all secrets required by the backend.
#          Run once after `docker compose up -d` and before starting the backend.
#          Requires: curl, openssl, VAULT_ADDR and VAULT_TOKEN in environment.
#
# Usage:
#   export VAULT_ADDR=http://localhost:8200
#   export VAULT_TOKEN=root
#   bash scripts/seed-vault.sh [OPENAI_API_KEY] [SENDGRID_API_KEY] [STRIPE_SECRET_KEY] [LANGSMITH_API_KEY]

set -euo pipefail

VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
VAULT_TOKEN="${VAULT_TOKEN:-root}"
OPENAI_KEY="${1:-sk-placeholder-replace-me}"
SENDGRID_KEY="${2:-SG.placeholder}"
STRIPE_KEY="${3:-sk_test_placeholder}"
LANGSMITH_KEY="${4:-ls__placeholder}"
ICECAT_KEY="${5:-icecat-placeholder}"
STRIPE_WEBHOOK_SECRET="${6:-whsec_placeholder}"

echo "==> Seeding Vault at ${VAULT_ADDR}"

# Generate RSA-4096 keypair for RS256 JWT signing
TMP=$(mktemp -d)
openssl genrsa -out "${TMP}/private.pem" 4096 2>/dev/null
openssl rsa -in "${TMP}/private.pem" -pubout -out "${TMP}/public.pem" 2>/dev/null

PRIVATE_KEY=$(cat "${TMP}/private.pem")
PUBLIC_KEY=$(cat "${TMP}/public.pem")
rm -rf "${TMP}"

# Detect python command (python3 on Linux/Mac, python on Windows)
PYTHON_CMD=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "")
if [ -z "${PYTHON_CMD}" ]; then
  echo "ERROR: python3 or python not found. Cannot JSON-encode RSA keys." >&2
  exit 1
fi

json_encode() {
  echo "$1" | "${PYTHON_CMD}" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
}

vault_put() {
  local path="$1"
  local data="$2"
  curl -s -o /dev/null -X POST \
    -H "X-Vault-Token: ${VAULT_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"data\": ${data}}" \
    "${VAULT_ADDR}/v1/secret/data/${path}"
  echo "  stored: ${path}"
}

# JWT keys
vault_put "mawrid/jwt" \
  "{\"private_key\": $(json_encode "${PRIVATE_KEY}"), \"public_key\": $(json_encode "${PUBLIC_KEY}")}"

# OpenAI
vault_put "mawrid/openai" "{\"api_key\": \"${OPENAI_KEY}\"}"

# SendGrid
vault_put "mawrid/sendgrid" "{\"api_key\": \"${SENDGRID_KEY}\"}"

# Stripe (secret_key for API calls; webhook_secret for HMAC signature verification)
vault_put "mawrid/stripe" \
  "{\"secret_key\": \"${STRIPE_KEY}\", \"webhook_secret\": \"${STRIPE_WEBHOOK_SECRET}\"}"

# LangSmith
vault_put "mawrid/langsmith" "{\"api_key\": \"${LANGSMITH_KEY}\"}"

# Icecat Open (Phase 2 enrichment — product specs database)
vault_put "mawrid/icecat" "{\"api_key\": \"${ICECAT_KEY}\"}"

# MinIO (Phase 2 enrichment — document + image storage)
vault_put "mawrid/minio" "{\"access_key\": \"minioadmin\", \"secret_key\": \"minioadmin\", \"endpoint\": \"minio:9000\"}"

# IMAP (optional — inbound supplier-reply detection). Set IMAP_USER + IMAP_PASSWORD in the
# environment to enable. For Gmail: enable IMAP, turn on 2FA, and use an App Password.
# If unset, the backend simply runs without inbound polling (manual reply logging still works).
if [ -n "${IMAP_USER:-}" ] && [ -n "${IMAP_PASSWORD:-}" ]; then
  IMAP_HOST="${IMAP_HOST:-imap.gmail.com}"
  vault_put "mawrid/imap" \
    "{\"host\": \"${IMAP_HOST}\", \"user\": \"${IMAP_USER}\", \"password\": $(json_encode "${IMAP_PASSWORD}")}"
  echo "  inbound email: ENABLED (${IMAP_USER} @ ${IMAP_HOST})"
else
  echo "  inbound email: disabled (set IMAP_USER + IMAP_PASSWORD to enable)"
fi

# Connect Gmail (OAuth) — set GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET (from keys.txt) to enable.
# Needed after a full `docker compose down` since Vault dev mode resets.
if [ -n "${GOOGLE_CLIENT_ID:-}" ] && [ -n "${GOOGLE_CLIENT_SECRET:-}" ]; then
  vault_put "mawrid/google" \
    "{\"client_id\": \"${GOOGLE_CLIENT_ID}\", \"client_secret\": \"${GOOGLE_CLIENT_SECRET}\"}"
  echo "  Connect Gmail: ENABLED"
else
  echo "  Connect Gmail: disabled (set GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET to enable)"
fi

echo ""
echo "==> Vault seeded successfully."
echo "    Pass your real keys as arguments:"
echo "    bash scripts/seed-vault.sh <openai> <sendgrid> <stripe_secret> <langsmith> <icecat> <stripe_webhook_secret>"
