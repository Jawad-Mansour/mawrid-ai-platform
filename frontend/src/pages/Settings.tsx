// Feature: Settings — workspace, theme picker, Connect Gmail, about, widget embed
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Globe, LogOut, ShieldCheck, Check, Clock, Info, Cpu, Boxes, Mail, Spline } from "lucide-react";
import { apiGet, apiDelete, apiPatch, apiErr } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { Card, SectionTitle, Spinner } from "@/components/ui";
import { THEMES, useThemeStore } from "@/stores/theme";
import { cn } from "@/lib/utils";

export function Settings() {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useThemeStore();
  const [origins, setOrigins] = useState("");
  const qc = useQueryClient();
  const [params] = useSearchParams();

  const gmail = useQuery({ queryKey: ["gmail-status"], queryFn: () => apiGet<{ connected: boolean; email: string | null; configured: boolean }>("/auth/google/status") });
  useEffect(() => {
    const g = params.get("gmail");
    if (g === "connected") { toast.success("Gmail connected"); qc.invalidateQueries({ queryKey: ["gmail-status"] }); }
    else if (g === "error") toast.error("Couldn't connect Gmail — try again.");
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  async function connectGmail() {
    try { const r = await apiGet<{ url: string }>("/auth/google/start"); window.location.href = r.url; }
    catch (e) { toast.error(apiErr(e, "Couldn't start Google sign-in")); }
  }
  const disconnectGmail = useMutation({
    mutationFn: () => apiDelete("/auth/google/disconnect"),
    onSuccess: () => { toast.success("Gmail disconnected"); qc.invalidateQueries({ queryKey: ["gmail-status"] }); },
    onError: (e) => toast.error(apiErr(e, "Failed")),
  });

  const saveOrigins = useMutation({
    mutationFn: () => apiPatch("/widget/settings", { allowed_origins: origins }),
    onSuccess: () => toast.success("Widget origins updated"),
    onError: (e) => toast.error(apiErr(e, "Update failed")),
  });

  return (
    <div className="space-y-6">
      <SectionTitle title="Settings" subtitle="Appearance, workspace, and embed options." />

      {/* Connect Gmail */}
      <Card>
        <SectionTitle title="Connect Gmail" subtitle="Send POs, outreach & dunning from your own Gmail (lands in the inbox, not Junk) — and auto-detect supplier replies back."
          right={<Mail className="h-5 w-5 text-ink-faint" />} />
        {gmail.isLoading ? <div className="flex items-center gap-2 text-sm text-ink-soft"><Spinner className="h-4 w-4" /> Checking…</div>
          : gmail.data?.configured === false ? (
            <div className="rounded-xl border border-warn/30 bg-warn/10 p-3 text-sm text-warn">Google sign-in isn't configured on the server yet.</div>
          ) : gmail.data?.connected ? (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-sm text-ink">
                <span className="grid h-9 w-9 place-items-center rounded-lg bg-emerald/15 text-emerald-soft"><Check className="h-4 w-4" /></span>
                Connected as <b className="font-mono text-emerald-soft">{gmail.data.email}</b>
              </div>
              <button className="btn-ghost" disabled={disconnectGmail.isPending} onClick={() => disconnectGmail.mutate()}>
                {disconnectGmail.isPending ? <Spinner className="h-4 w-4" /> : <Spline className="h-4 w-4" />} Disconnect
              </button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-sm text-ink-soft">Connect your Gmail so emails go out from your address and replies are detected automatically.</div>
              <button className="btn-gold" onClick={connectGmail}><Mail className="h-4 w-4" /> Connect Gmail</button>
            </div>
          )}
        <p className="mt-3 text-[11px] text-ink-faint">We only request send + read access, and never store your password. You can disconnect anytime.</p>
      </Card>

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
