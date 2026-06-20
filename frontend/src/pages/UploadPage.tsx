// Feature: Catalog Enrichment — Page 1: upload sheets (no gate), then for each sheet
//          pick an existing supplier OR create a new one, and enrich. Enriching a sheet
//          makes that supplier one you do business with.
// API:     POST /catalog/documents/upload · POST /catalog/documents/{id}/enrich ·
//          GET /catalog/products · GET /suppliers
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { UploadCloud, FileSpreadsheet, Sparkles, ArrowRight, CheckCircle2, X, Trash2, Loader2, Plus, AlertTriangle, Pencil } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiPatch, apiUpload, apiErr } from "@/lib/api";
import { Card, SectionTitle } from "@/components/ui";
import { EnrichLoader } from "@/components/EnrichLoader";
import { SupplierEditModal } from "@/components/SupplierEditModal";
import type { Product, Supplier } from "@/lib/types";

function asList(d: unknown): Product[] {
  if (Array.isArray(d)) return d as Product[];
  if (d && typeof d === "object" && Array.isArray((d as any).products)) return (d as any).products;
  return [];
}
function asSuppliers(d: unknown): Supplier[] { return Array.isArray(d) ? (d as Supplier[]) : []; }
const isEmail = (e: string) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e.trim());

interface Sup { name: string; email: string; location: string }
interface Sheet { id: string; rows: number; filename: string; enriched: boolean; sup: Sup }

export function UploadPage() {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [params] = useSearchParams();
  const location = useLocation();
  const seededStage = useRef(false);
  const [dragOver, setDragOver] = useState(false);
  // Persist staged sheets so they survive navigating away and back.
  const [sheets, setSheets] = useState<Sheet[]>(() => {
    try { return JSON.parse(localStorage.getItem("mawrid_upload_sheets") || "[]") as Sheet[]; } catch { return []; }
  });
  useEffect(() => { localStorage.setItem("mawrid_upload_sheets", JSON.stringify(sheets)); }, [sheets]);
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState<{ sheetId: string } | null>(null);
  const [activeTs, setActiveTs] = useState<number>(() => Number(localStorage.getItem("mawrid_enrich_active") || 0));
  const markActive = () => { const t = Date.now(); localStorage.setItem("mawrid_enrich_active", String(t)); setActiveTs(t); };
  const clearActive = () => { localStorage.removeItem("mawrid_enrich_active"); setActiveTs(0); };

  const [kick, setKick] = useState(false); // optimistic: show the loader the instant Enrich is clicked
  const products = useQuery({ queryKey: ["catalog"], queryFn: () => apiGet<unknown>("/catalog/products?limit=300"), refetchInterval: 2000 });
  const suppliersQ = useQuery({ queryKey: ["suppliers"], queryFn: () => apiGet<unknown>("/suppliers") });
  const suppliers = asSuppliers(suppliersQ.data);
  const all = asList(products.data);
  const pending = all.filter((p) => p.enrichment_status === "pending").length;
  const total = all.length;
  const done = total - pending;
  const enriching = pending > 0 || kick;
  const showDone = !enriching && activeTs > 0 && total > 0 && Date.now() - activeTs > 6000;
  // once real pending products appear, hand the loader over to the live count
  useEffect(() => { if (pending > 0) setKick(false); }, [pending]);

  // convo → enrichment handoff: ?supplier=<id> prefills new sheets with that supplier
  const presetId = params.get("supplier");
  const preset: Sup | null = presetId ? (() => { const s = suppliers.find((x) => x.supplier_id === presetId); return s ? { name: s.name, email: s.email ?? "", location: s.location ?? "" } : null; })() : null;

  const ACCEPT = [".pdf", ".xlsx", ".xls"];
  const ready = (s: Sup) => s.name.trim().length > 1 && s.location.trim().length > 0 && isEmail(s.email);

  async function takeFiles(files: FileList | File[] | null) {
    if (!files) return;
    const list = Array.from(files).filter((f) => ACCEPT.some((ext) => f.name.toLowerCase().endsWith(ext)));
    if (Array.from(files).length - list.length > 0) toast.error("Some files skipped — only PDF/Excel (.pdf, .xlsx, .xls).");
    if (list.length === 0) return;
    setBusy(true);
    for (const file of list) {
      try {
        const r = await apiUpload<{ document_id: string; rows_extracted: number; filename: string; already_existed?: boolean }>("/catalog/documents/upload", file, {});
        setSheets((s) => s.some((x) => x.id === r.document_id) ? s : [...s, { id: r.document_id, rows: r.rows_extracted, filename: r.filename, enriched: false, sup: preset ? { ...preset } : { name: "", email: "", location: "" } }]);
        toast.success(`${r.filename}: ${r.rows_extracted} row(s)${r.already_existed ? " (already uploaded)" : ""}`);
      } catch (e) { toast.error(apiErr(e, `Upload failed for ${file.name}`)); }
    }
    setBusy(false);
  }

  const enrichOne = useMutation({
    mutationFn: (s: Sheet) => apiPost<{ jobs_submitted: number }>(`/catalog/documents/${s.id}/enrich`, { supplier_name: s.sup.name, supplier_email: s.sup.email, supplier_location: s.sup.location }),
    onMutate: () => { setKick(true); markActive(); }, // instant feedback before the request returns
    onSuccess: (r, s) => { setSheets((x) => x.map((y) => (y.id === s.id ? { ...y, enriched: true } : y))); products.refetch(); toast.success(`${r.jobs_submitted} product(s) queued`); setTimeout(() => setKick(false), 8000); },
    onError: (e) => { setKick(false); toast.error(apiErr(e, "Enrichment failed")); },
  });
  async function enrichAll() { for (const s of sheets.filter((x) => !x.enriched && ready(x.sup))) await enrichOne.mutateAsync(s); }
  const setSup = (id: string, patch: Partial<Sup>) => setSheets((s) => s.map((x) => (x.id === id ? { ...x, sup: { ...x.sup, ...patch } } : x)));
  function pickSupplier(sheetId: string, supplierId: string) {
    const s = suppliers.find((x) => x.supplier_id === supplierId);
    if (s) setSup(sheetId, { name: s.name, email: s.email ?? "", location: s.location ?? "" });
  }

  // Persist a sheet's supplier to its DOCUMENT the moment its info is complete — so the supplier
  // (name · email · location) shows up in Upload History and everywhere, without waiting for enrich.
  const persistedSig = useRef<Record<string, string>>({});
  const persistSup = useMutation({
    mutationFn: ({ id, sup }: { id: string; sup: Sup }) =>
      apiPatch(`/catalog/documents/${id}/supplier`, { supplier_name: sup.name, supplier_email: sup.email, supplier_location: sup.location }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["documents"] }); qc.invalidateQueries({ queryKey: ["suppliers"] }); },
  });
  useEffect(() => {
    for (const s of sheets) {
      if (s.enriched || !ready(s.sup)) continue;
      const sig = `${s.sup.name}|${s.sup.email}|${s.sup.location}`;
      if (persistedSig.current[s.id] === sig) continue;
      persistedSig.current[s.id] = sig;
      persistSup.mutate({ id: s.id, sup: s.sup });
    }
  }, [sheets]); // eslint-disable-line react-hooks/exhaustive-deps

  // Staged from "Use in enrichment" on an emailed sheet → add the already-parsed document to
  // the list, prefilled with its supplier, so the user can enrich it straight away.
  useEffect(() => {
    const st = (location.state as { stageDoc?: { id: string; rows: number; filename: string }; supplierId?: string } | null) || {};
    const sd = st.stageDoc;
    if (!sd || seededStage.current || suppliersQ.isLoading) return;
    seededStage.current = true;
    const sup = st.supplierId ? suppliers.find((x) => x.supplier_id === st.supplierId) : undefined;
    const supObj: Sup = sup ? { name: sup.name, email: sup.email ?? "", location: sup.location ?? "" } : { name: "", email: "", location: "" };
    setSheets((s) => (s.some((x) => x.id === sd.id) ? s : [...s, { id: sd.id, rows: sd.rows, filename: sd.filename, enriched: false, sup: supObj }]));
    toast.success(`${sd.filename} added — set the supplier and enrich`);
  }, [location.state, suppliersQ.isLoading, suppliers]); // eslint-disable-line react-hooks/exhaustive-deps

  // when a new supplier is created from the modal, attach it to the sheet
  useEffect(() => { suppliersQ.refetch(); }, [modal]); // eslint-disable-line react-hooks/exhaustive-deps

  if (showDone) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <SectionTitle title="Upload Supplier Sheets" />
        <Card>
          <button onClick={clearActive} className="float-right grid h-8 w-8 place-items-center rounded-lg text-ink-faint hover:text-ink" title="Dismiss"><X className="h-4 w-4" /></button>
          <div className="flex flex-col items-center gap-4 py-8 text-center">
            <motion.div initial={{ scale: 0, rotate: -90 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: "spring", stiffness: 200, damping: 14 }}><CheckCircle2 className="h-16 w-16 text-emerald-soft" /></motion.div>
            <div><div className="text-xl font-800 text-ink">Catalogue enriched 🎉</div><div className="mt-1 text-sm text-ink-soft">{total} product(s) now have real images, descriptions and specs.</div></div>
            <div className="flex flex-wrap justify-center gap-3">
              <Link to="/catalog" className="btn-gold" onClick={clearActive}><FileSpreadsheet className="h-4 w-4" /> Open catalogue <ArrowRight className="h-4 w-4" /></Link>
              <button className="btn-ghost" onClick={() => { clearActive(); setSheets([]); }}>Upload more sheets</button>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  if (enriching) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <SectionTitle title="Upload Supplier Sheets" subtitle="Enrichment is running in the background." />
        <Card>
          <EnrichLoader done={done} total={total} />
          <div className="mt-2 flex justify-center gap-3"><Link to="/catalog" className="btn-gold"><Sparkles className="h-4 w-4" /> Watch the catalogue fill <ArrowRight className="h-4 w-4" /></Link></div>
          <p className="mt-3 text-center text-xs text-ink-faint">You can leave this page — enrichment keeps running and the bar will be up to date when you return.</p>
        </Card>
      </div>
    );
  }

  const pendingReady = sheets.filter((s) => !s.enriched && ready(s.sup)).length;
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <SectionTitle title="Upload Supplier Sheets" subtitle="Drop your sheets, then for each one pick an existing supplier or create a new one, and enrich."
        right={total > 0 ? <Link to="/catalog" className="btn-ghost !py-2"><FileSpreadsheet className="h-4 w-4" /> {total} in catalogue</Link> : undefined} />

      <Card>
        <input ref={fileRef} type="file" accept=".pdf,.xlsx,.xls" multiple className="hidden" onChange={(e) => { takeFiles(e.target.files); e.target.value = ""; }} />
        <div role="button" tabIndex={0} onClick={() => !busy && fileRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }} onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); takeFiles(e.dataTransfer.files); }}
          className={`flex min-h-[170px] cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-all ${dragOver ? "scale-[1.01] border-gold bg-gold/10 shadow-glow" : "border-line bg-white/[0.02] hover:border-gold/50 hover:bg-gold/5"} ${busy ? "pointer-events-none opacity-70" : ""}`}>
          <UploadCloud className={`h-12 w-12 text-gold transition-transform ${dragOver ? "scale-110" : ""}`} />
          <div><div className="text-base font-700 text-ink">{busy ? "Uploading & parsing…" : dragOver ? "Drop to upload" : "Drag & drop one or more supplier sheets"}</div>
            <div className="mt-1 text-xs text-ink-faint">PDF or Excel · multiple files · stored securely · parsed instantly</div></div>
        </div>
      </Card>

      {sheets.length > 0 && (
        <Card>
          <SectionTitle title={`${sheets.length} sheet(s) ready to enrich`} subtitle="Each sheet needs a supplier (name · valid email · location) before it can enrich."
            right={pendingReady > 0 ? <button className="btn-gold !py-2" disabled={enrichOne.isPending} onClick={enrichAll}><Sparkles className="h-4 w-4" /> Enrich {pendingReady} ready</button> : undefined} />
          <div className="space-y-3">
            {sheets.map((s) => {
              const chosen = s.sup.name.trim().length > 0;
              const ok = ready(s.sup);
              return (
              <div key={s.id} className="rounded-xl border border-line bg-white/[0.02] p-3">
                <div className="mb-2 flex items-center gap-2">
                  <FileSpreadsheet className="h-5 w-5 shrink-0 text-emerald-soft" />
                  <div className="min-w-0 flex-1"><div className="truncate text-sm font-700 text-ink">{s.filename}</div><div className="text-[11px] text-ink-faint">{s.rows} product row(s)</div></div>
                  {s.enriched ? <span className="chip border-emerald/30 bg-emerald/10 text-emerald-soft"><Loader2 className="h-3 w-3 animate-spin" /> Enriching</span>
                    : <button className="btn-gold !py-1.5 text-xs" disabled={!ok || enrichOne.isPending} onClick={() => enrichOne.mutate(s)} title={ok ? "Enrich this sheet" : "Set the supplier first"}><Sparkles className="h-3.5 w-3.5" /> Enrich</button>}
                  <button onClick={() => setSheets((x) => x.filter((y) => y.id !== s.id))} title="Remove from list" className="text-ink-faint hover:text-danger"><Trash2 className="h-4 w-4" /></button>
                </div>
                {!s.enriched && !chosen && (
                  // No supplier yet — pick an existing one OR create a new one (modal).
                  <div className="flex flex-wrap items-center gap-2">
                    <select className="input !py-1.5 min-w-[200px] flex-1 text-xs" value="" onChange={(e) => e.target.value && pickSupplier(s.id, e.target.value)}>
                      <option value="">Pick an existing supplier…</option>
                      {suppliers.map((x) => <option key={x.supplier_id} value={x.supplier_id}>{x.name}{x.location ? ` — ${x.location}` : ""}</option>)}
                    </select>
                    <span className="text-xs text-ink-faint">or</span>
                    <button onClick={() => setModal({ sheetId: s.id })} className="btn-ghost shrink-0 !py-1.5 text-xs"><Plus className="h-3.5 w-3.5" /> New supplier</button>
                  </div>
                )}
                {!s.enriched && chosen && (
                  // Supplier chosen — show a compact summary; only reveal fields still missing.
                  <div className="rounded-lg border border-line bg-white/[0.02] p-2.5">
                    <div className="flex items-center gap-2">
                      <div className={`grid h-7 w-7 shrink-0 place-items-center rounded-lg ${ok ? "bg-emerald/15 text-emerald-soft" : "bg-warn/15 text-warn"}`}>{ok ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}</div>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-700 text-ink">{s.sup.name}</div>
                        <div className="truncate text-[11px] text-ink-faint">{[s.sup.location, s.sup.email].filter(Boolean).join(" · ") || "needs email + location"}</div>
                      </div>
                      <button onClick={() => setSup(s.id, { name: "", email: "", location: "" })} className="flex shrink-0 items-center gap-1 text-xs text-ink-faint underline hover:text-ink"><Pencil className="h-3 w-3" /> Change</button>
                    </div>
                    {!ok && (
                      <div className="mt-2 grid gap-2 sm:grid-cols-2">
                        {!s.sup.location.trim() && <input className="input !py-1.5 text-xs" placeholder="Location *" value={s.sup.location} onChange={(e) => setSup(s.id, { location: e.target.value })} />}
                        {!isEmail(s.sup.email) && <input className={`input !py-1.5 text-xs ${s.sup.email && !isEmail(s.sup.email) ? "!border-danger/60" : ""}`} type="email" placeholder="Email *" value={s.sup.email} onChange={(e) => setSup(s.id, { email: e.target.value })} />}
                      </div>
                    )}
                  </div>
                )}
              </div>
              );
            })}
          </div>
        </Card>
      )}

      {modal && <SupplierEditModal supplier={null} onClose={() => setModal(null)}
        onSaved={(s) => setSup(modal.sheetId, { name: s.name, email: s.email ?? "", location: s.location ?? "" })} />}
    </div>
  );
}
