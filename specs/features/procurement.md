# Feature Spec — Order Management & Procurement

*Must be consistent with `specs/constitution.md`. Any conflict: constitution wins.*

---

## 1. What It Does

After the enrichment pipeline fills the internal catalog, the importer browses it, selects products, and places purchase orders with suppliers. The platform manages the complete cycle:

**select products → draft order → HITL-approve PO → track shipment → receive goods → update stock → publish deliberately to storefront**

This is the importer's primary daily workflow. Nothing in this feature bypasses HITL. Nothing reaches the storefront automatically.

---

## 2. Who Uses It

| Actor | Action |
|---|---|
| Importer / Store Owner | Browses internal catalog, selects products, creates order drafts |
| Importer / Store Owner | Reviews and approves/rejects/edits PO drafts in HITL Approval Center |
| Importer / Store Owner | Logs shipment details, updates status as container moves |
| Importer / Store Owner | Records received quantities, logs damages, files disputes |
| Importer / Store Owner | Selects products for storefront publishing, sets retail prices |
| Communication Agent | Drafts purchase orders in the supplier's registered language |
| n8n | WF-04 (PO approved → send to supplier), WF-05 (arrival alert), WF-06 (goods received → stock update) |

---

## 3. Inputs

| Input | Source |
|---|---|
| Product selections + quantities | Importer browsing internal catalog |
| Desired delivery date | Importer per draft |
| Supplier language preference | Supplier record (`language` field: ar / fr / en) |
| Shipment details | Importer after PO confirmed by supplier |
| Received quantities + damaged quantities | Importer at goods receiving |
| Retail price + storefront quantity | Importer at publishing |

---

## 4. Sub-Features

### 4.1 — Order Draft

**What it does**: Collects product selections into a reviewable, editable draft before committing to a PO.

- Importer selects products from the enriched internal catalog with filters (supplier, category, price range, enrichment status)
- Inline quantity field per product
- Drafts **automatically grouped by supplier** — one draft per supplier, created transparently
- Draft is fully editable: change quantities, remove products, add more products
- Desired delivery date is set per draft
- Draft is linked to the source document it came from
- Multiple drafts can exist simultaneously (different suppliers, different ordering cycles)

**Draft states**: `draft` (editable) → `submitted` (locked)

**Submit vs Place Order** — these are two distinct, explicit actions:
- **Submit**: "I am done selecting. Lock this list." Draft becomes read-only. A "Place Order" button appears.
- **Place Order**: "Now draft the PO and send it." Triggers Communication Agent to draft the PO. Until this is clicked, no agent runs and nothing is sent.

This separation gives the importer a final review of the product list before the PO is drafted.

**Failure modes:**
- Importer tries to edit a submitted draft → 409, draft is locked
- Product removed from catalog while in a draft → draft item marked stale, importer notified

---

### 4.2 — Purchase Order (HITL)

**What it does**: Generates a purchase order draft in the supplier's language and holds it for importer approval before anything is sent.

**Trigger**: Importer clicks "Place Order" on a submitted draft.

> **Phase 3 vs Phase 8 implementation note**: "Communication Agent" is the Phase 8 LangGraph agent. In Phase 3, PO drafting is a direct `chat_completion()` call using `prompts/communication/purchase_order.yaml`. The Phase 8 Communication Agent wraps this exact service call in a LangGraph node — no logic changes, only the caller changes. The HITL gate and all payload formats are identical.

**Flow**:
1. PO drafted in the supplier's registered language (AR / FR / EN) via `chat_completion()` with the purchase order prompt template
2. PO content: supplier name, importer name + contact, ordered product list (name, qty, unit price), requested delivery date, total value
3. PO draft written to `hitl_actions` table with `action_type = purchase_order_send`
4. Importer sees PO in HITL Approval Center: full PO text, supplier contact details, delivery channel
5. Importer choices:
   - **Approve** → PO sent to supplier by email (WhatsApp in Wave 1); order status → `sent`
   - **Reject** → draft discarded; order status → `cancelled`
   - **Edit** → importer modifies content inline → re-queued for approval before send
6. After send: PO record created (`purchase_order_id`, `supplier_id`, items, total, `sent_at`, status)
7. Supplier confirmation logged manually by importer (marks order as "confirmed by supplier")

**Language rule**: PO language is always the supplier's registered language — not the importer's preferred language.

**HITL constraint**: The PO is never sent without explicit importer approval. The Communication Agent produces a draft only.

**Failure modes:**
- Communication Agent fails to draft PO → HITL action created with error state; importer can write the PO manually and approve
- Email send fails after approval → status remains `pending_send`, retry with notification
- HITL action expires (default: 72 hours) → action archived, order status set to `expired_hitl`; importer must re-trigger

---

### 4.3 — Shipment / Container Tracking

**What it does**: Tracks where the goods are between PO send and physical arrival.

**Trigger**: After PO sent, importer logs shipment details.

**Shipment fields**:
- Carrier name
- Container or tracking number (optional)
- Ship date (actual or estimated)
- Expected arrival date
- Port or delivery location

**Status progression**: `pending_shipment` → `shipped` → `in_transit` → `at_customs` → `arrived`

- Importer updates status manually at each stage
- Expected arrival date can be updated at any time (delays are normal, no penalty)
- Multiple shipments per PO are allowed (partial deliveries)
- Shipment list view: all active shipments with status badges and days until expected arrival

**Arrival alert**: Scheduled daily check (n8n WF-05). Any shipment with expected arrival within the configurable window (default: 3 days) → notification in admin panel under "Upcoming Arrivals." No external message is sent — internal notification only.

**Failure modes:**
- Importer marks arrived before logging shipment → arrival can be logged retroactively
- Multiple partial deliveries → each tracked as an independent shipment record

---

### 4.4 — Goods Received & Stock Update

**What it does**: Records what was actually received when the container arrives and updates stock atomically.

**Trigger**: Importer marks shipment status as `arrived`, clicks "Record Receipt."

**Receiving form**: For each ordered product:
- `qty_received` — actual quantity physically received
- `qty_damaged` — units received in damaged / unusable condition (separate field, not deducted from qty_received)

**Barcode scan**: scan a product barcode to auto-highlight its row in the receiving form (uses Layer 6 of enrichment pipeline).

**Stock update rule** (applied per product):
```
qty_in_stock += qty_received - qty_damaged
```
Only undamaged units enter stock. Damaged units are counted and recorded but do not increase stock.

**Post-receipt state**: `inventory_status → in_stock` (if net qty > 0)

**Discrepancy detection** (auto-flagged on supplier record):
- `qty_received < qty_ordered` by more than 5% → discrepancy flag logged
- `qty_damaged > 0` → damage flag logged

**Damage dispute flow**:
After recording damages, a confirmation screen appears:
> "You recorded X damaged units of [product]. File a supplier dispute for damaged goods?"

- **File Dispute**: pre-fills dispute form (product name, `qty_damaged`, PO reference, shipment ID, damage description field) → importer submits → n8n WF-15 fires → Communication Agent drafts formal complaint → HITL queue (`action_type = dispute_letter`)
- **Skip**: dismissed; importer can file the dispute manually later from the supplier detail page

**Atomicity**: stock update is all-or-nothing per receiving event. A partial save is a data integrity violation. If the transaction fails, the entire receiving event is rolled back and the importer resubmits.

**Idempotency**: a receiving event for a given shipment can only be submitted once. A second attempt returns 409.

**Audit trail**: every receiving event is logged with timestamp, importer user_id, per-product received quantities, and damage counts.

**Failure modes:**
- DB transaction fails mid-write → full rollback, 500 returned, importer retries
- Importer accidentally records wrong qty → admin can void and re-record a receiving event (with audit trail)
- Shipment already received → 409 with explanation

---

### 4.5 — Storefront Publishing (Deliberate Selection)

**What it does**: Moves products from "in stock" to "visible on storefront" through an explicit importer action.

**Trigger**: Importer navigates to "Ready to Publish" section (products with `inventory_status = in_stock` and `storefront_status = not_published`).

**Per-product publish action**:
- Set **retail price** (required, independent of purchase price)
- Set **storefront quantity** (may be less than total stock — importer reserves stock for wholesale)
- Optional: add storefront-specific description override

**Publish result**: `storefront_status → published`; product appears on consumer storefront.

**Unpublish**: available at any time. `storefront_status → not_published`. Product disappears from storefront. Stock qty unchanged.

**Stock vs storefront qty**: tracked independently at all times.
- `qty_in_stock` = physical units on hand
- `storefront_qty` = units the importer has made available to consumers
- Consumer purchases decrement `storefront_qty`, not `qty_in_stock` directly
- When `storefront_qty` reaches 0 → storefront shows "Out of Stock", product stays published, stock still shows remaining units

**Bulk publish**: select multiple products → apply price multiplier (e.g., purchase price × 1.3) → publish all in one action.

**Auto-publish (Retail Only mode only)**: tenant can enable `auto_publish_on_receive`. When enabled, all received products are automatically published at the configured margin multiplier. This is a standing configuration decision, not bypassing HITL — the importer made an explicit choice at configuration time. Individual prices can still be edited after auto-publish.

**Admin catalog view** always shows three separate columns: stock qty / storefront qty / storefront status.

**Failure modes:**
- Importer tries to publish a product with no retail price → validation error, 422
- Importer sets storefront qty > stock qty → validation error
- Consumer purchases exactly the last unit while importer is mid-publish → atomic decrement, no oversell

---

## 5. Order Status Lifecycle

```
draft → submitted → pending_hitl → sent → confirmed → in_transit → received → [published to storefront]
                                        ↘ cancelled (rejected HITL or importer cancels)
                                        ↘ expired_hitl (HITL action expired)
```

---

## 6. Acceptance Criteria

### AC-1: Draft Grouping
- Select 5 products from 2 suppliers → exactly 2 drafts created, each containing only that supplier's products

### AC-2: Submit/Place Order Separation
- Submit a draft → status = `submitted`, edits rejected
- PO is NOT drafted on submit — only on "Place Order" click

### AC-3: PO Language
- French-speaking supplier → PO drafted in French
- Arabic-speaking supplier → PO drafted in Arabic
- English-speaking supplier → PO drafted in English

### AC-4: HITL Controls All Sends
- No PO reaches a supplier without an approved HITL action
- Edit flow: modified content is what gets sent, not the original draft

### AC-5: Shipment Tracking
- Shipment logged after PO sent → status = `pending_shipment`
- Status updated through all stages manually
- Expected arrival date updateable without penalty
- Two shipments for same PO → tracked independently

### AC-6: Arrival Alert
- Expected arrival within 3 days (configurable) → alert visible in admin panel under "Upcoming Arrivals"

### AC-7: Stock Accuracy
- Receive 100 ordered, log 20 damaged → `qty_in_stock += 80`
- Receive 80 of 100 ordered (>5% short) → discrepancy flag on supplier record
- Receive 98 of 100 ordered (<5% short) → no flag
- Receive twice for same shipment → second attempt returns 409

### AC-8: Dispute Surface
- Record >0 damaged → dispute confirmation screen appears
- Click "File Dispute" → dispute form pre-filled → HITL draft created with `action_type = dispute_letter`

### AC-9: Stock Atomicity
- Mid-transaction crash → full rollback, no partial stock update

### AC-10: Storefront Independence
- Publish 60 of 100 units → storefront shows 60, admin shows 100 in stock
- Consumer buys all 60 → storefront shows "Out of Stock", admin stock still shows 40
- Unpublish → removed from storefront, stock unchanged
- Retail price always independent of purchase price

### AC-11: Cross-Tenant
- Tenant A's drafts, POs, shipments, stock levels, and published products are invisible to Tenant B through any path

---

## 7. Edge Cases

| Scenario | Expected Behavior |
|---|---|
| Importer submits draft, then supplier updates their price | Price in draft reflects extraction-time price; importer sees note that catalog price may have changed |
| PO sent, supplier never confirms | Order stays in `sent` status indefinitely; importer marks as confirmed manually |
| Partial delivery: 60 of 100 units arrive first | First receiving event records 60; second event records remaining 40 when they arrive |
| Damage on all units (100 ordered, 100 damaged) | `qty_in_stock += 0`; `inventory_status` stays `not_ordered`; dispute prompted |
| Retail Only tenant receives goods | Auto-publish fires if enabled; otherwise standard "Ready to Publish" flow |
| Importer sets storefront qty to 0 explicitly | Product shows "Out of Stock" on storefront; not automatically unpublished |

---

*Next: `specs/features/dunning.md`*
