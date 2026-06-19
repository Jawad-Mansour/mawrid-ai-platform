// Feature: Procurement — PO email thread (Screen 3). Tracks the conversation with
//          the supplier: the request we sent, replies received (logged), and our
//          AI-assisted replies back.
// API:     GET /procurement/purchase-orders/{id} · POST .../messages · .../draft-reply · .../reply
import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowLeft, Send, Sparkles, Inbox, Building2, ClipboardList, MessageSquarePlus, Settings2, Trash2, CalendarCheck, CheckCircle2, Save, AlertTriangle, Pencil } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiPatch, apiErr } from "@/lib/api";
import { Card, SectionTitle, Loading, StatusBadge, Spinner } from "@/components/ui";
import { formatCurrency } from "@/lib/utils";

interface OrderLine { product_id?: string; product_name?: string; sku?: string | null; quantity: number; unit_price: number; currency?: string }

interface Extracted { intent: string; wants_changes: boolean; change_summary: string; arrival_date: string | null; promised_payment_date: string | null; summary: string }
interface Msg { direction: string; sender: string; body: string; at: string; extracted?: Extracted }
interface PODetail {
  po_id: string; po_number: string; supplier_id: string; supplier_name: string | null; supplier_email: string | null;
  status: string; total_amount: number | null; currency: string; po_text: string | null; line_items: any[];
  hitl_action_id: string | null; sent_at: string | null; created_at: string; messages: Msg[];
}

export function POThread() {
  const { poId } = useParams();
  const qc = useQueryClient();
  const po = useQuery({ queryKey: ["po", poId], queryFn: () => apiGet<PODetail>(`/procurement/purchase-orders/${poId}`), enabled: !!poId, refetchInterval: 8000 });
  const [logBody, setLogBody] = useState("");
  const [reply, setReply] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [lines, setLines] = useState<OrderLine[] | null>(null);
  const [agreedDate, setAgreedDate] = useState("");

  const d = po.data;
  const invalidate = () => qc.invalidateQueries({ queryKey: ["po", poId] });

  // hydrate the editable order lines from the PO
  useEffect(() => {
    if (d && lines === null) {
      setLines((d.line_items ?? []).map((l: any) => ({ ...l, quantity: Number(l.quantity ?? 0), unit_price: Number(l.unit_price ?? 0) })));
    }
  }, [d]); // eslint-disable-line react-hooks/exhaustive-deps

  const updateOrder = useMutation({
    mutationFn: (body: Record<string, any>) => apiPatch(`/procurement/purchase-orders/${poId}`, body),
    onSuccess: () => { toast.success("Order updated"); invalidate(); },
    onError: (e) => toast.error(apiErr(e, "Update failed")),
  });
  const orderLines = lines ?? [];
  const orderTotal = orderLines.reduce((s, l) => s + (l.quantity || 0) * (l.unit_price || 0), 0);
  function setLine(i: number, patch: Partial<OrderLine>) { setLines((ls) => (ls ?? []).map((l, j) => (j === i ? { ...l, ...patch } : l))); }
  function removeLine(i: number) { setLines((ls) => (ls ?? []).filter((_, j) => j !== i)); }

  const logReply = useMutation({
    mutationFn: () => apiPost(`/procurement/purchase-orders/${poId}/messages`, { body: logBody, direction: "inbound", sender: d?.supplier_name || "Supplier" }),
    onSuccess: () => { setLogBody(""); toast.success("Reply logged"); invalidate(); },
    onError: (e) => toast.error(apiErr(e, "Could not log")),
  });
  const sendReply = useMutation({
    mutationFn: () => apiPost(`/procurement/purchase-orders/${poId}/reply`, { body: reply }),
    onSuccess: () => { setReply(""); toast.success("Reply sent to supplier"); invalidate(); },
    onError: (e) => toast.error(apiErr(e, "Send failed")),
  });
  async function draftReply() {
    setDrafting(true);
    try { const r = await apiPost<{ reply: string }>(`/procurement/purchase-orders/${poId}/draft-reply`, {}); setReply(r.reply); }
    catch (e) { toast.error(apiErr(e, "Could not draft")); }
    finally { setDrafting(false); }
  }

  if (po.isLoading) return <Loading label="Loading order…" />;
  if (!d) return <Card><div className="py-10 text-center text-ink-soft">Order not found.</div></Card>;

  const notSent = d.status === "pending_hitl";

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <SectionTitle title={`Order ${d.po_number}`} subtitle="The conversation with your supplier for this purchase order."
        right={<div className="flex gap-2"><Link to={`/procurement/edit/${poId}`} className="btn-ghost !py-2"><Settings2 className="h-4 w-4" /> Edit order</Link><Link to="/purchase-orders" className="btn-ghost !py-2"><ArrowLeft className="h-4 w-4" /> All POs</Link></div>} />

      {/* header */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-xl bg-gold/15 text-gold-soft"><ClipboardList className="h-5 w-5" /></div>
            <div>
              <div className="flex items-center gap-2 text-sm font-700 text-ink"><Building2 className="h-3.5 w-3.5" /> {d.supplier_name} {d.supplier_email && <span className="font-mono text-xs text-ink-faint">· {d.supplier_email}</span>}</div>
              <div className="text-xs text-ink-soft">{d.line_items.length} line(s) · {formatCurrency(Number(d.total_amount ?? 0), d.currency)}{d.sent_at ? ` · sent ${new Date(d.sent_at).toLocaleString()}` : ""}</div>
            </div>
          </div>
          <StatusBadge status={d.status} />
        </div>
      </Card>

      {notSent ? (
        <Card>
          <div className="flex flex-col items-center gap-3 py-10 text-center">
            <div className="text-ink-soft">This order hasn't been sent yet.</div>
            {d.hitl_action_id ? <Link to={`/procurement/review/${d.hitl_action_id}`} className="btn-gold">Review &amp; send</Link> : null}
          </div>
        </Card>
      ) : (
        <>
          {/* thread */}
          <Card>
            <SectionTitle title="Thread" subtitle="Request sent, plus any replies." />
            <div className="space-y-4">
              {d.messages.length === 0 && <p className="py-6 text-center text-sm text-ink-faint">No messages yet.</p>}
              {d.messages.map((m, i) => {
                if (m.direction === "system") {
                  return (
                    <div key={i} className="flex justify-center">
                      <span className="rounded-full border border-line bg-white/[0.03] px-3 py-1 text-[11px] text-ink-faint"><Settings2 className="mr-1 inline h-3 w-3" /> {m.body} · {new Date(m.at).toLocaleString()}</span>
                    </div>
                  );
                }
                const out = m.direction === "outbound";
                return (
                  <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className={`flex gap-3 ${out ? "flex-row-reverse" : ""}`}>
                    <div className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg ${out ? "bg-gold text-bg" : "bg-grape/20 text-grape-soft"}`}>
                      {out ? <Send className="h-4 w-4" /> : <Inbox className="h-4 w-4" />}
                    </div>
                    <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${out ? "rounded-tr-sm bg-gold/15" : "rounded-tl-sm border border-line bg-bg-soft"}`}>
                      <div className="mb-1 flex items-center gap-2 text-[11px] text-ink-faint"><span className="font-700 text-ink-soft">{m.sender}</span> · {new Date(m.at).toLocaleString()}</div>
                      <div className="whitespace-pre-wrap leading-relaxed text-ink-soft">{m.body}</div>
                      {!out && m.extracted && <ExtractedPanel x={m.extracted} poId={poId!} />}
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </Card>

          {/* log an inbound supplier reply */}
          <Card>
            <SectionTitle title="Log a supplier reply" subtitle="Paste an email the supplier sent back, to keep the thread complete." right={<MessageSquarePlus className="h-5 w-5 text-ink-faint" />} />
            <textarea className="input min-h-[80px] resize-y" placeholder="Paste the supplier's reply…" value={logBody} onChange={(e) => setLogBody(e.target.value)} />
            <button className="btn-ghost mt-2" disabled={!logBody.trim() || logReply.isPending} onClick={() => logReply.mutate()}>{logReply.isPending ? <Spinner className="h-4 w-4" /> : <Inbox className="h-4 w-4" />} Log reply</button>
          </Card>

          {/* order actions — adjust items, confirm container date, set status */}
          <Card>
            <SectionTitle title="Order actions" subtitle="After the supplier replies, revise the order, confirm the container date, or mark it confirmed." right={<Settings2 className="h-5 w-5 text-ink-faint" />} />
            <div className="space-y-2">
              {orderLines.map((l, i) => (
                <div key={i} className="flex items-center gap-2 rounded-xl border border-line bg-white/[0.02] p-2">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm text-ink">{l.product_name}</div>
                    <div className="font-mono text-[11px] text-ink-faint">{l.sku ?? "—"}</div>
                  </div>
                  <input type="number" min={0} value={l.quantity} onChange={(e) => setLine(i, { quantity: Math.max(0, Number(e.target.value)) })} title="Quantity" className="input w-16 !py-1 text-center text-xs" />
                  <input type="number" min={0} step="0.01" value={l.unit_price} onChange={(e) => setLine(i, { unit_price: Math.max(0, Number(e.target.value)) })} title="Unit price" className="input w-20 !py-1 text-right text-xs" />
                  <span className="w-20 text-right font-mono text-xs text-ink">{formatCurrency((l.quantity || 0) * (l.unit_price || 0), d.currency)}</span>
                  <button onClick={() => removeLine(i)} title="Remove item" className="text-ink-faint hover:text-danger"><Trash2 className="h-3.5 w-3.5" /></button>
                </div>
              ))}
              {orderLines.length === 0 && <p className="py-2 text-center text-xs text-ink-faint">No items.</p>}
            </div>
            <div className="mt-2 flex items-center justify-between border-t border-line pt-2 text-sm">
              <span className="text-ink-soft">New order total</span>
              <span className="font-mono font-800 text-ink">{formatCurrency(orderTotal, d.currency)}</span>
            </div>
            <div className="mt-3 flex flex-wrap items-end gap-2">
              <button className="btn-ghost !py-2 text-xs" disabled={updateOrder.isPending} onClick={() => updateOrder.mutate({ line_items: orderLines })}>
                {updateOrder.isPending ? <Spinner className="h-3.5 w-3.5" /> : <Save className="h-3.5 w-3.5" />} Update items
              </button>
              <div className="flex items-end gap-2">
                <div>
                  <label className="label !mb-1 text-[10px]">Container / delivery date</label>
                  <input type="date" className="input !py-1.5 text-xs" value={agreedDate} onChange={(e) => setAgreedDate(e.target.value)} />
                </div>
                <button className="btn-ghost !py-2 text-xs" disabled={!agreedDate || updateOrder.isPending} onClick={() => updateOrder.mutate({ agreed_delivery_date: agreedDate })}>
                  <CalendarCheck className="h-3.5 w-3.5" /> Confirm date
                </button>
              </div>
              <button className="btn-gold !py-2 text-xs" disabled={updateOrder.isPending} onClick={() => updateOrder.mutate({ status: "confirmed", note: "order confirmed with supplier" })}>
                <CheckCircle2 className="h-3.5 w-3.5" /> Mark confirmed
              </button>
            </div>
          </Card>

          {/* reply to the supplier */}
          <Card>
            <SectionTitle title="Reply to supplier" right={<button onClick={draftReply} disabled={drafting} className="chip border-grape/30 bg-grape/10 text-grape-soft hover:bg-grape/20">{drafting ? <Spinner className="h-3 w-3" /> : <Sparkles className="h-3 w-3" />} Draft with AI</button>} />
            <textarea className="input min-h-[140px] resize-y" placeholder="Write a reply, or let the AI draft one from the thread…" value={reply} onChange={(e) => setReply(e.target.value)} />
            <button className="btn-gold mt-2" disabled={!reply.trim() || !d.supplier_email || sendReply.isPending} onClick={() => sendReply.mutate()}>{sendReply.isPending ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />} Send reply</button>
            {!d.supplier_email && <p className="mt-2 text-xs text-warn">⚠ Add a supplier email in Suppliers to send replies.</p>}
          </Card>
        </>
      )}
    </div>
  );
}

// What the AI understood from a supplier's reply, plus the actions it triggers:
// an "edit & resend" route when they want changes, and the auto-tracked arrival date.
function ExtractedPanel({ x, poId }: { x: Extracted; poId: string }) {
  const tone = x.intent === "reject" ? "border-danger/30 bg-danger/10 text-danger"
    : x.intent === "request_change" ? "border-warn/30 bg-warn/10 text-warn"
    : x.intent === "confirm" ? "border-emerald/30 bg-emerald/10 text-emerald-soft"
    : "border-line bg-white/[0.04] text-ink-soft";
  return (
    <div className="mt-2 rounded-lg border border-grape/25 bg-grape/5 p-2">
      <div className="flex items-center gap-1.5 text-[11px] font-700 text-grape-soft"><Sparkles className="h-3 w-3" /> What the AI understood</div>
      {x.summary && <div className="mt-1 text-[12px] text-ink-soft">{x.summary}</div>}
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
        <span className={`chip capitalize ${tone}`}>{x.intent.replace(/_/g, " ")}</span>
        {x.arrival_date && <span className="chip border-emerald/30 bg-emerald/10 text-emerald-soft"><CalendarCheck className="h-3 w-3" /> Arrival {x.arrival_date} · tracked</span>}
        {x.promised_payment_date && <span className="chip border-grape/30 bg-grape/10 text-grape-soft">Pays by {x.promised_payment_date}</span>}
      </div>
      {x.wants_changes && (
        <div className="mt-2 flex items-center gap-2 rounded-md border border-warn/30 bg-warn/10 p-1.5">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-warn" />
          <div className="flex-1 text-[11px] text-warn">{x.change_summary || "Supplier requested changes to the order."}</div>
          <Link to={`/procurement/edit/${poId}`} className="btn-gold shrink-0 !px-2 !py-1 text-[11px]"><Pencil className="h-3 w-3" /> Edit &amp; resend</Link>
        </div>
      )}
    </div>
  );
}
