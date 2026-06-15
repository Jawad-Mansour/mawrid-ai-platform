// Feature: Operations Command Center — main dashboard
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Boxes, CheckSquare, Banknote, Ship, AlertTriangle, TrendingUp,
  Package, Activity, ArrowUpRight, type LucideIcon,
} from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import { apiGet } from "@/lib/api";
import { Card, SectionTitle, StatusBadge } from "@/components/ui";
import { SupplierGlobe } from "@/components/SupplierGlobe";
import type { DashboardSummary, AIHealthResponse, HITLAction, DunningSequence } from "@/lib/types";
import { formatCurrency } from "@/lib/utils";

function asList<T>(d: unknown, key: string): T[] {
  if (Array.isArray(d)) return d as T[];
  if (d && typeof d === "object" && Array.isArray((d as any)[key])) return (d as any)[key];
  return [];
}

function Metric({ icon: Icon, label, value, accent, to, delta }: {
  icon: LucideIcon; label: string; value: string; accent: string; to?: string; delta?: string;
}) {
  const body = (
    <Card className="group relative overflow-hidden">
      <div className="flex items-start justify-between">
        <div className={`grid h-11 w-11 place-items-center rounded-xl ${accent}`}>
          <Icon className="h-5 w-5" />
        </div>
        {to && <ArrowUpRight className="h-4 w-4 text-ink-faint transition-colors group-hover:text-gold" />}
      </div>
      <div className="metric-num mt-4">{value}</div>
      <div className="mt-1 flex items-center gap-2 text-sm text-ink-soft">
        {label}
        {delta && <span className="text-xs text-emerald-soft">{delta}</span>}
      </div>
    </Card>
  );
  return to ? <Link to={to}>{body}</Link> : body;
}

export function Dashboard() {
  const summary = useQuery({ queryKey: ["summary"], queryFn: () => apiGet<DashboardSummary>("/admin/summary"), refetchInterval: 30_000 });
  const health = useQuery({ queryKey: ["ai-health"], queryFn: () => apiGet<AIHealthResponse>("/admin/ai-health") });
  const hitl = useQuery({ queryKey: ["hitl-pending"], queryFn: () => apiGet<unknown>("/hitl/actions?status=pending") });
  const dunning = useQuery({ queryKey: ["dunning-seq"], queryFn: () => apiGet<unknown>("/dunning/sequences") });

  // Render immediately and fill in as each query resolves (no full-page block).
  const s = summary.data;
  const actions = asList<HITLAction>(hitl.data, "actions").filter((a) => a.status === "pending").slice(0, 5);
  const sequences = asList<DunningSequence>(dunning.data, "sequences").slice(0, 5);

  const funnel = [
    { stage: "Pending", n: s?.pending_enrichment ?? 0 },
    { stage: "Enriched", n: s?.enriched_products ?? 0 },
    { stage: "Published", n: s?.published_products ?? 0 },
    { stage: "Failed", n: s?.failed_enrichment ?? 0 },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-800 tracking-tight text-ink">Operations Command Center</h1>
          <p className="mt-1 text-sm text-ink-soft">Real-time view across procurement, catalog, and collections.</p>
        </div>
        <div className="chip border-grape/40 bg-grape/10 text-grape-soft">
          <Activity className="h-3.5 w-3.5" /> Drift: {health.data?.drift_status ?? "—"}
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Metric icon={Package} label="Published products" value={String(s?.published_products ?? 0)} accent="bg-emerald/15 text-emerald-soft" to="/publishing" />
        <Metric icon={CheckSquare} label="Pending approvals" value={String(s?.pending_hitl_count ?? 0)} accent="bg-gold/15 text-gold-soft" to="/approvals" />
        <Metric icon={AlertTriangle} label="Overdue invoices" value={String(s?.overdue_invoices ?? 0)} accent="bg-danger/15 text-danger" to="/dunning" />
        <Metric icon={Banknote} label="Outstanding A/R" value={formatCurrency(s?.outstanding_receivables ?? 0)} accent="bg-grape/15 text-grape-soft" to="/dunning" />
      </div>

      {/* Globe + funnel */}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <SectionTitle title="Supplier Network" subtitle="Active sourcing locations" />
          <SupplierGlobe />
          <div className="mt-4 grid grid-cols-3 gap-3 text-center">
            <div><div className="metric-num text-xl">{s?.active_shipments ?? 0}</div><div className="text-xs text-ink-faint">Shipments</div></div>
            <div><div className="metric-num text-xl">{s?.low_stock_count ?? 0}</div><div className="text-xs text-ink-faint">Low stock</div></div>
            <div><div className="metric-num text-xl">{s?.consumer_orders_pending ?? 0}</div><div className="text-xs text-ink-faint">Orders</div></div>
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <SectionTitle title="Catalog Enrichment Funnel" subtitle="Product lifecycle distribution" right={<TrendingUp className="h-5 w-5 text-gold" />} />
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={funnel} margin={{ left: -16, right: 8, top: 8 }}>
              <defs>
                <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#D4A373" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#D4A373" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(212,163,115,0.08)" />
              <XAxis dataKey="stage" stroke="#6B6759" fontSize={12} />
              <YAxis stroke="#6B6759" fontSize={12} allowDecimals={false} />
              <Tooltip contentStyle={{ background: "rgba(20,25,35,0.95)", border: "1px solid rgba(212,163,115,0.2)", borderRadius: 12, color: "#ECE7DF" }} />
              <Area type="monotone" dataKey="n" stroke="#D4A373" strokeWidth={2.5} fill="url(#g)" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* HITL + Dunning */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <SectionTitle title="Pending Approvals" subtitle="Actions awaiting your sign-off"
            right={<Link to="/approvals" className="text-sm font-600 text-gold-soft hover:underline">View all</Link>} />
          {actions.length === 0 ? (
            <p className="py-8 text-center text-sm text-ink-soft">Nothing waiting — you're all caught up.</p>
          ) : (
            <div className="space-y-2">
              {actions.map((a) => (
                <Link key={a.action_id} to="/approvals" className="table-row flex items-center justify-between rounded-xl px-3 py-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-600 text-ink">{a.action_type.replace(/_/g, " ")}</div>
                    <div className="truncate text-xs text-ink-faint">
                      {a.payload?.to || a.payload?.supplier_name || a.payload?.invoice_id || a.action_id.slice(0, 12)}
                    </div>
                  </div>
                  <StatusBadge status={a.status} />
                </Link>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <SectionTitle title="Active Dunning Sequences" subtitle="Collections in progress"
            right={<Link to="/dunning" className="text-sm font-600 text-gold-soft hover:underline">Open engine</Link>} />
          {sequences.length === 0 ? (
            <p className="py-8 text-center text-sm text-ink-soft">No active sequences.</p>
          ) : (
            <div className="space-y-2">
              {sequences.map((d) => (
                <div key={d.sequence_id} className="table-row flex items-center justify-between rounded-xl px-3 py-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-600 text-ink">Invoice {d.invoice_id.slice(0, 10)}</div>
                    <div className="text-xs text-ink-faint">Track {d.track} · {d.current_step ?? "—"}</div>
                  </div>
                  <StatusBadge status={d.status} />
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* AI health strip */}
      <Card>
        <SectionTitle title="AI Model Health" subtitle="Registry status across all models"
          right={<Link to="/ai-health" className="text-sm font-600 text-gold-soft hover:underline">Details</Link>} />
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {(health.data?.models ?? []).map((m) => (
            <div key={m.name} className="rounded-xl border border-line bg-white/[0.02] p-4">
              <div className="flex items-center gap-2">
                <Boxes className="h-4 w-4 text-grape-soft" />
                <span className="truncate text-sm font-600 text-ink">{m.name}</span>
              </div>
              <div className="mt-2 flex items-center justify-between">
                <StatusBadge status={m.status} />
                <span className="font-mono text-xs text-ink-faint">{m.latest_version ? `v${m.latest_version}` : "—"}</span>
              </div>
            </div>
          ))}
          {(health.data?.models ?? []).length === 0 && (
            <div className="col-span-full flex items-center gap-2 py-4 text-sm text-ink-soft">
              <Ship className="h-4 w-4" /> No models registered yet — train them to populate the registry.
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
