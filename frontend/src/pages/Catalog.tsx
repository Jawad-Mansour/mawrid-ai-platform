// Feature: Catalog Enrichment — Page 2: the enriched catalogue. Rich product cards
//          (image, description excerpt, specs, sources), NLP-style search with
//          highlighting, status filters, and a "note for order" basket.
// API:     GET /catalog/products
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, RefreshCw, ImageOff, ShoppingBag, Check, ExternalLink, FileSpreadsheet, ArrowRight, UploadCloud, Pencil, X, Building2, Layers, Package, Sparkles } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { apiGet } from "@/lib/api";
import { SectionTitle, StatusBadge, Loading, EmptyState, Spinner } from "@/components/ui";
import { ProductModal } from "@/components/ProductModal";
import { EditProductModal } from "@/components/EditProductModal";
import { useBasket } from "@/stores/basket";
import { formatCurrency } from "@/lib/utils";
import { matchesQuery, highlightTerms } from "@/lib/search";
import type { Product } from "@/lib/types";

interface SheetDoc { document_id: string; filename: string; supplier_name?: string | null; uploaded_at: string; rows_extracted: number }

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
  // highlight the typed terms AND their synonyms (so a "silver" search lights up "inox")
  const terms = highlightTerms(q).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
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
  const [supplier, setSupplier] = useState("all");
  const [groupBySheet, setGroupBySheet] = useState(false);
  const [open, setOpen] = useState<Product | null>(null);
  const [editing, setEditing] = useState<Product | null>(null);
  const [params, setParams] = useSearchParams();
  const docId = params.get("doc");

  const products = useQuery({ queryKey: ["catalog"], queryFn: () => apiGet<unknown>("/catalog/products?limit=300"), refetchInterval: 8000 });
  const docs = useQuery({ queryKey: ["documents"], queryFn: () => apiGet<SheetDoc[]>("/catalog/documents") });

  // AI semantic search — debounced; runs the RAG pipeline (embeddings + rerank) to rank
  // by meaning. Instant keyword matching still runs locally; semantic results lead.
  const [debounced, setDebounced] = useState("");
  useEffect(() => { const t = setTimeout(() => setDebounced(search.trim()), 600); return () => clearTimeout(t); }, [search]);
  const sem = useQuery({
    queryKey: ["catalog-search", debounced],
    queryFn: () => apiGet<{ results: { product_id: string; score: number }[] }>(`/search/catalog?q=${encodeURIComponent(debounced)}`),
    enabled: debounced.length >= 3,
    staleTime: 60_000, retry: false,
  });
  const semIds = useMemo(() => (debounced.length >= 3 ? (sem.data?.results.map((r) => r.product_id) ?? []) : []), [sem.data, debounced]);
  const all = useMemo(() => asList(products.data), [products.data]);
  const docList = useMemo(() => docs.data ?? [], [docs.data]);
  const activeSheet = docId ? docList.find((d) => d.document_id === docId) : null;

  // distinct suppliers across the catalogue (each sheet's supplier)
  const suppliers = useMemo(() => {
    const set = new Set<string>();
    all.forEach((p) => (p.supplier_names ?? []).forEach((s) => set.add(s)));
    return [...set].sort();
  }, [all]);

  const rows = useMemo(() => {
    let list = all;
    if (docId) list = list.filter((p) => (p.document_ids ?? []).includes(docId));
    if (filter !== "all") list = list.filter((p) => p.enrichment_status === filter);
    if (supplier !== "all") list = list.filter((p) => (p.supplier_names ?? []).includes(supplier));
    if (search.trim()) {
      const kw = list.filter((p) => matchesQuery(p, search));
      if (semIds.length) {
        // Semantic-ranked matches first (in RAG order), then any keyword-only matches.
        const rank = new Map(semIds.map((id, i) => [id, i] as const));
        const semSet = new Set(semIds);
        const semMatched = list.filter((p) => semSet.has(p.product_id)).sort((a, b) => (rank.get(a.product_id) ?? 0) - (rank.get(b.product_id) ?? 0));
        list = [...semMatched, ...kw.filter((p) => !semSet.has(p.product_id))];
      } else {
        list = kw;
      }
    }
    return list;
  }, [all, filter, search, supplier, docId, semIds]);

  // grouped view: each sheet's own catalogue, in upload order (newest first)
  const grouped = useMemo(() => {
    if (!groupBySheet) return [];
    const out: { doc: SheetDoc | null; items: Product[] }[] = [];
    for (const d of docList) {
      const items = rows.filter((p) => (p.document_ids ?? []).includes(d.document_id));
      if (items.length) out.push({ doc: d, items });
    }
    const orphans = rows.filter((p) => !(p.document_ids ?? []).some((id) => docList.find((d) => d.document_id === id)));
    if (orphans.length) out.push({ doc: null, items: orphans });
    return out;
  }, [groupBySheet, docList, rows]);

  function clearSheet() { const p = new URLSearchParams(params); p.delete("doc"); setParams(p, { replace: true }); }
  function gotoSheet(id: string) { const p = new URLSearchParams(params); p.set("doc", id); setParams(p, { replace: true }); }

  return (
    <div className="space-y-6">
      <SectionTitle title="Catalogue" subtitle="Your enriched products — each with a real image, full description, specs & sources."
        right={
          <div className="flex gap-2">
            <Link to="/upload" className="btn-ghost !py-2"><UploadCloud className="h-4 w-4" /> Upload sheet</Link>
            {basket.items.length > 0 && <Link to="/procurement" className="btn-gold !py-2"><ShoppingBag className="h-4 w-4" /> {basket.items.length} noted <ArrowRight className="h-4 w-4" /></Link>}
          </div>
        } />

      {/* per-sheet catalogue header */}
      {activeSheet && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-gold/30 bg-gold/[0.06] p-4">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-gold/15 text-gold-soft"><FileSpreadsheet className="h-5 w-5" /></div>
            <div>
              <div className="text-sm font-700 text-ink">{activeSheet.filename}</div>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-ink-soft">
                {activeSheet.supplier_name && <span className="flex items-center gap-1"><Building2 className="h-3 w-3" /> {activeSheet.supplier_name}</span>}
                <span>{new Date(activeSheet.uploaded_at).toLocaleString()}</span>
                <span>{rows.length} product(s)</span>
              </div>
            </div>
          </div>
          <button onClick={clearSheet} className="chip border-line bg-white/[0.03] text-ink-soft hover:text-ink"><X className="h-3 w-3" /> View whole catalogue</button>
        </div>
      )}

      {/* search + filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
          <input className="input pl-9 pr-28" placeholder="Search by meaning — e.g. 'energy-efficient front-load washer'…" value={search} onChange={(e) => setSearch(e.target.value)} />
          {debounced.length >= 3 && (
            <span className="absolute right-2.5 top-1/2 flex -translate-y-1/2 items-center gap-1 rounded-md border border-grape/30 bg-grape/10 px-1.5 py-0.5 text-[10px] font-700 text-grape-soft">
              {sem.isFetching ? <Spinner className="h-3 w-3" /> : <Sparkles className="h-3 w-3" />} {semIds.length ? "AI ranked" : sem.isFetching ? "AI…" : "AI search"}
            </span>
          )}
        </div>
        {suppliers.length > 0 && (
          <select className="input !w-auto !py-2.5" value={supplier} onChange={(e) => setSupplier(e.target.value)} title="Filter by supplier">
            <option value="all">All suppliers</option>
            {suppliers.map((s) => {
              const n = all.filter((p) => (p.supplier_names ?? []).includes(s)).length;
              return <option key={s} value={s}>{s} ({n})</option>;
            })}
          </select>
        )}
        <button onClick={() => products.refetch()} className="btn-ghost !py-2.5" title="Refresh"><RefreshCw className="h-4 w-4" /></button>
        {!docId && (
          <button onClick={() => setGroupBySheet((g) => !g)} title="Group products by the sheet they came from"
            className={`chip ${groupBySheet ? "border-gold/50 bg-gold/15 text-gold-soft" : "border-line bg-white/[0.02] text-ink-soft hover:text-ink"}`}>
            <Layers className="h-3.5 w-3.5" /> By sheet
          </button>
        )}
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
      ) : groupBySheet ? (
        <div className="space-y-8">
          {grouped.map(({ doc, items }) => (
            <div key={doc?.document_id ?? "orphans"}>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2">
                <div className="flex items-center gap-2.5">
                  <div className="grid h-9 w-9 place-items-center rounded-xl bg-gold/15 text-gold-soft"><FileSpreadsheet className="h-4.5 w-4.5" /></div>
                  <div>
                    <div className="text-sm font-700 text-ink">{doc?.filename ?? "Not from a sheet"}</div>
                    <div className="flex flex-wrap items-center gap-x-3 text-[11px] text-ink-soft">
                      {doc?.supplier_name && <span className="flex items-center gap-1"><Building2 className="h-3 w-3" /> {doc.supplier_name}</span>}
                      {doc && <span>{new Date(doc.uploaded_at).toLocaleDateString()}</span>}
                      <span>{items.length} product(s)</span>
                    </div>
                  </div>
                </div>
                {doc && <button onClick={() => gotoSheet(doc.document_id)} className="chip border-line bg-white/[0.03] text-ink-soft hover:text-ink">Open this sheet <ArrowRight className="h-3 w-3" /></button>}
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {items.map((p) => <ProductGridCard key={p.product_id} p={p} q={search} sheetId={doc?.document_id ?? null} onOpen={() => setOpen(p)} onEdit={() => setEditing(p)} />)}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {rows.map((p) => <ProductGridCard key={p.product_id} p={p} q={search} sheetId={docId} onOpen={() => setOpen(p)} onEdit={() => setEditing(p)} />)}
        </div>
      )}

      {open && <ProductModal key={open.product_id} product={open} onClose={() => setOpen(null)} />}
      {editing && <EditProductModal key={editing.product_id} product={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function ProductGridCard({ p, q, sheetId, onOpen, onEdit }: { p: Product; q: string; sheetId: string | null; onOpen: () => void; onEdit: () => void }) {
  const basket = useBasket();
  const inBasket = basket.has(p.product_id);
  const [imgOk, setImgOk] = useState(true);
  // Always render exactly 3 spec slots so every card has the same height.
  const specs = Object.entries(p.specifications ?? {}).filter(([k]) => !/^quantity$/i.test(k)).slice(0, 3);
  const excerpt = plain(p.description).slice(0, 120);
  const available = p.available_qty ?? null;

  return (
    <div className="card group flex h-full flex-col overflow-hidden p-0 transition-all hover:-translate-y-0.5 hover:shadow-glow">
      <button onClick={onOpen} className="relative grid aspect-[4/3] shrink-0 place-items-center overflow-hidden border-b border-line bg-white">
        {p.image_url && imgOk ? (
          <img src={p.image_url} alt={p.product_name} className="h-full w-full object-contain p-3" loading="lazy" onError={() => setImgOk(false)} />
        ) : (
          <div className="flex flex-col items-center gap-1 text-ink-faint/50"><ImageOff className="h-7 w-7" /><span className="text-[10px]">no image — edit to add</span></div>
        )}
        <div className="absolute left-2 top-2"><StatusBadge status={p.enrichment_status} /></div>
        {p.enrichment_source && <span className="chip absolute right-2 top-2 border-white/20 bg-black/55 text-[10px] font-600 text-white">{p.enrichment_source}</span>}
        {available != null && (
          <span className="absolute bottom-2 left-2 flex items-center gap-1 rounded-md bg-emerald/90 px-1.5 py-0.5 text-[10px] font-700 text-white shadow"><Package className="h-3 w-3" /> {available} avail.</span>
        )}
      </button>

      <div className="flex flex-1 flex-col p-3.5">
        <button onClick={onOpen} className="text-left">
          <div className="line-clamp-2 min-h-[2.4rem] text-sm font-700 leading-snug text-ink"><Highlight text={p.product_name} q={q} /></div>
          <div className="mt-0.5 truncate font-mono text-[11px] text-ink-faint">{p.sku ?? "no sku"}</div>
        </button>

        {/* description — always reserve 2 lines so cards align */}
        <p className="mt-1.5 line-clamp-2 min-h-[2.1rem] text-xs leading-relaxed text-ink-soft">{excerpt ? `${excerpt}…` : <span className="text-ink-faint">No description yet.</span>}</p>

        {/* specs — always reserve exactly 3 rows */}
        <div className="mt-2 min-h-[3.4rem] space-y-0.5">
          {specs.map(([k, v]) => (
            <div key={k} className="flex justify-between gap-2 text-[11px]">
              <span className="truncate text-ink-soft">{k}</span>
              <span className="truncate text-right font-600 text-ink">{String(v)}</span>
            </div>
          ))}
        </div>

        <div className="mt-auto flex items-center justify-between border-t border-line pt-3">
          <div className="text-sm font-700 text-ink">{p.price != null ? formatCurrency(p.price, p.currency ?? "USD") : <span className="text-xs text-ink-faint">no price</span>}</div>
          <div className="flex items-center gap-1.5">
            {p.source_urls && p.source_urls.length > 0 && (
              <a href={p.source_urls[0].url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} title="Source" className="grid h-7 w-7 place-items-center rounded-lg border border-line text-ink-faint hover:text-ink"><ExternalLink className="h-3.5 w-3.5" /></a>
            )}
            <button onClick={onEdit} title="Edit product" className="grid h-7 w-7 place-items-center rounded-lg border border-line text-ink-faint hover:border-gold/50 hover:text-gold-soft"><Pencil className="h-3.5 w-3.5" /></button>
            <button onClick={() => basket.add(p, sheetId)} title={inBasket ? "Noted for order" : "Note for order"}
              className={`grid h-7 w-7 place-items-center rounded-lg border transition-all ${inBasket ? "border-gold bg-gold text-bg" : "border-line text-ink-soft hover:border-gold/50 hover:text-gold-soft"}`}>
              {inBasket ? <Check className="h-3.5 w-3.5" /> : <ShoppingBag className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
