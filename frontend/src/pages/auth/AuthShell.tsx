// Feature: Auth — shared shell with animated ambient background
import type { ReactNode } from "react";

export function AuthShell({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden bg-radial-fade px-6 py-10">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-40 top-0 h-96 w-96 rounded-full bg-grape/10 blur-3xl animate-float" />
        <div className="absolute -right-32 bottom-0 h-96 w-96 rounded-full bg-gold/10 blur-3xl animate-float" style={{ animationDelay: "2.5s" }} />
        <div className="absolute left-1/2 top-1/3 h-64 w-64 -translate-x-1/2 rounded-full bg-emerald/5 blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
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
          {subtitle ? <p className="mb-6 mt-1 text-sm capitalize text-ink-soft">{subtitle}</p> : <div className="mb-6" />}
          {children}
        </div>
      </div>
    </div>
  );
}
