// Feature: Supplier & Factory Network — Outreach Inbox. Every outreach conversation
//          (first-contact + replies). Open one to continue the convo until they send
//          a catalogue → "Use for enrichment" promotes them to Our Suppliers.
// API:     GET /network/conversations
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { Mailbox, Inbox, Send, ArrowRight, Building2, Search } from "lucide-react";
import { apiGet } from "@/lib/api";
import { Card, SectionTitle, Loading, EmptyState } from "@/components/ui";
import { formatRelativeDate } from "@/lib/utils";

interface Convo { supplier_id: string; name: string; email: string | null; relationship: string; message_count: number; last_at: string | null; last_direction: string | null }

export function OutreachInbox() {
  const navigate = useNavigate();
  const q = useQuery({ queryKey: ["conversations"], queryFn: () => apiGet<Convo[]>("/network/conversations"), refetchInterval: 10_000 });
  const list = q.data ?? [];
  const waiting = list.filter((c) => c.last_direction === "inbound");

  return (
    <div className="space-y-6">
      <SectionTitle title="Outreach Inbox" subtitle="Conversations with prospects you've reached out to — answer them, and when they send a catalogue, enrich it."
        right={<Link to="/suppliers/outreach" className="btn-ghost !py-2"><Search className="h-4 w-4" /> New outreach</Link>} />

      {q.isLoading ? <Loading /> : list.length === 0 ? (
        <Card><EmptyState icon={<Mailbox className="h-8 w-8" />} title="No conversations yet" hint="Start one from the Network map (Contact a factory) or Discover & Outreach." /></Card>
      ) : (
        <>
          {waiting.length > 0 && (
            <Card>
              <SectionTitle title="Awaiting your reply" subtitle="A supplier answered — open to respond." />
              <Rows rows={waiting} onOpen={(id) => navigate(`/suppliers/outreach?supplier=${id}`)} />
            </Card>
          )}
          <Card>
            <SectionTitle title="All conversations" />
            <Rows rows={list} onOpen={(id) => navigate(`/suppliers/outreach?supplier=${id}`)} />
          </Card>
        </>
      )}
    </div>
  );
}

function Rows({ rows, onOpen }: { rows: Convo[]; onOpen: (id: string) => void }) {
  return (
    <div className="space-y-2">
      {rows.map((c) => (
        <button key={c.supplier_id} onClick={() => onOpen(c.supplier_id)}
          className="flex w-full items-center gap-3 rounded-xl border border-line bg-white/[0.02] p-3.5 text-left transition-all hover:-translate-y-0.5 hover:border-gold/30 hover:shadow-glow">
          <div className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${c.last_direction === "inbound" ? "bg-emerald/15 text-emerald-soft" : "bg-grape/15 text-grape-soft"}`}>
            {c.last_direction === "inbound" ? <Inbox className="h-5 w-5" /> : <Send className="h-5 w-5" />}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-sm font-700 text-ink"><Building2 className="h-3.5 w-3.5 text-ink-faint" /> {c.name}
              <span className={`chip ${c.relationship === "active" ? "border-emerald/30 bg-emerald/10 text-emerald-soft" : "border-grape/30 bg-grape/10 text-grape-soft"}`}>{c.relationship === "active" ? "Our supplier" : "Prospect"}</span>
            </div>
            <div className="text-xs text-ink-soft">{c.message_count} message(s){c.email ? ` · ${c.email}` : ""}{c.last_at ? ` · ${formatRelativeDate(c.last_at)}` : ""}</div>
          </div>
          <ArrowRight className="h-4 w-4 text-ink-faint" />
        </button>
      ))}
    </div>
  );
}
