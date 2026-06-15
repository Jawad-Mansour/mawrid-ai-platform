// Feature: Onboarding — signup (Hybrid mode in capstone)
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/hooks/useAuth";
import { apiErr } from "@/lib/api";
import type { OperationalMode } from "@/lib/types";
import { Spinner } from "@/components/ui";

export function Signup() {
  const [params] = useSearchParams();
  const mode = (params.get("mode") as OperationalMode) || "hybrid";
  const { signup } = useAuth();
  const [company, setCompany] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await signup(company, email, password, mode);
      toast.success("Workspace provisioned — welcome to Mawrid");
    } catch (err) {
      toast.error(apiErr(err, "Signup failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Create your workspace" subtitle={`Operational mode: ${mode.replace("_", " ")}`}>
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="label">Business name</label>
          <input className="input" value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Acme Imports" required />
        </div>
        <div>
          <label className="label">Email</label>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@business.com" required />
        </div>
        <div>
          <label className="label">Password</label>
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Min 8 characters" required minLength={8} />
        </div>
        <button className="btn-gold w-full" disabled={busy}>
          {busy ? <Spinner className="h-4 w-4" /> : "Create workspace"}
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-ink-soft">
        Already registered? <Link to="/login" className="font-600 text-gold-soft hover:underline">Sign in</Link>
      </p>
    </AuthShell>
  );
}

export function AuthShell({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen place-items-center bg-radial-fade px-6">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center gap-3">
          <div className="grid h-12 w-12 place-items-center rounded-xl bg-gradient-to-br from-gold to-grape shadow-glow">
            <span className="text-xl font-800 text-bg">M</span>
          </div>
          <div>
            <div className="text-xl font-800 text-ink">Mawrid</div>
            <div className="text-xs uppercase tracking-widest text-ink-faint">AI Operations Platform</div>
          </div>
        </div>
        <div className="card p-7">
          <h1 className="text-2xl font-700 text-ink">{title}</h1>
          {subtitle && <p className="mb-6 mt-1 text-sm capitalize text-ink-soft">{subtitle}</p>}
          {!subtitle && <div className="mb-6" />}
          {children}
        </div>
      </div>
    </div>
  );
}
