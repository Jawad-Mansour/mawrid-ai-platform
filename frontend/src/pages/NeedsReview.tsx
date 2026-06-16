// Feature: Catalog Enrichment — Needs Review: products the AI couldn't confirm.
//          A human approves (promote to enriched) or re-runs enrichment.
// API:     GET /catalog/products · POST /catalog/products/{id}/approve · /retry-enrichment
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldQuestion, ImageOff, Check, RefreshCw, Eye, Pencil } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiErr } from "@/lib/api";
import { Card, SectionTitle, Loading, EmptyState } from "@/components/ui";
import { ProductModal } from "@/components/ProductModal";
import { EditProductModal } from "@/components/EditProductModal";
import type { Product } from "@/lib/types";

function asList(d: unknown): Product[] {
  if (Array.isArray(d)) return d as Product[];
  if (d && typeof d === "object" && Array.isArray((d as any).products)) return (d as any).products;
  return [];
}

export function NeedsReview() {
  const qc = useQueryClient();
  const [open, setOpen] = useState<Product | null>(null);
  const [editing, setEditing] = useState<Product | null>(null);
  const products = useQuery({ queryKey: ["catalog"], queryFn: () => apiGet<unknown>("/catalog/products?limit=300"), refetchInterval: 8000 });
  const items = useMemo(() => asList(products.data).filter((p) => p.enrichment_status === "needs_review"), [products.data]);

  const approve = useMutation({
    mutationFn: (id: string) => apiPost(`/catalog/products/${id}/approve`, {}),
    onSuccess: () => { toast.success("Approved — moved to the catalogue"); qc.invalidateQueries({ queryKey: ["catalog"] }); },
    onError: (e) => toast.error(apiErr(e, "Approve failed")),
  });
  const reenrich = useMutation({
    mutationFn: (id: string) => apiPost(`/catalog/products/${id}/retry-enrichment`, {}),
    onSuccess: () => { toast.success("Re-enriching…"); qc.invalidateQueries({ queryKey: ["catalog"] }); },
    onError: (e) => toast.error(apiErr(e, "Re-enrich failed")),
  });

  return (
    <div className="space-y-6">
      <SectionTitle title="Needs Review" subtitle="The AI wasn't confident about these (missing image, thin details, or partial match). Confirm or re-run." />

      {products.isLoading ? (
        <Loading />
      ) : items.length === 0 ? (
        <Card><EmptyState icon={<ShieldQuestion className="h-8 w-8" />} title="Nothing to review" hint="Every enriched product met the confidence bar. 🎉" /></Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((p) => (
            <div key={p.product_id} className="card flex flex-col overflow-hidden p-0">
              <button onClick={() => setOpen(p)} className="relative grid aspect-[4/3] place-items-center bg-white">
                {p.image_url ? <img src={p.image_url} alt="" className="h-full w-full object-contain p-3" /> : <div className="flex flex-col items-center gap-1 text-ink-faint/60"><ImageOff className="h-7 w-7" /><span className="text-[10px]">no image found</span></div>}
                <span className="chip absolute left-2 top-2 border-warn/40 bg-warn/15 text-warn">needs review</span>
              </button>
              <div className="flex flex-1 flex-col p-3.5">
                <div className="line-clamp-2 text-sm font-700 text-ink">{p.product_name}</div>
                <div className="mt-0.5 font-mono text-[11px] text-ink-faint">{p.sku ?? "no sku"}</div>
                <ul className="mt-2 space-y-0.5 text-[11px] text-ink-faint">
                  {!p.image_url && <li>• No product image found</li>}
                  {(Object.keys(p.specifications ?? {}).length < 5) && <li>• Few specifications</li>}
                  {(!p.description || p.description.length < 220) && <li>• Thin description</li>}
                </ul>
                <div className="mt-auto flex gap-2 pt-3">
                  <button onClick={() => setEditing(p)} className="btn-ghost flex-1 !py-2 text-xs"><Pencil className="h-3.5 w-3.5" /> Edit</button>
                  <button onClick={() => setOpen(p)} className="btn-ghost !py-2 text-xs" title="View"><Eye className="h-3.5 w-3.5" /></button>
                  <button onClick={() => reenrich.mutate(p.product_id)} disabled={reenrich.isPending} className="btn-ghost !py-2 text-xs" title="Re-run enrichment"><RefreshCw className="h-3.5 w-3.5" /></button>
                  <button onClick={() => approve.mutate(p.product_id)} disabled={approve.isPending} className="btn-gold !py-2 text-xs"><Check className="h-3.5 w-3.5" /> Approve</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {open && <ProductModal product={open} onClose={() => setOpen(null)} />}
      {editing && <EditProductModal product={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}
