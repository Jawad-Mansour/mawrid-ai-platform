# Mawrid — Remaining-fixes implementation spec (agent prompt)

You are implementing the **final 7 items** of a feedback batch on the Mawrid platform (a
multi-tenant AI ops platform for importers/distributors). Work **one phase at a time**, verify
each phase's gates before moving on, and **never ship mock/fake data** unless a phase explicitly
says "dummy data is acceptable". Below: global rules, then each phase with exact files, changes,
gotchas, and acceptance criteria.

---

## 0. Global rules (read first, apply to every phase)

**Commands** (run from repo root, always `uv`, never pip/poetry):
- `uv run ruff check .` — lint (Gate 1)
- `uv run mypy --strict .` — types (Gate 2)
- `uv run pytest backend/tests/unit/` — unit tests, LLM mocked (Gate 3)
- Frontend typecheck: `cd frontend && npm run typecheck`
- Run a single migration: `MSYS_NO_PATHCONV=1 docker compose exec -T backend /opt/venv/bin/alembic upgrade head`
- Restart backend after backend code changes: `docker compose restart backend` (no `--reload` in this stack). Frontend has Vite HMR (no restart).

**Known false positive:** `frontend/src/components/Markdown.tsx` reports TS2307/7006 on the host
(react-markdown types resolve only inside Docker). Ignore *only* those; every other tsc error is real.

**Conventions (hard):**
- Every Python file starts with the header block: `Feature/Layer/Module/Purpose/Depends/HITL`.
  Every TS file starts with `// Feature: / // Layer: / // Purpose: / // API:`.
- Layer rules: `core/` imports nothing from `infra/ api/ agents/`. `api/` does routing only.
- **HITL**: any action that sends a message / places an order / contacts an external party must
  create a `hitl_actions` row and wait for approval. Never send directly.
- **No mock data** (except where a phase says dummy is OK).
- Multi-tenant: every query is tenant-scoped (repos inherit `TenantRepository._tenant_filter`).
- Frontend theming: colours come from CSS vars — use `rgb(var(--accent))`, `text-ink`,
  `text-ink-soft`, `text-ink-faint`, `border-line`, `bg-bg-card`, `.card`, `.chip`, `.btn-gold`,
  `.btn-ghost`, `.input`, `.metric-num`, `StatusBadge`, `SectionTitle`, `Card`, `Spinner` from
  `@/components/ui`. Icons: `lucide-react`. Animations: `framer-motion`.
- Migrations: Alembic only. Current head is **0017**. New migration → `revision = "0018"`,
  `down_revision = "0017"`, filename `backend/alembic/versions/20260619_0018_<name>.py`. Mirror the
  style of `20260617_0016_supplier_relationship.py`.
- **Per-phase acceptance = all of: ruff clean · mypy --strict clean · `pytest backend/tests/unit/`
  green · frontend `tsc` clean (minus Markdown.tsx) · the phase's behaviour verified live.**

**Reference endpoints that already exist** (do not recreate):
- `/api/v1/assistant/chat` (advisor / command_center), `/api/v1/search/catalog` (semantic),
  `/api/v1/procurement/shipments`, `/api/v1/procurement/shipments/{id}/receive|receipt-pdf|receipt-email|dispute`,
  `/api/v1/procurement/stock`, `/api/v1/dunning/sequences`, `/api/v1/network/outreach|find-email`,
  `/api/v1/suppliers`, `/api/v1/network/conversations`, `/api/v1/auth/google/*` (Connect Gmail).
- Inbound replies are auto-detected via `app/infra/email/gmail.py::gmail_poll_and_ingest` and
  `app/infra/email/inbound.py::ingest_supplier_reply` (comprehension lives in
  `app/infra/email/comprehend.py`, returns `intent, wants_changes, change_summary, arrival_date,
  promised_payment_date, min_order_qty, summary`).

---

## Phase A — Specialized Business Advisor (note 23-advisor)

**Goal:** the Advisor must answer like a professional import/distribution consultant, not a generic
chatbot. Do NOT add a Hugging Face model — keep GPT-4o; specialization comes from persona +
frameworks + grounding (the grounding already exists in `_snapshot`).

**File:** `backend/app/api/assistant.py` (the `else` branch in `chat()` where `body.role == "advisor"`).

**Change:** replace the advisor `system` prompt with an expert persona + decision frameworks:
- Persona: "senior operations & finance advisor for a Lebanon/MENA importer-distributor."
- Always reason across these levers when relevant: **cash flow & working capital, supplier
  reliability/concentration risk, inventory turns & dead stock, pricing/margin, dunning/collections,
  procurement timing vs lead times.**
- Output format: a 1-line **recommendation**, then **2–4 concrete steps**, then a short **why**
  (grounded in the live snapshot numbers). Be specific, cite the tenant's real figures from the
  snapshot, never invent numbers. Keep it tight (no filler).
- Keep `lang` multilingual and keep the live `{summary}` injected.
- Keep `temperature` for advisor at ~0.3.

**Also:** the command-center→advisor chain already exists (the "Ask the advisor about this" button in
`frontend/src/pages/Intelligence.tsx` resends the grounded answer with role=advisor). Verify it still
works; no change needed unless broken.

**Acceptance:** ask the advisor "what should I focus on this week?" with real data present — it cites
real counts and gives a recommendation + steps + why. mypy/ruff/tsc/pytest green.

---

## Phase B — Received-goods report PDF + dispute message (note 18)

**Files:** `frontend/src/pages/inventory/Receive.tsx`, backend `backend/app/api/procurement.py`
(`shipment_receipt_pdf` / `_build_receipt` / `shipment_dispute`), `backend/app/infra/documents/receipt_pdf.py`.

1. **PDF download "didn't work":** in `Receive.tsx::downloadReport` the call is
   `apiClient.get('/procurement/shipments/{id}/receipt-pdf', { responseType: 'blob' })`. Verify the
   backend endpoint returns a real `application/pdf` (reportlab) with `Content-Disposition: attachment`.
   Gotchas to check: (a) the endpoint must be reachable **after** the receipt is confirmed (the
   `goods_received` row must exist — `_build_receipt` needs it); if you call it before confirming,
   return a clear 422, and in the UI only show the button after `received === true` (already the case).
   (b) Ensure `apiClient` base URL + auth header are attached for blob requests (they are; just confirm).
   Add a friendly error toast if the blob response is actually JSON/an error (check `res.data.type`).

2. **Dispute message wording:** the dispute is filed from `Receive.tsx::fileDispute` →
   `POST /procurement/shipments/{id}/dispute`. Improve the drafted claim so it is a **professional,
   specific claim email**: it must (a) name the PO, (b) list each short/damaged line with ordered vs
   received vs damaged quantities, (c) reference the attached goods-received report, (d) request a
   remedy (credit note / replacement) with a response deadline, (e) stay courteous. The draft is an
   LLM call in the dunning/dispute service (`dispute_letter` HITL type) — update the prompt template
   `backend/prompts/communication/dispute_letter.yaml` to enforce that structure, and make sure the
   discrepancy details (`damage_description`, per-line shorts/damages) are passed into the prompt.

**Acceptance:** confirm receipt with a damaged/short line → Download report PDF opens a valid PDF →
File dispute creates a `dispute_letter` HITL action whose body names the PO + the exact discrepancies +
a remedy request. Gates green.

---

## Phase C — Stock Levels UX/logic (note 20)

**Files:** `frontend/src/pages/inventory/Stock.tsx`, backend `GET /procurement/stock` (in
`backend/app/api/procurement.py`).

**Logic (backend, confirm/extend):** `/procurement/stock` should return every in-stock product with:
`product_id, product_name, sku, qty_in_stock, storefront_qty, reorder_threshold, retail_price,
supplier_names, low (bool = qty_in_stock <= reorder_threshold)`. Add a derived `reserved =
storefront_qty` and `available = qty_in_stock - storefront_qty` if not present.

**UX (frontend):** make Stock Levels genuinely useful:
- Top summary chips: # products, # low-stock, units on storefront, total stock value (Σ qty×price).
- Table/cards sorted **low-stock first**, each row showing: name + SKU, **in-stock / reserved /
  available** (3 clear numbers), an **editable reorder threshold** (PATCH `/products/{id}/threshold`),
  the **supplier**, and actions: **Restock** (POST `/products/{id}/restock`) and a **"Reorder from
  {supplier}"** button that deep-links to Create Order pre-filled for that product/supplier
  (`/procurement?product={id}` or the basket store).
- A low-stock row is visually flagged (amber). Keep the "Demand Signals (coming soon)" note.

**Gotcha:** don't fabricate sales-velocity numbers (Demand Signals stays "coming soon"). Only show
real fields. Empty state when no stock.

**Acceptance:** receive goods → those products appear in Stock with correct in-stock/reserved/available;
editing the threshold persists; low items are flagged; Restock and Reorder work. Gates green.

---

## Phase D — Dunning ↔ report linkage + reply tracking (note 21)

**Files:** `backend/app/api/procurement.py` (dispute), `backend/app/api/dunning.py`,
`frontend/src/pages/dunning/SupplierDunning.tsx`.

1. **Linkage:** a dispute filed from Received Goods (`dispute_letter` HITL) must appear in
   **Supplier Dunning → Disputes** and carry a reference back to the PO/shipment/report (store
   `po_id`/`shipment_id` in the HITL payload; show them on the dispute card with a link to the PO
   thread and a "Download report" action).
2. **Reply tracking:** replies to dunning/dispute emails are already auto-detected by the Gmail/IMAP
   poller (matched by sender→supplier→latest PO, or outreach thread). Verify a reply to a dunning
   email surfaces as a `supplier_reply` notification and threads onto the supplier's PO/outreach
   conversation. If a dunning email has no PO context, ensure the reply still records a
   `supplier_reply` notification linking to `/dunning`. No new infra — just confirm the matching path
   and add the `/dunning` link where missing.

**Acceptance:** file a dispute → it shows in Disputes with PO/report links → approve to send →
reply to it → the reply is detected and shown. Gates green.

---

## Phase E — Shipment arrival: Lebanese time + status stepper (note 17)

**Files:** migration `0018`, `backend/app/infra/db/models/order.py` (Shipment),
`backend/app/api/procurement.py` (shipment create/update + arrival-set), `frontend/src/pages/inventory/Shipments.tsx`,
`backend/app/infra/email/inbound.py::ingest_supplier_reply` (already sets arrival from comprehension).

1. **Exact time (Beirut):** `shipments.expected_arrival_date` is a `Date` (no time). Add migration
   **0018** adding nullable `expected_arrival_at TIMESTAMP WITH TIME ZONE`. Add the column to the
   `Shipment` model. When the importer sets/edits the arrival in `Shipments.tsx`, allow a **date + time**
   input; store it in `expected_arrival_at`. When the comprehension extracts an `arrival_date` (and a
   time if present), set `expected_arrival_at` too. **Always display arrival in Lebanese time**:
   `new Intl.DateTimeFormat('en-GB',{ dateStyle:'medium', timeStyle:'short', timeZone:'Asia/Beirut' }).format(new Date(at))`
   with a "Beirut time" hint. Keep `expected_arrival_date` for the date-only calendar/scheduler logic.
2. **Creative status buttons:** replace the flat `pending shipment / shipped / in transit / at customs
   / arrived` chips with a **horizontal stepper/timeline**: each stage is a node with an icon
   (Package/Ship/Truck/Building2/CheckCircle2), completed stages filled with `rgb(var(--accent))`, the
   current stage pulsing (framer-motion), future stages muted; clicking a node advances the shipment
   status (PATCH the shipment status). Animated connector line fills up to the current stage.

**Gotcha:** the scheduler `_run_arrival_check` queries `expected_arrival_date` — keep that column
populated (date part) so notifications still fire. mypy: the new column is `Mapped[datetime | None]`.

**Acceptance:** supplier agrees a date in an email → arrival auto-fills (date shown in Beirut time);
importer can set an exact time; the status stepper is a clear animated timeline and advances on click.
Migration applies; gates green.

---

## Phase F — "Ask for catalogue" status chip (note 3)

**File:** `frontend/src/pages/Suppliers.tsx` (the supplier card; it already shows a conversation
message-count chip from `/network/conversations`).

**Change:** on each supplier card show an explicit outreach **status chip** derived from the
conversation record: **"Catalogue requested"** (we sent, awaiting reply) / **"Replied"** (last
message is inbound) / nothing if no outreach. Use `conversation.last_direction` and
`message_count` (already fetched in `convoBy`). Keep the existing click-through to the thread. The
"Ask for catalogue" action already creates the HITL + conversation — just surface its state so it
persists visibly on the card and in HITL Approvals (HITL already shows it).

**Acceptance:** click "Ask for catalogue" on a supplier → a "Catalogue requested" chip appears and
persists on the card; when a reply is logged/detected it flips to "Replied". Gates green (frontend
only).

---

## Phase G — Richer 3D login/signup (final)

**Files:** `frontend/src/components/AuthScene.tsx` (the theme-aware 3D scene used by
`pages/auth/AuthShell.tsx` and `ChooseMode.tsx`).

**Change:** elevate the existing scene (orbital rings + tumbling glass cubes + accent aura) without
images: add depth and life — e.g. a parallax starfield/particle layer that drifts with subtle mouse
movement, a soft volumetric light sweep, a gentle 3D tilt on the central core, and richer glow on the
focused workspace card. Keep it **theme-aware** (`rgb(var(--accent) / a)`), **performant** (GPU
transforms / framer-motion, no layout thrash), and **hidden on small screens** where it already is.
Respect `prefers-reduced-motion`. Don't reintroduce the half-image idea (the user rejected it).

**Acceptance:** login + Create-Workspace pages feel premium and animated, recolour per theme, smooth
on a mid laptop, and don't block the form. tsc clean.

---

## Final verification (after all phases)

1. `uv run ruff check .` → clean
2. `uv run mypy --strict .` → clean
3. `uv run pytest backend/tests/unit/` → all green
4. `cd frontend && npm run typecheck` → clean except Markdown.tsx
5. Apply migration: `MSYS_NO_PATHCONV=1 docker compose exec -T backend /opt/venv/bin/alembic upgrade head`
6. `docker compose restart backend`; confirm `GET http://localhost:8000/health` → 200.
7. Live-verify each phase's acceptance criteria.
8. Reset demo data when handing back for testing: `bash scripts/reset_all.sh`.

**Commit:** one commit per phase (or one squashed commit), conventional message, **do NOT add a
`Co-Authored-By` trailer**. Never commit secrets (`keys.txt`, `resources/`, `output.txt` are
git-ignored). Then push.
