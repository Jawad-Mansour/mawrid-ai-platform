#!/usr/bin/env bash
# Feature: Full test reset — wipe ALL operational data for ONE tenant so every
# feature (catalog enrichment, suppliers, ordering, shipments, dunning, storefront)
# can be tested from a blank slate. KEEPS the tenant + user so you stay logged in.
#
# Usage:  bash scripts/reset_all.sh [email]
#         (defaults to demo@mawrid.ai)
set -euo pipefail

EMAIL="${1:-demo@mawrid.ai}"
PSQL() { docker compose exec -T postgres psql -U mawrid -d mawrid "$@"; }

TID=$(PSQL -tAc "select tenant_id from users where email='$EMAIL' limit 1;" | tr -d '[:space:]')
if [ -z "$TID" ]; then echo "no tenant for $EMAIL"; exit 1; fi
echo "-> wiping ALL data for $EMAIL ($TID)  [keeping login]"

# children -> parents, one transaction
PSQL -v ON_ERROR_STOP=1 -q <<SQL
begin;
delete from consumer_order_items   where tenant_id='$TID';
delete from consumer_orders        where tenant_id='$TID';
delete from storefront_orders      where tenant_id='$TID';
delete from goods_received         where tenant_id='$TID';
delete from supplier_delivery_events where tenant_id='$TID';
delete from shipments              where tenant_id='$TID';
delete from purchase_orders        where tenant_id='$TID';
delete from order_drafts           where tenant_id='$TID';
delete from dunning_sequences      where tenant_id='$TID';
delete from invoices               where tenant_id='$TID';
delete from customers              where tenant_id='$TID';
delete from graph_edges            where tenant_id='$TID';
delete from product_chunks         where tenant_id='$TID';
delete from outbox                 where tenant_id='$TID';
delete from review_queue           where tenant_id='$TID';
delete from products               where tenant_id='$TID';
delete from documents              where tenant_id='$TID';
delete from suppliers              where tenant_id='$TID';
delete from hitl_actions           where tenant_id='$TID';
delete from notifications          where tenant_id='$TID';
commit;
SQL

echo "done. Remaining for this tenant:"
PSQL -tAc "select '  products='||count(*) from products where tenant_id='$TID';
           select '  documents='||count(*) from documents where tenant_id='$TID';
           select '  suppliers='||count(*) from suppliers where tenant_id='$TID';
           select '  purchase_orders='||count(*) from purchase_orders where tenant_id='$TID';
           select '  hitl_actions='||count(*) from hitl_actions where tenant_id='$TID';
           select '  invoices='||count(*) from invoices where tenant_id='$TID';"
echo "-> Browser: run this in the console to clear cached UI state (chat history, staged sheets, basket):"
echo "   ['mawrid_assistant_sessions','mawrid_upload_sheets','mawrid-basket','mawrid_enrich_active'].forEach(k=>localStorage.removeItem(k));location.reload();"
