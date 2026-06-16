// Feature: Settings — workspace, theme picker, about, widget embed
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Globe, LogOut, ShieldCheck, Check, Clock, Info, Cpu, Boxes } from "lucide-react";
import { apiPatch, apiErr } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { Card, SectionTitle } from "@/components/ui";
import { THEMES, useThemeStore } from "@/stores/theme";
import { cn } from "@/lib/utils";

export function Settings() {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useThemeStore();
  const [origins, setOrigins] = useState("");

  const saveOrigins = useMutation({
    mutationFn: () => apiPatch("/widget/settings", { allowed_origins: origins }),
    onSuccess: () => toast.success("Widget origins updated"),
    onError: (e) => toast.error(apiErr(e, "Update failed")),
  });

  return (
    <div className="space-y-6">
      <SectionTitle title="Settings" subtitle="Appearance, workspace, and embed options." />

      {/* Theme picker */}
      <Card>
        <SectionTitle title="Appearance" subtitle="Pick a theme — it applies instantly across the app." />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {THEMES.map((t) => (
            <button
              key={t.key}
              disabled={!t.available}
              onClick={() => { setTheme(t.key); toast.success(`Theme: ${t.name}`); }}
              className={cn(
                "group relative overflow-hidden rounded-2xl border p-4 text-left transition-all",
                theme === t.key ? "border-gold/60 shadow-glow ring-1 ring-gold/30" : "border-line hover:border-gold/40",
                !t.available && "cursor-not-allowed opacity-60",
              )}
            >
              <div className="mb-3 h-16 w-full rounded-xl" style={{ background: `linear-gradient(135deg, ${t.swatch[0]}, ${t.swatch[1]})` }} />
              <div className="flex items-center justify-between">
                <span className="text-sm font-700 text-ink">{t.name}</span>
                {theme === t.key && <Check className="h-4 w-4 text-gold-soft" />}
                {!t.available && <Clock className="h-3.5 w-3.5 text-ink-faint" />}
              </div>
              <p className="mt-0.5 text-xs text-ink-faint">{t.available ? t.hint : "Coming soon"}</p>
            </button>
          ))}
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <SectionTitle title="Workspace" />
          <dl className="space-y-3 text-sm">
            {[
              ["Business email", user?.email],
              ["Tenant ID", user?.tenant_id],
              ["Role", user?.role],
              ["Operational mode", user?.operational_mode?.replace("_", " ")],
            ].map(([k, v]) => (
              <div key={k} className="flex items-center justify-between gap-3 border-b border-line pb-2">
                <dt className="text-ink-faint">{k}</dt>
                <dd className="truncate font-mono text-ink">{v ?? "—"}</dd>
              </div>
            ))}
          </dl>
          <button className="btn-danger mt-5 w-full" onClick={logout}><LogOut className="h-4 w-4" /> Sign out</button>
        </Card>

        <Card>
          <SectionTitle title="Embeddable Chat Widget" subtitle="Whitelist domains allowed to embed the storefront chatbot." />
          <label className="label"><Globe className="mr-1 inline h-3.5 w-3.5" /> Allowed origins (comma-separated)</label>
          <input className="input" placeholder="https://shop.example.com, https://www.example.com" value={origins} onChange={(e) => setOrigins(e.target.value)} />
          <button className="btn-gold mt-3" disabled={saveOrigins.isPending} onClick={() => saveOrigins.mutate()}>Save origins</button>
          <div className="mt-5 flex items-start gap-2 rounded-xl border border-grape/30 bg-grape/10 p-3 text-xs text-grape-soft">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
            The widget uses a short-lived signed token and a server-side origin check, so only whitelisted sites can embed it.
          </div>
        </Card>
      </div>

      {/* About */}
      <Card>
        <SectionTitle title="About Mawrid" subtitle="مورد — source, supplier" right={<Info className="h-5 w-5 text-ink-faint" />} />
        <p className="text-sm leading-relaxed text-ink-soft">
          Mawrid is a multi-tenant, AI-powered operations platform for importers &amp; distributors. It runs the full
          loop — supplier catalog enrichment → procurement → goods received → selective storefront publishing →
          customer orders → invoicing → automated dunning — with AI through every step. One enriched catalog powers
          both the importer's internal tooling and a consumer storefront.
        </p>
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {[
            { icon: Cpu, label: "AI", val: "GPT-4o · RAG (6-technique) · 3-tier intent · guardrails" },
            { icon: Boxes, label: "Backend", val: "FastAPI · Postgres+pgvector · Redis/ARQ · MinIO · Vault" },
            { icon: ShieldCheck, label: "Isolation", val: "3-layer tenant isolation · HITL on every external write" },
          ].map((b) => (
            <div key={b.label} className="rounded-xl border border-line bg-white/[0.02] p-4">
              <div className="flex items-center gap-2 text-sm font-600 text-ink"><b.icon className="h-4 w-4 text-gold-soft" /> {b.label}</div>
              <p className="mt-1 text-xs leading-relaxed text-ink-faint">{b.val}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap gap-2 text-xs text-ink-faint">
          <span className="chip border-line bg-white/[0.02]">Capstone build</span>
          <span className="chip border-line bg-white/[0.02]">DEC-001 → DEC-029</span>
          <span className="chip border-line bg-white/[0.02]">Lebanon · MENA</span>
        </div>
      </Card>
    </div>
  );
}
