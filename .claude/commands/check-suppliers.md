Run a verification checklist for Supplier Intelligence & Customer Management (Phase 7).

Check each item below and report PASS / FAIL / NOT_YET_BUILT for each:

**Supplier Record**
- [ ] `POST /procurement/suppliers` creates a supplier with name, email, phone, language (ar/fr/en)
- [ ] `GET /procurement/suppliers` lists suppliers for the tenant
- [ ] `language` field drives PO and dunning message language for this supplier

**Supplier Matching Waterfall**
- [ ] Exact name match → auto-linked, no HITL created
- [ ] TF-IDF cosine ≥ 0.9 → auto-linked, no HITL created
- [ ] Embedding cosine ≥ 0.9 → auto-linked, no HITL created
- [ ] TF-IDF or embedding 0.3–0.9 → HITL action created with `action_type = supplier_match_review`
- [ ] Both below 0.3 → HITL action with "create new supplier?" prompt
- [ ] Every match decision stored with confidence score

**Supplier Scoring (Ridge Regression)**
- [ ] Model loaded from MLflow registry at startup (`random_state=42`)
- [ ] Score computed using 6 features: on_time_delivery_rate, damage_rate, avg_price_vs_market, response_time_hours, catalog_completeness, discrepancy_rate
- [ ] Score recomputed after every goods receiving event linked to this supplier
- [ ] Score stored on supplier record (0–100) and visible in admin panel
- [ ] Supplier with 100% on-time delivery, 0 damage → score near 100
- [ ] Supplier with frequent late deliveries and damage → score near 0

**Reorder Signal**
- [ ] Product `qty_in_stock` drops below `reorder_threshold` + no active PO → HITL reorder draft created
- [ ] Active PO exists for this product → no duplicate reorder draft created
- [ ] Reorder draft in supplier's registered language

**Customer Record**
- [ ] Customer record: name, email, phone, segment (VIP/Regular/At-Risk/Dormant), language, payment_history_score
- [ ] `payment_history_score` updated rolling average after each payment event

**Customer Matching Waterfall**
- [ ] Exact email match → auto-linked (even if name/phone differ)
- [ ] Exact phone match → auto-linked
- [ ] Name TF-IDF ≥ 0.85 → auto-linked
- [ ] Name TF-IDF 0.3–0.85 → HITL review with `action_type = customer_match_review`
- [ ] Name TF-IDF < 0.3 → new customer record auto-created, no HITL

**Segmentation → Tone Classifier**
- [ ] VIP customer → Tone Classifier receives `segment = VIP` → gentle tone for dunning
- [ ] At-Risk customer + late payment → classifier may return firm

**Cross-Tenant**
- [ ] Tenant A's supplier and customer records invisible to Tenant B

Print a summary line: `X / Y checks PASS`. Flag any FAIL as a blocking issue.
