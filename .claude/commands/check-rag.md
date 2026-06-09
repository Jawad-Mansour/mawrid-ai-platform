Run a verification checklist for the RAG Pipeline (Phase 4) and Guardrails (Phase 5).

Check each item below and report PASS / FAIL / NOT_YET_BUILT for each:

**Scope Isolation**
- [ ] Admin chatbot (`enrichment_status = enriched`) finds enriched-but-unpublished products
- [ ] Consumer chatbot (`storefront_status = published`) cannot find any unpublished product
- [ ] Both scopes always filtered by `tenant_id`

**Pipeline Techniques**
- [ ] HyDE: vague query ("something to keep food cold") → hypothetical doc generated → finds refrigerators
- [ ] Multi-Query: 3 alternative phrasings generated → 4 total searches (original + 3 variants)
- [ ] Dense retrieval: HNSW index used (never sequential scan), returns top-20 child chunks
- [ ] Parent-Doc: child chunk IDs mapped to parent chunks — LLM receives parent chunks only
- [ ] GraphRAG: "washing machine" → graph also surfaces dryers from same supplier
- [ ] Cross-encoder: top-20 → top-6, completes in < 150ms on CPU
- [ ] MMR (λ=0.5): 6 near-identical chunks → diverse set after MMR

**Grounded Answers**
- [ ] Every answer cites product IDs from retrieved chunks
- [ ] LLM never invents a specification not present in the top-6 parent chunks
- [ ] "Product not in catalog" → honest "we don't have this" response

**Multilingual**
- [ ] Arabic query finds product with Arabic description
- [ ] French query finds product with French description

**Guardrails (Phase 5)**
- [ ] PII in user message (phone number) → Presidio strips before LLM sees it
- [ ] Jailbreak attempt → blocked by NeMo input rail, LLM not called
- [ ] Hallucinated spec (not in retrieved context) → blocked by NeMo output rail
- [ ] Consumer asks "where is my order?" → NeMo input rail blocks as off-topic

**Operational Queries (Admin Only)**
- [ ] "Which invoices are overdue?" → direct DB query result, no RAG
- [ ] "How many units of X do I have?" → live stock count from DB

**RAGAS Gate**
- [ ] All 4 RAGAS metrics above thresholds in `eval_thresholds.yaml`
- [ ] RAGAS runs nightly (Gate 7) — NOT on every push

**Cross-Tenant**
- [ ] Search as Tenant A → zero results from Tenant B's catalog

**LangSmith Traces**
- [ ] Every LLM call traced with latency, tokens, model ID, retrieved chunks visible

Print a summary line: `X / Y checks PASS`. Flag any FAIL as a blocking issue.
