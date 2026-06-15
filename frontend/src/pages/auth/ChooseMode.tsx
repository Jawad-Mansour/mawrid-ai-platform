// Feature: Onboarding — role carousel (one card in focus, neighbors faded)
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Building2, Store, Boxes, ShoppingBag, ArrowRight, Clock,
  ChevronLeft, ChevronRight, type LucideIcon,
} from "lucide-react";

interface Role {
  key: string;
  title: string;
  tag: string;
  available: boolean;
  icon: LucideIcon;
  desc: string;
  bullets: string[];
  accent: string;
  to?: string;
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

export function ChooseMode() {
  const navigate = useNavigate();
  const [active, setActive] = useState(0);
  const go = (dir: number) => setActive((a) => (a + dir + ROLES.length) % ROLES.length);

  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden bg-radial-fade px-6 py-12">
      {/* drifting ambient orbs */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-32 top-10 h-72 w-72 rounded-full bg-grape/10 blur-3xl animate-float" />
        <div className="absolute -right-24 bottom-0 h-80 w-80 rounded-full bg-gold/10 blur-3xl animate-float" style={{ animationDelay: "2s" }} />
      </div>

      <div className="relative w-full max-w-5xl">
        <div className="mb-10 text-center">
          <div className="mx-auto mb-5 grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-gold to-grape shadow-glow">
            <span className="text-2xl font-800 text-bg">M</span>
          </div>
          <h1 className="text-4xl font-800 tracking-tight text-ink">Who are you?</h1>
          <p className="mt-3 text-ink-soft">Pick a role to get started. Use the arrows to explore.</p>
        </div>

        {/* carousel */}
        <div className="relative h-[460px]">
          {ROLES.map((r, i) => {
            const offset = i - active;
            const abs = Math.abs(offset);
            const visible = abs <= 1;
            return (
              <motion.div
                key={r.key}
                className="absolute left-1/2 top-1/2"
                animate={{
                  x: `calc(-50% + ${offset * 300}px)`,
                  y: "-50%",
                  scale: offset === 0 ? 1 : 0.82,
                  opacity: visible ? (offset === 0 ? 1 : 0.32) : 0,
                  zIndex: 10 - abs,
                }}
                transition={{ type: "spring", stiffness: 120, damping: 20 }}
                style={{ pointerEvents: offset === 0 ? "auto" : "none" }}
              >
                <div
                  className={`card relative flex h-[440px] w-[360px] flex-col overflow-hidden p-7 ${
                    offset === 0 ? "shadow-glow ring-1 ring-gold/30" : ""
                  }`}
                >
                  {offset === 0 && (
                    <div className="pointer-events-none absolute -inset-px rounded-2xl bg-gradient-to-br from-gold/10 via-transparent to-grape/10" />
                  )}
                  <div className={`mb-5 grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br ${r.accent}`}>
                    <r.icon className="h-7 w-7 text-bg" />
                  </div>
                  <div className="mb-2 flex items-center gap-2">
                    <h3 className="text-2xl font-800 text-ink">{r.title}</h3>
                  </div>
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
                </div>
              </motion.div>
            );
          })}

          {/* arrows */}
          <button onClick={() => go(-1)} className="absolute left-0 top-1/2 z-20 grid h-12 w-12 -translate-y-1/2 place-items-center rounded-full glass hover:bg-white/[0.08]">
            <ChevronLeft className="h-5 w-5 text-ink" />
          </button>
          <button onClick={() => go(1)} className="absolute right-0 top-1/2 z-20 grid h-12 w-12 -translate-y-1/2 place-items-center rounded-full glass hover:bg-white/[0.08]">
            <ChevronRight className="h-5 w-5 text-ink" />
          </button>
        </div>

        {/* dots */}
        <div className="mt-2 flex justify-center gap-2">
          {ROLES.map((_, i) => (
            <button key={i} onClick={() => setActive(i)}
              className={`h-2 rounded-full transition-all ${i === active ? "w-7 bg-gold" : "w-2 bg-white/20 hover:bg-white/40"}`} />
          ))}
        </div>

        <p className="mt-8 text-center text-sm text-ink-soft">
          Already have an account? <a href="/login" className="font-600 text-gold-soft hover:underline">Sign in</a>
        </p>
      </div>
    </div>
  );
}
