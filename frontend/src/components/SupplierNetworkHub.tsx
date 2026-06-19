// Feature: Dashboard — Supplier Network hub. A theme-coloured 3D globe (cobe/WebGL) with
//          Lebanon as the glowing core and LIVE "flowing" connection lines out to each
//          sourcing region. Active regions glow; "coming soon" ones are dimmed + locked.
//          Arcs are re-projected every frame so they track the globe's rotation.
import { useEffect, useRef, useState } from "react";
import createGlobe from "cobe";
import { Lock } from "lucide-react";

interface Region { key: string; label: string; loc: [number, number]; active: boolean }

// Beirut is the hub (index 0); the rest are sourcing regions.
const HUB: Region = { key: "lb", label: "Lebanon", loc: [33.89, 35.5], active: true };
const REGIONS: Region[] = [
  { key: "europe", label: "Europe", loc: [48.5, 9.0], active: true },
  { key: "turkey", label: "Türkiye", loc: [39.0, 35.0], active: false },
  { key: "gulf", label: "Gulf", loc: [25.2, 55.27], active: false },
  { key: "china", label: "China", loc: [30.0, 110.0], active: false },
  { key: "usa", label: "USA", loc: [39.0, -98.0], active: false },
  { key: "australia", label: "Australia", loc: [-25.0, 133.0], active: false },
];
const ALL = [HUB, ...REGIONS];

const DEG = Math.PI / 180;
const THETA = 0.25;
const PHI_OFFSET = Math.PI;

function cssRgb(varName: string, fallback: [number, number, number]): [number, number, number] {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
  const parts = raw.split(/[\s,]+/).map(Number).filter((n) => !Number.isNaN(n));
  return parts.length === 3 ? [parts[0] / 255, parts[1] / 255, parts[2] / 255] : fallback;
}

interface P { x: number; y: number; front: boolean; scale: number }
function project(lat: number, lng: number, phi: number): P {
  const az = (lng + 180) * DEG + phi + PHI_OFFSET;
  const pol = (90 - lat) * DEG;
  const x = Math.sin(pol) * Math.sin(az);
  const y = Math.cos(pol);
  const z = Math.sin(pol) * Math.cos(az);
  const yt = y * Math.cos(THETA) - z * Math.sin(THETA);
  const zt = y * Math.sin(THETA) + z * Math.cos(THETA);
  return { x, y: yt, front: zt > 0, scale: 0.45 + 0.55 * Math.max(0, zt) };
}

export function SupplierNetworkHub({ themeKey = "gold" }: { themeKey?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState(340);
  const [pts, setPts] = useState<P[]>([]);
  const phiRef = useRef(-((HUB.loc[1] + 180) * DEG + PHI_OFFSET)); // start facing Lebanon

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setSize(Math.round(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

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
      mapSamples: 16000,
      mapBrightness: 6,
      baseColor: base,
      markerColor: accent,
      glowColor: glow,
      markers: ALL.map((r, i) => ({ location: r.loc, size: i === 0 ? 0.11 : r.active ? 0.07 : 0.05 })),
      onRender: (state) => {
        phiRef.current += 0.0026; // gentle drift
        state.phi = phiRef.current;
        state.width = size * dpr;
        state.height = size * dpr;
        if (frame++ % 2 === 0) setPts(ALL.map((r) => project(r.loc[0], r.loc[1], phiRef.current)));
      },
    });
    return () => globe.destroy();
  }, [size, themeKey]);

  const R = size / 2;
  const screen = (p: P) => ({ left: R + p.x * R * 0.92, top: R - p.y * R * 0.92 });
  const hub = pts[0];

  return (
    <div className="relative w-full">
      <div ref={wrapRef} className="relative mx-auto aspect-square w-full max-w-[360px]">
        <canvas ref={canvasRef} style={{ width: size, height: size }} className="h-full w-full [contain:layout_paint_size]" />

        {/* flowing connection arcs (Lebanon → each region), re-projected each frame */}
        <svg className="pointer-events-none absolute inset-0" width={size} height={size}>
          {hub && pts.map((p, i) => {
            if (i === 0 || !p.front || !hub.front) return null;
            const a = screen(hub); const b = screen(p);
            const mx = (a.left + b.left) / 2; const my = (a.top + b.top) / 2;
            // bow the arc outward from the globe centre for a satellite-link look
            const nx = mx - R; const ny = my - R; const nl = Math.hypot(nx, ny) || 1;
            const k = REGIONS[i - 1].active ? 26 : 16;
            const cx = mx + (nx / nl) * k; const cy = my + (ny / nl) * k;
            const d = `M ${a.left} ${a.top} Q ${cx} ${cy} ${b.left} ${b.top}`;
            const on = REGIONS[i - 1].active;
            return (
              <path key={i} d={d} fill="none"
                stroke={on ? "rgb(var(--accent))" : "rgb(var(--accent) / 0.35)"}
                strokeWidth={on ? 1.6 : 1}
                strokeDasharray={on ? "2 5" : "1 7"}
                className="flow-line" style={{ filter: on ? "drop-shadow(0 0 3px rgb(var(--accent) / 0.7))" : undefined, opacity: Math.min(p.scale, hub.scale) }}
              />
            );
          })}
        </svg>

        {/* region labels at their projected positions */}
        {pts.map((p, i) => {
          if (!p.front) return null;
          const r = ALL[i]; const s = screen(p);
          const isHub = i === 0;
          return (
            <div key={r.key} className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: s.left, top: s.top, opacity: p.scale, zIndex: isHub ? 30 : 20 }}>
              <span className="relative grid place-items-center">
                <span className={`absolute rounded-full ${isHub ? "h-5 w-5 animate-ping" : ""}`} style={{ background: isHub ? "rgb(var(--accent) / 0.4)" : undefined }} />
                <span className="relative rounded-full ring-2 ring-bg" style={{
                  width: isHub ? 11 : r.active ? 8 : 6, height: isHub ? 11 : r.active ? 8 : 6,
                  background: r.active ? "rgb(var(--accent))" : "rgb(148 163 184 / 0.8)",
                }} />
              </span>
              {(isHub || p.scale > 0.7) && (
                <span className={`mt-1 flex items-center gap-0.5 whitespace-nowrap rounded-md px-1.5 py-0.5 text-[9px] font-700 ${
                  isHub ? "bg-[rgb(var(--accent)/0.18)] text-[rgb(var(--accent-soft))]" : r.active ? "text-ink" : "text-ink-faint"}`}>
                  {!isHub && !r.active && <Lock className="h-2 w-2" />} {r.label}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* region legend */}
      <div className="mt-3 flex flex-wrap justify-center gap-1.5">
        {REGIONS.map((r) => (
          <span key={r.key} className={`chip ${r.active ? "border-[rgb(var(--accent)/0.5)] bg-[rgb(var(--accent)/0.12)] text-[rgb(var(--accent-soft))]" : "border-line bg-white/[0.02] text-ink-faint"}`}>
            {!r.active && <Lock className="h-3 w-3" />} {r.label}{!r.active && <span className="text-[9px] uppercase">soon</span>}
          </span>
        ))}
      </div>
    </div>
  );
}
