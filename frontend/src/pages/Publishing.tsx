// Feature: Storefront Publishing — enriched/in-stock -> published with retail price
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Store, Tag, EyeOff } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiDelete, apiErr } from "@/lib/api";
import { Card, SectionTitle, StatusBadge, Loading, EmptyState } from "@/components/ui";
import type { Product } from "@/lib/types";

function asList(d: unknown): Product[] {
  if (Array.isArray(d)) return d as Product[];
  if (d && typeof d === "object" && Array.isArray((d as any).products)) return (d as any).products;
  return [];
}

function PublishRow({ p, onDone }: { p: Product; onDone: () => void }) {
  const stock = p.qty_in_stock ?? 0;
  const [price, setPrice] = useState(p.retail_price ? String(p.retail_price) : "");
  const [qty, setQty] = useState(p.storefront_qty ? String(p.storefront_qty) : "");
  const published = p.storefront_status === "published";
  const visible = published ? (p.storefront_qty ?? 0) : Math.min(Number(qty || 0), stock);
  const reserved = Math.max(0, stock - visible);

  const publish = useMutation({
    mutationFn: () => apiPost(`/procurement/products/${p.product_id}/publish`, {
      retail_price: Number(price), storefront_qty: Math.min(Number(qty || 0), stock),
    }),
    onSuccess: () => { toast.success(`Published “${p.product_name}”`); onDone(); },
    onError: (e) => toast.error(apiErr(e, "Publish failed")),
  });
  const unpublish = useMutation({
    mutationFn: () => apiDelete(`/procurement/products/${p.product_id}/publish`),
    onSuccess: () => { toast.success("Removed from storefront"); onDone(); },
    onError: (e) => toast.error(apiErr(e, "Unpublish failed")),
  });

  return (
    <tr className="table-row">
      <td className="max-w-[240px] py-3 pr-3">
        <div className="truncate font-600 text-ink">{p.product_name}</div>
        <div className="truncate text-xs text-ink-faint">{p.sku ?? "—"}</div>
      </td>
      <td className="px-3"><StatusBadge status={p.storefront_status} /></td>
      <td className="px-3 text-center font-700 text-ink">{stock}</td>
      <td className="px-2">
        <div className="relative">
          <Tag className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint" />
          <input className="input w-24 pl-7 !py-1.5" placeholder="Price" value={price} onChange={(e) => setPrice(e.target.value)} />
        </div>
      </td>
      <td className="px-2"><input className="input w-20 !py-1.5 text-center" type="number" min={0} max={stock} placeholder="Qty" value={qty} onChange={(e) => setQty(String(Math.min(Number(e.target.value), stock)))} /></td>
      <td className="px-2 text-center"><span className="chip border-line bg-white/[0.03] text-ink-soft">{reserved} held</span></td>
      <td className="px-3 text-right">
        {published ? (
          <button className="btn-ghost !py-1.5" onClick={() => unpublish.mutate()}><EyeOff className="h-3.5 w-3.5" /> Unpublish</button>
        ) : (
          <button className="btn-emerald !py-1.5" disabled={!price || Number(qty) < 1} onClick={() => publish.mutate()}><Store className="h-3.5 w-3.5" /> Publish</button>
        )}
      </td>
    </tr>
  );
}

export function Publishing() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"ready" | "published">("ready");
  const q = useQuery({ queryKey: ["catalog-pub"], queryFn: () => apiGet<unknown>("/catalog/products?limit=200"), refetchInterval: 10_000 });

  const all = useMemo(() => asList(q.data).filter((p) => (p.qty_in_stock ?? 0) > 0), [q.data]);
  const rows = all.filter((p) => tab === "published" ? p.storefront_status === "published" : p.storefront_status !== "published");
  const refresh = () => qc.invalidateQueries({ queryKey: ["catalog-pub"] });

  return (
    <div className="space-y-6">
      <SectionTitle title="Storefront Publishing" subtitle="Publish from your inventory — hold back stock for wholesale by setting a visible quantity (e.g. 10 in stock → show 5, keep 5)." />
      <Card>
        <div className="mb-4 flex gap-2">
          {(["ready", "published"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`chip capitalize ${tab === t ? "border-gold/50 bg-gold/15 text-gold-soft" : "border-line bg-white/[0.02] text-ink-soft"}`}>
              {t === "ready" ? "Ready to publish" : "On storefront"}
            </button>
          ))}
        </div>
        {q.isLoading ? <Loading /> : rows.length === 0 ? (
          <EmptyState icon={<Store className="h-8 w-8" />} title={tab === "ready" ? "Nothing ready to publish" : "Storefront is empty"}
            hint={tab === "ready" ? "Enrich products and receive stock first." : "Publish products to populate your store."} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-xs uppercase tracking-wider text-ink-faint">
                <th className="py-2.5 pr-3 font-600">Product</th><th className="px-3 font-600">Storefront</th>
                <th className="px-3 text-center font-600">In stock</th><th className="px-2 font-600">Retail price</th>
                <th className="px-2 text-center font-600">Visible qty</th><th className="px-2 text-center font-600">Reserved</th><th className="px-3 font-600"></th>
              </tr></thead>
              <tbody>{rows.map((p) => <PublishRow key={p.product_id} p={p} onDone={refresh} />)}</tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
