// Feature: Inventory — Shipments & Arrivals. Track containers for sent POs from dispatch to
//          arrival with an animated status stepper; arrival auto-fills from an agreed email
//          date and shows the exact time in Beirut. When one arrives, receive the goods.
// API:     GET /procurement/purchase-orders · GET/POST /procurement/shipments · PUT /procurement/shipments/{id}/status
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Ship, Plus, Container, CalendarClock, CheckCircle2, ArrowRight, Truck, Package, Building2, Clock } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiPut, apiErr } from "@/lib/api";
import { Card, SectionTitle, Loading, EmptyState, Spinner } from "@/components/ui";
import { cn } from "@/lib/utils";

interface PO { po_id: string; po_number: string; status: string }
interface Shipment { shipment_id: string; po_id: string; carrier: string | null; tracking_number: string | null; expected_arrival_date: string | null; expected_arrival_at: string | null; status: string; created_at: string }

const STEP_META = [
  { key: "pending_shipment", label: "Pending", icon: Package },
  { key: "shipped", label: "Shipped", icon: Ship },
  { key: "in_transit", label: "In transit", icon: Truck },
  { key: "at_customs", label: "At customs", icon: Building2 },
  { key: "arrived", label: "Arrived", icon: CheckCircle2 },
];

// The stored datetime is the importer's Beirut wall-clock (numbers preserved) — show as-is.
function fmtArrival(at: string | null, date: string | null): { date: string; time: string | null } | null {
  if (at) return { date: at.slice(0, 10), time: at.slice(11, 16) };
  if (date) return { date: date.slice(0, 10), time: null };
  return null;
}

export function Shipments() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const pos = useQuery({ queryKey: ["purchase-orders"], queryFn: () => apiGet<PO[]>("/procurement/purchase-orders") });
  const ships = useQuery({ queryKey: ["shipments"], queryFn: () => apiGet<Shipment[]>("/procurement/shipments"), refetchInterval: 12_000 });
  const shipList = ships.data ?? [];
  const withShip = new Set(shipList.map((s) => s.po_id));
  const sentPOs = (pos.data ?? []).filter((p) => ["sent", "replied", "confirmed"].includes(p.status) && !withShip.has(p.po_id));

  const [form, setForm] = useState({ po_id: "", carrier: "", tracking_number: "", date: "", time: "" });
  const create = useMutation({
    mutationFn: () => apiPost("/procurement/shipments", {
      po_id: form.po_id, carrier: form.carrier || null, tracking_number: form.tracking_number || null,
      expected_arrival_date: form.date || null,
      expected_arrival_at: form.date ? `${form.date}T${form.time || "12:00"}` : null,
    }),
    onSuccess: () => { toast.success("Shipment created"); setForm({ po_id: "", carrier: "", tracking_number: "", date: "", time: "" }); qc.invalidateQueries({ queryKey: ["shipments"] }); },
    onError: (e) => toast.error(apiErr(e, "Could not create")),
  });
  const update = useMutation({
    mutationFn: ({ id, status, at }: { id: string; status: string; at?: string }) => apiPut(`/procurement/shipments/${id}/status`, { status, expected_arrival_at: at }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shipments"] }),
    onError: (e) => toast.error(apiErr(e, "Update failed")),
  });
  const poNum = (id: string) => (pos.data ?? []).find((p) => p.po_id === id)?.po_number ?? id.slice(0, 8);

  return (
    <div className="space-y-6">
      <SectionTitle title="Shipments & Arrivals" subtitle="Track each container from your supplier to your warehouse — arrival times shown in Beirut time." />

      <Card>
        <SectionTitle title="New shipment" subtitle="Log a container for a sent purchase order." right={<Ship className="h-5 w-5 text-ink-faint" />} />
        {sentPOs.length === 0 ? <p className="text-sm text-ink-faint">No sent POs awaiting a shipment. Send a purchase order first.</p> : (
          <div className="grid gap-3 sm:grid-cols-6">
            <select className="input sm:col-span-2" value={form.po_id} onChange={(e) => setForm({ ...form, po_id: e.target.value })}>
              <option value="">Purchase order…</option>
              {sentPOs.map((p) => <option key={p.po_id} value={p.po_id}>{p.po_number}</option>)}
            </select>
            <input className="input" placeholder="Carrier" value={form.carrier} onChange={(e) => setForm({ ...form, carrier: e.target.value })} />
            <input className="input" placeholder="Container #" value={form.tracking_number} onChange={(e) => setForm({ ...form, tracking_number: e.target.value })} />
            <input className="input" type="date" title="Arrival date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            <input className="input" type="time" title="Arrival time (Beirut)" value={form.time} onChange={(e) => setForm({ ...form, time: e.target.value })} />
            <button className="btn-gold sm:col-span-6" disabled={!form.po_id || create.isPending} onClick={() => create.mutate()}>{create.isPending ? <Spinner className="h-4 w-4" /> : <Plus className="h-4 w-4" />} Create shipment</button>
          </div>
        )}
      </Card>

      <Card>
        <SectionTitle title="In transit & arrived" />
        {ships.isLoading ? <Loading /> : shipList.length === 0 ? (
          <EmptyState icon={<Container className="h-8 w-8" />} title="No shipments yet" hint="Create one above for a sent purchase order." />
        ) : (
          <div className="space-y-4">
            {shipList.map((s) => {
              const stepIdx = Math.max(0, STEP_META.findIndex((m) => m.key === s.status));
              const arrived = s.status === "arrived";
              const eta = fmtArrival(s.expected_arrival_at, s.expected_arrival_date);
              return (
                <motion.div key={s.shipment_id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl border border-line bg-white/[0.02] p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <motion.div className={cn("grid h-10 w-10 place-items-center rounded-xl", arrived ? "bg-emerald/15 text-emerald-soft" : "bg-gold/15 text-gold-soft")} animate={arrived ? { rotate: [0, -8, 0] } : {}} transition={{ duration: 0.6 }}>
                        {arrived ? <CheckCircle2 className="h-5 w-5" /> : <Truck className="h-5 w-5" />}
                      </motion.div>
                      <div>
                        <div className="font-mono text-sm font-700 text-ink">{poNum(s.po_id)}</div>
                        <div className="flex flex-wrap items-center gap-x-3 text-[11px] text-ink-soft">
                          {s.carrier && <span>{s.carrier}</span>}{s.tracking_number && <span><Container className="mr-1 inline h-3 w-3" />{s.tracking_number}</span>}
                          {eta && <span className="text-gold-soft"><CalendarClock className="mr-1 inline h-3 w-3" />ETA {eta.date}{eta.time ? ` · ${eta.time}` : ""}{eta.time ? <span className="text-ink-faint"> Beirut</span> : ""}</span>}
                        </div>
                      </div>
                    </div>
                    <ArrivalEditor at={s.expected_arrival_at} date={s.expected_arrival_date} saving={update.isPending} onSave={(iso) => update.mutate({ id: s.shipment_id, status: s.status, at: iso })} />
                  </div>

                  {/* animated status stepper */}
                  <div className="mt-4 flex items-center">
                    {STEP_META.map((st, i) => {
                      const done = i < stepIdx; const active = i === stepIdx;
                      return (
                        <div key={st.key} className={cn("flex items-center", i < STEP_META.length - 1 && "flex-1")}>
                          <button onClick={() => update.mutate({ id: s.shipment_id, status: st.key })} title={st.label} className="flex flex-col items-center gap-1">
                            <motion.span className="grid h-9 w-9 place-items-center rounded-full border-2"
                              style={{
                                borderColor: done || active ? "rgb(var(--accent))" : "rgb(148 163 184 / 0.35)",
                                background: done ? "rgb(var(--accent))" : active ? "rgb(var(--accent) / 0.15)" : "transparent",
                                color: done ? "rgb(var(--bg))" : active ? "rgb(var(--accent-soft))" : "rgb(148 163 184 / 0.8)",
                              }}
                              animate={active ? { scale: [1, 1.12, 1], boxShadow: ["0 0 0px rgb(var(--accent)/0)", "0 0 14px rgb(var(--accent)/0.6)", "0 0 0px rgb(var(--accent)/0)"] } : {}}
                              transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}>
                              <st.icon className="h-4 w-4" />
                            </motion.span>
                            <span className={cn("text-[9px] font-600", active ? "text-gold-soft" : done ? "text-emerald-soft" : "text-ink-faint")}>{st.label}</span>
                          </button>
                          {i < STEP_META.length - 1 && (
                            <div className="mx-1 mb-4 h-0.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                              <motion.div className="h-full rounded-full" style={{ background: "rgb(var(--accent))" }} initial={{ width: 0 }} animate={{ width: i < stepIdx ? "100%" : "0%" }} transition={{ duration: 0.5 }} />
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {arrived && <div className="mt-3 flex justify-end"><Link to={`/inventory/receive?shipment=${s.shipment_id}`} className="btn-gold !py-1.5 text-xs">Receive goods <ArrowRight className="h-3 w-3" /></Link></div>}
                </motion.div>
              );
            })}
          </div>
        )}
      </Card>
      {!ships.isLoading && shipList.some((s) => s.status === "arrived") && (
        <div className="text-center"><button onClick={() => navigate("/inventory/receive")} className="btn-ghost">Go to Receive Goods <ArrowRight className="h-4 w-4" /></button></div>
      )}
    </div>
  );
}

function ArrivalEditor({ at, date, onSave, saving }: { at: string | null; date: string | null; onSave: (iso: string) => void; saving: boolean }) {
  const [open, setOpen] = useState(false);
  const [d, setD] = useState(at ? at.slice(0, 10) : (date ?? ""));
  const [t, setT] = useState(at ? at.slice(11, 16) : "12:00");
  if (!open) return <button onClick={() => setOpen(true)} className="chip border-line bg-white/[0.03] text-ink-soft hover:text-ink"><Clock className="h-3 w-3" /> Set arrival</button>;
  return (
    <div className="flex items-center gap-1.5">
      <input type="date" className="input !py-1 text-xs" value={d} onChange={(e) => setD(e.target.value)} />
      <input type="time" className="input !py-1 text-xs" title="Beirut time" value={t} onChange={(e) => setT(e.target.value)} />
      <button className="chip border-gold/40 bg-gold/10 text-gold-soft" disabled={!d || saving} onClick={() => { onSave(`${d}T${t || "12:00"}`); setOpen(false); }}>{saving ? <Spinner className="h-3 w-3" /> : "Save"}</button>
    </div>
  );
}
