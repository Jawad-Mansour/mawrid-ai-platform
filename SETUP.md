# Mawrid — Setup & Run Runbook

End-to-end steps to run the platform locally, then deploy. Backend Phases 1–12 are
complete; the UI (Phase 10.2 / 11.6) and production deploy (Phase 14) come after this.

---

## 1. Prerequisites

- **Docker Desktop** running (Windows/Mac/Linux).
- **uv** installed (`pip install uv` once) — never use pip/poetry/conda for project deps.
- API keys (see §2). Keep them in the gitignored `keys.txt` — never commit them.

---

## 2. Keys & accounts

| Secret | Required | Notes |
|--------|----------|-------|
| OpenAI `sk-...` | ✅ | Embeddings, extraction, enrichment, chat, drafts, guardrails |
| Stripe secret `sk_test_...` | ✅ (checkout) | Test mode for the capstone |
| Stripe webhook secret `whsec_...` | ✅ (checkout) | From `stripe listen` (local) or Dashboard → Webhooks |
| SendGrid `SG....` | ✅ (email) | **Also verify a sender** (Settings → Sender Authentication → Single Sender). Set `SENDGRID_FROM_EMAIL` to that verified address (currently set in `docker-compose.yml`). |
| Icecat username | 🟡 | Enrichment specs; degrades to web search if unavailable |
| LangSmith `lsv2_...` | ⚪ | Tracing only |

Auto-generated / dev defaults (do NOT supply): JWT keypair (seed script), MinIO
(`minioadmin`), Vault token (`root`), Postgres/Redis creds, n8n `admin/password`,
`n8n_service_token` (dev). Change all of these for production (§6).

### Stripe webhook secret — local
```bash
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
# copy the printed whsec_... value
```

---

## 3. Bring up the stack (local)

```bash
docker compose up -d
uv run alembic upgrade head

export VAULT_ADDR=http://localhost:8200 VAULT_TOKEN=root
# arg order: openai  sendgrid  stripe_secret  langsmith  icecat  stripe_webhook_secret
bash scripts/seed-vault.sh <openai> <sendgrid> <stripe_secret> <langsmith> <icecat> <whsec>
```
> Vault runs in dev mode (in-memory) — **re-run `seed-vault.sh` after every `docker compose down/up`.**

Verify: `GET http://localhost:8000/health` → `{"status":"ok"}`; MLflow `http://localhost:5000`;
MinIO console `http://localhost:9001`; n8n `http://localhost:5678`.

---

## 4. Train ML models (populates MLflow registry; activates intent Tier 2)

```bash
uv run python -m app.ml.tone.trainer
uv run python -m app.ml.supplier_scorer.trainer
uv run python -m app.ml.intent.trainer --tier all
```
All three degrade gracefully if skipped (rules/formula/Tier-1 cold-start), but training
gives the full 3-tier intent cascade and registry-backed models.

---

## 5. n8n workflows

1. Open `http://localhost:5678` (`admin` / `password`).
2. Import the 17 JSONs from `n8n/workflows/`.
3. Activate each workflow.
4. Backend ↔ n8n callbacks authenticate with `X-N8N-Service-Token` = `n8n_service_token`
   (dev default works locally; set a strong value for prod in both backend env and n8n).

> n8n is the automation layer; the backend also runs its own APScheduler for dunning, so
> the core app works without n8n for a demo.

---

## 6. Smoke test (confirms the pre-UI system end-to-end)

1. Sign up a tenant: `POST /api/v1/auth/signup`.
2. Upload a supplier PDF: `POST /api/v1/catalog/documents/upload` → `.../enrich`.
3. Confirm enrichment + that `product_chunks` get populated (relay) → `POST /api/v1/chat/admin`
   returns a grounded answer with sources.
4. Publish a product, then run one Stripe **test** payment through checkout →
   `POST /api/v1/webhooks/stripe` confirms it (stock decremented, dunning auto-stop).
5. Integration suite (real DB): `uv run pytest backend/tests/integration/`.

---

## 7. Deployment (Phase 14 — after the UI is built)

Uses `docker-compose.prod.yml` (pre-built images, multi-worker uvicorn, Caddy TLS).

Before deploying:
- Build & push images to a registry; replace `ghcr.io/your-org/...` in `docker-compose.prod.yml`.
- Set `DOMAIN` for the Caddyfile (TLS auto-provisioned via Let's Encrypt).
- The prod frontend is the **nginx** image on **:80** (Caddy already proxies `frontend:80`);
  ensure the frontend `nginx.conf` listens on 80 when the UI is added.
- Production secrets: real MinIO keys, a non-root Vault token (or managed Vault), a strong
  `n8n_service_token`, and `ENVIRONMENT=production` (already set in prod compose — this makes
  the Stripe webhook signature **mandatory**, so the real `whsec_` must be in Vault).
- Re-point the Stripe webhook endpoint to `https://<domain>/api/v1/webhooks/stripe`.

```bash
DOMAIN=app.example.com IMAGE_TAG=<tag> \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## What only you can do (cannot be automated from the repo)
- Start Docker Desktop.
- Run `stripe listen` (your Stripe login) to get `whsec_...`.
- Click the SendGrid verification email for your sender address.
