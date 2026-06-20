// Feature: Settings — tabbed: General (Gmail, theme, workspace, widget, about) and
//          Google Cloud Setup (a complete step-by-step guide to wire Connect Gmail).
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Globe, LogOut, ShieldCheck, Check, Clock, Info, Cpu, Boxes, Mail, Spline, Copy, ExternalLink, AlertTriangle, Cloud, SlidersHorizontal } from "lucide-react";
import { apiGet, apiDelete, apiPatch, apiErr } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { Card, SectionTitle, Spinner } from "@/components/ui";
import { THEMES, useThemeStore } from "@/stores/theme";
import { cn } from "@/lib/utils";

type Tab = "general" | "google";

export function Settings() {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useThemeStore();
  const [origins, setOrigins] = useState("");
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const [tab, setTab] = useState<Tab>(params.get("tab") === "google" ? "google" : "general");

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

  const connected = gmail.data?.connected;
  const TABS: { key: Tab; label: string; icon: typeof Mail }[] = [
    { key: "general", label: "General", icon: SlidersHorizontal },
    { key: "google", label: "Google Cloud Setup", icon: Cloud },
  ];

  return (
    <div className="space-y-6">
      <SectionTitle title="Settings" subtitle="Appearance, workspace, email connection and embed options." />

      {/* tab bar */}
      <div className="flex w-max gap-1 rounded-xl border border-line bg-white/[0.02] p-1">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={cn("flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-600 transition-all", tab === t.key ? "bg-gold/15 text-gold-soft" : "text-ink-soft hover:text-ink")}>
            <t.icon className="h-4 w-4" /> {t.label}
            {t.key === "google" && connected && <span className="ml-0.5 grid h-4 w-4 place-items-center rounded-full bg-emerald/20 text-emerald-soft"><Check className="h-2.5 w-2.5" /></span>}
          </button>
        ))}
      </div>

      {tab === "general" && (
        <>
          {/* Connect Gmail */}
          <Card>
            <SectionTitle title="Connect Gmail" subtitle="Send POs, outreach & dunning from your own Gmail (lands in the inbox, not Junk) — and auto-detect supplier replies back."
              right={<Mail className="h-5 w-5 text-ink-faint" />} />
            {gmail.isLoading ? <div className="flex items-center gap-2 text-sm text-ink-soft"><Spinner className="h-4 w-4" /> Checking…</div>
              : gmail.data?.configured === false ? (
                <div className="rounded-xl border border-warn/30 bg-warn/10 p-3 text-sm text-warn">Google sign-in isn't configured on the server yet — see the <button onClick={() => setTab("google")} className="underline">Google Cloud Setup</button> tab.</div>
              ) : connected ? (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2 text-sm text-ink">
                    <span className="grid h-9 w-9 place-items-center rounded-lg bg-emerald/15 text-emerald-soft"><Check className="h-4 w-4" /></span>
                    Connected as <b className="font-mono text-emerald-soft">{gmail.data?.email}</b>
                  </div>
                  <button className="btn-ghost" disabled={disconnectGmail.isPending} onClick={() => disconnectGmail.mutate()}>
                    {disconnectGmail.isPending ? <Spinner className="h-4 w-4" /> : <Spline className="h-4 w-4" />} Disconnect
                  </button>
                </div>
              ) : (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="text-sm text-ink-soft">Connect your Gmail so emails go out from your address and replies are detected automatically. First time? Open the <button onClick={() => setTab("google")} className="text-gold-soft underline">Google Cloud Setup</button> guide.</div>
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
        </>
      )}

      {tab === "google" && (
        <GoogleCloudGuide connected={!!connected} email={gmail.data?.email ?? null} configured={gmail.data?.configured !== false} onConnect={connectGmail} />
      )}
    </div>
  );
}

// ── Google Cloud Setup guide ────────────────────────────────────────────────────

function Copyable({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <button type="button"
      onClick={() => navigator.clipboard?.writeText(text).then(() => { setDone(true); toast.success("Copied"); setTimeout(() => setDone(false), 1200); })}
      className="group flex w-full items-center justify-between gap-2 rounded-lg border border-line bg-black/25 px-3 py-2 text-left font-mono text-xs text-ink hover:border-gold/40">
      <span className="truncate">{text}</span>
      {done ? <Check className="h-3.5 w-3.5 shrink-0 text-emerald-soft" /> : <Copy className="h-3.5 w-3.5 shrink-0 text-ink-faint group-hover:text-ink" />}
    </button>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-gold/40 bg-gold/10 text-xs font-800 text-gold-soft">{n}</div>
      <div className="min-w-0 flex-1 pb-1">
        <div className="text-sm font-700 text-ink">{title}</div>
        <div className="mt-1 space-y-1.5 text-[13px] leading-relaxed text-ink-soft">{children}</div>
      </div>
    </div>
  );
}

function Ext({ href, children }: { href: string; children: React.ReactNode }) {
  return <a href={href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-gold-soft underline decoration-dotted underline-offset-2 hover:text-gold">{children}<ExternalLink className="h-3 w-3" /></a>;
}

function GoogleCloudGuide({ connected, email, configured, onConnect }: { connected: boolean; email: string | null; configured: boolean; onConnect: () => void }) {
  // Dev redirect URI = the BACKEND origin + /auth/google/callback (port 8000 locally).
  const redirectDev = "http://localhost:8000/auth/google/callback";
  const scopes = ["https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/gmail.readonly"];

  return (
    <div className="space-y-6">
      <Card>
        <SectionTitle title="Connect with Google Cloud" subtitle="A one-time setup so Mawrid can send & read email through your own Gmail. No domain, no billing card — Gmail API in Testing mode is free."
          right={<Cloud className="h-5 w-5 text-ink-faint" />} />

        {/* live status */}
        <div className={cn("mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3 text-sm",
          connected ? "border-emerald/30 bg-emerald/10" : configured ? "border-line bg-white/[0.02]" : "border-warn/30 bg-warn/10")}>
          {connected ? (
            <span className="flex items-center gap-2 text-emerald-soft"><Check className="h-4 w-4" /> Connected as <b className="font-mono">{email}</b></span>
          ) : configured ? (
            <span className="flex items-center gap-2 text-ink-soft"><Mail className="h-4 w-4" /> Server is configured — finish the steps below, then connect your Gmail.</span>
          ) : (
            <span className="flex items-center gap-2 text-warn"><AlertTriangle className="h-4 w-4" /> Server credentials not seeded yet (step 6 is done by the developer).</span>
          )}
          {!connected && <button className="btn-gold !py-1.5 text-xs" onClick={onConnect}><Mail className="h-3.5 w-3.5" /> Connect Gmail</button>}
        </div>

        <div className="space-y-5">
          <Step n={0} title="Turn on 2-Step Verification (once, on your Google account)">
            <p>Google Cloud requires it. <Ext href="https://myaccount.google.com/signinoptions/two-step-verification">Google Account → Security → 2-Step Verification</Ext> → turn it on.</p>
          </Step>

          <Step n={1} title="Create a project — ignore every “free trial / $300” banner">
            <p>Open <Ext href="https://console.cloud.google.com/projectcreate">console.cloud.google.com/projectcreate</Ext> → name it <b>Mawrid</b>, Organization <b>No organization</b> → <b>Create</b>, then select it.</p>
            <div className="flex items-start gap-1.5 rounded-lg border border-warn/30 bg-warn/10 p-2 text-[12px] text-warn"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> Those “Start free / Try for free” banners are the paid trial and ask for a card. You don’t need them — just close them.</div>
          </Step>

          <Step n={2} title="Enable the Gmail API">
            <p><Ext href="https://console.cloud.google.com/apis/library/gmail.googleapis.com">APIs &amp; Services → Library</Ext> → search <b>Gmail API</b> → <b>Enable</b>.</p>
          </Step>

          <Step n={3} title="OAuth consent screen">
            <p><Ext href="https://console.cloud.google.com/apis/credentials/consent">APIs &amp; Services → OAuth consent screen</Ext> → User type <b>External</b> → <b>Create</b>.</p>
            <p>App name <b>Mawrid</b>, support email &amp; developer contact = yours → <b>Save and continue</b>.</p>
            <p><b>Scopes → Add or remove scopes</b> → add these two, then <b>Update</b>:</p>
            <div className="space-y-1.5">{scopes.map((s) => <Copyable key={s} text={s} />)}</div>
            <p><b>Test users → Add users</b> → add every Gmail you’ll send/test with (only these can connect while in Testing).</p>
            <p>Leave <b>Publishing status = Testing</b> — no Google review needed this way.</p>
          </Step>

          <Step n={4} title="Create the OAuth client + add the redirect URI">
            <p><Ext href="https://console.cloud.google.com/apis/credentials">APIs &amp; Services → Credentials → Create Credentials → OAuth client ID</Ext>.</p>
            <p>Application type <b>Web application</b>, name <b>Mawrid Web</b>. Under <b>Authorized redirect URIs → Add URI</b>, paste exactly:</p>
            <Copyable text={redirectDev} />
            <p className="text-[12px] text-ink-faint">In production, also add <span className="font-mono">https://YOUR_HOST/auth/google/callback</span>. The path must match exactly or Google rejects the sign-in.</p>
            <p>Click <b>Create</b>.</p>
          </Step>

          <Step n={5} title="Copy the Client ID & Client Secret">
            <p>The popup shows them (re-openable any time under Credentials):</p>
            <div className="rounded-lg border border-line bg-black/25 px-3 py-2 font-mono text-xs text-ink-soft">Client ID:&nbsp;&nbsp;&nbsp;&nbsp;…apps.googleusercontent.com<br />Client Secret: GOCSPX-…</div>
          </Step>

          <Step n={6} title="Hand them to the developer (server side, one time)">
            <p>They’re seeded into the secret store (Vault, gitignored — never committed):</p>
            <Copyable text="secret/mawrid/google → { client_id, client_secret }" />
            <p>Your per-user Gmail <b>refresh token</b> (created when you click Connect) is stored per-tenant, never in git.</p>
          </Step>

          <Step n={7} title="Connect your Gmail">
            <p>Back here → <b>Connect Gmail</b> → pick your account → allow. Emails now send <b>as you</b> (inbox, not Junk) and replies are auto-detected, threaded and comprehended (arrival date → tracking, MOQ, change requests).</p>
            {!connected && <button className="btn-gold !py-1.5 text-xs" onClick={onConnect}><Mail className="h-3.5 w-3.5" /> Connect Gmail now</button>}
          </Step>
        </div>
      </Card>

      <Card>
        <SectionTitle title="Good to know" right={<Info className="h-5 w-5 text-ink-faint" />} />
        <ul className="space-y-2 text-[13px] leading-relaxed text-ink-soft">
          <li className="flex gap-2"><Clock className="mt-0.5 h-4 w-4 shrink-0 text-gold-soft" /> In <b>Testing</b> mode, refresh tokens for an unverified app expire after <b>~7 days</b> — just click <b>Connect Gmail</b> again weekly. Perfect for the demo.</li>
          <li className="flex gap-2"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-gold-soft" /> Only the <b>test users</b> you added can connect until the app is verified.</li>
          <li className="flex gap-2"><Globe className="mt-0.5 h-4 w-4 shrink-0 text-gold-soft" /> For a public launch, submit the app for <Ext href="https://support.google.com/cloud/answer/13463073">Google OAuth verification</Ext> (needs a privacy policy + verified domain) to make tokens permanent and allow any user.</li>
          <li className="flex gap-2"><Mail className="mt-0.5 h-4 w-4 shrink-0 text-gold-soft" /> Quick fallback with no OAuth: Google Account → Security → <b>App passwords</b> → create one for “Mail”; the developer seeds <span className="font-mono">secret/mawrid/imap</span> and the IMAP poller reads your inbox in ~2 minutes (your account only).</li>
        </ul>
      </Card>
    </div>
  );
}
