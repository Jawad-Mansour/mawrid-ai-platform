#!/usr/bin/env bash
# Feature: Test reset — empty the catalog + order data for ONE tenant so the
# Enrichment and Order pages can be tested from scratch. Keeps suppliers,
# customers, invoices and dunning so the rest of the app stays populated.
#
# Usage:  bash scripts/reset_catalog.sh [email]
#         (defaults to demo@mawrid.ai)
set -euo pipefail

EMAIL="${1:-demo@mawrid.ai}"
PSQL() { docker compose exec -T postgres psql -U mawrid -d mawrid "$@"; }

TID=$(PSQL -tAc "select tenant_id from users where email='$EMAIL' limit 1;" | tr -d '[:space:]')
if [ -z "$TID" ]; then echo "‼ no tenant for $EMAIL"; exit 1; fi
echo "→ clearing catalog + orders for $EMAIL ($TID)"

PSQL -v ON_ERROR_STOP=1 -q <<SQL
delete from graph_edges    where tenant_id='$TID';
delete from product_chunks where tenant_id='$TID';
delete from outbox         where tenant_id='$TID';
delete from review_queue   where tenant_id='$TID';
delete from purchase_orders where tenant_id='$TID';
delete from order_drafts   where tenant_id='$TID';
delete from products       where tenant_id='$TID';
delete from documents      where tenant_id='$TID';
SQL

echo "✓ done. Remaining for this tenant:"
PSQL -tAc "select '  products='||count(*) from products where tenant_id='$TID';
           select '  documents='||count(*) from documents where tenant_id='$TID';
           select '  suppliers (kept)='||count(*) from suppliers where tenant_id='$TID';"
echo "→ In the browser, clear the in-page basket if it shows stale items (localStorage key: mawrid-basket)."
