// Feature: Auth — login with show-password, error display & success animation
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { apiErr } from "@/lib/api";
import { AuthShell } from "./AuthShell";
import { Spinner } from "@/components/ui";
import { PasswordField, SuccessSplash } from "@/components/auth/AuthBits";

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
      setDone(true);
      setTimeout(() => navigate("/"), 900);
    } catch (err) {
      setError(apiErr(err, "Invalid email or password"));
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Welcome back" subtitle="Sign in to your command center">
      <SuccessSplash show={done} message="Signed in" />
      <form onSubmit={onSubmit} className="space-y-4">
        {error && (
          <div className="flex items-start gap-2 rounded-xl border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
          </div>
        )}
        <div>
          <label className="label">Email</label>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@business.com" required />
        </div>
        <div>
          <label className="label">Password</label>
          <PasswordField value={password} onChange={setPassword} required />
        </div>
        <button className="btn-gold w-full" disabled={busy}>
          {busy ? <Spinner className="h-4 w-4" /> : "Sign in"}
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-ink-soft">
        New here? <Link to="/choose-mode" className="font-600 text-gold-soft hover:underline">Create a workspace</Link>
      </p>
    </AuthShell>
  );
}
