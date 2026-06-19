// Feature: Activity — chronological log of real events (enrichment done, order
//          created, PO sent, supplier reply, outreach sent). Distinct from the
//          Notifications "needs attention" view.
// API:     GET /notifications · POST /notifications/{id}/read · POST /notifications/read-all
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Sparkles, ShieldQuestion, ClipboardList, Send, Inbox, Mail, Activity as ActivityIcon, CheckCheck, BellOff,
} from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Card, SectionTitle, Loading } from "@/components/ui";
import { formatRelativeDate } from "@/lib/utils";

interface Note { notification_id: string; kind: string; title: string; body: string | null; link: string | null; read: boolean; created_at: string }
interface Resp { items: Note[]; unread: number }

const KIND: Record<string, { icon: typeof Sparkles; tone: string; label: string }> = {
  enrichment_done: { icon: Sparkles, tone: "text-emerald-soft", label: "Enrichment" },
  needs_review: { icon: ShieldQuestion, tone: "text-warn", label: "Needs review" },
  order_created: { icon: ClipboardList, tone: "text-gold-soft", label: "Order" },
  po_sent: { icon: Send, tone: "text-grape-soft", label: "PO sent" },
  supplier_reply: { icon: Inbox, tone: "text-sky-400", label: "Supplier reply" },
  outreach_sent: { icon: Mail, tone: "text-grape-soft", label: "Outreach" },
};
const meta = (k: string) => KIND[k] ?? { icon: ActivityIcon, tone: "text-ink-soft", label: k.replace(/_/g, " ") };

export function Activity() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [filter, setFilter] = useState("all");
  const [readFilter, setReadFilter] = useState<"all" | "unread">("all");
  const q = useQuery({ queryKey: ["activity"], queryFn: () => apiGet<Resp>("/notifications?limit=200"), refetchInterval: 10_000 });
  const items = q.data?.items ?? [];
  const unread = q.data?.unread ?? items.filter((i) => !i.read).length;
  const kinds = [...new Set(items.map((i) => i.kind))];
  const shown = items
    .filter((i) => filter === "all" || i.kind === filter)
    .filter((i) => readFilter === "all" || !i.read);

  // Optimistic: flip everything to read instantly, then sync with the server.
  const readAll = useMutation({
    mutationFn: () => apiPost("/notifications/read-all", {}),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: ["activity"] });
      const prev = qc.getQueryData<Resp>(["activity"]);
      qc.setQueryData<Resp>(["activity"], (old) => old ? { ...old, items: old.items.map((i) => ({ ...i, read: true })), unread: 0 } : old);
      return { prev };
    },
    onError: (_e, _v, ctx) => { if (ctx?.prev) qc.setQueryData(["activity"], ctx.prev); },
    onSettled: () => qc.invalidateQueries({ queryKey: ["activity"] }),
  });
  function open(n: Note) {
    qc.setQueryData<Resp>(["activity"], (old) => old ? { ...old, items: old.items.map((i) => i.notification_id === n.notification_id ? { ...i, read: true } : i), unread: Math.max(0, old.unread - (n.read ? 0 : 1)) } : old);
    apiPost(`/notifications/${n.notification_id}/read`, {}).finally(() => qc.invalidateQueries({ queryKey: ["activity"] }));
    if (n.link) navigate(n.link);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <SectionTitle title="Activity" subtitle="A live log of everything that happens in your workspace."
        right={<button onClick={() => readAll.mutate()} className="btn-ghost !py-2 text-xs"><CheckCheck className="h-3.5 w-3.5" /> Mark all read</button>} />

      {/* Unread / All split */}
      <div className="flex w-fit gap-1 rounded-xl border border-line bg-white/[0.02] p-1">
        {(["all", "unread"] as const).map((rf) => (
          <button key={rf} onClick={() => setReadFilter(rf)}
            className={cn("flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-600 capitalize transition-all", readFilter === rf ? "bg-gold/15 text-gold-soft" : "text-ink-soft hover:text-ink")}>
            {rf}{rf === "unread" && <span className="grid h-4 min-w-4 place-items-center rounded-full bg-gold/20 px-1 text-[10px] font-700 text-gold-soft">{unread}</span>}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        <button onClick={() => setFilter("all")} className={cn("chip", filter === "all" ? "border-gold/50 bg-gold/15 text-gold-soft" : "border-line bg-white/[0.02] text-ink-soft hover:text-ink")}>
          All <span className="ml-1 rounded-full bg-black/20 px-1.5 text-[10px]">{items.length}</span>
        </button>
        {kinds.map((k) => {
          const m = meta(k);
          const n = items.filter((i) => i.kind === k).length;
          return (
            <button key={k} onClick={() => setFilter(k)} className={cn("chip", filter === k ? "border-gold/50 bg-gold/15 text-gold-soft" : "border-line bg-white/[0.02] text-ink-soft hover:text-ink")}>
              <m.icon className={cn("h-3.5 w-3.5", m.tone)} /> {m.label} <span className="ml-1 rounded-full bg-black/20 px-1.5 text-[10px]">{n}</span>
            </button>
          );
        })}
      </div>

      {q.isLoading ? <Loading /> : shown.length === 0 ? (
        <Card>
          <div className="flex flex-col items-center gap-3 py-12 text-center text-ink-faint">
            <BellOff className="h-9 w-9" />
            <div className="text-base font-700 text-ink">{readFilter === "unread" && items.length > 0 ? "You're all caught up 🎉" : "No activity yet"}</div>
            <div className="text-sm">{readFilter === "unread" && items.length > 0 ? "No unread notifications." : "Upload a sheet or place an order — events will stream in here."}</div>
          </div>
        </Card>
      ) : (
        <div className="space-y-2">
          {shown.map((n, i) => {
            const m = meta(n.kind);
            return (
              <motion.button key={n.notification_id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: Math.min(i * 0.03, 0.4) }}
                onClick={() => open(n)}
                className={cn("flex w-full items-center gap-3 rounded-2xl border bg-bg-card px-4 py-3.5 text-left shadow-glass backdrop-blur transition-all hover:-translate-y-0.5 hover:shadow-glow",
                  n.read ? "border-line" : "border-gold/30")}>
                <div className={cn("grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-line bg-bg-soft shadow-glow", m.tone)}>
                  <m.icon className="h-5 w-5 drop-shadow-[0_0_6px_currentColor]" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 text-sm font-700 text-ink">{n.title}{!n.read && <span className="h-2 w-2 rounded-full bg-gold" />}</div>
                  {n.body && <div className="truncate text-xs text-ink-soft">{n.body}</div>}
                </div>
                <span className="shrink-0 text-[11px] text-ink-faint">{formatRelativeDate(n.created_at)}</span>
              </motion.button>
            );
          })}
        </div>
      )}
    </div>
  );
}
