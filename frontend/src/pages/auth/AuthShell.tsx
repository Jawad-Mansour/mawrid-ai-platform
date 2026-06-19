// Feature: Auth — shared shell with a theme-aware 3D ambient scene + entrance motion
import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { AuthScene } from "@/components/AuthScene";

export function AuthShell({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden bg-radial-fade px-6 py-10">
      <AuthScene />

      <div className="relative z-10 w-full max-w-md">
        <motion.div
          className="mb-6 flex items-center gap-3"
          initial={{ opacity: 0, y: -14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", stiffness: 200, damping: 20 }}
        >
          <motion.img
            src="/new_icon.ico" alt="Mawrid"
            className="h-12 w-12 rounded-xl shadow-glow"
            initial={{ scale: 0, rotate: -90 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ type: "spring", stiffness: 260, damping: 18, delay: 0.1 }}
          />
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
