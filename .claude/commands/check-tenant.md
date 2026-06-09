Run cross-tenant isolation verification. This maps to CI Gate 5 (15 attack vectors).

Check each vector below and report PASS / FAIL / NOT_YET_BUILT for each:

**Layer 1 — PostgreSQL RLS**
- [ ] RLS policy active on `products` table — query as Tenant A returns only Tenant A rows
- [ ] RLS policy active on `purchase_orders`, `invoices`, `hitl_actions`, `customers`, `suppliers`, `dunning_sequences`, `product_embeddings`, `consumer_orders` tables

**Layer 2 — Repository Base Class**
- [ ] `TenantRepository` auto-injects `tenant_id` on every query in every repo
- [ ] `tenant_id` is read from the verified JWT — never from the request body

**Layer 3 — Vector Store**
- [ ] pgvector search always includes `AND tenant_id = {current_tenant_id}`
- [ ] Embedding search as Tenant A returns zero results from Tenant B's embeddings

**15 Attack Vectors (all must block)**
- [ ] Direct product ID access: `GET /catalog/products/{tenant_b_product_id}` as Tenant A → 404
- [ ] Enriched catalog search as Tenant A → zero Tenant B products returned
- [ ] Storefront search as Tenant A → zero Tenant B products returned
- [ ] HITL queue as Tenant A → zero Tenant B actions visible
- [ ] Invoice list as Tenant A → zero Tenant B invoices returned
- [ ] Dunning sequence access as Tenant A → zero Tenant B sequences
- [ ] Supplier list as Tenant A → zero Tenant B suppliers returned
- [ ] Customer list as Tenant A → zero Tenant B customers returned
- [ ] PO list as Tenant A → zero Tenant B POs returned
- [ ] Shipment list as Tenant A → zero Tenant B shipments
- [ ] MinIO: presigned URL for Tenant B's document is inaccessible to Tenant A
- [ ] Redis: Tenant A's agent checkpoint is not readable by Tenant B
- [ ] pgvector chatbot as Tenant A → zero Tenant B product chunks returned
- [ ] Consumer order creation as Tenant A cannot reference Tenant B's products
- [ ] Admin panel summary stats for Tenant A contain only Tenant A data

Print a summary line: `X / 15 attack vectors BLOCKED`. Any failure is a CI hard fail.
