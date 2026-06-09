Run a verification checklist for the Catalog Enrichment Pipeline (Phase 2).

Check each item below in order and report PASS / FAIL / NOT_YET_BUILT for each:

**Layer 1 — File Ingestion**
- [ ] `POST /catalog/ingest` accepts PDF, Excel (.xlsx), JPEG, PNG
- [ ] Unsupported MIME types return 422 with allowed types listed
- [ ] Zero-byte file returns 422
- [ ] File exceeding size limit returns 413
- [ ] MinIO offline → 503, nothing partially stored
- [ ] Re-uploading same file byte-for-byte returns same `document_id` (idempotent)

**Layer 2 — Structure Detection**
- [ ] Excel files parsed with openpyxl (no vision model call)
- [ ] Digital PDF text extracted directly
- [ ] Scanned PDF / JPEG / PNG routed to GPT-4o vision
- [ ] Low-confidence detection flagged, not forced through extraction
- [ ] Rotated images pre-processed before vision call

**Layer 3 — NER Extraction**
- [ ] product_hash computed as `SHA-256(tenant_id + ":" + product_name + ":" + sku_if_present)` — colon-delimited
- [ ] Price preserved exactly as written — no rounding, no conversion
- [ ] Missing SKU → `sku = null`, product still extracted
- [ ] Audit log stores original row text alongside extracted fields for every row
- [ ] Same product with new price → `price_history` appended, no new product record

**Layer 4 — Enrichment Agent**
- [ ] Max 5 reasoning steps enforced — agent never exceeds this
- [ ] ToolError caught → agent continues with partial data, does not crash
- [ ] Duplicate skip: `product_hash` with `enrichment_status = enriched` → no re-enrichment
- [ ] LangSmith trace visible for every enrichment agent call

**Layer 5 — Queue, Outbox, Relay**
- [ ] One ARQ job per product, keyed on `product_hash` (idempotent submission)
- [ ] Job fails 3 times → appears in DLQ with error detail and stack trace
- [ ] Outbox: product write + embedding event in one atomic transaction
- [ ] Relay restart → events with `sent = false` re-processed without duplicates
- [ ] `GET /catalog/ingest/{document_id}/status` returns correct counts

**Layer 6 — Barcode Lookup**
- [ ] `GET /catalog/barcode/{code}` returns correct product in < 500ms
- [ ] Lookup by barcode field, fallback to SKU
- [ ] Cross-tenant lookup returns 404

**Cross-Tenant**
- [ ] Zero enriched products appear in another tenant's catalog search

Print a summary line: `X / Y checks PASS`. Flag any FAIL as a blocking issue.
