// Feature: Layout — slim header with an elegant Mawrid slogan (no search/bell here).
import { motion } from "framer-motion";

export function Topbar() {
  return (
    <header className="glass sticky top-0 z-20 flex items-center justify-center rounded-none border-x-0 border-t-0 px-6 py-3.5">
      <motion.div
        className="flex items-center gap-3 text-center"
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <span className="font-mono text-xl text-gold-soft">مَورِد</span>
        <span className="h-4 w-px bg-line" />
        <span className="bg-gradient-to-r from-gold-soft via-ink to-grape-soft bg-clip-text font-serif text-sm italic tracking-wide text-transparent sm:text-base">
          where supply meets intelligence
        </span>
      </motion.div>
    </header>
  );
}
