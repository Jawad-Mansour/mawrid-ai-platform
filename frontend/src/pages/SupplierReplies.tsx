// Feature: Procurement — Supplier Replies. A single inbox of every purchase-order
//          conversation: orders sent to suppliers, which ones replied, and a click
//          straight into the email thread to read/answer (AI-assisted).
// API:     GET /procurement/purchase-orders
import { useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate, Link } from "react-router-dom";
import { MessagesSquare, Inbox, Send, ArrowRight, Building2, Clock, MailSearch } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiErr } from "@/lib/api";
import { Card, SectionTitle, Loading, EmptyState, StatusBadge, Spinner } from "@/components/ui";
import { formatCurrency, formatRelativeDate } from "@/lib/utils";

interface PO { po_id: string; po_number: string; supplier_id: string; status: string; total_amount: number | null; currency: string; created_at: string }

const REPLY_STATES = new Set(["replied", "confirmed"]);
const SENT_STATES = new Set(["sent", "replied", "confirmed"]);

export function SupplierReplies() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const pos = useQuery({ queryKey: ["purchase-orders"], queryFn: () => apiGet<PO[]>("/procurement/purchase-orders"), refetchInterval: 10_000 });
  const list = Array.isArray(pos.data) ? pos.data : [];

  const conversations = useMemo(() => list.filter((p) => SENT_STATES.has(p.status)), [list]);
  const awaiting = conversations.filter((p) => p.status === "sent");
  const replied = conversations.filter((p) => REPLY_STATES.has(p.status));

  // Pull supplier replies from the operator mailbox on demand (same job the scheduler runs).
  const poll = useMutation({
    mutationFn: () => apiPost<{ enabled: number; fetched: number; processed: number }>("/procurement/inbound/poll", {}),
    onSuccess: (r) => {
      if (!r.enabled) toast.message("Inbound email isn't configured yet", { description: "Add IMAP credentials to Vault (mawrid/imap) to auto-detect replies. You can still log replies manually inside a thread." });
      else if (r.processed > 0) { toast.success(`${r.processed} new repl${r.processed === 1 ? "y" : "ies"} detected & threaded`); qc.invalidateQueries({ queryKey: ["purchase-orders"] }); }
      else toast.message("No new replies", { description: `Checked the mailbox — nothing new from your suppliers.` });
    },
    onError: (e) => toast.error(apiErr(e, "Couldn't check the mailbox")),
  });

  return (
    <div className="space-y-6">
      <SectionTitle title="Supplier Replies" subtitle="Every order you've sent and the conversation it started — open a thread to read or answer."
        right={<div className="flex gap-2">
          <button onClick={() => poll.mutate()} disabled={poll.isPending} className="btn-ghost !py-2" title="Check the mailbox for new supplier replies now">
            {poll.isPending ? <Spinner className="h-4 w-4" /> : <MailSearch className="h-4 w-4" />} Check inbox
          </button>
          <Link to="/purchase-orders" className="btn-ghost !py-2"><Send className="h-4 w-4" /> Purchase Orders</Link>
        </div>} />

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Conversations" value={conversations.length} icon={<MessagesSquare className="h-5 w-5" />} />
        <Stat label="Awaiting reply" value={awaiting.length} icon={<Clock className="h-5 w-5" />} tone="warn" />
        <Stat label="Replied" value={replied.length} icon={<Inbox className="h-5 w-5" />} tone="emerald" />
      </div>

      <Card>
        <SectionTitle title="Replied — needs your attention" subtitle="Suppliers who answered. Open to read & respond." />
        {pos.isLoading ? <Loading /> : replied.length === 0 ? (
          <EmptyState icon={<Inbox className="h-8 w-8" />} title="No replies yet" hint="When a supplier answers an order, it shows here." />
        ) : <Rows rows={replied} onOpen={(id) => navigate(`/purchase-orders/${id}`)} />}
      </Card>

      <Card>
        <SectionTitle title="Awaiting a reply" subtitle="Sent, no answer logged yet." />
        {pos.isLoading ? <Loading /> : awaiting.length === 0 ? (
          <EmptyState icon={<Send className="h-8 w-8" />} title="Nothing pending" hint="Sent orders waiting on the supplier appear here." />
        ) : <Rows rows={awaiting} onOpen={(id) => navigate(`/purchase-orders/${id}`)} />}
      </Card>
    </div>
  );
}

function Rows({ rows, onOpen }: { rows: PO[]; onOpen: (id: string) => void }) {
  return (
    <div className="space-y-2">
      {rows.map((p) => (
        <button key={p.po_id} onClick={() => onOpen(p.po_id)}
          className="flex w-full items-center gap-3 rounded-xl border border-line bg-white/[0.02] p-3.5 text-left transition-all hover:-translate-y-0.5 hover:border-gold/30 hover:shadow-glow">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-grape/15 text-grape-soft"><MessagesSquare className="h-5 w-5" /></div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 font-mono text-sm font-700 text-ink"><Building2 className="h-3.5 w-3.5 text-ink-faint" /> {p.po_number}</div>
            <div className="text-xs text-ink-soft">{p.total_amount != null ? formatCurrency(p.total_amount, p.currency) : "—"} · {formatRelativeDate(p.created_at)}</div>
          </div>
          <StatusBadge status={p.status} />
          <ArrowRight className="h-4 w-4 text-ink-faint" />
        </button>
      ))}
    </div>
  );
}

function Stat({ label, value, icon, tone }: { label: string; value: number; icon: React.ReactNode; tone?: "warn" | "emerald" }) {
  const ring = tone === "warn" ? "text-warn bg-warn/10" : tone === "emerald" ? "text-emerald-soft bg-emerald/10" : "text-gold-soft bg-gold/15";
  return (
    <Card className="flex items-center gap-3">
      <div className={`grid h-11 w-11 place-items-center rounded-xl ${ring}`}>{icon}</div>
      <div>
        <div className="text-2xl font-800 text-ink">{value}</div>
        <div className="text-xs text-ink-soft">{label}</div>
      </div>
    </Card>
  );
}
