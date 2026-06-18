// Feature: Procurement — Create Order (Screen 1). Noted products are grouped by the
//          SHEET they came from: each sheet becomes its own order to that sheet's
//          supplier. Quantities are hard-capped at the sheet's available stock; per
//          supplier MOQ is warned. One click drafts an order per sheet and the AI
//          writes a formal request email + an Excel for each.
// API:     GET /suppliers · GET /catalog/documents · POST /procurement/orders/draft · /place
import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, Link } from "react-router-dom";
import { Trash2, ShoppingBag, ImageOff, ArrowLeft, Receipt, AlertTriangle, ArrowRight, ClipboardList, FileSpreadsheet, Building2, Minus, Plus, Package } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiErr } from "@/lib/api";
import { Card, SectionTitle, EmptyState, Spinner } from "@/components/ui";
import { useBasket, type BasketItem } from "@/stores/basket";
import { formatCurrency } from "@/lib/utils";
import type { Supplier, OrderDraft } from "@/lib/types";

interface SheetDoc { document_id: string; filename: string; supplier_name?: string | null; uploaded_at: string }

function asSuppliers(d: unknown): Supplier[] {
  if (Array.isArray(d)) return d as Supplier[];
  if (d && typeof d === "object" && Array.isArray((d as any).suppliers)) return (d as any).suppliers;
  return [];
}

interface Group { key: string; doc: SheetDoc | null; supplierName: string | null; items: BasketItem[] }

export function Procurement() {
  const navigate = useNavigate();
  const basket = useBasket();
  const items = basket.items;

  const suppliers = useQuery({ queryKey: ["suppliers"], queryFn: () => apiGet<unknown>("/suppliers") });
  const docs = useQuery({ queryKey: ["documents"], queryFn: () => apiGet<SheetDoc[]>("/catalog/documents") });
  const supplierList = asSuppliers(suppliers.data);
  const docList = docs.data ?? [];

  // group the noted products by the sheet they were noted from
  const groups: Group[] = useMemo(() => {
    const map = new Map<string, Group>();
    for (const it of items) {
      const key = it.document_id ?? "none";
      if (!map.has(key)) {
        const doc = docList.find((d) => d.document_id === it.document_id) ?? null;
        map.set(key, { key, doc, supplierName: doc?.supplier_name ?? it.supplier_name ?? null, items: [] });
      }
      map.get(key)!.items.push(it);
    }
    return [...map.values()];
  }, [items, docList]);

  // per-group supplier override (defaults to the sheet's supplier, matched by name)
  const [override, setOverride] = useState<Record<string, string>>({});
  function resolveSupplierId(g: Group): string {
    if (override[g.key]) return override[g.key];
    if (g.supplierName) {
      const m = supplierList.find((s) => s.name.toLowerCase() === g.supplierName!.toLowerCase());
      if (m) return m.supplier_id;
    }
    return "";
  }

  const place = useMutation({
    mutationFn: async () => {
      const createdActions: string[] = [];
      for (const g of groups) {
        const supplierId = resolveSupplierId(g);
        if (!supplierId) throw new Error(`Pick a supplier for "${g.doc?.filename ?? "noted products"}".`);
        const currency = g.items[0]?.currency ?? "USD";
        const draft = await apiPost<OrderDraft>("/procurement/orders/draft", {
          supplier_id: supplierId,
          line_items: g.items.map((l) => ({
            product_id: l.product_id, product_name: l.product_name, sku: l.sku,
            quantity: l.qty, unit_price: l.price ?? 0, currency: l.currency ?? currency,
          })),
          notes: g.doc ? `From sheet: ${g.doc.filename}` : null,
          desired_delivery_date: null,
        });
        const placed = await apiPost<{ hitl_action_id: string }>(`/procurement/orders/${draft.order_id}/place`, {});
        createdActions.push(placed.hitl_action_id);
      }
      return createdActions;
    },
    onSuccess: (actions) => {
      basket.clear();
      if (actions.length === 1) {
        toast.success("Order drafted — review the AI email & spreadsheet");
        navigate(`/procurement/review/${actions[0]}`);
      } else {
        toast.success(`${actions.length} orders drafted — one per sheet`);
        navigate("/purchase-orders");
      }
    },
    onError: (e: any) => toast.error(e?.message ? e.message : apiErr(e, "Could not create order")),
  });

  return (
    <div className="space-y-6">
      <SectionTitle title="Create Order" subtitle="Your noted products, grouped by the sheet they came from. Each sheet becomes its own order to that supplier."
        right={
          <div className="flex gap-2">
            <Link to="/purchase-orders" className="btn-ghost !py-2"><ClipboardList className="h-4 w-4" /> Purchase Orders</Link>
            <Link to="/catalog" className="btn-ghost !py-2"><ArrowLeft className="h-4 w-4" /> Catalogue</Link>
          </div>
        } />

      {items.length === 0 ? (
        <Card>
          <EmptyState icon={<ShoppingBag className="h-8 w-8" />} title="Nothing noted yet" hint="Open the catalogue, tap the bag on products you want to order, then come back." />
          <div className="mt-4 text-center"><Link to="/catalog" className="btn-gold"><ShoppingBag className="h-4 w-4" /> Browse catalogue</Link></div>
        </Card>
      ) : (
        <>
          <div className="space-y-5">
            {groups.map((g) => (
              <SheetOrderCard key={g.key} group={g} supplierList={supplierList} selectedSupplierId={resolveSupplierId(g)}
                onSupplier={(id) => setOverride((o) => ({ ...o, [g.key]: id }))} />
            ))}
          </div>

          <Card>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="text-sm text-ink-soft">
                {groups.length === 1 ? "1 order" : `${groups.length} orders`} · {items.length} product(s) ·{" "}
                <span className="font-700 text-ink">{formatCurrency(items.reduce((s, i) => s + (i.price ?? 0) * i.qty, 0), items[0]?.currency ?? "USD")}</span> total
              </div>
              <button className="btn-gold" disabled={place.isPending} onClick={() => place.mutate()}>
                {place.isPending ? <Spinner className="h-4 w-4" /> : <ArrowRight className="h-4 w-4" />}
                {groups.length === 1 ? "Create order & review email" : `Create ${groups.length} orders & review`}
              </button>
            </div>
            <p className="mt-2 text-right text-[11px] text-ink-faint">For each sheet the AI drafts a formal request email + an Excel of codes & quantities. Nothing is sent until you approve.</p>
          </Card>
        </>
      )}
    </div>
  );
}

function SheetOrderCard({ group, supplierList, selectedSupplierId, onSupplier }: {
  group: Group; supplierList: Supplier[]; selectedSupplierId: string; onSupplier: (id: string) => void;
}) {
  const basket = useBasket();
  const supplier = supplierList.find((s) => s.supplier_id === selectedSupplierId);
  const currency = group.items[0]?.currency ?? supplier?.currency ?? "USD";
  const total = group.items.reduce((s, i) => s + (i.price ?? 0) * i.qty, 0);
  const totalUnits = group.items.reduce((s, i) => s + i.qty, 0);
  const moq = supplier?.moq ?? null;
  const belowMoq = moq != null && totalUnits < moq;

  return (
    <Card>
      {/* sheet header */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
        <div className="flex items-center gap-2.5">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-gold/15 text-gold-soft"><FileSpreadsheet className="h-5 w-5" /></div>
          <div>
            <div className="text-sm font-700 text-ink">{group.doc?.filename ?? "Noted products"}</div>
            <div className="flex flex-wrap items-center gap-x-3 text-[11px] text-ink-soft">
              {group.supplierName && <span className="flex items-center gap-1"><Building2 className="h-3 w-3" /> {group.supplierName}</span>}
              <span>{group.items.length} product(s) · {totalUnits} unit(s)</span>
            </div>
          </div>
        </div>
        <div className="min-w-[220px]">
          <select className="input !py-2 text-sm" value={selectedSupplierId} onChange={(e) => onSupplier(e.target.value)}>
            <option value="">Select supplier…</option>
            {supplierList.map((s) => <option key={s.supplier_id} value={s.supplier_id}>{s.name}{s.moq ? ` (MOQ ${s.moq})` : ""}</option>)}
          </select>
        </div>
      </div>

      {/* line items */}
      <div className="space-y-2">
        {group.items.map((l) => {
          const atMax = l.available != null && l.qty >= l.available;
          return (
            <div key={l.product_id} className="flex items-center gap-3 rounded-xl border border-line bg-white/[0.02] p-2.5">
              <div className="grid h-12 w-12 shrink-0 place-items-center overflow-hidden rounded-lg bg-white/[0.04]">
                {l.image_url ? <img src={l.image_url} alt="" className="h-full w-full object-contain" /> : <ImageOff className="h-4 w-4 text-ink-faint" />}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-600 text-ink">{l.product_name}</div>
                <div className="font-mono text-[11px] text-ink-faint">
                  {l.sku ?? "no sku"} · {l.price != null ? formatCurrency(l.price, l.currency ?? "USD") : "no price"}
                  {l.available != null && <span className="ml-1 inline-flex items-center gap-0.5 text-emerald-soft"><Package className="h-3 w-3" /> {l.available} avail.</span>}
                </div>
              </div>
              {/* qty stepper — hard-capped at available */}
              <div className="flex items-center gap-1">
                <button onClick={() => basket.setQty(l.product_id, l.qty - 1)} disabled={l.qty <= 1}
                  className="grid h-8 w-8 place-items-center rounded-lg border border-line text-ink-soft hover:text-ink disabled:opacity-40"><Minus className="h-3.5 w-3.5" /></button>
                <input type="number" min={1} max={l.available ?? undefined} value={l.qty}
                  onChange={(e) => basket.setQty(l.product_id, Number(e.target.value))}
                  className="input w-16 !py-1.5 text-center" />
                <button onClick={() => basket.setQty(l.product_id, l.qty + 1)} disabled={atMax}
                  title={atMax ? `Only ${l.available} available` : "Add one"}
                  className="grid h-8 w-8 place-items-center rounded-lg border border-line text-ink-soft hover:text-ink disabled:opacity-40"><Plus className="h-3.5 w-3.5" /></button>
              </div>
              <div className="w-20 text-right text-sm font-600 text-ink">{l.price != null ? formatCurrency(l.price * l.qty, l.currency ?? "USD") : "—"}</div>
              <button onClick={() => basket.remove(l.product_id)} className="text-ink-faint hover:text-danger"><Trash2 className="h-4 w-4" /></button>
            </div>
          );
        })}
      </div>

      {belowMoq && (
        <div className="mt-3 flex items-start gap-2 rounded-xl border border-warn/40 bg-warn/10 p-3 text-xs text-warn">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          This supplier needs a minimum of <b className="mx-1">{moq}</b> units per order. You have {totalUnits} — add {moq - totalUnits} more or pick another supplier.
        </div>
      )}

      <div className="mt-3 flex items-center justify-between border-t border-line pt-3">
        <span className="flex items-center gap-1.5 text-sm text-ink-soft"><Receipt className="h-4 w-4 text-ink-faint" /> Order cost</span>
        <span className="font-mono text-base font-800 text-ink">{formatCurrency(total, currency)}</span>
      </div>
    </Card>
  );
}
