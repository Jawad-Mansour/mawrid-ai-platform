// Feature: Catalog Enrichment — Page 1: upload a supplier sheet, save supplier
//          name/location, then trigger enrichment (one-by-one, background) with a
//          3D loading animation.
// API:     POST /catalog/documents/upload · POST /catalog/documents/{id}/enrich · GET /catalog/products
import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { UploadCloud, FileSpreadsheet, Sparkles, ArrowRight, CheckCircle2, Building2, MapPin } from "lucide-react";
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

type Step = "idle" | "parsed" | "enriching" | "done";

export function UploadPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<Step>("idle");
  const [dragOver, setDragOver] = useState(false);
  const [supplierName, setSupplierName] = useState("");
  const [supplierLocation, setSupplierLocation] = useState("");
  const [doc, setDoc] = useState<{ id: string; rows: number; filename: string } | null>(null);
  const [target, setTarget] = useState(0);
  const baselineRef = useRef(0);

  const products = useQuery({
    queryKey: ["catalog"],
    queryFn: () => apiGet<unknown>("/catalog/products?limit=300"),
    refetchInterval: step === "enriching" ? 4000 : false,
  });

  const enrichedCount = useMemo(
    () => asList(products.data).filter((p) => p.enrichment_status === "enriched" || p.enrichment_status === "needs_review").length,
    [products.data],
  );
  const done = Math.min(Math.max(enrichedCount - baselineRef.current, 0), target || 1);
  // flip to "done" once the queued batch has all resolved
  if (step === "enriching" && target > 0 && done >= target) setTimeout(() => setStep("done"), 0);

  const ACCEPT = [".pdf", ".xlsx", ".xls"];
  const upload = useMutation({
    mutationFn: (file: File) =>
      apiUpload<{ document_id: string; rows_extracted: number; filename: string }>(
        "/catalog/documents/upload", file, { supplier_name: supplierName, supplier_location: supplierLocation },
      ),
    onSuccess: (r) => {
      setDoc({ id: r.document_id, rows: r.rows_extracted, filename: r.filename });
      setStep("parsed");
      toast.success(`Parsed ${r.rows_extracted} product row(s)`);
    },
    onError: (e) => toast.error(apiErr(e, "Upload failed")),
  });

  const enrich = useMutation({
    mutationFn: (docId: string) => apiPost<{ jobs_submitted: number; failed_rows: number }>(`/catalog/documents/${docId}/enrich`, {}),
    onSuccess: (r) => {
      baselineRef.current = asList(products.data).filter((p) => p.enrichment_status === "enriched" || p.enrichment_status === "needs_review").length;
      setTarget(r.jobs_submitted || doc?.rows || 1);
      setStep(r.jobs_submitted > 0 ? "enriching" : "done");
      toast.success(`${r.jobs_submitted} product(s) queued — enriching now`);
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
  function reset() { setStep("idle"); setDoc(null); setTarget(0); }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <SectionTitle title="Upload Supplier Sheet" subtitle="Drop a supplier price list (PDF or Excel). The AI builds a rich catalogue — real image, full description & specs for every product." />

      {step === "enriching" ? (
        <Card>
          <EnrichLoader done={done} total={target} />
          <div className="mt-2 flex justify-center gap-3">
            <Link to="/catalog" className="btn-gold"><Sparkles className="h-4 w-4" /> Watch the catalogue fill <ArrowRight className="h-4 w-4" /></Link>
            <button className="btn-ghost" onClick={() => setStep("done")}>Run in background</button>
          </div>
        </Card>
      ) : step === "done" ? (
        <Card>
          <div className="flex flex-col items-center gap-4 py-6 text-center">
            <CheckCircle2 className="h-14 w-14 text-emerald-soft" />
            <div>
              <div className="text-xl font-800 text-ink">Catalogue enriched</div>
              <div className="mt-1 text-sm text-ink-faint">Your products now have real images, descriptions and specifications.</div>
            </div>
            <div className="flex gap-3">
              <Link to="/catalog" className="btn-gold"><FileSpreadsheet className="h-4 w-4" /> Open catalogue <ArrowRight className="h-4 w-4" /></Link>
              <button className="btn-ghost" onClick={reset}>Upload another sheet</button>
            </div>
          </div>
        </Card>
      ) : (
        <>
          {/* supplier details (saved with the upload) */}
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

            {step === "parsed" && doc && <EnrichBox phase="open" />}
            {step === "parsed" && doc && (
              <div className="mt-4 flex flex-col items-center gap-3 rounded-xl border border-gold/30 bg-gold/5 p-4 sm:flex-row sm:justify-between">
                <div className="flex items-center gap-3">
                  <FileSpreadsheet className="h-8 w-8 text-emerald-soft" />
                  <div>
                    <div className="text-sm font-700 text-ink">{doc.filename}</div>
                    <div className="text-xs text-ink-faint">{doc.rows} product row(s) extracted{supplierName ? ` · ${supplierName}` : ""}</div>
                  </div>
                </div>
                <button className="btn-gold w-full sm:w-auto" disabled={enrich.isPending} onClick={() => enrich.mutate(doc.id)}>
                  <Sparkles className="h-4 w-4" /> {enrich.isPending ? "Starting…" : `Enrich ${doc.rows} product(s)`}
                </button>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
