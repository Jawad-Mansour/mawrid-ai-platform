# Feature Spec — Agentic AI System

*Must be consistent with `specs/constitution.md`. Any conflict: constitution wins.*

---

## 1. What It Does

Provides the intelligence backbone for the platform. A Supervisor agent orchestrates five specialist agents to handle complex, multi-step tasks. A three-tier intent classifier routes incoming requests — fast fixed workflows handle the ~80% of traffic with known intent; the Supervisor handles the ~20% of complex or novel requests.

Every write action initiated by any agent goes through the HITL gate (`specs/features/hitl.md`). Agents propose — the importer decides.

LangGraph manages agent state with Redis-backed checkpointing. No progress is lost if an agent is interrupted.

---

## 2. Who Uses It

| Actor | Role |
|---|---|
| Importer (admin chatbot) | Sends queries that the intent classifier routes to the Supervisor or a fixed workflow |
| Supervisor Agent | Orchestrates specialist agents for complex multi-step tasks |
| Specialist Agents | Execute bounded tasks within their defined scope |
| MCP Servers | Provide tool access to agents (search, catalog, email dispatch, shipment) |
| LangSmith | Traces every agent step, tool call, reasoning, and latency |
| Redis (AsyncRedisSaver) | Persists agent state across steps; survives restarts |

---

## 3. Intent Classifier (3-Tier Cascade)

All incoming messages are classified before routing. The classifier runs in order — the first tier that produces a confident result stops the cascade.

```
Tier 1: TF-IDF + Logistic Regression  (~80% of traffic handled here)
    ↓ (low confidence or unknown intent)
Tier 2: DistilBERT fine-tuned → ONNX Runtime  (< 100ms on CPU)
    ↓ (still low confidence)
Tier 3: GPT-4o zero-shot  (fallback, used for complex/novel queries)
```

### 3.1 — Intent Classes

| Intent | Example Queries |
|---|---|
| `product_search` | "do you have Samsung TVs?", "show me fridges under $500" |
| `order_status` | "what's the status of my order?", "where is PO-123?" |
| `stock_check` | "how many units of X do I have?", "what's my current inventory?" |
| `shipment_status` | "where is my LG shipment?", "when does the container arrive?" |
| `invoice_query` | "which invoices are overdue?", "show me unpaid B2B invoices" |
| `dunning_action` | "stop dunning on invoice 456", "manually trigger Track 3" |
| `complex_task` | "find me a new appliance supplier and draft outreach", multi-step requests |
| `out_of_scope` | "what's the weather?", "write me a poem", off-topic queries |

**Routing by intent:**

| Intent | Route |
|---|---|
| `product_search` | RAG pipeline (enrichment catalog scope) |
| `order_status`, `stock_check`, `shipment_status`, `invoice_query` | Direct DB query — no LLM, no RAG |
| `dunning_action` | Direct service call to DunningService |
| `complex_task` | Supervisor Agent |
| `out_of_scope` | NeMo input rail blocks; polite rejection returned |

### 3.2 — Training Data

**Tier 1 and Tier 2 training**: 1200+ labeled synthetic examples from `intent_training_data.json`, generated in Phase 0.4.
- Minimum 150 examples per class
- 80/20 train/test split
- Hard negatives included (near-identical phrases with different intents)
- Arabic / French / English examples mixed throughout

**Tier 2 model**: DistilBERT fine-tuned on the training set, exported to ONNX for CPU inference. Inference < 100ms. Registered in MLflow.

**Eval gate**: Intent classifier F1 macro ≥ 0.85 on the held-out test set. Runs nightly (CI Gate 8). Test set used: `intent_test_set.json` (20% held-out split).

---

## 4. Agent Topology

### Supervisor Agent

**Role**: Central coordinator. Reads `current_task` from agent state, determines which specialist to invoke next, and assembles final response.

**Pattern**: Supervisor routes to specialists one at a time. It does not call all specialists simultaneously — it reasons about which specialist is needed at each step.

**State**: LangGraph state graph. Persisted in Redis via `AsyncRedisSaver`.

**Thread ID**: `{tenant_id}:{user_id}:{session_uuid}` — unique per user session, scoped to tenant.

**Termination**: Supervisor terminates when:
- All required specialist work is complete and a response is ready
- A HITL action has been created (execution pauses for importer approval)
- Maximum step count reached (safety limit)

**Bulk operation guard**: if a task involves > 10 products (e.g., "re-enrich all 50 LG products"), the Supervisor pauses and returns the count to the importer for explicit confirmation before dispatching any jobs. This prevents accidental large-batch operations.

---

### Extraction Specialist

**Role**: Processes supplier documents — CV layout detection + BERT NER extraction.

**Bounded execution**: Processes one document at a time. Submits enrichment jobs to ARQ queue. Returns `job_id` for status tracking.

**Tools**: Document structure detection, NER model inference.

**Does not**: Enrich products (that's the Enrichment Specialist). Does not write to the storefront.

---

### Enrichment Specialist

**Role**: Enriches a single product with descriptions, specifications, and images.

**Bounded execution**: Maximum **5 reasoning steps** per product. Hard stop at 5 — no exceptions.

**Tools** (via MCP):
- Web search
- Product image search

**ToolError handling**: Caught and handled. Agent continues with partial data — does not crash.

**Does not**: Modify price, SKU, or quantity. Does not publish to storefront.

**LangSmith trace**: every tool call, result, and reasoning step logged.

---

### Communication Agent

**Role**: Drafts all outgoing messages — purchase orders, dunning messages of all types, supplier outreach, dispute letters, fulfillment notifications.

**HITL-only**: Communication Agent never sends anything directly. Every draft it produces is written to `hitl_actions` table and waits for importer approval. The agent's job ends when the HITL action is created.

**Language**: always uses the recipient's registered language (supplier `language` field, customer `language` field).

**Tools** (via MCP):
- Email dispatch (write-only to HITL queue — does not actually send)
- Catalog read (to include product details in messages)

**Message types handled**:
- Purchase orders (all supplier languages)
- Dunning reminders (all 4 tracks, all days)
- Supplier discovery outreach
- Supplier dispute letters
- Fulfillment notifications
- Reorder requests

---

### Stock Monitor Agent

**Role**: Watches inventory levels. Signals reorder when a product's `qty_in_stock` falls below its configured `reorder_threshold` and there is no active PO for that product.

**Tools** (via MCP):
- Catalog read (stock levels, reorder thresholds)
- Order read (check for active POs)

**Output**: Signals reorder need → Supervisor routes to Communication Agent to draft reorder request → HITL.

**Does not**: Place orders directly. Does not modify stock levels.

---

### Supplier Discovery Agent (Stretch Goal)

*Attempt after all core features are stable. Not a hard requirement for capstone completion.*

**Role**: Researches potential new suppliers based on importer's stated need (product type, price target, region).

**Tools** (via MCP):
- Web search
- Catalog read (to understand existing supplier relationships)

**Output**: Ranked shortlist of supplier candidates with scoring rationale → presented in admin panel for importer review → importer selects candidates → Communication Agent drafts outreach → HITL.

---

## 5. MCP Servers

Agents access external capabilities through Model Context Protocol servers. Each MCP server is a defined tool set — agents cannot access capabilities outside their registered MCP servers.

| MCP Server | Tools Provided | Agents That Use It |
|---|---|---|
| `mcp_search` | Web search, product image search | Enrichment Specialist, Supplier Discovery |
| `mcp_catalog` | Catalog read, stock levels, product details | Communication Agent, Stock Monitor, RAG |
| `mcp_email_dispatch` | Write to HITL queue (no direct send) | Communication Agent |
| `mcp_shipment` | Shipment status read | Supervisor (for operational queries) |

All MCP server tool calls are traced in LangSmith.

---

## 6. LangGraph Checkpointing

**Checkpointer**: `AsyncRedisSaver` from `langgraph-checkpoint-redis`

**Thread ID format**: `{tenant_id}:{user_id}:{session_uuid}`

**Redis key namespace**: Agent checkpoints stored under `mawrid:{tenant_id}:checkpoint:{thread_id}` — the tenant_id prefix enforced at the key level prevents cross-tenant Redis key collision regardless of checkpointer internals.

**Isolation**: Thread IDs are tenant-scoped. Tenant A's agent state is never accessible by Tenant B's agents.

**Persistence**: Agent state (messages, tool results, current step) is serialized to Redis after every node execution. If the backend restarts mid-agent-run, the next request with the same `thread_id` resumes from the last checkpoint.

**Session UUID**: New UUID generated per conversation session. The importer starts a fresh conversation by obtaining a new `session_uuid`.

**Version pinning**: `langgraph` and `langgraph-checkpoint-redis` pinned to exact minor version (e.g., `langgraph==0.2.x`). Breaking API changes observed between minor versions — float to latest is not safe.

---

## 7. Guardrails

Applied to all LLM calls in the agent system. Configured in Phase 5, active for all subsequent phases.

**Presidio** (runs before every LLM call):
- Strips PII (phone numbers, emails, names, national IDs) from all inbound messages
- LLM never sees raw PII
- Original text preserved in DB

**NeMo Guardrails** (runs on input and output):
- **Input rail**: jailbreak detection, off-topic detection, prompt injection detection
- **Output rail**: self-check (does response match retrieved context?), hallucination guard (no specs not in context)
- Blocked input → polite rejection, LLM not called
- Blocked output → response not returned, fallback message sent

Both are middleware applied once — all agents inherit the protection without per-agent configuration.

---

## 8. LangSmith Tracing

Every agent run produces a trace in LangSmith:

- Intent classifier tier used and result
- Supervisor routing decision at each step
- Each specialist invoked: which MCP tools called, tool inputs, tool outputs
- Reasoning steps (for ReAct agents)
- LLM calls: prompt, response, model ID, token count, latency
- HITL action created: action_type, payload summary
- Total agent run latency
- Whether guardrails blocked any step

Traces are per-tenant-scoped in LangSmith (tenant_id included as metadata on every trace).

---

## 9. Acceptance Criteria

### AC-1: Classifier Routing
- Known simple intent (`stock_check`) → direct DB query, no Supervisor invoked
- Complex multi-step intent → Supervisor invoked
- Out-of-scope → rejected by NeMo input rail before any agent runs
- Arabic / French queries classified correctly (multilingual classifier)

### AC-2: Classifier Accuracy
- Intent F1 macro ≥ 0.85 on held-out test set (CI Gate 8 — nightly)

### AC-3: Supervisor Orchestration
- "Find me a new appliance supplier and draft outreach" → Supervisor invokes Supplier Discovery → then Communication Agent → HITL action created
- Complex task completes without manual intervention beyond HITL approval

### AC-4: Enrichment Specialist Bounded
- 5-step limit enforced — agent never exceeds 5 reasoning steps per product
- ToolError handled gracefully — agent continues with partial data

### AC-5: Communication Agent — HITL Only
- Communication Agent never sends directly — every message goes through `hitl_actions`
- Draft content in supplier's / customer's registered language

### AC-6: Stock Monitor Signal
- Stock drops below `reorder_threshold` + no active PO → HITL reorder draft created
- Active PO exists → no duplicate draft

### AC-7: Checkpointing
- Agent interrupted mid-run → on next request with same `thread_id` → resumes from last checkpoint
- Thread ID scoped to `tenant_id` — Tenant A's checkpoint never accessible by Tenant B

### AC-8: Guardrails Active
- Jailbreak attempt → blocked by NeMo input rail before any LLM called
- Hallucinated spec (not in retrieved context) → blocked by NeMo output rail
- PII in user message → Presidio strips before LLM sees it

### AC-9: LangSmith Traces
- Every agent run has a trace in LangSmith
- Trace includes: intent classification result, Supervisor routing, specialist steps, tool calls, HITL action created
- Trace metadata includes `tenant_id`

### AC-10: Agent Trajectory Snapshots
- 20 golden agent trajectories (defined intent → expected node sequence)
- CI Gate 6: agent trajectory snapshot test fails if any of the 20 takes a different path

---

## 10. Edge Cases

| Scenario | Expected Behavior |
|---|---|
| Intent classifier Tier 1 low confidence → Tier 2 invoked → Tier 2 also low confidence | Falls through to Tier 3 (GPT-4o zero-shot); latency acceptable for this rare path |
| Enrichment Specialist tool fails on all 5 steps | Saves product as `status = partial` with all fields null; does not crash or retry indefinitely |
| Communication Agent fails to draft (LLM error) | HITL action created with `draft_content = null` and error flag; importer can write content manually |
| Agent interrupted mid-Supervisor run (backend restart) | Next request with same `thread_id` resumes; Supervisor re-reads state from Redis checkpoint |
| Importer sends a follow-up message to a completed agent conversation | New `session_uuid` issued; fresh conversation started |
| Two simultaneous requests with same `thread_id` | LangGraph checkpoint serializes access; second request waits for first to complete |
| Supplier Discovery stretch goal not attempted | Core system ships without it; all other agents fully functional |

---

*SpecKit complete. All 9 specs written. Verify all against `resources/understanding_brainstorm/approved.md` before Phase 1 begins.*
