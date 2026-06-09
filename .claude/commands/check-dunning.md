Run a verification checklist for the Dunning Engine (Phase 6).

Check each item below and report PASS / FAIL / NOT_YET_BUILT for each:

**Track 1 — B2B Payables**
- [ ] Invoice with `due_date` = today + 3 → reminder drafted and placed in HITL queue
- [ ] Invoice already paid → no reminder drafted
- [ ] HITL `action_type = dunning_payables_advance`
- [ ] Channel: email (not WhatsApp — deferred to Wave 1)

**Track 2 — B2B Disputes**
- [ ] Importer files dispute → HITL draft created in supplier's language
- [ ] Arabic supplier → letter in Arabic; French supplier → letter in French
- [ ] HITL `action_type = dunning_disputes_on_demand`
- [ ] Track 2 returns 403 for `Retail Only` tenants (mode gate: Hybrid + Wholesale Only only)
- [ ] Track 2 is NOT stopped by payment (disputes are about quality, not payment)

**Track 3 — B2B Receivables**
- [ ] Invoice created → Day 7: HITL draft appears
- [ ] Day 14: second draft appears (escalated)
- [ ] Day 21: third draft appears (final notice)
- [ ] Trigger dates calculated from `due_date` (due_date = invoice_date + payment_terms_days)
- [ ] Tone selected by classifier before each draft

**Track 4 — B2C Collections**
- [ ] Day 3: gentle reminder with payment link → HITL
- [ ] Day 7: firm reminder with payment link → HITL
- [ ] Day 14: final notice with payment link → HITL
- [ ] Payment link in every B2C message is unique to the invoice
- [ ] Track 4 returns 403 for `Wholesale Only` tenants
- [ ] Channel: email + SMS in capstone (WhatsApp deferred to Wave 1)

**Tone Classifier**
- [ ] `days_overdue = 5` → gentle (Priority 1)
- [ ] `customer_segment = VIP, days_overdue = 30` → gentle (Priority 2)
- [ ] `segment = At-Risk, days_overdue = 20, previous_dunning_count = 3` → firm (Priority 3)
- [ ] `payment_history_score = 0.9, days_overdue = 12, segment = Regular` → gentle (Priority 4)
- [ ] `days_overdue = 12, segment = Regular, score = 0.5` → neutral (default)

**Payment Auto-Stop**
- [ ] Payment webhook received → invoice marked paid + all pending drafts cancelled in one transaction
- [ ] Same webhook received twice → second event is a no-op
- [ ] Track 2 is NOT stopped by payment

**HITL on Every Message**
- [ ] No dunning message ever sent without an approved HITL action
- [ ] Importer rejects a draft → message discarded, sequence continues to next scheduled day

**Cross-Tenant**
- [ ] Tenant A's invoices and dunning sequences invisible to Tenant B

Print a summary line: `X / Y checks PASS`. Flag any FAIL as a blocking issue.
