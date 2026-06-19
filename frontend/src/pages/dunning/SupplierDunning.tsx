// Feature: Financial — Supplier Dunning. The two real supplier-side money flows:
//          Payables (we owe a supplier → advance reminder) and Disputes (damaged/short
//          goods → formal claim). Each draft is HITL: approve to send a real email.
// API:     GET /hitl/actions?status=pending · POST /dunning/trigger/track1 ·
//          POST /hitl/actions/{id}/approve|reject
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Banknote, FileWarning, Check, X, Send, Building2, PlayCircle, ClipboardList, Download } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiErr, apiClient } from "@/lib/api";
import { Card, SectionTitle, Loading, EmptyState, Spinner } from "@/components/ui";
import type { HITLAction } from "@/lib/types";

const PAYABLE = "dunning_payables_advance";
const DISPUTE = "dispute_letter";

export function SupplierDunning() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"payables" | "disputes">("payables");
  const q = useQuery({ queryKey: ["hitl-all"], queryFn: () => apiGet<HITLAction[]>("/hitl/actions?status=pending"), refetchInterval: 12_000 });
  const actions = Array.isArray(q.data) ? q.data.filter((a) => a.status === "pending") : [];
  const payables = useMemo(() => actions.filter((a) => a.action_type === PAYABLE), [actions]);
  const disputes = useMemo(() => actions.filter((a) => a.action_type === DISPUTE), [actions]);

  const runPayables = useMutation({
    mutationFn: () => apiPost<{ created?: string[] }>("/dunning/trigger/track1", {}),
    onSuccess: (r) => { toast.success(`${r.created?.length ?? 0} payables reminder(s) drafted`); qc.invalidateQueries({ queryKey: ["hitl-all"] }); },
    onError: (e) => toast.error(apiErr(e, "Could not run payables")),
  });
  const approve = useMutation({ mutationFn: (id: string) => apiPost(`/hitl/actions/${id}/approve`, {}), onSuccess: () => { toast.success("Sent to supplier"); qc.invalidateQueries({ queryKey: ["hitl-all"] }); }, onError: (e) => toast.error(apiErr(e, "Send failed")) });
  const reject = useMutation({ mutationFn: (id: string) => apiPost(`/hitl/actions/${id}/reject`, {}), onSuccess: () => { toast("Rejected"); qc.invalidateQueries({ queryKey: ["hitl-all"] }); }, onError: (e) => toast.error(apiErr(e, "Reject failed")) });

  async function downloadReport(shipmentId: string, po: string) {
    try {
      const res = await apiClient.get(`/procurement/shipments/${shipmentId}/receipt-pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data as Blob); const a = document.createElement("a");
      a.href = url; a.download = `receipt-${po}.pdf`; a.click(); URL.revokeObjectURL(url);
    } catch (e) { toast.error(apiErr(e, "Couldn't download the report")); }
  }

  const list = tab === "payables" ? payables : disputes;

  return (
    <div className="space-y-6">
      <SectionTitle title="Supplier Dunning" subtitle="Money flows with your suppliers — every message is drafted by AI and sent only after you approve."
        right={<Link to="/dunning/customer" className="btn-ghost !py-2"><Banknote className="h-4 w-4" /> Customer dunning</Link>} />

      <div className="flex gap-1 rounded-2xl border border-line bg-white/[0.02] p-1">
        {([{ k: "payables", label: "Payables", icon: Banknote, n: payables.length }, { k: "disputes", label: "Disputes", icon: FileWarning, n: disputes.length }] as const).map((t) => (
          <button key={t.k} onClick={() => setTab(t.k)} className={`flex flex-1 items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-600 transition-all ${tab === t.k ? "bg-gold/15 text-gold-soft" : "text-ink-soft hover:text-ink"}`}>
            <t.icon className="h-4 w-4" /> {t.label} {t.n > 0 && <span className="grid h-5 min-w-5 place-items-center rounded-full bg-gold/20 px-1 text-[10px] font-700 text-gold-soft">{t.n}</span>}
          </button>
        ))}
      </div>

      {tab === "payables" && (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><div className="text-sm font-700 text-ink">Pay your suppliers on time</div><div className="text-xs text-ink-soft">Drafts a reminder ~3 days before each supplier invoice is due.</div></div>
            <button className="btn-gold !py-2" disabled={runPayables.isPending} onClick={() => runPayables.mutate()}>{runPayables.isPending ? <Spinner className="h-4 w-4" /> : <PlayCircle className="h-4 w-4" />} Run payables check</button>
          </div>
        </Card>
      )}
      {tab === "disputes" && (
        <div className="flex items-start gap-2 rounded-xl border border-line bg-white/[0.02] p-3 text-xs text-ink-soft">
          <FileWarning className="mt-0.5 h-4 w-4 shrink-0 text-warn" /> Disputes are filed from <Link to="/inventory/receive" className="text-gold-soft underline">Receive Goods</Link> when items arrive damaged or short. They appear here for approval.
        </div>
      )}

      <Card>
        <SectionTitle title={tab === "payables" ? "Payable reminders to send" : "Dispute letters to send"} subtitle="Approve to email the supplier." />
        {q.isLoading ? <Loading /> : list.length === 0 ? (
          <EmptyState icon={tab === "payables" ? <Banknote className="h-8 w-8" /> : <FileWarning className="h-8 w-8" />} title="Nothing pending" hint={tab === "payables" ? "Run a payables check, or you're all caught up." : "No disputes filed."} />
        ) : (
          <div className="space-y-3">
            {list.map((a) => (
              <div key={a.action_id} className="rounded-xl border border-line bg-white/[0.02] p-3.5">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-sm font-700 text-ink"><Building2 className="h-3.5 w-3.5 text-ink-faint" /> {a.payload.supplier_name ?? a.payload.to ?? "Supplier"}</div>
                  <span className="text-xs text-ink-faint">{a.payload.subject}</span>
                </div>
                <div className="max-h-[160px] overflow-y-auto whitespace-pre-wrap rounded-lg border border-line bg-black/20 p-3 text-xs text-ink-soft">{String(a.payload.body ?? a.payload.draft ?? "")}</div>
                {(a.payload.po_id || a.payload.shipment_id) && (
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
                    {a.payload.po_reference && <span className="font-mono text-ink-faint">PO {String(a.payload.po_reference)}</span>}
                    {a.payload.po_id && <Link to={`/purchase-orders/${a.payload.po_id}`} className="chip border-grape/30 bg-grape/10 text-grape-soft hover:bg-grape/20"><ClipboardList className="h-3 w-3" /> Open order</Link>}
                    {a.payload.shipment_id && <button onClick={() => downloadReport(String(a.payload.shipment_id), String(a.payload.po_reference ?? "report"))} className="chip border-line bg-white/[0.03] text-ink-soft hover:text-ink"><Download className="h-3 w-3" /> Report PDF</button>}
                  </div>
                )}
                <div className="mt-3 flex gap-2">
                  <button className="btn-gold !py-1.5 text-xs" disabled={!a.payload.to || approve.isPending} onClick={() => approve.mutate(a.action_id)}><Send className="h-3.5 w-3.5" /> Approve & send</button>
                  <button className="btn-danger !py-1.5 text-xs" disabled={reject.isPending} onClick={() => reject.mutate(a.action_id)}><X className="h-3.5 w-3.5" /> Reject</button>
                  {!a.payload.to && <span className="self-center text-[11px] text-warn">no email on file</span>}
                  {a.payload.to && <span className="self-center text-[11px] text-ink-faint"><Check className="mr-0.5 inline h-3 w-3" />{a.payload.to}</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
