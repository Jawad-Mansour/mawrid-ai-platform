// Feature: Supplier & Factory Network — real OpenStreetMap map (Leaflet via CDN).
// Layer:   Component
// Purpose: Render colour-coded factory/supplier markers on a real OSM map. Uses the
//          global `L` loaded from the Leaflet CDN in index.html (no bundler dep).
import { useEffect, useRef } from "react";

declare global {
  interface Window { L: any }
}

export interface MapPin {
  id: string;
  name: string;
  category: string;
  latitude: number | null;
  longitude: number | null;
  city?: string | null;
  country?: string | null;
  offering?: string | null;
  website?: string | null;
  rating?: number | null;
  source: string;
}

export function LeafletMap({
  pins, center, zoom, colorFor, onSelect, onContact, selectedIds, height = 460, maxBounds, minZoom,
}: {
  pins: MapPin[];
  center: [number, number];
  zoom: number;
  colorFor: (category: string) => string;
  onSelect?: (id: string) => void;
  onContact?: (id: string) => void;
  selectedIds?: string[];
  height?: number;
  maxBounds?: [[number, number], [number, number]];
  minZoom?: number;
}) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const layerRef = useRef<any>(null);

  // init once
  useEffect(() => {
    const L = window.L;
    if (!L || !elRef.current || mapRef.current) return;
    const map = L.map(elRef.current, {
      scrollWheelZoom: true,
      attributionControl: true,
      minZoom: minZoom ?? Math.max(2, zoom - 1),
      maxBounds: maxBounds ?? undefined,
      maxBoundsViscosity: 1.0, // hard wall — can't pan out of the region
    }).setView(center, zoom);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap',
    }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    setTimeout(() => map.invalidateSize(), 200);
    return () => { map.remove(); mapRef.current = null; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // recenter + re-fence when region changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (maxBounds) map.setMaxBounds(maxBounds);
    if (minZoom != null || zoom) map.setMinZoom(minZoom ?? Math.max(2, zoom - 1));
    map.setView(center, zoom);
  }, [center[0], center[1], zoom, maxBounds]); // eslint-disable-line react-hooks/exhaustive-deps

  // (re)draw markers
  useEffect(() => {
    const L = window.L;
    if (!L || !mapRef.current || !layerRef.current) return;
    layerRef.current.clearLayers();
    for (const p of pins) {
      if (p.latitude == null || p.longitude == null) continue;
      const selected = selectedIds?.includes(p.id);
      const color = colorFor(p.category);
      const marker = L.circleMarker([p.latitude, p.longitude], {
        radius: selected ? 9 : 6,
        color: selected ? "#ffffff" : color,
        weight: selected ? 3 : 1.5,
        fillColor: color,
        fillOpacity: 0.85,
      });
      const loc = [p.city, p.country].filter(Boolean).join(", ");
      const sel = selected ? "Selected ✓" : "Select to compare";
      marker.bindPopup(
        `<div style="font-family:sans-serif;min-width:180px">
          <div style="font-weight:700;font-size:13px;margin-bottom:2px">${escapeHtml(p.name)}</div>
          <div style="font-size:11px;color:#555;text-transform:capitalize">${escapeHtml(p.category)}${loc ? " · " + escapeHtml(loc) : ""}</div>
          ${p.rating != null ? `<div style="font-size:11px;color:#a86b3d;font-weight:700;margin-top:2px">★ ${p.rating.toFixed(1)} rating</div>` : ""}
          ${p.offering ? `<div style="font-size:11px;color:#333;margin-top:4px">${escapeHtml(p.offering)}</div>` : ""}
          <div style="font-size:10px;color:#888;margin:4px 0">${p.source === "curated" ? "Verified manufacturer" : p.source === "discovered" ? "Discovered" : "Your supplier"}</div>
          <div style="display:flex;gap:6px;margin-bottom:6px">
            ${p.website ? `<a href="${escapeHtml(withScheme(p.website))}" target="_blank" rel="noopener noreferrer" style="flex:1;text-align:center;text-decoration:none;cursor:pointer;border:1px solid #3b82f6;background:#3b82f622;color:#2563eb;border-radius:8px;padding:4px 6px;font-size:11px;font-weight:700">🌐 Website</a>` : ""}
            <button class="mawrid-contact" style="flex:1;cursor:pointer;border:1px solid #7c4dff;background:#7c4dff22;color:#6a3de8;border-radius:8px;padding:4px 6px;font-size:11px;font-weight:700">✉ Contact</button>
          </div>
          <button class="mawrid-sel" style="cursor:pointer;border:1px solid ${selected ? "#059669" : "#d4a373"};background:${selected ? "#05966922" : "#d4a37322"};color:${selected ? "#059669" : "#a86b3d"};border-radius:8px;padding:4px 8px;font-size:11px;font-weight:700;width:100%">${sel}</button>
        </div>`,
      );
      // hover shows the popup; it disappears shortly after the pointer leaves the marker AND
      // the popup (so you still have time to click Website/Contact/Compare).
      let closeTimer: ReturnType<typeof setTimeout> | null = null;
      const cancelClose = () => { if (closeTimer) { clearTimeout(closeTimer); closeTimer = null; } };
      const scheduleClose = () => { cancelClose(); closeTimer = setTimeout(() => marker.closePopup(), 220); };
      marker.on("mouseover", () => { cancelClose(); marker.openPopup(); });
      marker.on("mouseout", scheduleClose);
      marker.on("popupopen", (e: any) => {
        const node = e.popup?._contentNode;
        const wrap = node?.closest?.(".leaflet-popup");
        if (wrap) {
          wrap.addEventListener("mouseenter", cancelClose);
          wrap.addEventListener("mouseleave", scheduleClose);
        }
        const sb = node?.querySelector?.(".mawrid-sel");
        if (sb) sb.onclick = () => { onSelect?.(p.id); marker.closePopup(); };
        const cb = node?.querySelector?.(".mawrid-contact");
        if (cb) cb.onclick = () => { onContact?.(p.id); marker.closePopup(); };
      });
      marker.on("click", () => onSelect?.(p.id));
      layerRef.current.addLayer(marker);
    }
  }, [pins, selectedIds, colorFor, onSelect, onContact]);

  // `isolate` + z-0 keep Leaflet's internal high z-index panes from rendering
  // over the sticky topbar/slogan when the page scrolls.
  return <div ref={elRef} style={{ height }} className="relative z-0 w-full overflow-hidden rounded-2xl border border-line [isolation:isolate]" />;
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] as string));
}

function withScheme(url: string): string {
  return /^https?:\/\//i.test(url) ? url : `https://${url}`;
}
