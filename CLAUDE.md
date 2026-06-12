# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from the **project root** using `uv`. Never use pip, poetry, or conda.

```bash
uv sync                                          # install all deps (CI and local)
uv run ruff check .                              # lint (Gate 1)
uv run mypy --strict .                           # type check (Gate 2)
uv run pytest backend/tests/unit/                        # unit tests, LLM mocked (Gate 3, < 60s)
uv run pytest backend/tests/integration/                 # real DB + Redis, no LLM (Gate 4)
uv run pytest backend/tests/unit/test_enrichment_pipeline.py  # single test file
uv run pytest backend/tests/unit/ -k "test_goods_received"    # single test by name
uv run pytest backend/tests/evals/test_rag_quality.py    # nightly RAGAS eval (uses real LLM)
```

Docker Compose brings up all services (Postgres + pgvector, Redis, MinIO, Vault, n8n, SearXNG, ARQ worker):
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

**RLS Layer 1 status — non-functional until Phase 13:** `POSTGRES_USER: mawrid` makes `mawrid` a PostgreSQL superuser, which bypasses all RLS policies. Effective isolation is Layer 2 (`TenantRepository._tenant_filter()`) + Layer 3 (pgvector filter). Fix at Phase 13: create restricted `mawrid_app` role (DML only), use it in `DATABASE_URL` for services; keep `mawrid` for Alembic DDL only.

Breaking tenant isolation is a hard CI fail (15 cross-tenant attack vectors in `tests/integration/test_cross_tenant.py`).

### Key Domain Invariants

**product_hash** = `SHA-256(tenant_id + ":" + product_name + ":" + sku_if_present)` — price deliberately excluded. Colon-delimited to prevent hash collisions. Same product with a price change must not create a duplicate catalog entry. Price is stored as a versioned field with history.

**Enrichment ≠ Storefront** — enriched products land in the internal catalog only. A product reaches the storefront only after: goods physically received → importer deliberately selects → retail price set → published. The lifecycle is: `extracted → enriched → ordered → in_transit → in_stock → published`. These are tracked independently.

**HITL Rule** — every action that sends a message, places an order, or contacts an external party must create a `hitl_actions` record and wait for explicit importer approval (approve / reject / edit). No external write happens without it. HITL keyboard shortcuts A/R/E are required acceptance criteria.

**Outbox pattern** — enrichment result + embedding event are written atomically (one transaction: products table + outbox table). The outbox relay drains separately. Never dual-write (DB commit + queue publish as separate operations).

**Embedding model** — `text-embedding-3-small` (OpenAI API, 1536-dim). The `products.embedding` column is `Vector(1536)`. Do not use local SentenceTransformer or 384-dim models — the DB column dimension is fixed.

**Product embedding structure** — Phase 1: single `embedding` column on `products` table. Phase 4 adds parent/child chunk mapping with a separate `product_chunks` table (chunk text + chunk embedding + parent product_id). The `products.embedding` column holds the full-document embedding used for broad retrieval; chunks are used for precise passage extraction.

**Idempotency** — ARQ enrichment jobs are keyed on `product_hash`; submitting the same job twice is a no-op. Payment webhooks check a dedupe table inside the same transaction as fulfillment.

### Phase 2 Enrichment Pipeline (Sequential — NOT LangGraph)

- `backend/app/core/catalog/enrichment_pipeline.py` — deterministic 5-step pipeline (Phase 2.3+): Icecat → SearXNG → httpx + trafilatura → GPT-4o spec extraction → GPT-4o description
- This is NOT a LangGraph agent. Phase 8's Enrichment Specialist wraps it in a LangGraph node.
- `backend/app/core/catalog/parser.py` — MIME-type dispatcher (magic bytes sniff: PDF vs XLSX vs XLS)
- `backend/app/core/catalog/parsers/pdf_parser.py` — Docling PDF → markdown + table rows + image MinIO upload
- `backend/app/core/catalog/parsers/excel_parser.py` — openpyxl with merged-cell resolution → list-of-dicts rows
- `backend/app/api/catalog.py` — Layer 1+3+4 API: `POST /catalog/documents/upload` (idempotent), `POST /catalog/documents/{id}/enrich` (extraction + pipeline), `GET /catalog/documents/{id}`, `GET /catalog/documents/{id}/review-queue`, `GET /catalog/products`
- `backend/app/core/catalog/extractor.py` — GPT-4o batch extractor (Phase 2.3): normalises multilingual headers → English keys; preserves product_name verbatim; routes failed rows to review_queue
- `backend/app/core/catalog/enrichment_pipeline.py` — 5-step sequential pipeline (Phase 2.4): Icecat → SearXNG → httpx+trafilatura → GPT-4o spec fill → GPT-4o description. All steps gracefully degrade. Protocol-typed clients make unit testing possible without network.
- `backend/app/infra/db/repos/document_repo.py` — DocumentRepository (idempotent upsert, status transitions)
- `backend/app/infra/storage/minio.py` — real minio SDK client (async via asyncio.to_thread)
- `backend/app/infra/llm/openai.py` — async OpenAI: chat_completion + embed_text + embed_batch (tenacity retry x3)
- `backend/app/infra/vector/embedder.py` — thin embedding wrapper (text-embedding-3-small, 1536-dim)
- Icecat confidence: `high` = EAN matched + spec_count ≥ 5; `medium` = name matched + spec_count ≥ 3
- `document_id = SHA-256(file_bytes)` — primary key AND dedup key for uploaded documents
- Images: extracted from PDF (Docling) or downloaded from Icecat/web → stored in MinIO as `/{tenant_id}/images/{uuid}.png` — never a URL in the DB column; presigned URLs generated at serve time
- `enrichment_source`: `icecat` | `web` | `manual`; `enrichment_confidence`: `high` | `medium` | `partial`
- Failed extraction rows → `review_queue` table (no product row created)
- SearXNG (self-hosted Docker, port 8080) aggregates Google + Bing + DuckDuckGo, JSON output only — `search.formats: [json]` is mandatory in `searxng/settings.yml`
- Vault secrets: `mawrid/icecat` → `api_key`; `mawrid/minio` → `access_key`, `secret_key`, `endpoint`
- Migration 0003: enrichment columns on `products` + `documents` table + `review_queue` table + RLS on both
- `backend/app/infra/db/repos/outbox_repo.py` — OutboxRepository: `create()`, `get_pending_batch()` (FOR UPDATE SKIP LOCKED), `mark_processed()`
- `backend/app/infra/workers/outbox_relay.py` — `process_pending_events(session, tenant_id)` + `run_relay(session_factory)` main loop
- `backend/app/infra/workers/enrichment_worker.py` — ARQ WorkerSettings, `enrich_product()` job (idempotent on enrichment_status), startup/shutdown
- `GET /catalog/products` calls `product_repo.list_all()` — lists ALL products regardless of enrichment_status. Use `list_pending_enrichment()` only if you specifically want unprocessed ones.
- `infra/llm/embedder.py` does NOT exist — it was deleted. Real embedder: `infra/vector/embedder.py` (OpenAI text-embedding-3-small, 1536-dim).
- `infra/queue/client.py` does NOT exist — ARQ job submission is in `enrichment_worker.py` directly.

### LangGraph Agents (Phase 8)

- `thread_id` format: `{tenant_id}:{user_id}:{session_uuid}` — enforces per-tenant conversation isolation at the checkpointer level
- Supervisor routes to 5 specialists: Extraction, Enrichment, Communication, Stock Monitor, Discovery
- Specialist agents live in `backend/app/agents/specialists/` (5 files: extraction_agent, enrichment_agent, communication_agent, stock_monitor_agent, discovery_agent)
- MCP servers live in `backend/app/agents/mcp_servers/` (4 files: db_server, email_server, filesystem_server, n8n_server)
- Communication Agent drafts only — all drafts go to `hitl_actions`, never sent directly
- Enrichment Specialist: wraps `enrichment_pipeline.py` in a LangGraph node, max 5 steps

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

All classical ML models (intent classifier tiers 1-2, tone classifier, supplier scorer) are loaded from the MLflow model registry at application startup. The Tone classifier requires `backend/tests/evals/eval_dataset/tone_training_data.json` (3000 synthetic labeled examples, 1000/class, generated by `scripts/generate_tone_data.py` — already committed). Run `uv run python -m app.ml.tone.trainer` (with Docker Compose up) to train and register the model before the scheduler fires.

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
| | 0.2 Claude Code skills (9 skills — added check-suppliers) | ✅ Done |
| | 0.3 Tone classifier training data (3000 examples, 1000/class — committed) | ✅ Done |
| | 0.4 Intent classifier training data (1200+ examples) | ⬜ Pending — run `scripts/generate_intent_data.py` |
| **1 — Foundation** | 1.1 Local environment + Docker Compose | ✅ Done |
| | 1.2 CI/CD skeleton (Gates 1–3) | ✅ Done |
| | 1.3 Auth + tenant onboarding | ✅ Done |
| | 1.4 Database schema + Alembic migrations | ✅ Done |
| | 1.5 MLflow + LangSmith live | ✅ Done |
| | **Phase 1 complete — all 5 sub-phases verified** | ✅ |
| **2 — Enrichment** | 2.1 Layer 1: File ingestion + MinIO + API | ✅ Done |
| | 2.2 Layer 2: Docling PDF + openpyxl Excel parsing | ✅ Done |
| | 2.3 Layer 3: GPT-4o extraction (multilingual) | ✅ Done |
| | 2.4 Layer 4: 5-step sequential pipeline (Icecat→SearXNG→web→GPT-4o) | ✅ Done |
| | 2.5 Layer 5: Async ARQ submission + outbox relay + embeddings | ✅ Done |
| | 2.6 Layer 6: Integration test (20-product PDF end-to-end) | ✅ Done |
| | **Phase 2 complete — all 6 sub-phases verified** | ✅ |
| **3 — Procurement** | 3.0 Supplier CRUD (name, email, language, currency) | ✅ Done |
| | 3.1 Order draft creation (submit/place separation) | ✅ Done |
| | 3.2 PO drafting via GPT-4o + HITL (purchase_order_send) + SendGrid | ✅ Done |
| | 3.3 Shipment tracking (carrier, ETA, manual milestone updates) | ✅ Done |
| | 3.4 Goods received (atomic stock update: qty += received - damaged) | ✅ Done |
| | 3.5 Storefront publishing (retail price, storefront qty, storefront_status) | ✅ Done |
| | 3.6 Integration test (full procurement cycle end-to-end) | ✅ Done |
| | **Phase 3 complete — all 7 sub-phases verified** | ✅ |
| **4 — RAG** | 4.1 product_chunks table + migration 0005 (parent/child, HNSW, RLS) | ✅ Done |
| | 4.2 Dense retrieval (pgvector HNSW on child chunks) + parent-doc mapping | ✅ Done |
| | 4.3 HyDE + Multi-Query + RRF (expansion.py) | ✅ Done |
| | 4.4 Cross-encoder reranking (ms-marco-MiniLM-L-6-v2, local CPU) | ✅ Done |
| | 4.5 GraphRAG (networkx, graph_edges table, 2-hop traversal) | ✅ Done |
| | 4.6 MMR diversity (λ=0.5) | ✅ Done |
| | 4.7 Full RAG pipeline + /chat/admin + /chat/consumer + /search/catalog + /search/store | ✅ Done |
| | 4.8 RAGAS eval dataset (20 Q&A) + CI Gate 7 wired | ✅ Done |
| | **Phase 4 complete — all 8 sub-phases verified** | ✅ |
| **5 — Guardrails** | 5.1 Presidio PII redaction (EN/AR/FR) as middleware | ✅ Done |
| | 5.2 NeMo input + output rails on all LLM calls | ✅ Done |
| | 5.3 Re-verify Phase 4 with guardrails active | ✅ Done |
| | **Phase 5 complete — all 3 sub-phases verified** | ✅ |
| **6 — Dunning** | 6.0 generate_tone_data.py → 3000 examples (1000/class) committed; trainer ready | ✅ Done |
| | 6.1 Track 1: B2B Payables (APScheduler daily @ 07:00 UTC, dunning_payables_advance HITL) | ✅ Done |
| | 6.2 Track 2: B2B Disputes (on-demand, dunning_disputes_on_demand HITL, mode-gated) | ✅ Done |
| | 6.3 Track 3: B2B Receivables (Day 7/14/21 from due_date, tone classifier, HITL) | ✅ Done |
| | 6.4 Track 4: B2C Collections (Day 3/7/14 from invoice_date, tone classifier, payment link, HITL) | ✅ Done |
| | 6.5 Payment auto-stop (atomic: paid_at + sequences stopped + all pending HITL rejected) | ✅ Done |
| | 6.6 Integration test (all 4 tracks, auto-stop, mode gating — requires Docker Compose) | ⬜ Pending |
| **7 — Suppliers** | 7.1 Supplier scoring (Ridge regression, 6 features, MLflow registry) | ✅ Done |
| | 7.2 Supplier matching waterfall (exact → TF-IDF → embedding → HITL) | ✅ Done |
| | 7.3 Customer matching waterfall (email → phone → name TF-IDF → HITL) | ✅ Done |
| | 7.4 Customer segmentation + payment_history_score rolling update | ✅ Done |
| | 7.5 Reorder signal (Stock Monitor → HITL PO draft) | ✅ Done |
| | 7.6 Supplier discovery (SearXNG + GPT-4o + HITL supplier_outreach) | ✅ Done |
| | **Phase 7 complete — all 6 sub-phases verified** | ✅ |
| **8 — Agents** | 8.0 Run generate_intent_data.py → train Tier1 (TF-IDF+LR) + Tier2 (DistilBERT→ONNX) | ✅ Done |
| | 8.1 3-tier intent classifier cascade wired to /chat routing | ✅ Done |
| | 8.2 LangGraph Supervisor + Redis checkpointer (thread_id scoped) | ✅ Done |
| | 8.3 Communication Agent (wraps Phase 3/6 GPT-4o calls, all HITL-only) | ✅ Done |
| | 8.4 Enrichment Specialist (wraps sequential pipeline, max 5 LangGraph steps) | ✅ Done |
| | 8.5 Stock Monitor Agent | ✅ Done |
| | 8.6 MCP servers (search, catalog, email dispatch, shipment) | ✅ Done |
| | 8.7 Agent trajectory snapshots (20 golden paths, CI Gate 6) | ✅ Done |
| | **Phase 8 complete — all 8 sub-phases verified** | ✅ |
| **9 — n8n** | 15 workflow JSONs (WF-01 through WF-15) | ✅ Done |
| | **Phase 9 complete — all 17 workflows implemented (WF-01–WF-15 + WF-10a/b/c)** | ✅ |
| **10 — Admin UI** | Operations dashboard + all feature UIs + HITL keyboard shortcuts | ⬜ Pending |
| **11 — Storefront** | Consumer store + cart + checkout (Stripe/OMT/Whish) + consumer chatbot | ⬜ Pending |
| **12 — MLOps** | Drift detection (PSI) + MLflow experiment tracking + champion/challenger | ⬜ Pending |
| **13 — CI/CD** | All 9 gates verified to catch their target failure mode | ⬜ Pending |
| **14 — Deploy** | VPS production deployment + Caddy HTTPS + smoke test | ⬜ Pending |

---

## Plan & Specs

- Full 15-phase implementation plan: `resources/plan/plan.md`
- Approved feature decisions (DEC-001–DEC-029): `resources/understanding_brainstorm/approved.md`
- SpecKit docs (written before each phase's code): `specs/`
- n8n workflow exports (15 workflows, 17 JSON files): `n8n/workflows/`
- Versioned prompt templates: `backend/prompts/`
- ML eval thresholds: `backend/ml_config/eval_thresholds.yaml`
- Drift thresholds: `backend/ml_config/drift_thresholds.yaml`
