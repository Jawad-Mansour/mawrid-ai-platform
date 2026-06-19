// Feature: Suppliers — Our Suppliers (active) / Prospects directory. Add/edit via modal
//          (required fields + auto-find location), ask a supplier for a catalogue,
//          promote a prospect to Our Suppliers, see outreach history, and select 2+ to
//          compare on the rich Compare page.
// API:     GET /suppliers · PUT /suppliers/{id} · GET /network/conversations · POST /network/outreach
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Users, Plus, Mail, Phone, Star, MapPin, Pencil, GitCompare, MessageSquare, UserPlus, Check, Inbox, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiPut, apiDelete, apiErr } from "@/lib/api";
import { Card, SectionTitle, Loading, EmptyState, Spinner } from "@/components/ui";
import { SupplierEditModal } from "@/components/SupplierEditModal";
import { useNetwork } from "@/stores/network";
import type { Supplier } from "@/lib/types";

function asList(d: unknown): Supplier[] {
  if (Array.isArray(d)) return d as Supplier[];
  if (d && typeof d === "object" && Array.isArray((d as any).suppliers)) return (d as any).suppliers;
  return [];
}
interface Convo { supplier_id: string; message_count: number; last_direction: string | null }

export function Suppliers({ relationship }: { relationship?: "active" | "prospect" }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const net = useNetwork();
  const [editing, setEditing] = useState<{ supplier: Supplier | null } | null>(null);

  const list = useQuery({ queryKey: ["suppliers"], queryFn: () => apiGet<unknown>("/suppliers") });
  const convos = useQuery({ queryKey: ["conversations"], queryFn: () => apiGet<Convo[]>("/network/conversations") });
  const convoBy = useMemo(() => Object.fromEntries((convos.data ?? []).map((c) => [c.supplier_id, c])), [convos.data]);
  const suppliers = useMemo(() => {
    const all = asList(list.data);
    return relationship ? all.filter((s) => (s.relationship ?? "active") === relationship) : all;
  }, [list.data, relationship]);
  const isProspect = relationship === "prospect";

  const ask = useMutation({
    mutationFn: (s: Supplier) => apiPost<{ supplier_id: string }>("/network/outreach", { target_id: s.supplier_id, intent: "catalog", to: s.email || null }),
    onSuccess: (r) => { toast.success("Catalogue request drafted — approve in HITL"); qc.invalidateQueries({ queryKey: ["conversations"] }); navigate(`/suppliers/outreach?supplier=${r.supplier_id}`); },
    onError: (e) => toast.error(apiErr(e, "Could not draft")),
  });
  const promote = useMutation({
    mutationFn: (s: Supplier) => apiPut(`/suppliers/${s.supplier_id}`, { relationship: "active" }),
    onSuccess: () => { toast.success("Moved to Our Suppliers"); qc.invalidateQueries({ queryKey: ["suppliers"] }); },
    onError: (e) => toast.error(apiErr(e, "Failed")),
  });
  const remove = useMutation({
    mutationFn: (s: Supplier) => apiDelete(`/suppliers/${s.supplier_id}`),
    onSuccess: () => { toast.success("Supplier removed"); qc.invalidateQueries({ queryKey: ["suppliers"] }); qc.invalidateQueries({ queryKey: ["factories"] }); net.clear(); },
    onError: (e) => toast.error(apiErr(e, "Could not remove")),
  });

  const selectedHere = suppliers.filter((s) => net.has(s.supplier_id)).length;

  return (
    <div className="space-y-6">
      <SectionTitle
        title={isProspect ? "Prospects" : relationship === "active" ? "Our Suppliers" : "Suppliers"}
        subtitle={isProspect
          ? "Companies you're discovering or in outreach with — they become 'Our Suppliers' once you enrich a list from them or place an order."
          : "Suppliers you do business with — scored by delivery reliability, price consistency & catalogue completeness."}
        right={
          <div className="flex gap-2">
            {selectedHere >= 2 && <button onClick={() => navigate("/suppliers/compare")} className="btn-gold !py-2"><GitCompare className="h-4 w-4" /> Compare {selectedHere}</button>}
            <button className="btn-gold !py-2" onClick={() => setEditing({ supplier: null })}><Plus className="h-4 w-4" /> Add supplier</button>
          </div>
        } />

      <Card>
        <SectionTitle title="Directory" subtitle={`${suppliers.length} ${isProspect ? "prospect(s)" : "supplier(s)"} · select 2+ to compare`} />
        {list.isLoading ? <Loading /> : suppliers.length === 0 ? (
          <EmptyState icon={<Users className="h-8 w-8" />} title={isProspect ? "No prospects yet" : "No suppliers yet"} hint={isProspect ? "Discover some on the Network map, or add one manually." : "Add your first supplier, or enrich a sheet to create one automatically."} />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {suppliers.map((s) => {
              const on = net.has(s.supplier_id);
              const c = convoBy[s.supplier_id];
              return (
                <div key={s.supplier_id} className={`card p-4 transition-all ${on ? "ring-1 ring-gold/50 shadow-glow" : ""}`}>
                  <div className="flex items-start justify-between gap-2">
                    <button onClick={() => net.toggle(s.supplier_id)} className="min-w-0 flex-1 text-left">
                      <div className="truncate font-700 text-ink">{s.name}</div>
                      {s.rating != null && <span className="mt-0.5 flex items-center gap-0.5 text-xs font-700 text-gold-soft"><Star className="h-3 w-3 fill-current" /> {Number(s.rating).toFixed(1)}</span>}
                    </button>
                    <span className={`grid h-6 w-6 shrink-0 place-items-center rounded-md border ${on ? "border-gold bg-gold text-bg" : "border-line text-ink-faint"}`}>{on ? <Check className="h-3.5 w-3.5" /> : <GitCompare className="h-3 w-3" />}</span>
                  </div>
                  <div className="mt-2 space-y-1 text-xs text-ink-faint">
                    {s.location && <div className="flex items-center gap-1.5"><MapPin className="h-3 w-3" /> {s.location}</div>}
                    {s.email && <div className="flex items-center gap-1.5"><Mail className="h-3 w-3" /> {s.email}</div>}
                    {s.phone && <div className="flex items-center gap-1.5"><Phone className="h-3 w-3" /> {s.phone}</div>}
                    {c && <button onClick={() => navigate(`/suppliers/outreach?supplier=${s.supplier_id}`)} className="flex items-center gap-1.5 text-grape-soft hover:underline"><MessageSquare className="h-3 w-3" /> {c.message_count} message(s){c.last_direction === "inbound" ? " · replied" : ""}</button>}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1.5 border-t border-line pt-3">
                    <button onClick={() => setEditing({ supplier: s })} className="chip border-line bg-white/[0.03] text-ink-soft hover:text-ink"><Pencil className="h-3 w-3" /> Edit</button>
                    <button onClick={() => ask.mutate(s)} disabled={ask.isPending} className="chip border-grape/30 bg-grape/10 text-grape-soft hover:bg-grape/20">{ask.isPending ? <Spinner className="h-3 w-3" /> : <Inbox className="h-3 w-3" />} Ask for catalogue</button>
                    {isProspect && <button onClick={() => promote.mutate(s)} disabled={promote.isPending} className="chip border-emerald/30 bg-emerald/10 text-emerald-soft hover:bg-emerald/20"><UserPlus className="h-3 w-3" /> Add to Our Suppliers</button>}
                    <button onClick={() => { if (window.confirm(`Remove ${s.name}? This can't be undone.`)) remove.mutate(s); }} disabled={remove.isPending} className="chip border-danger/30 bg-danger/10 text-danger hover:bg-danger/20" title="Remove supplier"><Trash2 className="h-3 w-3" /> Remove</button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {net.selected.length > 0 && (
          <div className="mt-4 flex items-center justify-between rounded-xl border border-gold/30 bg-gold/[0.05] p-3 text-sm">
            <span className="text-ink-soft">{net.selected.length} selected for comparison{net.selected.length < 2 ? " — pick at least 2" : ""}</span>
            <div className="flex gap-2">
              <button onClick={() => net.clear()} className="btn-ghost !py-1.5 text-xs">Clear</button>
              <button onClick={() => navigate("/suppliers/compare")} disabled={net.selected.length < 2} className="btn-gold !py-1.5 text-xs"><GitCompare className="h-3.5 w-3.5" /> Compare</button>
            </div>
          </div>
        )}
      </Card>

      {editing && <SupplierEditModal supplier={editing.supplier} onClose={() => setEditing(null)} />}
    </div>
  );
}
