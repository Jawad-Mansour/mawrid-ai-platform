// Feature: Onboarding — operational mode chooser (flowing animated cards)
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Building2, Store, Boxes, ArrowRight, Clock } from "lucide-react";

const MODES = [
  {
    key: "hybrid",
    title: "Hybrid",
    tag: "Available now",
    available: true,
    icon: Building2,
    desc: "Import from suppliers AND run a retail storefront. Full platform: catalog, procurement, dunning, AI, storefront.",
    accent: "from-gold to-grape",
  },
  {
    key: "wholesale_only",
    title: "Wholesale Only",
    tag: "Coming soon",
    available: false,
    icon: Boxes,
    desc: "Pure importer selling to other businesses. Payables, receivables & disputes — no consumer storefront.",
    accent: "from-emerald to-emerald-soft",
  },
  {
    key: "retail_only",
    title: "Retail Only",
    tag: "Coming soon",
    available: false,
    icon: Store,
    desc: "Buy from local importers, sell retail. Storefront-first with B2C collections.",
    accent: "from-grape to-grape-soft",
  },
];

export function ChooseMode() {
  const navigate = useNavigate();
  return (
    <div className="relative min-h-screen overflow-hidden bg-radial-fade px-6 py-16">
      {/* drifting background cards */}
      <div className="pointer-events-none absolute inset-0 opacity-30">
        {[...Array(6)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute h-40 w-64 rounded-2xl border border-line bg-bg-card"
            initial={{ x: -300, y: 80 + i * 120, rotate: -8 }}
            animate={{ x: 1600, rotate: 8 }}
            transition={{ duration: 26 + i * 5, repeat: Infinity, ease: "linear", delay: i * 3 }}
          />
        ))}
      </div>

      <div className="relative mx-auto max-w-5xl">
        <div className="mb-12 text-center">
          <div className="mx-auto mb-5 grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-gold to-grape shadow-glow">
            <span className="text-2xl font-800 text-bg">M</span>
          </div>
          <h1 className="text-4xl font-800 tracking-tight text-ink">Welcome to Mawrid</h1>
          <p className="mt-3 text-ink-soft">Choose how your business operates. You can change modules later.</p>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          {MODES.map((m, i) => (
            <motion.button
              key={m.key}
              initial={{ opacity: 0, y: 28 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.12, type: "spring", stiffness: 90 }}
              whileHover={m.available ? { y: -8, scale: 1.02 } : {}}
              disabled={!m.available}
              onClick={() => m.available && navigate(`/signup?mode=${m.key}`)}
              className={`card group relative overflow-hidden p-6 text-left ${
                m.available ? "cursor-pointer hover:shadow-glow" : "cursor-not-allowed opacity-70"
              }`}
            >
              <div className={`mb-5 grid h-12 w-12 place-items-center rounded-xl bg-gradient-to-br ${m.accent}`}>
                <m.icon className="h-6 w-6 text-bg" />
              </div>
              <div className="mb-2 flex items-center gap-2">
                <h3 className="text-xl font-700 text-ink">{m.title}</h3>
                <span
                  className={`chip ${
                    m.available
                      ? "border-emerald/40 bg-emerald/15 text-emerald-soft"
                      : "border-gold/30 bg-gold/10 text-gold-soft"
                  }`}
                >
                  {!m.available && <Clock className="h-3 w-3" />} {m.tag}
                </span>
              </div>
              <p className="text-sm leading-relaxed text-ink-soft">{m.desc}</p>
              {m.available && (
                <div className="mt-5 flex items-center gap-1.5 text-sm font-600 text-gold-soft">
                  Get started <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                </div>
              )}
            </motion.button>
          ))}
        </div>

        <p className="mt-10 text-center text-sm text-ink-soft">
          Already have an account?{" "}
          <a href="/login" className="font-600 text-gold-soft hover:underline">Sign in</a>
        </p>
      </div>
    </div>
  );
}
