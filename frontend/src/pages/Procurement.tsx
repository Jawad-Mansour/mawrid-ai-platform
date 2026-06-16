// Feature: Procurement — order page driven by the "noted" basket: set quantities,
//          review a priced receipt, pick a supplier, draft the PO (→ Communication
//          Agent → HITL). Submitting locks the draft.
// API:     GET /catalog/products · GET /suppliers · GET/POST /procurement/orders*
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, ClipboardList, Send, ShoppingBag, ImageOff, ArrowLeft, Receipt } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { apiGet, apiPost, apiErr } from "@/lib/api";
import { Card, SectionTitle, StatusBadge, EmptyState } from "@/components/ui";
import { useBasket } from "@/stores/basket";
import { formatCurrency } from "@/lib/utils";
import type { Supplier, OrderDraft } from "@/lib/types";

function list<T>(d: unknown, key: string): T[] {
  if (Array.isArray(d)) return d as T[];
  if (d && typeof d === "object" && Array.isArray((d as any)[key])) return (d as any)[key];
  return [];
}

export function Procurement() {
  const qc = useQueryClient();
  const basket = useBasket();
  const [supplierId, setSupplierId] = useState("");
  const [notes, setNotes] = useState("");
  const [delivery, setDelivery] = useState("");

  const suppliers = useQuery({ queryKey: ["suppliers"], queryFn: () => apiGet<unknown>("/suppliers") });
  const orders = useQuery({ queryKey: ["orders"], queryFn: () => apiGet<unknown>("/procurement/orders"), refetchInterval: 12_000 });
  const supplierList = list<Supplier>(suppliers.data, "suppliers");
  const orderList = list<OrderDraft>(orders.data, "orders");

  const items = basket.items;
  const currency = items[0]?.currency ?? "USD";
  const total = useMemo(() => items.reduce((s, i) => s + (i.price ?? 0) * i.qty, 0), [items]);
  const totalUnits = useMemo(() => items.reduce((s, i) => s + i.qty, 0), [items]);

  const createDraft = useMutation({
    mutationFn: () =>
      apiPost<OrderDraft>("/procurement/orders/draft", {
        supplier_id: supplierId,
        line_items: items.map((l) => ({ product_id: l.product_id, product_name: l.product_name, qty: l.qty })),
        notes: notes || null,
        desired_delivery_date: delivery || null,
      }),
    onSuccess: () => {
      toast.success("Order draft created — review & place it from the list below.");
      basket.clear(); setNotes(""); setDelivery("");
      qc.invalidateQueries({ queryKey: ["orders"] });
    },
    onError: (e) => toast.error(apiErr(e, "Could not create draft")),
  });

  const submitOrder = useMutation({
    mutationFn: (id: string) => apiPost(`/procurement/orders/${id}/submit`, {}),
    onSuccess: () => { toast.success("Draft submitted (locked) — PO goes to HITL approval"); qc.invalidateQueries({ queryKey: ["orders"] }); },
    onError: (e) => toast.error(apiErr(e, "Submit failed")),
  });

  return (
    <div className="space-y-6">
      <SectionTitle title="Create Order" subtitle="Your noted products from the catalog — set quantities, review the receipt, draft the PO."
        right={<Link to="/catalog" className="btn-ghost !py-2"><ArrowLeft className="h-4 w-4" /> Back to catalog</Link>} />

      {items.length === 0 ? (
        <Card>
          <EmptyState icon={<ShoppingBag className="h-8 w-8" />} title="Nothing noted yet"
            hint="Open the catalog, click the bag icon on products you want to order, then come back here." />
          <div className="mt-4 text-center"><Link to="/catalog" className="btn-gold"><ShoppingBag className="h-4 w-4" /> Browse catalog</Link></div>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          {/* line items */}
          <Card>
            <SectionTitle title="Noted products" subtitle={`${items.length} product(s) · ${totalUnits} unit(s)`} />
            <div className="space-y-2">
              {items.map((l) => (
                <div key={l.product_id} className="flex items-center gap-3 rounded-xl border border-line bg-white/[0.02] p-2.5">
                  <div className="grid h-12 w-12 shrink-0 place-items-center overflow-hidden rounded-lg bg-white/[0.04]">
                    {l.image_url ? <img src={l.image_url} alt="" className="h-full w-full object-contain" /> : <ImageOff className="h-4 w-4 text-ink-faint" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-600 text-ink">{l.product_name}</div>
                    <div className="font-mono text-[11px] text-ink-faint">{l.sku ?? "no sku"} · {l.price != null ? formatCurrency(l.price, l.currency ?? "USD") : "no price"}</div>
                  </div>
                  <input type="number" min={1} value={l.qty}
                    onChange={(e) => basket.setQty(l.product_id, Number(e.target.value))}
                    className="input w-20 !py-1.5 text-center" />
                  <div className="w-20 text-right text-sm font-600 text-ink">{l.price != null ? formatCurrency(l.price * l.qty, l.currency ?? "USD") : "—"}</div>
                  <button onClick={() => basket.remove(l.product_id)} className="text-ink-faint hover:text-danger"><Trash2 className="h-4 w-4" /></button>
                </div>
              ))}
            </div>
          </Card>

          {/* receipt + draft */}
          <Card>
            <SectionTitle title="Receipt" right={<Receipt className="h-5 w-5 text-ink-faint" />} />
            <div className="space-y-1.5 text-sm">
              {items.map((l) => (
                <div key={l.product_id} className="flex justify-between gap-2 text-ink-soft">
                  <span className="min-w-0 truncate">{l.qty} × {l.product_name}</span>
                  <span className="shrink-0 font-mono text-ink">{l.price != null ? formatCurrency(l.price * l.qty, l.currency ?? "USD") : "—"}</span>
                </div>
              ))}
            </div>
            <div className="mt-3 flex justify-between border-t border-line pt-3 text-base font-800 text-ink">
              <span>Estimated total</span>
              <span className="font-mono">{formatCurrency(total, currency)}</span>
            </div>
            <p className="mt-1 text-[11px] text-ink-faint">Prices are the latest supplier-sheet prices; final PO totals confirm with the supplier.</p>

            <div className="mt-4 space-y-3">
              <div>
                <label className="label">Supplier</label>
                <select className="input" value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
                  <option value="">Select supplier…</option>
                  {supplierList.map((s) => <option key={s.supplier_id} value={s.supplier_id}>{s.name}{(s as any).location ? ` — ${(s as any).location}` : ""}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="label">Desired delivery</label><input type="date" className="input" value={delivery} onChange={(e) => setDelivery(e.target.value)} /></div>
                <div><label className="label">Notes</label><input className="input" placeholder="optional" value={notes} onChange={(e) => setNotes(e.target.value)} /></div>
              </div>
              <button className="btn-gold w-full" disabled={!supplierId || items.length === 0 || createDraft.isPending} onClick={() => createDraft.mutate()}>
                <ClipboardList className="h-4 w-4" /> Create order draft
              </button>
              <p className="text-center text-[11px] text-ink-faint">A draft is editable. Submitting locks it and sends the PO to HITL approval, where the Communication Agent drafts it in the supplier's language.</p>
            </div>
          </Card>
        </div>
      )}

      {/* existing orders */}
      <Card>
        <SectionTitle title="Order Drafts & POs" subtitle="Submit a draft to lock it, then place the PO (HITL)." />
        {orderList.length === 0 ? (
          <EmptyState title="No orders yet" hint="Your created drafts will appear here." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-xs uppercase tracking-wider text-ink-faint">
                <th className="py-2.5 pr-3 font-600">Order</th><th className="px-3 font-600">Items</th>
                <th className="px-3 font-600">Status</th><th className="px-3 font-600"></th>
              </tr></thead>
              <tbody>
                {orderList.map((o) => (
                  <tr key={o.order_id} className="table-row">
                    <td className="py-3 pr-3 font-mono text-xs text-ink">{o.order_id.slice(0, 12)}</td>
                    <td className="px-3 text-ink-soft">{o.line_items?.length ?? 0}</td>
                    <td className="px-3"><StatusBadge status={o.status} /></td>
                    <td className="px-3 text-right">
                      {o.status === "draft" && (
                        <button className="btn-ghost !py-1.5" onClick={() => submitOrder.mutate(o.order_id)}>
                          <Send className="h-3.5 w-3.5" /> Submit
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
