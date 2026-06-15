// Feature: All — shared presentational primitives
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("card p-5", className)}>{children}</div>;
}

export function SectionTitle({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div>
        <h2 className="text-lg font-700 text-ink">{title}</h2>
        {subtitle && <p className="mt-0.5 text-sm text-ink-soft">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

const TONE: Record<string, string> = {
  enriched: "border-emerald/40 bg-emerald/15 text-emerald-soft",
  published: "border-emerald/40 bg-emerald/15 text-emerald-soft",
  approved: "border-emerald/40 bg-emerald/15 text-emerald-soft",
  in_stock: "border-emerald/40 bg-emerald/15 text-emerald-soft",
  ok: "border-emerald/40 bg-emerald/15 text-emerald-soft",
  active: "border-emerald/40 bg-emerald/15 text-emerald-soft",
  pending: "border-gold/40 bg-gold/15 text-gold-soft",
  processing: "border-gold/40 bg-gold/15 text-gold-soft",
  pending_hitl: "border-gold/40 bg-gold/15 text-gold-soft",
  warning: "border-warn/40 bg-warn/15 text-warn",
  low_stock: "border-warn/40 bg-warn/15 text-warn",
  failed: "border-danger/40 bg-danger/15 text-danger",
  rejected: "border-danger/40 bg-danger/15 text-danger",
  severe: "border-danger/40 bg-danger/15 text-danger",
  dlq: "border-danger/40 bg-danger/15 text-danger",
  out_of_stock: "border-danger/40 bg-danger/15 text-danger",
};

export function StatusBadge({ status }: { status: string }) {
  const tone = TONE[status?.toLowerCase()] ?? "border-line bg-white/5 text-ink-soft";
  return <span className={cn("chip", tone)}>{(status ?? "—").replace(/_/g, " ")}</span>;
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-5 w-5 animate-spin text-gold", className)} />;
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-ink-soft">
      <Spinner /> <span className="text-sm">{label}</span>
    </div>
  );
}

export function EmptyState({ icon, title, hint }: { icon?: ReactNode; title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-line py-14 text-center">
      {icon && <div className="text-ink-faint">{icon}</div>}
      <p className="font-600 text-ink">{title}</p>
      {hint && <p className="max-w-sm text-sm text-ink-soft">{hint}</p>}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger">
      {message}
    </div>
  );
}
