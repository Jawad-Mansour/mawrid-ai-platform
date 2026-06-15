// Feature: Dashboard — supplier locations globe (pure SVG, orthographic-ish)
import { useMemo } from "react";

interface Loc {
  name: string;
  lat: number;
  lng: number;
  weight?: number; // 0..1 → dot size/intensity
}

const SUPPLIERS: Loc[] = [
  { name: "Shenzhen", lat: 22.5, lng: 114.0, weight: 1 },
  { name: "Istanbul", lat: 41.0, lng: 28.9, weight: 0.8 },
  { name: "Milan", lat: 45.4, lng: 9.2, weight: 0.6 },
  { name: "Guangzhou", lat: 23.1, lng: 113.3, weight: 0.9 },
  { name: "Frankfurt", lat: 50.1, lng: 8.7, weight: 0.5 },
  { name: "Beirut", lat: 33.9, lng: 35.5, weight: 0.7 },
  { name: "Dubai", lat: 25.2, lng: 55.3, weight: 0.6 },
  { name: "Seoul", lat: 37.5, lng: 127.0, weight: 0.5 },
];

const R = 150;
const CX = 170;
const CY = 170;
// rotate the globe so MENA/Asia faces us
const ROT = -60;

function project(lat: number, lng: number) {
  const lambda = ((lng + ROT) * Math.PI) / 180;
  const phi = (lat * Math.PI) / 180;
  const x = Math.cos(phi) * Math.sin(lambda);
  const y = Math.sin(phi);
  const z = Math.cos(phi) * Math.cos(lambda);
  return { x: CX + x * R, y: CY - y * R, visible: z > 0 };
}

export function SupplierGlobe() {
  const dots = useMemo(
    () => SUPPLIERS.map((s) => ({ ...s, ...project(s.lat, s.lng) })),
    [],
  );
  const meridians = useMemo(() => [-60, -30, 0, 30, 60], []);
  const parallels = useMemo(() => [-60, -30, 0, 30, 60], []);

  return (
    <div className="relative flex items-center justify-center">
      <svg viewBox="0 0 340 340" className="h-[300px] w-[300px] animate-float">
        <defs>
          <radialGradient id="globe" cx="38%" cy="32%" r="75%">
            <stop offset="0%" stopColor="#1c2530" />
            <stop offset="70%" stopColor="#121821" />
            <stop offset="100%" stopColor="#0c1016" />
          </radialGradient>
          <radialGradient id="halo" cx="50%" cy="50%" r="50%">
            <stop offset="60%" stopColor="rgba(212,163,115,0)" />
            <stop offset="100%" stopColor="rgba(212,163,115,0.18)" />
          </radialGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="2.4" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        <circle cx={CX} cy={CY} r={R + 14} fill="url(#halo)" />
        <circle cx={CX} cy={CY} r={R} fill="url(#globe)" stroke="rgba(212,163,115,0.22)" strokeWidth="1" />

        {/* parallels */}
        {parallels.map((lat) => {
          const ry = Math.cos((lat * Math.PI) / 180) * R;
          const cy = CY - Math.sin((lat * Math.PI) / 180) * R;
          return (
            <ellipse key={`p${lat}`} cx={CX} cy={cy} rx={R} ry={ry * 0.28}
              fill="none" stroke="rgba(157,78,221,0.10)" strokeWidth="0.8" />
          );
        })}
        {/* meridians */}
        {meridians.map((lng) => {
          const rx = Math.abs(Math.sin(((lng + ROT) * Math.PI) / 180)) * R;
          return (
            <ellipse key={`m${lng}`} cx={CX} cy={CY} rx={rx || 0.5} ry={R}
              fill="none" stroke="rgba(212,163,115,0.09)" strokeWidth="0.8" />
          );
        })}

        {/* supplier dots */}
        {dots.filter((d) => d.visible).map((d) => (
          <g key={d.name}>
            <circle cx={d.x} cy={d.y} r={3 + (d.weight ?? 0.5) * 3} fill="#D4A373"
              filter="url(#glow)" className="animate-pulseDot" />
            <circle cx={d.x} cy={d.y} r={1.6} fill="#E5C39E" />
          </g>
        ))}
      </svg>

      <div className="pointer-events-none absolute bottom-1 left-1/2 -translate-x-1/2 text-center">
        <div className="metric-num text-2xl">{SUPPLIERS.length}</div>
        <div className="text-[11px] uppercase tracking-widest text-ink-faint">active sources</div>
      </div>
    </div>
  );
}
