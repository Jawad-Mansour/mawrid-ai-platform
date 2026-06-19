// Feature: Supplier & Factory Network — the map hub. Real OSM map (locked to the
//          region) of curated manufacturers + saved suppliers + discovered ones,
//          colour-coded by category, with condition filter and slow pausable
//          per-category carousels. Click a card to select for comparison; Contact
//          starts outreach.
// API:     GET /network/regions · GET /network/factories · POST /network/refresh
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, GitCompare, MapPin, Globe2, Lock, Building2, ExternalLink, Mail, Check, ArrowRight, Factory, Bot, Sparkles, Search, ImagePlus } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiErr } from "@/lib/api";
import { SectionTitle, Loading, Spinner, Card } from "@/components/ui";
import { LeafletMap } from "@/components/LeafletMap";
import { FactoryDetailModal } from "@/components/FactoryDetailModal";
import { ContactModal } from "@/components/ContactModal";
import { useNetwork, colorForCategory } from "@/stores/network";
import { brandLogoSources } from "@/lib/utils";

interface Region { key: string; label: string; available: boolean; center: [number, number]; zoom: number; bounds?: [[number, number], [number, number]]; min_zoom?: number }
interface Pin2 { id: string; source: string; name: string; category: string; latitude: number | null; longitude: number | null; city?: string | null; country?: string | null; website?: string | null; logo_url?: string | null; email?: string | null; condition?: string | null; offering?: string | null }
interface FactoriesResp { region: string; pins: Pin2[]; categories: string[] }

export function Network() {
  const qc = useQueryClient();
  const net = useNetwork();
  const [contact, setContact] = useState<Pin2 | null>(null);
  const [active, setActive] = useState<string[]>([]); // selected categories; empty = show all
  const [cond, setCond] = useState<"all" | "new" | "used" | "both">("all");
  const [detail, setDetail] = useState<Pin2 | null>(null);
  const [search, setSearch] = useState("");

  const regions = useQuery({ queryKey: ["regions"], queryFn: () => apiGet<Region[]>("/network/regions") });
  const data = useQuery({ queryKey: ["factories", net.region], queryFn: () => apiGet<FactoriesResp>(`/network/factories?region=${net.region}`), refetchInterval: 30_000 });
  const refresh = useMutation({
    mutationFn: () => apiPost<{ geocoded: number }>("/network/refresh", {}),
    onSuccess: (r) => { toast.success(`Map refreshed — ${r.geocoded} supplier(s) geocoded`); data.refetch(); },
    onError: (e) => toast.error(apiErr(e, "Refresh failed")),
  });
  const discoverAgent = useMutation({
    mutationFn: () => apiPost<{ added: number }>("/network/discover", {}),
    onSuccess: (r) => { toast.success(r.added > 0 ? `Discovery agent added ${r.added} new prospect(s)` : "No new suppliers found this run"); qc.invalidateQueries({ queryKey: ["factories"] }); },
    onError: (e) => toast.error(apiErr(e, "Discovery failed")),
  });
  const logoAgent = useMutation({
    mutationFn: () => apiPost<{ filled: number }>("/network/enrich-logos", {}),
    onSuccess: (r) => { toast.success(r.filled > 0 ? `Logo agent filled ${r.filled} logo(s)` : "All logos already set"); qc.invalidateQueries({ queryKey: ["factories"] }); },
    onError: (e) => toast.error(apiErr(e, "Logo agent failed")),
  });

  const region = (regions.data ?? []).find((r) => r.key === net.region) ?? { center: [50, 10] as [number, number], zoom: 4 };
  const allPins = data.data?.pins ?? [];
  const categories = data.data?.categories ?? [];
  const colorFor = (c: string) => colorForCategory(c, categories);
  const condOk = (c?: string | null) => cond === "all" || c === cond || (c === "both" && (cond === "new" || cond === "used"));
  const q = search.trim().toLowerCase();
  const visiblePins = useMemo(() => allPins.filter((p) =>
    (active.length === 0 || active.includes(p.category)) && condOk(p.condition) &&
    (!q || p.name.toLowerCase().includes(q) || (p.city ?? "").toLowerCase().includes(q) || (p.country ?? "").toLowerCase().includes(q))
  ), [allPins, active, cond, q]);
  const byCategory = useMemo(() => {
    const m = new Map<string, Pin2[]>();
    visiblePins.forEach((p) => { if (!m.has(p.category)) m.set(p.category, []); m.get(p.category)!.push(p); });
    return [...m.entries()];
  }, [visiblePins]);

  return (
    <div className="space-y-6">
      <SectionTitle title="Supplier & Factory Network" subtitle="Real manufacturers & suppliers on the map — verified makers, your saved suppliers, and new ones discovered for your business."
        right={
          <div className="flex gap-2">
            {net.selected.length > 0 && <Link to="/suppliers/compare" className="btn-gold !py-2"><GitCompare className="h-4 w-4" /> Compare {net.selected.length}</Link>}
            <button onClick={() => refresh.mutate()} disabled={refresh.isPending} className="btn-ghost !py-2">{refresh.isPending ? <Spinner className="h-4 w-4" /> : <RefreshCw className="h-4 w-4" />} Refresh</button>
          </div>
        } />

      {/* search a specific supplier/factory by name or place */}
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search a supplier by name, city or country…"
          className="input !pl-9" />
        {search && <button onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-ink-faint hover:text-ink">clear</button>}
      </div>

      {/* region + condition selectors */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-1 text-xs uppercase tracking-wider text-ink-faint"><Globe2 className="h-3.5 w-3.5" /> Region</span>
        {(regions.data ?? []).map((r) => (
          <button key={r.key} disabled={!r.available} onClick={() => r.available && net.setRegion(r.key)}
            className={`chip ${net.region === r.key ? "border-gold/50 bg-gold/15 text-gold-soft" : r.available ? "border-line bg-white/[0.02] text-ink-soft hover:text-ink" : "border-line bg-white/[0.01] text-ink-faint/60 cursor-not-allowed"}`}>
            {!r.available && <Lock className="h-3 w-3" />} {r.label}{!r.available && <span className="ml-1 text-[9px] uppercase">soon</span>}
          </button>
        ))}
        <span className="ml-3 text-xs uppercase tracking-wider text-ink-faint">Condition</span>
        {(["all", "new", "used", "both"] as const).map((c) => (
          <button key={c} onClick={() => setCond(c)} className={`chip capitalize ${cond === c ? "border-gold/50 bg-gold/15 text-gold-soft" : "border-line bg-white/[0.02] text-ink-soft hover:text-ink"}`}>{c}</button>
        ))}
      </div>

      {/* network agents */}
      <div className="grid gap-3 sm:grid-cols-2">
        <AgentCard icon={Search} title="Discovery agent" desc="Searches the web for new real suppliers in your business — runs automatically every morning."
          running={discoverAgent.isPending} onRun={() => discoverAgent.mutate()} />
        <AgentCard icon={ImagePlus} title="Logo agent" desc="Finds & fills missing company logos from their website — runs each morning and on hover/click."
          running={logoAgent.isPending} onRun={() => logoAgent.mutate()} />
      </div>

      {data.isLoading ? <Loading label="Loading the network…" /> : (
        <>
          <LeafletMap pins={visiblePins} center={region.center} zoom={region.zoom} colorFor={colorFor} selectedIds={net.selected} onSelect={(id) => net.toggle(id)}
            onContact={(id) => { const pin = visiblePins.find((x) => x.id === id); if (pin) setContact(pin); }}
            maxBounds={(region as Region).bounds} minZoom={(region as Region).min_zoom} />

          {/* category filter — click one to show ONLY it; click more to add; click again to remove */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs uppercase tracking-wider text-ink-faint">Categories</span>
            <button onClick={() => setActive([])}
              className={`chip ${active.length === 0 ? "border-gold/50 bg-gold/15 text-gold-soft" : "border-line bg-white/[0.02] text-ink-soft hover:text-ink"}`}>All</button>
            {categories.map((c) => {
              const on = active.includes(c);
              const dim = active.length > 0 && !on;
              return (
                <button key={c} onClick={() => setActive((a) => (a.includes(c) ? a.filter((x) => x !== c) : [...a, c]))}
                  className={`chip capitalize ${on ? "border-gold/50 bg-gold/15 text-gold-soft" : dim ? "border-line bg-white/[0.01] text-ink-faint opacity-50" : "border-line bg-white/[0.04] text-ink"}`}>
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: colorFor(c) }} /> {c.replace("-", " ")} <span className="text-[10px] text-ink-faint">{allPins.filter((p) => p.category === c).length}</span>
                </button>
              );
            })}
          </div>

          {/* per-category carousels (slow; pause on hover) */}
          <div className="space-y-7">
            {byCategory.map(([cat, pins], i) => (
              <div key={cat}>
                <div className="mb-2 flex items-center gap-2">
                  <span className="h-3 w-3 rounded-full" style={{ background: colorFor(cat) }} />
                  <h3 className="text-sm font-700 capitalize text-ink">{cat.replace("-", " ")}</h3>
                  <span className="text-xs text-ink-faint">{pins.length} · hover to pause</span>
                </div>
                <DragCarousel reverse={i % 2 === 1}>
                  {pins.map((p) => (
                    <FactoryCard key={p.id} p={p} selected={net.has(p.id)} color={colorFor(cat)}
                      onToggle={() => net.toggle(p.id)} onOpen={() => setDetail(p)} onContact={() => setContact(p)} />
                  ))}
                </DragCarousel>
              </div>
            ))}
            {byCategory.length === 0 && <Card><div className="py-8 text-center text-ink-faint">No suppliers in the visible categories.</div></Card>}
          </div>
        </>
      )}

      {detail && (
        <FactoryDetailModal pin={detail} color={colorFor(detail.category)} selected={net.has(detail.id)}
          onClose={() => setDetail(null)} onToggle={() => net.toggle(detail.id)}
          onContact={() => { setContact(detail); setDetail(null); }} />
      )}

      {contact && <ContactModal target={contact} onClose={() => setContact(null)} />}
    </div>
  );
}

function AgentCard({ icon: Icon, title, desc, running, onRun }: { icon: typeof Bot; title: string; desc: string; running: boolean; onRun: () => void }) {
  return (
    <Card className="flex items-center gap-3">
      <motion.div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-gold/30 to-grape/30 text-gold-soft"
        animate={running ? { rotate: 360 } : {}} transition={{ duration: 1.2, repeat: running ? Infinity : 0, ease: "linear" }}>
        <Icon className="h-5 w-5" />
      </motion.div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 text-sm font-700 text-ink"><Bot className="h-3.5 w-3.5 text-grape-soft" /> {title}</div>
        <div className="text-[11px] text-ink-soft">{desc}</div>
      </div>
      <button onClick={onRun} disabled={running} className="btn-ghost shrink-0 !py-1.5 text-xs">{running ? <Spinner className="h-3.5 w-3.5" /> : <Sparkles className="h-3.5 w-3.5" />} Run now</button>
    </Card>
  );
}

// Slow auto-scrolling marquee that (a) pauses on hover and (b) lets you grab & drag the row
// by hand while paused, then resumes auto-scroll when the pointer leaves. JS-driven transform
// so the manual drag and the loop share one offset. Cards are repeated enough to fill the row.
function DragCarousel({ children, reverse }: { children: React.ReactNode; reverse?: boolean }) {
  const items = (Array.isArray(children) ? children : [children]).filter(Boolean);
  const trackRef = useRef<HTMLDivElement>(null);
  const offset = useRef(0);
  const halfW = useRef(0);
  const paused = useRef(false);
  const drag = useRef({ active: false, startX: 0, startOffset: 0, moved: false });

  const reps = items.length ? Math.max(2, Math.ceil(6 / items.length)) : 0;
  const base = Array.from({ length: reps }, () => items).flat();

  const apply = (o: number) => {
    const h = halfW.current;
    if (h > 0) { while (o <= -h) o += h; while (o > 0) o -= h; }
    offset.current = o;
    if (trackRef.current) trackRef.current.style.transform = `translate3d(${o}px,0,0)`;
  };

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    const measure = () => { halfW.current = track.scrollWidth / 2; };
    measure();
    const speed = reverse ? 0.7 : -0.7; // px/frame
    let raf = 0;
    const tick = () => {
      if (halfW.current > 0 && !paused.current && !drag.current.active) apply(offset.current + speed);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    window.addEventListener("resize", measure);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", measure); };
  }, [base.length, reverse]); // eslint-disable-line react-hooks/exhaustive-deps

  if (items.length === 0) return null;
  return (
    <div className="overflow-hidden py-1"
      onMouseEnter={() => (paused.current = true)}
      onMouseLeave={() => { paused.current = false; drag.current.active = false; }}>
      <div ref={trackRef}
        className="flex w-max cursor-grab gap-3 select-none active:cursor-grabbing"
        onPointerDown={(e) => { drag.current = { active: true, startX: e.clientX, startOffset: offset.current, moved: false }; (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId); }}
        onPointerMove={(e) => { if (!drag.current.active) return; const dx = e.clientX - drag.current.startX; if (Math.abs(dx) > 4) drag.current.moved = true; apply(drag.current.startOffset + dx); }}
        onPointerUp={() => { drag.current.active = false; }}
        onPointerCancel={() => { drag.current.active = false; }}
        onClickCapture={(e) => { if (drag.current.moved) { e.preventDefault(); e.stopPropagation(); drag.current.moved = false; } }}>
        {[...base, ...base].map((c, i) => <div key={i} className="shrink-0">{c}</div>)}
      </div>
    </div>
  );
}

// Logo with a robust fallback chain (Google favicon → DuckDuckGo → initials); see
// brandLogoSources. A real uploaded logo wins; dead Clearbit URLs are ignored.
function Logo({ name, url, website, color }: { name: string; url?: string | null; website?: string | null; color: string }) {
  const sources = brandLogoSources(url, website);
  const [idx, setIdx] = useState(0);
  const src = sources[idx];
  if (!src) return <span className="text-sm font-800" style={{ color }}>{name[0]?.toUpperCase()}</span>;
  return <img src={src} alt="" className="h-full w-full object-contain p-1" onError={() => setIdx((i) => i + 1)} />;
}

function FactoryCard({ p, selected, color, onToggle, onOpen, onContact }: { p: Pin2; selected: boolean; color: string; onToggle: () => void; onOpen: () => void; onContact: () => void }) {
  const loc = [p.city, p.country].filter(Boolean).join(", ");
  return (
    <div onClick={onOpen} title="Click for full details"
      className={`card flex w-[270px] cursor-pointer flex-col p-3.5 transition-all hover:-translate-y-0.5 hover:shadow-glow ${selected ? "ring-1 ring-gold/60" : ""}`}>
      <div className="flex items-center gap-2.5">
        <div className="grid h-11 w-11 shrink-0 place-items-center overflow-hidden rounded-xl bg-white" style={{ boxShadow: `inset 0 0 0 1px ${color}33` }}>
          <Logo name={p.name} url={p.logo_url} website={p.website} color={color} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-700 text-ink">{p.name}</div>
          <div className="flex items-center gap-1 text-[11px] text-ink-faint">{p.source === "curated" ? <Building2 className="h-3 w-3" /> : <MapPin className="h-3 w-3" />}<span className="capitalize">{p.source === "curated" ? "Verified maker" : p.source}</span></div>
        </div>
        <button onClick={(e) => { e.stopPropagation(); onToggle(); }} title="Select to compare"
          className={`grid h-7 w-7 shrink-0 place-items-center rounded-lg border ${selected ? "border-gold bg-gold text-bg" : "border-line text-ink-soft hover:border-gold/50"}`}>{selected ? <Check className="h-3.5 w-3.5" /> : <GitCompare className="h-3.5 w-3.5" />}</button>
      </div>
      <p className="mt-2 line-clamp-2 min-h-[2.2rem] text-xs text-ink-soft">{p.offering ?? "—"}</p>
      <div className="mt-1.5 space-y-0.5 text-[11px] text-ink-faint">
        {loc && <div className="flex items-center gap-1"><MapPin className="h-3 w-3" /> {loc}</div>}
        {p.condition && <div className="capitalize">Sells: {p.condition}</div>}
      </div>
      <div className="mt-2.5 flex items-center gap-1.5 border-t border-line pt-2.5">
        {p.website && <a href={/^https?:\/\//.test(p.website) ? p.website : `https://${p.website}`} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} className="grid h-7 w-7 place-items-center rounded-lg border border-line text-ink-faint hover:text-ink" title="Visit website"><ExternalLink className="h-3.5 w-3.5" /></a>}
        <button onClick={(e) => { e.stopPropagation(); onContact(); }} className="btn-gold flex-1 !py-1.5 text-xs"><Mail className="h-3.5 w-3.5" /> Contact <ArrowRight className="h-3 w-3" /></button>
      </div>
    </div>
  );
}
