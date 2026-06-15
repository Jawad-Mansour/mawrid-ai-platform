// Feature: Auth — reusable bits (password field, strength meter, success splash)
import { useState, type InputHTMLAttributes } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Eye, EyeOff, Check, X, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";

export function PasswordField({
  value,
  onChange,
  placeholder = "Password",
  ...rest
}: { value: string; onChange: (v: string) => void } & InputHTMLAttributes<HTMLInputElement>) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <input
        {...rest}
        type={show ? "text" : "password"}
        className="input pr-11"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
      <button
        type="button"
        onClick={() => setShow((s) => !s)}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-faint hover:text-ink"
        tabIndex={-1}
        aria-label={show ? "Hide password" : "Show password"}
      >
        {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}

export interface PwRule {
  label: string;
  ok: boolean;
}
export function passwordRules(pw: string): PwRule[] {
  return [
    { label: "At least 8 characters", ok: pw.length >= 8 },
    { label: "One special character", ok: /[^A-Za-z0-9]/.test(pw) },
    { label: "One uppercase letter", ok: /[A-Z]/.test(pw) },
    { label: "One number", ok: /[0-9]/.test(pw) },
  ];
}
export function passwordValid(pw: string): boolean {
  // Required: min 8 + special character (per spec). Upper/number strengthen it.
  return pw.length >= 8 && /[^A-Za-z0-9]/.test(pw);
}

export function PasswordStrength({ password }: { password: string }) {
  const rules = passwordRules(password);
  const score = rules.filter((r) => r.ok).length;
  const pct = (score / rules.length) * 100;
  const tone = score <= 1 ? "bg-danger" : score === 2 ? "bg-warn" : score === 3 ? "bg-gold" : "bg-emerald";
  const label = score <= 1 ? "Weak" : score === 2 ? "Fair" : score === 3 ? "Good" : "Strong";
  if (!password) return null;
  return (
    <div className="mt-2">
      <div className="flex items-center justify-between text-xs">
        <span className="text-ink-faint">Password strength</span>
        <span className="font-600 text-ink-soft">{label}</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/10">
        <div className={cn("h-full rounded-full transition-all duration-300", tone)} style={{ width: `${pct}%` }} />
      </div>
      <ul className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
        {rules.map((r) => (
          <li key={r.label} className={cn("flex items-center gap-1.5 text-xs", r.ok ? "text-emerald-soft" : "text-ink-faint")}>
            {r.ok ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />} {r.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SuccessSplash({ show, message }: { show: boolean; message: string }) {
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          className="fixed inset-0 z-50 grid place-items-center bg-bg/80 backdrop-blur-md"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            initial={{ scale: 0.6, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 200, damping: 16 }}
            className="flex flex-col items-center gap-4"
          >
            <motion.div
              className="grid h-24 w-24 place-items-center rounded-full bg-gradient-to-br from-emerald to-emerald-soft shadow-glow"
              initial={{ rotate: -20 }}
              animate={{ rotate: 0 }}
            >
              <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 0.15, type: "spring" }}>
                <CheckCircle2 className="h-12 w-12 text-white" />
              </motion.div>
            </motion.div>
            <p className="text-lg font-700 text-ink">{message}</p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
