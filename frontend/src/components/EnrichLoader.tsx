// Feature: Catalog Enrichment — 3D loading animation shown while products are
//          enriched one-by-one in the background.
import { motion } from "framer-motion";
import { Sparkles, Globe, FileText, ImageIcon, ListChecks } from "lucide-react";

const STEPS = [
  { icon: Globe, label: "Searching Icecat + web" },
  { icon: ImageIcon, label: "Fetching real product image" },
  { icon: FileText, label: "Writing description" },
  { icon: ListChecks, label: "Extracting specifications" },
];

export function EnrichLoader({ done, total }: { done: number; total: number }) {
  const pct = total ? Math.round((done / total) * 100) : 0;
  return (
    <div className="flex flex-col items-center gap-6 py-6">
      {/* 3D rotating cube of product cards */}
      <div className="relative h-32 w-32" style={{ perspective: 800 }}>
        <motion.div
          className="absolute inset-0"
          style={{ transformStyle: "preserve-3d" }}
          animate={{ rotateY: 360, rotateX: [0, 12, 0] }}
          transition={{ rotateY: { duration: 6, repeat: Infinity, ease: "linear" }, rotateX: { duration: 3, repeat: Infinity } }}
        >
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="absolute inset-0 grid place-items-center rounded-2xl border border-gold/40 bg-gradient-to-br from-gold/15 to-grape/15 shadow-glow backdrop-blur"
              style={{ transform: `rotateY(${i * 90}deg) translateZ(64px)` }}
            >
              <Sparkles className="h-8 w-8 text-gold" />
            </div>
          ))}
        </motion.div>
        {/* center glow */}
        <motion.div
          className="absolute left-1/2 top-1/2 h-16 w-16 -translate-x-1/2 -translate-y-1/2 rounded-full bg-gold/30 blur-2xl"
          animate={{ scale: [1, 1.3, 1], opacity: [0.5, 0.9, 0.5] }}
          transition={{ duration: 2, repeat: Infinity }}
        />
      </div>

      <div className="text-center">
        <div className="text-lg font-800 text-ink">Enriching your catalogue…</div>
        <div className="mt-1 text-sm text-ink-faint">Each product is researched one-by-one for its real image, description &amp; specs.</div>
      </div>

      {/* progress */}
      <div className="w-full max-w-sm">
        <div className="mb-1 flex justify-between text-xs text-ink-soft">
          <span>{done} of {total} enriched</span>
          <span className="font-mono">{pct}%</span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-full bg-white/10">
          <motion.div className="h-full rounded-full bg-gradient-to-r from-gold to-grape" animate={{ width: `${pct}%` }} transition={{ duration: 0.6 }} />
        </div>
      </div>

      {/* rotating step labels */}
      <div className="flex flex-wrap justify-center gap-2">
        {STEPS.map((s, i) => (
          <motion.span
            key={s.label}
            className="chip border-line bg-white/[0.03] text-ink-soft"
            animate={{ opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 2.4, repeat: Infinity, delay: i * 0.5 }}
          >
            <s.icon className="h-3.5 w-3.5 text-gold-soft" /> {s.label}
          </motion.span>
        ))}
      </div>
    </div>
  );
}
