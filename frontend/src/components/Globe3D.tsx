// Feature: Dashboard — true 3D globe (cobe / WebGL) with real supplier locations
import { useEffect, useRef, useState } from "react";
import createGlobe from "cobe";

export interface GlobeMarker {
  name: string;
  location: [number, number]; // [lat, lng]
  size?: number;
}

export const SUPPLIER_MARKERS: GlobeMarker[] = [
  { name: "Shenzhen", location: [22.54, 114.06], size: 0.09 },
  { name: "Guangzhou", location: [23.13, 113.26], size: 0.08 },
  { name: "Istanbul", location: [41.01, 28.98], size: 0.07 },
  { name: "Milan", location: [45.46, 9.19], size: 0.05 },
  { name: "Frankfurt", location: [50.11, 8.68], size: 0.05 },
  { name: "Beirut", location: [33.89, 35.5], size: 0.07 },
  { name: "Dubai", location: [25.2, 55.27], size: 0.06 },
  { name: "Seoul", location: [37.57, 126.98], size: 0.05 },
];

function cssRgb(varName: string, fallback: [number, number, number]): [number, number, number] {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
  const parts = raw.split(/[\s,]+/).map(Number).filter((n) => !Number.isNaN(n));
  if (parts.length === 3) return [parts[0] / 255, parts[1] / 255, parts[2] / 255];
  return fallback;
}

export function Globe3D({
  markers = SUPPLIER_MARKERS,
  themeKey = "gold",
}: {
  markers?: GlobeMarker[];
  themeKey?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState(300);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setSize(Math.round(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!canvasRef.current || size === 0) return;
    let phi = 4.2; // start rotated so MENA/Asia faces the viewer
    const accent = cssRgb("--accent-rgb", [0.83, 0.64, 0.45]);
    const base = cssRgb("--globe-base-rgb", [0.18, 0.21, 0.27]);
    const glow = cssRgb("--globe-glow-rgb", [0.13, 0.15, 0.2]);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const globe = createGlobe(canvasRef.current, {
      devicePixelRatio: dpr,
      width: size * dpr,
      height: size * dpr,
      phi: 0,
      theta: 0.28,
      dark: 1,
      diffuse: 1.2,
      mapSamples: 18000,
      mapBrightness: 6,
      baseColor: base,
      markerColor: accent,
      glowColor: glow,
      markers: markers.map((m) => ({ location: m.location, size: m.size ?? 0.06 })),
      onRender: (state) => {
        state.phi = phi;
        phi += 0.0035;
        state.width = size * dpr;
        state.height = size * dpr;
      },
    });
    return () => globe.destroy();
  }, [size, markers, themeKey]);

  return (
    <div ref={wrapRef} className="relative mx-auto aspect-square w-full max-w-[340px]">
      <canvas
        ref={canvasRef}
        style={{ width: size, height: size }}
        className="h-full w-full [contain:layout_paint_size]"
      />
    </div>
  );
}
