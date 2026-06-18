// Feature: shared "coming soon" page for deliberately-deferred features (real,
//          clearly-labelled — never a stub pretending to work).
import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { Card, SectionTitle } from "@/components/ui";

export function ComingSoon({ title, subtitle, tagline, points }: { title: string; subtitle: string; tagline: string; points: { label: string; detail: string }[] }) {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <SectionTitle title={title} subtitle={subtitle} right={<span className="chip border-grape/30 bg-grape/10 text-grape-soft"><Sparkles className="h-3.5 w-3.5" /> Coming soon</span>} />
      <Card>
        <div className="flex flex-col items-center gap-4 py-8 text-center">
          <motion.div className="grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-gold to-grape shadow-glow"
            animate={{ rotateY: [0, 360] }} transition={{ duration: 6, repeat: Infinity, ease: "linear" }} style={{ transformStyle: "preserve-3d" }}>
            <Sparkles className="h-7 w-7 text-bg" />
          </motion.div>
          <div className="text-lg font-800 text-ink">{tagline}</div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {points.map((p) => (
            <div key={p.label} className="rounded-xl border border-line bg-white/[0.02] p-3.5">
              <div className="text-sm font-700 text-ink">{p.label}</div>
              <div className="mt-0.5 text-xs text-ink-soft">{p.detail}</div>
            </div>
          ))}
        </div>
        <p className="mt-4 text-center text-[11px] text-ink-faint">This is a planned capability — surfaced here so the flow is clear. It is intentionally not active yet.</p>
      </Card>
    </div>
  );
}
