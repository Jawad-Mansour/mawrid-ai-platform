# Feature Spec — Dunning Engine

*Must be consistent with `specs/constitution.md`. Any conflict: constitution wins.*

---

## 1. What It Does

The dunning engine manages all money flows across the business simultaneously — automatically, persistently, and in the correct language — without the importer manually drafting a single message. Every drafted message requires HITL approval before it is sent.

**Six financial directions, four tracks:**

| Direction | Who Owes Whom | Track |
|---|---|---|
| Importer owes Supplier | Supplier invoiced importer | **Track 1 — B2B Payables** |
| Supplier owes resolution | Importer disputes quality / delivery | **Track 2 — B2B Disputes** |
| Wholesale client owes Importer | Importer invoiced a store / client | **Track 3 — B2B Receivables** |
| Consumer owes Store | Consumer placed order, hasn't paid | **Track 4 — B2C Collections** |

Payment received on any invoice → **auto-stops** all active dunning sequences for that invoice immediately.

All four tracks are active in the capstone. Dunning does not require the recipient to have a platform account — only their contact details (email, phone) stored in their supplier or customer record.

---

## 2. Who Uses It

| Actor | Role |
|---|---|
| Importer | Reviews and approves all drafted messages via HITL Approval Center |
| Communication Agent | Drafts all dunning messages in the correct language and tone |
| Tone Classifier (ML) | Selects tone (gentle / neutral / firm) for Tracks 3 and 4 |
| n8n | WF-09 through WF-15 trigger all 4 tracks on schedule |
| APScheduler | Daily check for Track 1 (payables) — 3-day advance window |
| Payment webhooks | Auto-stop dunning sequences when payment is confirmed |

---

## 3. Track Details

### Track 1 — B2B Payables (Importer Pays Supplier)

**Trigger**: Supplier invoice exists with `due_date` 3 days from today. APScheduler runs the daily check.

**Purpose**: Remind the importer to pay their supplier before the due date. Not a receivables reminder — the importer is the debtor here.

**Sequence**:
| Day | Action |
|---|---|
| due_date - 3 | Communication Agent drafts advance payment reminder → HITL → sent to importer (email) |

**Tone**: Always professional. Tone classifier not used for Track 1.

**Channel**: Email in capstone. WhatsApp in Wave 1.

**Auto-stop**: If the importer marks the invoice as paid before the reminder fires, the sequence is cancelled.

**HITL action_type**: `dunning_payables_advance`

---

### Track 2 — B2B Disputes (Importer Disputes Supplier)

**Trigger**: Importer manually files a dispute — either from the damage confirmation screen after goods receiving, or from the supplier detail page.

**Purpose**: Formally document and communicate a complaint (damaged goods, short delivery, quality issue) to the supplier in their language.

**Sequence**: On-demand (single message per dispute filing, not a scheduled escalation).

**Content**: Formal complaint letter in the supplier's registered language (AR / FR / EN). Content includes: product name, quantity, PO reference, shipment ID, damage description (provided by importer in the dispute form).

**Tone**: Always formal. Tone classifier not used for Track 2.

**Channel**: Email in capstone. WhatsApp in Wave 1.

**HITL action_type**: `dunning_disputes_on_demand`

**Mode gate**: `Hybrid` and `Wholesale Only` tenants only. `Retail Only` tenants do not have B2B Disputes (per DEC-005). Route returns 403 for Retail Only mode.

---

### Track 3 — B2B Receivables (Wholesale Client Pays Importer)

**Trigger**: Invoice issued to a wholesale client (store owner / business) where `status = unpaid` and days overdue from `due_date` reaches trigger thresholds.

**Trigger dates are calculated from `due_date`**, not from `invoice_date`. For B2B receivables, `due_date = invoice_date + payment_terms_days` (NET 30 / NET 60, from the client's contact record). Days-overdue = `today - due_date`.

**Sequence**:
| Day overdue (from due_date) | Action |
|---|---|
| Day 7 | Communication Agent drafts reminder → Tone Classifier selects tone → HITL → sent to client (email) |
| Day 14 | Escalated reminder → Tone Classifier selects tone (may increase) → HITL → sent |
| Day 21 | Final notice → Tone Classifier → HITL → sent |

**Tone selection**: Tone Classifier (gentle / neutral / firm) runs per message. Inputs: customer segment, payment history score, overdue amount, previous dunning count.

**Tone rules** (priority-ordered, first match wins):
1. `days_overdue ≤ 7` → gentle (regardless of segment)
2. `customer_segment = VIP` → gentle (relationship preservation)
3. `(segment = At-Risk OR Dormant) AND days_overdue ≥ 14 AND previous_dunning_count ≥ 2` → firm
4. `payment_history_score ≥ 0.8` → gentle (historically reliable)
5. Default → neutral

**Recipient**: wholesale client tracked as a contact record. No portal login required. Email sent using email address on their customer record.

**Channel**: Email in capstone. WhatsApp in Wave 1.

**HITL action_types**: `dunning_receivables_day7`, `dunning_receivables_day14`, `dunning_receivables_day21`

---

### Track 4 — B2C Collections (Consumer Pays Store)

**Trigger**: Consumer order placed, invoice generated, `status = unpaid`. Days from `invoice_date` reaches trigger thresholds.

**Sequence**:
| Day from invoice_date | Action |
|---|---|
| Day 3 | Gentle reminder with payment link → HITL → sent to consumer (email) |
| Day 7 | Firm reminder with payment link → HITL → sent |
| Day 14 | Final notice with payment link → HITL → sent |

**Payment link**: unique per invoice, embedded in every B2C message. Links to the Stripe / OMT / Whish checkout for that invoice.

**Tone**: Determined by Tone Classifier, same logic as Track 3. Day 3 defaults gentle. Escalates based on classifier.

**Recipient**: consumer's email from the order record. No account required.

**Channel**: Email in capstone. SMS as secondary (capstone). WhatsApp in Wave 1.

**HITL action_types**: `dunning_b2c_day3`, `dunning_b2c_day7`, `dunning_b2c_day14`

**Mode gate**: Track 4 only active for tenants in `Hybrid` or `Retail Only` mode. `Wholesale Only` tenants cannot trigger B2C collections.

---

## 4. Tone Classifier

**Type**: Classical ML — Ridge Regression / Gradient Boosted Classifier, 3 classes.

**Training data**: 240 labeled synthetic examples (`tone_training_data.json`), 80 per class (gentle / neutral / firm), generated in Phase 0.3.

**Inputs** (5 features):
- `days_overdue` (integer)
- `customer_segment` (VIP / Regular / At-Risk / Dormant)
- `overdue_amount` (float)
- `payment_history_score` (0.0 – 1.0)
- `previous_dunning_count` (integer)

**Output**: class label — `gentle` | `neutral` | `firm`

**Labeling rules** (deterministic, priority-ordered, used for ground truth generation):
1. Priority 1 → gentle: `days_overdue ≤ 7`
2. Priority 2 → gentle: `customer_segment = VIP`
3. Priority 3 → firm: `(segment = At-Risk OR Dormant) AND days_overdue ≥ 14 AND previous_dunning_count ≥ 2`
4. Priority 4 → gentle: `payment_history_score ≥ 0.8`
5. Default → neutral

**Class balancing**: SMOTE applied at training time to handle class imbalance.

**Reproducibility**: `random_state=42` on all training operations.

**Registry**: Model registered in MLflow after training. Loaded from registry at app startup.

---

## 5. Payment Auto-Stop

**Trigger**: Payment confirmation event received via webhook (Stripe / OMT / Whish) or manual "Mark as Paid" action.

**Rule**: All active dunning sequences for the paid invoice are stopped immediately and irreversibly.

**Idempotency**: If the same payment webhook is received twice (at-least-once delivery), the second event is a no-op — the invoice is already marked paid, the sequences are already stopped.

**Atomicity**: Invoice marked paid + all sequences stopped + all pending HITL actions cancelled in a single transaction.

**What "stopped" means per track**:
- Track 1: Payables reminder, if not yet sent, is cancelled
- Track 2: No auto-stop (disputes are about quality/delivery, not payment)
- Track 3: Day 7/14/21 messages not yet sent are cancelled; any pending HITL action is cancelled
- Track 4: Day 3/7/14 messages not yet sent are cancelled; any pending HITL action is cancelled

---

## 6. n8n Workflow Mapping

| Workflow | Track | Description |
|---|---|---|
| WF-09 | Track 1 | Dunning Trigger B2B Payables → Communication Agent → HITL → send |
| WF-10a | Track 4 | B2C Day 3 → Communication Agent → HITL → send |
| WF-10b | Track 4 | B2C Day 7 → Communication Agent → HITL → send |
| WF-10c | Track 4 | B2C Day 14 → Communication Agent → HITL → send |
| WF-11 | — | Stock below threshold (triggers procurement, not dunning) |
| WF-12 | Track 3 | B2B Receivables Day 7 → Communication Agent → HITL → send |
| WF-13 | Track 3 | B2B Receivables Day 14 → Communication Agent → HITL → send |
| WF-14 | Track 3 | B2B Receivables Day 21 → Communication Agent → HITL → send |
| WF-15 | Track 2 | B2B Dispute Filed → Communication Agent → HITL → send |
| WF-08 | All | Payment Received → stop all active sequences for invoice |

---

## 7. Data Model Notes

- `DunningSequence`: links an invoice to the active track, records which days have fired and their HITL status
- `Invoice`: includes `invoice_date`, `due_date`, `status` (unpaid / paid / reconciled), `invoice_type` (b2b / b2c)
- `ToneLabel` enum: `gentle` | `neutral` | `firm`
- `Track` enum: `1` | `2` | `3` | `4`
- Every HITL action created by dunning references the `invoice_id` — payment auto-stop uses this to cancel pending actions

---

## 8. Acceptance Criteria

### AC-1: Track 1 Fires Correctly
- Invoice with `due_date` = today + 3 → reminder drafted and placed in HITL queue
- Invoice already paid → no reminder drafted

### AC-2: Track 2 On-Demand
- Importer files dispute → HITL draft created in supplier's language
- Arabic supplier → letter in Arabic; French supplier → letter in French

### AC-3: Track 3 Timeline
- Invoice created → Day 7: HITL draft appears → Day 14: second draft → Day 21: third draft
- Each draft uses `due_date` as the reference date, not `invoice_date`
- Tone selected by classifier before each draft

### AC-4: Track 4 Timeline + Payment Link
- Consumer order unpaid → Day 3: gentle reminder with payment link → Day 7: firm → Day 14: final
- Payment link in every B2C message is unique to the invoice and functional
- Track 4 returns 403 for `Wholesale Only` tenants

### AC-5: Tone Classifier
- `days_overdue = 5` → gentle (Priority 1 fires regardless of other features)
- `customer_segment = VIP, days_overdue = 30` → gentle (Priority 2)
- `segment = At-Risk, days_overdue = 20, previous_dunning_count = 3` → firm (Priority 3)
- `payment_history_score = 0.9, days_overdue = 12, segment = Regular` → gentle (Priority 4)
- `days_overdue = 12, segment = Regular, score = 0.5` → neutral (default)

### AC-6: Payment Auto-Stop
- Payment webhook received → invoice marked paid + all pending drafts cancelled in one transaction
- Same webhook received twice → second event is no-op
- Track 2 is NOT stopped by payment (disputes are independent of payment)

### AC-7: HITL on Every Message
- No dunning message is ever sent without an approved HITL action
- Importer rejects a draft → message discarded, sequence continues to next scheduled day

### AC-8: Mode Gating
- `Wholesale Only` tenant: Track 4 returns 403 on any B2C dunning route

### AC-9: Cross-Tenant Isolation
- Tenant A's invoices and dunning sequences are never visible to Tenant B

---

## 9. Edge Cases

| Scenario | Expected Behavior |
|---|---|
| Day 7 HITL draft pending when payment arrives | Draft cancelled atomically with invoice paid marking |
| Importer rejects Day 7 draft | Sequence continues; Day 14 fires on schedule regardless |
| Invoice has both B2B and B2C dunning sequences | Each track operates independently |
| Wholesale client pays after Day 21 final notice | Invoice marked paid; no further messages |
| Dispute filed on an invoice that is also in Track 3 | Both operate independently — Track 2 is about quality, Track 3 is about payment |
| Communication Agent fails to draft a dunning message | HITL action created with `status = draft_failed`; importer notified; can write manually |
| Day 7 HITL not actioned by importer before Day 14 fires | Day 14 fires regardless; both are in HITL queue simultaneously |

---

*Next: `specs/features/supplier.md`*
