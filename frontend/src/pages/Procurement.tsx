// Feature: Procurement — build an order draft from the enriched catalog
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, Plus, Trash2, ClipboardList, Send } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiErr } from "@/lib/api";
import { Card, SectionTitle, StatusBadge, Loading, EmptyState } from "@/components/ui";
import type { Product, Supplier, OrderDraft } from "@/lib/types";

interface Line { product_id: string; product_name: string; qty: number }
function list<T>(d: unknown, key: string): T[] {
  if (Array.isArray(d)) return d as T[];
  if (d && typeof d === "object" && Array.isArray((d as any)[key])) return (d as any)[key];
  return [];
}

export function Procurement() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [supplierId, setSupplierId] = useState("");
  const [notes, setNotes] = useState("");
  const [delivery, setDelivery] = useState("");

  const products = useQuery({ queryKey: ["catalog-proc"], queryFn: () => apiGet<unknown>("/catalog/products?limit=200") });
  const suppliers = useQuery({ queryKey: ["suppliers"], queryFn: () => apiGet<unknown>("/suppliers") });
  const orders = useQuery({ queryKey: ["orders"], queryFn: () => apiGet<unknown>("/procurement/orders"), refetchInterval: 12_000 });

  const createDraft = useMutation({
    mutationFn: () =>
      apiPost<OrderDraft>("/procurement/orders/draft", {
        supplier_id: supplierId,
        line_items: lines.map((l) => ({ product_id: l.product_id, product_name: l.product_name, qty: l.qty })),
        notes: notes || null,
        desired_delivery_date: delivery || null,
      }),
    onSuccess: () => {
      toast.success("Order draft created");
      setLines([]); setNotes(""); setDelivery("");
      qc.invalidateQueries({ queryKey: ["orders"] });
    },
    onError: (e) => toast.error(apiErr(e, "Could not create draft")),
  });

  const submitOrder = useMutation({
    mutationFn: (id: string) => apiPost(`/procurement/orders/${id}/submit`, {}),
    onSuccess: () => { toast.success("Draft submitted (locked)"); qc.invalidateQueries({ queryKey: ["orders"] }); },
    onError: (e) => toast.error(apiErr(e, "Submit failed")),
  });

  const catalog = useMemo(() => {
    const all = list<Product>(products.data, "products").filter((p) => p.enrichment_status === "enriched" || p.enrichment_status === "pending");
    if (!search.trim()) return all.slice(0, 50);
    const q = search.toLowerCase();
    return all.filter((p) => p.product_name?.toLowerCase().includes(q) || p.sku?.toLowerCase().includes(q)).slice(0, 50);
  }, [products.data, search]);

  const supplierList = list<Supplier>(suppliers.data, "suppliers");
  const orderList = list<OrderDraft>(orders.data, "orders");

  function add(p: Product) {
    setLines((ls) => ls.find((l) => l.product_id === p.product_id) ? ls : [...ls, { product_id: p.product_id, product_name: p.product_name, qty: 1 }]);
  }

  return (
    <div className="space-y-6">
      <SectionTitle title="Procurement" subtitle="Select products from your internal catalog and draft a purchase order." />

      <div className="grid gap-6 lg:grid-cols-2">
        {/* catalog */}
        <Card>
          <div className="relative mb-4">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
            <input className="input pl-9" placeholder="Search catalog…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          {products.isLoading ? <Loading /> : catalog.length === 0 ? (
            <EmptyState title="No enriched products" hint="Enrich a catalog first." />
          ) : (
            <div className="max-h-[460px] space-y-1.5 overflow-y-auto pr-1">
              {catalog.map((p) => (
                <div key={p.product_id} className="table-row flex items-center justify-between rounded-xl px-3 py-2.5">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-600 text-ink">{p.product_name}</div>
                    <div className="truncate text-xs text-ink-faint">{p.sku ?? "no sku"}</div>
                  </div>
                  <button onClick={() => add(p)} className="btn-ghost !px-2.5 !py-1.5"><Plus className="h-4 w-4" /></button>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* draft */}
        <Card>
          <SectionTitle title="Order Draft" subtitle={`${lines.length} line item(s)`} />
          <div className="space-y-3">
            <div>
              <label className="label">Supplier</label>
              <select className="input" value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
                <option value="">Select supplier…</option>
                {supplierList.map((s) => <option key={s.supplier_id} value={s.supplier_id}>{s.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Desired delivery</label>
                <input type="date" className="input" value={delivery} onChange={(e) => setDelivery(e.target.value)} />
              </div>
              <div>
                <label className="label">Notes</label>
                <input className="input" placeholder="optional" value={notes} onChange={(e) => setNotes(e.target.value)} />
              </div>
            </div>

            <div className="rounded-xl border border-line bg-black/20 p-2">
              {lines.length === 0 ? (
                <p className="py-6 text-center text-sm text-ink-faint">Add products from the catalog →</p>
              ) : lines.map((l) => (
                <div key={l.product_id} className="flex items-center gap-2 px-2 py-1.5">
                  <span className="min-w-0 flex-1 truncate text-sm text-ink">{l.product_name}</span>
                  <input
                    type="number" min={1} value={l.qty}
                    onChange={(e) => setLines((ls) => ls.map((x) => x.product_id === l.product_id ? { ...x, qty: Number(e.target.value) } : x))}
                    className="input w-20 !py-1.5 text-center"
                  />
                  <button onClick={() => setLines((ls) => ls.filter((x) => x.product_id !== l.product_id))} className="text-ink-faint hover:text-danger">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>

            <button
              className="btn-gold w-full"
              disabled={!supplierId || lines.length === 0 || createDraft.isPending}
              onClick={() => createDraft.mutate()}
            >
              <ClipboardList className="h-4 w-4" /> Create draft
            </button>
          </div>
        </Card>
      </div>

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
