// Feature: Auth — shared shell with animated ambient background + entrance motion
import type { ReactNode } from "react";
import { motion } from "framer-motion";

export function AuthShell({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden bg-radial-fade px-6 py-10">
      {/* ambient drifting orbs (animate in, then float) */}
      <motion.div
        className="pointer-events-none absolute inset-0"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1.2 }}
      >
        <div className="absolute -left-40 top-0 h-96 w-96 rounded-full bg-grape/10 blur-3xl animate-float" />
        <div className="absolute -right-32 bottom-0 h-96 w-96 rounded-full bg-gold/10 blur-3xl animate-float" style={{ animationDelay: "2.5s" }} />
        <div className="absolute left-1/2 top-1/3 h-64 w-64 -translate-x-1/2 rounded-full bg-emerald/5 blur-3xl" />
      </motion.div>

      <div className="relative w-full max-w-md">
        <motion.div
          className="mb-6 flex items-center gap-3"
          initial={{ opacity: 0, y: -14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", stiffness: 200, damping: 20 }}
        >
          <motion.div
            className="grid h-12 w-12 place-items-center rounded-xl bg-gradient-to-br from-gold to-grape shadow-glow"
            initial={{ scale: 0, rotate: -90 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ type: "spring", stiffness: 260, damping: 18, delay: 0.1 }}
          >
            <span className="text-xl font-800 text-bg">M</span>
          </motion.div>
          <div>
            <div className="text-xl font-800 text-ink">Mawrid</div>
            <div className="text-xs uppercase tracking-widest text-ink-faint">AI Operations Platform</div>
          </div>
        </motion.div>

        <motion.div
          className="card p-7"
          initial={{ opacity: 0, y: 24, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ type: "spring", stiffness: 160, damping: 22, delay: 0.05 }}
        >
          <h1 className="text-2xl font-700 text-ink">{title}</h1>
          {subtitle ? <p className="mb-6 mt-1 text-sm capitalize text-ink-soft">{subtitle}</p> : <div className="mb-6" />}
          {children}
        </motion.div>
      </div>
    </div>
  );
}
