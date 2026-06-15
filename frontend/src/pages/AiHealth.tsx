// Feature: AI Model Health — MLflow registry, drift, eval thresholds, n8n status
import { useQuery } from "@tanstack/react-query";
import { BrainCircuit, Activity, Workflow, CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import { apiGet } from "@/lib/api";
import { Card, SectionTitle, StatusBadge, Loading } from "@/components/ui";
import type { AIHealthResponse, N8nStatusResponse } from "@/lib/types";

const DRIFT_TONE: Record<string, { c: string; Icon: any }> = {
  ok: { c: "text-emerald-soft", Icon: CheckCircle2 },
  warning: { c: "text-warn", Icon: AlertTriangle },
  severe: { c: "text-danger", Icon: XCircle },
};

export function AiHealth() {
  const health = useQuery({ queryKey: ["ai-health-pg"], queryFn: () => apiGet<AIHealthResponse>("/admin/ai-health") });
  const wf = useQuery({ queryKey: ["workflows"], queryFn: () => apiGet<N8nStatusResponse>("/admin/workflows") });

  if (health.isLoading) return <Loading label="Reading model registry…" />;
  const h = health.data;
  const drift = DRIFT_TONE[h?.drift_status ?? ""] ?? { c: "text-ink-soft", Icon: Activity };

  return (
    <div className="space-y-6">
      <SectionTitle title="AI Model Health" subtitle="Registry, drift detection, eval gates and automation status." />

      <div className="grid gap-6 md:grid-cols-3">
        <Card>
          <div className="flex items-center gap-3">
            <drift.Icon className={`h-8 w-8 ${drift.c}`} />
            <div>
              <div className="text-xs uppercase tracking-wider text-ink-faint">Drift status</div>
              <div className={`text-xl font-700 capitalize ${drift.c}`}>{h?.drift_status ?? "—"}</div>
            </div>
          </div>
          <div className="mt-2 text-xs text-ink-faint">Checked {h?.checked_at ? new Date(h.checked_at).toLocaleString() : "—"}</div>
        </Card>
        <Card>
          <div className="flex items-center gap-3">
            <BrainCircuit className="h-8 w-8 text-grape-soft" />
            <div>
              <div className="text-xs uppercase tracking-wider text-ink-faint">Registered models</div>
              <div className="text-xl font-700 text-ink">{h?.models?.length ?? 0}</div>
            </div>
          </div>
        </Card>
        <Card>
          <div className="flex items-center gap-3">
            <Workflow className="h-8 w-8 text-gold" />
            <div>
              <div className="text-xs uppercase tracking-wider text-ink-faint">n8n workflows</div>
              <div className="text-xl font-700 text-ink">{wf.data?.workflows?.length ?? 0}</div>
            </div>
          </div>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <SectionTitle title="Model Registry" subtitle="Champion versions in MLflow" />
          <div className="space-y-2">
            {(h?.models ?? []).map((m) => (
              <div key={m.name} className="table-row flex items-center justify-between rounded-xl px-3 py-3">
                <div>
                  <div className="font-600 text-ink">{m.name}</div>
                  <div className="text-xs text-ink-faint">{m.stage ?? "—"}</div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-ink-soft">{m.latest_version ? `v${m.latest_version}` : "—"}</span>
                  <StatusBadge status={m.status} />
                </div>
              </div>
            ))}
            {(h?.models ?? []).length === 0 && <p className="py-6 text-center text-sm text-ink-soft">No models registered.</p>}
          </div>
        </Card>

        <Card>
          <SectionTitle title="Eval Thresholds" subtitle="CI quality gates" />
          <div className="space-y-1.5 font-mono text-xs">
            {Object.entries(h?.eval_thresholds ?? {}).map(([group, vals]) => (
              <div key={group} className="rounded-xl border border-line bg-black/20 p-3">
                <div className="mb-1 font-sans text-sm font-600 capitalize text-ink">{group.replace(/_/g, " ")}</div>
                {typeof vals === "object" && vals
                  ? Object.entries(vals as Record<string, any>).map(([k, v]) => (
                      <div key={k} className="flex justify-between text-ink-soft"><span>{k}</span><span className="text-gold-soft">{String(v)}</span></div>
                    ))
                  : <span className="text-gold-soft">{String(vals)}</span>}
              </div>
            ))}
            {Object.keys(h?.eval_thresholds ?? {}).length === 0 && <p className="font-sans text-ink-soft">No thresholds configured.</p>}
          </div>
        </Card>
      </div>

      <Card>
        <SectionTitle title="Automation (n8n)" subtitle="Workflow run status" />
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {(wf.data?.workflows ?? []).map((w) => (
            <div key={w.workflow_id} className="rounded-xl border border-line bg-white/[0.02] p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-600 text-ink">{w.name}</span>
                <span className={`h-2 w-2 shrink-0 rounded-full ${w.active ? "bg-emerald-soft" : "bg-ink-faint"}`} />
              </div>
              <div className="mt-1 text-xs text-ink-faint">{w.last_execution_status ?? "no runs"}</div>
            </div>
          ))}
          {(wf.data?.workflows ?? []).length === 0 && <p className="col-span-full py-4 text-center text-sm text-ink-soft">No workflow data — import workflows into n8n.</p>}
        </div>
      </Card>
    </div>
  );
}
