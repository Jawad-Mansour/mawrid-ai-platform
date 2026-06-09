Run a verification checklist for Order Management & Procurement (Phase 3).

Check each item below and report PASS / FAIL / NOT_YET_BUILT for each:

**Order Draft**
- [ ] Products from 2 suppliers → exactly 2 drafts created, one per supplier
- [ ] Submit a draft → status = `submitted`, further edits return 409
- [ ] "Place Order" is a separate explicit action — PO is NOT drafted on submit

**Purchase Order — HITL**
- [ ] French-speaking supplier → PO drafted in French
- [ ] Arabic-speaking supplier → PO drafted in Arabic
- [ ] PO draft written to `hitl_actions` with `action_type = purchase_order_send`
- [ ] No PO reaches a supplier without an approved HITL action
- [ ] Edit flow: modified content is what gets sent, not original draft

**Shipment Tracking**
- [ ] Shipment logged after PO sent → status = `pending_shipment`
- [ ] Status updateable through all stages manually
- [ ] Expected arrival within 3 days → alert visible in admin "Upcoming Arrivals"
- [ ] Two shipments for same PO tracked independently

**Goods Received**
- [ ] Receive 100 ordered, log 20 damaged → `qty_in_stock += 80`
- [ ] Receive 80 of 100 ordered (>5% short) → discrepancy flag on supplier record
- [ ] Receive 98 of 100 ordered (<5% short) → no flag
- [ ] Record >0 damaged → dispute confirmation screen appears
- [ ] Same shipment received twice → second attempt returns 409
- [ ] Mid-transaction crash → full rollback, no partial stock update

**Storefront Publishing**
- [ ] Publish 60 of 100 units → storefront shows 60, admin stock shows 100
- [ ] Consumer buys all 60 → storefront "Out of Stock", admin stock shows 40
- [ ] Retail price always independent of purchase price
- [ ] `Wholesale Only` tenant → all `/store/...` routes return 403

**Cross-Tenant**
- [ ] Tenant A's drafts, POs, shipments, stock invisible to Tenant B

Print a summary line: `X / Y checks PASS`. Flag any FAIL as a blocking issue.
