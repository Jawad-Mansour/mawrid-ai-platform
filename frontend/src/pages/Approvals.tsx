// Feature: HITL Approval Center — approve / reject / edit (A / R / E shortcuts)
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, X, Pencil, Keyboard, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiPut, apiErr } from "@/lib/api";
import { Card, SectionTitle, StatusBadge, Loading, EmptyState } from "@/components/ui";
import type { HITLAction } from "@/lib/types";

function asList(d: unknown): HITLAction[] {
  if (Array.isArray(d)) return d as HITLAction[];
  if (d && typeof d === "object" && Array.isArray((d as any).actions)) return (d as any).actions;
  return [];
}

export function Approvals() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState(0);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const q = useQuery({
    queryKey: ["hitl-all"],
    queryFn: () => apiGet<unknown>("/hitl/actions?status=pending"),
    refetchInterval: 12_000,
  });
  const actions = useMemo(() => asList(q.data).filter((a) => a.status === "pending"), [q.data]);

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
        right={<span className="chip border-line bg-white/[0.02] text-ink-soft"><Keyboard className="h-3.5 w-3.5" /> A approve · R reject · E edit</span>}
      />

      {actions.length === 0 ? (
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
      )}
    </div>
  );
}
