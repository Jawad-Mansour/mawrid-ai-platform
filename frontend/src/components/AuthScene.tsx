// Feature: Auth — theme-aware 3D ambient scene (no images).
// Layer:   Component
// Purpose: A premium living backdrop for login/signup — a global import/supply network
//          (tilted orbital rings + travelling shipment nodes) feeding an AI core that tilts
//          in 3D toward the cursor, a parallax starfield, drifting glass "package" cubes,
//          and a soft light sweep. Mouse-parallax across depth layers; everything colours off
//          rgb(var(--accent)); respects prefers-reduced-motion.
import { useEffect, useMemo } from "react";
import { motion, useMotionValue, useSpring, useTransform, useReducedMotion } from "framer-motion";

const A = (a: number) => `rgb(var(--accent) / ${a})`; // accent at alpha — follows the active theme

/** A real CSS 3D cube (six translucent faces) — a stylised inventory package. */
function Cube({ size, dur, className, style }: { size: number; dur: number; className?: string; style?: React.CSSProperties }) {
  const h = size / 2;
  const faces = [
    `rotateY(0deg) translateZ(${h}px)`, `rotateY(90deg) translateZ(${h}px)`, `rotateY(180deg) translateZ(${h}px)`,
    `rotateY(-90deg) translateZ(${h}px)`, `rotateX(90deg) translateZ(${h}px)`, `rotateX(-90deg) translateZ(${h}px)`,
  ];
  return (
    <motion.div className={className} style={{ width: size, height: size, transformStyle: "preserve-3d", ...style }}
      animate={{ rotateX: [0, 360], rotateY: [360, 0] }} transition={{ duration: dur, repeat: Infinity, ease: "linear" }}>
      {faces.map((t, i) => (
        <div key={i} className="absolute inset-0 rounded-[10px] border"
          style={{ transform: t, borderColor: A(0.45), background: A(0.05), boxShadow: `inset 0 0 28px ${A(0.22)}`, backdropFilter: "blur(1px)" }} />
      ))}
    </motion.div>
  );
}

/** A tilted orbital ring carrying a glowing node — a global trade route around the AI core. */
function Orbit({ size, dur, tilt, reverse, dash }: { size: number; dur: number; tilt: number; reverse?: boolean; dash?: boolean }) {
  return (
    <div className="absolute left-1/2 top-1/2" style={{ transform: `translate(-50%,-50%) rotateX(72deg) rotateZ(${tilt}deg)`, transformStyle: "preserve-3d" }}>
      <motion.div className="relative rounded-full"
        style={{ width: size, height: size, border: `1px ${dash ? "dashed" : "solid"} ${A(0.18)}`, boxShadow: `0 0 40px ${A(0.08)}` }}
        animate={{ rotateZ: reverse ? [360, 0] : [0, 360] }} transition={{ duration: dur, repeat: Infinity, ease: "linear" }}>
        <div className="absolute h-2.5 w-2.5 rounded-full" style={{ top: -5, left: "50%", marginLeft: -5, background: A(0.95), boxShadow: `0 0 14px ${A(0.9)}` }} />
      </motion.div>
    </div>
  );
}

export function AuthScene() {
  const reduce = useReducedMotion();
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const sx = useSpring(mx, { stiffness: 60, damping: 18 });
  const sy = useSpring(my, { stiffness: 60, damping: 18 });

  useEffect(() => {
    if (reduce) return;
    const onMove = (e: PointerEvent) => { mx.set(e.clientX / window.innerWidth - 0.5); my.set(e.clientY / window.innerHeight - 0.5); };
    window.addEventListener("pointermove", onMove);
    return () => window.removeEventListener("pointermove", onMove);
  }, [reduce, mx, my]);

  // depth layers — parallax amount grows with "closeness"
  const farX = useTransform(sx, (v) => v * -14); const farY = useTransform(sy, (v) => v * -14);
  const midX = useTransform(sx, (v) => v * -30); const midY = useTransform(sy, (v) => v * -30);
  const nearX = useTransform(sx, (v) => v * -52); const nearY = useTransform(sy, (v) => v * -52);
  const coreRX = useTransform(sy, (v) => v * 18); const coreRY = useTransform(sx, (v) => v * -18);

  const stars = useMemo(() => Array.from({ length: 44 }, (_, i) => ({
    id: i, left: Math.random() * 100, top: Math.random() * 100,
    size: Math.random() * 1.6 + 0.6, delay: Math.random() * 4, dur: 2.5 + Math.random() * 3,
  })), []);

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      {/* soft accent aura (far layer) */}
      <motion.div className="absolute inset-0" style={{ x: farX, y: farY }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1.4 }}>
        <div className="absolute -left-40 top-0 h-96 w-96 rounded-full blur-3xl animate-float" style={{ background: A(0.12) }} />
        <div className="absolute -right-32 bottom-0 h-96 w-96 rounded-full blur-3xl animate-float" style={{ background: A(0.1), animationDelay: "2.5s" }} />
        <motion.div className="absolute left-1/2 top-1/2 h-72 w-72 -translate-x-1/2 -translate-y-1/2 rounded-full blur-3xl" style={{ background: A(0.16) }}
          animate={{ scale: [1, 1.18, 1], opacity: [0.6, 0.95, 0.6] }} transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }} />
      </motion.div>

      {/* parallax starfield */}
      <motion.div className="absolute inset-0 hidden md:block" style={{ x: farX, y: farY }}>
        {stars.map((s) => (
          <motion.span key={s.id} className="absolute rounded-full"
            style={{ left: `${s.left}%`, top: `${s.top}%`, width: s.size, height: s.size, background: A(0.85) }}
            animate={reduce ? {} : { opacity: [0.12, 0.7, 0.12], scale: [1, 1.5, 1] }}
            transition={{ duration: s.dur, repeat: Infinity, delay: s.delay, ease: "easeInOut" }} />
        ))}
      </motion.div>

      {/* soft light sweep */}
      {!reduce && (
        <motion.div className="absolute -inset-y-16 left-0 w-1/3 -skew-x-12"
          style={{ background: `linear-gradient(90deg, transparent, ${A(0.07)}, transparent)` }}
          animate={{ x: ["-50%", "380%"] }} transition={{ duration: 9, repeat: Infinity, ease: "easeInOut", repeatDelay: 2.5 }} />
      )}

      {/* the orbital network (mid layer) with a 3D-tilting core */}
      <motion.div className="absolute left-1/2 top-1/2 hidden h-0 w-0 md:block" style={{ x: midX, y: midY, perspective: 1100 }}
        initial={{ opacity: 0, scale: 0.85 }} animate={{ opacity: 0.9, scale: 1 }} transition={{ duration: 1.6, ease: "easeOut" }}>
        <Orbit size={520} dur={26} tilt={0} />
        <Orbit size={680} dur={40} tilt={32} reverse dash />
        <Orbit size={860} dur={60} tilt={-22} />
        <motion.div className="absolute left-1/2 top-1/2 h-24 w-24 -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{ rotateX: coreRX, rotateY: coreRY, transformStyle: "preserve-3d", background: `radial-gradient(circle at 38% 32%, rgb(255 255 255 / 0.7), ${A(0.7)} 45%, ${A(0)} 72%)` }}
          animate={{ scale: [1, 1.12, 1], opacity: [0.7, 1, 0.7] }} transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }} />
      </motion.div>

      {/* tumbling glass package cubes (near layer) */}
      <motion.div className="absolute inset-0 hidden lg:block" style={{ x: nearX, y: nearY }}>
        <Cube size={88} dur={30} className="absolute left-[8%] top-[20%]" style={{ opacity: 0.55 }} />
        <Cube size={56} dur={22} className="absolute left-[16%] bottom-[16%]" style={{ opacity: 0.4 }} />
        <Cube size={72} dur={26} className="absolute right-[10%] top-[24%]" style={{ opacity: 0.5 }} />
        <Cube size={48} dur={18} className="absolute right-[18%] bottom-[20%]" style={{ opacity: 0.35 }} />
      </motion.div>
    </div>
  );
}
