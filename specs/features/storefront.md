# Feature Spec — Customer-Facing Storefront

*Must be consistent with `specs/constitution.md`. Any conflict: constitution wins.*

---

## 1. What It Does

Provides a configurable e-commerce website where consumers browse published products, add items to a cart, checkout via multiple payment methods, and receive an invoice PDF by email. An AI chatbot grounded in published catalog data answers product questions throughout the store.

**The storefront only shows products the importer has explicitly published.** An enriched product, an in-stock product, and a published product are three different states. Only the last one is visible here.

**Mode gate**: Storefront routes are available only to tenants in `Hybrid` or `Retail Only` mode. `Wholesale Only` tenants receive 403 on all `/store/...` routes.

---

## 2. Who Uses It

| Actor | Action |
|---|---|
| Consumer (guest) | Browses products, searches, adds to cart, checks out, receives invoice by email |
| Consumer (guest) | Asks product questions in the storefront chatbot |
| Importer | Configures published products, sets retail prices, sets storefront quantities |
| Checkout | Processes payment via Stripe / OMT / Whish |
| n8n WF-07 | Consumer order confirmed → generate invoice PDF → send to consumer |
| n8n WF-08 | Payment received → mark invoice paid → stop any active B2C dunning sequences |
| B2C Dunning (Track 4) | Sends reminders with payment links when consumer hasn't paid |

Consumers browse and checkout as **guests in the capstone** — no account creation or login. Consumer accounts with order history and login are Wave 3.

---

## 3. Storefront Pages

### 3.1 — Product Catalog Page

- Displays all products where `storefront_status = published` for the tenant
- Grid layout with product image, name, short description, retail price
- Filters: category, price range, availability (in stock / out of stock)
- Semantic search bar: `GET /store/search?q={query}` → RAG pipeline, published scope
- Search results show term highlighting
- "Out of Stock" badge on products where `storefront_qty = 0` (still visible, not hidden)
- No unpublished product is ever returned in any search or listing

### 3.2 — Product Detail Page

- Full product name, full description (from enrichment), complete specifications (key-value pairs)
- Product image (sourced from enrichment pipeline, stored in MinIO)
- Retail price
- Stock availability indicator
- "Add to Cart" button (disabled when `storefront_qty = 0`)
- "Ask about this product" button → opens storefront chatbot pre-loaded with this product's context
- Related products (GraphRAG-surfaced: same category, same supplier)

### 3.3 — Cart

- Items: product name, unit price, quantity selector, line total
- Quantity selector bounded by `storefront_qty` — consumer cannot order more than available
- Subtotal + any applicable tax
- "Proceed to Checkout" button

### 3.4 — Checkout

- Consumer details: name, email, phone, delivery address
- Payment method selection: Stripe (card), OMT (Lebanese network), Whish (Lebanese network)
- Order summary confirmation before payment
- Payment processed by selected gateway
- On successful payment:
  - Consumer order record created
  - Invoice PDF generated
  - Invoice PDF sent to consumer's email (n8n WF-07)
  - Payment confirmation sent to platform (n8n WF-08 triggers if immediate)
  - `storefront_qty` decremented atomically (no oversell)

### 3.5 — Order Confirmation Page

- Order confirmation number
- Summary of items ordered
- "Invoice has been sent to your email" message
- No account creation prompt (guest checkout, Wave 3 adds accounts)

---

## 4. Language

- **Default**: English
- **Optional**: Arabic (RTL layout), French
- Language preference set at tenant level (tenant's storefront language configuration)
- Consumer order `language` field set to the tenant's configured storefront language at checkout time
- This language field feeds into B2C dunning message language (Track 4)

---

## 5. AI Chatbot (Consumer-Facing)

Powered by the RAG pipeline in published-products scope. Full spec in `specs/features/rag.md`.

- Site-wide chatbot widget, accessible from any storefront page
- Searches only `storefront_status = published` products
- Cannot answer operational questions (orders, invoices, supplier data) — NeMo input rail blocks these
- "Ask about this product" button on product detail page → injects that product's parent chunk directly into the conversation context (skips retrieval)
- Every answer cites the product ID(s) it references
- Multilingual: responds in the same language the consumer writes in

---

## 6. Payment Gateways

| Gateway | Use Case | Region |
|---|---|---|
| Stripe | International card payments | Global |
| OMT | Lebanese domestic network | Lebanon |
| Whish | Lebanese domestic network | Lebanon |

All three implemented via the `PaymentGateway` Protocol in `infra/payments/protocol.py`. Webhook verification required for all three before any payment is recorded.

**Webhook security**: All inbound payment webhooks verified via **HMAC-SHA256** before any processing. Stripe: `Stripe-Signature` header verified against the webhook secret stored in Vault. OMT/Whish: verified per their respective SDKs during Phase 11. Any webhook failing verification is rejected with 400 — no payment recorded, no dunning stopped.

**Payment idempotency**: payment webhook deduplication happens inside the same transaction as invoice marking and storefront qty decrement. Receiving the same webhook twice → second is a no-op.

**Payment link**: unique per invoice. Embedded in B2C dunning reminders. Consumer can pay from the link without navigating the storefront. Link expiry: 30 days from invoice date.

---

## 7. Invoice PDF

Generated automatically on order confirmation (n8n WF-07):
- Tenant business name and logo
- Consumer name, email, delivery address
- Line items: product name, qty, unit price, line total
- Invoice total
- Payment status
- Invoice number (unique per tenant)
- Sent to consumer's email immediately

Invoice PDF stored in MinIO at `{tenant_id}/invoices/{invoice_id}.pdf` and accessible via the admin panel.

---

## 8. Stock Decrement Rules

- `storefront_qty` decremented at the moment of successful payment — not at cart add, not at checkout start
- Decrement is atomic with order creation: both succeed or both roll back
- If two consumers check out simultaneously and only 1 unit remains: first payment succeeds, second receives an out-of-stock error and is not charged
- `storefront_qty = 0` after decrement → product shows "Out of Stock" on storefront, product remains published (not automatically unpublished)
- `qty_in_stock` is NOT decremented at checkout — only `storefront_qty`. The importer controls stock-to-storefront allocation.

---

## 9. Embeddable Widget

- Script loader: `/widget.js`
- **RS256-signed JWT**, 15-minute expiry — importer issues for their registered storefront domain
- Token refresh every 10 minutes (before expiry) handled transparently by the widget script
- Server-side origin check on all widget requests (in addition to CORS)
- Consumer can embed the chatbot on their own website (for Retail Only tenants who have a separate domain)

---

## 10. Acceptance Criteria

### AC-1: Mode Gate
- `Wholesale Only` tenant: all `/store/...` routes return 403

### AC-2: Published-Only Visibility
- All product listings, search results, and chatbot answers only contain products where `storefront_status = published`
- An enriched but unpublished product never appears in any consumer-facing result

### AC-3: Cross-Tenant Isolation
- Consumer browsing Tenant A's storefront cannot see Tenant B's products through any path (search, API, chatbot)

### AC-4: Storefront Search Scope
- `GET /store/search?q=...` returns only published products for the tenant

### AC-5: Checkout Flow
- Consumer checks out → order created → invoice PDF sent to consumer's email
- Consumer not charged if order creation fails (atomic)

### AC-6: No Oversell
- 1 unit remaining → two simultaneous checkouts → exactly one succeeds, one receives out-of-stock error
- `storefront_qty` decremented atomically at payment confirmation

### AC-7: Stock Independence
- Publish 60 of 100 units → consumer buys all 60 → storefront shows "Out of Stock", admin stock shows 40 remaining
- `qty_in_stock` unchanged by consumer purchases (only `storefront_qty` changes)

### AC-8: Payment Idempotency
- Same payment webhook received twice → invoice marked paid once, dunning stopped once, `storefront_qty` decremented once

### AC-9: Invoice PDF
- Invoice PDF generated and emailed within 60 seconds of order confirmation
- PDF contains correct line items, totals, tenant branding, invoice number

### AC-10: Consumer Language
- Consumer order `language` field set to tenant's configured storefront language at checkout
- B2C dunning Track 4 messages sent in this language

### AC-11: "Ask about this product"
- Button on product detail page → chatbot opens with that product's context pre-loaded
- Chatbot answers without triggering a vector search (context injected directly)

### AC-12: Payment Link
- Payment link in B2C dunning email is unique to the invoice
- Link routes to correct payment gateway checkout
- Link functional for 30 days from invoice date

---

## 11. Edge Cases

| Scenario | Expected Behavior |
|---|---|
| Importer unpublishes a product while consumer has it in cart | Cart shows "no longer available" warning; checkout blocked for that item |
| Consumer adds 5 units to cart but only 3 remain in storefront qty | Cart updated to 3 with warning; cannot proceed with 5 |
| Payment gateway times out mid-checkout | Consumer shown error, not charged, order not created; can retry |
| Invoice email bounces | Bounce recorded; invoice PDF still accessible by consumer via order confirmation page (Wave 3 adds account login); importer notified |
| Tenant changes storefront language after existing orders | Existing orders retain original language; new orders use new language |
| Consumer chatbot asked about an unpublished product | No retrieval match; chatbot responds "we don't have that product available" |
| Consumer chatbot asked "where is my order?" | NeMo input rail blocks as off-topic for consumer chatbot |
| Stripe webhook arrives before n8n WF-07 processes it | Payment idempotency guard handles out-of-order processing |

---

*Next: `specs/features/hitl.md`*
