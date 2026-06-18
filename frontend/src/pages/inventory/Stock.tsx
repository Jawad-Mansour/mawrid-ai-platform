// Feature: Inventory — Stock Levels. Every in-stock product, low ones flagged with
//          their source supplier and a one-click restock PO draft. Editable reorder point.
// API:     GET /procurement/stock · POST /procurement/products/{id}/restock · /threshold
import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Warehouse, PackageMinus, RefreshCw, Building2, TrendingUp, Store } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiErr } from "@/lib/api";
import { Card, SectionTitle, Loading, EmptyState, Spinner } from "@/components/ui";
import { formatCurrency } from "@/lib/utils";

interface Item { product_id: string; product_name: string; sku: string | null; qty_in_stock: number; storefront_qty: number; reorder_threshold: number | null; low: boolean; supplier_name: string | null; price: number | null; currency: string | null }

export function Stock() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["stock"], queryFn: () => apiGet<Item[]>("/procurement/stock"), refetchInterval: 20_000 });
  const [qty, setQty] = useState<Record<string, number>>({});
  const [thr, setThr] = useState<Record<string, number>>({});
  const rows = q.data ?? [];
  const lowCount = rows.filter((r) => r.low).length;

  const restock = useMutation({
    mutationFn: ({ id, quantity }: { id: string; quantity: number }) => apiPost<{ hitl_action_id: string }>(`/procurement/products/${id}/restock`, { quantity }),
    onSuccess: (r) => { toast.success("Restock PO drafted"); qc.invalidateQueries({ queryKey: ["stock"] }); if (r.hitl_action_id) navigate(`/procurement/review/${r.hitl_action_id}`); },
    onError: (e) => toast.error(apiErr(e, "Could not draft restock")),
  });
  const setThreshold = useMutation({
    mutationFn: ({ id, t }: { id: string; t: number }) => apiPost(`/procurement/products/${id}/threshold`, { reorder_threshold: t }),
    onSuccess: () => { toast.success("Reorder point saved"); qc.invalidateQueries({ queryKey: ["stock"] }); },
    onError: (e) => toast.error(apiErr(e, "Failed")),
  });

  return (
    <div className="space-y-6">
      <SectionTitle title="Stock Levels" subtitle="Everything you hold in stock — low items are flagged so you can reorder from the right supplier."
        right={<button onClick={() => q.refetch()} className="btn-ghost !py-2"><RefreshCw className="h-4 w-4" /> Refresh</button>} />

      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Products in stock" value={rows.length} icon={<Warehouse className="h-5 w-5" />} />
        <Stat label="Low stock" value={lowCount} icon={<PackageMinus className="h-5 w-5" />} tone="warn" />
        <Stat label="On storefront" value={rows.filter((r) => r.storefront_qty > 0).length} icon={<Store className="h-5 w-5" />} tone="emerald" />
      </div>

      <div className="flex items-start gap-2 rounded-xl border border-grape/25 bg-grape/[0.06] p-3 text-xs text-ink-soft">
        <TrendingUp className="mt-0.5 h-4 w-4 shrink-0 text-grape-soft" />
        <span>Low-stock is flagged on quantity vs. reorder point. <Link to="/inventory/demand" className="text-grape-soft underline">Demand Signals</Link> (coming soon) will also weigh sales velocity, time-to-sell and interest.</span>
      </div>

      <Card>
        <SectionTitle title="In stock" />
        {q.isLoading ? <Loading /> : rows.length === 0 ? (
          <EmptyState icon={<Warehouse className="h-8 w-8" />} title="Nothing in stock yet" hint="Receive goods on an arrived shipment to build your stock." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-xs uppercase tracking-wider text-ink-faint">
                <th className="py-2 pr-2 font-600">Product</th><th className="px-2 text-right font-600">In stock</th><th className="px-2 text-right font-600">On store</th><th className="px-2 text-center font-600">Reorder ≤</th><th className="px-2 font-600">Supplier</th><th className="px-2 text-right font-600">Restock</th>
              </tr></thead>
              <tbody>
                {rows.map((p) => (
                  <tr key={p.product_id} className={`border-b border-line/60 ${p.low ? "bg-warn/[0.04]" : ""}`}>
                    <td className="py-2 pr-2"><div className="line-clamp-1 text-ink">{p.product_name}</div><div className="font-mono text-[10px] text-ink-faint">{p.sku ?? "—"}{p.price != null ? ` · ${formatCurrency(p.price, p.currency ?? "USD")}` : ""}</div></td>
                    <td className="px-2 text-right"><span className={`inline-flex items-center gap-1 font-700 ${p.low ? "text-danger" : "text-ink"}`}>{p.low && <PackageMinus className="h-3.5 w-3.5" />}{p.qty_in_stock}</span></td>
                    <td className="px-2 text-right text-ink-soft">{p.storefront_qty || "—"}</td>
                    <td className="px-2 text-center">
                      <input type="number" min={0} defaultValue={p.reorder_threshold ?? 5} onChange={(e) => setThr({ ...thr, [p.product_id]: Number(e.target.value) })}
                        onBlur={() => { const t = thr[p.product_id]; if (t != null && t !== (p.reorder_threshold ?? 5)) setThreshold.mutate({ id: p.product_id, t }); }}
                        className="input w-14 !py-1 text-center text-xs" />
                    </td>
                    <td className="px-2 text-ink-soft">{p.supplier_name ? <span className="inline-flex items-center gap-1"><Building2 className="h-3 w-3" />{p.supplier_name}</span> : <span className="text-warn">no source</span>}</td>
                    <td className="px-2 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <input type="number" min={1} value={qty[p.product_id] ?? 20} onChange={(e) => setQty({ ...qty, [p.product_id]: Math.max(1, Number(e.target.value)) })} className="input w-14 !py-1 text-right text-xs" />
                        <button className="btn-gold !py-1 text-xs" disabled={!p.supplier_name || restock.isPending} onClick={() => restock.mutate({ id: p.product_id, quantity: qty[p.product_id] ?? 20 })}>{restock.isPending ? <Spinner className="h-3.5 w-3.5" /> : "Restock"}</button>
                      </div>
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

function Stat({ label, value, icon, tone }: { label: string; value: number; icon: React.ReactNode; tone?: "warn" | "emerald" }) {
  const ring = tone === "warn" ? "text-warn bg-warn/10" : tone === "emerald" ? "text-emerald-soft bg-emerald/10" : "text-gold-soft bg-gold/15";
  return (
    <Card className="flex items-center gap-3">
      <div className={`grid h-11 w-11 place-items-center rounded-xl ${ring}`}>{icon}</div>
      <div><div className="text-2xl font-800 text-ink">{value}</div><div className="text-xs text-ink-soft">{label}</div></div>
    </Card>
  );
}
