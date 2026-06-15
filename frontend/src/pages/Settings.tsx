// Feature: Settings — tenant info, widget embed origins, sign out
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Globe, LogOut, ShieldCheck } from "lucide-react";
import { apiPatch, apiErr } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { Card, SectionTitle } from "@/components/ui";

export function Settings() {
  const { user, logout } = useAuth();
  const [origins, setOrigins] = useState("");

  const saveOrigins = useMutation({
    mutationFn: () => apiPatch("/widget/settings", { allowed_origins: origins }),
    onSuccess: () => toast.success("Widget origins updated"),
    onError: (e) => toast.error(apiErr(e, "Update failed")),
  });

  return (
    <div className="space-y-6">
      <SectionTitle title="Settings" subtitle="Workspace configuration and embed options." />

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
              <div key={k} className="flex items-center justify-between gap-3 border-b border-line/60 pb-2">
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
    </div>
  );
}
