// Feature: Procurement — Create Order (Screen 1). Pick noted products + quantities
//          (capped by the supplier-sheet quantity), warn on supplier MOQ, then create
//          the order and continue to Review & Send.
// API:     GET /suppliers · POST /procurement/orders/draft · POST /procurement/orders/{id}/place
import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, Link } from "react-router-dom";
import { Trash2, ShoppingBag, ImageOff, ArrowLeft, Receipt, AlertTriangle, ArrowRight, ClipboardList } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiErr } from "@/lib/api";
import { Card, SectionTitle, EmptyState, Spinner } from "@/components/ui";
import { useBasket } from "@/stores/basket";
import { formatCurrency } from "@/lib/utils";
import type { Supplier, OrderDraft } from "@/lib/types";

function asSuppliers(d: unknown): Supplier[] {
  if (Array.isArray(d)) return d as Supplier[];
  if (d && typeof d === "object" && Array.isArray((d as any).suppliers)) return (d as any).suppliers;
  return [];
}

export function Procurement() {
  const navigate = useNavigate();
  const basket = useBasket();
  const [supplierId, setSupplierId] = useState("");
  const [notes, setNotes] = useState("");
  const [delivery, setDelivery] = useState("");

  const suppliers = useQuery({ queryKey: ["suppliers"], queryFn: () => apiGet<unknown>("/suppliers") });
  const supplierList = asSuppliers(suppliers.data);
  const selectedSupplier = supplierList.find((s) => s.supplier_id === supplierId);

  const items = basket.items;
  const currency = items[0]?.currency ?? selectedSupplier?.currency ?? "USD";
  const total = useMemo(() => items.reduce((s, i) => s + (i.price ?? 0) * i.qty, 0), [items]);
  const totalUnits = useMemo(() => items.reduce((s, i) => s + i.qty, 0), [items]);
  const moq = selectedSupplier?.moq ?? null;
  const belowMoq = moq != null && totalUnits < moq;

  const createReview = useMutation({
    mutationFn: async () => {
      const draft = await apiPost<OrderDraft>("/procurement/orders/draft", {
        supplier_id: supplierId,
        line_items: items.map((l) => ({
          product_id: l.product_id, product_name: l.product_name, sku: l.sku,
          quantity: l.qty, unit_price: l.price ?? 0, currency: l.currency ?? currency,
        })),
        notes: notes || null,
        desired_delivery_date: delivery || null,
      });
      const placed = await apiPost<{ hitl_action_id: string }>(`/procurement/orders/${draft.order_id}/place`, {});
      return placed;
    },
    onSuccess: (placed) => {
      basket.clear();
      toast.success("Order drafted — review the AI email & spreadsheet");
      navigate(`/procurement/review/${placed.hitl_action_id}`);
    },
    onError: (e) => toast.error(apiErr(e, "Could not create order")),
  });

  return (
    <div className="space-y-6">
      <SectionTitle title="Create Order" subtitle="Your noted products — set quantities, pick a supplier, then review the AI-written request."
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
        <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
          {/* line items */}
          <Card>
            <SectionTitle title="Noted products" subtitle={`${items.length} product(s) · ${totalUnits} unit(s)`} />
            <div className="space-y-2">
              {items.map((l) => {
                const overCap = l.available != null && l.qty > l.available;
                return (
                  <div key={l.product_id} className="flex items-center gap-3 rounded-xl border border-line bg-white/[0.02] p-2.5">
                    <div className="grid h-12 w-12 shrink-0 place-items-center overflow-hidden rounded-lg bg-white/[0.04]">
                      {l.image_url ? <img src={l.image_url} alt="" className="h-full w-full object-contain" /> : <ImageOff className="h-4 w-4 text-ink-faint" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-600 text-ink">{l.product_name}</div>
                      <div className="font-mono text-[11px] text-ink-faint">
                        {l.sku ?? "no sku"} · {l.price != null ? formatCurrency(l.price, l.currency ?? "USD") : "no price"}
                        {l.available != null && <span className="ml-1 text-ink-soft">· {l.available} available</span>}
                      </div>
                    </div>
                    <div className="flex flex-col items-end">
                      <input type="number" min={1} max={l.available ?? undefined} value={l.qty}
                        onChange={(e) => basket.setQty(l.product_id, l.available != null ? Math.min(Number(e.target.value), l.available) : Number(e.target.value))}
                        className={`input w-20 !py-1.5 text-center ${overCap ? "!border-danger" : ""}`} />
                      {overCap && <span className="mt-0.5 text-[10px] text-danger">max {l.available}</span>}
                    </div>
                    <div className="w-20 text-right text-sm font-600 text-ink">{l.price != null ? formatCurrency(l.price * l.qty, l.currency ?? "USD") : "—"}</div>
                    <button onClick={() => basket.remove(l.product_id)} className="text-ink-faint hover:text-danger"><Trash2 className="h-4 w-4" /></button>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* supplier + receipt */}
          <Card>
            <SectionTitle title="Order summary" right={<Receipt className="h-5 w-5 text-ink-faint" />} />
            <div className="space-y-3">
              <div>
                <label className="label">Supplier</label>
                <select className="input" value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
                  <option value="">Select supplier…</option>
                  {supplierList.map((s) => <option key={s.supplier_id} value={s.supplier_id}>{s.name}{s.location ? ` — ${s.location}` : ""}{s.moq ? ` (MOQ ${s.moq})` : ""}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="label">Desired delivery</label><input type="date" className="input" value={delivery} onChange={(e) => setDelivery(e.target.value)} /></div>
                <div><label className="label">Notes</label><input className="input" placeholder="optional" value={notes} onChange={(e) => setNotes(e.target.value)} /></div>
              </div>

              {belowMoq && (
                <div className="flex items-start gap-2 rounded-xl border border-warn/40 bg-warn/10 p-3 text-xs text-warn">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  This supplier requires a minimum of <b className="mx-1">{moq}</b> units per order. You have {totalUnits}. Add {moq - totalUnits} more or pick another supplier.
                </div>
              )}

              <div className="flex justify-between border-t border-line pt-3 text-base font-800 text-ink">
                <span>Estimated total</span><span className="font-mono">{formatCurrency(total, currency)}</span>
              </div>

              <button className="btn-gold w-full" disabled={!supplierId || items.length === 0 || createReview.isPending} onClick={() => createReview.mutate()}>
                {createReview.isPending ? <Spinner className="h-4 w-4" /> : <ArrowRight className="h-4 w-4" />} Create order & review email
              </button>
              <p className="text-center text-[11px] text-ink-faint">Next, the AI drafts the request email + an Excel of codes & quantities. Nothing is sent until you approve.</p>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
