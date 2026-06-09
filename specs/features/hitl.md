# Feature Spec — HITL Approval Center

*Must be consistent with `specs/constitution.md`. Any conflict: constitution wins.*

---

## 1. What It Does

The HITL (Human-In-The-Loop) Approval Center is the single point through which every AI-generated action that contacts an external party or places an order must pass before execution. It is not a notification system — it is a gate. Nothing reaches a supplier, customer, or payment system without an explicit importer decision.

This is a cross-cutting feature. Every feature that generates an outward action (procurement, dunning, supplier management, agentic system) writes to the same `hitl_actions` table and surfaces in the same Approval Center UI.

**The HITL Rule** (from constitution): Every action that sends a message, places an order, or contacts an external party requires explicit importer approval. No exceptions.

---

## 2. Who Uses It

| Actor | Role |
|---|---|
| Importer | Reviews, approves, rejects, and edits all pending actions |
| Communication Agent | Creates draft content for every HITL action |
| Dunning Engine | Creates HITL actions for all track messages |
| Procurement Flow | Creates HITL actions for PO drafts |
| Supplier Intelligence | Creates HITL actions for reorder and outreach drafts |
| Agentic System | Creates HITL actions for any write operation initiated by an agent |

---

## 3. Action Types

Every HITL action has an `action_type` that identifies what will happen when approved. This is the complete list:

| `action_type` | Triggered By | Effect on Approval |
|---|---|---|
| `purchase_order_send` | Procurement: "Place Order" clicked | PO sent to supplier via email |
| `dunning_payables_advance` | Track 1: APScheduler daily check | Payment reminder sent to importer |
| `dunning_disputes_on_demand` | Track 2: Dispute filed by importer | Formal complaint sent to supplier |
| `dunning_receivables_day7` | Track 3: Day 7 from due_date | Reminder sent to wholesale client |
| `dunning_receivables_day14` | Track 3: Day 14 from due_date | Escalated reminder sent to wholesale client |
| `dunning_receivables_day21` | Track 3: Day 21 from due_date | Final notice sent to wholesale client |
| `dunning_b2c_day3` | Track 4: Day 3 from invoice_date | Gentle reminder + payment link sent to consumer |
| `dunning_b2c_day7` | Track 4: Day 7 from invoice_date | Firm reminder + payment link sent to consumer |
| `dunning_b2c_day14` | Track 4: Day 14 from invoice_date | Final notice + payment link sent to consumer |
| `supplier_outreach` | Supplier discovery: outreach to candidate | Outreach email sent to candidate supplier |
| `customer_match_review` | Customer matching: confidence < 0.85 | Importer decides: merge or create new record |
| `supplier_match_review` | Supplier matching: confidence 0.3–0.9 | Importer decides: merge or create new record |
| `fulfillment_notification` | Consumer order: fulfillment update | Fulfillment notification sent to consumer |
| `dispute_letter` | Goods receiving: damage reported | Formal dispute letter sent to supplier |

---

## 4. Action Statuses

```
pending → approved → [action executed]
        → rejected → [draft discarded]
        → edited   → pending (re-enters queue for approval)
        → expired  → [archived, no action taken]
        → cancelled → [archived, no action taken]
```

| Status | Meaning |
|---|---|
| `pending` | Awaiting importer decision |
| `approved` | Importer approved; action is executing or has executed |
| `rejected` | Importer rejected; draft discarded; no action taken |
| `edited` | Importer modified content; action returned to `pending` for re-approval |
| `expired` | No decision within the expiry window; action archived |
| `cancelled` | Cancelled programmatically (e.g., payment received before dunning sends) |

**Transition rules:**
- `pending → approved`: importer clicks Approve
- `pending → rejected`: importer clicks Reject
- `pending → edited`: importer modifies content and saves; status → `pending` (not auto-approved)
- `pending → expired`: expiry timer fires with no importer action
- `pending → cancelled`: system event (payment received, order cancelled) cancels the action

**No direct path from `rejected` or `expired` back to `pending`.** If a rejected action needs to be re-created, the originating flow must re-trigger it (e.g., importer clicks "Place Order" again on a procurement draft).

---

## 5. Expiry Rules

All pending actions expire if not actioned by the importer within the configured window. Expiry is not a failure — it is a decision not to send. The importer can re-trigger the action if needed.

| Action Type | Default Expiry |
|---|---|
| `purchase_order_send` | 72 hours |
| All dunning actions | 48 hours |
| `supplier_outreach` | 72 hours |
| `customer_match_review` | 7 days |
| `supplier_match_review` | 7 days |
| `fulfillment_notification` | 24 hours |
| `dispute_letter` | 72 hours |

Expiry is processed by a background job that checks `hitl_actions WHERE status = 'pending' AND expires_at < NOW()` and sets status to `expired`.

Match review actions (customer_match_review, supplier_match_review) have longer expiry (7 days) because they affect data integrity rather than time-sensitive communications.

---

## 6. Data Model

```python
# hitl_actions table
id:          UUID (primary key)
tenant_id:   UUID (RLS-enforced)
action_type: ActionType enum
status:      HitlStatus enum
payload:     JSONB  # full draft content — varies by action_type (see section 7)
created_at:  datetime
actioned_at: datetime (nullable — set when status transitions from pending)
expires_at:  datetime
created_by:  UUID (agent or system that created the action)
actioned_by: UUID (importer user_id who approved/rejected — nullable until actioned)
```

RLS policy enforces `tenant_id` on every query. An importer can only see and action their own tenant's HITL actions.

---

## 7. Payload Structure by Action Type

Payloads are JSONB. Each action type has a defined schema.

**`purchase_order_send`**:
```json
{
  "supplier_id": "...",
  "supplier_name": "...",
  "supplier_email": "...",
  "language": "ar",
  "draft_content": "...",
  "line_items": [{"product_name": "...", "qty": 10, "unit_price": "450 USD"}],
  "total": "4500 USD",
  "requested_delivery_date": "2026-06-20"
}
```

**Dunning actions** (all tracks, all days):
```json
{
  "invoice_id": "...",
  "recipient_name": "...",
  "recipient_email": "...",
  "language": "fr",
  "tone": "neutral",
  "draft_content": "...",
  "payment_link": "https://..." // Track 4 only
}
```

**`customer_match_review`** and **`supplier_match_review`**:
```json
{
  "incoming": {"name": "...", "email": "...", "phone": "..."},
  "candidates": [
    {"id": "...", "name": "...", "email": "...", "confidence": 0.72}
  ]
}
```

**`dispute_letter`** and **`dunning_disputes_on_demand`**:
```json
{
  "supplier_id": "...",
  "supplier_name": "...",
  "supplier_email": "...",
  "language": "ar",
  "draft_content": "...",
  "po_reference": "PO-...",
  "shipment_id": "...",
  "products_affected": [{"name": "...", "qty_damaged": 20}]
}
```

---

## 8. Approval Center UI

### 8.1 — Queue View

- Lists all `pending` actions for the tenant, sorted by `expires_at` ascending (most urgent first)
- Grouped by `action_type` with counts
- Each card shows: action type label, recipient, draft content preview, time remaining before expiry
- Color-coded urgency: green (>24h), amber (6–24h), red (<6h)
- Bulk approve: select multiple pending actions of the same type → approve all in one click

### 8.2 — Action Card

Each pending action renders as a card with:

- **Action type badge**: readable label (e.g., "Purchase Order", "Dunning Reminder — Day 7")
- **Recipient**: name, email, channel
- **Full draft content**: complete message text (not a preview)
- **Inline edit field**: importer can modify the draft content directly in the card
- **Three action buttons**: Approve / Reject / Edit

### 8.3 — Keyboard Shortcuts (Required Acceptance Criteria)

These shortcuts are active when an action card is focused:

| Key | Action |
|---|---|
| `A` | Approve the focused action |
| `R` | Reject the focused action |
| `E` | Enter edit mode for the focused action's draft content |
| `↑` / `↓` | Move focus to previous / next action card |
| `Esc` | Exit edit mode without saving (cancel edit) |
| `Enter` (in edit mode) | Save edits and return to pending status |

These shortcuts are not optional — they are required acceptance criteria. An importer reviewing 20 HITL actions per day needs to be able to approve them in rapid succession without reaching for the mouse.

### 8.4 — History View

- Shows all actioned actions (approved / rejected / expired / cancelled) with timestamps
- Filterable by action_type, status, date range
- Full audit trail: who created it, who actioned it, what the final content was

---

## 9. Acceptance Criteria

### AC-1: Queue Completeness
- Every external write action (from the complete list in Section 3) appears in the HITL queue before execution
- An action that does not appear in the queue before execution is a critical bug

### AC-2: Approve Flow
- Importer approves → action executes (email sent / PO submitted) → status = `approved` with `actioned_at` and `actioned_by`
- Nothing is sent before approval

### AC-3: Reject Flow
- Importer rejects → draft discarded → no external action taken → status = `rejected`
- Rejected dunning action → sequence continues; next scheduled day still fires

### AC-4: Edit Flow
- Importer edits draft content → status returns to `pending` (not auto-approved)
- Edited content (not the original draft) is what gets sent on subsequent approval

### AC-5: Expiry
- Action not actioned within expiry window → status = `expired`, no action taken
- Expired actions visible in history view

### AC-6: Cancellation
- Payment received → all pending dunning actions for that invoice → status = `cancelled` atomically
- Cancelled actions visible in history view

### AC-7: Keyboard Shortcuts
- `A` key approves the focused card
- `R` key rejects the focused card
- `E` key enters edit mode on the focused card
- `↑` / `↓` navigate between cards
- `Esc` exits edit mode without saving
- `Enter` (in edit mode) saves and returns card to pending
- All shortcuts work without mouse interaction

### AC-8: Cross-Tenant Isolation
- Tenant A's HITL queue is never visible to Tenant B
- RLS enforces this at the database level

### AC-9: Match Review Actions
- `customer_match_review` and `supplier_match_review` show both the incoming record and the candidate match(es) with confidence scores
- Importer can: confirm match (merge), reject match (create new record), or select a different existing record

### AC-10: Bulk Approve
- Select 5 `dunning_b2c_day3` actions → approve all → all 5 executed → all status = `approved`

---

## 10. Edge Cases

| Scenario | Expected Behavior |
|---|---|
| Payment arrives while importer is mid-review of a dunning HITL action | Action cancelled server-side; importer sees "This action was cancelled — invoice paid" on refresh |
| Importer approves an expired action | 409 — action is expired, cannot be approved; shown in history |
| Two importers from same tenant (future multi-user) | First to action wins; second sees "already actioned by [user]" |
| Communication Agent fails to generate draft | HITL action created with `draft_content = null` and an error note; importer can write content manually and approve |
| Importer edits and saves, then edits again before approving | Both edits accepted; final saved content is what gets sent |
| Action payload contains PII | Presidio redacts PII in draft content before displaying in UI; original stored in DB |

---

*Next: `specs/features/agentic.md`*
