// Feature: Dashboard — interactive 3D globe (cobe / WebGL) with real supplier hubs.
//          Markers are projected from the spinning sphere to 2D each frame so we can
//          overlay DOM hotspots that show a supplier window on hover, and a hub rail
//          that "flies" the globe to a city on click/hover.
import { useEffect, useMemo, useRef, useState } from "react";
import createGlobe from "cobe";
import { motion, AnimatePresence } from "framer-motion";
import { MapPin, Package, Clock, ShieldCheck, Star } from "lucide-react";

export interface SupplierHub {
  name: string;
  country: string;
  flag: string;
  location: [number, number]; // [lat, lng]
  suppliers: number;
  categories: string[];
  leadDays: number;
  reliability: number; // 0–100
  size?: number;
}

export const SUPPLIER_HUBS: SupplierHub[] = [
  { name: "Shenzhen", country: "China", flag: "🇨🇳", location: [22.54, 114.06], suppliers: 18, categories: ["Electronics", "Accessories"], leadDays: 32, reliability: 88, size: 0.09 },
  { name: "Guangzhou", country: "China", flag: "🇨🇳", location: [23.13, 113.26], suppliers: 12, categories: ["Apparel", "Homeware"], leadDays: 34, reliability: 84, size: 0.07 },
  { name: "Istanbul", country: "Türkiye", flag: "🇹🇷", location: [41.01, 28.98], suppliers: 9, categories: ["Textiles", "Food"], leadDays: 12, reliability: 91, size: 0.07 },
  { name: "Milan", country: "Italy", flag: "🇮🇹", location: [45.46, 9.19], suppliers: 5, categories: ["Fashion", "Design"], leadDays: 9, reliability: 94, size: 0.05 },
  { name: "Frankfurt", country: "Germany", flag: "🇩🇪", location: [50.11, 8.68], suppliers: 6, categories: ["Industrial", "Auto"], leadDays: 8, reliability: 96, size: 0.05 },
  { name: "Beirut", country: "Lebanon", flag: "🇱🇧", location: [33.89, 35.5], suppliers: 7, categories: ["FMCG", "Local"], leadDays: 3, reliability: 90, size: 0.07 },
  { name: "Dubai", country: "UAE", flag: "🇦🇪", location: [25.2, 55.27], suppliers: 11, categories: ["Re-export", "Luxury"], leadDays: 5, reliability: 93, size: 0.06 },
  { name: "Seoul", country: "South Korea", flag: "🇰🇷", location: [37.57, 126.98], suppliers: 4, categories: ["Beauty", "Tech"], leadDays: 28, reliability: 92, size: 0.05 },
];

// Tweak if the dots sit a constant rotation off the landmass.
const MARKER_PHI_OFFSET = Math.PI;
const DEG = Math.PI / 180;
const THETA = 0.28; // must match the cobe constructor `theta`

function cssRgb(varName: string, fallback: [number, number, number]): [number, number, number] {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
  const parts = raw.split(/[\s,]+/).map(Number).filter((n) => !Number.isNaN(n));
  if (parts.length === 3) return [parts[0] / 255, parts[1] / 255, parts[2] / 255];
  return fallback;
}

interface Projected { x: number; y: number; front: boolean; scale: number }

function project(lat: number, lng: number, phi: number): Projected {
  // cobe frame: azimuth = (lng + 180) + spin; polar from north pole.
  const az = (lng + 180) * DEG + phi + MARKER_PHI_OFFSET;
  const pol = (90 - lat) * DEG;
  const x = Math.sin(pol) * Math.sin(az);
  const y = Math.cos(pol);
  const z = Math.sin(pol) * Math.cos(az);
  // camera tilt (theta) about the X axis
  const yt = y * Math.cos(THETA) - z * Math.sin(THETA);
  const zt = y * Math.sin(THETA) + z * Math.cos(THETA);
  return { x, y: yt, front: zt > 0, scale: 0.42 + 0.58 * Math.max(0, zt) };
}

export function Globe3D({ hubs = SUPPLIER_HUBS, themeKey = "gold" }: { hubs?: SupplierHub[]; themeKey?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState(320);
  const [hover, setHover] = useState<number | null>(null);
  const [pinned, setPinned] = useState<number | null>(null);
  const [pts, setPts] = useState<Projected[]>([]);

  // phi/target live in refs so hover/click can steer the spin without re-creating the globe.
  const phiRef = useRef(4.2);
  const targetRef = useRef<number | null>(null);
  const autoRef = useRef(true);

  const active = pinned ?? hover;

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setSize(Math.round(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // When a hub becomes active, fly the globe so that city faces the viewer.
  useEffect(() => {
    if (active == null) { autoRef.current = true; targetRef.current = null; return; }
    autoRef.current = false;
    const lng = hubs[active].location[1];
    // face-front when az ≈ 0 (mod 2π): phi = -((lng+180)deg + offset)
    let t = -((lng + 180) * DEG + MARKER_PHI_OFFSET);
    const cur = phiRef.current;
    t += Math.round((cur - t) / (2 * Math.PI)) * 2 * Math.PI; // nearest equivalent angle
    targetRef.current = t;
  }, [active, hubs]);

  useEffect(() => {
    if (!canvasRef.current || size === 0) return;
    const accent = cssRgb("--accent-rgb", [0.83, 0.64, 0.45]);
    const base = cssRgb("--globe-base-rgb", [0.18, 0.21, 0.27]);
    const glow = cssRgb("--globe-glow-rgb", [0.13, 0.15, 0.2]);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let frame = 0;

    const globe = createGlobe(canvasRef.current, {
      devicePixelRatio: dpr,
      width: size * dpr,
      height: size * dpr,
      phi: 0,
      theta: THETA,
      dark: 1,
      diffuse: 1.2,
      mapSamples: 18000,
      mapBrightness: 6,
      baseColor: base,
      markerColor: accent,
      glowColor: glow,
      markers: hubs.map((m) => ({ location: m.location, size: m.size ?? 0.06 })),
      onRender: (state) => {
        const target = targetRef.current;
        if (target != null) {
          phiRef.current += (target - phiRef.current) * 0.08; // ease toward city
        } else if (autoRef.current) {
          phiRef.current += 0.0035; // idle drift
        }
        state.phi = phiRef.current;
        state.width = size * dpr;
        state.height = size * dpr;

        // Project markers ~30fps for the DOM overlay (throttled to halve setState churn).
        if (frame++ % 2 === 0) {
          setPts(hubs.map((h) => project(h.location[0], h.location[1], phiRef.current)));
        }
      },
    });
    return () => globe.destroy();
  }, [size, hubs, themeKey]);

  const R = size / 2;
  const card = active != null ? hubs[active] : null;

  return (
    <div className="relative w-full">
      <div
        ref={wrapRef}
        className="relative mx-auto aspect-square w-full max-w-[360px]"
        onMouseLeave={() => setHover(null)}
      >
        <canvas ref={canvasRef} style={{ width: size, height: size }} className="h-full w-full [contain:layout_paint_size]" />

        {/* projected interactive hotspots */}
        {pts.map((p, i) => {
          if (!p.front) return null;
          const left = R + p.x * R * 0.92;
          const top = R - p.y * R * 0.92;
          const isOn = active === i;
          return (
            <button
              key={hubs[i].name}
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={{ left, top, zIndex: isOn ? 30 : 20, opacity: p.scale }}
              onMouseEnter={() => setHover(i)}
              onClick={() => setPinned((v) => (v === i ? null : i))}
            >
              <span className="relative grid place-items-center">
                <span className={`absolute rounded-full bg-gold/40 ${isOn ? "h-5 w-5 animate-ping" : "h-3.5 w-3.5 animate-pulse"}`} />
                <span className={`relative rounded-full ring-2 ring-bg ${isOn ? "h-3 w-3 bg-gold" : "h-2 w-2 bg-gold-soft"}`} style={{ transform: `scale(${0.7 + 0.5 * p.scale})` }} />
              </span>
            </button>
          );
        })}

        {/* supplier window */}
        <AnimatePresence>
          {card && (
            <motion.div
              initial={{ opacity: 0, y: 8, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.96 }}
              transition={{ type: "spring", stiffness: 320, damping: 26 }}
              className="card absolute left-1/2 top-2 z-40 w-64 -translate-x-1/2 p-4 text-left shadow-glow"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xl">{card.flag}</span>
                  <div>
                    <div className="text-sm font-700 leading-tight text-ink">{card.name}</div>
                    <div className="flex items-center gap-1 text-xs text-ink-faint"><MapPin className="h-3 w-3" /> {card.country}</div>
                  </div>
                </div>
                <span className="chip border-gold/30 bg-gold/10 text-gold-soft"><Package className="h-3 w-3" /> {card.suppliers}</span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-lg border border-line bg-white/[0.02] p-2">
                  <div className="flex items-center gap-1 text-ink-faint"><Clock className="h-3 w-3" /> Lead time</div>
                  <div className="mt-0.5 font-mono font-700 text-ink">{card.leadDays}d</div>
                </div>
                <div className="rounded-lg border border-line bg-white/[0.02] p-2">
                  <div className="flex items-center gap-1 text-ink-faint"><ShieldCheck className="h-3 w-3" /> Reliability</div>
                  <div className="mt-0.5 font-mono font-700 text-emerald-soft">{card.reliability}%</div>
                </div>
              </div>
              <div className="mt-2 flex flex-wrap gap-1">
                {card.categories.map((c) => <span key={c} className="chip border-line bg-white/[0.02] text-ink-soft">{c}</span>)}
              </div>
              {pinned === active && <div className="mt-2 flex items-center gap-1 text-[10px] text-ink-faint"><Star className="h-3 w-3 text-gold-soft" /> pinned — click the dot again to release</div>}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* reliable hub rail */}
      <div className="mt-4 flex flex-wrap justify-center gap-1.5">
        {hubs.map((h, i) => (
          <button
            key={h.name}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
            onClick={() => setPinned((v) => (v === i ? null : i))}
            className={`chip transition-all ${active === i ? "border-gold/50 bg-gold/15 text-gold-soft shadow-glow" : "border-line bg-white/[0.02] text-ink-soft hover:border-gold/30"}`}
          >
            <span>{h.flag}</span> {h.name}
          </button>
        ))}
      </div>
    </div>
  );
}
