// Feature: Onboarding — role carousel (one card in focus, neighbors receding in 3D).
//          Keyboard arrows, drag/swipe with velocity snapping, and a smooth spring.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence, useMotionValue, type PanInfo } from "framer-motion";
import {
  Building2, Store, Boxes, ShoppingBag, ArrowRight, Clock,
  ChevronLeft, ChevronRight, type LucideIcon,
} from "lucide-react";

interface Role {
  key: string; title: string; tag: string; available: boolean; icon: LucideIcon;
  desc: string; bullets: string[]; accent: string; to?: string;
}

const ROLES: Role[] = [
  {
    key: "hybrid", title: "Business Owner", tag: "Available now", available: true,
    icon: Building2, accent: "from-gold to-grape", to: "/signup?mode=hybrid",
    desc: "Import from suppliers and run a retail storefront — the full Mawrid platform.",
    bullets: ["AI catalog enrichment", "Procurement + HITL approvals", "Dunning engine + storefront", "Supplier intelligence"],
  },
  {
    key: "wholesale_only", title: "Wholesale Importer", tag: "Coming soon", available: false,
    icon: Boxes, accent: "from-emerald to-emerald-soft",
    desc: "Sell only to other businesses — payables, receivables and disputes, no consumer store.",
    bullets: ["B2B payables & receivables", "Supplier disputes", "Wholesale client tracking", "No storefront"],
  },
  {
    key: "retail_only", title: "Retail Store", tag: "Coming soon", available: false,
    icon: Store, accent: "from-grape to-grape-soft",
    desc: "Buy from local importers and sell retail — storefront-first with B2C collections.",
    bullets: ["Storefront-first", "B2C collections", "Auto-publish stock", "Local supplier tracking"],
  },
  {
    key: "customer", title: "Shopper", tag: "Coming soon", available: false,
    icon: ShoppingBag, accent: "from-grape-soft to-gold",
    desc: "Browse every published store, ask the AI assistant, and check out — no account needed.",
    bullets: ["Browse all stores", "AI product chat", "Cart & checkout", "Invoice by email"],
  },
];

const SPRING = { type: "spring" as const, stiffness: 130, damping: 20, mass: 0.8 };
const GAP = 300;

export function ChooseMode() {
  const navigate = useNavigate();
  const [active, setActive] = useState(0);
  const drag = useMotionValue(0);
  const go = (dir: number) => setActive((a) => Math.min(ROLES.length - 1, Math.max(0, a + dir)));

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowLeft") go(-1);
      else if (e.key === "ArrowRight") go(1);
      else if (e.key === "Enter") {
        const r = ROLES[active];
        if (r.available && r.to) navigate(r.to);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, navigate]);

  function onDragEnd(_: unknown, info: PanInfo) {
    const power = info.offset.x + info.velocity.x * 0.18; // swipe momentum
    if (power < -GAP / 3) go(1);
    else if (power > GAP / 3) go(-1);
    drag.set(0);
  }

  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden bg-radial-fade px-6 py-12">
      <motion.div className="pointer-events-none absolute inset-0" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1 }}>
        <div className="absolute -left-32 top-10 h-72 w-72 rounded-full bg-grape/10 blur-3xl animate-float" />
        <div className="absolute -right-24 bottom-0 h-80 w-80 rounded-full bg-gold/10 blur-3xl animate-float" style={{ animationDelay: "2s" }} />
      </motion.div>

      <div className="relative w-full max-w-5xl">
        <motion.div className="mb-10 text-center" initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }} transition={SPRING}>
          <motion.div
            className="mx-auto mb-5 grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-gold to-grape shadow-glow"
            initial={{ scale: 0, rotate: -120 }} animate={{ scale: 1, rotate: 0 }} transition={{ ...SPRING, delay: 0.1 }}
          >
            <span className="text-2xl font-800 text-bg">M</span>
          </motion.div>
          <h1 className="text-4xl font-800 tracking-tight text-ink">Who are you?</h1>
          <p className="mt-3 text-ink-soft">Drag, swipe, or use ← → to explore. Press Enter to choose.</p>
        </motion.div>

        {/* carousel — a single draggable layer; cards transform off the shared offset */}
        <div className="relative h-[480px]" style={{ perspective: 1400 }}>
          <motion.div
            className="absolute inset-0"
            style={{ x: drag }}
            drag="x"
            dragElastic={0.12}
            dragConstraints={{ left: 0, right: 0 }}
            onDragEnd={onDragEnd}
          >
            {ROLES.map((r, i) => {
              const offset = i - active;
              const abs = Math.abs(offset);
              const visible = abs <= 2;
              return (
                <motion.div
                  key={r.key}
                  className="absolute left-1/2 top-1/2"
                  initial={false}
                  animate={{
                    x: `calc(-50% + ${offset * GAP}px)`,
                    y: "-50%",
                    scale: offset === 0 ? 1 : abs === 1 ? 0.82 : 0.7,
                    rotateY: offset * -22,
                    z: offset === 0 ? 0 : -abs * 120,
                    opacity: visible ? (offset === 0 ? 1 : abs === 1 ? 0.42 : 0.12) : 0,
                    filter: offset === 0 ? "blur(0px)" : `blur(${abs * 2}px)`,
                  }}
                  transition={SPRING}
                  style={{ zIndex: 10 - abs, transformStyle: "preserve-3d", pointerEvents: offset === 0 ? "auto" : "none" }}
                >
                  <motion.div
                    whileHover={offset === 0 ? { y: -6 } : undefined}
                    transition={{ type: "spring", stiffness: 300, damping: 22 }}
                    className={`card relative flex h-[452px] w-[360px] cursor-grab flex-col overflow-hidden p-7 active:cursor-grabbing ${
                      offset === 0 ? "shadow-glow ring-1 ring-gold/40" : ""
                    }`}
                    onClick={() => offset !== 0 && setActive(i)}
                  >
                    {offset === 0 && (
                      <>
                        <motion.div
                          className="pointer-events-none absolute -inset-px rounded-2xl bg-gradient-to-br from-gold/15 via-transparent to-grape/15"
                          animate={{ opacity: [0.5, 0.9, 0.5] }}
                          transition={{ duration: 3.5, repeat: Infinity }}
                        />
                        <div className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-gold/20 blur-3xl" />
                      </>
                    )}
                    <div className={`mb-5 grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br ${r.accent} shadow-glow`}>
                      <r.icon className="h-7 w-7 text-bg" />
                    </div>
                    <h3 className="mb-2 text-2xl font-800 text-ink">{r.title}</h3>
                    <span className={`chip w-fit ${r.available ? "border-emerald/40 bg-emerald/15 text-emerald-soft" : "border-gold/30 bg-gold/10 text-gold-soft"}`}>
                      {!r.available && <Clock className="h-3 w-3" />} {r.tag}
                    </span>
                    <p className="mt-4 text-sm leading-relaxed text-ink-soft">{r.desc}</p>
                    <ul className="mt-4 space-y-2">
                      {r.bullets.map((b) => (
                        <li key={b} className="flex items-center gap-2 text-sm text-ink">
                          <span className="h-1.5 w-1.5 rounded-full bg-gold" /> {b}
                        </li>
                      ))}
                    </ul>
                    <div className="mt-auto">
                      {r.available ? (
                        <button onClick={() => navigate(r.to!)} className="btn-gold w-full">
                          Create workspace <ArrowRight className="h-4 w-4" />
                        </button>
                      ) : (
                        <button disabled className="btn-ghost w-full opacity-60">Coming soon</button>
                      )}
                    </div>
                  </motion.div>
                </motion.div>
              );
            })}
          </motion.div>

          <button onClick={() => go(-1)} disabled={active === 0}
            className="absolute left-0 top-1/2 z-20 grid h-12 w-12 -translate-y-1/2 place-items-center rounded-full glass transition-all hover:bg-white/[0.08] disabled:opacity-30">
            <ChevronLeft className="h-5 w-5 text-ink" />
          </button>
          <button onClick={() => go(1)} disabled={active === ROLES.length - 1}
            className="absolute right-0 top-1/2 z-20 grid h-12 w-12 -translate-y-1/2 place-items-center rounded-full glass transition-all hover:bg-white/[0.08] disabled:opacity-30">
            <ChevronRight className="h-5 w-5 text-ink" />
          </button>
        </div>

        <div className="mt-2 flex justify-center gap-2">
          {ROLES.map((_, i) => (
            <button key={i} onClick={() => setActive(i)}
              className={`h-2 rounded-full transition-all ${i === active ? "w-7 bg-gold" : "w-2 bg-white/20 hover:bg-white/40"}`} />
          ))}
        </div>

        <AnimatePresence mode="wait">
          <motion.p key={active} className="mt-6 text-center text-sm font-600 text-gold-soft"
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}>
            {active + 1} / {ROLES.length} · {ROLES[active].title}
          </motion.p>
        </AnimatePresence>

        <p className="mt-4 text-center text-sm text-ink-soft">
          Already have an account? <a href="/login" className="font-600 text-gold-soft hover:underline">Sign in</a>
        </p>
      </div>
    </div>
  );
}
