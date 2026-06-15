// Feature: Dunning Engine — 4 tracks, aging, active sequences
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Banknote, ArrowDownToLine, ArrowUpFromLine, Users, FileWarning, Play, Square } from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from "recharts";
import { toast } from "sonner";
import { apiGet, apiPost, apiErr } from "@/lib/api";
import { Card, SectionTitle, StatusBadge, Loading, EmptyState } from "@/components/ui";
import type { DunningSequence } from "@/lib/types";
import { formatCurrency } from "@/lib/utils";

function asList(d: unknown): DunningSequence[] {
  if (Array.isArray(d)) return d as DunningSequence[];
  if (d && typeof d === "object" && Array.isArray((d as any).sequences)) return (d as any).sequences;
  return [];
}

const TRACKS = [
  { key: "track1", label: "B2B Payables", desc: "Remind to pay suppliers (3-day advance)", icon: ArrowUpFromLine, ep: "/dunning/trigger/track1", color: "from-gold to-gold-deep" },
  { key: "track3", label: "B2B Receivables", desc: "Chase wholesale clients (Day 7/14/21)", icon: ArrowDownToLine, ep: "/dunning/trigger/track3", color: "from-emerald to-emerald-soft" },
  { key: "track4", label: "B2C Collections", desc: "Consumer reminders (Day 3/7/14)", icon: Users, ep: "/dunning/trigger/track4", color: "from-grape to-grape-soft" },
  { key: "disputes", label: "B2B Disputes", desc: "Formal supplier complaint letters", icon: FileWarning, ep: null, color: "from-danger to-warn" },
];

export function Dunning() {
  const qc = useQueryClient();
  const sequences = useQuery({ queryKey: ["dunning"], queryFn: () => apiGet<unknown>("/dunning/sequences"), refetchInterval: 12_000 });
  const aging = useQuery({ queryKey: ["aging"], queryFn: () => apiGet<Record<string, number>>("/invoices/aging") });

  const trigger = useMutation({
    mutationFn: (ep: string) => apiPost<{ created?: string[] } | unknown>(ep, {}),
    onSuccess: () => { toast.success("Track run complete — new drafts (if any) are in Approvals"); qc.invalidateQueries({ queryKey: ["dunning"] }); },
    onError: (e) => toast.error(apiErr(e, "Track run failed")),
  });
  const stop = useMutation({
    mutationFn: (id: string) => apiPost(`/dunning/sequences/${id}/stop`, {}),
    onSuccess: () => { toast.success("Sequence stopped"); qc.invalidateQueries({ queryKey: ["dunning"] }); },
    onError: (e) => toast.error(apiErr(e, "Stop failed")),
  });

  const seqs = asList(sequences.data);
  const a = aging.data ?? {};
  const agingData = [
    { bucket: "Current", v: a.current ?? 0 },
    { bucket: "1–30", v: a.days_1_30 ?? 0 },
    { bucket: "31–60", v: a.days_31_60 ?? 0 },
    { bucket: "61–90", v: a.days_61_90 ?? 0 },
    { bucket: "90+", v: a.over_90 ?? 0 },
  ];
  const colors = ["#40916C", "#D4A373", "#E2A03F", "#B07D4F", "#E5484D"];

  return (
    <div className="space-y-6">
      <SectionTitle title="Dunning Engine" subtitle="All four collection tracks. Every message is drafted, then held for your approval." />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {TRACKS.map((t) => (
          <Card key={t.key}>
            <div className={`mb-3 grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br ${t.color}`}>
              <t.icon className="h-5 w-5 text-bg" />
            </div>
            <div className="font-700 text-ink">{t.label}</div>
            <p className="mt-1 min-h-[40px] text-xs text-ink-soft">{t.desc}</p>
            {t.ep ? (
              <button className="btn-ghost mt-3 w-full !py-2" disabled={trigger.isPending} onClick={() => trigger.mutate(t.ep!)}>
                <Play className="h-3.5 w-3.5" /> Run check
              </button>
            ) : (
              <div className="mt-3 text-center text-xs text-ink-faint">Filed from an invoice</div>
            )}
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <SectionTitle title="Receivables Aging" subtitle="Outstanding by age" right={<Banknote className="h-5 w-5 text-gold" />} />
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={agingData} margin={{ left: -18, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(212,163,115,0.08)" />
              <XAxis dataKey="bucket" stroke="#6B6759" fontSize={11} />
              <YAxis stroke="#6B6759" fontSize={11} />
              <Tooltip cursor={{ fill: "rgba(255,255,255,0.03)" }}
                contentStyle={{ background: "rgba(20,25,35,0.95)", border: "1px solid rgba(212,163,115,0.2)", borderRadius: 12, color: "#ECE7DF" }}
                formatter={(v: number) => formatCurrency(v)} />
              <Bar dataKey="v" radius={[6, 6, 0, 0]}>
                {agingData.map((_, i) => <Cell key={i} fill={colors[i]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card className="lg:col-span-2">
          <SectionTitle title="Active Sequences" subtitle="Payment confirmation auto-stops a sequence." />
          {sequences.isLoading ? <Loading /> : seqs.length === 0 ? (
            <EmptyState icon={<Banknote className="h-8 w-8" />} title="No active sequences" hint="Run a track check, or sequences start automatically on overdue invoices." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-line text-left text-xs uppercase tracking-wider text-ink-faint">
                  <th className="py-2.5 pr-3 font-600">Invoice</th><th className="px-3 font-600">Track</th>
                  <th className="px-3 font-600">Step</th><th className="px-3 font-600">Status</th><th className="px-3 font-600"></th>
                </tr></thead>
                <tbody>
                  {seqs.map((d) => (
                    <tr key={d.sequence_id} className="table-row">
                      <td className="py-3 pr-3 font-mono text-xs text-ink">{d.invoice_id.slice(0, 12)}</td>
                      <td className="px-3 text-ink-soft">{d.track}</td>
                      <td className="px-3 text-ink-soft">{d.current_step ?? "—"}</td>
                      <td className="px-3"><StatusBadge status={d.status} /></td>
                      <td className="px-3 text-right">
                        {d.status === "active" && (
                          <button className="btn-ghost !py-1.5" onClick={() => stop.mutate(d.sequence_id)}><Square className="h-3.5 w-3.5" /> Stop</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
