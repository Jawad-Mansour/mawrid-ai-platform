// Feature: Procurement — PO email thread (Screen 3). Tracks the conversation with
//          the supplier: the request we sent, replies received (logged), and our
//          AI-assisted replies back.
// API:     GET /procurement/purchase-orders/{id} · POST .../messages · .../draft-reply · .../reply
import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowLeft, Send, Sparkles, Inbox, Building2, ClipboardList, MessageSquarePlus } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiErr } from "@/lib/api";
import { Card, SectionTitle, Loading, StatusBadge, Spinner } from "@/components/ui";
import { formatCurrency } from "@/lib/utils";

interface Msg { direction: string; sender: string; body: string; at: string }
interface PODetail {
  po_id: string; po_number: string; supplier_id: string; supplier_name: string | null; supplier_email: string | null;
  status: string; total_amount: number | null; currency: string; po_text: string | null; line_items: any[];
  sent_at: string | null; created_at: string; messages: Msg[];
}

export function POThread() {
  const { poId } = useParams();
  const qc = useQueryClient();
  const po = useQuery({ queryKey: ["po", poId], queryFn: () => apiGet<PODetail>(`/procurement/purchase-orders/${poId}`), enabled: !!poId, refetchInterval: 8000 });
  const [logBody, setLogBody] = useState("");
  const [reply, setReply] = useState("");
  const [drafting, setDrafting] = useState(false);

  const d = po.data;
  const invalidate = () => qc.invalidateQueries({ queryKey: ["po", poId] });

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
        right={<Link to="/purchase-orders" className="btn-ghost !py-2"><ArrowLeft className="h-4 w-4" /> All POs</Link>} />

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
                const out = m.direction === "outbound";
                return (
                  <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className={`flex gap-3 ${out ? "flex-row-reverse" : ""}`}>
                    <div className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg ${out ? "bg-gold text-bg" : "bg-grape/20 text-grape-soft"}`}>
                      {out ? <Send className="h-4 w-4" /> : <Inbox className="h-4 w-4" />}
                    </div>
                    <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${out ? "rounded-tr-sm bg-gold/15" : "rounded-tl-sm border border-line bg-bg-soft"}`}>
                      <div className="mb-1 flex items-center gap-2 text-[11px] text-ink-faint"><span className="font-700 text-ink-soft">{m.sender}</span> · {new Date(m.at).toLocaleString()}</div>
                      <div className="whitespace-pre-wrap leading-relaxed text-ink-soft">{m.body}</div>
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
