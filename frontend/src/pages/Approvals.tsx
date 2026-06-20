// Feature: HITL Approval Center — approve / reject / edit (A / R / E shortcuts)
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, X, Pencil, Keyboard, ShieldCheck, History, Clock } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiPut, apiErr } from "@/lib/api";
import { Card, SectionTitle, StatusBadge, Loading, EmptyState } from "@/components/ui";
import type { HITLAction } from "@/lib/types";

function asList(d: unknown): HITLAction[] {
  if (Array.isArray(d)) return d as HITLAction[];
  if (d && typeof d === "object" && Array.isArray((d as any).actions)) return (d as any).actions;
  return [];
}

const TYPE_LABELS: Record<string, string> = {
  purchase_order_send: "Purchase Orders",
  dispute_letter: "Disputes",
  goods_received_report: "Goods-Received Reports",
  dunning_payables_advance: "Payables",
  dunning_disputes_on_demand: "Payment Disputes",
  dunning_receivables: "Receivables",
  dunning_collections: "Collections",
  supplier_match_review: "Supplier Matches",
  supplier_outreach: "Supplier Outreach",
  customer_match_review: "Customer Matches",
};
const labelFor = (t: string) => TYPE_LABELS[t] ?? t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export function Approvals() {
  const qc = useQueryClient();
  const [view, setView] = useState<"pending" | "history">("pending");
  const [tab, setTab] = useState("all");
  const [selected, setSelected] = useState(0);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const q = useQuery({
    queryKey: ["hitl-all"],
    queryFn: () => apiGet<unknown>("/hitl/actions?status=pending"),
    refetchInterval: 12_000,
  });
  const history = useQuery({
    queryKey: ["hitl-history"],
    queryFn: () => apiGet<unknown>("/hitl/actions?all_statuses=true"),
    enabled: view === "history",
    refetchInterval: 20_000,
  });
  const historyActions = useMemo(
    () => asList(history.data).filter((a) => a.status !== "pending").sort((a, b) => String(b.created_at).localeCompare(String(a.created_at))),
    [history.data],
  );
  const allActions = useMemo(() => asList(q.data).filter((a) => a.status === "pending"), [q.data]);
  // one tab per tracked action type (notification-center style), with counts
  const tabs = useMemo(() => {
    const counts = new Map<string, number>();
    allActions.forEach((a) => counts.set(a.action_type, (counts.get(a.action_type) ?? 0) + 1));
    return [...counts.entries()].map(([type, count]) => ({ type, count }));
  }, [allActions]);
  const actions = useMemo(() => (tab === "all" ? allActions : allActions.filter((a) => a.action_type === tab)), [allActions, tab]);

  const approve = useMutation({
    mutationFn: (id: string) => apiPost(`/hitl/actions/${id}/approve`, {}),
    onSuccess: () => { toast.success("Approved & dispatched"); qc.invalidateQueries({ queryKey: ["hitl-all"] }); },
    onError: (e) => toast.error(apiErr(e, "Approve failed")),
  });
  const reject = useMutation({
    mutationFn: (id: string) => apiPost(`/hitl/actions/${id}/reject`, {}),
    onSuccess: () => { toast.success("Rejected"); qc.invalidateQueries({ queryKey: ["hitl-all"] }); },
    onError: (e) => toast.error(apiErr(e, "Reject failed")),
  });
  const saveEdit = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, any> }) => apiPut(`/hitl/actions/${id}`, { payload }),
    onSuccess: () => { toast.success("Draft updated"); setEditing(null); qc.invalidateQueries({ queryKey: ["hitl-all"] }); },
    onError: (e) => toast.error(apiErr(e, "Edit failed")),
  });

  const current = actions[selected];

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (editing) return;
      if (!current) return;
      const t = (e.target as HTMLElement)?.tagName;
      if (t === "INPUT" || t === "TEXTAREA") return;
      if (e.key.toLowerCase() === "a") approve.mutate(current.action_id);
      if (e.key.toLowerCase() === "r") reject.mutate(current.action_id);
      if (e.key.toLowerCase() === "e") startEdit(current);
      if (e.key === "ArrowDown") setSelected((s) => Math.min(s + 1, actions.length - 1));
      if (e.key === "ArrowUp") setSelected((s) => Math.max(s - 1, 0));
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [current, editing, actions.length]); // eslint-disable-line

  function startEdit(a: HITLAction) {
    setEditing(a.action_id);
    setDraft(String(a.payload?.body ?? a.payload?.draft ?? a.payload?.message ?? JSON.stringify(a.payload, null, 2)));
  }

  if (q.isLoading) return <Loading label="Loading approval queue…" />;

  return (
    <div className="space-y-6">
      <SectionTitle
        title="HITL Approval Center"
        subtitle="No external message, order, or payment leaves the system without your sign-off."
        right={
          <div className="flex items-center gap-2">
            <div className="flex gap-1 rounded-xl border border-line bg-white/[0.02] p-0.5">
              <button onClick={() => setView("pending")} className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-600 transition-all ${view === "pending" ? "bg-gold/15 text-gold-soft" : "text-ink-soft hover:text-ink"}`}><ShieldCheck className="h-3.5 w-3.5" /> Pending{allActions.length > 0 && <span className="rounded-full bg-black/20 px-1.5 text-[10px]">{allActions.length}</span>}</button>
              <button onClick={() => setView("history")} className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-600 transition-all ${view === "history" ? "bg-gold/15 text-gold-soft" : "text-ink-soft hover:text-ink"}`}><History className="h-3.5 w-3.5" /> History</button>
            </div>
            {view === "pending" && <span className="chip border-line bg-white/[0.02] text-ink-soft"><Keyboard className="h-3.5 w-3.5" /> A · R · E</span>}
          </div>
        }
      />

      {view === "history" && <HistoryView actions={historyActions} loading={history.isLoading} />}

      {/* tracked-type tabs (notification-center style) */}
      {view === "pending" && allActions.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <button onClick={() => { setTab("all"); setSelected(0); }}
            className={`chip ${tab === "all" ? "border-gold/50 bg-gold/15 text-gold-soft" : "border-line bg-white/[0.02] text-ink-soft hover:text-ink"}`}>
            All <span className="ml-1 rounded-full bg-black/20 px-1.5 text-[10px]">{allActions.length}</span>
          </button>
          {tabs.map((t) => (
            <button key={t.type} onClick={() => { setTab(t.type); setSelected(0); }}
              className={`chip ${tab === t.type ? "border-gold/50 bg-gold/15 text-gold-soft" : "border-line bg-white/[0.02] text-ink-soft hover:text-ink"}`}>
              {labelFor(t.type)} <span className="ml-1 rounded-full bg-black/20 px-1.5 text-[10px]">{t.count}</span>
            </button>
          ))}
        </div>
      )}

      {view === "pending" && (actions.length === 0 ? (
        <EmptyState icon={<ShieldCheck className="h-9 w-9" />} title="Queue is clear" hint="Every pending action has been actioned. New drafts will appear here." />
      ) : (
        <div className="grid gap-6 lg:grid-cols-5">
          {/* list */}
          <div className="space-y-2 lg:col-span-2">
            {actions.map((a, i) => (
              <button
                key={a.action_id}
                onClick={() => setSelected(i)}
                className={`card w-full p-4 text-left transition-all ${i === selected ? "shadow-glow ring-1 ring-gold/40" : "hover:bg-white/[0.04]"}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-700 text-ink">{a.action_type.replace(/_/g, " ")}</span>
                  <StatusBadge status={a.status} />
                </div>
                <div className="mt-1 truncate text-xs text-ink-faint">
                  {a.payload?.to || a.payload?.supplier_name || a.payload?.subject || a.payload?.invoice_id || a.action_id.slice(0, 14)}
                </div>
              </button>
            ))}
          </div>

          {/* detail */}
          <div className="lg:col-span-3">
            {current && (
              <Card>
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-lg font-700 text-ink">{current.action_type.replace(/_/g, " ")}</h3>
                  <StatusBadge status={current.status} />
                </div>

                <div className="space-y-3 text-sm">
                  {["to", "subject", "supplier_name", "invoice_id", "language"].map((k) =>
                    current.payload?.[k] ? (
                      <div key={k} className="flex gap-2">
                        <span className="w-24 shrink-0 text-xs uppercase tracking-wider text-ink-faint">{k.replace("_", " ")}</span>
                        <span className="text-ink">{String(current.payload[k])}</span>
                      </div>
                    ) : null,
                  )}
                </div>

                <div className="mt-4">
                  <div className="label">Message draft</div>
                  {editing === current.action_id ? (
                    <>
                      <textarea className="input min-h-[200px] font-mono text-xs" value={draft} onChange={(e) => setDraft(e.target.value)} />
                      <div className="mt-3 flex gap-2">
                        <button
                          className="btn-gold"
                          onClick={() => saveEdit.mutate({ id: current.action_id, payload: { ...current.payload, body: draft } })}
                        >
                          Save draft
                        </button>
                        <button className="btn-ghost" onClick={() => setEditing(null)}>Cancel</button>
                      </div>
                    </>
                  ) : (
                    <div className="max-h-[260px] overflow-y-auto whitespace-pre-wrap rounded-xl border border-line bg-black/20 p-4 text-sm text-ink">
                      {String(current.payload?.body ?? current.payload?.draft ?? current.payload?.message ?? JSON.stringify(current.payload, null, 2))}
                    </div>
                  )}
                </div>

                {editing !== current.action_id && (
                  <div className="mt-5 flex flex-wrap gap-2">
                    <button className="btn-emerald" onClick={() => approve.mutate(current.action_id)} disabled={approve.isPending}>
                      <Check className="h-4 w-4" /> Approve <kbd className="ml-1 rounded bg-black/20 px-1.5 text-xs">A</kbd>
                    </button>
                    <button className="btn-danger" onClick={() => reject.mutate(current.action_id)} disabled={reject.isPending}>
                      <X className="h-4 w-4" /> Reject <kbd className="ml-1 rounded bg-black/20 px-1.5 text-xs">R</kbd>
                    </button>
                    <button className="btn-ghost" onClick={() => startEdit(current)}>
                      <Pencil className="h-4 w-4" /> Edit <kbd className="ml-1 rounded bg-black/20 px-1.5 text-xs">E</kbd>
                    </button>
                  </div>
                )}
              </Card>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// Read-only log of past decisions (approved / rejected / expired) — the HITL history.
function HistoryView({ actions, loading }: { actions: HITLAction[]; loading: boolean }) {
  if (loading) return <Loading label="Loading history…" />;
  if (actions.length === 0) return <EmptyState icon={<History className="h-9 w-9" />} title="No history yet" hint="Actions you approve or reject will be logged here." />;
  return (
    <div className="space-y-2">
      {actions.map((a) => {
        const target = a.payload?.to || a.payload?.supplier_name || a.payload?.subject || a.payload?.invoice_id || a.payload?.po_number || "";
        return (
          <Card key={a.action_id} className="flex items-center gap-3 !p-3.5">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate text-sm font-700 text-ink">{labelFor(a.action_type)}</span>
                <StatusBadge status={a.status} />
              </div>
              {target && <div className="mt-0.5 truncate text-xs text-ink-faint">{String(target)}</div>}
            </div>
            <span className="flex shrink-0 items-center gap-1 text-[11px] text-ink-faint"><Clock className="h-3 w-3" /> {a.created_at ? new Date(a.created_at).toLocaleString() : ""}</span>
          </Card>
        );
      })}
    </div>
  );
}
