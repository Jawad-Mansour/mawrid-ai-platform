// Feature: Supplier & Factory Network — side-by-side comparison of selected
//          factories/suppliers (same category recommended).
// API:     POST /network/compare
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { GitCompare, X, Trash2, Mail, ExternalLink, MapPin, Factory, Star, AlertTriangle, ArrowLeft } from "lucide-react";
import { apiPost } from "@/lib/api";
import { SectionTitle, Card, Loading, EmptyState } from "@/components/ui";
import { useNetwork } from "@/stores/network";
import type { MapPin as Pin } from "@/components/LeafletMap";

interface Row extends Pin {
  website?: string | null; logo_url?: string | null; condition?: string | null; score?: number | null;
  subcategory?: string | null; email?: string | null; relationship?: string | null;
  rating?: number | null; moq?: number | null; currency?: string | null; language?: string | null;
  phone?: string | null; metrics?: Record<string, number> | null; po_count?: number; total_spend?: number;
}

export function Compare() {
  const navigate = useNavigate();
  const net = useNetwork();
  const q = useQuery({
    queryKey: ["compare", net.selected],
    queryFn: () => apiPost<Row[]>("/network/compare", { ids: net.selected }),
    enabled: net.selected.length > 0,
  });
  const rows = q.data ?? [];
  const mixed = new Set(rows.map((r) => r.category)).size > 1;

  if (net.selected.length < 2) {
    return (
      <div className="space-y-6">
        <SectionTitle title="Compare" subtitle="Select at least 2 factories or suppliers to compare them side by side."
          right={<Link to="/suppliers/network" className="btn-ghost !py-2"><ArrowLeft className="h-4 w-4" /> Network</Link>} />
        <Card><EmptyState icon={<GitCompare className="h-8 w-8" />} title={net.selected.length === 1 ? "Pick one more" : "Nothing selected"}
          hint={net.selected.length === 1 ? "You've selected 1 — choose at least one more from the Network map or Our Suppliers." : "Open the Network map (tap the compare icon on cards) or Our Suppliers, select 2+, then come back."} /></Card>
        <div className="flex justify-center gap-2">
          <Link to="/suppliers/network" className="btn-ghost"><GitCompare className="h-4 w-4" /> Network map</Link>
          <Link to="/suppliers" className="btn-ghost">Our Suppliers</Link>
        </div>
      </div>
    );
  }

  const txt = (v: any, suffix = "") => (v != null && v !== "" ? `${v}${suffix}` : "—");
  const pct = (v?: number) => (v != null ? `${Math.round(v * 100)}%` : "—");
  type RD = { label: string; render: (r: Row) => React.ReactNode } | { section: string };
  const rowDef: RD[] = [
    { section: "Profile" },
    { label: "Type", render: (r) => <span className="capitalize">{r.source === "curated" ? "Verified maker" : r.relationship === "prospect" ? "Prospect" : r.source === "discovered" ? "Discovered" : "Our supplier"}</span> },
    { label: "Category", render: (r) => <span className="capitalize">{r.category.replace("-", " ")}{r.subcategory ? ` · ${r.subcategory}` : ""}</span> },
    { label: "What they provide", render: (r) => <span className="text-ink-soft">{txt(r.offering)}</span> },
    { label: "Sells (condition)", render: (r) => <span className="capitalize">{txt(r.condition)}</span> },
    { section: "Location" },
    { label: "City / Country", render: (r) => <span className="flex items-center gap-1 text-ink-soft"><MapPin className="h-3 w-3" /> {[r.city, r.country].filter(Boolean).join(", ") || "—"}</span> },
    { section: "Commercial" },
    { label: "Email", render: (r) => <span className="text-ink-soft">{txt(r.email)}</span> },
    { label: "Phone", render: (r) => <span className="text-ink-soft">{txt(r.phone)}</span> },
    { label: "Website", render: (r) => r.website ? <a href={r.website} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-grape-soft hover:underline"><ExternalLink className="h-3 w-3" /> visit</a> : "—" },
    { label: "Currency / Lang", render: (r) => <span>{txt(r.currency)}{r.language ? ` · ${r.language.toUpperCase()}` : ""}</span> },
    { label: "MOQ", render: (r) => <span>{txt(r.moq, " units")}</span> },
    { label: "Rating", render: (r) => r.rating != null ? <span className="flex items-center gap-1 text-gold-soft"><Star className="h-3 w-3 fill-current" /> {r.rating.toFixed(1)}</span> : <span className="text-ink-faint">—</span> },
    { section: "Performance" },
    { label: "Score", render: (r) => r.score != null ? <span className="font-700 text-gold-soft">{r.score.toFixed(0)}/100</span> : <span className="text-ink-faint">—</span> },
    { label: "On-time delivery", render: (r) => <span>{pct(r.metrics?.on_time_delivery_rate)}</span> },
    { label: "Damage rate", render: (r) => <span>{pct(r.metrics?.damage_rate)}</span> },
    { label: "Discrepancy rate", render: (r) => <span>{pct(r.metrics?.discrepancy_rate)}</span> },
    { label: "Catalogue completeness", render: (r) => <span>{pct(r.metrics?.catalog_completeness)}</span> },
    { label: "Purchase orders", render: (r) => <span>{txt(r.po_count)}</span> },
    { label: "Total spend", render: (r) => <span>{r.total_spend ? `${r.currency ?? ""} ${r.total_spend.toLocaleString()}` : "—"}</span> },
  ];

  return (
    <div className="space-y-6">
      <SectionTitle title="Compare" subtitle={`${rows.length} selected`}
        right={<div className="flex gap-2"><button onClick={() => net.clear()} className="btn-ghost !py-2 text-xs"><Trash2 className="h-3.5 w-3.5" /> Clear</button><Link to="/suppliers/network" className="btn-ghost !py-2"><ArrowLeft className="h-4 w-4" /> Network</Link></div>} />

      {mixed && <div className="flex items-center gap-2 rounded-xl border border-warn/40 bg-warn/10 p-3 text-xs text-warn"><AlertTriangle className="h-4 w-4" /> You're comparing different categories — comparison is most meaningful within the same category.</div>}

      {q.isLoading ? <Loading /> : (
        <Card className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                <th className="w-40 p-2"></th>
                {rows.map((r) => (
                  <th key={r.id} className="min-w-[200px] border-l border-line p-3 text-left align-top">
                    <div className="flex items-start gap-2">
                      <div className="grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-lg bg-white">
                        {r.logo_url ? <img src={r.logo_url} alt="" className="h-full w-full object-contain p-1" onError={(e) => ((e.target as HTMLImageElement).style.display = "none")} /> : <Factory className="h-5 w-5 text-ink-faint" />}
                      </div>
                      <div className="min-w-0 flex-1"><div className="text-sm font-700 text-ink">{r.name}</div></div>
                      <button onClick={() => net.toggle(r.id)} className="text-ink-faint hover:text-danger"><X className="h-3.5 w-3.5" /></button>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rowDef.map((rd, i) => (
                "section" in rd ? (
                  <tr key={`s${i}`} className="border-t border-line bg-white/[0.02]">
                    <td colSpan={rows.length + 1} className="px-2 py-1.5 text-[11px] font-700 uppercase tracking-wider text-gold-soft">{rd.section}</td>
                  </tr>
                ) : (
                  <tr key={rd.label} className="border-t border-line">
                    <td className="p-2 text-xs uppercase tracking-wider text-ink-faint">{rd.label}</td>
                    {rows.map((r) => <td key={r.id} className="border-l border-line p-3 align-top text-ink">{rd.render(r)}</td>)}
                  </tr>
                )
              ))}
              <tr className="border-t border-line">
                <td className="p-2"></td>
                {rows.map((r) => (
                  <td key={r.id} className="border-l border-line p-3">
                    <button onClick={() => navigate(`/suppliers/outreach?target=${encodeURIComponent(r.id)}`)} className="btn-gold !py-1.5 text-xs"><Mail className="h-3.5 w-3.5" /> Contact</button>
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
