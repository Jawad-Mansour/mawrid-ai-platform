// Feature: Catalog Enrichment — Page 2: the enriched catalogue. Rich product cards
//          (image, description excerpt, specs, sources), NLP-style search with
//          highlighting, status filters, and a "note for order" basket.
// API:     GET /catalog/products
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, RefreshCw, ImageOff, ShoppingBag, Check, ExternalLink, FileSpreadsheet, ArrowRight, UploadCloud, Pencil } from "lucide-react";
import { Link } from "react-router-dom";
import { apiGet } from "@/lib/api";
import { SectionTitle, StatusBadge, Loading, EmptyState } from "@/components/ui";
import { ProductModal } from "@/components/ProductModal";
import { EditProductModal } from "@/components/EditProductModal";
import { useBasket } from "@/stores/basket";
import { formatCurrency } from "@/lib/utils";
import type { Product } from "@/lib/types";

function asList(d: unknown): Product[] {
  if (Array.isArray(d)) return d as Product[];
  if (d && typeof d === "object" && Array.isArray((d as any).products)) return (d as any).products;
  return [];
}
function plain(md: string | null | undefined): string {
  if (!md) return "";
  return md.replace(/[#*_>`\-]/g, " ").replace(/\[(.*?)\]\(.*?\)/g, "$1").replace(/\s+/g, " ").trim();
}
function Highlight({ text, q }: { text: string; q: string }) {
  if (!q.trim()) return <>{text}</>;
  const terms = q.trim().split(/\s+/).filter((t) => t.length > 1).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (terms.length === 0) return <>{text}</>;
  const re = new RegExp(`(${terms.join("|")})`, "ig");
  return <>{text.split(re).map((p, i) => (re.test(p) ? <mark key={i} className="rounded bg-gold/30 px-0.5 text-ink">{p}</mark> : <span key={i}>{p}</span>))}</>;
}

const FILTERS = [
  { key: "all", label: "All" },
  { key: "enriched", label: "Enriched" },
  { key: "needs_review", label: "Needs review" },
  { key: "pending", label: "Enriching" },
  { key: "failed", label: "Failed" },
] as const;

export function Catalog() {
  const basket = useBasket();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["key"]>("all");
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState<Product | null>(null);
  const [editing, setEditing] = useState<Product | null>(null);

  const products = useQuery({ queryKey: ["catalog"], queryFn: () => apiGet<unknown>("/catalog/products?limit=300"), refetchInterval: 8000 });
  const all = useMemo(() => asList(products.data), [products.data]);

  const rows = useMemo(() => {
    let list = all;
    if (filter !== "all") list = list.filter((p) => p.enrichment_status === filter);
    const q = search.trim().toLowerCase();
    if (q) {
      list = list.filter((p) =>
        p.product_name?.toLowerCase().includes(q) || p.sku?.toLowerCase().includes(q) ||
        (p.description ?? "").toLowerCase().includes(q) ||
        JSON.stringify(p.specifications ?? {}).toLowerCase().includes(q));
    }
    return list;
  }, [all, filter, search]);

  return (
    <div className="space-y-6">
      <SectionTitle title="Catalogue" subtitle="Your enriched products — each with a real image, full description, specs & sources."
        right={
          <div className="flex gap-2">
            <Link to="/upload" className="btn-ghost !py-2"><UploadCloud className="h-4 w-4" /> Upload sheet</Link>
            {basket.items.length > 0 && <Link to="/procurement" className="btn-gold !py-2"><ShoppingBag className="h-4 w-4" /> {basket.items.length} noted <ArrowRight className="h-4 w-4" /></Link>}
          </div>
        } />

      {/* search + filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
          <input className="input pl-9" placeholder="Search products, specs & descriptions…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <button onClick={() => products.refetch()} className="btn-ghost !py-2.5" title="Refresh"><RefreshCw className="h-4 w-4" /></button>
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button key={f.key} onClick={() => setFilter(f.key)}
              className={`chip ${filter === f.key ? "border-gold/50 bg-gold/15 text-gold-soft" : "border-line bg-white/[0.02] text-ink-soft hover:text-ink"}`}>{f.label}</button>
          ))}
        </div>
      </div>

      {products.isLoading ? (
        <Loading />
      ) : rows.length === 0 ? (
        <EmptyState icon={<FileSpreadsheet className="h-8 w-8" />} title="No products yet"
          hint="Upload a supplier sheet to build your catalogue — the AI fetches real images, descriptions and specs." />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {rows.map((p) => <ProductGridCard key={p.product_id} p={p} q={search} onOpen={() => setOpen(p)} onEdit={() => setEditing(p)} />)}
        </div>
      )}

      {open && <ProductModal product={open} onClose={() => setOpen(null)} />}
      {editing && <EditProductModal product={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function ProductGridCard({ p, q, onOpen, onEdit }: { p: Product; q: string; onOpen: () => void; onEdit: () => void }) {
  const basket = useBasket();
  const inBasket = basket.has(p.product_id);
  const [imgOk, setImgOk] = useState(true);
  // Always render exactly 3 spec slots so every card has the same height.
  const specs = Object.entries(p.specifications ?? {}).slice(0, 3);
  const excerpt = plain(p.description).slice(0, 120);

  return (
    <div className="card group flex h-full flex-col overflow-hidden p-0 transition-all hover:-translate-y-0.5 hover:shadow-glow">
      <button onClick={onOpen} className="relative grid aspect-[4/3] shrink-0 place-items-center bg-white">
        {p.image_url && imgOk ? (
          <img src={p.image_url} alt={p.product_name} className="h-full w-full object-contain p-3" loading="lazy" onError={() => setImgOk(false)} />
        ) : (
          <div className="flex flex-col items-center gap-1 text-ink-faint/50"><ImageOff className="h-7 w-7" /><span className="text-[10px]">no image — edit to add</span></div>
        )}
        <div className="absolute left-2 top-2"><StatusBadge status={p.enrichment_status} /></div>
        {p.enrichment_source && <span className="chip absolute right-2 top-2 border-white/20 bg-black/55 text-[10px] font-600 text-white">{p.enrichment_source}</span>}
      </button>

      <div className="flex flex-1 flex-col p-3.5">
        <button onClick={onOpen} className="text-left">
          <div className="line-clamp-2 min-h-[2.4rem] text-sm font-700 leading-snug text-ink"><Highlight text={p.product_name} q={q} /></div>
          <div className="mt-0.5 font-mono text-[11px] text-ink-faint">{p.sku ?? "no sku"}</div>
        </button>

        {/* description — always reserve 2 lines so cards align */}
        <p className="mt-1.5 line-clamp-2 min-h-[2.1rem] text-xs leading-relaxed text-ink-soft">{excerpt ? `${excerpt}…` : <span className="text-ink-faint">No description yet.</span>}</p>

        {/* specs — always reserve 3 rows */}
        <div className="mt-2 min-h-[3.4rem] space-y-0.5">
          {specs.map(([k, v]) => (
            <div key={k} className="flex justify-between gap-2 text-[11px]">
              <span className="truncate text-ink-faint">{k}</span>
              <span className="truncate text-right font-500 text-ink-soft">{String(v)}</span>
            </div>
          ))}
        </div>

        <div className="mt-auto flex items-center justify-between border-t border-line pt-3">
          <div className="text-sm font-700 text-ink">{p.price != null ? formatCurrency(p.price, p.currency ?? "USD") : <span className="text-xs text-ink-faint">—</span>}</div>
          <div className="flex items-center gap-1.5">
            {p.source_urls && p.source_urls.length > 0 && (
              <a href={p.source_urls[0].url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} title="Source" className="grid h-7 w-7 place-items-center rounded-lg border border-line text-ink-faint hover:text-ink"><ExternalLink className="h-3.5 w-3.5" /></a>
            )}
            <button onClick={onEdit} title="Edit product" className="grid h-7 w-7 place-items-center rounded-lg border border-line text-ink-faint hover:border-gold/50 hover:text-gold-soft"><Pencil className="h-3.5 w-3.5" /></button>
            <button onClick={() => basket.add(p)} title={inBasket ? "Noted for order" : "Note for order"}
              className={`grid h-7 w-7 place-items-center rounded-lg border transition-all ${inBasket ? "border-gold bg-gold text-bg" : "border-line text-ink-soft hover:border-gold/50 hover:text-gold-soft"}`}>
              {inBasket ? <Check className="h-3.5 w-3.5" /> : <ShoppingBag className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
