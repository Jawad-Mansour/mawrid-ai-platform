List all HITL-gated actions and their current state. Use this to audit the HITL queue during development and to verify HITL coverage is complete.

**Step 1 — Coverage audit (development check)**

Verify that every action type below has a corresponding HITL record creator in the codebase:

| action_type | Expected creator location |
|---|---|
| `purchase_order_send` | `core/procurement/services.py` — triggered on "Place Order" |
| `dunning_payables_advance` | `core/dunning/tracks.py` — Track 1, APScheduler |
| `dunning_disputes_on_demand` | `core/dunning/tracks.py` — Track 2, dispute filing |
| `dunning_receivables_day7` | `core/dunning/tracks.py` — Track 3, Day 7 |
| `dunning_receivables_day14` | `core/dunning/tracks.py` — Track 3, Day 14 |
| `dunning_receivables_day21` | `core/dunning/tracks.py` — Track 3, Day 21 |
| `dunning_b2c_day3` | `core/dunning/tracks.py` — Track 4, Day 3 |
| `dunning_b2c_day7` | `core/dunning/tracks.py` — Track 4, Day 7 |
| `dunning_b2c_day14` | `core/dunning/tracks.py` — Track 4, Day 14 |
| `supplier_outreach` | `agents/specialists/discovery_agent.py` — supplier discovery outreach |
| `customer_match_review` | `core/customers/services.py` — matching waterfall |
| `supplier_match_review` | `core/suppliers/services.py` — matching waterfall |
| `fulfillment_notification` | `core/storefront/services.py` — order fulfillment |
| `dispute_letter` | `core/procurement/services.py` — damage dispute |

For each, run: `grep -r "action_type.*<type>" backend/app/` and report FOUND / MISSING.

**Step 2 — Live queue status (when services are running)**

Query: `SELECT action_type, status, COUNT(*) FROM hitl_actions GROUP BY action_type, status ORDER BY action_type;`

Report the table. Highlight any `pending` actions that are approaching expiry.

**Step 3 — Keyboard shortcut verification**

Confirm the frontend HITL Approval Center implements:
- [ ] `A` key → Approve focused action
- [ ] `R` key → Reject focused action
- [ ] `E` key → Enter edit mode on focused action
- [ ] `↑` / `↓` → Navigate between action cards
- [ ] `Esc` → Exit edit mode without saving
- [ ] `Enter` (in edit mode) → Save and return to pending

Print: `X / 14 action types found in codebase` and `X / 6 keyboard shortcuts implemented`.
