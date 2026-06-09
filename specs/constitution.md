# Mawrid — Constitution

*The non-negotiables. Every feature spec, every implementation decision, every line of code must be consistent with the rules written here. If a spec contradicts the constitution, the constitution wins.*

*Source of truth: `resources/understanding_brainstorm/approved.md` (DEC-001 through DEC-019)*

---

## 1. What Mawrid Is

Mawrid is a **multi-tenant, AI-powered operations platform** for importers and distributors in the MENA region. It manages the complete operational loop on both sides of the business simultaneously:

- **Supply side**: receive supplier catalogs → enrich into internal catalog → order from suppliers → track shipments → receive goods → publish selectively to storefront
- **Customer side**: take consumer orders → generate invoices → manage all payment collections via the dunning engine

**The governing principle**: The importer makes decisions. The platform executes the work.

---

## 2. Hard Constraints

These are absolute rules. No exception, no workaround, no "just this once."

---

### 2.1 — Multi-Tenant Isolation

Every tenant's data is architecturally unreachable by any other tenant. This is enforced at **three independent layers simultaneously** — all three must be active, always:

| Layer | Mechanism |
|---|---|
| Database | PostgreSQL Row-Level Security on every table that has a `tenant_id` |
| Application | `TenantRepository` base class auto-injects `tenant_id` on every query — no query bypasses this |
| Vector store | pgvector searches always include `AND tenant_id = {current_tenant_id}` |

This same isolation extends to: every MinIO blob path, every Redis key namespace, every log line, every rate-limit bucket.

**CI enforcement**: Cross-tenant red-team test suite (15 attack vectors) runs on every PR to master. Any single vector that succeeds is a hard build failure — not a warning.

**Violation examples that are never acceptable:**
- Reading `tenant_id` from the request body instead of the verified JWT
- A repository method that queries without a `tenant_id` filter
- A vector search that returns embeddings from any tenant other than the authenticated one
- An enriched product from Tenant A appearing in Tenant B's storefront search results

---

### 2.2 — HITL Rule

**Every action that sends a message, places an order, or contacts an external party requires explicit importer approval before execution. No exceptions.**

The flow is always: agent drafts → `hitl_actions` table → importer reviews in HITL Approval Center → importer approves → action executes.

**Actions that are always HITL-gated** (complete list):

| `action_type` | Trigger |
|---|---|
| `purchase_order_send` | Procurement: PO drafted for supplier |
| `dunning_payables_advance` | B2B Payables: 3-day advance reminder |
| `dunning_disputes_on_demand` | B2B Disputes: formal complaint to supplier |
| `dunning_receivables_day7` | B2B Receivables: Day 7 reminder |
| `dunning_receivables_day14` | B2B Receivables: Day 14 escalation |
| `dunning_receivables_day21` | B2B Receivables: Day 21 final notice |
| `dunning_b2c_day3` | B2C Collections: Day 3 gentle reminder |
| `dunning_b2c_day7` | B2C Collections: Day 7 firm reminder |
| `dunning_b2c_day14` | B2C Collections: Day 14 final notice |
| `supplier_outreach` | Supplier discovery: outreach to new candidate |
| `customer_match_review` | Customer matching: confidence below auto-link threshold |
| `supplier_match_review` | Supplier matching: confidence below auto-link threshold |
| `fulfillment_notification` | Consumer order: fulfillment notification |
| `dispute_letter` | Damaged goods: formal supplier complaint |

**What is NOT HITL-gated:** Internal read operations, stock updates, embedding generation, invoice PDF generation, dashboard reads. Anything that does not contact an external party or place an order.

---

### 2.3 — Enrichment ≠ Storefront

An enriched product is **not** a published product. These are two completely separate state machines on the same product record.

```
enrichment_status:  pending → in_progress → enriched | partial | failed
inventory_status:   not_ordered → ordered → in_transit → in_stock
storefront_status:  not_published → published
```

Products appear on the consumer storefront **only** after:
1. Physical goods received (`inventory_status = in_stock`)
2. Importer deliberately selects products to publish
3. Importer sets a retail price (independent of purchase price)
4. Importer sets a storefront quantity
5. Importer clicks "Publish"

**Auto-publish exception**: Retail Only tenants may enable `auto_publish_on_receive` — even then, the system is executing a standing decision the importer made explicitly at onboarding. The HITL Rule is satisfied by that configuration choice.

**Storefront search** (`WHERE storefront_status = 'published'`) and **internal catalog search** (`WHERE enrichment_status = 'enriched'`) are two distinct scopes. The consumer chatbot can never surface a product the importer has not published.

---

### 2.4 — No Hardcoded Secrets

No API key, database password, JWT secret, or any credential is ever hardcoded in source code, committed to git, or present in any file that is not `.gitignore`d.

- All secrets are stored in HashiCorp Vault
- The backend refuses to start if Vault is unreachable
- `.env.example` documents every variable name and purpose — no real values, committed to git
- `.env` (with real values) is `.gitignore`d
- Any accidental secret commit: rotate immediately, do not just delete the commit

---

### 2.5 — Async Everywhere

All I/O is non-blocking. No synchronous call ever runs on the FastAPI event loop.

- Every route handler is `async def`
- Every database query uses SQLAlchemy 2.0 async session
- Every Redis operation is async
- Every external API call (LLM, MinIO, Vault, email) is async
- Background processing (enrichment, outbox relay) runs in separate worker processes — never on the API server's event loop

---

### 2.6 — No Raw Queries Bypassing RLS

All database access goes through the repository layer. The repository base class enforces `tenant_id` filtering on every operation.

- No `session.execute(text("SELECT * FROM products"))` outside a repository
- No Alembic migration that contains business-logic queries
- No admin shortcut that reads across tenants without an explicit, documented exception (platform-level admin monitoring is the only case — handled separately)

---

### 2.7 — Outbox Pattern for Dual Writes

Any operation that writes to the database **and** must publish an event (e.g., enrich product + emit embedding event) uses the outbox pattern:

1. Write to the target table
2. Write the event to the `outbox` table
3. Both writes in a single atomic transaction

The outbox relay reads unprocessed events and dispatches them. If the relay crashes, events survive in Postgres. They are re-processed on restart — idempotently, with no duplicates.

**Never**: DB commit → then queue publish as a separate operation. This is a data-loss path.

---

### 2.8 — Idempotency at Every Consumer

At-least-once delivery is the default for all queues and webhooks. Every consumer must be idempotent — receiving the same message twice must produce the same result as receiving it once.

- ARQ enrichment jobs are keyed on `product_hash` — same job submitted twice = one execution
- Payment webhook deduplication happens inside the same transaction as the fulfillment update
- Outbox relay checks `sent = true` before re-processing
- Re-uploading the same supplier document returns the same `document_id`, queues no new jobs

---

### 2.9 — Clean Architecture Rule

Module dependencies flow in one direction only:

```
api/ → core/ ← infra/
agents/ → core/ ← infra/
```

- `core/` contains domain models and pure business logic. It imports nothing from `infra/`, `agents/`, or `api/`. Zero external library dependencies (except Pydantic and standard library).
- `infra/` contains DB, Redis, MinIO, LLM, and all external clients. It imports from `core/` for domain models only.
- `api/` handles HTTP routing and request/response shaping only. No business logic. Calls core services.
- `agents/` contains LangGraph agents. Uses infra clients and calls core services. Owns no business logic.
- `typing.Protocol` defines the plug shape for any external dependency that needs a test fake.

A `core/` file that imports from `infra/` is a build failure (enforced by import linting).

---

### 2.10 — Security Standards

These algorithms are locked. No ad-hoc choices during implementation.

| Concern | Algorithm / Standard | Notes |
|---|---|---|
| Password hashing | `argon2id` | Memory-hard, current best practice. Via `passlib[argon2]`. Never bcrypt, never MD5, never SHA-256 for passwords. |
| JWT signing | `RS256` (asymmetric) | Private key signs (stored in Vault). Public key verifies. Public JWKS endpoint at `/auth/.well-known/jwks.json` for future federation. |
| `product_hash` | `SHA-256(tenant_id + ":" + product_name + ":" + sku)` | Deterministic. Colon-delimited to prevent collision between `("AB", "CDE")` and `("ABC", "DE")`. |
| File content hash | `SHA-256` | Used for upload idempotency — re-uploading same bytes returns same `document_id`. |
| Webhook signature verification | `HMAC-SHA256` | Stripe: `Stripe-Signature` header. OMT/Whish: verify per their SDK during Phase 11. Reject any webhook that fails verification before processing. |
| CORS | Restrictive by default | Allowed origins: the tenant's configured storefront domain + admin panel domain only. Wildcard `*` is never acceptable. |
| HTTPS / TLS | Enforced in production | TLS termination at reverse proxy (Nginx). Backend never serves plain HTTP in production. HTTP → HTTPS redirect mandatory. |
| JWT expiry | Access token: 15 min · Refresh token: 7 days | Refresh token rotation on every use. Refresh token stored as `httpOnly` cookie. Access token in memory only (not localStorage). |
| Sensitive fields in logs | Never logged | `password`, `token`, `secret`, `card_number`, `cvv` — structlog must redact these fields if they accidentally appear in log context. |

**Vault key paths (structure — actual values never committed):**
- `secret/mawrid/{env}/db` — Postgres credentials
- `secret/mawrid/{env}/redis` — Redis password
- `secret/mawrid/{env}/jwt` — RS256 private key PEM
- `secret/mawrid/{env}/openai` — OpenAI API key
- `secret/mawrid/{env}/stripe` — Stripe secret key + webhook secret
- `secret/mawrid/{env}/minio` — MinIO access key + secret
- `secret/mawrid/{env}/email` — Email provider API key

---

## 3. Architectural Decisions (Locked)

These decisions are made and closed. They are not re-opened without a documented decision record.

| Decision | What It Locks |
|---|---|
| **Modular Monolith** (not microservices) | One FastAPI app, one Docker Compose stack, strict internal module boundaries |
| **Python 3.11** | Pin in `.python-version`, enforced in CI |
| **uv** (not pip, not poetry, not conda) | All deps in `pyproject.toml`. `uv sync` installs. `uv run` executes. `uv.lock` committed. |
| **PostgreSQL + pgvector** | All structured data + vector embeddings in one database |
| **LangGraph + AsyncRedisSaver** | Agent state persisted in Redis. `thread_id = {tenant_id}:{user_id}:{session_uuid}` |
| **paraphrase-multilingual-MiniLM-L12-v2** | Local 384-dim embedding model for EN/AR/FR. Loaded once at startup. |
| **ms-marco-MiniLM-L-6-v2** | Cross-encoder reranker. Top-20 → top-6. Loaded once at startup. |
| **ARQ + Redis** | Async job queue for enrichment pipeline |
| **n8n** | All event-driven automation — 15 core workflows in capstone |
| **MLflow** | ML model registry and experiment tracking, running from Phase 1 |
| **LangSmith** | LLM call tracing, tool use traces, agent step traces, running from Phase 1 |
| **NeMo Guardrails** | Input + output rails on all LLM calls, added Phase 5, inherited by all subsequent phases |
| **Presidio** | PII redaction in EN/AR/FR before every LLM call |
| **Stripe + OMT + Whish** | All three payment gateways. No alternative. |
| **GitHub Actions** | CI/CD. Tiered gates (push / PR / nightly). |

---

## 4. Operational Modes

At onboarding, each tenant selects their business model. The same backend enforces mode rules via a `require_mode(*modes)` FastAPI dependency.

| Mode | Storefront | Active Dunning Tracks | Example |
|---|---|---|---|
| **Hybrid** | Yes | Payables + Receivables + B2C + Disputes | Importer who also runs a retail store |
| **Wholesale Only** | No | Payables + Receivables + Disputes | Pure importer, sells only to other businesses |
| **Retail Only** | Yes | B2C Collections | Store owner who buys from importers |

**Backend is the authority.** Frontend reads `operational_mode` from `/auth/me` and hides irrelevant navigation — but the backend enforces the gate independently. A frontend bypass returns 403.

---

## 5. Technology Constraints

- **mypy --strict** must pass on every commit. No `# type: ignore` without a documented reason in the same line.
- **ruff** lint must pass on every commit.
- **Pydantic v2** for all request/response schemas: `model_config = ConfigDict(extra='forbid')`. Closed enums via `Literal`.
- **SQLAlchemy 2.0 async** — no `Session.execute()`, no blocking ORM patterns.
- **random_state=42** on all ML training operations.
- **structlog** for all logging — every log line carries `request_id`, `tenant_id`, `latency_ms`.
- **langgraph** and **langgraph-checkpoint-redis** pinned to exact minor version (breaking changes observed between minors).
- Pre-commit hooks: ruff + mypy run locally before every `git commit`. CI rejects anything that bypasses them.

---

## 6. CI/CD Gates (Non-Negotiable Thresholds)

| Gate | When | Threshold |
|---|---|---|
| ruff lint | Every push | Zero errors |
| mypy --strict | Every push | Zero errors |
| Unit tests | Every push | All pass, < 3 min total |
| Integration tests | Every PR to master | All pass |
| Cross-tenant red-team | Every PR to master | 15/15 attack vectors blocked — any breach = hard fail |
| Agent trajectory snapshots | Every PR to master | All 20 golden sequences match |
| RAGAS eval | Nightly | All 4 metrics above thresholds in `eval_thresholds.yaml` |
| Intent classifier F1 | Nightly | Macro F1 ≥ 0.85 |
| Drift detection | Nightly | PSI < 0.10 normal · 0.10–0.20 watch · ≥ 0.25 alarm |

Merge to master requires: all PR gates green on current commit **and** latest nightly eval passed within 24 hours.

---

## 7. What Is Out of Scope for the Capstone

These are approved and documented but explicitly deferred:

- WhatsApp Business channel (DEC-011) → Wave 1
- Marketing Studio — AI-generated product images and social posting (DEC-006) → Wave 1
- Fraud detection classifier (DEC-007) → Wave 1
- Customer segmentation (DEC-007) → Wave 1
- AI pricing recommendations (DEC-007) → Wave 1
- Returns & After-Sales agent (DEC-008) → Wave 2
- Customs Document Intelligence (DEC-008) → Wave 2
- Consumer portal login and order history → Wave 3
- Supplier Discovery agent — attempt as stretch after core is stable

Any feature in this list that appears in a Phase 0–14 implementation task is a scope creep violation.

---

*Next: `specs/features/enrichment.md`*
