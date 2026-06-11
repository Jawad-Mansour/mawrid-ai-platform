Run a verification checklist for the Catalog Enrichment Pipeline (Phase 2).

Check each item below in order and report PASS / FAIL / NOT_YET_BUILT for each:

**Layer 1 — File Ingestion**
- [ ] `POST /catalog/documents/upload` accepts PDF and Excel (.xlsx)
- [ ] Unsupported MIME types (e.g. .txt, .csv) return 422 with allowed types listed
- [ ] Zero-byte file returns 422
- [ ] Re-uploading same file byte-for-byte returns same `document_id` and `already_existed: true` (idempotent)
- [ ] File stored in MinIO at `{tenant_id}/documents/{document_id}/{filename}`

**Layer 2 — Document Parsing**
- [ ] Excel files parsed with openpyxl (merged cells resolved)
- [ ] PDF files parsed with Docling → markdown + table rows
- [ ] `GET /catalog/documents/{document_id}` returns `status = completed` after successful parse
- [ ] `GET /catalog/documents/{document_id}` returns `status = failed` on parse error

**Layer 3 — GPT-4o Batch Extraction**
- [ ] `product_hash` computed as `SHA-256(tenant_id + ":" + product_name + ":" + sku_if_present)` — colon-delimited
- [ ] `product_name` preserved verbatim — never translated
- [ ] Price preserved exactly as written — no rounding, no currency conversion
- [ ] Missing SKU → `sku = null`, product still extracted
- [ ] Failed rows (no resolvable product_name) routed to `review_queue` table, not silently dropped
- [ ] Same product with new price → `price_history` appended, no new product record created
- [ ] `GET /catalog/documents/{document_id}/review-queue` lists failed extraction rows

**Layer 4 — Sequential Enrichment Pipeline (5 Steps)**
- [ ] Step 1 (Icecat): EAN barcode lookup attempted first; falls back to name lookup on failure
- [ ] Icecat confidence = `high` when EAN matched + ≥5 specs; `medium` when name matched + ≥3 specs
- [ ] Step 2 (SearXNG): skipped when Icecat confidence = `high`; returns top-3 URLs otherwise
- [ ] Step 3 (httpx + trafilatura): each URL fetched; text cleaned; truncated to 8 000 chars max
- [ ] Step 4 (GPT-4o spec fill): merged specs dict returned; no invented values
- [ ] Step 5 (GPT-4o description): 2–3 sentence English description returned
- [ ] Graceful degradation: timeout/error in any step does not abort pipeline; partial results saved
- [ ] Duplicate skip: product with `enrichment_status = enriched` → ARQ job returns `skipped`

**Phase 2.5 — Async ARQ Submission**
- [ ] `POST /catalog/documents/{id}/enrich` submits one ARQ job per extracted product; does NOT run pipeline inline
- [ ] Endpoint returns immediately with `{jobs_submitted: N}` (not enrichment results)
- [ ] `GET /catalog/documents/{document_id}` shows enrichment progress counts (pending / enriched / failed)
- [ ] ARQ worker (`enrichment_worker.py`) processes each product independently in background

**Layer 5 — Outbox Relay & Embedding**
- [ ] Product write + outbox embedding event written in one atomic transaction
- [ ] Outbox relay uses `FOR UPDATE SKIP LOCKED` — no duplicate processing on concurrent relay instances
- [ ] Relay calls OpenAI `text-embedding-3-small` → 1536-dim vector written to `products.embedding`
- [ ] Relay restart → unprocessed events re-processed without duplicates
- [ ] `GET /catalog/products` shows enriched products with `enrichment_status = enriched`

**Layer 6 — Internal Catalog**
- [ ] `GET /catalog/products` returns all enriched products for the tenant (regardless of storefront status)
- [ ] Zero enriched products appear in another tenant's catalog (cross-tenant isolation)
- [ ] `storefront_status = not_published` for every product after enrichment

Print a summary line: `X / Y checks PASS`. Flag any FAIL as a blocking issue.
