// Feature: Layout — animated ambient background (theme-aware) so pages aren't blank.
import { motion } from "framer-motion";

export function Background() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      {/* subtle grid */}
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "linear-gradient(rgb(var(--accent)) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--accent)) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
        }}
      />
      {/* drifting accent orbs */}
      <motion.div
        className="absolute -left-40 -top-32 h-[28rem] w-[28rem] rounded-full bg-gold/10 blur-3xl"
        animate={{ x: [0, 60, 0], y: [0, 40, 0] }}
        transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute -right-40 top-1/4 h-[26rem] w-[26rem] rounded-full bg-grape/10 blur-3xl"
        animate={{ x: [0, -50, 0], y: [0, 60, 0] }}
        transition={{ duration: 26, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-[-10rem] left-1/3 h-[24rem] w-[24rem] rounded-full bg-emerald/8 blur-3xl"
        animate={{ x: [0, 40, 0], y: [0, -40, 0] }}
        transition={{ duration: 30, repeat: Infinity, ease: "easeInOut" }}
      />
      {/* soft top glow */}
      <div className="absolute inset-x-0 top-0 h-64 bg-gradient-to-b from-gold/[0.05] to-transparent" />
    </div>
  );
}
