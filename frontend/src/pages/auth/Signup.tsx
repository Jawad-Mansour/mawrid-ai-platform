// Feature: Onboarding — signup with password UX, validation & success animation
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { apiErr } from "@/lib/api";
import type { OperationalMode } from "@/lib/types";
import { Spinner } from "@/components/ui";
import { PasswordField, PasswordStrength, SuccessSplash, passwordValid } from "@/components/auth/AuthBits";
import { AuthShell } from "./AuthShell";

export function Signup() {
  const [params] = useSearchParams();
  const mode = (params.get("mode") as OperationalMode) || "hybrid";
  const { signup } = useAuth();
  const navigate = useNavigate();

  const [company, setCompany] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const mismatch = confirm.length > 0 && confirm !== password;
  const canSubmit = company.trim() && email.trim() && passwordValid(password) && password === confirm;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!passwordValid(password)) return setError("Password needs at least 8 characters and one special character.");
    if (password !== confirm) return setError("Passwords don't match.");
    setBusy(true);
    try {
      await signup(company, email, password, mode);
      setDone(true);
      setTimeout(() => navigate("/"), 1100);
    } catch (err) {
      setError(apiErr(err, "Signup failed"));
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Create your workspace" subtitle={`Operational mode: ${mode.replace("_", " ")}`}>
      <SuccessSplash show={done} message="Workspace ready — welcome to Mawrid" />
      <form onSubmit={onSubmit} className="space-y-4">
        {error && (
          <div className="flex items-start gap-2 rounded-xl border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
          </div>
        )}
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
          <PasswordField value={password} onChange={setPassword} placeholder="Create a strong password" required />
          <PasswordStrength password={password} />
        </div>
        <div>
          <label className="label">Confirm password</label>
          <PasswordField value={confirm} onChange={setConfirm} placeholder="Re-enter password" required />
          {mismatch && <p className="mt-1 text-xs text-danger">Passwords don't match</p>}
          {confirm.length > 0 && !mismatch && <p className="mt-1 text-xs text-emerald-soft">Passwords match ✓</p>}
        </div>
        <button className="btn-gold w-full" disabled={busy || !canSubmit}>
          {busy ? <Spinner className="h-4 w-4" /> : "Create workspace"}
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-ink-soft">
        Already registered? <Link to="/login" className="font-600 text-gold-soft hover:underline">Sign in</Link>
      </p>
    </AuthShell>
  );
}
