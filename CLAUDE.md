# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from the **project root** using `uv`. Never use pip, poetry, or conda.

```bash
uv sync                                          # install all deps (CI and local)
uv run ruff check .                              # lint (Gate 1)
uv run mypy --strict .                           # type check (Gate 2)
uv run pytest tests/unit/                        # unit tests, LLM mocked (Gate 3, < 60s)
uv run pytest tests/integration/                 # real DB + Redis, no LLM (Gate 4)
uv run pytest tests/unit/test_enrichment_pipeline.py  # single test file
uv run pytest tests/unit/ -k "test_goods_received"    # single test by name
uv run pytest tests/evals/test_rag_quality.py    # nightly RAGAS eval (uses real LLM)
```

Docker Compose brings up all services (Postgres + pgvector, Redis, MinIO, Vault, n8n):
```bash
docker compose up -d
```

Backend and frontend are separate Docker services. Run both with `docker compose up` — there is no separate `npm` or `uvicorn` dev command outside Docker.

Migrations use Alembic — never bypass with raw SQL:
```bash
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"
```

## Architecture

**Modular Monolith** — one FastAPI app (`backend/app/`), one Docker Compose stack, strict internal module boundaries enforced by convention. Transactions across modules are trivial (same DB session). Modules can be extracted later; the boundaries make that straightforward.

### Layer Rules (hard constraints)

```
core/      — domain models + pure business logic — ZERO external dependencies
infra/     — DB, Redis, MinIO, LLM, Vault clients — imports from core only
api/       — HTTP routing only — calls services, returns responses, no business logic
agents/    — LangGraph agents — use infra clients, call core services, own no business logic
```

`core/` must never import from `infra/`, `agents/`, or `api/`. Use `typing.Protocol` for any external dependency that needs a test fake (e.g., `PaymentGateway`, `EmailSender`).

### Multi-Tenant Isolation (3 independent layers)

1. PostgreSQL Row-Level Security on every table with `tenant_id`
2. `TenantRepository` base class auto-injects `tenant_id` on every query — all repos inherit this
3. pgvector searches always include a `tenant_id` filter

Breaking tenant isolation is a hard CI fail (15 cross-tenant attack vectors in `tests/integration/test_cross_tenant.py`).

### Key Domain Invariants

**product_hash** = `SHA-256(tenant_id + ":" + product_name + ":" + sku_if_present)` — price deliberately excluded. Colon-delimited to prevent hash collisions. Same product with a price change must not create a duplicate catalog entry. Price is stored as a versioned field with history.

**Enrichment ≠ Storefront** — enriched products land in the internal catalog only. A product reaches the storefront only after: goods physically received → importer deliberately selects → retail price set → published. The lifecycle is: `extracted → enriched → ordered → in_transit → in_stock → published`. These are tracked independently.

**HITL Rule** — every action that sends a message, places an order, or contacts an external party must create a `hitl_actions` record and wait for explicit importer approval (approve / reject / edit). No external write happens without it. HITL keyboard shortcuts A/R/E are required acceptance criteria.

**Outbox pattern** — enrichment result + embedding event are written atomically (one transaction: products table + outbox table). The outbox relay drains separately. Never dual-write (DB commit + queue publish as separate operations).

**Embedding model** — `text-embedding-3-small` (OpenAI API, 1536-dim). The `products.embedding` column is `Vector(1536)`. Do not use local SentenceTransformer or 384-dim models — the DB column dimension is fixed.

**Product embedding structure** — Phase 1: single `embedding` column on `products` table. Phase 4 adds parent/child chunk mapping with a separate `product_chunks` table (chunk text + chunk embedding + parent product_id). The `products.embedding` column holds the full-document embedding used for broad retrieval; chunks are used for precise passage extraction.

**Idempotency** — ARQ enrichment jobs are keyed on `product_hash`; submitting the same job twice is a no-op. Payment webhooks check a dedupe table inside the same transaction as fulfillment.

### LangGraph Agents

- `thread_id` format: `{tenant_id}:{user_id}:{session_uuid}` — enforces per-tenant conversation isolation at the checkpointer level
- Supervisor routes to 5 specialists: Extraction, Enrichment, Communication, Stock Monitor, Discovery
- Specialist agents live in `backend/app/agents/specialists/` (5 files: extraction_agent, enrichment_agent, communication_agent, stock_monitor_agent, discovery_agent)
- MCP servers live in `backend/app/agents/mcp_servers/` (4 files: db_server, email_server, filesystem_server, n8n_server)
- Communication Agent drafts only — all drafts go to `hitl_actions`, never sent directly
- Enrichment ReAct agent: max 5 steps enforced in `prompts/enrichment_agent.yaml`

### 3-Tier Intent Classifier

Traffic flows through tiers in order until confidence threshold met:
1. TF-IDF + Logistic Regression — handles ~80% of traffic, sub-millisecond
2. DistilBERT fine-tuned → ONNX Runtime — < 100ms
3. GPT-4o zero-shot — only for ambiguous queries

### RAG Pipeline (6 techniques, in order)

HyDE + Multi-Query → RRF merge → Dense retrieval (pgvector HNSW) → Parent-Doc chunk mapping → GraphRAG → Cross-Encoder reranking (top-20 → top-6) → MMR diversity (λ=0.5) → LLM → NeMo output rail

**Scope filters are mandatory:**
- Admin chatbot: `WHERE enrichment_status = 'enriched'`
- Consumer chatbot: `WHERE storefront_status = 'published'`

### ML Models

All classical ML models (intent classifier tiers 1-2, tone classifier, supplier scorer) are loaded from the MLflow model registry at application startup. The Tone classifier requires `backend/tests/evals/eval_dataset/tone_training_data.json` (240 synthetic labeled examples generated in Phase 0.3 via `scripts/generate_tone_data.py`).

### Secrets

All secrets come from HashiCorp Vault (`backend/app/infra/secrets/vault.py`). The backend refuses to start if Vault is unreachable. Never commit real secrets. `.env.example` contains documented variable names only.

**Vault dev mode resets on every `docker compose down/up`** — secrets are in-memory only. Always re-seed after a full stack restart:
```bash
VAULT_ADDR=http://localhost:8200 VAULT_TOKEN=root bash scripts/seed-vault.sh
```

### WhatsApp

WhatsApp is deferred to Wave 1 (DEC-011). In the capstone: B2B communications = email only. B2C = email + SMS. All dunning, PO, and fulfillment code must reflect this.

### Deferred ORM Models

`storefront_orders` table exists in the DB (created in migration 0001) but has no ORM model — the model will be added in Phase 11 (Storefront). Do not add it earlier.

## File Header Convention

Every Python file begins with:
```python
"""
Feature:  <feature name>
Layer:    Core / Service
Module:   app.core.catalog.services
Purpose:  <what this file does>
Depends:  <key imports>
HITL:     <which action types this file creates, or "None">
"""
```

Every TypeScript file begins with:
```typescript
// Feature: <feature name>
// Layer:   Component
// Purpose: <what this component does>
// API:     <endpoints it calls>
```

This makes `grep -r "Feature: Dunning"` find the full stack for any feature instantly.

## CI/CD Gates

| When | Gates | Time limit |
|------|-------|------------|
| Every push | Gate 1: ruff + mypy · Gate 2: unit tests (LLM mocked) · Gate 3: bandit + CORS/RS256/argon2id/HMAC invariants | < 3 min |
| PR to master | + Gate 4: integration · Gate 5: cross-tenant red-team · Gate 6: agent trajectory snapshots | < 15 min |
| Nightly on master | Gate 7: RAGAS · Gate 8: classifier F1 ≥ 0.85 · Gate 9: drift (PSI ≥ 0.25 = alarm) | — |

Merge to master requires all PR gates green + nightly eval passed within 24 hours.

## Phase Progress

Track what is done. Update this section when each phase's Verify gate passes.

| Phase | Sub-phase | Status |
|-------|-----------|--------|
| **0 — Spec & Skills** | 0.1 SpecKit documents (9 files) | ✅ Done |
| | 0.2 Claude Code skills (8 skills) | ✅ Done |
| | 0.3 Tone classifier training data (240 examples) | ⬜ Pending |
| | 0.4 Intent classifier training data (1200+ examples) | ⬜ Pending |
| **1 — Foundation** | 1.1 Local environment + Docker Compose | ✅ Done |
| | 1.2 CI/CD skeleton (Gates 1–3) | ✅ Done |
| | 1.3 Auth + tenant onboarding | ✅ Done |
| | 1.4 Database schema + Alembic migrations | ✅ Done |
| | 1.5 MLflow + LangSmith live | ✅ Done |
| | **Phase 1 complete — all 5 sub-phases verified** | ✅ |
| **2 — Enrichment** | Full pipeline (6 layers) | ⬜ Pending |
| **3 — Procurement** | Draft → PO → shipment → receive → publish | ⬜ Pending |
| **4 — RAG** | 6-technique pipeline + chatbots | ⬜ Pending |
| **5 — Guardrails** | Presidio + NeMo on all LLM calls | ⬜ Pending |
| **6 — Dunning** | 4 tracks + tone classifier | ⬜ Pending |
| **7 — Suppliers** | Matching + scoring + customer mgmt | ⬜ Pending |
| **8 — Agents** | Supervisor + 5 specialists + intent classifier | ⬜ Pending |
| **9 — n8n** | All 15 capstone workflows | ⬜ Pending |
| **10 — Admin UI** | Command center dashboard | ⬜ Pending |
| **11 — Storefront** | Consumer store + checkout | ⬜ Pending |
| **12 — MLOps** | Drift detection + governance | ⬜ Pending |
| **13 — CI/CD** | All 9 gates audited | ⬜ Pending |
| **14 — Deploy** | VPS production deployment | ⬜ Pending |

---

## Plan & Specs

- Full 15-phase implementation plan: `resources/plan/plan.md`
- Approved feature decisions (DEC-001–DEC-019): `resources/understanding_brainstorm/approved.md`
- SpecKit docs (written before each phase's code): `specs/`
- n8n workflow exports (15 workflows, 17 JSON files): `n8n/workflows/`
- Versioned prompt templates: `backend/prompts/`
- ML eval thresholds: `backend/ml_config/eval_thresholds.yaml`
- Drift thresholds: `backend/ml_config/drift_thresholds.yaml`
