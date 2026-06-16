// Feature: Auth — full-screen sign-out animation
import { motion, AnimatePresence } from "framer-motion";
import { LogOut } from "lucide-react";
import { useAuthStore } from "@/stores/auth";

export function LogoutOverlay() {
  const loggingOut = useAuthStore((s) => s.loggingOut);
  return (
    <AnimatePresence>
      {loggingOut && (
        <motion.div
          className="fixed inset-0 z-[100] grid place-items-center bg-page/90 backdrop-blur-md"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="flex flex-col items-center gap-4"
            initial={{ scale: 0.85, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 1.1, opacity: 0 }}
            transition={{ type: "spring", stiffness: 220, damping: 20 }}
          >
            <motion.div
              className="grid h-20 w-20 place-items-center rounded-3xl bg-gradient-to-br from-gold to-grape shadow-glow"
              animate={{ rotate: [0, -8, 0], scale: [1, 1.05, 1] }}
              transition={{ duration: 1.1, repeat: Infinity }}
            >
              <LogOut className="h-9 w-9 text-bg" />
            </motion.div>
            <div className="text-center">
              <div className="text-lg font-700 text-ink">Signing you out…</div>
              <div className="text-sm text-ink-faint">See you soon.</div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
