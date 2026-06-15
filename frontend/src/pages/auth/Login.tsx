// Feature: Auth — login
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/hooks/useAuth";
import { apiErr } from "@/lib/api";
import { AuthShell } from "./Signup";
import { Spinner } from "@/components/ui";

export function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email, password);
      toast.success("Welcome back");
    } catch (err) {
      toast.error(apiErr(err, "Invalid credentials"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Sign in">
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="label">Email</label>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@business.com" required />
        </div>
        <div>
          <label className="label">Password</label>
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
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
