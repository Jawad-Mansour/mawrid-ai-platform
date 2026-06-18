// Feature: Procurement — Review & Send (Screen 2). Two sections side by side:
//          (1) the ORDER SPREADSHEET — fully editable (qty + unit price per line,
//          remove lines), built from the original sheet's products & prices, with a
//          live order cost; (2) the formal REQUEST EMAIL (editable). Approving sends
//          the email to the supplier with the up-to-date Excel attached.
// API:     GET/PUT/POST /hitl/actions/{id} · POST /procurement/order-excel
import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { Send, FileSpreadsheet, Download, X, Check, Mail, Building2, ArrowLeft, Sparkles, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiPut, apiErr, apiClient } from "@/lib/api";
import { Card, SectionTitle, Loading, Spinner } from "@/components/ui";
import { formatCurrency } from "@/lib/utils";

interface POAction { action_id: string; action_type: string; status: string; payload: Record<string, any> }
interface Line { product_id?: string; product_name?: string; sku?: string | null; quantity: number; unit_price: number; currency?: string }

export function OrderReview() {
  const { actionId } = useParams();
  const navigate = useNavigate();
  const action = useQuery({ queryKey: ["hitl-action", actionId], queryFn: () => apiGet<POAction>(`/hitl/actions/${actionId}`), enabled: !!actionId });
  const [bodyEdit, setBodyEdit] = useState<string | null>(null);
  const [lines, setLines] = useState<Line[] | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  const a = action.data;
  const p = a?.payload ?? {};
  // hydrate editable lines + email once the action loads
  useEffect(() => {
    if (a && lines === null) setLines((p.line_items ?? []).map((l: any) => ({ ...l, quantity: Number(l.quantity ?? 0), unit_price: Number(l.unit_price ?? 0) })));
    if (a && email === null) setEmail(String(p.to ?? ""));
  }, [a]); // eslint-disable-line react-hooks/exhaustive-deps

  if (action.isLoading) return <Loading label="Loading the draft…" />;
  const currency = p.currency ?? "USD";
  const body = bodyEdit ?? String(p.body ?? "");
  const rows = lines ?? [];
  const total = rows.reduce((s, l) => s + (l.quantity || 0) * (l.unit_price || 0), 0);
  const alreadyHandled = a && a.status !== "pending";

  function setLine(i: number, patch: Partial<Line>) {
    setLines((ls) => (ls ?? []).map((l, j) => (j === i ? { ...l, ...patch } : l)));
  }
  function removeLine(i: number) { setLines((ls) => (ls ?? []).filter((_, j) => j !== i)); }

  const toAddr = (email ?? String(p.to ?? "")).trim();
  async function persistEdits() {
    await apiPut(`/hitl/actions/${actionId}`, { payload: { ...p, to: toAddr, body, line_items: rows, total } });
  }
  async function approve() {
    if (rows.length === 0) { toast.error("Add at least one line."); return; }
    if (!toAddr) { toast.error("Enter the supplier's email to send."); return; }
    setSending(true);
    try {
      // if the supplier had no email on file, save the one entered here for next time
      if (!p.to && toAddr && p.supplier_id) {
        try { await apiPut(`/suppliers/${p.supplier_id}`, { email: toAddr }); } catch { /* non-fatal */ }
      }
      await persistEdits();
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
      const res = await apiClient.post(`/procurement/order-excel`, {
        line_items: rows, supplier_name: p.supplier_name ?? "Supplier", po_number: p.po_number ?? "ORDER", currency,
      }, { responseType: "blob" });
      const url = URL.createObjectURL(res.data as Blob);
      const link = document.createElement("a");
      link.href = url; link.download = `${p.po_number ?? "order"}.xlsx`; link.click();
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

      <SectionTitle title="Review & Send" subtitle="The AI wrote this request. Edit the spreadsheet or the email, then approve to send it with the Excel attached."
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
        <div className="grid gap-6 lg:grid-cols-[1.1fr_1fr]">
          {/* the editable spreadsheet */}
          <Card>
            <SectionTitle title="Order spreadsheet" subtitle={`${p.po_number ?? ""} · ${p.supplier_name ?? ""} — edit quantities or prices`}
              right={<button onClick={downloadExcel} className="btn-ghost !py-2 text-xs"><Download className="h-3.5 w-3.5" /> Excel</button>} />
            <div className="mb-3 flex items-center gap-2 rounded-xl border border-emerald/30 bg-emerald/10 p-2.5 text-xs text-emerald-soft">
              <FileSpreadsheet className="h-4 w-4" /> {p.po_number ?? "order"}.xlsx will be attached to the email.
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-line text-left text-xs uppercase tracking-wider text-ink-faint">
                  <th className="py-2 pr-2 font-600">Code</th><th className="px-2 font-600">Product</th>
                  <th className="px-2 text-right font-600">Qty</th><th className="px-2 text-right font-600">Unit</th>
                  <th className="px-2 text-right font-600">Total</th><th></th>
                </tr></thead>
                <tbody>
                  {rows.map((l, i) => (
                    <tr key={i} className="border-b border-line/60">
                      <td className="py-2 pr-2 font-mono text-xs text-ink-soft">{l.sku ?? l.product_id?.slice(0, 8)}</td>
                      <td className="max-w-[150px] px-2"><span className="line-clamp-1 text-ink">{l.product_name}</span></td>
                      <td className="px-2 text-right">
                        <input type="number" min={1} value={l.quantity} onChange={(e) => setLine(i, { quantity: Math.max(0, Number(e.target.value)) })}
                          className="input w-16 !py-1 text-right text-xs" />
                      </td>
                      <td className="px-2 text-right">
                        <input type="number" min={0} step="0.01" value={l.unit_price} onChange={(e) => setLine(i, { unit_price: Math.max(0, Number(e.target.value)) })}
                          className="input w-20 !py-1 text-right text-xs" />
                      </td>
                      <td className="px-2 text-right font-mono text-ink">{formatCurrency((l.quantity || 0) * (l.unit_price || 0), currency)}</td>
                      <td className="pl-1"><button onClick={() => removeLine(i)} className="text-ink-faint hover:text-danger"><Trash2 className="h-3.5 w-3.5" /></button></td>
                    </tr>
                  ))}
                  {rows.length === 0 && <tr><td colSpan={6} className="py-6 text-center text-ink-faint">No lines — rejecting is the only option.</td></tr>}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex justify-between border-t border-line pt-3 text-base font-800 text-ink">
              <span>Order cost</span><span className="font-mono">{formatCurrency(total, currency)}</span>
            </div>
          </Card>

          {/* the formal email */}
          <Card>
            <SectionTitle title="Request email" right={<span className="chip border-grape/30 bg-grape/10 text-grape-soft"><Sparkles className="h-3 w-3" /> AI-drafted</span>} />
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <Mail className="h-4 w-4 shrink-0 text-ink-faint" />
                <span className="shrink-0 text-ink-soft">To:</span>
                <input className={`input !py-1.5 text-sm ${!toAddr ? "!border-warn/60" : ""}`} type="email"
                  placeholder="supplier@email.com" value={email ?? ""} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div className="flex items-center gap-2 text-ink-soft"><Building2 className="h-4 w-4 text-ink-faint" /> {p.supplier_name} · {p.language?.toUpperCase?.() ?? "EN"}</div>
              <div className="text-xs text-ink-faint">Subject: {p.subject}</div>
            </div>
            <textarea
              className="input mt-3 min-h-[300px] resize-y font-sans leading-relaxed"
              value={body}
              onChange={(e) => setBodyEdit(e.target.value)}
            />
            {!p.to && (
              <p className="mt-2 text-xs text-warn">⚠ This supplier had no email on file — enter one above. It will be saved to the supplier for next time.</p>
            )}
            <div className="mt-4 flex gap-3">
              <button className="btn-gold flex-1" disabled={sending || !toAddr || rows.length === 0} onClick={approve}>
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
