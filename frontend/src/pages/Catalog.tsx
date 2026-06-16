// Feature: Catalog Enrichment — upload, enrich, searchable internal catalog
import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UploadCloud, Search, Sparkles, FileSpreadsheet, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiUpload, apiErr } from "@/lib/api";
import { Card, SectionTitle, StatusBadge, Loading, EmptyState } from "@/components/ui";
import type { Product } from "@/lib/types";

function asList(d: unknown): Product[] {
  if (Array.isArray(d)) return d as Product[];
  if (d && typeof d === "object" && Array.isArray((d as any).products)) return (d as any).products;
  return [];
}

const FILTERS = ["all", "pending", "enriched", "published", "failed"] as const;

export function Catalog() {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  const [search, setSearch] = useState("");
  const [lastDoc, setLastDoc] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const ACCEPT = [".pdf", ".xlsx", ".xls"];
  function accepted(f: File) {
    return ACCEPT.some((ext) => f.name.toLowerCase().endsWith(ext));
  }
  function takeFile(f: File | undefined) {
    if (!f) return;
    if (!accepted(f)) { toast.error("Only PDF or Excel (.pdf, .xlsx, .xls) files are supported."); return; }
    upload.mutate(f);
  }

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
    mutationFn: (file: File) => apiUpload<{ document_id: string; rows_extracted: number }>("/catalog/documents/upload", file),
    onSuccess: (r) => {
      setLastDoc(r.document_id);
      toast.success(`Parsed ${r.rows_extracted} row(s) — enriching now…`);
      qc.invalidateQueries({ queryKey: ["catalog"] });
      // Auto-enrich: no second click needed, and progress is tracked server-side
      // (the products query below polls), so it survives switching tabs.
      enrich.mutate(r.document_id);
    },
    onError: (e) => toast.error(apiErr(e, "Upload failed")),
  });

  const all = useMemo(() => asList(products.data), [products.data]);
  const counts = useMemo(() => ({
    total: all.length,
    pending: all.filter((p) => p.enrichment_status === "pending").length,
    enriched: all.filter((p) => p.enrichment_status === "enriched").length,
    failed: all.filter((p) => p.enrichment_status === "failed").length,
  }), [all]);
  const enriching = counts.pending > 0;

  const rows = useMemo(() => {
    let list = asList(products.data);
    if (filter !== "all") list = list.filter((p) => (p.enrichment_status === filter) || (filter === "published" && p.storefront_status === "published"));
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((p) => p.product_name?.toLowerCase().includes(q) || p.sku?.toLowerCase().includes(q));
    }
    return list;
  }, [products.data, filter, search]);

  return (
    <div className="space-y-6">
      <SectionTitle title="Catalog Enrichment" subtitle="Drop a supplier sheet → AI builds your searchable internal catalog" />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.xlsx,.xls"
            className="hidden"
            onChange={(e) => { takeFile(e.target.files?.[0]); e.target.value = ""; }}
          />
          <div
            role="button"
            tabIndex={0}
            onClick={() => !upload.isPending && fileRef.current?.click()}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") fileRef.current?.click(); }}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); takeFile(e.dataTransfer.files?.[0]); }}
            className={`flex w-full cursor-pointer flex-col items-center gap-3 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-all ${
              dragOver ? "scale-[1.02] border-gold bg-gold/10 shadow-glow" : "border-line bg-white/[0.02] hover:border-gold/50 hover:bg-gold/5"
            } ${upload.isPending ? "pointer-events-none opacity-70" : ""}`}
          >
            <UploadCloud className={`h-10 w-10 text-gold transition-transform ${dragOver ? "scale-110" : ""}`} />
            <div>
              <div className="font-600 text-ink">{upload.isPending ? "Uploading…" : dragOver ? "Drop to upload" : "Drag & drop or click to upload"}</div>
              <div className="mt-1 text-xs text-ink-faint">PDF or Excel · parsed instantly</div>
            </div>
          </div>

          {/* Live enrichment progress — server-backed (polls every 8s), survives tab switches */}
          {(enriching || enrich.isPending || (lastDoc && counts.total > 0)) && (
            <div className="mt-4 rounded-xl border border-gold/30 bg-gold/5 p-4">
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
              {counts.pending > 0 && <p className="mt-2 text-xs text-ink-faint">{counts.pending} product(s) running Icecat → web → GPT-4o. This keeps going if you switch tabs.</p>}
              {lastDoc && (
                <button onClick={() => enrich.mutate(lastDoc)} disabled={enrich.isPending} className="btn-ghost mt-3 w-full !py-2 text-xs">
                  <RefreshCw className="h-3.5 w-3.5" /> Re-run enrichment
                </button>
              )}
            </div>
          )}

          <p className="mt-4 text-xs leading-relaxed text-ink-faint">
            Enrichment runs Icecat → web search → GPT-4o to fill specs & descriptions, then embeds each
            product for semantic search. Products stay in your internal catalog — publishing is a separate step.
          </p>
        </Card>

        <Card className="lg:col-span-2">
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <div className="relative min-w-[200px] flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
              <input className="input pl-9" placeholder="Search name or SKU…" value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            <button onClick={() => products.refetch()} className="btn-ghost !py-2.5" title="Refresh">
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
          <div className="mb-3 flex flex-wrap gap-2">
            {FILTERS.map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`chip capitalize ${filter === f ? "border-gold/50 bg-gold/15 text-gold-soft" : "border-line bg-white/[0.02] text-ink-soft hover:text-ink"}`}
              >
                {f}
              </button>
            ))}
          </div>

          {products.isLoading ? (
            <Loading />
          ) : rows.length === 0 ? (
            <EmptyState icon={<Boxesi />} title="No products yet" hint="Upload a supplier sheet and enrich it to populate your catalog." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs uppercase tracking-wider text-ink-faint">
                    <th className="py-2.5 pr-3 font-600">Product</th>
                    <th className="px-3 font-600">SKU</th>
                    <th className="px-3 font-600">Source</th>
                    <th className="px-3 font-600">Enrichment</th>
                    <th className="px-3 font-600">Storefront</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((p) => (
                    <tr key={p.product_id} className="table-row">
                      <td className="max-w-[280px] py-3 pr-3">
                        <div className="truncate font-600 text-ink">{p.product_name}</div>
                        {p.description && <div className="truncate text-xs text-ink-faint">{p.description}</div>}
                      </td>
                      <td className="px-3 font-mono text-xs text-ink-soft">{p.sku ?? "—"}</td>
                      <td className="px-3 text-xs text-ink-soft">{p.enrichment_source ?? "—"}</td>
                      <td className="px-3"><StatusBadge status={p.enrichment_status} /></td>
                      <td className="px-3"><StatusBadge status={p.storefront_status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function Boxesi() {
  return <FileSpreadsheet className="h-8 w-8" />;
}
