# Feature Spec — NLP Search & RAG Pipeline

*Must be consistent with `specs/constitution.md`. Any conflict: constitution wins.*

---

## 1. What It Does

Provides two distinct AI-powered search and chat experiences:

1. **Internal catalog search** — the importer queries all enriched products regardless of storefront or inventory status. Used for browsing, comparing, and selecting products to order.
2. **Consumer storefront chatbot** — consumers ask questions and get grounded, cited answers about published products only.

The pipeline uses six retrieval techniques in sequence. Every answer is grounded in retrieved catalog data. No answer is generated from model memory.

Guardrails (NeMo + Presidio) are added in Phase 5 and inherited by this pipeline. This spec describes the pipeline itself; guardrail behavior is described in `specs/constitution.md` (hard constraint) and Phase 5 of the plan.

---

## 2. Who Uses It

| Actor | Scope | What They Can Ask |
|---|---|---|
| Importer (admin chatbot) | All enriched products | Product questions, operational questions (orders, invoices, stock, dunning), complex multi-step queries |
| Consumer (storefront chatbot) | Published products only | Product questions, availability, specifications |

The admin chatbot is the importer's primary intelligence interface. The consumer chatbot is scoped to published products only — it cannot answer about unpublished products, orders, invoices, or any operational data.

---

## 3. Pipeline — Exact Execution Order

```
User Query
    │
    ▼
[Presidio PII Strip]         ← strips phone numbers, emails, names before any LLM call
    │
    ▼
[NeMo Input Rail]            ← jailbreak / off-topic / prompt injection detection; blocks before LLM
    │
    ├── [HyDE]               ← LLM generates hypothetical product description → embed → extra search vector
    │
    └── [Multi-Query]        ← LLM generates 3 query variants → 4 parallel vector searches (original + 3)
            │
            ▼
    [RRF Merge]              ← Reciprocal Rank Fusion: merges HyDE + 3 multi-query result lists → ranked candidates
            │
            ▼
    [Dense Retrieval]        ← pgvector HNSW search on child chunks, top-20 results
                               Scope filter applied HERE (see section 4)
                               Always: AND tenant_id = {current_tenant_id}
            │
            ▼
    [Parent-Doc Mapping]     ← replace each child chunk ID with its parent chunk (1024 tokens)
            │
            ▼
    [GraphRAG]               ← traverse networkx knowledge graph from top hits:
                               product → supplier edges
                               product → category edges
                               category → parent category edges
                               Adds structurally related products not reachable by vector distance
            │
            ▼
    [Cross-Encoder Reranking] ← ms-marco-MiniLM-L-6-v2, runs over top-20 candidates → reranked top-6
                                Must complete in < 150ms on CPU
            │
            ▼
    [MMR λ=0.5]              ← Maximal Marginal Relevance: removes near-duplicate chunks, keeps diverse top-6
            │
            ▼
    [LLM Prompt Assembly]
        system:  strict grounding prompt from prompts/rag_system.yaml
                 "Answer only from the provided context. Cite product IDs. Do not invent specifications."
        context: top-6 parent chunks with product IDs
        user:    original query (after PII strip)
            │
            ▼
    LLM generates answer (GPT-4o)
            │
            ▼
    [NeMo Output Rail]       ← self-check: does response match retrieved context?
                               hallucination guard: no specs not present in top-6 chunks
            │
            ▼
    Response with citations (product_id references)
```

---

## 4. Scope Filter

Applied at the Dense Retrieval step. Determines which products can appear in results.

| Context | SQL Filter | Who Uses It |
|---|---|---|
| Admin chatbot (importer) | `WHERE enrichment_status = 'enriched' AND tenant_id = ?` | Importer browsing all enriched products |
| Consumer chatbot (storefront) | `WHERE storefront_status = 'published' AND tenant_id = ?` | Consumer on storefront |
| Catalog search endpoint | `WHERE enrichment_status = 'enriched' AND tenant_id = ?` | Importer browsing catalog |
| Storefront search endpoint | `WHERE storefront_status = 'published' AND tenant_id = ?` | Consumer searching storefront |

**Invariant**: `tenant_id` filter is always present. A query that returns another tenant's product is a cross-tenant violation (CI hard fail).

**Invariant**: An unpublished product can never appear in a consumer-facing result, regardless of how the query is phrased.

---

## 5. Retrieval Techniques

### 5.1 — Dense Retrieval (pgvector HNSW)

- Embedding model: `paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions, loaded once at startup
- Searches on child chunks (256-token precision units)
- HNSW index on `product_embeddings` — never a sequential scan
- Returns top-20 child chunk results per search vector

### 5.2 — Parent-Document Chunking

- Each product produces two embedding types stored in `product_embeddings`:
  - **Child chunk** (`chunk_type = 'child'`): ~256 tokens — precise, used for vector matching
  - **Parent chunk** (`chunk_type = 'parent'`): ~1024 tokens — full context, delivered to LLM
- After dense retrieval returns child chunk IDs → map each to its parent chunk
- LLM context window receives parent chunks only

### 5.3 — HyDE (Hypothetical Document Embedding)

- LLM generates a hypothetical product listing that would answer the query
- The hypothetical listing is embedded → used as an additional search vector
- Closes the vocabulary gap between a user's natural language query and product catalog text

### 5.4 — Multi-Query Expansion

- LLM generates 3 alternative phrasings of the original query
- Each variant is embedded and searched independently (4 total searches: original + 3 variants)
- All 4 result lists merged via RRF into a single ranked candidate list

### 5.5 — RRF (Reciprocal Rank Fusion)

- Merges multiple ranked result lists into one without requiring score normalization
- Formula: `RRF_score(d) = Σ 1 / (k + rank_i(d))` where k=60
- Handles cases where the same product appears in multiple result lists

### 5.6 — Cross-Encoder Reranking

- Model: `cross-encoder/ms-marco-MiniLM-L-6-v2`, loaded locally at startup
- Takes the top-20 from RRF merge
- Scores each (query, chunk) pair directly — more accurate than cosine similarity alone
- Returns top-6 reranked results
- **Latency constraint**: must complete in < 150ms on CPU

### 5.7 — GraphRAG (Knowledge Graph Traversal)

- Knowledge graph: `networkx` in-memory per tenant, built from catalog data
- Edge types stored in `graph_edges` table: `same_category`, `same_supplier`, `related`
- Traversal: starting from the top vector hits, traverse 1 hop to find:
  - Products from the same supplier
  - Products in the same category
  - Products in parent/child categories
- Graph results added to the candidate pool before reranking
- Graph is per-tenant — traversal never crosses tenant boundaries

### 5.8 — MMR (Maximal Marginal Relevance)

- λ = 0.5 (balance between relevance and diversity)
- Applied to the final 6 candidates after cross-encoder reranking
- Removes near-identical chunks (high cosine similarity to already-selected chunks)
- Ensures diverse product coverage reaches the LLM context

---

## 6. Admin Chatbot Routing

The importer-facing chatbot handles three query types, routed by the 3-tier intent classifier:

| Query Type | Example | Routing |
|---|---|---|
| **Product question** | "describe the LG OLED TV features" | RAG pipeline over enriched catalog |
| **Operational question** | "which invoices are overdue?", "what's the status of PO-123?", "how many units of X do I have?" | Direct API/DB query — no RAG, no LLM generation |
| **Complex multi-step** | "which low-stock products have the highest-scoring supplier?" | Supervisor agent with multiple tools |

Operational queries are answered from live database state, not from retrieved chunks. This is faster, cheaper, and more accurate than RAG for structured data questions.

**Per-product "Ask about this product" button**: on both admin product detail page and storefront product page. Opens chatbot pre-loaded with that product's full context (its parent chunk injected directly into the conversation, skipping retrieval).

---

## 7. Tracing

Every LLM call in the pipeline is traced in LangSmith:
- Query received (after PII strip)
- HyDE hypothetical generated
- Multi-query variants generated
- Dense search results (top-20 child chunks)
- Parent chunks after mapping
- Graph traversal results
- Cross-encoder scores
- MMR final selection
- LLM prompt assembled
- LLM response generated
- NeMo output rail result
- Total latency, token count, model ID

---

## 8. RAGAS Evaluation

**Metrics evaluated** (all four):
- `context_precision` — are the retrieved chunks relevant to the query?
- `context_recall` — does the retrieved set contain the information needed to answer?
- `faithfulness` — does the answer stay within what the chunks contain?
- `answer_relevancy` — does the answer address the question?

**Dataset**: 20 question-answer pairs from the real enriched catalog (`rag_questions.json`).

**Thresholds**: set in `eval_thresholds.yaml`. CI gate fails if any metric drops below threshold.

**When it runs**: Nightly on master branch (Gate 7). Not on every push — RAGAS requires real LLM calls.

**Cross-tenant RAGAS**: eval queries for Tenant A never return Tenant B context — verified in the eval suite.

---

## 9. Acceptance Criteria

### AC-1: Scope Isolation
- Admin chatbot finds enriched-but-unpublished products
- Consumer chatbot cannot find any unpublished product, regardless of query phrasing
- Both always filtered by `tenant_id`

### AC-2: Cross-Tenant Zero Leakage
- Search as Tenant A → zero results from Tenant B's catalog in any scope
- Included as one of the 15 cross-tenant CI red-team attack vectors

### AC-3: Multilingual
- Arabic query finds product with Arabic description
- French query finds product with French description
- Vocabulary gap bridged: "something to keep food cold" finds refrigerators

### AC-4: Parent Chunks to LLM
- Search matches on child chunk → parent chunk (full context) delivered to LLM, not the child chunk

### AC-5: Cross-Encoder Improves Ranking
- 20 candidates where the most relevant is not ranked first by dense search → after reranking, most relevant is first
- Reranking completes in < 150ms on CPU

### AC-6: GraphRAG Finds Related Products
- Search "washing machine" → vector finds specific model → graph also surfaces dryers from same supplier and other washing machines from same category

### AC-7: MMR Prevents Duplicates
- 6 near-identical chunks (same product, slightly different excerpts) → after MMR → diverse set covering different products

### AC-8: Grounded Answers
- Every answer cites product IDs from retrieved chunks
- LLM never invents a specification not present in the top-6 parent chunks
- "Product not in catalog" → honest "we don't have this" response

### AC-9: Operational Queries (Admin Only)
- "Which invoices are overdue?" → direct DB query result, correct data, no RAG
- "How many units of X do I have?" → live stock count from DB

### AC-10: RAGAS Gate
- All 4 RAGAS metrics above thresholds in `eval_thresholds.yaml`
- CI gate active and failing when any metric drops

### AC-11: LangSmith Traces
- Every LLM call traced with latency, tokens, model ID, retrieved chunks visible in LangSmith

---

## 10. Edge Cases

| Scenario | Expected Behavior |
|---|---|
| Query about a product not in the catalog at all | LLM responds "I don't have information about that product" — no hallucination |
| Query in a mix of Arabic and English | Embedding model handles mixed-language queries natively |
| Consumer asks about an operational matter ("where is my order?") | Rejected by NeMo input rail as off-topic for consumer chatbot |
| Admin chatbot asked about another tenant's products | Scope filter + tenant_id filter returns zero results; LLM responds "not found" |
| All 6 parent chunks are about the same product | MMR diversifies; LLM still generates a focused answer on that product |
| Cross-encoder returns very low scores for all 20 candidates | Top-6 still returned (relative ranking), response hedged with low-confidence phrasing |
| "Ask about this product" button used on unpublished product (admin view) | Parent chunk injected directly; chatbot answers from that context; scope filter not applied in direct-inject mode |

---

*Next: `specs/features/storefront.md`*
