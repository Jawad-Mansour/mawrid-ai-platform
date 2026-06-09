# Mawrid
## Multi-Tenant AI Operations Platform for Importers & Distributors

**Lebanon · MENA Region · Any product-based import/distribution business**

> This document is the complete specification and source of truth for Mawrid. It covers all approved decisions, the full feature set, the technology stack, and architectural diagrams. Open-ended exploration and brainstorm material live in `brainstorm.md`.

*Version: Capstone Build · Updated: 2026-06-06 · Decisions: DEC-001 through DEC-019*

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Project Description](#project-description)
3. [Platform Architecture Overview](#platform-architecture-overview)
4. [Section 1 — Approved Decisions (DEC-001 → DEC-019)](#section-1--decisions)
5. [Section 2 — Capstone Build (12 Days)](#section-2--capstone-build-12-day-deliverable)
6. [Section 3 — Future Scope](#section-3--future-scope-post-capstone)
7. [Section 4 — Feature Reference Tables](#section-4--feature-reference-tables)
8. [Section 5 — Technology Stack & Engineering Standards](#section-5--technology-stack--engineering-standards)
9. [Section 6 — Architecture Diagrams](#section-6--architecture-diagrams)

---

## Problem Statement

Lebanon's importers and distributors operate at the intersection of two chaotic worlds simultaneously. The businesses vary: an importer who sources goods from overseas suppliers and may or may not run a retail storefront; a regional distributor managing dozens of supplier relationships and selling wholesale to stores; a store owner who buys from local importers and sells retail. Many Lebanese operators are all three at once — sourcing internationally, distributing locally, and running a consumer storefront simultaneously. That combined importer-and-store-owner profile is the primary persona Mawrid is built for. They are competent operators who have survived in a difficult market, but they are drowning in manual processes on both sides of their business every single day.

**Problem 1 — Procurement is broken.** A typical importer receives dozens of supplier catalogs every month: PDFs, Excel sheets, scanned images of handwritten price lists, WhatsApp photos of product tables. Extracting product names, SKUs, prices, and specifications from these documents takes a full working day per catalog — by hand, into another spreadsheet. Mistakes are common. By the time the data is clean, some prices have already changed. The importer has no systematic way to compare suppliers, no record of delivery reliability, and no structured approach to discovering better deals. Supplier relationships are managed entirely through personal contacts and informal trust.

**Problem 2 — Customer operations are fragmented.** After procuring goods, the same person becomes a store owner. They manage orders, generate invoices, track payments, chase overdue accounts, and communicate with customers — all through a patchwork of WhatsApp messages, phone calls, and manually-maintained spreadsheets. A missed payment reminder costs money. A lost invoice creates a dispute. A payment received on the wrong channel goes unrecorded. There is no unified view of who owes what, no automated follow-up, and no early signal that a payment will be late or a customer will churn.

**Problem 3 — There is no intelligence layer.** The importer makes pricing decisions by gut feel, reorder decisions by walking the warehouse, and supplier choices by personal relationship. There is no data on which products move fast, no alert when stock drops below a safe threshold, no market price comparison, and no prediction of which invoice will be paid late. Every decision that could be improved by data is instead made by instinct, accumulated experience, and hope.

**These three problems compound each other.** An importer overwhelmed by catalog processing has no time to analyze pricing. One who spends half the day chasing payments on WhatsApp has no bandwidth to research better suppliers. The result is a business that survives but never scales — operationally trapped by the weight of its own manual processes.

Mawrid is built to break this trap.

---

## Project Description

**Mawrid** (Arabic: مورد — *source, supplier*) is a multi-tenant, AI-powered operations platform that connects both sides of an importer's business into a single unified system. It handles the complete operational loop: receiving a supplier catalog → enriching products into a searchable internal catalog → selecting and ordering from that catalog → tracking incoming shipments → receiving goods and updating stock → selectively publishing products to the storefront → taking customer orders → generating invoices → automatically managing all payment collections — with AI running through every step.

The enriched catalog is the importer's internal working tool — a structured, searchable, AI-augmented view of what suppliers offer. Products do not appear on the public storefront automatically. The importer browses the internal catalog, places orders with suppliers, receives the physical goods, and then deliberately selects which products (and at what retail price and quantity) appear on their customer-facing store. This mirrors exactly how a real import business operates: procure first, then decide what to sell.

The platform is designed to serve any product-based import or distribution business without modification. The first tenant is Jawad's father's home appliance import operation in Lebanon. The same platform, unchanged, can serve a food distributor, a pharmaceutical importer, a clothing wholesaler, or any business that buys from suppliers and sells to customers.

**Multi-Tenant SaaS architecture** means one deployment of Mawrid serves multiple importer businesses simultaneously. Each business's data — products, orders, customers, documents, embeddings, files — is completely isolated from every other business at three independent enforcement layers. Tenants cannot reach each other's data, even if they attempt to.

**The platform's core promise is radical time savings.** A full day of manual catalog processing becomes under five minutes. Dunning letters written by hand become AI-drafted messages approved in one click. Supplier comparisons that required calling three contacts become a ranked comparison table. The importer makes decisions; the platform executes the work.

**Operational Modes** — At onboarding, the tenant selects their business model: Hybrid (imports and runs a retail store), Wholesale Only (sells only to other businesses), or Retail Only (buys wholesale and sells retail). The same Importer user type handles all three — only the enabled modules differ.

**User Progression across three phases:**

| Phase | Who Has an Account | What They Can Do |
|-------|--------------------|-----------------|
| Phase 1 (Capstone) | Importer/Store Owner (admin) | Full platform: catalog, orders, suppliers, dunning, AI, dashboard |
| Phase 1 (Capstone) | End Consumer | Guest: browse storefront, add to cart, checkout, receive invoice by email |
| Phase 2 (Wave 1/2) | Wholesale Store Owner | Buyer account: B2B ordering portal, tracked by B2B Receivables dunning |
| Phase 3 (Wave 3) | Consumer with Account | Login, order history, loyalty, returns portal, WhatsApp channel |

---

## Platform Architecture Overview

Mawrid is a two-sided platform with an AI intelligence layer spanning both sides. Every component is built on one governing principle: **the importer makes decisions, the platform executes the work.**

### The Supply Side (Inbound)

Everything that connects the importer to their suppliers — and by symmetry, the store owner to their importers. The workflow is identical for both user types: only the upstream relationship differs.

**Step 1 — Catalog Ingestion & Enrichment.** A supplier sends a price list in any format — PDF, Excel spreadsheet, scanned image, even a WhatsApp photo. The extraction pipeline processes it immediately: computer vision detects the document layout; a BERT-based named entity recognition model extracts every product row; a bounded ReAct agent enriches each product with descriptions, detailed specifications, and sourced product images by searching external sources (max 5 reasoning steps per product). The enriched products land in a fully searchable, semantically embedded **internal catalog** in under five minutes — replacing a full day of manual data entry. This catalog is the importer's private working tool. No product appears on the public storefront at this stage.

**Step 2 — Order Creation & Procurement.** The importer browses and filters the internal catalog, selects desired products and quantities, and creates an order draft per supplier. The Communication Agent drafts a purchase order in the supplier's language. The importer reviews it in the HITL Approval Center and approves — only then is the PO sent to the supplier by email or WhatsApp. The importer then logs shipment details (carrier, container number, expected arrival date) and tracks the container through its journey.

**Step 3 — Goods Received & Stock Update.** When the container arrives, the importer records actual received quantities for each product. Stock levels are updated atomically. Any discrepancy between ordered and received quantities is flagged and logged against the supplier's performance record.

**Step 4 — Selective Storefront Publishing.** With physical goods in stock, the importer deliberately selects which products to publish on the customer-facing storefront, sets the retail price (independent of the purchase price), and sets the storefront-visible quantity. An importer may reserve stock for wholesale clients and publish only part of the inventory. A store owner in Retail Only mode can optionally auto-publish all received stock. Products appear on the storefront only after this explicit publishing step.

**Supplier Management runs in parallel.** The platform scores suppliers by delivery reliability, price consistency, and catalog completeness; automates reorder draft requests when stock drops below configurable thresholds; and composes multilingual outreach (Arabic, French, English) for supplier discovery. Every AI-generated message is held in a HITL approval queue before it leaves the system. Nothing is sent without the importer's explicit sign-off.

**User Type Symmetry.** An importer's upstream is an overseas supplier. A store owner's upstream is a local importer. Both use the same procurement workflow, the same enrichment pipeline, and the same order/tracking/receiving cycle. The difference is operational mode: the store owner's storefront is their primary sales channel and they publish most or all of their received stock; the importer may run a storefront as a secondary channel and publish selectively.

### The Customer Side (Outbound)

Everything that connects the importer's store to its customers. The enriched catalog powers a configurable e-commerce website: semantic product search with NLP highlighting, detailed product pages with web-sourced descriptions and real product images retrieved by the enrichment pipeline, a shopping cart, and checkout via Stripe, OMT, or Whish (Lebanon's payment networks). A per-product AI chatbot answers questions grounded in the actual catalog data.

On order confirmation, an invoice PDF is generated and dispatched automatically. If payment is not received on schedule, the dunning engine activates. It manages all six money flows across the business simultaneously — supplier payables, wholesale receivables, retail consumer collections, and formal supplier dispute letters — each with its own escalation timeline, communication channel, and ML-selected tone. Payment confirmation stops the sequence immediately and marks the invoice reconciled.

### The AI Layer

The intelligence layer runs across both sides. A three-tier intent classifier (TF-IDF + Logistic Regression → fine-tuned DL ONNX model → GPT-4o zero-shot) routes ~80% of chat messages to fast fixed workflows and ~20% to the Supervisor agent for complex multi-step reasoning. The Supervisor orchestrates five specialist agents: Extraction, Enrichment, Supplier Discovery, Communication, and Stock Monitor — each with defined tool access and bounded execution limits.

Six-technique Advanced RAG (Dense retrieval + Parent-Document chunking, HyDE + Multi-Query expansion, Cross-Encoder re-ranking, GraphRAG via product-category-supplier knowledge graph, MMR diversity filtering, tenant-scoped metadata filter) grounds every AI answer in the actual catalog. NeMo Guardrails apply input and output safety rails on every LLM interaction. Presidio redacts PII before any message reaches the LLM. All write actions pause for HITL approval before execution.

### The Operations Layer

n8n handles all event-driven automation across 21 total workflows (15 active in the capstone, 6 future): tenant provisioning, catalog ingestion, enrichment completion, PO send, shipment alerts, goods received, order confirmation, payment detection, all four dunning tracks, reorder triggers, and more. GitHub Actions runs tiered CI: push gates (lint, type check, unit tests < 3 min); PR gates (integration, cross-tenant red-team, agent snapshots < 15 min); nightly evals (RAGAS, classifier F1, drift detection) — any gate failure blocks the merge. MLflow tracks every ML model version; LangSmith traces every LLM call and tool use. The Full Operations Command Center gives the importer one admin panel with visibility into every dimension of the business.

---
## SECTION 1 — Decisions

---

### [DEC-001] Catalog Enrichment — Approved (v2 definition)
Drop any supplier sheet (PDF, Excel, scanned image) → agentic pipeline detects document structure → extracts every product row → enriches each with descriptions, detailed specifications, and images, keeping original prices intact. Result is an enriched internal catalog — the importer's private working tool. NLP search with highlighting across 150+ products. Full day of manual work → under 5 minutes.

**Product lifecycle states:** `extracted` → `enriched` (internal catalog, not on storefront) → `ordered` → `in_transit` → `in_stock` → `published` (deliberately selected for storefront, with retail price). Each state is tracked independently. Enrichment and storefront publishing are completely decoupled.

---

### [DEC-002] Hard Tenant Isolation — Approved
Full multi-tenant isolation at 3 independent layers:
1. PostgreSQL Row-Level Security on every table
2. Repository base class auto-injects `tenant_id` on every query
3. pgvector tenant-filtered vector search (tenant_id on all embeddings)

Cross-tenant red-team test suite runs on every CI merge and blocks on failure. Applies to: every Postgres row, pgvector embedding, MinIO blob, Redis key, log line, rate-limit bucket.
**Why**: The platform serves any importer/distributor business — not just home appliances. One tenant's data is architecturally unreachable by any other, proven automatically on every push.

---

### [DEC-003] Supplier Intelligence + Full-Loop Reorder — Merged v1 + v2
- Discovers and scores suppliers by reliability, price, delivery time, product type
- Supplier type filter: new-only or new-and-used *(location filter: future enhancement)*
- Multilingual outreach (AR/FR/EN) drafted by Communication agent — all HITL-gated before send
- Reorder loop: stock drops below threshold + demand signal high → draft purchase order queued for importer one-click approval → auto-sent on approval
- Customer identification (from v2): AI identifies potential local wholesale store-owner clients — outreach HITL-gated

---

### [DEC-004] Dunning Engine — 4 Tracks, Covering All 6 Financial Directions

The dunning engine manages all money flows between the importer, their suppliers, their store clients, and their retail consumers. All message drafts require HITL approval before sending. Payment confirmation auto-stops the dunning sequence for that invoice.

**6 directional flows and which track handles them:**

| Direction | Who Owes Whom | Track | System Action |
|-----------|--------------|-------|---------------|
| Supplier → Importer *(supplier invoices importer)* | Importer owes Supplier | **B2B Payables** | Reminds importer to pay supplier before due date (3-day advance) |
| Importer → Supplier *(quality or delivery problem)* | Supplier owes resolution | **B2B Disputes** | Drafts formal complaint letter to supplier in supplier's language |
| Importer → Store *(importer invoiced the store)* | Store owes Importer | **B2B Receivables** | Reminds store to pay invoice (Day 7 → Day 14 → Day 21, segment-aware tone) |
| Store → Importer *(store payment confirmed)* | — | All tracks | Payment confirmation stops the active dunning sequence |
| Store → Consumer *(store invoiced the consumer)* | Consumer owes Store | **B2C Collections** | Reminds consumer to pay (Day 3 gentle + payment link → Day 7 firm → Day 14 final) |
| Consumer → Store *(consumer payment confirmed)* | — | All tracks | Payment confirmation stops the active dunning sequence |

**Track details:**

| Track | Timeline | Channels | Tone |
|-------|----------|----------|------|
| B2B Payables | 3-day advance reminder | Email (WhatsApp: Wave 1) | Professional |
| B2B Disputes | On-demand (filed manually by importer) | Email (WhatsApp: Wave 1) | Formal, in supplier's language |
| B2B Receivables | Day 7 / Day 14 / Day 21 | Email (WhatsApp: Wave 1) | Segment-aware (tone classifier) |
| B2C Collections | Day 3 / Day 7 / Day 14 | Email + SMS | Gentle to firm (tone classifier) |

Tone (gentle / neutral / firm) selected by 3-class ML classifier based on customer segment, payment history, and overdue amount.

**All 4 tracks are active in the capstone.** Dunning does not require the recipient to have a portal account — it only needs their contact information (email, phone, WhatsApp), which is stored in their customer or supplier record. Wholesale clients are tracked as contact records in V1; they get a portal login in Phase 2. This means B2B Receivables and B2B Disputes are fully functional from day one without any additional user type.

---

### [DEC-005] Operational Modes — Replaces "Pure Importer" User Type
At onboarding, tenant selects their business model. Same Importer user type — different enabled modules:

| Mode | Storefront | Active Dunning Tracks | Use Case |
|------|-----------|----------------------|----------|
| **Hybrid** (default) | Yes | Payables + Receivables + B2C + Disputes | Jawad's father: imports AND runs retail store |
| **Wholesale Only** | No | Payables + Receivables + Disputes | Pure importer: sells only to other stores, no consumer website |
| **Retail Only** | Yes | B2C Collections | Store owner: buys from importers, sells retail — storefront is primary channel |

**Upstream symmetry**: An importer's upstream is overseas suppliers. A store owner's upstream is local importers. Both use the same enrichment pipeline, the same procurement workflow (order draft → PO → track → receive), and the same stock management. The key difference is intent:
- **Importer**: storefront optional, selective publishing — may reserve stock for wholesale clients
- **Store owner**: storefront primary, typically publishes most or all received stock — can enable auto-publish on goods received

In **Retail Only** mode the "Supplier" module tracks importers exactly as Hybrid/Wholesale tracks overseas suppliers — same scoring, same HITL outreach, same PO flow. The platform does not care whether the upstream is a supplier in China or a distributor in Beirut.

Consumer note: In **Hybrid** and **Retail Only** modes, end consumers browse the storefront, add to cart, and checkout as guests — no account needed in V1. They receive invoices by email and can be reached by the B2C dunning track using email/phone from the order. Consumer accounts with login are Phase 3.

---

### [DEC-006] Marketing Studio — Approved
Auto-generates professional product marketing images and short-form videos from catalog data with the importer's logo composited in. Multiple variants per product, scheduled posting to Instagram, Facebook, and WhatsApp catalog. Importer approves content before scheduling is automatic.
**Who uses it**: Any tenant with a storefront.
**Phase**: Wave 1 (post-capstone).

---

### [DEC-007] Fraud Detection, Segmentation & Pricing — Approved
- **Fraud Detection**: Real-time XGBoost + SMOTE classifier scores every order before commit. Flagged orders go to fraud review queue.
- **Segmentation**: K-means clusters store clients (wholesale) and consumers into VIP / Regular / At-Risk / Dormant. Dunning tone and communication adapt per segment.
- **AI Pricing**: Flags products priced above MENA market average. Recommends competitive range. Never auto-changes price — always HITL.
**Phase**: Wave 1 (post-capstone).

---

### [DEC-008] After-Sales & Document Intelligence — Approved (clarified)
**This is NOT dunning.** Dunning is about collecting money owed. After-Sales handles post-sale issues and customs paperwork — two separate sub-features:

**Sub-feature A — Returns & After-Sales:**
Customer wants to return a product or file a complaint → agent checks the configured return policy → if approved: generates credit note PDF → if edge case: escalates to importer. Replaces importer manually handling every return email.

**Sub-feature B — Customs Document Intelligence:**
Lebanese importers process heavy customs paperwork (bills of lading, commercial invoices, certificates of origin, customs declarations). This sub-feature: classifies each document type, extracts structured data (quantities, values, HS codes, origin country), cross-references against the product catalog, and runs a RAG compliance check against Lebanese import regulations to flag issues before they cause fines or delays.
**Phase**: Wave 2.

---

### [DEC-009] E-commerce Website + RAG Chatbot — Approved
Enriched catalog powers a configurable product website. Product browser with semantic search, cart, checkout (Stripe + OMT + Whish). AI chatbot widget serving the entire site — grounded, cited answers. Per-product "Ask about this product" button pre-loads that product's context into the chat. Multilingual: English default, Arabic and French optional. Embeddable widget (/widget.js, signed short-lived JWT, server-side origin check).

---

### [DEC-010] Agentic AI System — Approved
Supervisor agent orchestrates 5 specialists:
1. **Extraction** — CV layout detection + BERT NER for supplier documents
2. **Enrichment** — ReAct loop (max 5 steps), fills product data gaps
3. **Supplier Discovery** — finds and scores new suppliers
4. **Communication** — drafts all outgoing messages in the correct language
5. **Stock Monitor** — tracks inventory, triggers reorder signals

3-tier classifier router: TF-IDF → DL ONNX → LLM zero-shot. Simple queries (~80%) → fixed workflow. Complex tasks (~20%) → Supervisor + Specialists.
MCP (Model Context Protocol) connects agents to external tools. Redis-backed LangGraph checkpoints ensure no job progress is lost. HITL gates on all write actions. NeMo Guardrails (input + output rails) + Presidio PII redaction on all LLM interactions.

---

### [DEC-011] WhatsApp Business Channel — Deferred to Wave 1
The v1 "AI Agent on Every Channel" feature (website + WhatsApp + voice) is split: website + chatbot in capstone (DEC-009), WhatsApp Business channel (browse, ask, order by text or voice) deferred to Wave 1 to ship cleanly.

---

### [DEC-012] Full Operations Command Center — Merged v1 + v2
One admin panel managing everything: catalog, suppliers, orders, all 4 dunning tracks, payments, enrichment job queue, marketing studio queue, fraud review queue, segmentation view, pricing flags, returns queue, customs documents, AI model health dashboard, full agent trace logs, n8n automation status.

---

### [DEC-013] CI/CD Eval Pipeline — Approved
Tiered GitHub Actions CI. All thresholds in `eval_thresholds.yaml`. Any regression blocks merge.

**Every push (any branch, < 3 min):** ruff lint · mypy strict · pytest unit tests (LLM mocked)

**Every PR to master (< 15 min):** all push gates + pytest integration tests (real DB + Redis) · cross-tenant red-team (15 attack vectors, must block 100% — any breach is a hard fail, including internal catalog products appearing in consumer storefront search) · agent trajectory snapshot tests (20 known intents)

**Nightly on master:** RAGAS eval (context precision, recall, faithfulness, relevancy) · intent classifier F1 macro ≥ 0.85 · drift detection (PSI, chi-square, embedding centroid)

Merge to master requires all push + PR gates green on current commit AND latest nightly eval passed within 24 hours.

---

### [DEC-014] n8n Automation Workflows — What They Are and Why

**What n8n is**: n8n is a self-hosted workflow automation tool (think Zapier, but you own it). In Mawrid, n8n is the event-driven glue between all services — when something happens anywhere in the platform, n8n catches the event and runs the corresponding automated business process. Every business-critical sequence (new order → invoice → payment tracking → dunning) runs through n8n.

**Why 15 core in capstone and 6 future**: The 15 core workflows (WF-01 through WF-15) cover all active capstone features including the full dunning engine. The 6 future workflows activate when their corresponding Wave 1/2 features are turned on.

**Capstone Core (15):**
1. New Tenant Signup → provision DB schema + MinIO bucket + Redis namespace + send welcome email
2. Supplier Document Uploaded → trigger extraction + enrichment pipeline
3. Enrichment Job Complete → update internal catalog + notify importer (ready to browse and order)
4. Purchase Order Approved (HITL) → send PO to supplier via email/WhatsApp → create shipment tracking record
5. Shipment Arrival Alert (scheduled, daily) → find shipments arriving within configured days → admin panel notification
6. Goods Received Submitted → update stock quantities → check reorder thresholds → flag discrepancies vs ordered qty
7. Consumer Order Confirmed → generate invoice PDF + send to customer + start payment tracking
8. Payment Received → mark invoice paid + stop all active dunning sequences for that invoice
9. Dunning Trigger B2B Payables → Communication agent drafts reminder → HITL → send to importer
10. Dunning Trigger B2C → Communication agent drafts reminder + payment link → HITL → send to consumer
11. Stock Below Threshold → Stock Monitor signals → Communication agent drafts reorder request → HITL → send to supplier
12. B2B Receivables Day 7 → draft reminder to wholesale client (contact record) → HITL → send
13. B2B Receivables Day 14 → escalated reminder → HITL → send
14. B2B Receivables Day 21 → final notice → HITL → send
15. B2B Dispute Filed → Communication agent generates formal complaint letter in supplier's language → HITL → send

**Future (6) — pre-built, activate when feature is ready:**
16. WhatsApp Message Received → route to channel handler *(Wave 1)*
17. Marketing Campaign Triggered → generate images/videos → importer approves → schedule post *(Wave 1)*
18. Fraud Alert Fired → flag order + pause fulfillment + notify importer for manual review *(Wave 1)*
19. Return Request Submitted → After-Sales agent checks policy → approve + credit note PDF, or escalate *(Wave 2)*
20. Supplier Discovery Completed → present scored shortlist to importer for review *(stretch/Wave 1)*
21. Right-to-Erasure Request → purge all tenant data across Postgres + pgvector + MinIO + Redis + logs *(always available)*

---

### [DEC-015] Payment Gateways — Stripe + OMT + Whish
All 3 gateways included. Stripe for international cards, OMT and Whish for Lebanese-specific payment networks. Payment links embedded in B2C dunning reminders and in checkout.

---

### [DEC-016] Per-Tenant Rate Limiting — Included in V1
Each tenant gets its own rate limit bucket keyed by `tenant_id` in Redis. Prevents one tenant from degrading shared infrastructure for others.

---

### [DEC-017] Start With Father's Case — Confirmed Approach
Build the Importer in Hybrid mode (father's use case) first and make it production-quality. His case covers: importing goods from suppliers (catalog enrichment, supplier intelligence), running a retail store (storefront, B2C checkout), and managing money both ways (B2B Payables to suppliers, B2C Collections from customers). Once this works flawlessly, add other user types and operational modes one at a time.

---

### [DEC-018] Capstone Feasibility — Confirmed for 12 Days
The selected 9 features are doable in 12 days given Jawad's background. Key notes:
- Full Dunning Engine: all 4 tracks active in capstone; wholesale clients tracked as contact records (no portal login needed for dunning to work)
- Supplier Discovery agent: V1 stretch goal — attempt after core features are stable
- The 14-day v2 build plan maps cleanly to the 12-day capstone with compressed milestones

---

### [DEC-019] Barcode Live Product Lookup — Capstone Feature
**What it is**: The importer, store owner, or store staff opens the operations dashboard on their phone, taps "Scan Barcode," and points the camera at any product. The system instantly shows: product name, description, category, current stock quantity, and price.

**Use cases it covers**:
- Warehouse floor: check stock level of a product without going to the computer
- Receiving goods: scan incoming items to verify against the purchase order
- Customer query in-store: a customer asks about a product — scan it immediately

**What it does NOT do**: No catalog building via barcode. Supplier sheets handle catalog ingestion — scanning 150 items one by one is impractical. This is purely a lookup tool.

**Implementation**:
- Frontend: `@zxing/browser` library in React — reads EAN-13, UPC-A, Code-128, Code-39, QR codes via phone/tablet camera. Pure browser, no app install required.
- Product data model: `barcode` field added to the product table alongside SKU.
- Backend: `GET /api/v1/catalog/barcode/{code}` — fast DB lookup by barcode or SKU, returns product details + stock quantity. No AI, pure database query, sub-500ms response.
- Mobile-responsive dashboard (PWA-ready): the scanner button is visible and usable on mobile.

**Who uses it**: Importer + Store Owner and store staff.
**Phase**: Capstone.

---

## SECTION 2 — Capstone Build (12-Day Deliverable)

Selected features: the most valuable and completable in 12 days. Every feature is functional and production-quality. This is what gets demonstrated and submitted.

> **Coverage**: Multi-agent LangGraph, full advanced RAG (HyDE/GraphRAG/RAGAS), classical ML + DL with ONNX lean serving, MLOps model registry, NeMo two-layer guardrails, Redis production queue with outbox pattern, and a production-grade multi-tenant architecture. Covers 16 of 17 bootcamp areas in the capstone alone. Every future wave feature builds on the same enriched catalog, isolated infrastructure, and agent framework — each addition is a new capability, never a rebuild.

---

### F1 — Hard Tenant Isolation + Self-Signup

**What it is**: A new importer signs up → the system automatically provisions a fully isolated workspace. No manual setup.

**Components:**
- Self-signup flow: name, email, password, business name, operational mode selection (Hybrid / Wholesale / Retail)
- Auto-provisioning: dedicated PostgreSQL schema + pgvector namespace + MinIO bucket + Redis key prefix + Vault secret path
- 3-layer isolation enforced from first query: RLS + repository filter + vector filter
- JWT authentication with role-based access control (admin role in V1)
- Per-tenant rate limiting (Redis, keyed by tenant_id)
- Cross-tenant red-team CI gate (proves isolation on every push)

**Who uses it**: Every importer who signs up. Jawad as platform operator monitors all tenants.

---

### F2 — Automated Catalog Enrichment → Internal Working Catalog

**What it is**: The importer drops a supplier sheet — the AI pipeline does everything else. The result is an enriched, semantically searchable **internal catalog** — the importer's private working tool. Products in this catalog are not on the public storefront yet.

**Components:**
- Document intake: PDF, Excel, scanned image, SFTP drop
- CV model: detects layout (tables, text areas, columns)
- BERT NER: extracts product name, SKU, price, unit, supplier from each row
- Enrichment agent: ReAct loop (max 5 steps) fills missing descriptions, specs, and images per product
- Outbox pattern: product write + event publish in one atomic transaction
- Redis job queue: enrichment jobs with checkpoints and Dead Letter Queue for failed jobs
- Idempotency: deduplication on product hash (re-uploading same sheet is safe)
- pgvector: every product embedded and indexed for semantic search (internal catalog search)
- NLP search: full-text + semantic search with term highlighting — used by importer to browse, compare, and select products
- Enrichment queue panel: visible in operations dashboard (pending / running / failed / DLQ)

**What happens after enrichment**: The importer browses the enriched catalog, selects products, and creates purchase orders (F2B below). Storefront publishing is a separate, deliberate act done only after goods are physically received.

---

### F2B — Order Management & Procurement

**What it is**: The complete cycle from selecting products in the internal catalog to having physical goods in stock and selectively live on the storefront.

**Components:**
- **Order Draft**: Importer selects products from the enriched catalog, sets quantities per product, groups by supplier automatically — creating one order draft per supplier
- **Purchase Order (HITL)**: Communication Agent drafts the PO in the supplier's registered language (AR/FR/EN); importer reviews and approves in HITL Approval Center; PO sent to supplier via email/WhatsApp only after approval
- **Order Status Tracking**: draft → pending_hitl → sent → confirmed → in_transit → received → cancelled
- **Shipment / Container Tracking**: importer logs carrier, container number, ship date, and expected arrival; timeline view in the admin panel; configurable arrival alert (default: 3 days before) fires a notification
- **Goods Received**: importer records actual received quantities per product; stock updated atomically; discrepancy (received < ordered) logged against supplier performance record; barcode scan used to verify incoming items against the PO
- **Storefront Publishing (deliberate)**: from received stock, importer selects products to publish, sets retail price (independent of purchase price), and sets storefront-visible quantity; unpublished products remain in stock but are invisible to consumers; store owners in Retail Only mode can enable auto-publish for all received goods

**Who uses it**: Every tenant, every mode. The importer's primary workflow. The store owner's equivalent workflow with importers as upstream.

---

### F3 — E-commerce Website + RAG Chatbot

**What it is**: Products deliberately selected from received stock are published to a configurable storefront. An AI chatbot grounded in the published catalog serves every customer question.

**Components:**
- Configurable product storefront: product catalog, search, filters, product detail pages
- Cart and checkout: full flow with Stripe + OMT + Whish
- Invoice PDF: auto-generated on order confirmation, sent by email
- Payment link: unique per invoice, included in B2C dunning reminders
- AI chatbot widget: site-wide, grounded answers from the product catalog with citations
- Per-product "Ask about this product" button: opens chatbot pre-loaded with that product's context
- Advanced RAG (6 techniques): Dense + Parent-Document, HyDE + Multi-Query, Cross-Encoder Re-ranking, GraphRAG (product-category-supplier knowledge graph), MMR diversity, tenant metadata filtering
- RAGAS evaluation: nightly CI gate (context precision, recall, faithfulness, response relevancy — not on every push)
- Multilingual: English default, Arabic and French optional
- Embeddable widget: /widget.js loader, signed short-lived JWT, server-side origin check

---

### F4 — Agentic AI System

**What it is**: The intelligence backbone. A Supervisor agent orchestrates 5 specialists to handle every complex task.

**Agents:**
- **Extraction Specialist**: document parsing — CV layout detection + BERT NER
- **Enrichment Specialist**: ReAct loop, fills product data gaps (bounded, max 5 steps)
- **Supplier Discovery Specialist** *(stretch)*: searches for and scores new suppliers
- **Communication Specialist**: drafts all outgoing messages in the correct language (dunning, outreach, disputes, reorder requests)
- **Stock Monitor Specialist**: tracks inventory levels, signals reorder when threshold crossed
- **Supervisor**: orchestrates specialists for complex multi-step tasks; routes via intent classifier

**Routing:**
- 3-tier intent classifier: TF-IDF → DL ONNX → LLM zero-shot cascade
- Simple/known intent (~80%): fixed workflow (fast, cheap)
- Complex/novel intent (~20%): Supervisor + Specialists

**Infrastructure:**
- MCP (Model Context Protocol): agents connect to external tools via MCP servers
- LangGraph + Redis checkpoints: agent state persists across steps; no progress lost on restart
- HITL gates: all write actions (send email, create order, change price) pause for importer approval
- NeMo Guardrails (2-layer): input rail + output rail; jailbreak detection + content filtering
- Presidio: PII detected and masked in all LLM inputs and outputs

---

### F5 — Full Dunning Engine (All 4 Tracks)

**What it is**: The platform manages all 6 money directions automatically. No invoice slips through.

**All 4 tracks active in the capstone:**

- **B2B Payables**: 3 days before supplier invoice due → Communication agent drafts reminder → importer approves → sent to importer as a payment reminder
- **B2C Collections**: consumer order unpaid → Day 3 gentle reminder + payment link → Day 7 firm → Day 14 final notice → Communication agent drafts each → HITL → sent to consumer by email/SMS
- **B2B Receivables**: wholesale client owes importer → Day 7 → Day 14 → Day 21 → segment-aware tone → HITL → sent to client by email (WhatsApp in Wave 1; client tracked as contact record, no portal login required)
- **B2B Disputes**: importer files complaint against supplier → Communication agent drafts formal letter in supplier's language → HITL → sent to supplier by email (WhatsApp in Wave 1)

**Supporting infrastructure:**
- Dunning tone classifier: 3-class ML model (gentle / neutral / firm) considers customer segment, payment history, overdue amount
- Payment confirmation auto-stop: any payment received immediately stops the dunning sequence for that invoice
- n8n workflows WF-09 through WF-15 cover all 4 dunning tracks in the capstone

---

### F6 — Supplier Intelligence + Full-Loop Reorder

**What it is**: The platform knows which suppliers are worth working with and closes the reorder loop automatically.

**Components:**
- Supplier scoring: multi-criteria ranking (reliability, price, delivery time, product quality)
- Reorder loop: Stock Monitor signals low stock + demand is high → Communication agent drafts purchase order → importer approves → sent to supplier automatically
- Multilingual outreach: Communication agent writes in the supplier's language (AR/FR/EN) — all HITL
- Supplier Discovery *(stretch)*: importer specifies a product need → agent searches and scores potential suppliers → presents ranked shortlist for review
- Wholesale customer identification *(stretch)*: AI identifies potential store-owner clients — outreach HITL-gated

---

### F7 — Full Operations Command Center

**What it is**: One admin panel where the importer manages everything without switching tools.

**Panels:**
- Catalog: all products, enrichment status, edit/approve, search
- Barcode scanner: mobile-ready live scan → product info + stock quantity
- Enrichment queue: pending / running / failed / DLQ jobs
- Suppliers: scores, history, outreach queue, reorder drafts
- Orders: full lifecycle view — pending → confirmed → invoiced → paid → reconciled
- Dunning: active sequences per invoice per track, approve/send pending drafts
- Payments: receivables vs payables, payment link status
- AI health dashboard: classifier accuracy, RAG scores (RAGAS), agent health, drift metrics
- Agent trace logs: full LangGraph step-by-step trace per run
- n8n automation status: workflow run history, failures, retries

---

### F8 — CI/CD + MLOps

**What it is**: Every push is automatically validated. No regression ships. Every model is tracked.

**CI/CD (GitHub Actions on every push):**
- Classifier accuracy gate (intent routing threshold)
- RAG faithfulness gate (RAGAS — all 4 metrics)
- Agent tool-selection accuracy (known scenarios)
- Cross-tenant red-team (must block 100% of cross-tenant data access attempts)
- Smoke tests (happy-path end-to-end)
- All thresholds in `eval_thresholds.yaml` — versioned, auditable

**MLOps:**
- MLflow model registry: semantic versioning + SHA-256 artifact hash for every ML model
- LangSmith: full trace of every LLM call, tool use, and agent step
- Drift detection: PSI (numeric features), chi-square (categorical features), embedding drift
- Structured logging: every log line carries tenant_id, request_id, p50/p95/p99 latency
- Ollama: local LLM fallback for privacy-sensitive operations

---

### F9 — Core Automations (n8n — 15 Workflows)

All event-driven business processes run through n8n. See [DEC-014] for full workflow list. The 15 capstone core workflows (WF-01 through WF-15) cover: tenant provisioning, catalog ingestion, enrichment completion, purchase order send (HITL), shipment arrival alert, goods received + stock update, consumer order confirmation + invoice, payment received + dunning auto-stop, B2B Payables dunning, B2C Collections dunning (Day 3 / 7 / 14), stock threshold reorder trigger, B2B Receivables 3-stage dunning (Day 7 / 14 / 21), and B2B Dispute filing. Every message-sending workflow has a HITL approval node before any external dispatch.

---

## SECTION 3 — Future Scope (Post-Capstone)

Everything below is deliberately excluded from the 12-day capstone. Features are fully designed (see approved.md and brainstorm.md) and can be activated incrementally.

### Wave 1 (First Sprint After Capstone)
- **WhatsApp Business channel** (browse, ask, place orders by text or voice)
- **Fraud Detection** (XGBoost + SMOTE real-time order scoring)
- **Customer Segmentation** (K-means: VIP / Regular / At-Risk / Dormant)
- **AI Pricing Intelligence** (flag products above MENA market average, recommend range)
- **Marketing Studio** (auto-generate images + videos, scheduled social posting)
- **Arabic Supplier NER** (specialized extraction for Arabic-language supplier sheets)
- **n8n future workflows (WF-16 through WF-21)** activated as each Wave 1 feature ships

### Wave 2 (Second Sprint)
- **Wholesale Store Owner accounts** (Phase 2 user type — B2B ordering portal)
- **Cash flow forecasting** (predict cash position from outstanding receivables/payables)
- **Pricing Regression model** (full recommended sell price model)
- **After-Sales / Returns agent** (policy check → credit note PDF)
- **Customs Document Intelligence** (classify, extract, cross-reference, Lebanese compliance RAG)
- **n8n workflows 16–17** activated

### Wave 3
- **Consumer accounts** (Phase 3: login, order history, loyalty program, returns portal)
- **Return Classifier** ML model
- **Full marketing campaign builder** (segment targeting, A/B testing)
- **WhatsApp voice message support**

### Wave 4
- **Platform API** for third-party integrations
- **Cross-tenant anonymized benchmarking**
- **Franchise module** (one importer, multiple store managers)

---

## SECTION 4 — Feature Reference Tables

### 4.1 Full Final Project — All Features (Complete Vision)

| Feature | Category | Phase |
|---------|----------|-------|
| Hard Tenant Isolation (3-layer RLS) | Infrastructure | Capstone |
| Self-Signup + Auto-Provisioning | Infrastructure | Capstone |
| JWT Auth + RBAC | Infrastructure | Capstone |
| Vault Secrets Management | Infrastructure | Capstone |
| Per-Tenant Rate Limiting | Infrastructure | Capstone |
| Operational Mode Config (Hybrid/Wholesale/Retail) | Infrastructure | Capstone |
| Cross-Tenant Red-Team CI Gate | Infrastructure | Capstone |
| Right-to-Erasure (full data purge) | Infrastructure | Wave 1 |
| Supplier Sheet Ingestion (PDF/Excel/image/SFTP) | Catalog | Capstone |
| CV Layout Detection + BERT NER | Catalog | Capstone |
| Catalog Enrichment (ReAct agent + outbox + Redis DLQ) | Catalog | Capstone |
| pgvector Embeddings (internal catalog search) | Catalog | Capstone |
| NLP Product Search with Highlighting (internal) | Catalog | Capstone |
| Barcode Live Product Lookup (mobile camera scan) | Catalog | Capstone |
| Arabic Supplier NER | Catalog | Wave 1 |
| Order Draft Creation from Enriched Catalog | Procurement | Capstone |
| Purchase Order Management (HITL send to supplier) | Procurement | Capstone |
| Shipment / Container Tracking (arrival alerts) | Procurement | Capstone |
| Goods Received & Stock Update (discrepancy flagging) | Procurement | Capstone |
| Storefront Publishing (deliberate selection from stock) | Procurement | Capstone |
| Auto-Publish on Receive (Retail Only mode toggle) | Procurement | Capstone |
| Configurable Product Storefront | E-commerce | Capstone |
| Cart + Checkout (Stripe + OMT + Whish) | E-commerce | Capstone |
| Invoice PDF Generation + Email Dispatch | E-commerce | Capstone |
| Payment Link Generation | E-commerce | Capstone |
| Multilingual Storefront (EN/AR/FR) | E-commerce | Capstone |
| Embeddable Widget | E-commerce | Capstone |
| WhatsApp Business Channel | E-commerce | Wave 1 |
| Consumer Accounts + Loyalty | E-commerce | Wave 3 |
| RAG Chatbot Widget (6 techniques) | AI Chat | Capstone |
| Per-Product "Ask About This" Button | AI Chat | Capstone |
| GraphRAG Knowledge Graph | AI Chat | Capstone |
| RAGAS CI Evaluation Gate | AI Chat | Capstone |
| Extraction Specialist Agent | Agents | Capstone |
| Enrichment Specialist Agent | Agents | Capstone |
| Communication Specialist Agent | Agents | Capstone |
| Stock Monitor Specialist Agent | Agents | Capstone |
| Supervisor Agent | Agents | Capstone |
| Supplier Discovery Agent | Agents | Capstone (stretch) |
| 3-Tier Intent Classifier (TF-IDF/ONNX/LLM) | Agents | Capstone |
| MCP Integration | Agents | Capstone |
| LangGraph + Redis Checkpoints | Agents | Capstone |
| HITL Gates (all write actions) | Agents | Capstone |
| NeMo Guardrails (input + output) | Agents | Capstone |
| Presidio PII Redaction | Agents | Capstone |
| Order Lifecycle Management | Orders | Capstone |
| Supplier Scoring Model | Suppliers | Capstone |
| Reorder Loop (stock → draft PO → HITL → send) | Suppliers | Capstone |
| Multilingual Supplier Outreach | Suppliers | Capstone |
| Wholesale Customer Identification | Suppliers | Capstone (stretch) |
| Location-Based Supplier Filter | Suppliers | Wave 2 |
| B2B Payables Dunning Track | Dunning | Capstone |
| B2C Collections Dunning Track | Dunning | Capstone |
| B2B Receivables Dunning Track | Dunning | Capstone |
| B2B Disputes Track | Dunning | Capstone |
| Dunning Tone Classifier (3-class ML) | Dunning | Capstone |
| Payment Confirmation Auto-Stop | Dunning | Capstone |
| Fraud Detection (XGBoost + SMOTE) | Intelligence | Wave 1 |
| Customer Segmentation (K-means) | Intelligence | Wave 1 |
| AI Pricing Intelligence (market flag) | Intelligence | Wave 1 |
| Pricing Regression Model | Intelligence | Wave 2 |
| Cash Flow Forecasting | Intelligence | Wave 2 |
| Return Classifier ML Model | Intelligence | Wave 3 |
| Marketing Studio (images + videos) | Marketing | Wave 1 |
| Scheduled Social Posting | Marketing | Wave 1 |
| Full Campaign Builder | Marketing | Wave 3 |
| After-Sales / Returns Agent | After-Sales | Wave 2 |
| Customs Document Classification + Extraction | Compliance | Wave 2 |
| Lebanese Import Compliance RAG | Compliance | Wave 2 |
| Wholesale Store Owner Accounts | User Types | Phase 2 / Wave 2 |
| Consumer Accounts with Login | User Types | Phase 3 / Wave 3 |
| Full Operations Command Center | Operations | Capstone |
| n8n Core Workflows (15) | Automation | Capstone |
| n8n Future Workflows (6) | Automation | Wave 1-2 |
| MLflow Model Registry | MLOps | Capstone |
| LangSmith LLM Tracing | MLOps | Capstone |
| GitHub Actions Eval Pipeline | MLOps | Capstone |
| Drift Detection | MLOps | Capstone |
| Structured Logging | MLOps | Capstone |
| Docker Compose + Worker Scaling | Infra | Capstone |

---

### 4.2 Capstone-Version Features

| # | Feature | Key Deliverable |
|---|---------|----------------|
| 1 | Hard Tenant Isolation + Self-Signup | New tenant auto-provisioned, 3-layer isolation proven in CI |
| 2 | Automated Catalog Enrichment | Supplier PDF → enriched internal catalog in <5 min |
| 3 | Order Management & Procurement | Order draft → HITL PO → shipment tracking → goods received → stock update → selective storefront publishing |
| 4 | E-commerce Website + RAG Chatbot | Storefront powered by published stock + AI chatbot with citations |
| 5 | Agentic AI System | Supervisor + 5 specialists + classifier router + HITL + Guardrails |
| 6 | Full Dunning Engine (all 4 tracks) | All 4 tracks active; wholesale clients as contact records, no portal login needed |
| 7 | Supplier Intelligence + Reorder | Supplier scoring + reorder loop; discovery as stretch |
| 8 | Full Operations Command Center | Single panel covering all catalog, procurement, order, dunning, AI, and MLOps views |
| 9 | CI/CD + MLOps | Every push gated; MLflow + LangSmith + RAGAS + drift detection |
| 10 | Core Automations (n8n 15 workflows) | All capstone event flows automated including procurement + full dunning engine |

---

### 4.3 Future Scope Features

| Feature | Wave | Dependency |
|---------|------|-----------|
| Arabic Supplier NER | Wave 1 | Arabic corpus + training data |
| WhatsApp Business Channel | Wave 1 | WhatsApp Business API approval |
| Fraud Detection | Wave 1 | Order volume for training data |
| Customer Segmentation | Wave 1 | Customer history data |
| AI Pricing Intelligence | Wave 1 | Market price data feed |
| Marketing Studio (images + videos) | Wave 1 | Image gen + video gen model integration |
| Scheduled Social Posting | Wave 1 | Instagram/Facebook API setup |
| Wholesale Store Owner Accounts | Wave 2 | Phase 2 user type + B2B ordering portal |
| Cash Flow Forecasting | Wave 2 | Historical payment data |
| Pricing Regression Model | Wave 2 | Sufficient order history |
| After-Sales / Returns Agent | Wave 2 | Return policy corpus per tenant |
| Customs Document Intelligence | Wave 2 | Lebanese customs regulation corpus |
| Lebanese Import Compliance RAG | Wave 2 | Regulation corpus + Arabic legal NLP |
| Consumer Accounts + Loyalty | Wave 3 | Phase 3 user type |
| Return Classifier ML Model | Wave 3 | Labeled return history |
| Full Campaign Builder | Wave 3 | Segment history + A/B tooling |
| WhatsApp Voice Message Support | Wave 3 | ASR model integration |
| Platform API | Wave 4 | Stable core API |
| Cross-Tenant Benchmarking | Wave 4 | Multi-tenant data volume |
| Franchise Module | Wave 4 | Business model validation |

---



---

## SECTION 5 — Technology Stack & Engineering Standards

> Every specific library, tool, pattern, and rule we will use. No ambiguity. If it is not listed here, we do not use it without adding it here first.

---

### 5.1 Language & Runtime

| Decision | Choice | Why |
|----------|--------|-----|
| Language | Python 3.11 | Bootcamp baseline, stable asyncio, compatible with all ML libraries |
| Type system | Full type hints everywhere | mypy-compatible, Pydantic strict mode |
| Project config | `pyproject.toml` | Single config file for ruff, mypy, pytest, project metadata |
| Environment | `.env` in dev, real env vars in prod | Via pydantic-settings |

---

### 5.2 Backend Framework & API Layer

| Decision | Choice | Notes |
|----------|--------|-------|
| Framework | **FastAPI** (async) | Async all the way — no blocking I/O in request path |
| HTTP client | **httpx** (async) | Never use `requests` — it blocks the event loop |
| Request validation | **Pydantic v2** `BaseModel` + `Field` + `field_validator` | At every HTTP boundary |
| Config management | **pydantic-settings** `BaseSettings` with `extra="forbid"` | Single `Settings` class, `.env` in dev. Missing required vars = startup failure |
| Retry logic | **tenacity** — `@retry`, `stop_after_attempt(3)`, `wait_exponential` | On all external calls (LLM, external APIs). Retry transient errors only (network/timeout) |
| Logging | **structlog** — JSON-structured logs | Every line carries `tenant_id`, `request_id`. Never use `print()` |
| Rate limiting | **slowapi** — per-tenant Redis bucket | Keyed by `tenant_id` |
| File uploads | **python-multipart** | For supplier document uploads |
| Async file I/O | **aiofiles** | For reading/writing files without blocking |
| Router pattern | **FastAPI `APIRouter`** per domain | One router per module (catalog, orders, dunning, suppliers, agents, webhooks, auth, admin) |
| Dependency injection | **FastAPI `Depends()`** for everything | DB session, LLM client, current user, ML models — no globals |
| Singleton loading | **`@asynccontextmanager` lifespan** on the FastAPI app | ML models, embedding model, LLM client, DB engine, Redis client load once at startup |
| Webhook handling | **Standard FastAPI routes** under `/api/v1/webhooks/` | Inbound: Stripe payment confirmation, OMT/Whish callbacks, n8n trigger callbacks. Signature verification on all inbound webhooks |
| CORS | **FastAPI CORSMiddleware** | Tenant-specific origins allowed |
| Caching | **`functools.lru_cache`** for deterministic helpers (Settings, config) | **`cachetools.TTLCache`** for external API responses (market prices, exchange rates). Document TTL choice in code |
| Error isolation in agents | **`ToolError` Pydantic model** returned from tools on failure | Never crash the agent loop. LLM reasons about the error and continues |

---

### 5.3 Database & Storage

| Component | Choice | Detail |
|-----------|--------|--------|
| Primary DB | **PostgreSQL 16** | With Row-Level Security on every table |
| Async driver | **asyncpg** | For SQLAlchemy async engine |
| Sync driver | **psycopg2** | For Alembic migrations only (sync) |
| ORM | **SQLAlchemy 2.0** (async, `DeclarativeBase`) | Async sessions via `AsyncSession` |
| Migrations | **Alembic** | Schema migrations versioned in repo |
| Vector store | **pgvector 0.7** | Already in Postgres — no separate vector DB needed |
| Vector index | **HNSW** (NOT IVFFlat) | Better query-time accuracy and speed, no upfront tuning needed |
| Cache / Queue / Sessions | **Redis 7** with `redis[hiredis]` async client | Used for: enrichment job queue, LangGraph checkpoints, session storage, rate-limit buckets, TTL caches |
| Object storage | **MinIO** with `minio` Python SDK | S3-compatible. Tenant-scoped paths. Supplier docs, product images, invoice PDFs |
| Secrets | **HashiCorp Vault** | All API keys, DB passwords, JWT secrets. Never in `.env` in production |
| Enrichment queue | **ARQ (Async Redis Queue)** | Python-native async task queue on top of Redis. Handles enrichment jobs with retries, DLQ, and idempotency on `product_hash` |

---

### 5.4 AI / ML Libraries

**LLM & Agents:**

| Library | Version | Use |
|---------|---------|-----|
| `langchain` + `langchain-openai` + `langchain-community` | latest stable | Tool definitions, chains, retrieval |
| `langgraph` | 0.2.x | Supervisor + specialist agent orchestration, state machines, checkpointing |
| `openai` | latest | GPT-4o as primary LLM |
| `anthropic` | latest | Claude Sonnet as secondary/fallback LLM |
| `ollama` + `ollama-python` | latest | Local LLM for privacy-sensitive ops |
| `nemo-guardrails` | latest | 2-layer safety rails (input + output) |
| `presidio-analyzer` + `presidio-anonymizer` | latest | PII detection and redaction |

**Embeddings & RAG:**

| Library | Choice | Why |
|---------|--------|-----|
| Embedding model | `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers) | Local, free, multilingual EN/AR/FR. 384 dimensions. Good for product catalog data |
| Alt embedding | `text-embedding-3-small` (OpenAI API) | Higher quality, use for production upgrade |
| Cross-encoder (reranking) | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Local, fast (~50ms), no API cost |
| `sentence-transformers` | latest | Embedding model serving |
| `ragas` | latest | RAG evaluation: faithfulness, context precision/recall, answer relevance |

**Document Processing:**

| Library | Use |
|---------|-----|
| `pdfplumber` | PDF text and table extraction (better than pypdf2 for tables) |
| `openpyxl` | Excel .xlsx parsing |
| `xlrd` | Excel .xls (older format) |
| `Pillow` | Image processing for product photos |
| `pytesseract` + Tesseract OCR | Scanned image/PDF text extraction |
| GPT-4o vision | CV layout detection and extraction for complex documents (V1 approach — fine-tune a local model in Wave 1) |

**Classical ML:**

| Library | Use |
|---------|-----|
| `scikit-learn` | Intent classifier (TF-IDF + LR), tone classifier, supplier scorer, pipeline |
| `xgboost` | Fraud classifier (Wave 1) |
| `imbalanced-learn` (SMOTE) | Class imbalance handling for fraud model |
| `onnx` + `onnxruntime` | Export trained models to ONNX for lean CPU inference |
| `transformers` (HuggingFace) | BERT-based models (NER, intent classifier DL tier) |
| `torch` | Required by transformers for training only |
| `mlflow` | Model registry, experiment tracking, SHA-256 artifact hashes |
| `langsmith` | LLM call tracing and evaluation |

**Knowledge Graph (GraphRAG):**

| Library | Use |
|---------|-----|
| `networkx` | Build and query product-category-supplier knowledge graph |
| PostgreSQL (existing) | Persist graph edges as relationship tables |

---

### 5.5 Agent & RAG Implementation Details

**RAG pipeline — 6 techniques in implementation order** (matches Advanced RAG Guide recommended sequencing):

1. **Dense Retrieval + Parent-Child chunking**: Child chunks (256 tokens) for embedding/similarity search; parent chunks (1024 tokens) returned to LLM. HNSW index on pgvector. Scope filter: `WHERE tenant_id = :current AND enrichment_status = 'enriched'` (admin) or `storefront_status = 'published'` (consumer).
2. **Query Expansion — HyDE + Multi-Query**: LLM generates a hypothetical product description (HyDE) → embedded → searched. Also generates 3 query variants → 4 parallel searches merged via RRF (closes vocabulary gap between user phrasing and catalog language).
3. **Cross-Encoder Re-Ranking**: Top-20 from dense search → `cross-encoder/ms-marco-MiniLM-L-6-v2` → reranked → top-6 returned (local, < 150ms, no API cost).
4. **GraphRAG**: Knowledge graph (networkx + `graph_edges` table): product → category, product → supplier. Graph traversal surfaces structurally related products not reachable by vector distance alone. Results merged with vector results via RRF.
5. **MMR (Maximal Marginal Relevance)**: λ=0.5 — prevents near-identical chunks in the LLM context window; ensures top-6 are diverse.
6. **Tenant-scoped metadata filtering**: Applied at every retrieval step — no cross-tenant results are physically possible at the DB/vector layer.

*Note: Contextual Retrieval (LLM-generated chunk prefix at indexing time) was evaluated but excluded — it requires an LLM call per chunk at index time, which is expensive for a 150+ product catalog that re-indexes on every enrichment. GraphRAG provides the structural context without indexing-time LLM cost.*

**Agent architecture:**
- LangGraph `StateGraph` with Redis checkpointer (`RedisSaver`) for persistent state
- Each specialist is a LangGraph node; Supervisor routes between them via conditional edges
- Max steps per agent run: 5 (hard cap, prevents infinite loops)
- HITL: agent pauses at `interrupt()` node for write actions; resumes on approval via `/agents/resume/{thread_id}`
- MCP: agents connect to external tools via MCP servers (defined in `tools/` module)

---

### 5.6 Automation Layer — n8n Decision (Final)

**Alternatives evaluated:**

| Option | Verdict |
|--------|---------|
| **Celery + Beat** | Good for background tasks but no visual UI, no built-in external integrations, complex HITL state management |
| **Temporal** | Excellent for durable workflows but steep learning curve, wrong for 12-day build |
| **Prefect** | Better for ML batch pipelines, not event-driven business orchestration |
| **APScheduler + custom webhooks** | Requires building every external integration (email, SMS, WhatsApp, payment callbacks) from scratch — weeks of work |
| **n8n** ✅ | 400+ pre-built integrations (email, SMS, Stripe, WhatsApp), visual workflow builder, self-hosted, HITL approval nodes, webhook + schedule triggers |

**Decision: n8n stays.**

**Architecture — clear separation of responsibility:**
- **n8n handles**: event routing, scheduling, external integrations (email provider, SMS via Twilio, payment webhooks from Stripe/OMT/Whish), HITL approval routing, multi-service orchestration
- **Python / ARQ handles**: all ML processing, model inference, business logic, enrichment workers
- **How they connect**: n8n calls FastAPI webhook endpoints (`POST /api/v1/webhooks/n8n/{event}`) for anything requiring Python ML or business logic. FastAPI fires n8n webhook URLs for triggering workflows from code.

**n8n deployment**: Docker Compose service with persistent volume. Workflow JSONs version-controlled in `n8n/workflows/`.

---

### 5.7 Frontend Stack

| Technology | Choice | Use |
|-----------|--------|-----|
| Framework | **React 18 + TypeScript** | Type-safe UI |
| Bundler | **Vite** | Fast dev server and build |
| UI components | **shadcn/ui + Tailwind CSS** | Accessible, composable, no styling conflicts |
| Data fetching | **TanStack Query v5** (React Query) | Server state, caching, background refetch, optimistic updates |
| Routing | **React Router v6** | SPA routing with nested layouts |
| Global state | **Zustand** | Lightweight, no boilerplate |
| Barcode scanning | **@zxing/browser** | Browser-native camera barcode scanner. Reads EAN-13, UPC, Code-128, QR. No app install. |
| Charts | **recharts** | Model health dashboard, sales/revenue charts |
| Notifications | **sonner** | Toast notifications for HITL approvals, job completions |
| HTTP | **axios** with interceptors | Auth headers, error handling centralized |
| PDF preview | **react-pdf** | Invoice PDF preview in browser |
| Design principle | **Mobile-responsive (PWA-ready)** | Barcode scanner requires phone camera — dashboard must work on mobile |

---

### 5.8 Auth & Security

| Component | Choice | Detail |
|-----------|--------|--------|
| User management | **fastapi-users** | Registration, login, password reset, email verification |
| JWT library | **PyJWT** | Token generation and validation |
| JWT algorithm | **RS256** (asymmetric) | Private key signs (stored in Vault). Public key verifies. JWKS endpoint at `GET /auth/.well-known/jwks.json` |
| Access token expiry | **15 minutes** | Kept in memory only — never in localStorage |
| Refresh token expiry | **7 days, rotating** | Stored as `httpOnly` cookie. Rotated on every use |
| Password hashing | **argon2id** via `passlib[argon2]` | Memory-hard, current best practice. Never bcrypt, never plain SHA-256 for passwords |
| Content / identity hashing | **SHA-256** | `product_hash = SHA-256(tenant_id + ":" + product_name + ":" + sku)`. File upload idempotency hash. Colon-delimited to prevent collisions |
| Secrets | **HashiCorp Vault** | All API keys, DB passwords, RS256 private key, Stripe webhook secret. Vault paths: `secret/mawrid/{env}/{service}` |
| Rate limiting | **slowapi** | Per-tenant Redis bucket, configurable limits |
| Webhook security | **HMAC-SHA256 signature verification** | Stripe: `Stripe-Signature` header. OMT/Whish: per SDK. Reject any webhook failing verification before processing |
| CORS | **FastAPI CORSMiddleware** | Tenant-registered storefront domain only — wildcard `*` never acceptable |
| HTTPS | **TLS at reverse proxy (Nginx)** | HTTP → HTTPS redirect mandatory in production. Backend never serves plain HTTP in production |
| Redis key namespace | `mawrid:{tenant_id}:{resource}:{id}` | Prevents cross-tenant key collision at the key level |
| Widget auth | **RS256-signed JWT** (15-min expiry) | For embeddable storefront widget. Importer issues for their domain |
| Server-side origin check | Custom middleware | Widget requests validated server-side, not just CORS |
| Sensitive log fields | **Never logged** | `password`, `token`, `secret`, `card_number` — structlog redacts if accidentally included in context |

---

### 5.9 Communication & Document Generation

| Need | Tool | Notes |
|------|------|-------|
| Transactional email | **SMTP via n8n email node** (aiosmtplib as fallback) | Invoices, dunning reminders, welcome email |
| SMS (B2C dunning) | **Twilio SMS** via n8n Twilio node | Phone number from order record |
| Invoice PDF | **reportlab** (Python) + **Jinja2** templates | Generated on order confirmation |
| WhatsApp | **Twilio WhatsApp API** via n8n | Wave 1 |
| Credit note PDF | **reportlab** + Jinja2 | Wave 2 (returns) |

---

### 5.10 Code Quality & Testing

**Linting & Formatting:**
```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "F", "I", "B", "UP", "ASYNC", "S"]

[tool.mypy]
strict = true
```

**Pre-commit hooks**: ruff (lint + format) + mypy run on every commit.

**Testing stack:**

| Tool | Use |
|------|-----|
| `pytest` + `pytest-asyncio` | All tests, async support |
| `httpx.AsyncClient` | API endpoint testing (FastAPI test client) |
| `pytest-mock` + `monkeypatch` | Mock LLM calls, external APIs, Redis |
| `factory-boy` | Test data factories for DB models |

**What we test (from Engineering Standards Guide):**
1. Pydantic schemas — valid AND invalid inputs for every model
2. Tool logic — mocked external calls, test happy path + failure modes (`ToolError` returned correctly)
3. One full E2E agent run — all external calls mocked, assert correct tools called and response well-formed
4. Cross-tenant isolation — attempt to read tenant B's data as tenant A, assert blocked

**CI (GitHub Actions) — tiered (see DEC-013 for full spec):**

*Every push (< 3 min):*
- `ruff check .` (linting)
- `mypy --strict .` (type checking)
- `pytest tests/unit/ -q` (unit tests, LLM mocked)

*Every PR to master (< 15 min):*
- All push gates +
- `pytest tests/integration/` (real DB + Redis, no LLM)
- Cross-tenant red-team (15 vectors — ANY pass = hard fail)
- Agent trajectory snapshot tests (20 known intents)

*Nightly on master (expensive — real LLM):*
- RAGAS eval gate (RAG faithfulness vs `eval_thresholds.yaml`) ← **nightly only, NOT on push**
- Intent classifier F1 gate (≥ 0.85)
- Drift detection run

---

### 5.11 Engineering Standards — Binding Rules

These rules are non-negotiable. Every PR is reviewed against them.

1. **Async all the way**: `httpx` (not `requests`), `asyncio.sleep` (not `time.sleep`), `asyncio.to_thread()` for CPU-bound ML inference in request path. Every route and tool is `async def`.

2. **Dependency injection via `Depends()`**: DB session, LLM client, current user, ML models, Redis client — all injected. Zero globals outside `app.state` singletons.

3. **Singletons via lifespan only**: ML models, embedding model, DB engine, Redis client, LLM client load once in `@asynccontextmanager lifespan`. Never at import time.

4. **Config through `Settings` only**: Zero `os.getenv()` calls outside the `Settings` class. `extra="forbid"` catches typos at startup.

5. **Pydantic at every external boundary**: HTTP request bodies, agent tool inputs, LLM structured outputs, webhook payloads — all Pydantic models with `Field(...)` constraints.

6. **Retries and timeouts on every external call**: `tenacity` with `stop_after_attempt(3)`, `wait_exponential`, retry only on transient exceptions. All `httpx` calls have explicit `timeout=`.

7. **ToolError for agent failures**: Tools return `ToolError` model on failure — never raise exceptions that crash the agent loop. Let the LLM reason about failures.

8. **Structured JSON logging with `structlog`**: Zero `print()` calls. Every log line has `tenant_id` and `request_id`. Exception tracebacks via `log.exception()`.

9. **Tests in CI**: No PR merges without all tests passing. Pydantic schemas, tool logic, and one E2E agent path always covered.

10. **No bare `except`**: Catch specific exception types. No swallowed errors.

---

## SECTION 6 — Architecture Diagrams

Visual representations of every major system, flow, and interaction in the Mawrid platform. Each diagram is accompanied by a written explanation of the key relationships and decisions it represents.

---

### 6.1 Platform High-Level Architecture

```
                            MAWRID PLATFORM
                   Multi-Tenant AI Operations (SaaS)
    ┌────────────────────────────────────────────────────────────┐
    │                                                            │
    │   SUPPLY SIDE (Inbound)         CUSTOMER SIDE (Outbound)  │
    │  ┌─────────────────────┐       ┌─────────────────────┐    │
    │  │  Supplier Documents  │       │  Product Storefront  │    │
    │  │  PDF / Excel / Image │       │  Semantic Search     │    │
    │  │  WhatsApp photo      │       │  Cart + Checkout     │    │
    │  └──────────┬──────────┘       │  Invoice Dispatch     │    │
    │             │                  └──────────┬──────────┘    │
    │             ▼                             │                │
    │  ┌─────────────────────┐                 │                │
    │  │  Extraction Pipeline │                 │                │
    │  │  CV → NER → ReAct   │                 │                │
    │  │  < 5 min per catalog │                 │                │
    │  └──────────┬──────────┘                 │                │
    │             │                             │                │
    │             ▼                             ▼                │
    │  ┌──────────────────────────────────────────────────────┐  │
    │  │              PRODUCT CATALOG                         │  │
    │  │    PostgreSQL 16 + pgvector (HNSW) — Tenant-Isolated │  │
    │  └──────────────────────┬───────────────────────────────┘  │
    │                         │                                   │
    │  ┌──────────────────────▼───────────────────────────────┐  │
    │  │                   AI LAYER                           │  │
    │  │  3-Tier Intent Classifier → Supervisor + 5 Agents   │  │
    │  │  6-Technique Advanced RAG (pgvector + GraphRAG)      │  │
    │  │  NeMo Guardrails (input + output) + Presidio PII     │  │
    │  │  HITL Gate on every write action                     │  │
    │  └──────────────────────┬───────────────────────────────┘  │
    │                         │                                   │
    │  ┌──────────────────────▼───────────────────────────────┐  │
    │  │              OPERATIONS LAYER                        │  │
    │  │  n8n (15 capstone / 21 total) · Command Center       │  │
    │  │  GitHub Actions CI/CD · MLflow · LangSmith Tracing   │  │
    │  │  Dunning Engine (4 Tracks, 6 Directions)             │  │
    │  └──────────────────────────────────────────────────────┘  │
    └────────────────────────────────────────────────────────────┘
```

The platform operates as two connected sides sharing a single enriched product catalog as their source of truth. The supply side feeds the catalog; the customer side consumes it. The AI layer runs across both, and the operations layer orchestrates everything via event-driven workflows. Every component is multi-tenant: a single deployment serves multiple importer businesses simultaneously, with each business's data completely isolated at three enforcement layers.

---

### 6.2 Multi-Tenant Isolation (3 Layers)

```
    TENANT A Request                    TENANT B Request
    ┌───────────────────┐              ┌───────────────────┐
    │  JWT: tenant_id=A │              │  JWT: tenant_id=B │
    └─────────┬─────────┘              └─────────┬─────────┘
              │                                   │
    ┌─────────▼───────────────────────────────────▼─────────┐
    │         LAYER 1: Repository Base Class                 │
    │                                                        │
    │  Every query auto-injects WHERE tenant_id = :current  │
    │  No repository method can return cross-tenant rows     │
    │  Enforced in Python before any SQL executes            │
    └─────────────────────────┬──────────────────────────────┘
                              │
    ┌─────────────────────────▼──────────────────────────────┐
    │         LAYER 2: PostgreSQL Row-Level Security         │
    │                                                        │
    │  RLS policy on every table enforces tenant_id filter  │
    │  at the database engine level                          │
    │  A raw SQL injection cannot cross tenants              │
    │  Even a DB admin query respects RLS per session        │
    └─────────────────────────┬──────────────────────────────┘
                              │
    ┌─────────────────────────▼──────────────────────────────┐
    │         LAYER 3: pgvector Tenant-Filtered Search       │
    │                                                        │
    │  All embeddings stored with tenant_id metadata tag     │
    │  Every vector similarity search filtered by tenant_id  │
    │  A semantic query never surfaces another tenant's docs │
    └────────────┬──────────────────────────────┬────────────┘
                 │                              │
     ┌───────────▼──────────┐      ┌───────────▼──────────┐
     │    TENANT A DATA      │      │    TENANT B DATA      │
     │  ┌──────────────────┐│      │  ┌──────────────────┐│
     │  │  DB rows (RLS)   ││      │  │  DB rows (RLS)   ││
     │  │  Vectors (tagged)││      │  │  Vectors (tagged)││
     │  │  MinIO /tenant-A/││      │  │  MinIO /tenant-B/││
     │  │  Redis ns:A:*    ││      │  │  Redis ns:B:*    ││
     │  └──────────────────┘│      │  └──────────────────┘│
     └──────────────────────┘      └──────────────────────┘

    CI RED-TEAM: automated test on every push tries to
    access Tenant B data as Tenant A → must fail 100%
```

Three independent enforcement layers mean no single point of failure for data isolation. A bug at the application layer (Layer 1) is caught by the database (Layer 2). A misconfigured query is blocked by RLS regardless. The vector search layer (Layer 3) ensures that even semantic queries — which can surface unexpected matches — are bounded to the requesting tenant's data. The automated red-team test in CI ensures this holds after every code change.

---

### 6.3 User Types & Phase Progression

```
    ══════════════════════════════════════════════════════════
    PHASE 1 — CAPSTONE BUILD
    ══════════════════════════════════════════════════════════

    ┌──────────────────────────────────────────────────────┐
    │  IMPORTER / STORE OWNER  (authenticated admin)       │
    │                                                      │
    │  Full platform access:                               │
    │  ✓ Catalog enrichment & management                   │
    │  ✓ Supplier scoring, discovery, reorder              │
    │  ✓ Orders, invoices, payment tracking                │
    │  ✓ All 4 dunning tracks (payables/receivables/       │
    │    disputes/B2C collections)                         │
    │  ✓ AI assistant + HITL approval queue                │
    │  ✓ Full Operations Command Center                    │
    │  ✓ Barcode live lookup (scan → instant product info) │
    └──────────────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────────────┐
    │  END CONSUMER  (guest — no account required)         │
    │                                                      │
    │  ✓ Browse public storefront (semantic search)        │
    │  ✓ Add to cart, checkout (Stripe / OMT / Whish)      │
    │  ✓ Receive invoice by email                          │
    │  ✓ Reached by B2C dunning if payment overdue         │
    │  ✗ No login, no order history, no account            │
    └──────────────────────────────────────────────────────┘

    ══════════════════════════════════════════════════════════
    PHASE 2 — WAVE 1 / 2 (POST-CAPSTONE)
    ══════════════════════════════════════════════════════════

    ┌──────────────────────────────────────────────────────┐
    │  WHOLESALE STORE OWNER  (buyer account)              │
    │                                                      │
    │  ✓ B2B ordering portal (bulk orders, trade pricing)  │
    │  ✓ Invoice history, payment tracking                 │
    │  ✓ Subject to B2B Receivables dunning track          │
    │  Note: tracked as contact record in Phase 1 —        │
    │  dunning works without portal login                  │
    └──────────────────────────────────────────────────────┘

    ══════════════════════════════════════════════════════════
    PHASE 3 — WAVE 3 (FUTURE)
    ══════════════════════════════════════════════════════════

    ┌──────────────────────────────────────────────────────┐
    │  CONSUMER WITH ACCOUNT  (retail customer)            │
    │                                                      │
    │  ✓ Login, order history, loyalty program             │
    │  ✓ Returns portal (AI-assisted returns/complaints)   │
    │  ✓ WhatsApp channel integration                      │
    │  ✓ Consumer segmentation (VIP / Regular / At-Risk)   │
    └──────────────────────────────────────────────────────┘
```

The user model is deliberately phased. Phase 1 focuses on the importer's own operations — the biggest pain point — without building user account systems for buyers or consumers (which adds complexity without capstone value). Phase 2 adds buyer portals once the core operational loops are proven. Phase 3 adds consumer loyalty once B2B is stable. Each phase builds on the same catalog, the same infrastructure, and the same agent framework — no rebuilds.

---

### 6.4 Operational Modes

```
    ┌──────────────────┬──────────────────┬──────────────────┐
    │   HYBRID MODE    │ WHOLESALE ONLY   │  RETAIL ONLY     │
    │   (Default)      │ (Pure Importer)  │ (Store Owner)    │
    ├──────────────────┼──────────────────┼──────────────────┤
    │ Example: Jawad's │ Sells only to    │ Buys wholesale,  │
    │ father — imports │ other businesses │ sells to retail  │
    │ AND runs a store │ no public store  │ consumers only   │
    ├──────────────────┼──────────────────┼──────────────────┤
    │ Storefront:  YES │ Storefront:  NO  │ Storefront:  YES │
    │ Catalog:     YES │ Catalog:     YES │ Catalog:     YES │
    │ B2B Payables:YES │ B2B Payables:YES │ B2B Payables:YES │
    │ B2B Receiv.: YES │ B2B Receiv.: YES │ B2B Receiv.: YES │
    │ B2C Collect.:YES │ B2C Collect.: NO │ B2C Collect.:YES │
    │ B2B Disputes:YES │ B2B Disputes:YES │ B2B Disputes: NO │
    │ AI Assistant:YES │ AI Assistant:YES │ AI Assistant:YES │
    └──────────────────┴──────────────────┴──────────────────┘

    Selected at tenant onboarding. Same Importer user type.
    Modules enabled/disabled per mode — no separate codebase.
```

Operational modes replace the concept of separate user types for different business models. Instead of "importer" vs "store owner" as distinct accounts, the same account holder selects their mode at setup. This avoids building three separate permission systems and keeps the data model uniform. The mode can be changed by the importer at any time through the admin settings.

---

### 6.5 Catalog Enrichment Pipeline

```
    SUPPLIER SUBMITS DOCUMENT
    ┌──────────────────────────────────────────┐
    │  Any format:                             │
    │  PDF · Excel · Scanned Image · Photo     │
    └────────────────────┬─────────────────────┘
                         │
                         ▼
    ┌──────────────────────────────────────────┐
    │  EXTRACTION AGENT                        │
    │                                          │
    │  1. CV Layout Detection                  │
    │     GPT-4o vision identifies:            │
    │     tables, columns, headers, rows       │
    │                                          │
    │  2. BERT NER Extraction                  │
    │     Per row, extracts:                   │
    │     · Product name      · SKU / Barcode  │
    │     · Price (preserved) · Unit / Qty     │
    │     · Supplier ref      · Specifications │
    └────────────────────┬─────────────────────┘
                         │  one job per product
                         ▼
    ┌──────────────────────────────────────────┐
    │  REDIS JOB QUEUE (ARQ)                   │
    │                                          │
    │  · Idempotent on product_hash            │
    │    (duplicate upload = no duplicate job) │
    │  · Dead Letter Queue for failed jobs     │
    │  · Async Python workers (ARQ)            │
    └────────────────────┬─────────────────────┘
                         │
                         ▼
    ┌──────────────────────────────────────────┐
    │  ENRICHMENT AGENT  (Bounded ReAct Loop)  │
    │                                          │
    │  Max 5 reasoning steps per product:      │
    │                                          │
    │  [Thought]  "Need full description"      │
    │  [Action]   web_search(product_name)     │
    │  [Observe]  Found specs on manufacturer  │
    │  [Thought]  "Need product image"         │
    │  [Action]   image_search(product_name)   │
    │  [Observe]  Image URL found → download   │
    │  → STOP (steps exhausted or complete)    │
    └────────────────────┬─────────────────────┘
                         │  atomic commit
                         ▼
    ┌──────────────────────────────────────────┐
    │  OUTBOX PATTERN (Atomic Dual Write)      │
    │                                          │
    │  Single DB transaction:                  │
    │  · Write enriched product to catalog     │
    │  · Write enrichment event to outbox tbl  │
    │  → Relay picks up event, publishes it    │
    │  → pgvector embedding generated & stored │
    └────────────────────┬─────────────────────┘
                         │
                         ▼
    ┌──────────────────────────────────────────┐
    │  ENRICHED PRODUCT CATALOG                │
    │                                          │
    │  · Full description + specifications     │
    │  · Product image (MinIO)                 │
    │  · Semantic embedding (pgvector HNSW)    │
    │  · Original price preserved              │
    │  · Tenant-isolated                       │
    │  · NLP-searchable with highlighting      │
    └──────────────────────────────────────────┘

    Throughput: 150+ products in < 5 minutes
    Manual equivalent: 1 full working day
```

The outbox pattern is critical here: it ensures that both the product write and the embedding event are committed atomically, eliminating the dual-write problem. Without this, a server crash between writing the product and writing the event would leave the catalog and the vector index out of sync. The idempotency key (product_hash) means re-uploading the same catalog does not create duplicate jobs.

---

### 6.6 Advanced RAG Pipeline (6 Techniques)

```
    USER QUERY
    "Do you have a 65-inch Samsung TV under $800?"
         │
         ▼
    ┌────────────────────────────────────────────────┐
    │  TECHNIQUE 5: QUERY EXPANSION                  │
    │                                                │
    │  HyDE: LLM generates a hypothetical product   │
    │  description → embed it → use as search vector │
    │  (closes vocabulary gap: user says "cheap",   │
    │   catalog says "budget-friendly")              │
    │                                                │
    │  Multi-Query: generate 3 query variants        │
    │  → parallel search → merge results (RRF)       │
    └──────────────────────┬─────────────────────────┘
                           │
                           ▼
    ┌────────────────────────────────────────────────┐
    │  TECHNIQUE 2: PARENT-CHILD RETRIEVAL           │
    │                                                │
    │  Child chunks (256 tokens): small, precise     │
    │  → used for embedding and similarity search    │
    │  Parent chunks (1024 tokens): full context     │
    │  → returned to the LLM once child is matched  │
    │  (best of both: precise match + rich context) │
    └──────────────────────┬─────────────────────────┘
                           │
                           ▼
    ┌────────────────────────────────────────────────┐
    │  TECHNIQUE 1: DENSE VECTOR SEARCH              │
    │                                                │
    │  Model: paraphrase-multilingual-MiniLM-L12-v2 │
    │  (local, EN + AR + FR, 384 dimensions)         │
    │  Index: HNSW (better accuracy than IVFFlat)    │
    │  Filter: WHERE tenant_id = :current (always)   │
    │  Returns: top-20 candidate parent chunks       │
    └──────────────────────┬─────────────────────────┘
                           │  20 candidates
                           ▼
    ┌────────────────────────────────────────────────┐
    │  TECHNIQUE 3: CROSS-ENCODER RE-RANKING         │
    │                                                │
    │  Model: cross-encoder/ms-marco-MiniLM-L-6-v2  │
    │  (local, fast — no API calls)                  │
    │  Scores each (query, chunk) pair jointly       │
    │  Unlike bi-encoder: sees both texts at once    │
    │  Returns: top-6 most relevant chunks           │
    └──────────────────────┬─────────────────────────┘
                           │  6 candidates
                           ▼
    ┌────────────────────────────────────────────────┐
    │  TECHNIQUE 6: MMR (Maximal Marginal Relevance) │
    │                                                │
    │  λ = 0.5 (relevance + diversity balanced)      │
    │  Prevents: 6 near-identical chunks in context  │
    │  Each selection maximizes relevance while      │
    │  minimizing overlap with already-selected      │
    └──────────────────────┬─────────────────────────┘
                           │  6 diverse chunks
                           ▼
    ┌────────────────────────────────────────────────┐
    │  TECHNIQUE 4: GRAPHRAG (parallel path)         │
    │                                                │
    │  Knowledge graph: Product → Category →        │
    │  Supplier (built with networkx)                │
    │  Graph traversal finds related products        │
    │  not reachable by vector distance alone        │
    │  Results merged with vector results via RRF    │
    └──────────────────────┬─────────────────────────┘
                           │  final context window
                           ▼
    ┌────────────────────────────────────────────────┐
    │  LLM GENERATION (GPT-4o)                       │
    │                                                │
    │  Input: NeMo Guardrails (input rail)           │
    │  + Presidio PII redaction before LLM sees it  │
    │  Generation: grounded in retrieved context     │
    │  Output: NeMo Guardrails (output rail)         │
    │  Answer includes product citations + stock     │
    │                                                │
    │  RAGAS evaluation: nightly CI gate              │
    │  (context precision, recall, faithfulness,     │
    │   answer relevance — all vs thresholds)        │
    └────────────────────────────────────────────────┘

    "Yes, we have the Samsung 65-inch QLED at $749..."
    [with product citation and available stock count]
```

The six techniques work together to solve different failure modes: dense search retrieves semantically similar items; parent-child provides rich context; query expansion bridges vocabulary gaps; cross-encoder re-ranking eliminates false positives from the initial retrieval; MMR ensures diversity in context; GraphRAG surfaces structurally related products that are vector-distant. The RAGAS CI gate means any degradation in RAG quality blocks deployment automatically.

---

### 6.7 Agentic AI System Architecture

```
    USER MESSAGE / SYSTEM EVENT
               │
               ▼
    ┌──────────────────────────────────────────┐
    │       3-TIER INTENT CLASSIFIER           │
    │                                          │
    │  Tier 1: TF-IDF + Logistic Regression   │
    │    ├─ High confidence + known intent     │
    │    └─► Fixed workflow (fast, cheap)      │
    │                                          │
    │  Tier 2: Fine-tuned DL (ONNX)           │
    │    ├─ High confidence + known intent     │
    │    └─► Fixed workflow                    │
    │                                          │
    │  Tier 3: GPT-4o zero-shot               │
    │    └─► Routes all remaining messages     │
    └──────────────────┬───────────────────────┘
                       │
           ┌───────────┴───────────┐
         ~80%                    ~20%
      Simple / Known          Complex / Novel
           │                       │
           ▼                       ▼
    ┌─────────────────┐   ┌───────────────────────┐
    │  FIXED FLOWS    │   │  SUPERVISOR AGENT      │
    │                 │   │  (LangGraph)           │
    │  Pre-defined    │   │                        │
    │  fast paths     │   │  · Plans multi-step    │
    │  No LLM needed  │   │    task decomposition  │
    │  for most cases │   │  · Routes to specialists│
    │                 │   │  · State persists in   │
    │                 │   │    Redis (resumable)   │
    └─────────────────┘   └──────────┬────────────┘
                                     │
                ┌────────────────────┼────────────────────┐
                │                    │                     │
                ▼                    ▼                     ▼
       ┌─────────────┐    ┌──────────────┐     ┌──────────────┐
       │ EXTRACTION  │    │  ENRICHMENT  │     │ COMM. AGENT  │
       │   AGENT     │    │    AGENT     │     │              │
       │             │    │              │     │ Drafts in    │
       │ CV + NER    │    │ ReAct loop   │     │ AR / FR / EN │
       │ on documents│    │ max 5 steps  │     │ Any channel  │
       └─────────────┘    └──────────────┘     └──────────────┘
                │                    │
                ▼                    ▼
       ┌─────────────┐    ┌──────────────┐
       │  SUPPLIER   │    │    STOCK     │
       │ DISCOVERY   │    │   MONITOR   │
       │   AGENT     │    │    AGENT    │
       │             │    │             │
       │ Finds &     │    │ Detects low │
       │ scores new  │    │ stock →     │
       │ suppliers   │    │ draft PO    │
       └─────────────┘    └──────────────┘
                │
                ▼
       ┌─────────────────────────────┐
       │         HITL GATE           │
       │   (all write actions)       │
       │                             │
       │  Importer sees draft:       │
       │  ✓ Approve → execute        │
       │  ✗ Reject → discard         │
       │  ✎ Edit → re-submit         │
       └─────────────────────────────┘

    Cross-cutting concerns:
    · MCP: agents connect to external tools via MCP servers
    · LangGraph checkpointing: state in Redis — no lost progress
    · NeMo Guardrails: input + output safety on every LLM call
    · Presidio: PII redacted before any user data reaches LLM
    · ToolError: tools return structured errors, never crash agent

    Future agents (Wave 1-3):
    Fraud Detection · Pricing Intelligence · Customer Identification
    Marketing Studio · WhatsApp Channel · Customer Segmentation
    Returns & After-Sales · Customs Document · Compliance RAG
```

The three-tier classifier is the key cost-efficiency decision: most operational messages (order status, product availability, price check) are handled by fast deterministic workflows without ever hitting an LLM. Only genuinely complex or ambiguous requests escalate to the Supervisor agent. This keeps inference costs low and response latency high for the majority of interactions while preserving full agent capability for the cases that need it. The HITL gate ensures the importer remains in control of all consequential actions — no email, order, or PO is executed without their approval.

---

### 6.8 Dunning Engine — 4 Tracks, 6 Directions

```
    ═══════════════════════════════════════════════════════════
    ALL MONEY FLOWS IN THE BUSINESS
    ═══════════════════════════════════════════════════════════

    ┌────────────┐         ┌──────────────┐         ┌──────────────┐
    │  SUPPLIER  │         │   IMPORTER   │         │   CONSUMER   │
    │            │         │ (+ Store     │         │  (retail     │
    │            │         │   Owner)     │         │   customer)  │
    └──────┬─────┘         └──────┬───────┘         └──────┬───────┘
           │                      │                         │
           │  ① Supplier          │  ③ Store invoices       │
           │    invoices          │    consumer             │
           │    importer          │    ─────────────────►  │
           │    ─────────────►    │                         │
           │                      │  ④ Consumer pays        │
           │  [TRACK 1:           │  ◄─────────────────     │
           │   B2B PAYABLES]      │                         │
           │  System alerts       │  [TRACK 4:              │
           │  importer 3 days     │   B2C COLLECTIONS]      │
           │  before due date     │  Day 3: gentle +        │
           │                      │    payment link         │
           │  ② Quality           │  Day 7: firm            │
           │    problem →         │  Day 14: final          │
           │    importer          │                         │
           │    disputes          │         ┌───────────────┤
           │    supplier          │         │  WHOLESALE    │
           │    ◄─────────────    │         │  STORE CLIENT │
           │                      │         │  (contact rec)│
           │  [TRACK 2:           │         └───────┬───────┘
           │   B2B DISPUTES]      │                 │
           │  Formal complaint    │  ⑤ Importer     │
           │  letter drafted      │    invoices     │
           │  in supplier's       │    wholesale    │
           │  language            │    client       │
           │  (on demand)         │    ─────────────►
           │                      │                 │
           │                      │  ⑥ Wholesale   │
           │                      │    client pays  │
           │                      │    ◄────────────│
           │                      │                 │
           │                      │  [TRACK 3:      │
           │                      │   B2B RECEIV.]  │
           │                      │  Day 7: remind  │
           │                      │  Day 14: escal. │
           │                      │  Day 21: final  │
           └──────────────────────┴─────────────────┘

    ═══════════════════════════════════════════════════════════
    TRACK SUMMARY
    ═══════════════════════════════════════════════════════════

    Track           Direction          Timeline        Channel
    ──────────────  ─────────────────  ──────────────  ──────────────
    B2B Payables    Importer→Supplier  -3 days (adv.)  Email (WhatsApp: Wave 1)
    B2B Disputes    Importer→Supplier  On demand        Email (WhatsApp: Wave 1)
    B2B Receivables Importer→Wholesale Day 7/14/21     Email (WhatsApp: Wave 1)
    B2C Collections Store→Consumer    Day 3/7/14       Email+SMS

    ALL TRACKS:
    · Draft generated by Communication Agent
    · Held in HITL queue → importer approves before sending
    · Tone selected by 3-class ML classifier (gentle/neutral/firm)
      based on segment, payment history, and overdue amount
    · Payment confirmation → dunning sequence stops immediately
    · Dunning does NOT require portal accounts — only contact info
      (email, phone, WhatsApp) stored in the contact record
```

The dunning engine covering all 6 directions in the capstone is a key architectural decision. Initially, the B2B Receivables and Disputes tracks seemed to require portal accounts for wholesale clients — but they only need contact records (email + phone), which the importer already maintains. Portal login for wholesale clients is a Phase 2 addition for ordering functionality. This means all four dunning tracks are fully operational from day one without building a wholesale portal. The ML tone classifier prevents tone mismatches that damage relationships — a VIP client who is 2 days late gets a gentle reminder, not a firm demand letter.

---

### 6.9 Order & Invoice Lifecycle

```
    CONSUMER                       SYSTEM
    ────────                       ──────

    Browses storefront
    (semantic search + AI chatbot)
           │
           ▼
    Adds to cart
           │
           ▼
    Checkout
    (Stripe / OMT / Whish)         ──► Payment gateway processes
           │                       ──► Webhook confirms payment
           ▼
    ORDER CONFIRMED                ──► Invoice PDF generated (auto)
                                   ──► Invoice emailed to consumer
                                   ──► n8n WF-07 triggered
                                   ──► Payment tracking started
                                   ──► Stock quantity decremented
                                        │
                                        ▼
                                   Payment window
                                   (configurable per tenant)
                                        │
                         ┌─────────────┴─────────────────┐
                         │ Paid in time?                  │
                         ▼                                ▼
                   PAYMENT CONFIRMED             DUNNING TRIGGERED
                   ─────────────────             ─────────────────
                   · Invoice → Paid              B2C Track:
                   · Order → Reconciled          · Day 3: gentle +
                   · Dunning auto-stopped          payment link
                   · n8n WF-08 triggered         · Day 7: firm
                   · Receivables updated         · Day 14: final
                         │                       Each → HITL → send
                         ▼
                   RECONCILED
                   Receivables dashboard updated
                   Available for reporting

    ─────────────────────────────────────────────────────────
    PARALLEL: IMPORTER VIEW
    ─────────────────────────────────────────────────────────

    Operations Command Center shows:
    · All active orders and their status
    · Invoice aging (current / 7d / 14d / 21d+ overdue)
    · Active dunning sequences and their stage
    · Revenue collected vs outstanding this month
    · One-click access to HITL approval queue
```

The order lifecycle integrates the storefront, payment gateways, invoice generation, and dunning engine into a single continuous flow. The importer does not need to manually track any of this — the Command Center gives them a live dashboard view of every order's status, and the dunning engine handles follow-up automatically (pending HITL approval). The payment gateway webhooks (Stripe, OMT, Whish) are the trigger that stops dunning sequences, making payment confirmation immediate and reliable.

---

### 6.10 n8n Automation Architecture

```
    EVENT SOURCE                n8n WORKFLOW             OUTPUTS
    ────────────                ────────────             ───────

    New tenant signup      ──►  WF-01: Provision    ──►  Create DB schema
                                                    ──►  Create MinIO bucket
                                                    ──►  Create Redis namespace
                                                    ──►  Send welcome email

    Document uploaded      ──►  WF-02: Doc Ingest   ──►  Call /api/extraction
                                                    ──►  Queue enrichment jobs (ARQ)

    Enrichment job done    ──►  WF-03: Enrich Done  ──►  Update catalog record
                                                    ──►  Notify importer

    PO approved (HITL)     ──►  WF-04: PO Send      ──►  Email PO to supplier
                                                    ──►  Create shipment record

    Shipment arriving      ──►  WF-05: Arrival      ──►  Admin panel notification
    (daily scheduled)           Alert               ──►  Upcoming arrivals badge

    Goods received         ──►  WF-06: Stock        ──►  Update stock quantities
    submitted                   Update              ──►  Check reorder thresholds
                                                    ──►  Flag ordered vs received

    Consumer order +       ──►  WF-07: Order        ──►  Generate invoice PDF
    payment confirmed           Confirmed           ──►  Email invoice to consumer
                                                    ──►  Start payment tracking

    Payment webhook        ──►  WF-08: Payment      ──►  Mark invoice paid
    received                    Received            ──►  Stop dunning sequence
                                                    ──►  Update reconciliation

    Invoice due - 3 days   ──►  WF-09: B2B          ──►  Draft payment reminder
                                Payables Dunning    ──►  HITL queue → send

    Consumer overdue:
    +3 days                ──►  WF-10a: B2C Day 3   ──►  Gentle draft + link
    +7 days                ──►  WF-10b: B2C Day 7   ──►  Firm draft
    +14 days               ──►  WF-10c: B2C Day 14  ──►  Final notice

    Stock threshold hit    ──►  WF-11: Reorder       ──►  Draft PO (Comm Agent)
                                Trigger             ──►  HITL queue → send to supplier

    Wholesale +7 days      ──►  WF-12: B2B Recv D7  ──►  Draft reminder → HITL
    Wholesale +14 days     ──►  WF-13: B2B Recv D14 ──►  Draft escalated → HITL
    Wholesale +21 days     ──►  WF-14: B2B Recv D21 ──►  Draft final → HITL
    Dispute filed          ──►  WF-15: B2B Dispute  ──►  Draft complaint → HITL

    ─── Future (Wave 1-3) ────────────────────────────────────────
    WF-16: WhatsApp Channel Integration
    WF-17: Marketing Content Scheduling
    WF-18: Fraud Alert Triage
    WF-19: Returns Processing
    WF-20: Supplier Discovery Campaign
    WF-21: GDPR/Data Erasure Request

    ──────────────────────────────────────────────────────────────
    ALL WORKFLOWS:
    · n8n calls FastAPI endpoints for ML/business logic
    · Python/ARQ handles all ML-heavy processing internally
    · HITL approval node in n8n before any external message
    · Webhook triggers for payment events (Stripe, OMT, Whish)
    · Schedule triggers for dunning timeline enforcement
```

n8n was chosen over alternatives (Celery+Beat, Temporal, Prefect) because it provides 400+ pre-built integrations (email, SMS, Stripe, WhatsApp, OMT) out of the box, has a visual HITL approval workflow node, supports both schedule and webhook triggers, and runs as a Docker container alongside the rest of the stack. The ML-heavy processing stays in Python (FastAPI + ARQ) where it belongs; n8n only handles event routing, external integrations, and workflow orchestration. This separation of concerns means n8n never needs to understand model inference, and Python never needs to manage email delivery.

---

### 6.11 CI/CD & MLOps Pipeline

```
    DEVELOPER PUSHES CODE
               │
               ▼
    ┌──────────────────────────────────────────────┐
    │   EVERY PUSH — any branch (< 3 min)          │
    │                                              │
    │  ① ruff check .          (linting)           │
    │  ② mypy --strict .       (type checking)     │
    │  ③ pytest tests/unit/ -q (LLM mocked)        │
    └─────────────────┬──────────┬─────────────────┘
                      │          │
                   PASS        FAIL
                      │          │
                      ▼          ▼
    ┌──────────────────────────────────────────────┐
    │   EVERY PR TO MASTER (< 15 min)              │
    │                                              │
    │  All push gates +                            │
    │  ④ pytest tests/integration/ (real DB+Redis) │
    │  ⑤ Cross-Tenant Red-Team (15 vectors)        │
    │     → MUST fail 100% of attempts             │
    │  ⑥ Agent trajectory snapshot tests           │
    │     (20 known intents — golden sequences)    │
    └─────────────────┬──────────┬─────────────────┘
                      │          │
                   PASS        FAIL
                      │          │
                      ▼          ▼
               MERGE ALLOWED  PR BLOCKED
                              Regression logged
                              in LangSmith

    ─────────────────────────────────────────────────
    NIGHTLY ON MASTER (expensive — real LLM calls)
    ─────────────────────────────────────────────────

    ┌──────────────────────────────────────────────┐
    │  ⑦ RAGAS Evaluation vs eval_thresholds.yaml  │
    │     ├── Context precision ≥ threshold         │
    │     ├── Context recall    ≥ threshold         │
    │     ├── Faithfulness      ≥ threshold         │
    │     └── Answer relevance  ≥ threshold         │
    │  ⑧ Classifier F1 gate (F1 macro ≥ 0.85)      │
    │  ⑨ Drift detection run                        │
    │     (PSI + chi-square + embedding drift)      │
    └──────────────────────────────────────────────┘

    Merge to master requires: all PR gates green on
    current commit AND latest nightly passed within
    24 hours (or triggered manually).

    ─────────────────────────────────────────────────
    MLOPS (running in background continuously)
    ─────────────────────────────────────────────────

    ┌──────────────────────────────────────────────┐
    │  MLflow Model Registry                       │
    │  · All models versioned (SHA-256 hash)       │
    │  · Stages: staging → production → archived  │
    │  · Champion/challenger gates on promotion    │
    └──────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────┐
    │  LangSmith Tracing                           │
    │  · Every LLM call logged (latency, tokens)  │
    │  · Every tool invocation logged              │
    │  · Every agent step traced                  │
    │  · RAGAS scores appended to traces           │
    └──────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────┐
    │  Drift Detection (scheduled nightly)         │
    │  · PSI for numeric feature drift             │
    │  · Chi-square for categorical drift          │
    │  · Embedding drift (cosine dist. tracking)  │
    │  · Alert → retrain trigger if drift > θ     │
    └──────────────────────────────────────────────┘
```

The CI pipeline enforces quality at three levels simultaneously: code correctness (tests), AI quality (RAGAS evals), and security (cross-tenant red-team). The cross-tenant test is treated as a hard gate — a single failure blocks the merge, with no exceptions. The distinction between tests (deterministic, run every commit) and evals (probabilistic, LLM-judged, slower) follows bootcamp guidance: evals are expensive and slow, so they run on CI but are cached when possible and not blocking locally. MLflow provides the model registry backbone that makes champion/challenger promotions auditable and rollbacks possible in under 60 seconds.

---

### 6.12 Data Storage Architecture

```
    ┌──────────────────────────────────────────────────────────┐
    │                    PostgreSQL 16                         │
    │                                                          │
    │  Core tables (all with tenant_id + RLS):                │
    │  ┌────────────┐ ┌────────────┐ ┌────────────────────┐  │
    │  │  tenants   │ │  products  │ │      orders        │  │
    │  │ (root, no  │ │ name, sku, │ │ consumer_id, items,│  │
    │  │  tenant_id)│ │ price,desc,│ │ total, status,     │  │
    │  └────────────┘ │ barcode,   │ │ payment_status     │  │
    │                  │ embedding_r│ └────────────────────┘  │
    │                  └────────────┘                         │
    │  ┌────────────┐ ┌────────────┐ ┌────────────────────┐  │
    │  │  invoices  │ │  dunning   │ │     suppliers      │  │
    │  │ order_ref, │ │ sequences  │ │ name, contact,     │  │
    │  │ amount,    │ │ track,day, │ │ score, language,   │  │
    │  │ due_date,  │ │ status,    │ │ performance_hist   │  │
    │  │ paid_at    │ │ sent_at    │ └────────────────────┘  │
    │  └────────────┘ └────────────┘                         │
    │  ┌────────────┐ ┌────────────┐                         │
    │  │   outbox   │ │ graph_edges│                         │
    │  │ event_type,│ │ src, dst,  │                         │
    │  │ payload,   │ │ rel_type   │                         │
    │  │ sent: bool │ │ (GraphRAG) │                         │
    │  └────────────┘ └────────────┘                         │
    └──────────────────────────────────────────────────────────┘

    ┌───────────────────────────┐  ┌──────────────────────────┐
    │      pgvector 0.7         │  │         Redis 7           │
    │   (HNSW — not IVFFlat)    │  │                          │
    │                           │  │  Enrichment job queue    │
    │  product_embeddings table │  │  (ARQ — per tenant ns)   │
    │  · vector(384)            │  │                          │
    │  · tenant_id tag          │  │  LangGraph checkpoints   │
    │  · product_id FK          │  │  (thread state per conv) │
    │  · chunk_type             │  │                          │
    │    (parent vs child)      │  │  Rate limit buckets      │
    │                           │  │  TTL caches (lru+TTL)    │
    │  HNSW chosen over         │  │  Session tokens          │
    │  IVFFlat: better recall   │  │  Outbox relay state      │
    │  accuracy at same speed   │  │                          │
    └───────────────────────────┘  └──────────────────────────┘

    ┌───────────────────────────┐  ┌──────────────────────────┐
    │         MinIO             │  │    HashiCorp Vault        │
    │   (S3-compatible, local)  │  │                          │
    │                           │  │  DB connection strings   │
    │  Bucket per tenant:       │  │  API keys:               │
    │  /tenant-{id}/            │  │  · OpenAI               │
    │    /docs/      (raw input)│  │  · Stripe, OMT, Whish   │
    │    /images/    (products) │  │  · Twilio (SMS)         │
    │    /invoices/  (PDFs)     │  │  · SendGrid (email)     │
    │    /exports/   (reports)  │  │  JWT signing secret      │
    │                           │  │  Tenant-specific secrets │
    │  Path signing via         │  │                          │
    │  short-lived presigned    │  │  Zero hardcoded secrets  │
    │  URLs (no public access)  │  │  in codebase             │
    └───────────────────────────┘  └──────────────────────────┘
```

The storage architecture separates hot operational data (PostgreSQL), fast semantic search (pgvector), async job queues and state (Redis), binary files (MinIO), and secrets (Vault) into purpose-built systems. Each storage system has its own tenant isolation strategy appropriate to its nature: RLS for relational data, metadata filtering for vector search, namespace prefixes for Redis keys, bucket-level separation for file storage, and per-tenant secret paths in Vault. HNSW was chosen over IVFFlat for the vector index because it provides better recall accuracy without requiring periodic retraining of the index (IVFFlat requires periodic vacuum-and-rebuild as data grows).

---

### 6.13 Complete System Data Flow

```
    ═══════════════════════════════════════════════════════════
    END-TO-END DATA FLOW: SUPPLIER TO CONSUMER
    ═══════════════════════════════════════════════════════════

    SUPPLIER                                         CONSUMER
    ────────                                         ────────

    Sends price list                                 Visits storefront
         │                                                │
         ▼                                                │
    Upload API                                           │
    /api/v1/catalog/ingest                               │
         │                                                │
         ▼                                                │
    [Extraction Pipeline]                                │
    · CV detects layout                                  │
    · NER extracts rows                                  │
    · Jobs queued (ARQ)                                  │
         │                                                │
         ▼                                                │
    [Enrichment Pipeline]                                │
    · ReAct agent per product                            │
    · Descriptions + images                              │
    · Outbox atomic commit                               │
         │                                                │
         ▼                                                │
    ┌───────────────────────────────────────────────┐   │
    │           PRODUCT CATALOG                     │   │
    │   PostgreSQL + pgvector (HNSW, tenant-scoped) │◄──┘
    └───────────────────────────────────────────────┘
         │
         ├──────────────────────────────────────────►
         │              Semantic search               Consumer searches
         │              GET /api/v1/catalog/search
         │
         ├──────────────────────────────────────────►
         │              Barcode lookup                Warehouse scan
         │              GET /api/v1/catalog/barcode/{code}
         │
         ├──────────────────────────────────────────►
         │              AI chatbot query              Consumer asks
         │              RAG → LLM → cited answer
         │
         └──────────────────────────────────────────►
                        Add to cart → checkout        Consumer orders
                        POST /api/v1/orders
                             │
                             ▼
                        Invoice generated
                        Payment tracking started
                             │
                        [Dunning Engine activates if needed]
                             │
                        Payment confirmed (webhook)
                             │
                        Order reconciled
```

The data flow diagram shows how the enriched product catalog sits at the center of the entire platform — it is both the output of the supply side processing and the input to all customer-facing features. Every consumer interaction (search, barcode scan, chatbot, order) reads from the same enriched, embedded, tenant-scoped catalog. This unified data model is what makes "each future feature is a new capability, never a rebuild" possible: new features like marketing content generation, fraud scoring, or pricing intelligence all consume the same catalog data.

---

*Decisions finalized: DEC-001 through DEC-019*
*Capstone start: father's Hybrid-mode tenant as first proof of concept*
