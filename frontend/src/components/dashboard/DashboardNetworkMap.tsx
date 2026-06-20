// Feature: Dashboard — Supplier Network map. Europe shows the real OSM map with the
//          tenant's supplier/factory locations; the other regions are shown with a
//          locked "coming soon" overlay (no locations yet).
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Lock, Globe2, MapPin, Star } from "lucide-react";
import { apiGet } from "@/lib/api";
import { LeafletMap } from "@/components/LeafletMap";
import { colorForCategory } from "@/stores/network";

interface Region { key: string; label: string; available: boolean; center: [number, number]; zoom: number; bounds?: [[number, number], [number, number]]; min_zoom?: number }
interface Pin { id: string; source: string; name: string; category: string; latitude: number | null; longitude: number | null; city?: string | null; country?: string | null; website?: string | null; offering?: string | null; rating?: number | null }
interface FactoriesResp { pins: Pin[]; categories: string[] }

const FALLBACK: Region[] = [
  { key: "europe", label: "Europe", available: true, center: [50, 10], zoom: 4, bounds: [[33, -16], [72, 45]], min_zoom: 4 },
  { key: "turkey", label: "Türkiye", available: false, center: [39, 35], zoom: 5 },
  { key: "gulf", label: "Gulf", available: false, center: [25, 50], zoom: 5 },
  { key: "china", label: "China", available: false, center: [35, 105], zoom: 4 },
  { key: "usa", label: "USA", available: false, center: [39, -98], zoom: 4 },
  { key: "australia", label: "Australia", available: false, center: [-25, 133], zoom: 4 },
];

export function DashboardNetworkMap() {
  const navigate = useNavigate();
  const [region, setRegion] = useState("europe");
  const regionsQ = useQuery({ queryKey: ["regions"], queryFn: () => apiGet<Region[]>("/network/regions") });
  const factories = useQuery({ queryKey: ["factories", "europe"], queryFn: () => apiGet<FactoriesResp>("/network/factories?region=europe"), staleTime: 30_000 });

  const regions = (regionsQ.data && regionsQ.data.length ? regionsQ.data : FALLBACK);
  const reg = regions.find((r) => r.key === region) ?? regions[0];
  const europe = region === "europe";
  const categories = factories.data?.categories ?? [];
  const pins = europe ? (factories.data?.pins ?? []).filter((p) => p.latitude != null && p.longitude != null) : [];
  const colorFor = (c: string) => colorForCategory(c, categories);
  const topRated = [...(factories.data?.pins ?? [])]
    .filter((p) => p.rating != null)
    .sort((a, b) => (b.rating ?? 0) - (a.rating ?? 0))
    .slice(0, 5);

  return (
    <div className="space-y-3">
      {/* region selector */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-1 text-xs uppercase tracking-wider text-ink-faint"><Globe2 className="h-3.5 w-3.5" /> Region</span>
        {regions.map((r) => (
          <button key={r.key} disabled={!r.available} onClick={() => r.available && setRegion(r.key)}
            className={`chip ${region === r.key ? "border-gold/50 bg-gold/15 text-gold-soft" : r.available ? "border-line bg-white/[0.02] text-ink-soft hover:text-ink" : "border-line bg-white/[0.01] text-ink-faint/70 cursor-not-allowed"}`}>
            {!r.available && <Lock className="h-3 w-3" />} {r.label}{!r.available && <span className="ml-0.5 text-[9px] uppercase">soon</span>}
          </button>
        ))}
      </div>

      {/* map + locked overlay */}
      <div className="relative">
        <LeafletMap pins={pins} center={reg.center} zoom={reg.zoom} colorFor={colorFor} height={340}
          maxBounds={reg.bounds} minZoom={reg.min_zoom}
          onContact={(id) => navigate(`/suppliers/outreach?target=${encodeURIComponent(id)}`)}
          onSelect={() => navigate("/suppliers/network")} />
        {!europe && (
          <div className="absolute inset-0 z-[5] grid place-items-center rounded-2xl border border-line bg-bg/55 backdrop-blur-md">
            <div className="flex flex-col items-center gap-2 text-center">
              <span className="grid h-14 w-14 place-items-center rounded-2xl border border-gold/30 bg-gold/10 text-gold-soft shadow-glow"><Lock className="h-6 w-6" /></span>
              <div className="text-lg font-800 text-ink">{reg.label}</div>
              <div className="chip border-gold/30 bg-gold/10 text-gold-soft">Coming soon</div>
              <p className="max-w-[220px] text-xs text-ink-faint">Sourcing in {reg.label} unlocks in a future wave — Europe is live now.</p>
            </div>
          </div>
        )}
      </div>

      {europe && (
        <div className="flex items-center justify-between text-xs text-ink-faint">
          <span className="flex items-center gap-1"><MapPin className="h-3 w-3" /> {pins.length} location(s) · hover a pin for website / contact</span>
          <span>{categories.length} categories</span>
        </div>
      )}

      {europe && topRated.length > 0 && (
        <div className="rounded-xl border border-line bg-white/[0.02] p-3">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-700 text-ink"><Star className="h-3.5 w-3.5 text-gold-soft" /> Top-rated makers</div>
          <div className="grid gap-1.5 sm:grid-cols-2">
            {topRated.map((p) => (
              <button key={p.id} onClick={() => navigate("/suppliers/network")} className="flex items-center justify-between gap-2 rounded-lg px-2 py-1 text-left text-xs transition-colors hover:bg-white/[0.05]">
                <span className="min-w-0 flex-1 truncate text-ink">{p.name}</span>
                <span className="flex shrink-0 items-center gap-0.5 font-700 text-gold-soft"><Star className="h-3 w-3 fill-current" /> {p.rating?.toFixed(1)}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
