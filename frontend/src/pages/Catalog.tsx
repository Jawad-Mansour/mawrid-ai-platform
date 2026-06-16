// Feature: Catalog Enrichment — upload (supplier + drag-drop), enrich, rich product
//          listing with images/specs/sources, semantic search + highlight, basket.
// API:     POST /catalog/documents/upload · POST /catalog/documents/{id}/enrich
//          GET /catalog/products · GET /search/catalog
import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  UploadCloud, Search, Sparkles, RefreshCw, ImageOff, ShoppingBag, Check,
  ExternalLink, FileSpreadsheet, ArrowRight,
} from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { apiGet, apiPost, apiUpload, apiErr } from "@/lib/api";
import { Card, SectionTitle, StatusBadge, Loading, EmptyState } from "@/components/ui";
import { ProductModal } from "@/components/ProductModal";
import { useBasket } from "@/stores/basket";
import { formatCurrency } from "@/lib/utils";
import type { Product } from "@/lib/types";

function asList(d: unknown): Product[] {
  if (Array.isArray(d)) return d as Product[];
  if (d && typeof d === "object" && Array.isArray((d as any).products)) return (d as any).products;
  return [];
}

// highlight matched query terms
function Highlight({ text, q }: { text: string; q: string }) {
  if (!q.trim()) return <>{text}</>;
  const terms = q.trim().split(/\s+/).filter((t) => t.length > 1).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (terms.length === 0) return <>{text}</>;
  const re = new RegExp(`(${terms.join("|")})`, "ig");
  const parts = text.split(re);
  return <>{parts.map((p, i) => (re.test(p) ? <mark key={i} className="rounded bg-gold/30 px-0.5 text-ink">{p}</mark> : <span key={i}>{p}</span>))}</>;
}

const FILTERS = [
  { key: "all", label: "All" },
  { key: "enriched", label: "Enriched" },
  { key: "needs_review", label: "Needs review" },
  { key: "pending", label: "Enriching" },
  { key: "failed", label: "Failed" },
] as const;

export function Catalog() {
  const qc = useQueryClient();
  const basket = useBasket();
  const fileRef = useRef<HTMLInputElement>(null);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["key"]>("all");
  const [search, setSearch] = useState("");
  const [lastDoc, setLastDoc] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [supplierName, setSupplierName] = useState("");
  const [supplierLocation, setSupplierLocation] = useState("");
  const [open, setOpen] = useState<Product | null>(null);

  const products = useQuery({
    queryKey: ["catalog"],
    queryFn: () => apiGet<unknown>("/catalog/products?limit=200"),
    refetchInterval: 8000,
  });

  const enrich = useMutation({
    mutationFn: (docId: string) => apiPost<{ jobs_submitted: number; failed_rows: number }>(`/catalog/documents/${docId}/enrich`, {}),
    onSuccess: (r) => {
      toast.success(`${r.jobs_submitted} product(s) queued for AI enrichment`);
      qc.invalidateQueries({ queryKey: ["catalog"] });
    },
    onError: (e) => toast.error(apiErr(e, "Enrichment failed")),
  });

  const upload = useMutation({
    mutationFn: (file: File) =>
      apiUpload<{ document_id: string; rows_extracted: number }>("/catalog/documents/upload", file, {
        supplier_name: supplierName,
        supplier_location: supplierLocation,
      }),
    onSuccess: (r) => {
      setLastDoc(r.document_id);
      toast.success(`Parsed ${r.rows_extracted} row(s) — enriching now…`);
      qc.invalidateQueries({ queryKey: ["catalog"] });
      enrich.mutate(r.document_id);
    },
    onError: (e) => toast.error(apiErr(e, "Upload failed")),
  });

  const ACCEPT = [".pdf", ".xlsx", ".xls"];
  function takeFile(f: File | undefined) {
    if (!f) return;
    if (!ACCEPT.some((ext) => f.name.toLowerCase().endsWith(ext))) {
      toast.error("Only PDF or Excel (.pdf, .xlsx, .xls) files are supported.");
      return;
    }
    upload.mutate(f);
  }

  const all = useMemo(() => asList(products.data), [products.data]);
  const counts = useMemo(() => ({
    total: all.length,
    pending: all.filter((p) => p.enrichment_status === "pending").length,
    enriched: all.filter((p) => p.enrichment_status === "enriched").length,
  }), [all]);
  const enriching = counts.pending > 0;

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
      <SectionTitle
        title="Catalog Enrichment"
        subtitle="Drop a supplier sheet → AI fetches the real image, description & specs for each product"
        right={
          basket.items.length > 0 ? (
            <Link to="/procurement" className="btn-gold !py-2">
              <ShoppingBag className="h-4 w-4" /> {basket.items.length} noted <ArrowRight className="h-4 w-4" />
            </Link>
          ) : undefined
        }
      />

      {/* Upload */}
      <Card>
        <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
          <div>
            <input ref={fileRef} type="file" accept=".pdf,.xlsx,.xls" className="hidden"
              onChange={(e) => { takeFile(e.target.files?.[0]); e.target.value = ""; }} />
            <div
              role="button" tabIndex={0}
              onClick={() => !upload.isPending && fileRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
              onDrop={(e) => { e.preventDefault(); setDragOver(false); takeFile(e.dataTransfer.files?.[0]); }}
              className={`flex h-full min-h-[150px] cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-8 text-center transition-all ${
                dragOver ? "scale-[1.02] border-gold bg-gold/10 shadow-glow" : "border-line bg-white/[0.02] hover:border-gold/50 hover:bg-gold/5"
              } ${upload.isPending ? "pointer-events-none opacity-70" : ""}`}
            >
              <UploadCloud className={`h-9 w-9 text-gold transition-transform ${dragOver ? "scale-110" : ""}`} />
              <div>
                <div className="font-600 text-ink">{upload.isPending ? "Uploading…" : dragOver ? "Drop to upload" : "Drag & drop or click"}</div>
                <div className="mt-1 text-xs text-ink-faint">PDF or Excel · parsed instantly</div>
              </div>
            </div>
          </div>
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div><label className="label">Supplier name</label><input className="input" placeholder="e.g. Global Tech Distributors" value={supplierName} onChange={(e) => setSupplierName(e.target.value)} /></div>
              <div><label className="label">Supplier location</label><input className="input" placeholder="e.g. Dubai, UAE" value={supplierLocation} onChange={(e) => setSupplierLocation(e.target.value)} /></div>
            </div>
            {(enriching || enrich.isPending || (lastDoc && counts.total > 0)) && (
              <div className="rounded-xl border border-gold/30 bg-gold/5 p-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2 font-600 text-ink">
                    {enriching || enrich.isPending ? <Sparkles className="h-4 w-4 animate-pulse text-gold" /> : <FileSpreadsheet className="h-4 w-4 text-emerald-soft" />}
                    {enriching ? "Enriching with AI…" : enrich.isPending ? "Queuing…" : "Catalog ready"}
                  </span>
                  <span className="font-mono text-xs text-ink-soft">{counts.enriched}/{counts.total} done</span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full rounded-full bg-gold transition-all duration-700" style={{ width: `${counts.total ? (counts.enriched / counts.total) * 100 : 0}%` }} />
                </div>
                {counts.pending > 0 && <p className="mt-1.5 text-xs text-ink-faint">Running Icecat → web → GPT-4o for the real image, description & specs. Keeps going if you switch tabs.</p>}
              </div>
            )}
            <p className="text-xs leading-relaxed text-ink-faint">
              Each product is matched on Icecat, then web-researched for its real photo, description and specifications.
              Anything the AI can't confirm is routed to <span className="text-ink-soft">Needs review</span> for a human — never shown as a confident result.
            </p>
          </div>
        </div>
      </Card>

      {/* Search + filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
          <input className="input pl-9" placeholder="Search products, specs & descriptions…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <button onClick={() => products.refetch()} className="btn-ghost !py-2.5" title="Refresh"><RefreshCw className="h-4 w-4" /></button>
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button key={f.key} onClick={() => setFilter(f.key)}
              className={`chip ${filter === f.key ? "border-gold/50 bg-gold/15 text-gold-soft" : "border-line bg-white/[0.02] text-ink-soft hover:text-ink"}`}>
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Product grid */}
      {products.isLoading ? (
        <Loading />
      ) : rows.length === 0 ? (
        <EmptyState icon={<FileSpreadsheet className="h-8 w-8" />} title="No products yet"
          hint="Upload a supplier sheet above — the AI will build rich product cards with real images." />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {rows.map((p) => <ProductGridCard key={p.product_id} p={p} q={search} onOpen={() => setOpen(p)} />)}
        </div>
      )}

      {open && <ProductModal product={open} onClose={() => setOpen(null)} />}
    </div>
  );
}

function ProductGridCard({ p, q, onOpen }: { p: Product; q: string; onOpen: () => void }) {
  const basket = useBasket();
  const inBasket = basket.has(p.product_id);
  const [imgOk, setImgOk] = useState(true);
  const specs = Object.entries(p.specifications ?? {}).slice(0, 3);

  return (
    <div className="card group flex flex-col overflow-hidden p-0 transition-all hover:-translate-y-0.5 hover:shadow-glow">
      <button onClick={onOpen} className="relative grid aspect-[4/3] place-items-center bg-white/[0.03]">
        {p.image_url && imgOk ? (
          <img src={p.image_url} alt={p.product_name} className="h-full w-full object-contain p-4" loading="lazy" onError={() => setImgOk(false)} />
        ) : (
          <div className="flex flex-col items-center gap-1 text-ink-faint"><ImageOff className="h-7 w-7" /><span className="text-[10px]">no image</span></div>
        )}
        <div className="absolute left-2 top-2"><StatusBadge status={p.enrichment_status} /></div>
        {p.enrichment_source && <span className="chip absolute right-2 top-2 border-line bg-black/40 text-[10px] text-ink-soft">{p.enrichment_source}</span>}
      </button>

      <div className="flex flex-1 flex-col p-3.5">
        <button onClick={onOpen} className="text-left">
          <div className="line-clamp-2 text-sm font-700 leading-snug text-ink"><Highlight text={p.product_name} q={q} /></div>
          <div className="mt-0.5 font-mono text-[11px] text-ink-faint">{p.sku ?? "no sku"}</div>
        </button>

        {specs.length > 0 && (
          <div className="mt-2 space-y-0.5">
            {specs.map(([k, v]) => (
              <div key={k} className="flex justify-between gap-2 text-[11px]">
                <span className="truncate text-ink-faint">{k}</span>
                <span className="truncate text-right text-ink-soft">{String(v)}</span>
              </div>
            ))}
          </div>
        )}

        <div className="mt-auto flex items-center justify-between pt-3">
          <div className="text-sm font-700 text-ink">{p.price != null ? formatCurrency(p.price, p.currency ?? "USD") : <span className="text-xs text-ink-faint">—</span>}</div>
          <div className="flex items-center gap-1.5">
            {p.source_urls && p.source_urls.length > 0 && (
              <a href={p.source_urls[0].url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} title="Source" className="grid h-7 w-7 place-items-center rounded-lg border border-line text-ink-faint hover:text-ink"><ExternalLink className="h-3.5 w-3.5" /></a>
            )}
            <button
              onClick={() => basket.add(p)}
              title={inBasket ? "Noted for order" : "Note for order"}
              className={`grid h-7 w-7 place-items-center rounded-lg border transition-all ${inBasket ? "border-gold bg-gold text-bg" : "border-line text-ink-soft hover:border-gold/50 hover:text-gold-soft"}`}
            >
              {inBasket ? <Check className="h-3.5 w-3.5" /> : <ShoppingBag className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
