// Feature: Catalog Enrichment — 3D box: open & inviting before enrichment, then it
//          closes and spins while products are researched one-by-one.
import { motion } from "framer-motion";
import { Sparkles, Globe, FileText, ImageIcon, ListChecks } from "lucide-react";

const S = 104; // box size (px)
const H = S / 2;
const faceBase =
  "absolute rounded-lg border border-gold/50 bg-gradient-to-br from-gold/30 to-grape/30 shadow-glow backdrop-blur-sm";

/** A 3D box. phase "open" = lid up + sparkles rising; "enriching" = lid closed + spinning. */
export function EnrichBox({ phase }: { phase: "open" | "enriching" }) {
  const spinning = phase === "enriching";
  const faceStyle = { width: S, height: S, left: "50%", top: "50%", marginLeft: -H, marginTop: -H } as const;

  return (
    <div className="relative grid h-52 w-full place-items-center" style={{ perspective: 900 }}>
      {/* sparkles rising out of the open box */}
      {phase === "open" &&
        [0, 1, 2, 3, 4].map((i) => (
          <motion.div
            key={i}
            className="absolute"
            style={{ left: `calc(50% + ${(i - 2) * 16}px)` }}
            initial={{ y: 10, opacity: 0 }}
            animate={{ y: [-10, -54], opacity: [0, 1, 0] }}
            transition={{ duration: 2.2, repeat: Infinity, delay: i * 0.35 }}
          >
            <Sparkles className="h-4 w-4 text-gold" />
          </motion.div>
        ))}

      <motion.div
        className="relative"
        style={{ width: S, height: S, transformStyle: "preserve-3d" }}
        animate={{ rotateX: 58, rotateY: spinning ? 360 : 0, y: phase === "open" ? [0, -6, 0] : 0 }}
        transition={{
          rotateY: spinning ? { duration: 4.5, repeat: Infinity, ease: "linear" } : { duration: 0.6 },
          rotateX: { duration: 0.6 },
          y: { duration: 3, repeat: Infinity },
        }}
      >
        {/* walls + floor (open-top box) */}
        <div className={faceBase} style={{ ...faceStyle, transform: `translateZ(${H}px)` }} />
        <div className={faceBase} style={{ ...faceStyle, transform: `rotateY(180deg) translateZ(${H}px)` }} />
        <div className={faceBase} style={{ ...faceStyle, transform: `rotateY(90deg) translateZ(${H}px)` }} />
        <div className={faceBase} style={{ ...faceStyle, transform: `rotateY(-90deg) translateZ(${H}px)` }} />
        <div className={`${faceBase} grid place-items-center`} style={{ ...faceStyle, transform: `rotateX(90deg) translateZ(${H}px)` }}>
          <Sparkles className="h-8 w-8 text-gold/70" />
        </div>

        {/* lid — hinged at the back edge: open (up) when idle, closed when enriching */}
        <div style={{ ...faceStyle, position: "absolute", transformStyle: "preserve-3d", transform: `translateZ(${H}px) rotateX(-90deg)`, transformOrigin: "top" }}>
          <motion.div
            className={`${faceBase} grid place-items-center`}
            style={{ width: S, height: S, transformOrigin: "top" }}
            animate={{ rotateX: phase === "open" ? -78 : 0 }}
            transition={{ type: "spring", stiffness: 120, damping: 14 }}
          >
            <Sparkles className="h-7 w-7 text-grape-soft" />
          </motion.div>
        </div>
      </motion.div>

      {/* center glow */}
      <motion.div
        className="pointer-events-none absolute left-1/2 top-1/2 h-20 w-20 -translate-x-1/2 -translate-y-1/2 rounded-full bg-gold/30 blur-2xl"
        animate={{ scale: spinning ? [1, 1.35, 1] : [1, 1.1, 1], opacity: [0.4, 0.8, 0.4] }}
        transition={{ duration: 2, repeat: Infinity }}
      />
    </div>
  );
}

const STEPS = [
  { icon: Globe, label: "Searching Icecat + web" },
  { icon: ImageIcon, label: "Finding the real product image" },
  { icon: FileText, label: "Writing the description" },
  { icon: ListChecks, label: "Extracting specifications" },
];

export function EnrichLoader({ done, total }: { done: number; total: number }) {
  const pct = total ? Math.round((done / total) * 100) : 0;
  return (
    <div className="flex flex-col items-center gap-5 py-4">
      <EnrichBox phase="enriching" />
      <div className="text-center">
        <div className="text-lg font-800 text-ink">Enriching your catalogue…</div>
        <div className="mt-1 text-sm text-ink-faint">Each product is researched one-by-one for its real image, description &amp; specs.</div>
      </div>
      <div className="w-full max-w-sm">
        <div className="mb-1 flex justify-between text-xs text-ink-soft">
          <span>{done} of {total} enriched</span>
          <span className="font-mono">{pct}%</span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-full bg-white/10">
          <motion.div className="h-full rounded-full bg-gradient-to-r from-gold to-grape" animate={{ width: `${pct}%` }} transition={{ duration: 0.6 }} />
        </div>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {STEPS.map((s, i) => (
          <motion.span key={s.label} className="chip border-line bg-white/[0.03] text-ink-soft"
            animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 2.4, repeat: Infinity, delay: i * 0.5 }}>
            <s.icon className="h-3.5 w-3.5 text-gold-soft" /> {s.label}
          </motion.span>
        ))}
      </div>
    </div>
  );
}
