// Feature: Catalog Enrichment — 3D box: open & inviting before enrichment, then it
//          closes and spins while products are researched one-by-one.
import { motion } from "framer-motion";
import { Sparkles, Globe, FileText, ImageIcon, ListChecks } from "lucide-react";

const S = 104; // box size (px)
const H = S / 2;
const faceBase =
  "absolute rounded-lg border border-gold/50 bg-gradient-to-br from-gold/30 to-grape/30 shadow-glow backdrop-blur-sm";

/** A proper 3D cube. "enriching" = closed cube spinning, viewed from the front;
 *  "open" = the top opens like a lid with sparkles rising. */
export function EnrichBox({ phase }: { phase: "open" | "enriching" }) {
  const spinning = phase === "enriching";
  const faceStyle = { width: S, height: S, left: "50%", top: "50%", marginLeft: -H, marginTop: -H } as const;
  // small tilt = front view (not top-down); a bit more tilt when open so you see inside
  const tilt = spinning ? -18 : -46;

  return (
    <div className="relative grid h-56 w-full place-items-center" style={{ perspective: 760 }}>
      {/* sparkles rising out of the open box */}
      {phase === "open" &&
        [0, 1, 2, 3, 4].map((i) => (
          <motion.div
            key={i}
            className="absolute"
            style={{ left: `calc(50% + ${(i - 2) * 16}px)` }}
            initial={{ y: 10, opacity: 0 }}
            animate={{ y: [-10, -58], opacity: [0, 1, 0] }}
            transition={{ duration: 2.2, repeat: Infinity, delay: i * 0.35 }}
          >
            <Sparkles className="h-4 w-4 text-gold" />
          </motion.div>
        ))}

      <motion.div
        className="relative"
        style={{ width: S, height: S, transformStyle: "preserve-3d" }}
        animate={{ rotateX: tilt, rotateY: spinning ? 360 : -32, y: phase === "open" ? [0, -6, 0] : 0 }}
        transition={{
          rotateY: spinning ? { duration: 7, repeat: Infinity, ease: "linear" } : { duration: 0.6 },
          rotateX: { duration: 0.6 },
          y: { duration: 3, repeat: Infinity },
        }}
      >
        {/* the 4 sides + bottom of a clean cube */}
        <div className={`${faceBase} grid place-items-center`} style={{ ...faceStyle, transform: `translateZ(${H}px)` }}>
          <Sparkles className="h-8 w-8 text-gold/80" />
        </div>
        <div className={faceBase} style={{ ...faceStyle, transform: `rotateY(180deg) translateZ(${H}px)` }} />
        <div className={faceBase} style={{ ...faceStyle, transform: `rotateY(90deg) translateZ(${H}px)` }} />
        <div className={`${faceBase} grid place-items-center`} style={{ ...faceStyle, transform: `rotateY(-90deg) translateZ(${H}px)` }}>
          <Sparkles className="h-7 w-7 text-grape-soft/80" />
        </div>
        <div className={faceBase} style={{ ...faceStyle, transform: `rotateX(-90deg) translateZ(${H}px)` }} />

        {/* the top = a lid hinged at the back edge (closed when enriching, open when idle) */}
        <div style={{ ...faceStyle, position: "absolute", transformStyle: "preserve-3d", transform: `rotateX(90deg) translateZ(${H}px)`, transformOrigin: "top" }}>
          <motion.div
            className={`${faceBase} grid place-items-center`}
            style={{ width: S, height: S, transformOrigin: "top" }}
            animate={{ rotateX: phase === "open" ? -112 : 0 }}
            transition={{ type: "spring", stiffness: 120, damping: 14 }}
          >
            <Sparkles className="h-7 w-7 text-gold/70" />
          </motion.div>
        </div>
      </motion.div>

      {/* center glow */}
      <motion.div
        className="pointer-events-none absolute left-1/2 top-1/2 h-24 w-24 -translate-x-1/2 -translate-y-1/2 rounded-full bg-gold/30 blur-2xl"
        animate={{ scale: spinning ? [1, 1.35, 1] : [1, 1.1, 1], opacity: [0.4, 0.8, 0.4] }}
        transition={{ duration: 2, repeat: Infinity }}
      />
    </div>
  );
}

/** Enriching visual — a glowing AI core with orbiting rings (distinct from the box). */
export function EnrichOrbit() {
  const ring = "absolute inset-0 rounded-full border-2";
  return (
    <div className="relative grid h-44 w-full place-items-center" style={{ perspective: 700 }}>
      <div className="relative h-36 w-36" style={{ transformStyle: "preserve-3d" }}>
        {/* orbiting rings on different axes */}
        <motion.div className={`${ring} border-gold/50`} style={{ transformStyle: "preserve-3d" }} animate={{ rotateX: 70, rotateZ: 360 }} transition={{ rotateZ: { duration: 4, repeat: Infinity, ease: "linear" } }}>
          <span className="absolute -top-1.5 left-1/2 h-3 w-3 -translate-x-1/2 rounded-full bg-gold shadow-glow" />
        </motion.div>
        <motion.div className={`${ring} border-grape/50`} style={{ transformStyle: "preserve-3d" }} animate={{ rotateX: 70, rotateY: 60, rotateZ: -360 }} transition={{ rotateZ: { duration: 5, repeat: Infinity, ease: "linear" } }}>
          <span className="absolute -bottom-1.5 left-1/2 h-2.5 w-2.5 -translate-x-1/2 rounded-full bg-grape-soft shadow-glow" />
        </motion.div>
        <motion.div className={`${ring} border-emerald/40`} style={{ transformStyle: "preserve-3d" }} animate={{ rotateY: 75, rotateZ: 360 }} transition={{ rotateZ: { duration: 6, repeat: Infinity, ease: "linear" } }} />

        {/* pulsing core */}
        <motion.div
          className="absolute left-1/2 top-1/2 grid h-16 w-16 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-gradient-to-br from-gold to-grape shadow-glow"
          animate={{ scale: [1, 1.12, 1] }} transition={{ duration: 1.8, repeat: Infinity }}
        >
          <Sparkles className="h-7 w-7 text-bg" />
        </motion.div>
        <motion.div
          className="absolute left-1/2 top-1/2 h-24 w-24 -translate-x-1/2 -translate-y-1/2 rounded-full bg-gold/25 blur-2xl"
          animate={{ scale: [1, 1.4, 1], opacity: [0.4, 0.8, 0.4] }} transition={{ duration: 2, repeat: Infinity }}
        />
      </div>
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
