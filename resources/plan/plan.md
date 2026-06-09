# Mawrid — Implementation Plan

*Updated: 2026-06-07*

---

## Architecture Decision — Modular Monolith

**Choice: Modular Monolith (not microservices, not a single ball of mud)**

The bootcamp lesson from Week 8 is clear: Segment split too early, operational overhead overwhelmed, and they merged back. Shopify and Instagram shipped fast as monoliths and split only when forced by scale. For a capstone, a modular monolith is the correct choice — most of the benefit of clean separation, none of the distributed systems overhead.

One FastAPI application, one Docker Compose stack, strict internal module boundaries enforced by convention rather than network calls. Each module (catalog, procurement, dunning, suppliers, customers, storefront) owns its domain and does not reach into another module's internal code — only through defined service interfaces.

**Why not microservices right now:**
- One team, one codebase, one deploy — no network debugging between services
- Transactions across modules are trivial (same DB session)
- Can be split later if a module genuinely needs separate scaling or release cadence — the clean boundaries make extraction straightforward

**Guiding clean architecture rule (from Week 8):**
- `core/` — domain models + pure business logic — zero external dependencies
- `infra/` — database, Redis, MinIO, LLM clients — always points IN to core, never the reverse
- `api/` — HTTP routing only — calls services, returns responses, no business logic here
- `agents/` — LangGraph agents — use infra clients, call core services, never own business logic
- Protocols (typing.Protocol) define plug shapes for external dependencies — FakeGateway for tests, real gateway in production

---

## Project File Structure

```
mawrid-ai-platform/
│
├── backend/
│   ├── app/
│   │   │
│   │   ├── api/                          # HTTP layer: routing, request parsing, response shaping only
│   │   │   ├── deps.py                   # JWT parsing, tenant_id extraction, DB session + repo injection
│   │   │   ├── auth.py                   # Feature: Auth — signup, login, JWT issuance
│   │   │   ├── catalog.py                # Feature: Catalog Enrichment — upload, status, barcode lookup, DLQ
│   │   │   ├── procurement.py            # Feature: Procurement — drafts, POs, shipments, receiving, publishing
│   │   │   ├── dunning.py                # Feature: Dunning Engine — sequences, tracks, manual triggers, stop
│   │   │   ├── invoices.py               # Feature: Invoice Management — list, aging, PDF download, manual paid
│   │   │   ├── suppliers.py              # Feature: Supplier Intelligence — CRUD, events, discovery, scoring
│   │   │   ├── customers.py              # Feature: Customer Management — CRUD, segmentation
│   │   │   ├── hitl.py                   # Feature: HITL Approval Center — list, approve, reject, edit
│   │   │   ├── search.py                 # Feature: RAG Search — internal catalog + storefront scopes
│   │   │   ├── chat.py                   # Feature: AI Chatbot — admin (any business question) + consumer (published)
│   │   │   ├── storefront.py             # Feature: Storefront — published products, cart, checkout, consumer orders
│   │   │   ├── webhooks.py               # Feature: Payment Webhooks — Stripe/OMT/Whish inbound events (verify + dispatch)
│   │   │   └── admin.py                  # Feature: Operations Dashboard — summary, AI health, n8n status
│   │   │
│   │   ├── core/                         # Domain logic — NO imports from infra, agents, or api
│   │   │   │
│   │   │   ├── auth/                     # Feature: Authentication & Tenant Onboarding
│   │   │   │   ├── models.py             #   Tenant, User, Role enum
│   │   │   │   └── services.py           #   AuthService: signup, login, JWT creation, triggers tenant provisioning
│   │   │   │
│   │   │   ├── catalog/                  # Feature: Catalog Enrichment
│   │   │   │   ├── models.py             #   Product, Document, EnrichmentStatus enum, InventoryStatus enum
│   │   │   │   ├── services.py           #   EnrichmentService: ingest, dedupe on product_hash, enrich lifecycle
│   │   │   │   └── pipeline.py           #   Pipeline orchestrator: detection → extraction → enrichment
│   │   │   │
│   │   │   ├── procurement/              # Feature: Order Management & Procurement
│   │   │   │   ├── models.py             #   OrderDraft, PurchaseOrder, Shipment, GoodsReceived, DamageReport
│   │   │   │   └── services.py           #   ProcurementService: draft, submit, place_order, receive, publish
│   │   │   │
│   │   │   ├── dunning/                  # Feature: Dunning Engine
│   │   │   │   ├── models.py             #   DunningSequence, Invoice, Track enum (1-4), ToneLabel enum
│   │   │   │   ├── services.py           #   DunningService: trigger, stop, auto_stop_on_payment
│   │   │   │   └── tracks.py             #   Track rules: trigger day, message type, escalation sequence per track
│   │   │   │
│   │   │   ├── suppliers/                # Feature: Supplier Intelligence
│   │   │   │   ├── models.py             #   Supplier, DeliveryEvent, SupplierScore, MatchResult
│   │   │   │   └── services.py           #   SupplierService, ScoringService, MatchingService
│   │   │   │
│   │   │   ├── customers/                # Feature: Customer Management
│   │   │   │   ├── models.py             #   Customer, Segment enum, MatchResult
│   │   │   │   └── services.py           #   CustomerService, MatchingService (waterfall: email → phone → name)
│   │   │   │
│   │   │   ├── hitl/                     # Cross-cutting: HITL gate (used by ALL features)
│   │   │   │   ├── models.py             #   HitlAction, ActionType enum, HitlStatus enum
│   │   │   │   └── services.py           #   HitlService: create, approve, reject, expire, cancel_for_invoice
│   │   │   │
│   │   │   └── storefront/               # Feature: Customer-Facing Store
│   │   │       ├── models.py             #   ConsumerOrder, CartItem, FulfillmentStatus enum
│   │   │       └── services.py           #   StorefrontService, CheckoutService, PublishingService
│   │   │
│   │   ├── infra/                        # External concerns — only layer allowed to use external libs
│   │   │   │
│   │   │   ├── db/
│   │   │   │   ├── base.py               #   TenantRepository: every query auto-scoped to tenant_id (base class)
│   │   │   │   ├── session.py            #   SQLAlchemy async session factory
│   │   │   │   ├── models/               #   ORM models (SQLAlchemy mapped classes)
│   │   │   │   │   ├── tenant.py         #     Tenants, Users tables (root — Tenants has no tenant_id itself)
│   │   │   │   │   ├── product.py        #     Products, ProductEmbeddings (parent + child chunks)
│   │   │   │   │   ├── order.py          #     OrderDrafts, OrderDraftItems, PurchaseOrders, Shipments, GoodsReceived
│   │   │   │   │   ├── dunning.py        #     DunningSequences, Invoices (both B2B and B2C)
│   │   │   │   │   ├── supplier.py       #     Suppliers, DeliveryEvents
│   │   │   │   │   ├── customer.py       #     Customers
│   │   │   │   │   ├── hitl.py           #     HitlActions
│   │   │   │   │   ├── storefront.py     #     ConsumerOrders, ConsumerOrderItems
│   │   │   │   │   ├── graph.py          #     GraphEdges (product→supplier→category knowledge graph edges for GraphRAG)
│   │   │   │   │   └── outbox.py         #     Outbox table (embedding events awaiting relay)
│   │   │   │   └── repos/                #   Repository: one per aggregate, inherits TenantRepository
│   │   │   │       ├── product_repo.py
│   │   │   │       ├── order_repo.py
│   │   │   │       ├── shipment_repo.py
│   │   │   │       ├── invoice_repo.py
│   │   │   │       ├── dunning_repo.py
│   │   │   │       ├── supplier_repo.py
│   │   │   │       ├── customer_repo.py
│   │   │   │       ├── hitl_repo.py
│   │   │   │       └── outbox_repo.py
│   │   │   │
│   │   │   ├── queue/                    #   Feature: Async job queue (ARQ + Redis)
│   │   │   │   ├── client.py             #     Producer: submit_enrichment_job (idempotent on product_hash)
│   │   │   │   └── results.py            #     Poll job status from ARQ result store
│   │   │   │
│   │   │   ├── workers/                  #   Background workers (separate Docker processes)
│   │   │   │   ├── enrichment_worker.py  #     ARQ worker: pull enrichment jobs, run pipeline, write outbox
│   │   │   │   └── outbox_relay.py       #     Relay: drain outbox → generate embedding → write pgvector
│   │   │   │
│   │   │   ├── storage/
│   │   │   │   └── minio.py              #   MinIO client — tenant-scoped bucket paths always
│   │   │   │
│   │   │   ├── vector/
│   │   │   │   └── pgvector.py           #   pgvector search — always includes tenant_id filter
│   │   │   │
│   │   │   ├── secrets/
│   │   │   │   └── vault.py              #   HashiCorp Vault client — backend refuses to start if unreachable
│   │   │   │
│   │   │   ├── payments/                 #   Payment gateway clients (Protocol + per-provider implementations)
│   │   │   │   ├── protocol.py           #     PaymentGateway Protocol: charge(), verify_webhook() — test fake implements this
│   │   │   │   ├── stripe.py             #     Stripe implementation (card payments, international)
│   │   │   │   ├── omt.py                #     OMT implementation (Lebanese network)
│   │   │   │   └── whish.py              #     Whish implementation (Lebanese network)
│   │   │   │
│   │   │   ├── email/
│   │   │   │   └── sender.py             #   Email client (SendGrid/SES): sends invoice PDFs + dunning + notifications
│   │   │   │
│   │   │   ├── messaging/
│   │   │   │   └── whatsapp.py           #   Twilio/Meta Business API client for WhatsApp dispatch
│   │   │   │
│   │   │   ├── scheduler.py              #   APScheduler: registers all daily dunning check jobs (Tracks 1-4)
│   │   │   │                             #   Started in main.py startup; triggers dunning service per schedule
│   │   │   │
│   │   │   └── llm/
│   │   │       ├── openai.py             #   GPT-4o client wrapper (vision + text)
│   │   │       └── embedder.py           #   SentenceTransformer: paraphrase-multilingual-MiniLM-L12-v2 (384-dim)
│   │   │
│   │   ├── agents/                       # LangGraph agents (Supervisor topology)
│   │   │   ├── supervisor.py             #   Supervisor: reads current_task → routes to correct specialist node
│   │   │   ├── extraction.py             #   Extraction Specialist: submits ARQ enrichment job, returns job_id
│   │   │   ├── enrichment.py             #   Enrichment Specialist: ReAct loop, max 5 steps, ToolError handled
│   │   │   ├── communication.py          #   Communication Agent: drafts POs, dunning, outreach, disputes → HITL only
│   │   │   ├── stock_monitor.py          #   Stock Monitor: checks thresholds, creates reorder HITL PO drafts
│   │   │   ├── discovery.py              #   Supplier Discovery: web search → score → HITL outreach per candidate
│   │   │   ├── checkpointer.py           #   AsyncRedisSaver setup: thread_id = {tenant_id}:{user_id}:{session_uuid}
│   │   │   └── mcp_servers.py            #   MCP server registrations: search, catalog, email dispatch, shipment
│   │   │
│   │   ├── rag/                          # 6-technique Advanced RAG pipeline
│   │   │   ├── pipeline.py               #   Orchestrator: runs all 6 techniques in correct order
│   │   │   ├── retrieval.py              #   Dense retrieval (pgvector HNSW) + Parent-Doc chunk mapping
│   │   │   ├── expansion.py              #   HyDE + Multi-Query (3 variants) → RRF merge
│   │   │   ├── reranking.py              #   Cross-Encoder: ms-marco-MiniLM-L-6-v2, top-20 → top-6
│   │   │   ├── graph.py                  #   GraphRAG: networkx knowledge graph, product→supplier→category edges
│   │   │   └── diversity.py              #   MMR: λ=0.5, prevents near-identical chunks reaching LLM
│   │   │
│   │   ├── ml/                           # Classical ML models (loaded from MLflow registry at startup)
│   │   │   ├── intent/
│   │   │   │   ├── tier1.py              #   TF-IDF + Logistic Regression (~80% of traffic, sub-ms)
│   │   │   │   ├── tier2.py              #   DistilBERT fine-tuned → ONNX Runtime (< 100ms)
│   │   │   │   └── classifier.py         #   Cascade: Tier1 → Tier2 → Tier3 (GPT-4o zero-shot)
│   │   │   ├── tone/
│   │   │   │   └── classifier.py         #   Ridge/GBC: 5 features → gentle/neutral/firm (SMOTE balanced)
│   │   │   └── scoring/
│   │   │       └── supplier_scorer.py    #   Ridge regression: delivery events → supplier score (0-100)
│   │   │
│   │   ├── guardrails/                   # NeMo Guardrails + Presidio (active after Phase 5, inherited by all)
│   │   │   ├── presidio.py               #   PII redaction: EN/AR/FR — called before every LLM call
│   │   │   └── nemo/
│   │   │       ├── config.yml            #   input + retrieval + output rails active
│   │   │       ├── prompts.yml           #   self-check prompts (gpt-4o-mini for rail calls — cheap + fast)
│   │   │       └── rails/
│   │   │           ├── input.co          #   Colang: jailbreak, off-topic, prompt injection detection
│   │   │           └── output.co         #   Colang: self-check grounding, hallucination guard
│   │   │
│   │   ├── middleware/                   # FastAPI middleware (applied to all routes)
│   │   │   ├── tenant.py                 #   Extract tenant_id from JWT, attach to request state
│   │   │   ├── rate_limit.py             #   Per-tenant rate limiting using Redis token bucket
│   │   │   └── logging.py                #   Structured JSON logs: request_id, tenant_id, latency_ms
│   │   │
│   │   └── main.py                       # FastAPI app factory: routers, middleware, scheduler start, startup/shutdown
│   │
│   ├── alembic/                          # Database migrations (never bypass with raw SQL)
│   │   ├── env.py
│   │   └── versions/                     # One file per migration, descriptive name
│   │
│   ├── tests/
│   │   ├── unit/                         # Fast, deterministic — LLM always mocked at fixture level
│   │   │   ├── conftest.py               #   FakeLLM, FakePaymentGateway, FakeEmailSender, in-memory state
│   │   │   ├── test_enrichment_pipeline.py
│   │   │   ├── test_order_draft.py        #   Submit vs Place Order separation; draft grouping by supplier
│   │   │   ├── test_goods_received.py     #   Damaged qty logic; dispute prompt trigger; stock = received - damaged
│   │   │   ├── test_dunning_tracks.py     #   Each track trigger day; due_date vs invoice_date verified
│   │   │   ├── test_tone_classifier.py
│   │   │   ├── test_supplier_matching.py  #   Confidence threshold logic; TF-IDF + embedding max
│   │   │   ├── test_customer_matching.py  #   Email → phone → name waterfall; HITL threshold boundaries
│   │   │   ├── test_hitl_service.py       #   Approve/reject/expire/cancel; cancel_for_invoice idempotency
│   │   │   ├── test_payment_autostop.py   #   Idempotent webhook; both sequences + HITL drafts stopped
│   │   │   └── test_publishing.py         #   Stock qty vs published qty independence; retail price separation
│   │   │
│   │   ├── integration/                  # Real DB + Redis, no LLM, no external APIs
│   │   │   ├── conftest.py               #   Test DB setup (separate schema), clean state between tests
│   │   │   ├── test_cross_tenant.py       #   15 attack vectors — ANY pass = CI hard fail
│   │   │   ├── test_queue_idempotency.py  #   Same product_hash → exactly one job queued and executed
│   │   │   ├── test_outbox_relay.py       #   Crash + restart → no duplicates, no missing embeddings
│   │   │   └── test_procurement_flow.py   #   Draft → submit → Place Order → HITL → PO → ship → receive → publish
│   │   │
│   │   └── evals/                        # Probabilistic — run nightly on master, never on every commit
│   │       ├── test_rag_quality.py        #   RAGAS: context_precision, context_recall, faithfulness, relevancy
│   │       ├── test_agent_trajectories.py #   Snapshot: golden node sequence per intent (20 scenarios)
│   │       ├── test_intent_classifier.py  #   F1 macro ≥ 0.85 on held-out test set
│   │       └── eval_dataset/
│   │           ├── rag_questions.json     #   20 question-answer pairs from real enriched catalog
│   │           └── intent_test_set.json   #   150+ labeled intent examples per class
│   │
│   ├── ml_config/
│   │   ├── drift_thresholds.yaml         # PSI thresholds (< 0.10 OK / 0.10-0.20 WATCH / ≥ 0.25 ALARM)
│   │   └── eval_thresholds.yaml          # RAGAS minimums, F1 floor, agent accuracy floor
│   │
│   ├── prompts/                          # Versioned prompt templates (source-controlled, pinned per phase)
│   │   ├── enrichment_agent.yaml         # ReAct enrichment prompt + tool descriptions (max 5 steps enforced here)
│   │   ├── rag_system.yaml               # RAG system prompt: strict grounding, cite product IDs, no invention
│   │   ├── discovery_agent.yaml          # Supplier discovery + scoring prompt
│   │   └── communication/                # Communication Agent prompts — one file per message type
│   │       ├── purchase_order.yaml        #   PO drafting template in AR/FR/EN
│   │       ├── dunning_payables.yaml      #   Track 1: advance reminder to importer (professional tone, fixed)
│   │       ├── dunning_receivables.yaml   #   Track 3: B2B receivables escalation series (tone from classifier)
│   │       ├── dunning_b2c.yaml           #   Track 4: B2C collections with payment link injection
│   │       ├── dispute_letter.yaml        #   Track 2: formal complaint to supplier in their language
│   │       └── fulfillment_notification.yaml  # Consumer fulfillment notification (email in capstone; WhatsApp in Wave 1)
│   │
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/                       # shadcn/ui — fully customized, no default grey theme
│   │   │   ├── catalog/                  # Feature: Internal catalog table, product detail, upload zone
│   │   │   ├── procurement/              # Feature: Order drafts, PO review, shipment timeline, receiving form
│   │   │   ├── hitl/                     # Feature: HITL Approval Center — primary importer workflow
│   │   │   ├── dunning/                  # Feature: Dunning sequences, tracks timeline
│   │   │   ├── suppliers/                # Feature: Supplier table, score bars, outreach log
│   │   │   ├── customers/                # Feature: Customer list, match review queue
│   │   │   └── storefront/               # Feature: Product grid, cart, checkout, chatbot
│   │   │
│   │   ├── pages/
│   │   │   ├── admin/                    # All authenticated admin pages
│   │   │   └── store/                    # Public storefront pages
│   │   │
│   │   ├── hooks/                        # TanStack Query hooks — one file per feature domain
│   │   ├── stores/                       # Zustand stores — cart, auth, UI state
│   │   └── lib/
│   │       ├── api.ts                    # Axios client with JWT header injection
│   │       └── utils.ts
│   │
│   └── Dockerfile
│
├── n8n/
│   └── workflows/                        # All 15 workflow JSON exports (version-controlled)
│       ├── wf01_tenant_provisioning.json
│       ├── wf02_document_uploaded.json
│       ├── wf03_enrichment_complete.json
│       ├── wf04_po_approved.json
│       ├── wf05_shipment_arrival_alert.json
│       ├── wf06_goods_received.json
│       ├── wf07_order_confirmed.json
│       ├── wf08_payment_received.json
│       ├── wf09_payables_trigger.json
│       ├── wf10a_b2c_day3.json
│       ├── wf10b_b2c_day7.json
│       ├── wf10c_b2c_day14.json
│       ├── wf11_stock_threshold.json
│       ├── wf12_receivables_day7.json
│       ├── wf13_receivables_day14.json
│       ├── wf14_receivables_day21.json
│       └── wf15_dispute_filed.json
│
├── specs/                                # SpecKit: written before any code in each phase
│   ├── constitution.md
│   └── features/
│       ├── enrichment.md
│       ├── procurement.md
│       ├── dunning.md
│       ├── supplier.md
│       ├── rag.md
│       ├── storefront.md
│       ├── hitl.md                       # HITL gate spec: all action types, statuses, expiry rules, HITL Rule
│       └── agentic.md                    # Agent topology, Supervisor pattern, checkpoint strategy, MCP tools
│
├── .github/
│   └── workflows/
│       ├── push.yml                      # Every push: lint + mypy + unit tests (< 3 min)
│       ├── pr.yml                        # PR to master: + integration + red-team + snapshots (< 15 min)
│       └── nightly.yml                   # Nightly on master: RAGAS + F1 + drift detection
│
├── .claude/
│   └── commands/                         # Claude Code skills (Phase 0)
│
├── pyproject.toml                        # uv project file: all Python deps + tool config (ruff, mypy, pytest)
├── uv.lock                               # Lockfile — committed to git, reproducible installs across all envs
├── .python-version                       # Python version pin: "3.11"
├── .env.example                          # All env vars documented with descriptions — no real values, committed
├── docker-compose.yml                    # Local dev: all services with health checks
├── docker-compose.prod.yml               # Production overrides
└── Caddyfile                             # HTTPS reverse proxy: api.domain + app.domain + n8n.domain
```

---

## File Header Convention

Every backend Python file begins with a module-level docstring using this format:

```python
"""
Feature:  Catalog Enrichment Pipeline
Layer:    Core / Service
Module:   app.core.catalog.services
Purpose:  EnrichmentService — receives uploaded documents, manages enrichment
          lifecycle (pending → in_progress → complete/partial/failed), deduplicates
          on product_hash, never modifies prices or SKUs from extraction.
Depends:  app.core.catalog.models, app.infra.db.repos.product_repo (injected)
HITL:     None — enrichment is internal only. Publishing is in procurement/services.py.
"""
```

Every frontend TypeScript file begins with:

```typescript
// Feature: HITL Approval Center
// Layer:   Component
// Purpose: HitlActionCard — renders a single pending action with Approve/Reject/Edit
//          inline controls. Keyboard shortcuts: A=Approve, R=Reject, E=Edit.
// API:     PATCH /admin/hitl/{id}/approve | reject | edit
```

These headers are written when the file is created. They are updated when the file's purpose changes. They make `grep -r "Feature: Dunning"` find every file in the dunning stack instantly.

---

## Coding Standards

From the bootcamp coding guidelines, applied throughout the project:

**Package Manager: uv (mandatory — no pip, no poetry, no conda)**
- All dependencies in `pyproject.toml` at the project root
- `uv sync` to install (CI and local) — run from project root always
- `uv run <command>` to run any tool from project root: `uv run pytest`, `uv run ruff check .`, `uv run mypy --strict .`
- `uv.lock` committed to git at project root — ensures identical installs across local, CI, and production
- `.python-version` at project root pins `3.11`
- Dockerfile: `COPY pyproject.toml uv.lock .python-version ./` then `RUN pip install uv && uv sync --frozen`

**Python:**
- Python 3.11, type annotations everywhere, `mypy --strict` must pass
- Pydantic v2 for all request/response schemas: `model_config = ConfigDict(extra='forbid')`, closed enums via `Literal`
- `async/await` everywhere in FastAPI routes and repositories — no blocking calls on the event loop
- SQLAlchemy 2.0 async session — no raw SQL that bypasses RLS
- `random_state=42` on all ML training operations for reproducibility
- Structured logging via `structlog` — every log includes `request_id`, `tenant_id`, `latency_ms`

**Version pinning (critical libraries with known breaking changes between patch versions):**
- `langgraph==0.2.x` — pin exact minor, not `>=0.2`; breaking API changes observed between 0.1 and 0.2
- `langgraph-checkpoint-redis==0.2.x` — must match langgraph minor version exactly
- Use `uv add langgraph==0.2.x langgraph-checkpoint-redis==0.2.x` — do not allow uv to float to latest

**Repository pattern:**
```
TenantRepository (base)
└── auto-injects tenant_id on every query
└── every subclass gets: list(), get(), create(), update(), delete()
└── no raw queries ever leave a repo — domain logic only calls repos
```

**Idempotency rule (from Week 8):**
- At-least-once delivery is the default; every consumer must be idempotent
- ARQ enrichment jobs keyed on `product_hash` — duplicate job = no-op
- Payment webhooks: dedupe table checked inside the same transaction as fulfillment

**Outbox rule (from Week 8):**
- Never dual-write (DB commit + queue publish in two separate operations)
- Enrichment result + embedding event written atomically to DB + outbox
- Outbox relay drains separately — if relay crashes, events survive in Postgres

**Testing rule (from Week 8):**
- LLM always mocked at fixture level in unit tests — FakeLLM returns canned responses
- Integration tests: real DB + real Redis, no LLM, no external APIs
- Evals: real LLM, run nightly, not on every commit
- Snapshot tests for agent trajectories: golden node sequence captured, CI fails if agent takes different path

**Clean architecture rule:**
- `core/` imports nothing from `infra/` or `agents/`
- `infra/` imports from `core/` (for domain models only)
- `api/` imports from `core/` (services) and `infra/` (repos via DI)
- Use `typing.Protocol` for any external dependency that needs a test fake

---

## CI/CD Strategy — Tiered Gates

**Question answered: CI/CD on every push, or only at the end?**

Fast deterministic gates run on **every push to every branch**. Slow probabilistic evals run **nightly on master**. Merge to master is blocked until both the push gates and the latest nightly eval pass.

```
Every push (any branch) — must complete in < 3 minutes:
  Gate 1: uv run ruff check .
  Gate 2: uv run mypy --strict .
  Gate 3: uv run pytest tests/unit/ (LLM mocked, ~200 tests, < 60 seconds)

Every PR to master — must complete in < 15 minutes:
  All push gates +
  Gate 4: uv run pytest tests/integration/ (real DB + Redis, no LLM)
  Gate 5: cross-tenant red-team (15 attack vectors — ANY pass = hard fail)
  Gate 6: agent trajectory snapshot tests (20 known scenarios)

Nightly on master — expensive, slow, probabilistic:
  Gate 7: uv run pytest tests/evals/test_rag_quality.py (RAGAS, real LLM)
  Gate 8: uv run pytest tests/evals/test_intent_classifier.py (F1 macro ≥ 0.85)
  Gate 9: drift detection run — fires alert if PSI > 0.2 or chi-square p < 0.01

Merge to master requires:
  All PR gates green on current commit +
  Nightly eval passed within last 24 hours (or triggered manually)
```

**Why this split:** Tests are deterministic — push them on every commit, catch regressions immediately. Evals are probabilistic and expensive (real LLM calls, RAGAS scoring) — running them on every commit wastes money and adds noise. Tests catch structure; evals catch quality. Both are necessary. Neither replaces the other.

**CI/CD is built in Phase 1 skeleton, but it grows:**
- Phase 1 CI: Gates 1-3 only (unit tests don't exist yet, but the runner is wired)
- Phase 2 CI: unit tests for enrichment pipeline added → Gate 3 grows
- Phase 4 CI: RAGAS eval added → nightly Gate 7 wired
- Phase 7 CI: supplier/customer matching tests added → Gate 3 grows
- Phase 8 CI: agent trajectory snapshots → Gate 6 wired
- Phase 13: all 9 gates verified to catch their target failure mode

---

## Core Build Principle

Every layer of every feature is fully verified before the next layer is touched.
No stacking untested code. No moving forward on assumptions.
If a layer does not work correctly, it is fixed until it does — then the next layer begins.

**HITL Rule:** Every action that sends a message, places an order, or contacts an external party requires explicit importer approval before execution. No exceptions.

**Enrichment ≠ Storefront:** Enriched products go into the internal catalog — the importer's working tool. Products reach the storefront only after: goods are physically received → importer deliberately selects products → retail price is set → published.

---

## Phase Order

```
Phase 0  — Spec & Skills Setup
Phase 1  — Foundation (DB, auth, services, MLflow server, LangSmith)
Phase 2  — Catalog Enrichment Pipeline (internal catalog)
Phase 3  — Order Management & Procurement
Phase 4  — NLP Search & RAG (internal catalog + storefront chatbot, pre-guardrails)
Phase 5  — Guardrails & Security (Presidio + NeMo — applied to Phase 4, re-verified)
Phase 6  — Dunning Engine (4 Tracks) — guardrails already available
Phase 7  — Supplier Intelligence & Customer Management
Phase 8  — Agentic System — guardrails already available
Phase 9  — n8n Automations (15 Workflows)
Phase 10 — Operations Command Center & Admin UI
Phase 11 — Customer-Facing Storefront
Phase 12 — MLOps Governance (drift, champion/challenger, full tracing)
Phase 13 — Full CI/CD Quality Gates
Phase 14 — Production Deployment
```

**Progressive build note (12-day timeline):**
Phases 12, 13, and 14 are NOT built in isolation at the end — they grow throughout:
- MLflow + LangSmith: running from Phase 1. Phase 12 only adds drift detection + governance rules.
- CI gates: Gate 1–3 wired in Phase 1, grow each phase. Phase 13 only audits all 9 catch their target.
- VPS server setup (Phase 14.1): started during Phase 9 in parallel. Phase 14 is final deploy + smoke test.
This means the last day is deploy + verify, not "build three phases in one day."

---

## Phase 0 — Spec & Skills Setup

**Goal:** Working methodology established before a single line of code is written. SpecKit specs exist. Claude Code skills created for repetitive workflows.

### 0.1 SpecKit Documents

- [ ] Create `specs/constitution.md` — project principles, hard constraints, non-negotiables (multi-tenant isolation, HITL on all external writes, no hardcoded secrets, async everywhere, no raw queries bypassing RLS, enrichment ≠ storefront)
- [ ] Create `specs/features/enrichment.md` — full spec for catalog enrichment pipeline (internal catalog)
- [ ] Create `specs/features/procurement.md` — full spec for order draft, PO, shipment tracking, goods received, storefront publishing
- [ ] Create `specs/features/dunning.md` — full spec for dunning engine (4 tracks, all money flows, HITL at every stage; channels: email only in capstone, WhatsApp in Wave 1)
- [ ] Create `specs/features/supplier.md` — full spec for supplier intelligence + customer management
- [ ] Create `specs/features/rag.md` — full spec for RAG pipeline and AI chatbot
- [ ] Create `specs/features/storefront.md` — full spec for e-commerce storefront and checkout (include: consumer order language defaults to tenant storefront language)
- [ ] Create `specs/features/hitl.md` — full spec for HITL gate: all action types, all statuses, expiry rules, HITL Rule; **keyboard shortcuts (A=Approve, R=Reject, E=Edit) are required acceptance criteria**
- [ ] Create `specs/features/agentic.md` — agent topology, Supervisor pattern, checkpoint strategy, MCP tools
- [ ] Each spec contains: what it does, who uses it, inputs, outputs, edge cases, failure modes, acceptance criteria
- [ ] Review all specs against `resources/understanding_brainstorm/approved.md` — confirm no contradictions

**Verify 0.1:** Every core feature has a written spec. Acceptance criteria are measurable, not vague.

### 0.2 Claude Code Skills (Slash Commands)

- [ ] Create `/check-enrichment` skill — runs enrichment pipeline verification checklist
- [ ] Create `/check-procurement` skill — runs order/shipment/receiving verification checklist
- [ ] Create `/check-dunning` skill — runs dunning engine verification checklist
- [ ] Create `/check-rag` skill — runs RAG quality checks
- [ ] Create `/check-tenant` skill — runs cross-tenant isolation test
- [ ] Create `/check-ci` skill — shows current CI gate status
- [ ] Create `/check-hitl` skill — lists all HITL-gated actions and their current state (pending / approved / rejected / expired / cancelled)
- [ ] Create `/phase-status` skill — shows which checklist items are done/pending for current phase
- [ ] Document each skill with: trigger, what it does, expected output

**Verify 0.2:** Each skill invoked successfully. Each returns a clear pass/fail result.

### 0.3 — Synthetic Training Data (Tone Classifier)

*The tone classifier (Phase 6.2) requires 200+ labeled examples across 3 classes. A new project has zero real invoice history. Generate synthetically now — blocking if left to Phase 6.*

- [ ] Write a script `scripts/generate_tone_data.py` that creates realistic invoice/customer/overdue scenarios
- [ ] Each scenario has: days_overdue (0-90), customer_segment (VIP/Regular/At-Risk/Dormant), overdue_amount, payment_history_score (0.0-1.0), previous_dunning_count
- [ ] Label each scenario: gentle / neutral / firm using deterministic rules (these become the ground truth)
  - **Evaluation order: conditions are checked in priority sequence — first match wins. Rules are mutually exclusive by design.**
  - Priority 1 → gentle: days_overdue ≤ 7 (barely overdue — always gentle regardless of segment)
  - Priority 2 → gentle: customer_segment = VIP (relationship preservation — always gentle regardless of history)
  - Priority 3 → firm: (customer_segment = At-Risk OR customer_segment = Dormant) AND days_overdue ≥ 14 AND previous_dunning_count ≥ 2
  - Priority 4 → gentle: payment_history_score ≥ 0.8 (historically reliable payer — gentle if not already firm)
  - Default → neutral: everything else
- [ ] Generate minimum 80 examples per class (240 total) with realistic variation
- [ ] Save to `backend/tests/evals/eval_dataset/tone_training_data.json`
- [ ] Verify class distribution is balanced before SMOTE

**Verify 0.3:** 240 labeled examples generated. All 3 classes represented. File committed to repo.

---

### 0.4 — Synthetic Training Data (Intent Classifier)

*The intent classifier (Phase 8.1) requires 150+ labeled examples per class. Same cold-start problem as the tone classifier — solve it now, not in Phase 8 when the build clock is running.*

- [ ] Define all intent classes covering the full platform (minimum 8 classes):
  - `product_search` — "do you have Samsung TVs?", "show me fridges under $500"
  - `order_status` — "what's the status of my order?", "where is PO-123?"
  - `stock_check` — "how many units of X do I have?", "what's my current inventory?"
  - `shipment_status` — "where is my LG shipment?", "when does the container arrive?"
  - `invoice_query` — "which invoices are overdue?", "show me unpaid B2B invoices"
  - `dunning_action` — "stop dunning on invoice 456", "manually trigger Track 3"
  - `complex_task` — "find me a new appliance supplier and draft outreach", multi-step requests
  - `out_of_scope` — "what's the weather?", "write me a poem", off-topic queries
- [ ] Write `scripts/generate_intent_data.py` — produces labeled examples per class
- [ ] Each example: `{"text": "...", "intent": "product_search", "source": "synthetic"}`
- [ ] Labeling is deterministic: keyword patterns + sentence templates, not LLM-generated (no randomness in ground truth)
- [ ] Generate minimum 150 examples per class (1200+ total) with realistic variation in phrasing (Arabic/French/English mixed)
- [ ] Include hard negatives: near-identical phrases with different intents (e.g., "how many did I order?" vs "how many do I have?" → order_status vs stock_check)
- [ ] Save to `backend/tests/evals/eval_dataset/intent_training_data.json`
- [ ] Split: 80% train / 20% held-out test — held-out set used by CI Gate 8

**Verify 0.4:** 1200+ labeled examples generated. All classes balanced. Train/test split saved. File committed to repo.

---

## Phase 1 — Foundation

**Goal:** Platform exists locally. All services run. Auth works. Database exists with all tables and isolation enforced. CI runs on every push. Observability servers active from day one.

### 1.1 Local Environment

- [ ] `uv` installed locally — `pip install uv` once, then never use pip again for this project
- [ ] `backend/pyproject.toml` created with all Python deps, ruff config, mypy config, pytest config
- [ ] `uv sync` installs dependencies from `uv.lock` — clean, reproducible
- [ ] All Python commands run as `uv run <command>` — no global tool installs
- [ ] All required services defined in Docker Compose and start cleanly:
  - PostgreSQL 16 + pgvector extension
  - Redis 7
  - MinIO
  - HashiCorp Vault (dev mode for local)
  - n8n
  - MLflow tracking server (needed from Phase 2 onwards — start now)
  - LangSmith or local LangFuse (needed from Phase 2 onwards — start now)
  - Backend (FastAPI, Dockerfile uses `uv sync --frozen` then `uv run uvicorn`)
  - Frontend (Vite dev server)
- [ ] Each service has a health check — Docker Compose restarts unhealthy services
- [ ] Environment variables documented in `.env.example` — every variable named and described, no real values
- [ ] No secrets committed to Git at any point
- [ ] Backend returns `{"status": "ok"}` on `GET /health`
- [ ] MLflow UI accessible at `localhost:5000`
- [ ] Tracing UI accessible at `localhost:4000` (or configured endpoint)

**Verify 1.1:** `docker compose up` → all containers healthy. `/health` returns 200. MLflow UI loads. Tracing UI loads.

### 1.2 CI/CD Skeleton

**Push gate (every branch, < 3 minutes):**
- [ ] GitHub Actions workflow file created: `.github/workflows/push.yml`
- [ ] Triggers on every push to any branch
- [ ] CI installs uv: `pip install uv && uv sync --frozen` (matches lockfile exactly)
- [ ] Gate 1: `uv run ruff check .` — fails immediately on any lint error, before tests run
- [ ] Gate 2: `uv run mypy --strict .` — any type error fails the build
- [ ] Gate 3: `uv run pytest tests/unit/` — even if only 1 smoke test exists yet; grows as phases complete
- [ ] Total runtime < 3 minutes

**PR gate (PRs to master, < 15 minutes):**
- [ ] GitHub Actions workflow file: `.github/workflows/pr.yml`
- [ ] Triggers on pull_request targeting master only
- [ ] Runs all push gates first
- [ ] Gate 4: pytest tests/integration/ (added once Phase 1 integration tests exist)
- [ ] Gate 5: cross-tenant red-team test (added in Phase 13 — wired here as a placeholder that passes with 0 tests)
- [ ] Gate 6: agent trajectory snapshots (added in Phase 8)
- [ ] Merge to master blocked until all PR gates pass

**Nightly eval gate (main branch, once per night):**
- [ ] GitHub Actions workflow file: `.github/workflows/nightly.yml`
- [ ] Triggers on schedule: `cron: '0 2 * * *'` (2 AM)
- [ ] Gate 7: RAGAS eval (added Phase 4 — real LLM calls, checks eval_thresholds.yaml)
- [ ] Gate 8: intent classifier F1 eval (added Phase 8)
- [ ] Gate 9: drift detection run (added Phase 12)
- [ ] Failure posts to Telegram channel (pick one: Telegram — consistent with Phase 14.5 Uptime Kuma alerts)

**Pre-commit hooks (local enforcement before push):**
- [ ] `pre-commit` package added to dev dependencies in `pyproject.toml`
- [ ] `.pre-commit-config.yaml` created at project root with two hooks:
  - `ruff` (lint + format) — runs on every `git commit`
  - `mypy --strict` — runs on every `git commit`
- [ ] `uv run pre-commit install` run once after repo clone (documented in README / onboarding notes)
- [ ] Hooks confirmed working: commit a file with a type error → commit rejected locally before push

**Verify 1.2:** Push a file with a lint error → push gate fails in < 60 seconds. Fix it → green. Confirm three separate workflow files exist. Pre-commit hook rejects a bad commit locally.

### 1.3 Multi-Tenant Auth & Isolation

- [ ] Tenant table exists (root table — no tenant_id on itself)
- [ ] User table exists (linked to tenant)
- [ ] Password hashing: **argon2id** via `passlib[argon2]` — never bcrypt, never plain SHA-256 for passwords
- [ ] JWT signing: **RS256** asymmetric — private key loaded from Vault at startup, never hardcoded
- [ ] JWT issued on login contains: user_id, tenant_id, role
- [ ] Access token expiry: **15 minutes**. Refresh token expiry: **7 days** with rotation on every use
- [ ] Refresh token stored as `httpOnly` cookie (not localStorage). Access token kept in memory only
- [ ] Public JWKS endpoint: `GET /auth/.well-known/jwks.json` — exposes RS256 public key for future federation
- [ ] Every authenticated route extracts tenant_id from JWT — never from request body
- [ ] PostgreSQL Row-Level Security enabled on every table that has a tenant_id
- [ ] Repository base class: every query automatically scoped to current tenant — no raw queries bypass this
- [ ] MinIO: each tenant gets an isolated bucket at provisioning
- [ ] Redis: each tenant's keys namespaced as `mawrid:{tenant_id}:{resource_type}:{id}` — prevents cross-tenant key collision
- [ ] CORS: `CORSMiddleware` configured with tenant's registered domain only — wildcard `*` never acceptable
- [ ] Cross-tenant test: Tenant A user requests Tenant B's resources → returns 404 or 403, never the actual data
- [ ] Cross-tenant test added to CI — fails the build if any cross-tenant access succeeds

**Operational mode gating:**
- [ ] `operational_mode` field on tenant record: `hybrid | wholesale_only | retail_only`
- [ ] FastAPI dependency `require_mode(*modes)` — raises 403 if tenant's mode is not in the allowed list
- [ ] Storefront routes (`/store/...`) gated with `require_mode("hybrid", "retail_only")` — Wholesale Only tenants get 403
- [ ] B2C dunning routes gated with `require_mode("hybrid", "retail_only")`
- [ ] B2B Disputes track gated with `require_mode("hybrid", "wholesale_only")`
- [ ] Mode enforced on the backend — frontend reads mode from `/auth/me` and hides irrelevant nav items, but backend is the authority

**Verify 1.3:** Two real tenants exist. Tenant A cannot read, write, search, or download anything belonging to Tenant B through any path. Wholesale-Only tenant receives 403 on any storefront route.

### 1.4 Core Database Schema

- [ ] All tables created via Alembic migrations:
  - tenants (includes `operational_mode` field: hybrid / wholesale_only / retail_only), users
  - products (enrichment_status, inventory_status, storefront_status — three independent state machines)
    - `barcode` field (nullable string — EAN-13/UPC/Code-128/QR; not SKU; lookup by this field in Phase 2.6)
    - `price_history` JSONB field — array of `{price, currency, observed_at}` entries; current price = last entry
    - `reorder_threshold` integer field (nullable — set per product for Stock Monitor in Phase 7.7)
  - order_drafts, order_draft_items
  - purchase_orders, purchase_order_items
  - shipments (status: pending / shipped / in_transit / at_customs / arrived)
  - goods_received, goods_received_items (includes `qty_damaged` field)
  - orders (consumer orders, includes `language` field — set at checkout to tenant storefront language), invoices
  - suppliers (includes `language` field: ar/fr/en), customers (includes `segment` and `language` fields)
  - dunning_sequences
  - hitl_actions (id, tenant_id, action_type, status, payload JSONB, created_at, actioned_at, expires_at)
  - outbox
  - graph_edges (tenant_id, source_product_id, target_product_id, edge_type: same_category/same_supplier/related)
- [ ] pgvector extension active
- [ ] product_embeddings table with vector(384) column, HNSW index, and `chunk_type` tag (parent/child)
- [ ] RLS policy on every table with tenant_id (including hitl_actions)
- [ ] Migrations run forward cleanly on a fresh database
- [ ] Migrations roll back cleanly (downgrade -1 works)

**Verify 1.4:** Fresh database → `alembic upgrade head` → all tables and indexes exist including barcode, price_history, graph_edges → `alembic downgrade -1` → clean rollback.

---

## Phase 2 — Catalog Enrichment Pipeline

**Goal:** A supplier price list in any format becomes a fully enriched, searchable internal working catalog in under 5 minutes. The result is the importer's private tool — not the storefront. Every layer tested independently before the next is built.

---

### 2.1 — Layer 1: File Ingestion

*The file must be received correctly in every format before any processing begins.*

- [ ] Upload endpoint accepts multipart file upload
- [ ] MIME type validation: PDF, Excel (.xlsx), PNG, JPEG — any other type rejected with a clear error
- [ ] File size limit enforced (configurable per tenant)
- [ ] File stored in MinIO at the correct tenant-scoped path immediately on upload
- [ ] Upload returns a document_id for status tracking
- [ ] Upload is idempotent: re-uploading the same file returns the same document_id, no duplicates
- [ ] If MinIO is unavailable: upload fails with a clear error, nothing partially saved
- [ ] Status endpoint: `GET /catalog/ingest/{document_id}/status` returns current stage

**Test every file type:**
- [ ] Upload a clean multi-page PDF with a product table → stored correctly in MinIO
- [ ] Upload an Excel file (.xlsx) with multiple sheets → stored correctly
- [ ] Upload a scanned image (JPEG, low quality, skewed) → stored correctly
- [ ] Upload a PNG screenshot of a WhatsApp price list → stored correctly
- [ ] Upload a .txt file → rejected with validation error
- [ ] Upload a 0-byte file → rejected with validation error
- [ ] Upload a file > size limit → rejected with validation error
- [ ] Disconnect MinIO during upload → error returned, no partial file in storage

**Verify 2.1 before proceeding:** All file types accepted. All invalid inputs rejected. MinIO failure handled gracefully.

---

### 2.2 — Layer 2: Document Structure Detection

*The system must correctly understand what it's looking at before extracting anything.*

- [ ] For Excel files: structure read directly (openpyxl) — columns, headers, data rows identified without vision
- [ ] For PDF files with clear digital text: text extracted directly, tables detected from layout
- [ ] For PDF files that are scanned/image-based: routed to vision model (GPT-4o vision)
- [ ] For image files: pre-processing applied (contrast enhancement, deskew, noise reduction) before vision
- [ ] Vision model call identifies: document type (price list, catalog, invoice), table boundaries, column headers, data rows
- [ ] Output: normalized intermediate format — list of rows, each with column positions
- [ ] If structure detection confidence is low → flagged for manual review, not silently passed forward
- [ ] Structure detection result logged for debugging

**Test document structure detection:**
- [ ] Clean PDF price table (aligned columns, clear headers) → correctly identifies all columns
- [ ] PDF with merged cells → handles gracefully, no crash
- [ ] Multi-page PDF (cover page + product tables) → skips cover, reads product pages
- [ ] Excel with multiple sheets (only one is the price list) → identifies the right sheet
- [ ] Rotated scanned image (90 degrees) → pre-processing corrects orientation
- [ ] Low-quality scan → detected with lower confidence, flagged for review
- [ ] WhatsApp photo (perspective distortion) → structure detected or flagged
- [ ] Document with no table (just text paragraphs) → flagged as non-tabular, not force-extracted

**Verify 2.2 before proceeding:** Detection correct on every file type. Ambiguous cases flagged, never silently wrong.

---

### 2.3 — Layer 3: Data Extraction (NER / BERT)

*Every product field must be extracted correctly and completely before enrichment begins.*

- [ ] NER model processes each detected row
- [ ] Extracted fields per product: name, SKU, barcode (if present), price, unit, quantity, any specification columns
- [ ] Price preserved exactly as written — no rounding, no conversion, no modification
- [ ] SKU preserved exactly — no normalization that would alter it
- [ ] Missing fields are null — never fabricated, never guessed
- [ ] `product_hash` computed per extracted product: deterministic, based on `SHA-256(tenant_id + ":" + product_name + ":" + sku)` when SKU is present, or `SHA-256(tenant_id + ":" + product_name)` when SKU is absent — colon delimiter prevents hash collisions between `("AB", "CDE")` and `("ABC", "DE")`
  - Price is intentionally excluded from the hash — same product re-sent with updated price = same product, updated price (not a duplicate)
  - Price is stored as a versioned field: `price_history` tracks all observed prices with timestamps
  - If price changes on re-upload: existing product updated with new price, previous price archived — not a new catalog entry
- [ ] Extraction result stored before enrichment starts (durable intermediate state)
- [ ] If NER fails on a row → row is flagged, not silently skipped
- [ ] Extraction audit log: original row text + extracted fields side by side

**Test extraction accuracy:**
- [ ] Simple row ("Samsung TV 65inch $499 2 pcs") → correct name, price, qty
- [ ] Row with Arabic product name ("تلفزيون سامسونج ٦٥ بوصة") → name preserved in Arabic, price extracted
- [ ] Row with French description ("Réfrigérateur LG 350L 1200€") → correct extraction
- [ ] Mixed language row (Arabic name, English specs) → handles without corruption
- [ ] Row with price range ("$199-$249") → stored as-is, not forced into single price
- [ ] Row with missing SKU → SKU is null, product still extracted
- [ ] Row with merged specification text → parsed into key-value pairs
- [ ] Row with extra noise (footnote markers, asterisks) → noise stripped, core data preserved
- [ ] Re-extracting the same document → same product_hash values for same rows
- [ ] 5 complete supplier PDFs with 20+ products each → extraction reviewed manually, errors fixed

**Verify 2.3 before proceeding:** Extraction verified manually on real supplier documents. No fabricated data. No silent failures.

---

### 2.4 — Layer 4: Product Enrichment (ReAct Agent)

*Each product enriched with real, accurate information. Agent is bounded and graceful on failure.*

- [ ] Enrichment agent runs per product (not per document)
- [ ] Agent has access to: web search tool, product image search tool
- [ ] Agent is bounded: maximum 5 reasoning steps, then stops
- [ ] Agent target fields: full product description, detailed specifications (key-value pairs), product image URL
- [ ] Agent never modifies price, SKU, or quantity — these come from extraction and are locked
- [ ] If a field cannot be found after max steps → field is null, product saved as partially enriched
- [ ] Tool failure → agent continues with what it has, does not crash
- [ ] ToolError returned on any tool failure — agent handles gracefully
- [ ] Enrichment status tracked per product: pending / in_progress / complete / partial / failed
- [ ] Products enriched in background (do not block the upload response)
- [ ] Duplicate check: if product_hash already fully enriched → skip, do not re-enrich
- [ ] Every enrichment agent call traced in LangSmith (tool used, result, reasoning steps, latency)
- [ ] After enrichment: product enrichment_status = `enriched`, inventory_status = `not_ordered`, storefront_status = `not_published`

**Test enrichment quality:**
- [ ] Common home appliance (Samsung TV) → description and specs found, image found
- [ ] Niche product (local Lebanese brand) → description found or partial, no fabrication
- [ ] Product with Arabic name → web search executed with Arabic query, finds correct product
- [ ] Product with only a price and no SKU → enrichment runs, finds what it can
- [ ] Simulated web search failure → product saved as partial, status = "partial", no crash
- [ ] 5-step limit: product needing 10 searches → stops at 5, saves partial data
- [ ] Re-triggering enrichment on a failed product → runs again correctly
- [ ] 15 products enriched end-to-end → manually review results for accuracy, fix any issues

**Verify 2.4 before proceeding:** Enrichment produces accurate, non-fabricated data. 15-product manual review passes. LangSmith traces visible. Enriched products are in internal catalog only — NOT on storefront.

---

### 2.5 — Layer 5: Queue, Storage & Outbox

*Processing must be reliable, fault-tolerant, and idempotent.*

- [ ] Each extracted product becomes one enrichment job in the Redis queue (ARQ)
- [ ] Job keyed on product_hash — same job submitted twice results in one execution
- [ ] Job retries: 3 attempts with exponential backoff on transient failures
- [ ] After 3 failures: job moves to Dead Letter Queue (DLQ), error recorded with full context
- [ ] DLQ inspectable via admin API: view failed jobs, retry a specific job, discard a job
- [ ] Enrichment result written to database using outbox pattern:
  - Enriched product written to products table
  - Embedding event written to outbox table
  - Both in a single atomic transaction
- [ ] Background relay: picks up outbox events, generates embedding, stores in pgvector, marks event as sent
- [ ] Embeddings generated immediately on enrichment completion (internal catalog is searchable right away)
- [ ] Product images downloaded and stored in MinIO at the correct tenant-scoped path
- [ ] If relay crashes mid-way: on restart, unprocessed outbox events re-processed — no data loss, no duplicate embeddings
- [ ] Progress tracking: `GET /catalog/ingest/{document_id}/status` shows: total products, queued, enriched, partial, failed

**Test queue and storage reliability:**
- [ ] Submit 20 products → verify exactly 20 jobs in queue
- [ ] Submit same 20 products again → queue still has 20, no duplicates
- [ ] Force a job to fail 3 times → appears in DLQ with error detail
- [ ] Retry from DLQ → job executes correctly
- [ ] Kill the relay process mid-embedding → restart → remaining embeddings generated without duplicates
- [ ] Verify: products table + product_embeddings table are in sync for all enriched products

**Verify 2.5 before proceeding:** Queue idempotent. DLQ works. Outbox prevents data loss. All enriched products searchable in internal catalog.

---

### 2.6 — Layer 6: Full Enrichment Integration Test

*The complete pipeline from file upload to searchable internal catalog.*

- [ ] Upload a real 20-product supplier PDF (home appliances)
- [ ] Verify all 20 products extracted correctly
- [ ] Verify all 20 products enriched (or correctly marked partial)
- [ ] Verify all 20 have embeddings in pgvector → searchable in internal catalog
- [ ] Measure total time from upload to searchable: must be under 5 minutes
- [ ] Re-upload same PDF → no new products, no new jobs queued
- [ ] Upload second different supplier PDF → products added to catalog, no mixing
- [ ] Verify: none of the 20 products appear on the storefront (storefront_status = not_published for all)
- [ ] Barcode lookup: assign barcodes to 3 products → `GET /catalog/barcode/{code}` returns correct product in < 500ms

**Verify 2.6:** Full enrichment pipeline works. All products in internal catalog, zero on storefront. Barcode lookup works.

---

## Phase 3 — Order Management & Procurement

**Goal:** The importer browses the internal enriched catalog, selects products, sends purchase orders to suppliers (HITL), tracks incoming shipments, receives and records goods, updates stock, and deliberately publishes selected products to the storefront. This is the core daily workflow for both importers and store owners.

---

### 3.1 — Order Draft Creation

*The importer selects products from the enriched internal catalog and creates a purchase order draft.*

- [ ] Internal catalog view: browse all enriched products with filters (supplier, category, price range, enrichment status)
- [ ] "Add to Order Draft" button per product — quantity field inline
- [ ] Order draft automatically groups selected products by supplier
- [ ] One order draft created per supplier with products from that supplier
- [ ] Order draft shows per-supplier: product list, quantities, unit prices (from extraction), line totals, grand total
- [ ] Draft is editable: change quantities, remove products, add more before submitting
- [ ] Draft linked to source document (which supplier price list it came from)
- [ ] Draft status: draft (editable) → submitted (locked, no more edits)
- [ ] Multiple drafts can exist simultaneously (for different suppliers or different ordering cycles)
- [ ] Desired delivery date per draft (importer can set when they need the goods)
- [ ] Submitted draft shows a "Place Order" button — submitting the draft and sending the PO are two separate actions
  - Submitting = "I'm done selecting products, lock this list"
  - Place Order = "Now draft the PO and send it to the supplier"
  - This separation allows the importer to review the final product list before triggering the PO drafting process

**Test:**
- [ ] Select 5 products from 2 different suppliers → 2 separate drafts created automatically
- [ ] Edit quantities on one draft → quantities updated correctly
- [ ] Change delivery date → saved correctly
- [ ] Add more products to an existing draft → products appended
- [ ] Submit draft → draft status = submitted, no more edits allowed, "Place Order" button appears
- [ ] Do NOT automatically draft PO on submit — only on "Place Order" click

**Verify 3.1:** Order drafts created correctly per supplier. Grouping automatic. Submit locks the draft. Place Order triggers PO drafting.

---

### 3.2 — Purchase Order Communication & HITL

*Basic Communication Agent for PO drafting. HITL before every send. Will be extended in Phase 6 (Dunning) for all other message types.*

- [ ] On "Place Order" click (on a submitted draft): Communication Agent drafts a PO message in the supplier's registered language (AR/FR/EN)
- [ ] PO content: supplier name, importer name + contact, ordered product list (name, qty, unit price), requested delivery date, total value
- [ ] PO format appropriate to channel: formal letter for email, concise structured message for WhatsApp
- [ ] Draft enters hitl_actions table with action_type = "purchase_order_send"
- [ ] Importer reviews in HITL Approval Center: full PO preview, supplier contact details, channel
- [ ] Importer can: Approve → PO sent, Reject → draft discarded, Edit → modify content and re-queue
- [ ] After approval: PO sent to supplier via email (WhatsApp in Wave 1); order status → sent
- [ ] Supplier confirmation logged manually by importer (importer marks order as "confirmed by supplier")
- [ ] PO record created: purchase_order_id, supplier_id, items, total, sent_at, status

**Test:**
- [ ] Submit draft to French-speaking supplier → PO drafted in French → HITL action appears
- [ ] Submit draft to Arabic-speaking supplier → PO drafted in Arabic → HITL action appears
- [ ] Edit PO before approving (change one quantity) → modified PO sent, not original
- [ ] Reject PO → draft discarded, order status = cancelled
- [ ] Approve PO → sent to supplier → order status = sent
- [ ] Verify HITL isolation: Tenant A's PO drafts never visible to Tenant B

**Verify 3.2:** PO drafted in correct language. HITL controls all sending. Nothing sent without approval.

---

### 3.3 — Shipment / Container Tracking

*After a PO is sent, the importer tracks when the goods will arrive.*

- [ ] After PO sent, importer can log shipment details on the order:
  - Carrier name
  - Container or tracking number (optional)
  - Ship date (actual or estimated)
  - Expected arrival date
  - Port or delivery location
- [ ] Shipment record created with status: pending_shipment → shipped → in_transit → at_customs → arrived
- [ ] Importer can update status at each step manually
- [ ] Importer can update expected arrival date (delays are normal — no penalty for changing it)
- [ ] Arrival alert: scheduled daily check → if shipment expected within X days (configurable, default 3) → notification in admin panel
- [ ] Arrival alert also shows on the dashboard under "Upcoming Arrivals"
- [ ] Multiple shipments per PO allowed (partial deliveries from same supplier)
- [ ] Shipment list view: all active shipments with status badges and days until expected arrival

**Test:**
- [ ] Log shipment after PO approved → shipment record created with status = pending_shipment
- [ ] Update status to shipped → in_transit → status updates correctly
- [ ] Change expected arrival date (delay scenario) → updated and reflected in upcoming arrivals
- [ ] Set expected arrival to tomorrow → arrival alert fires in admin panel
- [ ] Two separate shipments for same PO → both tracked independently

**Verify 3.3:** Shipment tracking works. Arrival alerts fire correctly. Delays can be updated without issues.

---

### 3.4 — Goods Received & Stock Update

*When the container arrives, actual received quantities are recorded and stock is updated.*

- [ ] Importer marks shipment as "arrived" from the shipment detail view
- [ ] Goods receiving form appears: for each ordered product, two input fields:
  - `qty_received` — actual received quantity
  - `qty_damaged` — units received in damaged/unusable condition (separate from received qty)
- [ ] Barcode scan option: scan item barcode to auto-fill the row (uses barcode lookup from Phase 2.6)
- [ ] On submit: `qty_in_stock` for each product += `qty_received - qty_damaged` (only undamaged units enter stock)
- [ ] Inventory_status for received products → `in_stock` (if net qty > 0)
- [ ] Discrepancy detection: if `qty_received` < `qty_ordered` by more than 5% → flagged automatically on supplier record
- [ ] Damage detection: if `qty_damaged` > 0 → flagged on supplier record; confirmation screen shows "File supplier dispute for damaged goods?" prompt
  - Clicking "File Dispute" pre-fills the dispute form: product name, qty_damaged, PO reference, shipment ID, damage description field
  - Importer fills damage description → submits → n8n WF-15 fires → Communication Agent drafts formal complaint → HITL queue (same Track 2 flow)
  - Importer can also skip and file the dispute manually later from the supplier detail page
- [ ] Flagged discrepancies and damages recorded on supplier's performance record (feed into supplier scoring in Phase 7)
- [ ] Stock update is atomic — all-or-nothing per receiving event, no partial saves
- [ ] Receiving event logged with timestamp, importer user, received quantities, and damage counts for audit trail
- [ ] After receiving: undamaged units are physically in stock — eligible for storefront publishing

**Test:**
- [ ] Receive all ordered quantities, 0 damaged → all products get correct qty_in_stock, inventory_status = in_stock
- [ ] Receive 100 ordered, log 20 damaged → qty_in_stock += 80, supplier record flagged, dispute prompt shown
- [ ] Receive partial quantities (80% of ordered) → stock updated with actual qty, discrepancy flag fired
- [ ] Receive slightly less than ordered (within 5%) → no discrepancy flag
- [ ] Barcode scan during receiving → correct product row highlighted, qty fields ready
- [ ] Click "File Dispute" from damage confirmation → dispute form pre-filled → HITL draft created (Track 2)
- [ ] Verify: stock update is atomic — kill process mid-submit → restart → no partial updates
- [ ] Receive twice for same shipment → second receive rejected (idempotent)

**Verify 3.4:** Stock accurately reflects undamaged received units. Discrepancies and damages flagged separately. Damaged goods surface Track 2 dispute option at the right moment. Audit trail complete.

---

### 3.5 — Storefront Publishing (Deliberate Selection from Stock)

*After goods are received, the importer selects which products to publish to the web store, sets retail prices, and controls available quantities.*

- [ ] After goods received, products appear in "Ready to Publish" section of catalog view
- [ ] For each product to publish:
  - Set retail price (independent of purchase price — importer decides their margin)
  - Set storefront quantity (may be less than total stock — importer may reserve some for wholesale)
  - Optional: add storefront-specific description override
- [ ] Publishing action: product storefront_status → `published`, appears on customer storefront
- [ ] Unpublish at any time: product removed from storefront, stock remains
- [ ] Update retail price or storefront quantity without unpublishing
- [ ] Storefront shows "Out of Stock" when published qty reaches 0 (does not auto-unpublish)
- [ ] Bulk publish: select multiple products → set price multiplier (e.g., purchase price × 1.3) → publish all
- [ ] **Retail Only mode (store owner)**: toggle "Auto-Publish on Receive" — when enabled, all received products are automatically published at a configurable margin multiplier, importer can still edit individual prices after
- [ ] Admin catalog view shows three separate columns: stock qty / published qty / storefront status

**Test:**
- [ ] Receive 100 units of a product → publish 60 to storefront, keep 40 for wholesale
- [ ] Storefront shows 60 available, admin shows 100 in stock
- [ ] Consumer buys 60 → storefront shows "Out of Stock" → admin stock still shows 40 remaining
- [ ] Unpublish a product → removed from storefront → admin stock unchanged
- [ ] Set retail price different from purchase price → storefront shows retail price
- [ ] Bulk publish 10 products with 1.3x multiplier → all published with correct retail prices
- [ ] Auto-publish toggle (Retail Only mode): receive 5 products → all 5 auto-published with margin

**Verify 3.5:** Storefront only shows deliberately published products. Stock and storefront quantities tracked independently. Retail price and purchase price are always separate.

---

### 3.6 — Procurement Full Integration Test

- [ ] Browse enriched catalog → select 8 products from 2 suppliers → 2 order drafts created
- [ ] Submit draft for Supplier A → PO HITL draft appears in Arabic → approve → PO sent
- [ ] Submit draft for Supplier B → PO HITL draft appears in English → edit one qty → approve → PO sent
- [ ] Log shipment for Supplier A's PO → expected arrival = 3 days from now
- [ ] Arrival alert fires → "Supplier A container arriving in 3 days" visible on dashboard
- [ ] Mark Supplier A shipment as arrived → goods receiving form → enter actual qtys → submit → stock updated
- [ ] Discrepancy in one product (ordered 20, received 18) → flagged on Supplier A's record
- [ ] Publish 4 of 8 received products with retail prices → 4 visible on storefront, 4 not
- [ ] Verify: storefront shows exactly the 4 published products at retail prices
- [ ] Verify: internal catalog shows all 8 enriched products with stock quantities

**Verify 3.6:** Complete procurement cycle works end to end. Stock and storefront are always in correct, separate states.

---

## Phase 4 — NLP Search & RAG

**Goal:** The enriched internal catalog is fully searchable by the importer. Consumers get accurate, cited AI answers from the published catalog. Guardrails will be added in Phase 5 — this phase builds and verifies the RAG pipeline itself.

*This phase begins only after Phase 2 and Phase 3 are fully verified.*

### RAG Pipeline Exact Flow (verified here, guardrails added in Phase 5)

```
User Query
    │
    ▼
[Presidio PII Strip]  ← added in Phase 5, no-op here
    │
    ▼
[NeMo Input Rail]     ← added in Phase 5, no-op here
    │
    ├── HyDE: LLM generates hypothetical product description → embed → search vector
    │
    └── Multi-Query: generate 3 query variants → 4 searches (original + 3 variants)
            │
            ▼
    [RRF Merge] ← merges HyDE results + 3 multi-query results → ranked candidate list
            │
            ▼
    [Dense Retrieval] ← pgvector HNSW, top-20 from child chunks, tenant_id filtered
            │
            ▼
    [Parent-Doc Mapping] ← replace child chunk IDs with their parent chunks (1024 tokens)
            │
            ▼
    [GraphRAG] ← traverse networkx graph from top hits: product→supplier, product→category
                  add structurally related products not reachable by vector distance alone
            │
            ▼
    [Cross-Encoder Reranking] ← ms-marco-MiniLM-L-6-v2, top-20 → reranked → top-6
            │
            ▼
    [MMR λ=0.5] ← diversify: remove near-identical chunks, keep diverse top-6
            │
            ▼
    [LLM Prompt] ← system: strict grounding prompt from prompts/rag_system.yaml
                   context: top-6 parent chunks with product IDs
                   user: original query
            │
            ▼
    LLM generates answer (GPT-4o)
            │
            ▼
    [NeMo Output Rail] ← added Phase 5: self-check (grounded?), facts check (no hallucinated specs?)
            │
            ▼
    Response with citations (product_id links)

Scope filter applied at Dense Retrieval step:
  - Admin chatbot:    WHERE enrichment_status = 'enriched'
                      (all enriched products — regardless of inventory or storefront status)
  - Consumer chatbot: WHERE storefront_status = 'published'
                      (only products the importer has explicitly published to the storefront)
  Both always:        AND tenant_id = {current_tenant_id}
```

### 4.1 — Embedding & Dense Search

- [ ] Embedding model loaded once at startup — `paraphrase-multilingual-MiniLM-L12-v2` (local, 384 dims, EN/AR/FR)
- [ ] Internal catalog search: `GET /catalog/search?q={query}` — returns all enriched products for the tenant
- [ ] Storefront search: `GET /store/search?q={query}` — returns only published products (storefront_status = published)
- [ ] Both searches always filtered by tenant_id — never returns another tenant's products
- [ ] HNSW index confirmed active on pgvector — not a sequential scan

**Test:**
- [ ] Importer searches internal catalog → finds enriched products regardless of storefront status
- [ ] Consumer searches storefront → finds only published products
- [ ] Arabic query finds product with Arabic description (both contexts)
- [ ] French query finds product with French description
- [ ] English "energy efficient fridge" finds relevant products even if listing says "low power consumption refrigerator"
- [ ] Search as Tenant A → zero results from Tenant B's catalog in both contexts

**Verify 4.1:** Two distinct search scopes work correctly. Internal = all enriched. Storefront = published only.

### 4.2 — Parent-Child Retrieval

- [ ] Products chunked into parent (full context, 1024 tokens) and child (precise search, 256 tokens) chunks on embedding
- [ ] Search matches on child chunks, returns parent chunks to LLM
- [ ] Both parent and child embeddings stored in product_embeddings with chunk_type tag

**Test:**
- [ ] Search for a specific spec mentioned in a child chunk → parent chunk (full description) returned to LLM

**Verify 4.2:** Parent chunks delivered to LLM, child chunks used for matching.

### 4.3 — Query Expansion (HyDE + Multi-Query)

- [ ] HyDE: LLM generates hypothetical product description → embed it → use for search
- [ ] Multi-Query: 3 query variants generated → searched in parallel → results merged with RRF
- [ ] Query expansion runs before dense search

**Test:**
- [ ] Vague query ("something to keep food cold") → HyDE generates refrigerator description → finds refrigerators

**Verify 4.3:** Vocabulary gap between user query and catalog bridged.

### 4.4 — Cross-Encoder Re-Ranking

- [ ] `cross-encoder/ms-marco-MiniLM-L-6-v2` loaded locally at startup
- [ ] Top-20 from dense search → re-ranked → top-6 returned
- [ ] Re-ranking runs in < 150ms on CPU

**Test:**
- [ ] 20 candidates where most relevant is not ranked first by dense search → after re-ranking, most relevant is first

**Verify 4.4:** Re-ranking improves relevance. Runs within latency budget.

### 4.5 — GraphRAG

- [ ] Knowledge graph built from catalog: product → category, product → supplier, category → parent category
- [ ] Graph traversal finds related products not reachable by vector distance alone
- [ ] Graph results merged with vector results via RRF
- [ ] Graph is per-tenant

**Test:**
- [ ] Search "washing machine" → vector finds specific model → graph also returns related dryer (same supplier) and another washing machine (same category)

**Verify 4.5:** Graph traversal surfaces structurally related products.

### 4.6 — MMR (Diversity)

- [ ] MMR applied to final 6 candidates before LLM context assembly
- [ ] λ = 0.5 (balance relevance and diversity)
- [ ] 6 near-identical chunks → after MMR → diverse set covering different products

**Verify 4.6:** No 6 near-identical chunks ever reach the LLM context.

### 4.7 — Full RAG Pipeline + AI Chatbot (Pre-Guardrails)

*Built and verified here without guardrails. Phase 5 adds Presidio + NeMo and re-verifies.*

- [ ] Full pipeline: query expansion → RRF merge → dense search → parent-doc mapping → GraphRAG → cross-encoder re-ranking → MMR → LLM generation
- [ ] LLM answers grounded in retrieved chunks — every answer cites which products it references
- [ ] **Importer-facing chatbot (admin panel)**: answers any question about the business through the operations command center
  - Product questions (e.g., "which Samsung TVs are in stock?") → RAG pipeline over ALL enriched products
  - Operational questions (e.g., "what's the status of my LG shipment?", "which invoices are overdue?", "how many units of X do I have?") → routed by 3-tier intent classifier to direct API/DB query, no RAG needed
  - Complex multi-step questions (e.g., "which of my low-stock products have the highest-scoring supplier?") → Supervisor agent with multiple tools
  - Can answer about: orders, shipments, invoices, suppliers, dunning status, stock levels, published products, pending HITL actions
- [ ] **Consumer-facing chatbot (storefront)**: searches across PUBLISHED products only; limited scope — cannot answer operational questions
- [ ] Per-product "Ask about this product" button on both admin product detail and storefront product page → pre-loads that product's context
- [ ] Every LLM call traced in LangSmith: latency, tokens, model ID, retrieved chunks

**Test (without guardrails yet):**
- [ ] Importer asks "which Samsung products are enriched but not yet ordered?" → direct DB query result, no RAG
- [ ] Importer asks "describe the features of the LG OLED TV" → RAG pipeline finds it in internal catalog
- [ ] Importer asks "which invoices from wholesale clients are overdue?" → direct query, returns aging data
- [ ] Consumer asks about same unpublished product → chatbot cannot find it (not in published set)
- [ ] Ask about a published product from consumer chatbot → cited, accurate answer
- [ ] Ask about a product not in catalog at all → honest "we don't have this" response

**Note:** Jailbreak, off-topic, and PII tests deferred to Phase 5 (Guardrails).

**Verify 4.7:** Admin chatbot answers both product and operational questions correctly. Consumer chatbot sees only published products. LangSmith traces visible.

### 4.8 — RAGAS Evaluation

- [ ] Create 20-question evaluation dataset from the real enriched catalog
- [ ] RAGAS metrics computed: context precision, context recall, faithfulness, answer relevancy
- [ ] Thresholds set in `eval_thresholds.yaml`
- [ ] RAGAS evaluation added to CI — fails the build if any metric drops below threshold
- [ ] Cross-tenant RAGAS test: eval queries for Tenant A never return Tenant B context

**Verify 4.8:** RAGAS scores meet thresholds. CI gate active.

---

## Phase 5 — Guardrails & Security

**Goal:** All LLM calls protected. PII redacted before LLM sees it. Jailbreaks blocked. Hallucinated specs caught. After this phase, every subsequent phase (Dunning, Agents, Storefront) inherits these protections automatically.

*After Phase 5, go back and re-verify Phase 4.7 with guardrails active.*

### 5.1 — Presidio PII Redaction

- [ ] Presidio analyzer configured for EN, AR, FR
- [ ] Entities detected: phone numbers, email addresses, credit cards, national IDs, person names, locations
- [ ] Applied to all inbound user messages before any LLM call
- [ ] Applied to all supplier document text before extraction LLM calls
- [ ] Redacted text used by LLM; original text kept in DB for business records
- [ ] Redaction runs as a middleware layer — transparently applied to all LLM entry points

**Test:**
- [ ] "My number is 03-123456" → LLM sees "My number is <PHONE_NUMBER>"
- [ ] Arabic message with name and phone → both redacted correctly
- [ ] French message with email → email redacted correctly
- [ ] No PII in message → message passes through unchanged
- [ ] LangSmith traces show redacted text, not original

**Verify 5.1:** PII redacted in EN/AR/FR before any LLM call. Originals preserved in DB.

### 5.2 — NeMo Guardrails

- [ ] Input rail: jailbreak detection, off-topic detection, prompt injection detection
- [ ] Output rail: self-check (does response match context?), hallucination guard (no specs not in retrieved context)
- [ ] Applied to all LLM calls in RAG pipeline and agent system (middleware — added once, inherited everywhere)
- [ ] Blocked input → polite rejection message returned, no LLM called
- [ ] Blocked output → response not returned, regeneration or fallback message sent

**Test:**
- [ ] "Ignore all previous instructions and..." → blocked by input rail, LLM not called
- [ ] "Act as DAN and..." → blocked by input rail
- [ ] LLM generates spec not in retrieved context → blocked by output rail
- [ ] Off-topic question on store chatbot ("what is the capital of France?") → rejected
- [ ] Valid product question → passes through, answer returned normally
- [ ] Prompt injection in a product description → blocked

**Verify 5.2:** Both rails active on all LLM paths. Jailbreaks blocked. Hallucinated specs blocked.

### 5.3 — Re-Verify RAG with Guardrails Active

- [ ] Run the same Phase 4.7 chatbot tests — all still pass with guardrails active
- [ ] Run jailbreak and off-topic tests — all blocked
- [ ] PII test: user includes phone number in chatbot query → Presidio strips it → answer does not reference the phone number
- [ ] RAGAS scores re-run — guardrails do not degrade RAG quality below thresholds

**Verify 5.3:** RAG quality maintained. Security layer active. Both together work correctly.

### 5.4 — Secrets Management Hardening

- [ ] All external API keys stored in HashiCorp Vault
- [ ] Backend reads secrets from Vault at startup
- [ ] Local dev: .env acceptable for convenience (never committed)
- [ ] Vault access requires authentication — no anonymous access
- [ ] If Vault unreachable at startup: backend refuses to start with clear error

**Verify 5.4:** Remove a secret from Vault → backend startup fails. Restore it → backend starts.

---

## Phase 6 — Dunning Engine (4 Tracks)

**Goal:** All 6 money flows tracked. Every overdue invoice triggers the correct dunning track on the correct day. AI drafts every message (guardrails active from Phase 5). HITL approves before every send. Payment stops everything immediately.

*Each track built and tested independently before the next is added.*

### Dunning Pipeline Flow (same pattern for all 4 tracks)

```
Daily scheduler (n8n or APScheduler) fires per track rule:

Invoice state check
    │
    ▼ trigger condition met (e.g., due_date - today = 3 for Track 1)
    │
    ▼
Already has active sequence for this invoice? → YES → skip (idempotent)
    │ NO
    ▼
Tone Classifier
    │  inputs: days_overdue, customer_segment, overdue_amount,
    │          payment_history_score, previous_dunning_count
    ▼
tone: gentle | neutral | firm | professional (Track 1 bypasses)
    │
    ▼
Communication Agent
    │  inputs: task_type, invoice_data, contact_record, language, tone
    │  NeMo Input Rail → drafts message → NeMo Output Rail
    ▼
Message draft (NOT sent)
    │
    ▼
hitl_actions table
    │  action_type: dunning_{track}_{day}
    │  status: pending
    │  payload: {message, recipient, channel, invoice_ref, tone}
    ▼
Admin HITL Approval Center
    │
    ├── Approve → n8n webhook → message dispatched
    │            (B2B tracks: email only — WhatsApp in Wave 1)
    │            (B2C track: email + SMS)
    │            → dunning_sequence status = sent
    │
    ├── Reject  → sequence paused for this stage
    │
    └── Edit    → modified content → re-queued as pending
                → re-approval required before send

Payment received (any time):
    → hitl_actions WHERE invoice_id = X AND status = 'pending' → status = 'cancelled'
    → dunning_sequences WHERE invoice_id = X → status = 'stopped'
    → invoice.paid_at = now(), status = 'paid'
    (idempotent: same webhook twice = no-op)

6 Money Flows (4 tracks covering all directions):
  Track 1: Importer → Supplier (importer's payable — advance warning TO importer)
  Track 2: Supplier → Importer (dispute, supplier owes refund — letter FROM importer)
  Track 3: Wholesale Client → Importer (importer's receivable — reminder TO wholesale client)
  Track 4: Consumer → Store (store's receivable — reminder TO consumer)
  (Tracks 1+3 = receivable side; Track 2 = dispute; Track 4 = B2C)
```

---

### 6.1 — Core: Invoice Tracking & Payment Status

- [ ] Invoice table tracks: amount, due_date, paid_at (nullable), status (open/paid/overdue/disputed), invoice_type (b2c/b2b_receivable/b2b_payable)
- [ ] `due_date` is always set explicitly at invoice creation:
  - B2C orders: due_date = order date (immediate payment expected)
  - B2B receivables (wholesale clients): due_date = invoice_date + payment_terms_days (NET 30, NET 60 — from the client's contact record)
  - B2B payables (supplier invoices): due_date = as stated on the supplier's invoice
  - Days-overdue calculation: `today - due_date` — always relative to due_date, never to invoice creation date
- [ ] Payment status updated automatically on payment webhook confirmation
- [ ] Invoice aging computed on demand: current, 7d overdue, 14d overdue, 21d+
- [ ] Invoice linked to: consumer order (for B2C), or contact record (for B2B)
- [ ] Idempotency: processing same payment webhook twice does not double-mark an invoice as paid
- [ ] `GET /admin/invoices/aging` returns correct buckets for the tenant

**Test:**
- [ ] Create invoice → mark paid via webhook → paid_at populated, status = "paid"
- [ ] Same webhook twice → invoice still marked paid exactly once
- [ ] Invoke aging endpoint → invoices distributed into correct buckets

**Verify 6.1:** Invoice lifecycle correct and idempotent.

---

### 6.2 — Tone Classifier

**Feature vector per invoice/contact pair:**
```
days_overdue          (int)     — 0 to 90+
customer_segment      (ordinal) — VIP=0, Regular=1, At-Risk=2, Dormant=3
overdue_amount        (float)   — standardized
payment_history_score (float)   — 0.0-1.0, computed from past payment records
previous_dunning_count(int)     — how many times previously dunned for this contact
```

**Model: Gradient Boosting Classifier (or Ridge + OVR) with SMOTE for class balance.**
Why not just rules: a VIP customer 14 days overdue might still get "gentle" if they have a perfect payment history — the ML model learns these interactions. Rules can't.

- [ ] Training dataset: minimum 200 labeled examples across all 3 classes (gentle/neutral/firm)
- [ ] SMOTE applied to training set if any class < 60 examples
- [ ] 5-fold StratifiedKFold cross-validation; F1 macro per class logged to MLflow per run
- [ ] Best run registered in MLflow model registry under name "tone_classifier", stage = "production"
- [ ] Model loaded from MLflow registry at backend startup (not from local file)
- [ ] Tone selection is deterministic: same features → same output always
- [ ] Track 1 (B2B Payables advance reminders): tone always "professional" — bypasses classifier

**Test:**
- [ ] 2 days overdue, VIP customer, 0 previous dunning, high history score → "gentle"
- [ ] 14 days overdue, At-Risk customer, 2 previous dunning → "firm"
- [ ] 7 days overdue, Regular customer, first time → "neutral"
- [ ] Track 1 advance reminder (0 days overdue) → "professional" bypasses classifier, not passed to model
- [ ] Same inputs twice → identical output (determinism)
- [ ] F1 macro on held-out test set logged and meets threshold in eval_thresholds.yaml

**Verify 6.2:** Tone classifier correct on all test cases. SMOTE applied. Registered in MLflow production stage. Loaded from registry at startup.

---

### 6.3 — Communication Agent (Full — Message Drafting)

*Extends the basic PO drafting agent from Phase 3 to handle all dunning message types. Guardrails from Phase 5 are active.*

- [ ] Communication Agent receives: task type, invoice data, contact record, language, tone
- [ ] Drafts: reminder / escalation / formal complaint / final notice
- [ ] Message in the correct language (AR / FR / EN):
  - B2B tracks (1, 2, 3): from contact record's language field (supplier or wholesale client)
  - B2C track (4): from consumer order's language field (defaulted to tenant storefront language at checkout)
- [ ] Message tone matches tone classifier output
- [ ] Payment link embedded in B2C messages (Day 3): unique per invoice URL
- [ ] Formal dispute letter: uses supplier's registered language, formal tone regardless of classifier
- [ ] Draft stored in hitl_actions table — NOT sent
- [ ] NeMo guardrails applied: output rail verifies message is appropriate (no hallucinated invoice amounts)
- [ ] Every Communication Agent call traced in LangSmith

**Test:**
- [ ] B2C Day 3 reminder in English → contains payment link, gentle tone
- [ ] B2B Receivables Day 14 reminder in French → correct French, escalated tone
- [ ] B2B Dispute in Arabic → correct formal Arabic, references specific invoice
- [ ] B2B Payables advance reminder in English → professional tone, exact due date and amount

**Verify 6.3:** All message types draft correctly in all 3 languages. Guardrails active. Nothing sent — drafts in hitl_actions.

---

### 6.4 — HITL Approval Flow (Dunning-Specific)

- [ ] Pending HITL actions visible in admin panel: list of drafts with message preview
- [ ] Each action shows: message content, recipient, channel (email for B2B; email + SMS for B2C), invoice ref, days overdue
- [ ] Importer can: Approve (sent), Reject (discarded, sequence paused), Edit (modify, re-queue as pending)
- [ ] Approved action: triggers send via n8n webhook
- [ ] Rejected action: sequence paused for this stage
- [ ] Edited action: appears in queue with modified content for re-approval
- [ ] Actions expire after 72 hours if not actioned → status = expired, no message sent
- [ ] Tenant isolation: Tenant A's HITL queue never shows Tenant B's dunning drafts

**Test:**
- [ ] Create pending action → appears in admin panel immediately
- [ ] Approve → n8n triggered → message dispatched (test mode)
- [ ] Reject → no message sent, status = rejected
- [ ] Edit → modified message appears → approve → modified message sent (not original)
- [ ] Let expire (set to 5 seconds for test) → auto-expires → no message sent

**Verify 6.4:** HITL correctly controls all dunning dispatch. No message sent without approval.

---

### 6.5 — Track 1: B2B Payables (Importer Pays Supplier)

- [ ] Detect supplier invoices due in 3 days (scheduled daily)
- [ ] Check: already an active payables sequence for this invoice? If yes, skip (idempotent)
- [ ] Communication Agent drafts reminder to importer: "Invoice from [Supplier] due in 3 days — Amount: [X]"
- [ ] Draft enters hitl_actions with action_type = "dunning_payables_advance"
- [ ] After approval: reminder sent to importer
- [ ] Sequence status tracked: pending → sent → stopped (on payment)

**Test:**
- [ ] Supplier invoice due_date = today + 3 days → reminder draft appears in HITL queue
- [ ] Invoice due_date = today + 5 days → no draft (too early)
- [ ] Approve → reminder sent to importer
- [ ] Mark invoice paid → sequence stopped

**Verify 6.5:** Track 1 fires on correct day. Sequence stops on payment. Cannot trigger twice for same invoice.

---

### 6.6 — Track 4: B2C Collections (Store Collects from Consumer)

*Three-stage escalation. HITL required at every stage.*

- [ ] Day 3 overdue: gentle reminder + unique payment link
- [ ] Day 7 overdue: firm reminder (different message, no payment link repeat)
- [ ] Day 14 overdue: final notice
- [ ] Each stage: HITL draft created → importer approves → message sent
- [ ] Never sends Day 7 draft to consumer who has not received Day 3
- [ ] Payment received → all pending HITL drafts for this invoice cancelled → sequence stopped

**Test:**
- [ ] Consumer invoice overdue 3 days → Day 3 HITL draft with payment link
- [ ] Approve Day 3 → sent. Consumer pays 2 days later → Day 7 HITL draft cancelled, stopped
- [ ] Consumer ignores → Day 7 draft appears on Day 7 → Day 14 draft on Day 14
- [ ] Day 7 draft never appears if Day 3 was not approved and sent first

**Verify 6.6:** Three-stage escalation correct. HITL at every stage. Payment stops at any point.

---

### 6.7 — Track 3: B2B Receivables (Importer Collects from Wholesale Client)

- [ ] Day 7: first reminder to wholesale client
- [ ] Day 14: escalated reminder (tone classified per client segment)
- [ ] Day 21: final notice
- [ ] Contact record sufficient — no portal account required
- [ ] HITL draft at each stage → importer approves → message sent via email (WhatsApp in Wave 1)
- [ ] Payment confirmation stops sequence and cancels pending HITL drafts

**Test:**
- [ ] VIP wholesale client 7 days overdue → gentle tone on draft
- [ ] At-risk wholesale client 21 days overdue → firm tone on draft
- [ ] Client pays on Day 10 → Day 14 HITL draft cancelled immediately

**Verify 6.7:** Three-stage escalation correct. Tone per segment correct. HITL at every stage. Email only in capstone.

---

### 6.8 — Track 2: B2B Disputes (Importer Disputes Supplier)

- [ ] Importer manually triggers dispute from admin panel: selects supplier invoice, describes complaint
- [ ] Communication Agent drafts formal complaint letter in supplier's registered language
- [ ] Draft enters hitl_actions with action_type = "dunning_disputes_on_demand"
- [ ] Importer reviews → approve → complaint sent to supplier
- [ ] Importer can edit before approving
- [ ] Dispute record created: date filed, invoice ref, supplier, letter content, status = open

**Test:**
- [ ] Dispute against French-speaking supplier → complaint in French → HITL draft appears
- [ ] Dispute against Arabic-speaking supplier → complaint in Arabic
- [ ] Edit draft before approving → final approved content recorded
- [ ] Approve → sent to supplier via email (WhatsApp in Wave 1)
- [ ] Dispute visible in supplier management panel

**Verify 6.8:** Dispute letter in correct language. HITL present. Dispute record tracked. Email only in capstone.

---

### 6.9 — Payment Auto-Stop

- [ ] Payment webhook (Stripe / OMT / Whish) triggers auto-stop
- [ ] Auto-stop: all active dunning_sequences for that invoice → status = "stopped"
- [ ] Auto-stop: all pending hitl_actions for that invoice → status = "cancelled"
- [ ] Invoice marked as paid, paid_at timestamped
- [ ] Auto-stop idempotent: same webhook twice → no-op

**Test:**
- [ ] Active B2C Day 7 → pending HITL draft → payment webhook → sequence stopped → draft cancelled → invoice paid
- [ ] Multiple active sequences (payables + receivables) → both stopped by one payment
- [ ] Webhook received twice → second processing is a no-op

**Verify 6.9:** No dunning message sent after payment. Even pending HITL drafts cancelled.

---

### 6.10 — Dunning Full Integration Test

- [ ] Create 4 invoices — one scenario for each track
- [ ] Advance each to correct day trigger
- [ ] Verify each track creates the correct HITL draft with correct language and tone
- [ ] Approve each → verify messages dispatched via correct channel
- [ ] Simulate payment for each → all sequences stop, all pending HITL drafts cancelled
- [ ] Check dunning_sequences table: all 4 show correct lifecycle (active → sent → stopped)
- [ ] Admin panel dunning view shows correct state for all 4 scenarios

**Verify 6.10:** All 4 tracks work together. No interference between tracks. Admin panel accurate.

---

## Phase 7 — Supplier Intelligence & Customer Management

**Goal:** Importer manages, discovers, and scores suppliers (or importers, for store owners). Customer records managed and linked to all business records. Guardrails active for all outreach drafts.

*Each component verified independently before combining.*

---

### 7.1 — Customer Records

- [ ] Customer table: name, type (wholesale / retail), email, phone, WhatsApp, language, segment (VIP/Regular/At-Risk/Dormant, default: Regular), tenant_id
- [ ] Customer created automatically from consumer checkout
- [ ] Customer created manually by importer (B2B wholesale client)
- [ ] Duplicate detection: same email for this tenant → link to existing record, no duplicate
- [ ] Customer linked to: all their orders, invoices, dunning sequences
- [ ] `GET /admin/customers` → paginated list with type and segment filters

**Test:**
- [ ] Consumer checks out with email already in system → linked to existing customer, no duplicate
- [ ] Importer adds wholesale client manually → customer created
- [ ] Soft-delete customer → linked invoices and dunning sequences remain intact

**Verify 7.1:** Customer records correct. No duplicates. Segment field available to tone classifier.

---

### 7.2 — Customer Matching (Returning Customers) with HITL Review

**Matching algorithm (waterfall, stops at first match):**
```
Signal 1: Exact email match (same tenant) → confidence 1.0 → auto-confirm, no HITL
Signal 2: Exact normalized phone match (same tenant) → confidence 0.95 → auto-confirm, no HITL
Signal 3: Name fuzzy match only (no email/phone overlap):
    - Normalize: lowercase, strip diacritics
    - TF-IDF token similarity → score
    - Threshold: score ≥ 0.85 → auto-confirm | score < 0.85 → HITL review
Signal 4: No match above 0.3 → create new customer record, no HITL
```

- [ ] On every new order, checkout, or manually added contact: matching waterfall runs automatically
- [ ] Exact email match within tenant → auto-linked, no action needed
- [ ] Exact phone match within tenant → auto-linked
- [ ] Name-only match ≥ 0.85 → auto-linked
- [ ] Name-only match 0.3–0.85 → hitl_actions with action_type = "customer_match_review" — shows proposed match vs incoming contact side by side
- [ ] Name-only match < 0.3 → new customer created automatically
- [ ] Importer in review: Confirm match (linked) / Reject (new customer created) / Assign to different existing customer
- [ ] Match review actions do not expire (no time pressure on importer)
- [ ] Match confidence and signals used recorded on customer record

**Test:**
- [ ] Same tenant, same email → auto-confirmed, no HITL action created
- [ ] Same phone, different name spelling → auto-confirmed (phone wins over name)
- [ ] Similar name ("Ahmad Mansour" vs "Ahmed Mansour"), no email/phone → match review HITL
- [ ] Completely different name, no overlap → new customer, no HITL
- [ ] Importer confirms name match → order linked to existing customer with correct history
- [ ] Importer rejects → order linked to newly created customer record

**Verify 7.2:** High-confidence matches automatic. Low-confidence surfaced for review. No silent wrong matches. Signals and confidence recorded.

---

### 7.3 — Supplier Records & CRUD

*"Supplier" in this context means: overseas supplier for importers, local importer for store owners. Same model.*

- [ ] Supplier table: name, contact_email, contact_phone, WhatsApp, language (ar/fr/en), currency, tenant_id
- [ ] Supplier linked to: all products they supply, all purchase orders, all invoices owed to them, all dunning sequences
- [ ] `POST /admin/suppliers` → create supplier
- [ ] `PUT /admin/suppliers/{id}` → update contact info, language
- [ ] `POST /admin/suppliers/{id}/event` → record delivery event (on_time / late / damaged / wrong_item / discrepancy)
- [ ] Delivery event updates performance_history and triggers score recalculation

**Verify 7.3:** Supplier CRUD works. Events (including discrepancies from Phase 3.4) recorded. History preserved.

---

### 7.4 — Supplier Scoring Model

**Synthetic training data (prerequisite — cold-start problem, same approach as Phase 0.3):**
- [ ] Write `scripts/generate_supplier_score_data.py` — generates 60 synthetic supplier profiles
- [ ] Each profile has: on_time_delivery_rate (0.0–1.0), damage_rate (0.0–0.3), avg_price_vs_market (0.7–1.5 multiplier), response_time_hours (1–168), catalog_completeness (0.0–1.0), discrepancy_rate (0.0–0.2)
- [ ] Label each profile with a ground-truth score (0–100) using deterministic rules:
  - Base score = 100
  - `– (1 - on_time_delivery_rate) × 40` (delivery reliability is the most weighted factor)
  - `– damage_rate × 30`
  - `– max(0, avg_price_vs_market - 1.0) × 15` (penalise above-market pricing only)
  - `– (response_time_hours / 168) × 10`
  - `– (1 - catalog_completeness) × 5`
  - Clamped to [0, 100]
- [ ] Save to `backend/tests/evals/eval_dataset/supplier_score_data.json`
- [ ] Real delivery events (from Phase 3.4 discrepancies and Phase 7.3 events) replace synthetic data post-launch

- [ ] Features: on_time_delivery_rate, damage_rate, avg_price_vs_market, response_time_hours, catalog_completeness, discrepancy_rate
- [ ] Classical ML model (Ridge regression or similar) trained on synthetic-rated supplier set (replaced with real data post-launch)
- [ ] Score updated automatically after every new delivery event or discrepancy flag
- [ ] Score components shown separately (importer sees WHY a supplier is scored low)
- [ ] Model registered in MLflow model registry under stage = "production"

**Test:**
- [ ] Supplier with all on-time deliveries, low prices, full catalog → high score
- [ ] Supplier with 2 late deliveries + discrepancy → score drops, breakdown shows cause
- [ ] Adding on-time event → score recalculates upward

**Verify 7.4:** Scoring accurate, explainable, updated in real time.

---

### 7.5 — Supplier-Product Matching with HITL Review

**Matching algorithm (3-tier, same pattern as customer matching):**
```
1. Exact normalized name match (lowercase, strip punctuation) → confidence 1.0 → auto-link
2. TF-IDF cosine similarity on supplier name tokens → score 0.0-1.0
   OR multilingual sentence embedding cosine → score 0.0-1.0
   Take max of the two scores
3. Threshold: score ≥ 0.9 → auto-link | score 0.3-0.9 → HITL review | score < 0.3 → unknown supplier
```

- [ ] Every product has an optional `supplier_id` link
- [ ] During enrichment extraction: NER extracts supplier name from document header/letterhead
- [ ] Extracted supplier name normalized and matched against all tenant's supplier records
- [ ] Exact match → auto-linked with confidence 1.0
- [ ] TF-IDF or embedding cosine ≥ 0.9 → auto-linked
- [ ] Score 0.3–0.9 → hitl_actions with action_type = "supplier_match_review" (importer sees both names side by side)
- [ ] Score < 0.3 (no recognizable match) → hitl_actions with "create new supplier?" prompt
- [ ] Importer can manually assign or re-assign supplier to any product at any time
- [ ] Match confidence and algorithm used recorded on the product record for audit

**Test:**
- [ ] "Samsung Electronics Co. Ltd" matches existing "Samsung Electronics" → exact normalized match → auto-linked
- [ ] "LG Electroniq" (typo) matches "LG Electronics" → cosine score ~0.92 → auto-linked
- [ ] "رمي للتوزيع" (Arabic) matches Arabic name in suppliers table → embedding similarity → auto-linked or HITL
- [ ] Completely new supplier name with no record → HITL action with creation prompt
- [ ] Catalog with no supplier name extractable → supplier_id remains null, no HITL (null is valid)

**Verify 7.5:** High-confidence matches automatic. Low-confidence surfaced for review. Algorithm and score recorded.

---

### 7.6 — Supplier Discovery with HITL Outreach

- [ ] Discovery request: importer provides product category, optional location preference
- [ ] Supplier Discovery Agent searches for potential suppliers via web search
- [ ] For each discovered supplier: estimate scoring features, compute estimated score with confidence label
- [ ] Results ranked by estimated score
- [ ] Communication Agent drafts initial outreach in correct language for each
- [ ] Guardrails active on all drafted outreach
- [ ] All outreach drafts enter hitl_actions with action_type = "supplier_outreach"
- [ ] Importer: approve / reject / edit then approve
- [ ] After approval: outreach sent, supplier record created with status = "contacted"

**Test:**
- [ ] Request discovery for "home appliances" → returns ranked list
- [ ] Arabic-language website → outreach in Arabic
- [ ] Reject one → discarded, others still pending
- [ ] Edit one → modified version approved → sent

**Verify 7.6:** Discovery returns ranked results. Outreach in correct language. HITL controls all contact.

**Timeline risk:** If Phase 7 exceeds its allocated time, Supplier Discovery (this sub-phase) is the designated drop. Replace `discovery.py` with a stub that returns an empty candidate list and logs a `feature_disabled` warning. The Supervisor topology does not change — the node exists but has no real implementation. The rest of Phase 7 (scoring, matching, reorder, segmentation) ships as planned. Supplier Discovery can be activated in Wave 1 when timeline permits.

---

### 7.7 — Reorder Automation with HITL

- [ ] Each product has a configurable `reorder_threshold` (qty)
- [ ] Stock Monitor checks stock levels (scheduled daily + triggered on goods received)
- [ ] When qty falls below threshold: identify best-scored supplier for that product category
- [ ] Communication Agent drafts PO in supplier's language (uses Phase 3 PO drafting logic)
- [ ] PO draft enters hitl_actions with action_type = "purchase_order_send"
- [ ] Importer reviews → approve / reject / edit

**Note:** This uses the same purchase_order_send HITL flow as Phase 3, but triggered by stock threshold rather than manual order draft.

**Test:**
- [ ] Set product qty to 0 (below threshold) → PO HITL draft appears in queue
- [ ] Multiple products below threshold from different suppliers → separate PO draft per supplier
- [ ] Approve → sent to supplier in correct language

**Verify 7.7:** Reorders triggered correctly. HITL controls sending.

---

### 7.8 — Customer Segmentation

- [ ] Segment field on customer record: VIP / Regular / At-Risk / Dormant (default: Regular)
- [ ] Manual segment assignment by importer in admin panel
- [ ] Segment used by tone classifier (Phase 6.2)
- [ ] Segment visible in customer list view

*Note: Automated K-means segmentation is Wave 1.*

**Verify 7.8:** Segment manageable in admin panel, correctly used by tone classifier.

---

### 7.9 — Supplier & Customer Integration Test

- [ ] Full supplier lifecycle: create → upload catalog (enrichment) → HITL supplier match review → record 5 delivery events → score updates → stock falls below threshold → reorder PO HITL → approve → PO sent
- [ ] Full customer lifecycle (B2C): checkout → customer record created → invoice → overdue → B2C dunning HITL at Day 3, 7, 14 → consumer pays → sequences stopped
- [ ] Full customer lifecycle (B2B): importer adds wholesale client → invoice → overdue → B2B receivables HITL at Day 7, 14, 21 → payment → stopped
- [ ] Supplier discovery: request → discover 3 candidates → HITL outreach for all 3 → approve 1 → sent → supplier added as "contacted"
- [ ] Customer match review: order with low-confidence match → HITL review → importer confirms → order linked

**Verify 7.9:** All lifecycles work end-to-end. HITL at every external action point.

---

## Phase 8 — Agentic System

**Goal:** 3-tier classifier routes correctly. Supervisor orchestrates specialists. Every write action is HITL-gated. Guardrails active (from Phase 5). Agents survive server restarts.

### 8.1 — Intent Classifier (3 Tiers)

- [ ] Define intent classes covering all platform operations (including procurement intents: order, track shipment, receive goods)
- [ ] Training dataset: minimum 150 labeled examples per class
- [ ] Tier 1: TF-IDF + Logistic Regression → fast, handles ~80% of messages
- [ ] Tier 2: fine-tuned DistilBERT → exported to ONNX → fast inference < 100ms
- [ ] Tier 3: LLM zero-shot (with guardrails active)
- [ ] Fixed workflow handlers: product search, order status, price check, stock check, shipment status
- [ ] COMPLEX_TASK intent → routes to Supervisor agent
- [ ] Classifier accuracy CI gate: F1 macro ≥ 0.85
- [ ] Tier 1 + Tier 2 model artifacts registered in MLflow

**Contingency — DistilBERT fine-tuning slip:** If Tier 2 cannot be completed within the Phase 8 timeline (fine-tuning takes longer than expected or ONNX export fails), skip Tier 2 and run the cascade as Tier 1 → Tier 3 (GPT-4o zero-shot) directly. This decision must be made by Day 3 of Phase 8 — not after the deadline. Tier 2 can be added in Phase 12 as a model registry update without changing the classifier interface.

**Test:**
- [ ] "Do you have Samsung TVs?" → Tier 1 → product search, no LLM call
- [ ] "Find me the cheapest supplier for home appliances and draft an outreach" → COMPLEX_TASK → Supervisor
- [ ] "Where is my shipment from LG?" → Tier 1 → shipment status lookup, no LLM call
- [ ] "What's the weather?" → OUT_OF_SCOPE → rejected, guardrails confirm correct

**Verify 8.1:** Tiers cascade correctly. ~80% resolved by Tier 1/2. CI gate active.

### 8.2 — Supervisor Agent + 5 Specialists

**LangGraph topology — Supervisor pattern:**
- Supervisor StateGraph: typed state `{messages, current_task, tenant_id, thread_id, specialist_result, hitl_action_ids}`
- Conditional edge on Supervisor node: task_type → routes to correct specialist node
- Every node is an async function: receives state, returns Command(update=..., goto=next_node)
- Read tools (search, stock check, catalog browse) execute immediately — no HITL needed
- Write tools (send message, place order, contact supplier) — Communication Agent writes to hitl_actions, never executes directly

**Redis Checkpointing (LangGraph AsyncRedisSaver):**
- `thread_id = f"{tenant_id}:{user_id}:{session_uuid}"` — tenant-scoped, collision-proof
- State checkpointed after every node execution — crash-safe
- Same thread_id on reconnect → graph resumes from last completed node, not from beginning
- Time-travel replay available in LangSmith for debugging any past run

- [ ] LangGraph StateGraph built with Supervisor topology (5 specialist nodes)
- [ ] AsyncRedisSaver wired as checkpointer — same Redis as ARQ queue, different key prefix
- [ ] thread_id format `{tenant_id}:{user_id}:{session_uuid}` enforced in all agent invocations
- [ ] State typed with TypedDict — mypy validates all state accesses
- [ ] Agent state survives `docker restart backend` — same conversation resumes
- [ ] Enrichment Specialist: ReAct loop, max_steps=5 hard cap, ToolError handled gracefully
- [ ] Communication Agent: only write tool is `write_hitl_draft(action_type, payload)` — nothing sent directly
- [ ] Bulk operation guard: if task involves >10 products, Supervisor pauses and returns count for confirmation before proceeding
- [ ] All LangGraph node executions traced in LangSmith with step name, duration, tool used

**Test:**
- [ ] "Process my new supplier catalog" → Extraction Specialist → ARQ job queued → job_id in state
- [ ] "Re-enrich all 50 LG products" → bulk guard fires → count returned → importer confirms → 50 ARQ jobs
- [ ] "Draft a reorder PO for LG fridges" → Communication Agent → hitl_actions row created with action_type=purchase_order_send
- [ ] "Find me a new appliance supplier" → Discovery Agent → 3 candidates → 3 hitl_actions for outreach
- [ ] `docker restart backend` mid-task → same thread_id → resumes from last checkpoint, correct state
- [ ] Tenant A thread_id never resolves to Tenant B checkpoint — isolation verified
- [ ] Open LangSmith → find runs above → full node sequence + tool calls visible

**Verify 8.2:** All 5 specialists function. HITL gate holds all write actions. State persistence verified across restart. Checkpoint tenant isolation verified.

### 8.3 — MCP Server Integration

- [ ] MCP servers registered: search, catalog lookup, email dispatch, shipment status lookup
- [ ] All MCP tools tenant-scoped
- [ ] ToolError on MCP failure → agent handles gracefully

**Verify 8.3:** Agents use MCP tools correctly. Tool failures don't crash agents.

---

## Phase 9 — n8n Automations (15 Core Workflows)

**Goal:** All 15 capstone event flows run automatically. Every message-sending workflow has an HITL approval node before any external message is dispatched. n8n never sends without importer approval.

*Each workflow built, triggered manually to verify, then left on schedule/webhook.*

**Invoice PDF generation (prerequisite — build before WF-07):**
- [ ] `POST /api/v1/invoices/generate` endpoint — accepts order_id, returns invoice_id + PDF stored in MinIO
- [ ] PDF built with `reportlab` + `Jinja2` template: invoice number, line items, totals, tenant logo, payment link, due date
- [ ] Unique payment link injected per invoice (tenant payment gateway URL + signed token)
- [ ] Invoice PDF stored in MinIO at `/{tenant_id}/invoices/{invoice_id}.pdf`
- [ ] `GET /api/v1/invoices/{id}/pdf` — returns presigned MinIO URL (15-min expiry) for download
- [ ] Invoice record created in invoices table: amount, due_date, status=open, linked to consumer order
- [ ] WF-07 calls this endpoint after payment webhook confirmation → PDF generated → email with link dispatched

- [ ] **WF-01:** Tenant provisioning → create MinIO bucket, Redis namespace, send welcome email
- [ ] **WF-02:** Document uploaded → call extraction API → queue enrichment jobs
- [ ] **WF-03:** Enrichment complete → update internal catalog status → notify importer "X products ready to browse"
- [ ] **WF-04:** Purchase Order approved (HITL) → send PO to supplier via email (WhatsApp in Wave 1) → create shipment tracking record
- [ ] **WF-05:** Shipment Arrival Alert (scheduled, daily) → find shipments arriving within configured days → admin panel notification + upcoming arrivals badge
- [ ] **WF-06:** Goods Received submitted → update stock quantities → check all products against reorder thresholds → flag discrepancies
- [ ] **WF-07:** Consumer Order confirmed (payment webhook) → generate invoice PDF → email to consumer → order appears in admin with status "pending fulfillment"
- [ ] **WF-08:** Payment received → trigger auto-stop on all active dunning sequences → mark invoice paid → cancel all pending HITL dunning drafts
- [ ] **WF-09:** B2B Payables trigger (scheduled, daily) → find supplier invoices due in 3 days → call Communication Agent API → create HITL dunning drafts
- [ ] **WF-10a:** B2C Day 3 trigger (scheduled, daily) → find overdue B2C invoices at Day 3 → Communication Agent API → HITL drafts with payment links
- [ ] **WF-10b:** B2C Day 7 trigger → same pattern → HITL drafts
- [ ] **WF-10c:** B2C Day 14 trigger → same pattern → HITL drafts
- [ ] **WF-11:** Stock threshold breach (triggered by WF-06 or daily check) → call Stock Monitor API → create reorder HITL PO draft
- [ ] **WF-12:** B2B Receivables Day 7 → find overdue wholesale invoices → Communication Agent → HITL drafts
- [ ] **WF-13:** B2B Receivables Day 14 → same pattern
- [ ] **WF-14:** B2B Receivables Day 21 → same pattern
- [ ] **WF-15:** B2B Dispute filed (webhook from admin panel) → Communication Agent → HITL dispute draft

- [ ] All workflows: HITL approval node before any outbound message — n8n waits for approval webhook from admin
- [ ] All workflows: exported as JSON to `n8n/workflows/` (version-controlled)

**Test each workflow:**
- [ ] Manually trigger each via n8n UI
- [ ] Verify correct FastAPI API calls (check backend logs)
- [ ] Verify HITL action created in hitl_actions table
- [ ] Approve HITL action via admin panel → verify n8n sends the message (test mode)

**Verify Phase 9:** All 15 workflows execute without error. HITL gate in every message-sending workflow.

---

## Phase 10 — Operations Command Center & Admin UI

**Goal:** Importer has one stunning admin panel with complete visibility and control. HITL Approval Center is the centerpiece. Procurement pipeline fully visible and manageable.

### 10.1 — Backend APIs (Command Center)

- [ ] Dashboard summary: active shipments (upcoming arrivals), outstanding invoices, overdue count, low stock count, pending HITL count (prominent), enrichment queue depth, published products count, stock value, revenue this month
- [ ] HITL management: `GET /admin/hitl/pending`, `POST /admin/hitl/{id}/approve`, `POST /admin/hitl/{id}/reject`, `POST /admin/hitl/{id}/edit`
- [ ] HITL filtering by action_type: dunning / purchase_order_send / supplier_outreach / customer_match / supplier_match / fulfillment_notification
- [ ] Internal catalog endpoints: list all enriched products with filters (enrichment_status, inventory_status, storefront_status), edit, re-enrich, DLQ inspection, DLQ retry
- [ ] Order Draft management: create, edit, submit, view per-supplier
- [ ] Purchase Order management: list, status tracking, link to shipment
- [ ] Shipment tracking: list all shipments with status and expected arrival, update status, log shipment details
- [ ] Goods Received: submit receiving form, view receiving history, view discrepancy log
- [ ] Storefront Publishing: select products to publish, set retail price, set qty, publish/unpublish
- [ ] Consumer Order management: list with payment status, fulfillment status update
- [ ] Order fulfillment notification HITL: when importer marks order as "ready", Communication Agent drafts consumer notification → HITL draft → approve → notification sent
- [ ] Invoice management: list with aging filter, download invoice PDF, manual payment mark
- [ ] Dunning management: active sequences, history, manual override
- [ ] Supplier management: list with scores, event recording, outreach log, purchase order history
- [ ] Customer management: list with type + segment filters, match review queue, customer detail
- [ ] AI health: model versions, RAGAS latest scores, drift status
- [ ] n8n workflow status: last run, next scheduled run, success/fail

**Verify 10.1:** All endpoints return correct tenant-scoped data.

### 10.2 — Admin UI Design

*UI must be stunning. Not adequate — stunning. Every screen should feel professional, modern, and intentional.*

- [ ] Design system: deep navy + warm amber accent, typography, spacing scale, component variants
- [ ] Dark mode and light mode — both polished
- [ ] shadcn/ui as base — fully customized, no default grey theme
- [ ] Smooth page transitions and micro-interactions (Framer Motion)
- [ ] Data tables: sortable, filterable, loading skeletons (not spinners)
- [ ] Status indicators: color-coded badges across all states (enriched, ordered, in_transit, in_stock, published, overdue, paid, etc.)
- [ ] Charts: revenue vs outstanding, dunning pipeline, enrichment progress, stock levels, supplier scores
- [ ] Empty states: designed, with helpful call-to-action
- [ ] Error states: designed, branded
- [ ] Responsive: works on tablet for warehouse use

### 10.3 — Admin Panel Screens

- [ ] **Dashboard:** summary cards + charts + upcoming shipments widget + recent HITL actions + AI health + quick actions ("Upload Catalog", "Add Supplier", "View Pending Approvals")
- [ ] **HITL Approval Center:** Most important screen. All pending actions grouped by type. Each card: preview of message/PO/match, recipient, channel, invoice ref. Approve/Reject/Edit inline. Keyboard shortcuts (A=Approve, R=Reject, E=Edit). Badge on nav showing count.
- [ ] **Internal Catalog:** product table with tri-status badges (enrichment / stock / storefront) + upload drag-drop zone + barcode scanner + product detail slide-over (edit, re-enrich, publish toggle, retail price)
- [ ] **Procurement:** Order drafts list → create new draft → submit draft → PO history → link to shipments
- [ ] **Shipments:** timeline view of all active shipments with expected arrival, status updates, receiving button when arrived
- [ ] **Goods Received:** receiving form (scan or manual qty entry) + receiving history + discrepancy log
- [ ] **Storefront Publishing:** products ready to publish list (in_stock, not_published) + set retail price + qty + publish action
- [ ] **Suppliers:** table with score bars + add supplier + supplier detail with performance chart + PO history + outreach log
- [ ] **Customers:** table with type/segment badges + match review queue tab + customer detail with order history + invoice aging
- [ ] **Consumer Orders:** table with payment + fulfillment status + fulfill button → HITL notification flow
- [ ] **Invoices:** table with aging color-coding + PDF download + manual payment mark + dunning sequence status
- [ ] **Dunning:** active sequences timeline + completed history + manual stop option
- [ ] **Automations:** status cards for all 15 n8n workflows with last run, next run, success/fail, manual trigger
- [ ] **AI Health:** model cards + RAGAS score gauges + drift alert panel
- [ ] **Settings:** operational mode selector (Hybrid/Wholesale/Retail), reorder thresholds, auto-publish toggle, payment gateway config

**Verify 10.3:** Every screen reviewed for visual quality, not just functionality. HITL Approval Center requires ≤ 2 clicks to approve any pending action.

---

## Phase 11 — Customer-Facing Storefront

**Goal:** A stunning public storefront powered by deliberately published products. Consumers discover, explore, ask questions, and buy in one smooth flow.

### 11.1 — Storefront Design

*Storefront must be stunning. First impression of the importer's brand.*

- [ ] Custom theme per tenant (colors, logo, fonts) — configured in admin settings
- [ ] Hero section: clean, branded, fast-loading
- [ ] Product grid: enriched images (from enrichment pipeline), names, retail prices — consistent card design
- [ ] Product detail page: image gallery, full description, specifications table, AI chatbot entry, add to cart
- [ ] Search bar: prominent, fast, live results as you type (debounced 300ms)
- [ ] Mobile-first: perfect on phones (Lebanon browses on mobile)
- [ ] Page load: fast — WebP images, lazy load, minimal JS blocking

### 11.2 — Product Discovery & Search

- [ ] Storefront search uses the published-only RAG pipeline (from Phase 4.1)
- [ ] Category browse: filter by product category
- [ ] Sort by: price low/high, newest, in-stock first
- [ ] Out-of-stock products shown but grayed with "Out of Stock" badge
- [ ] Only published (storefront_status = published) products shown
- [ ] Dense search response: < 300ms. Full RAG response: < 2s

**Verify 11.2:** Storefront shows only published products. Internal catalog products (not yet published) never appear.

### 11.3 — AI Chatbot (Consumer-Facing)

- [ ] Floating chat button on all storefront pages
- [ ] Full chat page `/chat`
- [ ] Per-product "Ask about this product" button → pre-loads product context
- [ ] Answers grounded in published catalog, with product citations linking to product pages
- [ ] Guardrails active (Phase 5): off-topic blocked, PII redacted, jailbreaks blocked
- [ ] Multilingual: AR/FR/EN, receives answer in same language

**Verify 11.3:** Chatbot safe, grounded in published catalog only, multilingual.

### 11.4 — Cart & Checkout

- [ ] Cart: session-based (no account required)
- [ ] Cart badge shows item count in header at all times
- [ ] Real-time stock check on add-to-cart: cannot add more than published storefront qty
- [ ] Checkout: name, email, phone — clean, minimal form
- [ ] Consumer order language: defaults to tenant's configured storefront language (set in admin Settings); stored on the order record at checkout time — used by dunning engine for B2C message language
- [ ] Payment gateways — **Protocol-stub decision:**
  - `PaymentGateway` Protocol defined in `infra/payments/protocol.py` (Phase 1 already defines this)
  - **Stripe**: fully implemented — has a public sandbox, no business registration required. Capstone demo uses Stripe test mode.
  - **OMT + Whish**: implemented as Protocol stubs in capstone — `raise NotImplementedError` with a log message. Real credentials require Lebanese business registration; stubs let CI pass and the architecture is correct. Activate when credentials confirmed.
  - Gateway selection per checkout: tenant config field `payment_gateways: list[str]` — defaults to `["stripe"]`
  - UI shows logos for all configured gateways; Stripe-only in capstone demo is acceptable and not a gap
- [ ] Stripe Elements embedded: card input feels native
- [ ] On payment success: confirmation page + "Invoice sent to [email]"
- [ ] On payment failure: clear error + retry option
- [ ] After successful checkout: n8n WF-07 triggered → invoice generated → consumer emailed → order in admin as "pending fulfillment"
- [ ] Successful checkout decrements storefront published qty (not total stock)

### 11.5 — Order Fulfillment Notification (HITL)

*Handled as a direct API call — no n8n workflow. Fulfillment is admin-initiated (importer clicks a button), not schedule or event-triggered, so n8n adds no value here. The backend handles the full flow.*

- [ ] Admin panel shows consumer orders with status: "pending fulfillment" / "fulfilled"
- [ ] Importer marks order as fulfilled (ready for pickup / shipped) with optional tracking number
- [ ] `POST /admin/orders/{id}/fulfill` → Communication Agent drafts consumer notification → HITL draft with action_type = "fulfillment_notification"
- [ ] Importer reviews in HITL Approval Center → approve → `POST /admin/hitl/{id}/approve` → backend dispatches notification via email (WhatsApp in Wave 1)
- [ ] Importer can edit the draft before approving
- [ ] Order status updated to "fulfilled" after HITL approval

**Test fulfillment HITL:**
- [ ] Consumer completes checkout → order appears as "pending fulfillment"
- [ ] Importer marks ready → HITL draft for notification appears
- [ ] Approve → consumer receives notification with correct order details
- [ ] Edit draft (add "Please bring your ID") → modified notification sent

**Verify 11.5:** Consumer notified via HITL-approved message only. Storefront qty and stock qty remain independently correct.

### 11.6 — Barcode Scan (Warehouse / Admin)

- [ ] Barcode scan button in admin catalog view
- [ ] Camera opens via `@zxing/browser`
- [ ] Scanned barcode → `GET /catalog/barcode/{code}` → product info in < 500ms
- [ ] Result: product name, current stock qty, published qty, retail price, supplier name
- [ ] Works on mobile camera (used during goods receiving for verification)

### 11.7 — Embeddable Storefront Widget

*The importer can embed their storefront chatbot on any existing website (e.g., their own WordPress site) using a single `<script>` tag. The widget is a floating chat button that opens the full RAG chatbot — scoped to their published catalog.*

- [ ] Backend: `GET /api/v1/widget/token` — authenticated admin endpoint; returns a signed short-lived JWT (15-min expiry) scoped to the tenant's published catalog; payload: `{tenant_id, scope: "storefront", exp}`
- [ ] Backend: `/widget.js` served as a public static file — self-contained JS bundle (~20KB) that injects a floating chat button into any page
- [ ] Widget JS: loads the JWT from the embed snippet's `data-token` attribute; sends it as Bearer header on all chat API calls
- [ ] Server-side origin check middleware: validates `Origin` header on widget chat requests against the tenant's configured `allowed_origins` list (set in admin Settings)
- [ ] Admin Settings: `allowed_origins` field — comma-separated list of domains allowed to embed the widget
- [ ] Embed snippet generated in admin Settings: `<script src="https://api.domain/widget.js" data-token="{token}"></script>`
- [ ] Widget UI: floating button (tenant brand color) → slide-up chat panel → same RAG chatbot as storefront, published scope
- [ ] Token refresh: widget requests a fresh token from `/widget/token` every 10 minutes via a tenant-proxied refresh call (avoids CORS issues)

**Test:**
- [ ] Generate embed snippet → paste into a plain HTML file → widget loads, chat works
- [ ] Token expired → widget shows "session expired, click to refresh" — does not error silently
- [ ] Request from non-allowed origin → 403 returned, widget shows error state
- [ ] Widget only surfaces published products (same consumer chatbot scope)

**Verify 11.7:** Widget embeds cleanly. Origin check enforced. Chatbot scoped to published products only. Token expiry handled gracefully.

**Verify Phase 11:** Full consumer journey: land → search → product detail → chatbot → add to cart → checkout (Stripe test mode) → invoice email. Importer marks fulfilled → HITL notification → consumer receives. Widget embedded and functional. All screens visually reviewed.

---

## Phase 12 — MLOps Governance

**Goal:** All ML models versioned, governed, monitored. Drift detected automatically. Champions never silently replaced.

*MLflow and LangSmith have been running since Phase 1. This phase formalizes governance.*

### 12.1 — MLflow Model Registry (Full Governance)

- [ ] All models registered: intent classifier (Tier 1 + Tier 2 ONNX), tone classifier, supplier scorer
- [ ] Each model: version number, SHA-256 artifact hash, training metrics, stage (staging/production/archived)
- [ ] Models loaded from registry at startup — not from local files
- [ ] Champion/challenger gate: before promoting to production, run eval set — new model must match or beat current
- [ ] SHA-256 verified on every model load
- [ ] Downgrade path: archived model can be promoted back without retraining

**Verify 12.1:** Downgrade a model → system serves production version. SHA-256 verified on load.

### 12.2 — LangSmith Tracing (Full Audit)

- [ ] Confirm every LLM call traced from all phases: latency, tokens, model ID
- [ ] Confirm every agent step traced: thought, action, observation, tool name, tool result
- [ ] RAGAS scores attached to traces as metadata
- [ ] LangSmith project: `mawrid-capstone`
- [ ] Trace retention policy configured

**Verify 12.2:** Run one RAG query → open LangSmith → full trace visible.

### 12.3 — Drift Detection

- [ ] PSI for numeric feature drift (intent classifier features)
- [ ] Chi-square for categorical feature drift
- [ ] Cosine drift for embedding distribution (centroid tracking)
- [ ] Runs nightly (APScheduler or n8n)
- [ ] Drift alert surfaced in Admin AI Health dashboard
- [ ] Alert thresholds documented in `ml_config/drift_thresholds.yaml`

**Verify 12.3:** Inject synthetic drift → alert fires → visible in admin panel.

---

## Phase 13 — Full CI/CD Quality Gates

**Goal:** All 9 gates fully wired and verified. The tiered CI/CD strategy (defined in the Architecture section) is complete and proven to catch its target failure mode.

**Push gate — verified to complete in < 3 minutes:**
- [ ] Gate 1: ruff lint — any lint error → immediate fail, no tests run
- [ ] Gate 2: mypy --strict — any type error → fail
- [ ] Gate 3: pytest tests/unit/ — full unit suite with mocked LLM, < 60 seconds
- [ ] Verify: push a lint error → fails in < 60 seconds

**PR-to-master gate — verified to complete in < 15 minutes:**
- [ ] Gate 4: pytest tests/integration/ — real DB, real Redis, no LLM
- [ ] Gate 5: cross-tenant red-team — 15 attack vectors, ALL blocked (ANY pass = hard fail)
  - Tenant A cannot read Tenant B's products, orders, invoices, HITL actions, customers, suppliers
  - Tenant A's HITL actions never visible to Tenant B's admin panel
  - Internal catalog products (not_published) never appear in storefront search for any tenant
  - pgvector search always returns only the querying tenant's embeddings
- [ ] Gate 6: agent trajectory snapshot tests — 20 known intents, golden node sequence verified
- [ ] Merge to master blocked until Gates 1-6 all pass on current commit

**Nightly eval gate — verified to fire and report correctly:**
- [ ] Gate 7: RAGAS eval — context_precision, context_recall, faithfulness, answer_relevancy all meet eval_thresholds.yaml
- [ ] Gate 8: intent classifier F1 macro ≥ 0.85 on held-out test set (150+ examples per class)
- [ ] Gate 9: drift detection — PSI per feature, chi-square on categoricals, cosine on embedding centroid
- [ ] Nightly failure → Telegram alert sent to configured channel
- [ ] Nightly gate result blocks master merge if last nightly failed (enforced via GitHub status check)

**Test every gate catches its failure mode:**
- [ ] Break a lint rule → Gate 1 fails, no other gate runs
- [ ] Add a `# type: ignore` to suppress a real type error → Gate 2 catches remaining type errors
- [ ] Delete a unit test assertion → Gate 3 misses it? Verify it fails — if not, fix the test
- [ ] Add a cross-tenant data leak intentionally → Gate 5 hard-fails
- [ ] Make an enriched-but-unpublished product appear in storefront search → Gate 5 fails
- [ ] Drop RAG quality below threshold → Gate 7 fails on nightly
- [ ] Lower classifier F1 below 0.85 → Gate 8 fails on nightly
- [ ] Inject synthetic feature drift → Gate 9 fires alert

**Verify Phase 13:** All 9 gates wired. Each gate independently verified to catch exactly the failure mode it is named for.

---

## Phase 14 — Production Deployment

**Goal:** Mawrid runs on a real server, HTTPS, automated deployment on every CI-passing push to master.

### 14.1 — Server Setup

- [ ] Hetzner CX22 VPS (or DigitalOcean Basic Droplet) provisioned
- [ ] Ubuntu 24.04 LTS
- [ ] Docker Engine + Docker Compose plugin installed
- [ ] UFW firewall: only ports 22, 80, 443 open
- [ ] fail2ban installed (blocks brute-force SSH)
- [ ] Non-root deployment user

### 14.2 — HTTPS & Reverse Proxy

- [ ] Caddy added to production Docker Compose
- [ ] Caddyfile: routes `api.domain.com` → backend, `app.domain.com` → frontend, `n8n.domain.com` → n8n (restricted access)
- [ ] SSL certificate: automatic via Let's Encrypt
- [ ] All HTTP redirected to HTTPS automatically
- [ ] Internal services (Postgres, Redis, MinIO, Vault) not exposed on public ports

### 14.3 — Production Configuration

- [ ] `.env.prod` on VPS (never in Git)
- [ ] HashiCorp Vault unsealed with production credentials
- [ ] All external API keys in Vault: OpenAI, Stripe, OMT, Whish, Twilio, SendGrid
- [ ] `restart: always` on all Docker services
- [ ] Resource limits set per container (prevent OOM cascades)

### 14.4 — Automated Deployment

- [ ] GitHub Actions deploy workflow: triggers only after all PR gates pass (Gates 1–6) on the master branch commit being deployed; nightly gates (7–9) must have passed within the last 24 hours
- [ ] Deploy: SSH to VPS → git pull → docker compose pull → docker compose up -d → alembic upgrade head
- [ ] Deployment completes in < 2 minutes
- [ ] Rollback: revert commit → push → CI runs → auto-deploys previous version

### 14.5 — Backup & Monitoring

- [ ] Daily PostgreSQL backup: compressed dump to `/backups/` on VPS
- [ ] Backups retained for 7 days, oldest rotated automatically
- [ ] Uptime Kuma: monitors `GET /health` every 60 seconds
- [ ] Alert: Telegram message if any service goes down

### 14.6 — Production Verification Checklist

- [ ] `GET https://api.yourdomain.com/health` → `{"status": "ok"}`
- [ ] Upload a real supplier PDF → enriched products appear in internal catalog within 5 minutes
- [ ] Create order draft → submit → PO HITL draft → approve → PO sent to supplier
- [ ] Log shipment → arrival alert fires → mark arrived → goods received → stock updated
- [ ] Publish 5 products with retail prices → appear on storefront immediately
- [ ] Full checkout (Stripe test mode) → order confirmed → invoice received by consumer email
- [ ] Importer marks fulfilled → HITL notification → consumer receives it
- [ ] HITL Approval Center: create a dunning sequence → HITL draft → approve → message dispatched
- [ ] Admin login → Command Center dashboard loads with real data, all charts rendered
- [ ] Barcode scan in admin → correct product shown with stock + published qty
- [ ] All 15 n8n workflows verified running on production
- [ ] Cross-tenant red-team test manually on production → all 15 attack vectors blocked
- [ ] Enriched-but-unpublished product confirmed absent from consumer storefront search
- [ ] RAGAS eval run against production → all thresholds met
- [ ] Drift detection nightly job verified running

---

## Definition of Done

The capstone is complete when every item below is checked:

- [ ] All 9 CI gates pass: push gates (1-3) + PR gates (4-6) green on every commit; nightly eval (7-9) last run within 24 hours
- [ ] Platform live at HTTPS domain, all services healthy
- [ ] First real tenant provisioned and using the platform
- [ ] Real supplier catalog (20+ products) uploaded, enriched, in internal catalog
- [ ] Order draft created from catalog → PO sent to supplier after HITL approval
- [ ] Shipment tracked → goods received → stock updated
- [ ] 10+ products published to storefront with retail prices
- [ ] Full checkout tested end-to-end (Stripe test mode) with fulfillment HITL notification sent
- [ ] All 4 dunning tracks verified with real invoice scenarios — HITL approval at every stage confirmed
- [ ] Supplier discovery tested: found → scored → HITL outreach approved and sent
- [ ] Supplier-product matching HITL verified: low-confidence match reviewed and confirmed
- [ ] Customer matching HITL verified: returning customer confirmed correctly via review queue
- [ ] Fulfillment notification HITL verified: consumer notified after importer approval
- [ ] All 15 n8n workflows running and verified on production
- [ ] HITL Approval Center: all action types (dunning, PO, outreach, match, fulfillment) tested and working
- [ ] Operations Command Center: all screens visually stunning, all data accurate
- [ ] Storefront: visually stunning, mobile-responsive, chatbot grounded and safe
- [ ] Storefront shows ONLY published products — zero enriched-but-unpublished products visible
- [ ] RAGAS scores meet all thresholds
- [ ] Intent classifier F1 ≥ 0.85
- [ ] Cross-tenant red-team: 0 breaches across all 15 attack vectors
- [ ] All ML models in MLflow production stage with SHA-256 verified
- [ ] LangSmith traces visible for all LLM + agent calls
- [ ] Drift detection running nightly, alert visible in admin panel
- [ ] Production backup running daily, retention verified
- [ ] Uptime monitoring active with Telegram alerts configured

---

*Build in order. Verify each layer before building the next. Fix until correct, then proceed.*
*Every external action requires HITL. No exceptions.*
*Enrichment → internal catalog. Stock received → deliberate publishing → storefront. Always.*
