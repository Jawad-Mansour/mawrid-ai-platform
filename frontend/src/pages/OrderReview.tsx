// Feature: Procurement — Review & Send (Screen 2). Shows the AI-drafted request
//          email (editable) + the generated Excel (codes · qty · sum); approve sends
//          it to the supplier with the spreadsheet attached (via HITL approve).
// API:     GET/PUT/POST /hitl/actions/{id} · GET /procurement/orders/{id}/excel
import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { Send, FileSpreadsheet, Download, X, Check, Mail, Building2, ArrowLeft, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiPut, apiErr, apiClient } from "@/lib/api";
import { Card, SectionTitle, Loading, Spinner } from "@/components/ui";
import { formatCurrency } from "@/lib/utils";

interface POAction { action_id: string; action_type: string; status: string; payload: Record<string, any> }

export function OrderReview() {
  const { actionId } = useParams();
  const navigate = useNavigate();
  const action = useQuery({ queryKey: ["hitl-action", actionId], queryFn: () => apiGet<POAction>(`/hitl/actions/${actionId}`), enabled: !!actionId });
  const [bodyEdit, setBodyEdit] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  if (action.isLoading) return <Loading label="Loading the draft…" />;
  const a = action.data;
  const p = a?.payload ?? {};
  const lines: any[] = p.line_items ?? [];
  const currency = p.currency ?? "USD";
  const body = bodyEdit ?? String(p.body ?? "");
  const alreadyHandled = a && a.status !== "pending";

  async function approve() {
    setSending(true);
    try {
      if (bodyEdit != null && bodyEdit !== p.body) {
        await apiPut(`/hitl/actions/${actionId}`, { payload: { ...p, body: bodyEdit } });
      }
      await apiPost(`/hitl/actions/${actionId}/approve`, {});
      setSent(true);
      setTimeout(() => navigate("/purchase-orders"), 1500);
    } catch (e) {
      toast.error(apiErr(e, "Could not send"));
      setSending(false);
    }
  }
  async function reject() {
    try { await apiPost(`/hitl/actions/${actionId}/reject`, {}); toast("Order rejected"); navigate("/procurement"); }
    catch (e) { toast.error(apiErr(e, "Reject failed")); }
  }
  async function downloadExcel() {
    try {
      const res = await apiClient.get(`/procurement/orders/${p.order_id}/excel`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data as Blob);
      const link = document.createElement("a");
      link.href = url; link.download = p.attachment_filename || "order.xlsx"; link.click();
      URL.revokeObjectURL(url);
    } catch (e) { toast.error(apiErr(e, "Download failed")); }
  }

  return (
    <div className="space-y-6">
      <AnimatePresence>
        {sent && (
          <motion.div className="fixed inset-0 z-[100] grid place-items-center bg-page/85 backdrop-blur-md" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <motion.div className="flex flex-col items-center gap-3" initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: "spring", stiffness: 200, damping: 14 }}>
              <motion.div className="grid h-20 w-20 place-items-center rounded-full bg-gradient-to-br from-gold to-grape shadow-glow" animate={{ rotate: [0, -12, 0] }} transition={{ duration: 0.8, repeat: 1 }}>
                <Send className="h-9 w-9 text-bg" />
              </motion.div>
              <div className="text-lg font-800 text-ink">Sent to {p.supplier_name} 🎉</div>
              <div className="text-sm text-ink-faint">The request + spreadsheet are on their way.</div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <SectionTitle title="Review & Send" subtitle="The AI wrote this request. Edit anything, then approve to send it with the Excel attached."
        right={<Link to="/procurement" className="btn-ghost !py-2"><ArrowLeft className="h-4 w-4" /> Back</Link>} />

      {alreadyHandled ? (
        <Card>
          <div className="flex flex-col items-center gap-3 py-12 text-center">
            <Check className="h-12 w-12 text-emerald-soft" />
            <div className="text-lg font-700 text-ink">This order was already {a!.status}.</div>
            <Link to="/purchase-orders" className="btn-gold">View Purchase Orders</Link>
          </div>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
          {/* the spreadsheet */}
          <Card>
            <SectionTitle title="Order spreadsheet" subtitle={`${p.po_number ?? ""} · ${p.supplier_name ?? ""}`}
              right={<button onClick={downloadExcel} className="btn-ghost !py-2 text-xs"><Download className="h-3.5 w-3.5" /> Excel</button>} />
            <div className="mb-3 flex items-center gap-2 rounded-xl border border-emerald/30 bg-emerald/10 p-2.5 text-xs text-emerald-soft">
              <FileSpreadsheet className="h-4 w-4" /> {p.attachment_filename ?? "order.xlsx"} will be attached to the email.
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-line text-left text-xs uppercase tracking-wider text-ink-faint">
                  <th className="py-2 pr-2 font-600">Code</th><th className="px-2 font-600">Product</th>
                  <th className="px-2 text-right font-600">Qty</th><th className="px-2 text-right font-600">Total</th>
                </tr></thead>
                <tbody>
                  {lines.map((l, i) => (
                    <tr key={i} className="table-row">
                      <td className="py-2 pr-2 font-mono text-xs text-ink-soft">{l.sku ?? l.product_id?.slice(0, 8)}</td>
                      <td className="max-w-[180px] px-2"><span className="line-clamp-1 text-ink">{l.product_name}</span></td>
                      <td className="px-2 text-right font-mono text-ink">{l.quantity}</td>
                      <td className="px-2 text-right font-mono text-ink">{formatCurrency((l.quantity ?? 0) * (l.unit_price ?? 0), currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex justify-between border-t border-line pt-3 text-base font-800 text-ink">
              <span>Total</span><span className="font-mono">{formatCurrency(Number(p.total ?? 0), currency)}</span>
            </div>
          </Card>

          {/* the email */}
          <Card>
            <SectionTitle title="Request email" right={<span className="chip border-grape/30 bg-grape/10 text-grape-soft"><Sparkles className="h-3 w-3" /> AI-drafted</span>} />
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2 text-ink-soft"><Mail className="h-4 w-4 text-ink-faint" /> To: <span className="font-600 text-ink">{p.to || "— (no supplier email)"}</span></div>
              <div className="flex items-center gap-2 text-ink-soft"><Building2 className="h-4 w-4 text-ink-faint" /> {p.supplier_name} · {p.language?.toUpperCase?.() ?? "EN"}</div>
              <div className="text-xs text-ink-faint">Subject: {p.subject}</div>
            </div>
            <textarea
              className="input mt-3 min-h-[280px] resize-y font-sans leading-relaxed"
              value={body}
              onChange={(e) => setBodyEdit(e.target.value)}
            />
            {!p.to && <p className="mt-2 text-xs text-warn">⚠ This supplier has no email on file — add one in Suppliers before sending.</p>}
            <div className="mt-4 flex gap-3">
              <button className="btn-gold flex-1" disabled={sending || !p.to} onClick={approve}>
                {sending ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />} Approve & send
              </button>
              <button className="btn-danger" disabled={sending} onClick={reject}><X className="h-4 w-4" /> Reject</button>
            </div>
            <p className="mt-2 text-center text-[11px] text-ink-faint">Approving records the PO and emails the supplier with the spreadsheet attached.</p>
          </Card>
        </div>
      )}
    </div>
  );
}
