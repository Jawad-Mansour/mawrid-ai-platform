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

# Stripe
vault_put "mawrid/stripe" "{\"secret_key\": \"${STRIPE_KEY}\"}"

# LangSmith
vault_put "mawrid/langsmith" "{\"api_key\": \"${LANGSMITH_KEY}\"}"

# Icecat Open (Phase 2 enrichment — product specs database)
vault_put "mawrid/icecat" "{\"api_key\": \"${ICECAT_KEY}\"}"

# MinIO (Phase 2 enrichment — document + image storage)
vault_put "mawrid/minio" "{\"access_key\": \"minioadmin\", \"secret_key\": \"minioadmin\", \"endpoint\": \"minio:9000\"}"

echo ""
echo "==> Vault seeded successfully."
echo "    Pass your real keys as arguments: bash scripts/seed-vault.sh sk-real-openai-key SG.key sk_key ls__key icecat-key"
