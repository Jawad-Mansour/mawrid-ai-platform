# Feature Spec — Supplier Intelligence & Customer Management

*Must be consistent with `specs/constitution.md`. Any conflict: constitution wins.*

---

## 1. What It Does

### Supplier Intelligence
Manages the importer's supplier relationships with structured data, automatic scoring, and AI-assisted outreach. Tracks delivery reliability and quality events. Automates reorder signals when stock falls below threshold.

### Customer Management
Identifies and deduplicates customer records as orders arrive. Segments customers by behavior. Provides the customer context that the Tone Classifier and dunning engine use.

Both features run automatic matching pipelines that route uncertain matches to HITL review rather than silently making a wrong decision.

---

## 2. Who Uses It

| Actor | Role |
|---|---|
| Importer | Reviews supplier scores, manages supplier records, files disputes |
| Importer | Reviews HITL match queues (customer and supplier matching) |
| Importer | Triggers supplier discovery (stretch goal) |
| Supplier Scorer (ML) | Ridge regression model scoring suppliers 0–100 |
| Stock Monitor Agent | Monitors inventory levels, signals reorder when threshold crossed |
| Communication Agent | Drafts reorder requests and supplier outreach (all HITL-gated) |
| n8n WF-11 | Stock below threshold → reorder signal → HITL draft |

---

## 3. Supplier Intelligence

### 3.1 — Supplier Record

Each supplier record contains:
- Name, contact email, contact phone
- `language` field: `ar` | `fr` | `en` (determines language of all outgoing communications)
- Country and region
- Product categories they supply
- `reorder_threshold` — configurable per product linked to this supplier
- Performance history (delivery events)
- Current supplier score (0–100)
- Active dunning sequences (Track 1 and Track 2)

---

### 3.2 — Supplier Matching

When a new supplier name appears (e.g., from an uploaded price list), the system attempts to match it against existing supplier records before creating a duplicate.

**Matching waterfall** (in order):

| Step | Method | Threshold | Action |
|---|---|---|---|
| 1 | Exact name match | 1.0 | Auto-link, no HITL |
| 2 | TF-IDF cosine similarity | ≥ 0.9 | Auto-link, no HITL |
| 3 | Embedding cosine similarity | ≥ 0.9 | Auto-link, no HITL |
| 4 | TF-IDF or embedding | 0.3 – 0.9 | HITL review (`action_type = supplier_match_review`) |
| 5 | TF-IDF and embedding | < 0.3 | HITL action with "create new supplier?" prompt — importer confirms before record is created |

**HITL match review**: Importer sees the incoming name alongside the candidate match(es) with similarity scores. Options: confirm match, reject match (create new supplier), or select a different existing supplier.

**Confidence score stored**: every auto-link and manual decision is stored with its confidence score for audit and model improvement.

---

### 3.3 — Supplier Scoring

**Model**: Ridge Regression. Produces a score 0–100.

**Inputs** (6 features, all derived from delivery events):

| Feature | Description |
|---|---|
| `on_time_delivery_rate` | Fraction of deliveries arriving by expected date |
| `damage_rate` | `qty_damaged / qty_received` across all deliveries |
| `avg_price_vs_market` | Average price ratio vs market (1.0 = at market; > 1.0 = above market) |
| `response_time_hours` | Average hours from PO sent to supplier confirmation |
| `catalog_completeness` | Fraction of product rows with all required fields filled |
| `discrepancy_rate` | Fraction of deliveries where received qty < ordered qty by > 5% |

**Scoring formula** (deterministic, used as ground truth for training):
```
score = 100
score -= (1 - on_time_delivery_rate) × 40
score -= damage_rate × 30
score -= max(0, avg_price_vs_market - 1.0) × 15
score -= (response_time_hours / 168) × 10
score -= (1 - catalog_completeness) × 5
score = clamp(score, 0, 100)
```
Delivery reliability is the most heavily weighted factor (40 points).

**Score recomputed** after every goods receiving event linked to this supplier.

**Output**: Score stored on supplier record. Visible in supplier detail view as a bar and numeric score.

**Registry**: Model registered in MLflow. Loaded from registry at app startup.

**Reproducibility**: `random_state=42` on training.

---

### 3.4 — Reorder Signal (Stock Monitor)

**Trigger**: Stock Monitor Agent runs on schedule. For each product with a configured `reorder_threshold`: if `qty_in_stock` falls below the threshold AND the product has no active pending PO, a reorder signal fires.

**Flow**:
1. Stock Monitor signals low stock for product X at supplier Y
2. Communication Agent drafts a reorder request to supplier Y in their registered language
3. HITL action created (`action_type = purchase_order_send`)
4. Importer reviews, approves → PO sent
5. n8n WF-11 orchestrates this flow

**Guard**: if there is already an active PO for this product (status: `pending_hitl`, `sent`, or `confirmed`), no reorder signal fires.

---

### 3.5 — Supplier Discovery (Stretch Goal)

*Attempt after all core features are stable. Not a hard requirement for capstone completion.*

**Flow**:
1. Importer specifies a product need (type, category, price target)
2. Discovery Agent searches external sources (web search via MCP)
3. Agent scores each candidate using scoring criteria
4. Ranked shortlist presented in admin panel
5. Importer selects candidates for outreach
6. Communication Agent drafts outreach in candidate's likely language → HITL → sent
7. n8n WF-20 orchestrates this flow (future workflow, pre-built)

---

## 4. Customer Management

### 4.1 — Customer Record

Each customer record contains:
- Name
- Email address
- Phone number
- `segment`: `VIP` | `Regular` | `At-Risk` | `Dormant`
- `language`: `ar` | `fr` | `en` (used for dunning message language)
- `payment_history_score`: 0.0 – 1.0 (rolling average, updated on each payment event)
- Order history
- Active dunning sequences (Track 3 or Track 4)

**Segmentation rule** (applied periodically, not real-time):
- **VIP**: high order frequency + high order value + `payment_history_score ≥ 0.8`
- **Regular**: consistent ordering, payment on time
- **At-Risk**: recent drop in order frequency or delayed payments
- **Dormant**: no orders in configurable window (default: 90 days)

Segmentation drives dunning tone (passed to Tone Classifier) and dunning track selection (B2B vs B2C).

---

### 4.2 — Customer Matching

When a new order arrives (name, email, phone from checkout), the system attempts to identify if this is an existing customer before creating a duplicate record.

**Matching waterfall** (in order, first match wins):

| Step | Method | Score | Action |
|---|---|---|---|
| 1 | Exact email match | 1.0 | Auto-link — email is the definitive identity signal |
| 2 | Exact phone match | 0.95 | Auto-link |
| 3 | Name TF-IDF similarity | ≥ 0.85 | Auto-link |
| 4 | Name TF-IDF similarity | 0.3 – 0.85 | HITL review (`action_type = customer_match_review`) |
| 5 | Name TF-IDF similarity | < 0.3 | Auto-create new customer record, no HITL |

**HITL match review**: Importer sees the incoming customer details (name, email, phone from order) alongside the candidate match. Options: confirm match (merge into existing record), reject match (create new customer).

**Confidence score stored**: every match decision recorded with confidence score.

**No match found at all**: new customer record created automatically.

---

### 4.3 — Payment History Score

Updated on every payment event for this customer:
```
new_score = (old_score * (n - 1) + payment_outcome) / n
```
Where `payment_outcome = 1.0` if paid on time, `0.0` if paid after dunning, `0.5` if paid late but before dunning.

`n` = total number of invoices for this customer.

---

## 5. Data Model Notes

- `Supplier`: id, tenant_id, name, email, phone, language, score, created_at
- `DeliveryEvent`: id, tenant_id, supplier_id, po_id, shipment_id, qty_ordered, qty_received, qty_damaged, expected_date, received_date
- `SupplierScore`: id, tenant_id, supplier_id, score, computed_at (history of scores)
- `MatchResult`: id, tenant_id, entity_type (supplier/customer), incoming_name, matched_id (nullable), confidence, method, decision (auto/hitl), decided_at
- `Customer`: id, tenant_id, name, email, phone, segment, language, payment_history_score
- `Segment` enum: `VIP` | `Regular` | `At-Risk` | `Dormant`

---

## 6. Acceptance Criteria

### AC-1: Supplier Matching Waterfall
- Exact name → auto-linked, no HITL
- TF-IDF/embedding ≥ 0.9 → auto-linked, no HITL
- TF-IDF/embedding 0.3–0.9 → HITL action created with both candidates visible
- Below 0.3 → HITL action with "create new supplier?" prompt — importer confirms before record created
- Every match decision stored with confidence score

### AC-2: Supplier Score
- Supplier with 100% on-time delivery, 0 damage → score near 100
- Supplier with frequent late deliveries and damage → score near 0
- Score recomputed after each goods receiving event

### AC-3: Reorder Signal
- `qty_in_stock` drops below `reorder_threshold` + no active PO → HITL reorder draft created
- Active PO already exists → no duplicate reorder draft
- HITL reorder draft in supplier's registered language

### AC-4: Customer Matching Waterfall
- Same email → auto-linked (even if name and phone differ)
- Same phone, different email → auto-linked
- Name TF-IDF ≥ 0.85, no email/phone match → auto-linked
- Name TF-IDF 0.3–0.85 → HITL review with both records visible
- Name TF-IDF < 0.3 → new customer record auto-created, no HITL

### AC-5: Segmentation Inputs to Dunning
- VIP customer → Tone Classifier receives `segment = VIP` → gentle tone
- At-Risk customer + late payment → classifier may return firm

### AC-6: Payment History Score
- First payment on time → score = 1.0
- First payment after dunning → score = 0.0
- Mixed history → rolling average

### AC-7: Cross-Tenant
- Tenant A's supplier and customer records invisible to Tenant B

---

## 7. Edge Cases

| Scenario | Expected Behavior |
|---|---|
| Same supplier appears under two slightly different name spellings across two documents | Matching waterfall catches it; if confidence 0.3–0.9, HITL review; importer merges |
| Customer changes email between orders | Old email auto-links to old record; new order with new email → name/phone waterfall; if < 0.85 name match → HITL |
| Supplier score computed with only 1 delivery event | Score computed but flagged as low-confidence (few data points); shown with sample size |
| Stock drops below threshold while goods are already in transit | No reorder signal — active PO guard prevents duplicate |
| Importer rejects a customer HITL match | New customer record created; the incoming order is linked to the new record |

---

*Next: `specs/features/rag.md`*
