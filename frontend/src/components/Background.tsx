// Feature: Layout — animated ambient background (theme-aware): drifting color orbs,
//          floating geometric shapes and a faint grid, so pages are never blank.
import { motion } from "framer-motion";

const ORBS = [
  { cls: "bg-gold/12", size: "30rem", pos: "-left-44 -top-36", dur: 22, path: { x: [0, 70, 0], y: [0, 40, 0] } },
  { cls: "bg-grape/12", size: "28rem", pos: "-right-44 top-1/4", dur: 26, path: { x: [0, -60, 0], y: [0, 70, 0] } },
  { cls: "bg-emerald/10", size: "26rem", pos: "bottom-[-12rem] left-1/3", dur: 30, path: { x: [0, 50, 0], y: [0, -50, 0] } },
  { cls: "bg-gold/10", size: "22rem", pos: "right-1/4 bottom-[-8rem]", dur: 34, path: { x: [0, -40, 0], y: [0, -30, 0] } },
];

const SHAPES = [
  { cls: "left-[12%] top-[18%] h-24 w-24 rounded-3xl border-2 border-gold/20", rotate: 360, dur: 40 },
  { cls: "right-[14%] top-[30%] h-16 w-16 rotate-45 border-2 border-grape/25", rotate: 405, dur: 32 },
  { cls: "left-[20%] bottom-[16%] h-20 w-20 rounded-full border-2 border-emerald/20", rotate: -360, dur: 46 },
  { cls: "right-[22%] bottom-[22%] h-12 w-12 rounded-xl border-2 border-gold/20", rotate: 360, dur: 28 },
];

export function Background() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      {/* faint grid */}
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "linear-gradient(rgb(var(--accent)) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--accent)) 1px, transparent 1px)",
          backgroundSize: "46px 46px",
        }}
      />
      {/* drifting color orbs */}
      {ORBS.map((o, i) => (
        <motion.div
          key={i}
          className={`absolute ${o.pos} ${o.cls} rounded-full blur-3xl`}
          style={{ width: o.size, height: o.size }}
          animate={o.path}
          transition={{ duration: o.dur, repeat: Infinity, ease: "easeInOut" }}
        />
      ))}
      {/* floating outline shapes */}
      {SHAPES.map((s, i) => (
        <motion.div
          key={i}
          className={`absolute ${s.cls}`}
          animate={{ rotate: s.rotate, y: [0, -14, 0] }}
          transition={{ rotate: { duration: s.dur, repeat: Infinity, ease: "linear" }, y: { duration: s.dur / 3, repeat: Infinity, ease: "easeInOut" } }}
        />
      ))}
      {/* soft top + bottom glows for depth */}
      <div className="absolute inset-x-0 top-0 h-64 bg-gradient-to-b from-gold/[0.06] to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-64 bg-gradient-to-t from-grape/[0.05] to-transparent" />
    </div>
  );
}
