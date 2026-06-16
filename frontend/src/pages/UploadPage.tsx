// Feature: Catalog Enrichment — Page 1: upload a supplier sheet, save supplier
//          name/location, then trigger enrichment (one-by-one, background) with a
//          3D loading animation. Enrichment progress is read from the server, so it
//          keeps tracking even if you leave this tab and come back.
// API:     POST /catalog/documents/upload · POST /catalog/documents/{id}/enrich · GET /catalog/products
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { UploadCloud, FileSpreadsheet, Sparkles, ArrowRight, Building2, MapPin } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiUpload, apiErr } from "@/lib/api";
import { Card, SectionTitle } from "@/components/ui";
import { EnrichLoader, EnrichBox } from "@/components/EnrichLoader";
import type { Product } from "@/lib/types";

function asList(d: unknown): Product[] {
  if (Array.isArray(d)) return d as Product[];
  if (d && typeof d === "object" && Array.isArray((d as any).products)) return (d as any).products;
  return [];
}

export function UploadPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [supplierName, setSupplierName] = useState("");
  const [supplierLocation, setSupplierLocation] = useState("");
  const [doc, setDoc] = useState<{ id: string; rows: number; filename: string } | null>(null);
  const wasEnriching = useRef(false);

  // Server-derived progress — survives leaving and re-entering this tab.
  const products = useQuery({
    queryKey: ["catalog"],
    queryFn: () => apiGet<unknown>("/catalog/products?limit=300"),
    refetchInterval: 4000,
  });
  const all = asList(products.data);
  const pending = all.filter((p) => p.enrichment_status === "pending").length;
  const total = all.length;
  const done = total - pending;
  const enriching = pending > 0;

  useEffect(() => {
    if (enriching) wasEnriching.current = true;
    else if (wasEnriching.current) {
      wasEnriching.current = false;
      toast.success("Catalogue enriched — open the Catalogue to see it");
    }
  }, [enriching]);

  const ACCEPT = [".pdf", ".xlsx", ".xls"];
  const upload = useMutation({
    mutationFn: (file: File) =>
      apiUpload<{ document_id: string; rows_extracted: number; filename: string }>(
        "/catalog/documents/upload", file, { supplier_name: supplierName, supplier_location: supplierLocation },
      ),
    onSuccess: (r) => {
      setDoc({ id: r.document_id, rows: r.rows_extracted, filename: r.filename });
      toast.success(`Parsed ${r.rows_extracted} product row(s)`);
    },
    onError: (e) => toast.error(apiErr(e, "Upload failed")),
  });

  const enrich = useMutation({
    mutationFn: (docId: string) => apiPost<{ jobs_submitted: number; failed_rows: number }>(`/catalog/documents/${docId}/enrich`, {}),
    onSuccess: (r) => {
      setDoc(null);
      products.refetch();
      toast.success(`${r.jobs_submitted} product(s) queued — enriching one by one`);
    },
    onError: (e) => toast.error(apiErr(e, "Enrichment failed")),
  });

  function takeFile(f: File | undefined) {
    if (!f) return;
    if (!ACCEPT.some((ext) => f.name.toLowerCase().endsWith(ext))) {
      toast.error("Only PDF or Excel (.pdf, .xlsx, .xls) files are supported.");
      return;
    }
    upload.mutate(f);
  }

  // ── Enriching view (server-driven; persists across navigation) ──────────────
  if (enriching) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <SectionTitle title="Upload Supplier Sheet" subtitle="Enrichment is running in the background." />
        <Card>
          <EnrichLoader done={done} total={total} />
          <div className="mt-2 flex justify-center gap-3">
            <Link to="/catalog" className="btn-gold"><Sparkles className="h-4 w-4" /> Watch the catalogue fill <ArrowRight className="h-4 w-4" /></Link>
          </div>
          <p className="mt-3 text-center text-xs text-ink-faint">You can leave this page — enrichment keeps running and the bar will be up to date when you return.</p>
        </Card>
      </div>
    );
  }

  // ── Upload form (idle / parsed) ─────────────────────────────────────────────
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <SectionTitle title="Upload Supplier Sheet" subtitle="Drop a supplier price list (PDF or Excel). The AI builds a rich catalogue — real image, full description & specs for every product."
        right={total > 0 ? <Link to="/catalog" className="btn-ghost !py-2"><FileSpreadsheet className="h-4 w-4" /> {total} in catalogue</Link> : undefined} />

      {/* supplier details */}
      <Card>
        <SectionTitle title="Supplier details" subtitle="Saved with this sheet — used later for ordering." />
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="label"><Building2 className="mr-1 inline h-3.5 w-3.5" /> Supplier name</label>
            <input className="input" placeholder="e.g. Candy Hoover Group" value={supplierName} onChange={(e) => setSupplierName(e.target.value)} />
          </div>
          <div>
            <label className="label"><MapPin className="mr-1 inline h-3.5 w-3.5" /> Location</label>
            <input className="input" placeholder="e.g. Brugherio, Italy" value={supplierLocation} onChange={(e) => setSupplierLocation(e.target.value)} />
          </div>
        </div>
      </Card>

      {/* dropzone */}
      <Card>
        <input ref={fileRef} type="file" accept=".pdf,.xlsx,.xls" className="hidden"
          onChange={(e) => { takeFile(e.target.files?.[0]); e.target.value = ""; }} />
        {!doc ? (
          <div
            role="button" tabIndex={0}
            onClick={() => !upload.isPending && fileRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); takeFile(e.dataTransfer.files?.[0]); }}
            className={`flex min-h-[200px] cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-12 text-center transition-all ${
              dragOver ? "scale-[1.01] border-gold bg-gold/10 shadow-glow" : "border-line bg-white/[0.02] hover:border-gold/50 hover:bg-gold/5"
            } ${upload.isPending ? "pointer-events-none opacity-70" : ""}`}
          >
            <UploadCloud className={`h-12 w-12 text-gold transition-transform ${dragOver ? "scale-110" : ""}`} />
            <div>
              <div className="text-base font-700 text-ink">{upload.isPending ? "Uploading & parsing…" : dragOver ? "Drop to upload" : "Drag & drop your supplier sheet"}</div>
              <div className="mt-1 text-xs text-ink-faint">PDF or Excel (.pdf, .xlsx, .xls) · stored securely · parsed instantly</div>
            </div>
          </div>
        ) : (
          // parsed → show the open box + an explicit Enrich button (no overlap)
          <div className="flex flex-col items-center gap-5 py-2">
            <EnrichBox phase="open" />
            <div className="flex items-center gap-2 text-sm text-ink"><FileSpreadsheet className="h-4 w-4 text-emerald-soft" /> <span className="font-700">{doc.filename}</span> · {doc.rows} product row(s) extracted</div>
            <div className="flex gap-3">
              <button className="btn-gold" disabled={enrich.isPending} onClick={() => enrich.mutate(doc.id)}>
                <Sparkles className="h-4 w-4" /> {enrich.isPending ? "Starting…" : `Enrich ${doc.rows} product(s)`}
              </button>
              <button className="btn-ghost" onClick={() => { setDoc(null); fileRef.current?.click(); }}>Choose another</button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
