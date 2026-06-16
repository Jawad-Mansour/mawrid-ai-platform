#!/usr/bin/env bash
# Feature: Demo seed — one command to make the whole app look alive for a presentation.
# Creates (or reuses) a known demo account and populates its tenant with realistic
# suppliers, customers, products (every lifecycle stage), invoices (aged receivables +
# payables), shipments, pending HITL actions, storefront orders and dunning sequences.
#
# Usage:  bash scripts/seed_demo.sh
# Login:  demo@mawrid.ai  /  Demo!pass2026
set -euo pipefail

BASE="http://localhost:8000/api/v1"
EMAIL="demo@mawrid.ai"
PASS="Demo!pass2026"
COMPANY="Mawrid Demo Co"

echo "→ ensuring demo account ($EMAIL) exists…"
curl -s -m 20 -X POST "$BASE/auth/signup" -H "Content-Type: application/json" \
  -d "{\"company_name\":\"$COMPANY\",\"email\":\"$EMAIL\",\"password\":\"$PASS\",\"mode\":\"hybrid\"}" \
  -o /dev/null -w "  signup HTTP %{http_code} (400 = already exists, fine)\n" || true

PSQL() { docker compose exec -T postgres psql -U mawrid -d mawrid "$@"; }

TID=$(PSQL -tAc "select tenant_id from tenants where name='$COMPANY' order by created_at limit 1;" | tr -d '[:space:]')
if [ -z "$TID" ]; then echo "‼ could not resolve tenant_id"; exit 1; fi
echo "→ tenant_id = $TID"

echo "→ clearing any previous seed for this tenant…"
PSQL -v ON_ERROR_STOP=1 -q <<SQL
delete from dunning_sequences where tenant_id='$TID';
delete from storefront_orders where tenant_id='$TID';
delete from hitl_actions where tenant_id='$TID';
delete from shipments where tenant_id='$TID';
delete from invoices where tenant_id='$TID';
delete from products where tenant_id='$TID';
delete from customers where tenant_id='$TID';
delete from suppliers where tenant_id='$TID';
SQL

echo "→ seeding…"
PSQL -v ON_ERROR_STOP=1 -q <<SQL
-- ── Suppliers (themed on the dashboard globe hubs) ───────────────────────────
insert into suppliers (supplier_id, tenant_id, name, email, phone, score, language, currency, discrepancy_count, damage_count) values
 (md5('s1'||'$TID'),'$TID','Shenzhen ElectroParts Ltd','sales@shenzhen-ep.cn','+8675588001','88','en','USD',1,0),
 (md5('s2'||'$TID'),'$TID','Guangzhou HomeGoods Co','export@gz-home.cn','+8620881220','84','en','USD',3,2),
 (md5('s3'||'$TID'),'$TID','Istanbul Tekstil A.S.','info@istanbul-tekstil.tr','+902125550','91','en','EUR',0,0),
 (md5('s4'||'$TID'),'$TID','Milano Design SRL','ciao@milano-design.it','+390255512','94','en','EUR',0,0),
 (md5('s5'||'$TID'),'$TID','Frankfurt Industrie GmbH','kontakt@frankfurt-ind.de','+496955123','96','en','EUR',0,0),
 (md5('s6'||'$TID'),'$TID','Beirut Trading SARL','hello@beirut-trading.lb','+9611350','90','ar','USD',1,0),
 (md5('s7'||'$TID'),'$TID','Dubai Re-Export DMCC','desk@dubai-reexport.ae','+97143330','93','en','USD',2,1),
 (md5('s8'||'$TID'),'$TID','Seoul Beauty Inc','global@seoul-beauty.kr','+8225551','92','en','USD',0,0);

-- ── Customers (mix of B2B wholesale + B2C retail) ────────────────────────────
insert into customers (customer_id, tenant_id, customer_type, name, email, phone, payment_history_score, segment, language, previous_dunning_count) values
 (md5('c1'||'$TID'),'$TID','b2b','Cedar Retail Group','ap@cedarretail.lb','+9611700','7.2','wholesale','ar',1),
 (md5('c2'||'$TID'),'$TID','b2b','Mount Lebanon Markets','finance@mlmarkets.lb','+9611701','5.8','wholesale','ar',3),
 (md5('c3'||'$TID'),'$TID','b2b','Tripoli Distributors','pay@tripolidist.lb','+9616702','8.1','wholesale','fr',0),
 (md5('c4'||'$TID'),'$TID','b2c','Rana Khalil','rana.k@gmail.com','+9613703','9.0','retail','en',0),
 (md5('c5'||'$TID'),'$TID','b2c','Omar Haddad','omar.haddad@gmail.com','+9613704','4.5','retail','ar',2),
 (md5('c6'||'$TID'),'$TID','b2c','Yara Saab','yara.saab@outlook.com','+9613705','8.8','retail','en',0);

-- ── Products (every lifecycle stage) ─────────────────────────────────────────
-- enriched + published (on storefront)
insert into products (product_id, tenant_id, product_hash, product_name, sku, enrichment_status, inventory_status, storefront_status, qty_in_stock, storefront_qty, price_history, barcode, description, specifications, enrichment_source, enrichment_confidence, currency, retail_price, reorder_threshold) values
 (md5('p1'||'$TID'),'$TID',md5('p1h'||'$TID'),'Anker PowerCore 20000 Power Bank','ANK-PC20K','enriched','in_stock','published',140,120,'[{"price":18.50,"at":"2026-05-01"}]','0848061045',  'High-capacity 20000mAh portable charger with PowerIQ fast charging.','{"capacity":"20000mAh","ports":"2x USB-A, 1x USB-C","weight":"343g"}','icecat','high','USD',39.90,30),
 (md5('p2'||'$TID'),'$TID',md5('p2h'||'$TID'),'Philips LED Bulb 9W E27 (4-pack)','PHL-LED9W','enriched','in_stock','published',300,260,'[{"price":2.10,"at":"2026-05-01"}]','8718699',     'Warm-white 806lm LED bulbs, 15000h lifetime, E27 base.','{"watt":"9W","lumens":"806","base":"E27","pack":"4"}','icecat','high','USD',7.50,80),
 (md5('p3'||'$TID'),'$TID',md5('p3h'||'$TID'),'Istanbul Cotton Bath Towel Set','IST-TWL-SET','enriched','in_stock','published',85,70,'[{"price":11.00,"at":"2026-05-10"}]','8690000', 'Premium Turkish cotton towel set (2 bath, 2 hand).','{"material":"100% cotton","gsm":"550","pieces":"4"}','web','high','USD',24.00,20),
 (md5('p4'||'$TID'),'$TID',md5('p4h'||'$TID'),'Seoul Hydra Vitamin-C Serum 30ml','SEO-VC30','enriched','in_stock','published',60,55,'[{"price":6.80,"at":"2026-05-12"}]','8801000', 'Brightening vitamin-C facial serum, K-beauty formulation.','{"volume":"30ml","skin":"all types"}','web','medium','USD',19.90,15);

-- enriched, in stock, NOT yet published (ready to publish)
insert into products (product_id, tenant_id, product_hash, product_name, sku, enrichment_status, inventory_status, storefront_status, qty_in_stock, price_history, barcode, description, specifications, enrichment_source, enrichment_confidence, currency, reorder_threshold) values
 (md5('p5'||'$TID'),'$TID',md5('p5h'||'$TID'),'Bosch Cordless Drill GSR 12V','BSH-GSR12','enriched','in_stock','unpublished',40,'[{"price":42.00,"at":"2026-05-14"}]','4059952','Compact 12V cordless drill/driver with 2 batteries.','{"voltage":"12V","torque":"30Nm","chuck":"10mm"}','icecat','high','USD',25),
 (md5('p6'||'$TID'),'$TID',md5('p6h'||'$TID'),'Milano Ceramic Coffee Mug 350ml','MIL-MUG350','enriched','in_stock','unpublished',210,'[{"price":1.90,"at":"2026-05-14"}]','8000000','Hand-finished Italian ceramic mug, dishwasher safe.','{"volume":"350ml","material":"ceramic"}','web','medium','USD',60),
 (md5('p7'||'$TID'),'$TID',md5('p7h'||'$TID'),'Frankfurt Steel Tool Box 18in','FRK-TBX18','enriched','in_stock','unpublished',32,'[{"price":15.50,"at":"2026-05-15"}]','4000000','Heavy-duty steel tool box with cantilever trays.','{"size":"18in","material":"steel"}','icecat','high','USD',12);

-- low stock (below reorder threshold → reorder signal)
insert into products (product_id, tenant_id, product_hash, product_name, sku, enrichment_status, inventory_status, storefront_status, qty_in_stock, storefront_qty, price_history, barcode, description, specifications, enrichment_source, enrichment_confidence, currency, retail_price, reorder_threshold) values
 (md5('p8'||'$TID'),'$TID',md5('p8h'||'$TID'),'Dubai Dates Gift Box 1kg','DXB-DATES1','enriched','low_stock','published',8,8,'[{"price":9.00,"at":"2026-05-16"}]','6291000','Premium Medjool dates in a luxury gift box.','{"weight":"1kg","origin":"UAE"}','web','medium','USD',22.00,25);

-- pending enrichment (just uploaded)
insert into products (product_id, tenant_id, product_hash, product_name, sku, enrichment_status, inventory_status, storefront_status, qty_in_stock, price_history, currency) values
 (md5('p9'||'$TID'),'$TID',md5('p9h'||'$TID'),'Generic Wireless Mouse 2.4G','GEN-WM24','pending','unknown','unpublished',0,'[]','USD'),
 (md5('p10'||'$TID'),'$TID',md5('p10h'||'$TID'),'USB-C to HDMI Adapter 4K','GEN-UCHDMI','pending','unknown','unpublished',0,'[]','USD'),
 (md5('p11'||'$TID'),'$TID',md5('p11h'||'$TID'),'Stainless Water Bottle 750ml','GEN-WB750','pending','unknown','unpublished',0,'[]','USD');

-- failed enrichment (routed for review)
insert into products (product_id, tenant_id, product_hash, product_name, sku, enrichment_status, inventory_status, storefront_status, qty_in_stock, price_history, currency) values
 (md5('p12'||'$TID'),'$TID',md5('p12h'||'$TID'),'Unbranded Item Lot #4471','???-4471','failed','unknown','unpublished',0,'[]','USD');

-- ── Invoices — receivables (aged for the dunning + aging chart) ──────────────
insert into invoices (invoice_id, tenant_id, direction, invoice_type, amount_due, invoice_date, due_date, payment_terms_days, status, created_at, contact_email, contact_name, contact_language, customer_id, currency) values
 (md5('i1'||'$TID'),'$TID','receivable','sale',1850.00, CURRENT_DATE-40, CURRENT_DATE-25,15,'unpaid', now(),'ap@cedarretail.lb','Cedar Retail Group','ar',md5('c1'||'$TID'),'USD'),
 (md5('i2'||'$TID'),'$TID','receivable','sale', 920.00, CURRENT_DATE-30, CURRENT_DATE-16,14,'unpaid', now(),'finance@mlmarkets.lb','Mount Lebanon Markets','ar',md5('c2'||'$TID'),'USD'),
 (md5('i3'||'$TID'),'$TID','receivable','sale', 540.00, CURRENT_DATE-22, CURRENT_DATE-8, 14,'unpaid', now(),'pay@tripolidist.lb','Tripoli Distributors','fr',md5('c3'||'$TID'),'USD'),
 (md5('i4'||'$TID'),'$TID','receivable','sale',  79.90, CURRENT_DATE-12, CURRENT_DATE-5,  7,'unpaid', now(),'omar.haddad@gmail.com','Omar Haddad','ar',md5('c5'||'$TID'),'USD'),
 (md5('i5'||'$TID'),'$TID','receivable','sale', 240.00, CURRENT_DATE-6,  CURRENT_DATE+8, 14,'unpaid', now(),'rana.k@gmail.com','Rana Khalil','en',md5('c4'||'$TID'),'USD'),
 (md5('i6'||'$TID'),'$TID','receivable','sale', 410.00, CURRENT_DATE-50, CURRENT_DATE-36,14,'paid',  now(),'yara.saab@outlook.com','Yara Saab','en',md5('c6'||'$TID'),'USD');
update invoices set paid_at = now()-interval '20 days' where invoice_id=md5('i6'||'$TID');

-- ── Invoices — payables (we owe suppliers) ──────────────────────────────────
insert into invoices (invoice_id, tenant_id, direction, invoice_type, amount_due, invoice_date, due_date, payment_terms_days, status, created_at, contact_email, contact_name, contact_language, supplier_id, currency) values
 (md5('i7'||'$TID'),'$TID','payable','purchase',3200.00, CURRENT_DATE-10, CURRENT_DATE+4, 14,'unpaid', now(),'sales@shenzhen-ep.cn','Shenzhen ElectroParts Ltd','en',md5('s1'||'$TID'),'USD'),
 (md5('i8'||'$TID'),'$TID','payable','purchase',1450.00, CURRENT_DATE-8,  CURRENT_DATE+6, 14,'unpaid', now(),'info@istanbul-tekstil.tr','Istanbul Tekstil A.S.','en',md5('s3'||'$TID'),'EUR');

-- ── Shipments (active + one received) ───────────────────────────────────────
insert into shipments (shipment_id, tenant_id, po_id, carrier, tracking_number, expected_arrival_date, status, created_at) values
 (md5('sh1'||'$TID'),'$TID','PO-1001','DHL','DHL77123456', CURRENT_DATE+6, 'in_transit', now()),
 (md5('sh2'||'$TID'),'$TID','PO-1002','Aramex','ARX99887766', CURRENT_DATE+2, 'at_customs', now()),
 (md5('sh3'||'$TID'),'$TID','PO-1003','MSC','MSC10293847',  CURRENT_DATE+14,'shipped',    now());
insert into shipments (shipment_id, tenant_id, po_id, carrier, tracking_number, expected_arrival_date, status, received_at, created_at) values
 (md5('sh4'||'$TID'),'$TID','PO-0999','FedEx','FDX55512345', CURRENT_DATE-3, 'received', now()-interval '3 days', now()-interval '12 days');

-- ── Pending HITL actions (the approval center) ──────────────────────────────
insert into hitl_actions (action_id, tenant_id, action_type, status, payload, created_at, expires_at) values
 (md5('h1'||'$TID'),'$TID','purchase_order_send','pending',
   '{"supplier_name":"Shenzhen ElectroParts Ltd","supplier_email":"sales@shenzhen-ep.cn","currency":"USD","total":3200,"lines":[{"product":"Anker PowerCore 20000","qty":100,"unit":18.5},{"product":"USB-C to HDMI Adapter 4K","qty":200,"unit":6.75}],"draft":"Dear Shenzhen ElectroParts, please find our purchase order PO-1004 below..."}',
   now(), now()+interval '3 days'),
 (md5('h2'||'$TID'),'$TID','dunning_receivables','pending',
   '{"customer_name":"Mount Lebanon Markets","invoice_id":"INV-0002","amount":920,"days_overdue":16,"tone":"firm","draft":"Dear Mount Lebanon Markets, our records show invoice INV-0002 for USD 920 is now 16 days past due..."}',
   now(), now()+interval '3 days'),
 (md5('h3'||'$TID'),'$TID','supplier_outreach','pending',
   '{"candidate":"Vietnam Homeware Export JSC","reason":"Lower lead time for homeware category","draft":"Hello, we are an importer in Lebanon sourcing homeware and would like to request your catalog and MOQ..."}',
   now(), now()+interval '5 days'),
 (md5('h4'||'$TID'),'$TID','reorder','pending',
   '{"product":"Dubai Dates Gift Box 1kg","sku":"DXB-DATES1","qty_in_stock":8,"reorder_threshold":25,"suggested_qty":100,"supplier":"Dubai Re-Export DMCC"}',
   now(), now()+interval '3 days');

-- ── Storefront orders (consumer) ────────────────────────────────────────────
insert into storefront_orders (order_id, tenant_id, customer_id, payment_gateway, total_amount, status, items, created_at) values
 (md5('o1'||'$TID'),'$TID',md5('c4'||'$TID'),'stripe', 64.90,'processing','[{"sku":"ANK-PC20K","name":"Anker PowerCore 20000","qty":1,"price":39.90},{"sku":"SEO-VC30","name":"Seoul Hydra Serum","qty":1,"price":19.90}]', now()-interval '2 hours'),
 (md5('o2'||'$TID'),'$TID',md5('c6'||'$TID'),'stripe', 24.00,'pending','[{"sku":"IST-TWL-SET","name":"Istanbul Towel Set","qty":1,"price":24.00}]', now()-interval '40 minutes'),
 (md5('o3'||'$TID'),'$TID',md5('c4'||'$TID'),'stripe', 15.00,'fulfilled','[{"sku":"PHL-LED9W","name":"Philips LED Bulb 4-pack","qty":2,"price":7.50}]', now()-interval '3 days');

-- ── Active dunning sequences (linked to overdue receivables) ────────────────
insert into dunning_sequences (sequence_id, tenant_id, invoice_id, track, status, created_at) values
 (md5('d1'||'$TID'),'$TID',md5('i1'||'$TID'),'receivables','active', now()-interval '5 days'),
 (md5('d2'||'$TID'),'$TID',md5('i2'||'$TID'),'receivables','active', now()-interval '2 days'),
 (md5('d3'||'$TID'),'$TID',md5('i4'||'$TID'),'b2c','active', now()-interval '1 day');
SQL

echo ""
echo "✓ demo seed complete."
PSQL -tAc "select '  suppliers='||count(*) from suppliers where tenant_id='$TID';
           select '  customers='||count(*) from customers where tenant_id='$TID';
           select '  products='||count(*) from products where tenant_id='$TID';
           select '  invoices='||count(*) from invoices where tenant_id='$TID';
           select '  shipments='||count(*) from shipments where tenant_id='$TID';
           select '  pending HITL='||count(*) from hitl_actions where tenant_id='$TID' and status='pending';
           select '  storefront orders='||count(*) from storefront_orders where tenant_id='$TID';
           select '  dunning sequences='||count(*) from dunning_sequences where tenant_id='$TID';"
echo ""
echo "→ Log in at http://localhost:3000  with  $EMAIL  /  $PASS"
