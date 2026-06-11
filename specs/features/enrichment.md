# Feature Spec — Catalog Enrichment Pipeline

*Must be consistent with `specs/constitution.md`. Any conflict: constitution wins.*

---

## 1. What It Does

A supplier sends a price list in any format — PDF, Excel spreadsheet, scanned image, WhatsApp photo. The enrichment pipeline receives it and produces a fully searchable, AI-augmented **internal catalog** in under five minutes. This replaces a full day of manual data entry.

The result is the importer's **private working tool** — a structured, semantically searchable view of what their suppliers offer. It is not the storefront. No enriched product appears on the consumer-facing store until the importer deliberately publishes it after receiving physical goods.

---

## 2. Who Uses It

| Actor | Action |
|---|---|
| Importer / Store Owner | Uploads a supplier price list via the admin panel |
| Importer / Store Owner | Monitors enrichment progress via the status panel |
| Importer / Store Owner | Browses the enriched internal catalog to select products for ordering |
| Importer / Store Owner | Uses barcode scan to look up individual products in the warehouse |
| Admin panel | Shows enrichment queue: pending / running / enriched / partial / failed / DLQ |

The consumer never interacts with this feature. The enriched catalog is invisible to consumers.

---

## 3. Inputs

| Input | Format | Notes |
|---|---|---|
| Supplier price list | PDF | Digital text or scanned/image-based |
| Supplier price list | Excel (.xlsx) | Single or multi-sheet |
| Supplier price list | JPEG | Scanned image, WhatsApp photo |
| Supplier price list | PNG | Screenshot, scanned image |

**Rejected inputs** (return a validation error, nothing stored):
- Any MIME type other than the four above
- Files larger than the per-tenant configured size limit
- Zero-byte files

---

## 4. Outputs

### 4.1 — Per Document
- `document_id` — returned immediately on upload for status tracking
- MinIO storage at `{tenant_id}/documents/{document_id}/original.{ext}`
- Enrichment status per document: how many products are queued / enriched / partial / failed

### 4.2 — Per Product (after full pipeline)
| Field | Source | Mutable after extraction? |
|---|---|---|
| `name` | NER extraction | No |
| `sku` | NER extraction | No |
| `barcode` | NER extraction (if present) | No |
| `price` | NER extraction (exact as written) | No — new price on re-upload archives to `price_history` |
| `unit` | NER extraction | No |
| `quantity` | NER extraction | No |
| `price_history` | Accumulated on re-uploads | Append-only |
| `description` | Enrichment agent | Yes (agent fills this) |
| `specifications` | Enrichment agent | Yes — JSONB key-value pairs |
| `image_url` | Enrichment agent | Yes — sourced externally, stored in MinIO |
| `enrichment_status` | Pipeline state machine | Auto-managed |
| `inventory_status` | Pipeline sets initial value | `not_ordered` after enrichment |
| `storefront_status` | Pipeline sets initial value | `not_published` after enrichment |
| `product_hash` | Computed on extraction | Immutable |

---

## 5. Pipeline Layers

The pipeline has six sequential layers. Each layer must be verified independently before the next begins. A failure in any layer is recorded — never silently swallowed.

### Layer 1 — File Ingestion

**Responsibility**: Receive the file, validate it, store it durably.

- Multipart upload endpoint: `POST /catalog/ingest`
- MIME type validated against the allowed list before any processing
- File stored in MinIO at the correct tenant-scoped path atomically — either fully stored or not stored at all
- Upload returns `document_id` immediately
- **Idempotency**: re-uploading the same file (same content hash) returns the same `document_id`, no duplicate storage, no duplicate pipeline runs
- If MinIO is unreachable: request fails with a clear error, nothing partially stored
- Status endpoint: `GET /catalog/ingest/{document_id}/status`

**Failure modes:**
- MinIO unavailable → 503 with error message, nothing written
- File exceeds size limit → 413 with limit in error message
- Unsupported MIME type → 422 with allowed types listed
- Zero-byte file → 422

---

### Layer 2 — Document Structure Detection

**Responsibility**: Understand what the document contains before extracting anything.

**Routing by document type:**

| Format | Method |
|---|---|
| Excel (.xlsx) | `openpyxl` reads structure directly — no vision model needed |
| PDF with digital text | Text extracted directly; tables detected from layout |
| PDF that is scanned/image-based | Routed to GPT-4o vision |
| JPEG / PNG | Pre-processed (contrast enhancement, deskew, noise reduction) then GPT-4o vision |

**Vision model identifies**: document type (price list / catalog / invoice), table boundaries, column headers, data rows.

**Output**: Normalized intermediate format — list of rows, each row mapped to column positions. This intermediate is stored durably before Layer 3 starts.

**Ambiguity handling:**
- Low detection confidence → flagged for manual review, not forced into extraction
- Document with no table structure (plain paragraphs only) → flagged as non-tabular, pipeline stops here for that document
- Detection result logged in full for debugging

**Failure modes:**
- Vision model call fails → document flagged, enrichment status set to `failed`, error recorded
- Rotated image (90°) → pre-processing corrects orientation before vision call
- Low-quality scan → lower confidence score, flagged — not silently sent to extraction

---

### Layer 3 — Data Extraction (GPT-4o Batch Extraction)

**Responsibility**: Extract every product field from the detected rows. Nothing fabricated.

> **Implementation note (DEC-021)**: Extraction uses GPT-4o in batches of 20 rows, not a local BERT/NER model. Headers in any language are normalised to English keys. `product_name` is preserved verbatim — never translated.

**Extracted fields per product row:**
`name`, `sku`, `barcode` (if present), `price`, `unit`, `quantity`, any additional specification columns detected.

**Field rules:**
- Price is preserved **exactly as written** — no rounding, no currency conversion, no modification
- SKU is preserved exactly — no normalization
- Barcode is preserved exactly (EAN-13, UPC, Code-128, QR — whatever is in the document)
- Missing fields are `null` — never guessed, never fabricated
- Price ranges (e.g., "$199–$249") are stored as-is, not forced into a single value

**Product hash computation** (determines identity, used for idempotency):
```
if sku is not null:
    product_hash = SHA-256(tenant_id + ":" + product_name + ":" + sku)
else:
    product_hash = SHA-256(tenant_id + ":" + product_name)
```
Colon delimiter prevents hash collisions between `("AB", "CDE")` and `("ABC", "DE")`.

Price is **intentionally excluded from the hash**. The same product re-submitted with an updated price is the same product — not a new one. The new price is appended to `price_history`:
```json
[
  {"price": "499 USD", "observed_at": "2026-06-07T10:00:00Z"},
  {"price": "479 USD", "observed_at": "2026-06-14T09:00:00Z"}
]
```
Current price = the last entry. Previous prices are never deleted.

**Extraction audit log**: for each row, the original raw text and the extracted fields are stored side by side. This enables debugging when extraction is wrong.

**Failure modes:**
- NER fails on a specific row → that row is flagged and recorded, pipeline continues with remaining rows
- NER fails entirely → document status set to `failed`, error logged

---

### Layer 4 — Product Enrichment (Sequential Pipeline, 5 Steps)

**Responsibility**: Enrich each extracted product with real, accurate information from external sources.

**Runs per product** (not per document). Each product is an independent enrichment job.

> **Implementation note (DEC-022)**: This is a **deterministic sequential pipeline**, NOT a LangGraph ReAct agent. Phase 8's Enrichment Specialist wraps this pipeline in a single LangGraph node. The pipeline itself has no agent loop — it executes exactly 5 steps in order, with graceful degradation at each.

**The 5 steps (executed in order):**

| Step | Source | Action |
|---|---|---|
| 1 | Icecat Open API | Lookup by EAN barcode first; fall back to product name. Confidence: `high` if EAN + ≥5 specs; `medium` if name + ≥3 specs. |
| 2 | SearXNG | Search `"{name} {sku} specifications datasheet"` → top 3 URLs. **Skipped** if Step 1 returned `high` confidence. |
| 3 | httpx + trafilatura | Fetch each URL, extract clean text (8 000 chars max). Concurrent fetches, timeout per URL. |
| 4 | GPT-4o spec fill | Merge Icecat specs + web text → final `specifications` dict. No invented values — only what appears in sources. |
| 5 | GPT-4o description | 2–3 sentence English product description from merged context. |

**Graceful degradation**: a timeout or error in any step does not abort the pipeline. The product is saved with whatever data was gathered before the failure.

**Immutable fields — pipeline never overwrites:**
`price`, `sku`, `barcode` — locked at extraction.

**Partial enrichment**: if description or specifications are empty after all 5 steps, `enrichment_status = partial`. Partial products are still in the internal catalog and searchable.

**Duplicate skip**: if `product_hash` already has `enrichment_status = enriched` → skip. No re-enrichment. ARQ job returns `{status: "skipped", reason: "already_enriched"}`.

**State after successful enrichment:**
```
enrichment_status = enriched
inventory_status  = not_ordered
storefront_status = not_published
```

**Failure modes:**
- All 5 steps return nothing → `enrichment_status = partial`, product saved with empty specs
- Network timeout on every step → `partial` (graceful fallback, not crash)
- Product not found anywhere → `partial` with only extraction-time fields

---

### Layer 5 — Queue, Storage & Outbox

**Responsibility**: Reliable, fault-tolerant, idempotent job execution and embedding storage.

**Job queue (ARQ + Redis):**
- One enrichment job per extracted product
- Job key = `product_hash` — submitting the same job twice = one execution, no duplicate
- Retry policy: 3 attempts with exponential backoff on transient failures
- After 3 failures: job moved to **Dead Letter Queue (DLQ)**
  - DLQ records: job payload, error message, stack trace, attempt count, timestamps
  - DLQ inspectable via admin API: list, retry individual job, discard individual job

**Outbox pattern (atomic write):**
After enrichment succeeds, a single transaction writes:
1. Enriched product to `products` table
2. Embedding event to `outbox` table

If either write fails, both are rolled back. The job is retried from the queue.

**Outbox relay (separate process):**
- Polls outbox for unprocessed events (`FOR UPDATE SKIP LOCKED` — crash-safe, no duplicate processing)
- Generates embedding using OpenAI **text-embedding-3-small** (1536-dim) via API call (DEC-027)
- Writes vector to `products.embedding` (`Vector(1536)` column, HNSW index)
- Marks outbox event as processed
- If relay crashes: on restart, any unprocessed event is re-processed idempotently
- Single full-document embedding per product in Phase 2

> **Phase 4 adds chunking**: In Phase 4, a separate `product_chunks` table stores parent chunks (~1024 tokens, LLM context) and child chunks (~256 tokens, vector search targets). Phase 2 uses a single full-document embedding on the `products` table only.

**Image storage:**
- Product image URL found by enrichment agent → downloaded → stored in MinIO at `{tenant_id}/images/{product_id}.{ext}`
- `image_url` on the product record updated to the MinIO path

**Status tracking:** `GET /catalog/ingest/{document_id}/status` returns:
```json
{
  "document_id": "...",
  "total_products": 20,
  "queued": 2,
  "in_progress": 1,
  "enriched": 15,
  "partial": 1,
  "failed": 0,
  "dlq": 1
}
```

**Failure modes:**
- Redis unavailable at job submission → upload endpoint returns 503
- pgvector write fails → outbox event remains `sent = false`, retried on next relay cycle
- MinIO unavailable for image storage → enrichment continues without image, logged

---

### Layer 6 — Barcode Lookup

**Responsibility**: Fast in-warehouse product lookup by barcode or SKU scan.

- Endpoint: `GET /catalog/barcode/{code}`
- Looks up by `barcode` field first, then by `sku` field
- Returns: product name, description, category, current stock quantity, purchase price
- Response time: **< 500ms** (pure DB query, no AI, no embeddings)
- Tenant-scoped: only returns products belonging to the authenticated tenant
- Used during goods receiving (scan to verify against PO) and in-warehouse stock checks

---

## 6. Acceptance Criteria

All criteria must pass before Phase 2 is considered complete. Each is independently verifiable.

### AC-1: File Acceptance
- PDF, Excel (.xlsx), JPEG, PNG — all accepted and stored in MinIO
- .txt, .csv, .docx — all rejected with a 422 validation error
- Zero-byte file → 422
- File exceeding size limit → 413
- MinIO offline during upload → 503, no partial file stored

### AC-2: Idempotency
- Re-uploading the same file byte-for-byte returns the same `document_id`
- No new enrichment jobs queued for a re-upload
- Re-uploading a file where the product prices have changed → same products updated, `price_history` appended — no new product records created

### AC-3: Extraction Accuracy
- Arabic, French, and English product names extracted without corruption
- Mixed-language rows handled without crashing
- Price preserved exactly as written (no rounding, no conversion)
- Missing SKU → `sku = null`, product still extracted
- Rows that fail NER → flagged in audit log, not silently skipped
- Audit log contains original row text alongside extracted fields for every row

### AC-4: Enrichment Quality
- 15 manually reviewed enriched products: no fabricated specifications
- Products with Arabic names: web search executed with Arabic query
- Partial enrichment (some fields found, some not) → `enrichment_status = partial`, product in catalog
- Failed tool call → agent continues, does not crash
- 5-step limit enforced: agent never exceeds 5 reasoning steps per product
- LangSmith traces visible for every enrichment agent call

### AC-5: Queue Reliability
- 20 products submitted → exactly 20 jobs in queue (no duplicates)
- Same 20 products submitted again → queue unchanged (idempotent)
- Job that fails 3 times → appears in DLQ with error detail and stack trace
- Retry from DLQ → executes correctly
- Relay killed mid-embedding → on restart, remaining embeddings generated without duplicates
- `products` table and `product_embeddings` table are in sync for all enriched products

### AC-6: Pipeline Speed
- Upload to fully searchable in internal catalog: **< 5 minutes** for a 20-product document

### AC-7: Storefront Isolation
- Zero enriched products appear in storefront search results
- `storefront_status = not_published` for every product after enrichment
- Consumer chatbot cannot find any enriched-but-unpublished product

### AC-8: Barcode Lookup
- `GET /catalog/barcode/{code}` returns correct product in **< 500ms**
- Lookup by barcode field succeeds
- Lookup by SKU field succeeds (fallback)
- Cross-tenant lookup returns 404 (never returns another tenant's product)

### AC-9: Search Scope
- Internal catalog search (`GET /catalog/search`) returns all enriched products for the tenant regardless of storefront status
- Storefront search (`GET /store/search`) returns only `storefront_status = published` products
- Both scopes always filtered by `tenant_id` — zero cross-tenant results

---

## 7. Edge Cases

| Scenario | Expected Behavior |
|---|---|
| PDF is a cover page with no product table | Flagged as non-tabular after Layer 2; no extraction attempted; status = `failed`; error recorded |
| Excel has 5 sheets, only one is a price list | Layer 2 identifies the correct sheet; other sheets ignored |
| Product row has a price range ("$199–$249") | Stored as-is in price field; not forced to single value |
| Same product appears twice in same document (exact duplicate row) | Same `product_hash` → one job queued, one product record |
| Same product appears twice with different prices in same document | Most recently seen price wins; both prices in `price_history` |
| Supplier document is in Arabic only (right-to-left) | Language preserved throughout; embedding model handles Arabic natively |
| Image download fails (URL returns 404) | `image_url` remains null; enrichment status still `enriched` (image is not a required field) |
| Enrichment agent finds a product image but it's behind a paywall | Image not downloaded; `image_url` = null; enrichment continues |
| Relay crashes after writing embedding for product 7 of 20 | On restart: products 1–7 have `sent = true`, skipped; products 8–20 re-processed |
| Product enriched but pgvector write fails | Outbox event not marked `sent`; retried on next relay cycle; no duplicate embedding |
| Tenant uploads 1000-product catalog | Pipeline scales via queue; no timeout on upload endpoint; status endpoint shows progress |

---

## 8. What This Feature Is Not

- **Not the storefront.** Enriched products are the importer's internal tool. Publishing is a separate, deliberate act in the procurement flow.
- **Not a pricing tool.** The pipeline preserves prices exactly as received. It never suggests, adjusts, or compares prices.
- **Not a barcode catalog builder.** Barcode lookup is a warehouse tool. The catalog is built from supplier documents, not by scanning items one by one.
- **Not a deduplication tool across tenants.** `product_hash` is scoped to `tenant_id`. The same Samsung TV for two different tenants is two independent product records.

---

*Next: `specs/features/procurement.md`*
