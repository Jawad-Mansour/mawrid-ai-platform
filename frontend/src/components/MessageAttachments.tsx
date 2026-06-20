// Feature: Inbound email attachments — download a supplier's emailed sheet, or send it
//          straight to enrichment (parses + stages it as a catalog document).
// API:     GET /catalog/attachment-url · POST /catalog/attachment/enrich
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileSpreadsheet, Download, Sparkles, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiErr } from "@/lib/api";

export interface MsgAttachment { filename: string; key: string; mime?: string | null; size?: number | null }

export function MessageAttachments({ attachments, supplierId, supplierName }: {
  attachments?: MsgAttachment[] | null; supplierId?: string; supplierName?: string | null;
}) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState<string | null>(null);
  if (!attachments || attachments.length === 0) return null;

  async function download(a: MsgAttachment) {
    setBusy(a.key + ":dl");
    try {
      const r = await apiGet<{ url: string }>(`/catalog/attachment-url?key=${encodeURIComponent(a.key)}`);
      window.open(r.url, "_blank", "noopener");
    } catch (e) { toast.error(apiErr(e, "Couldn't open the file")); }
    finally { setBusy(null); }
  }
  async function useForEnrichment(a: MsgAttachment) {
    setBusy(a.key + ":en");
    try {
      const r = await apiPost<{ document_id: string; filename: string; rows_extracted: number }>(
        "/catalog/attachment/enrich", { key: a.key, filename: a.filename, supplier_name: supplierName ?? null });
      toast.success(`${a.filename}: ${r.rows_extracted} row(s) ready to enrich`);
      navigate("/upload", { state: { stageDoc: { id: r.document_id, rows: r.rows_extracted, filename: r.filename }, supplierId } });
    } catch (e) { toast.error(apiErr(e, "Couldn't prepare the sheet")); }
    finally { setBusy(null); }
  }

  return (
    <div className="mt-2 space-y-1.5">
      {attachments.map((a) => (
        <div key={a.key} className="flex flex-wrap items-center gap-2 rounded-lg border border-line bg-black/20 px-2.5 py-1.5">
          <FileSpreadsheet className="h-4 w-4 shrink-0 text-emerald-soft" />
          <span className="min-w-0 flex-1 truncate text-xs text-ink">{a.filename}{a.size ? <span className="text-ink-faint"> · {Math.round(a.size / 1024)} KB</span> : null}</span>
          <button onClick={() => download(a)} disabled={busy === a.key + ":dl"} className="chip border-line bg-white/[0.03] text-ink-soft hover:text-ink">
            {busy === a.key + ":dl" ? <Loader2 className="h-3 w-3 animate-spin" /> : <Download className="h-3 w-3" />} Download
          </button>
          <button onClick={() => useForEnrichment(a)} disabled={busy === a.key + ":en"} className="chip border-grape/30 bg-grape/10 text-grape-soft hover:bg-grape/20">
            {busy === a.key + ":en" ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />} Use in enrichment
          </button>
        </div>
      ))}
    </div>
  );
}
