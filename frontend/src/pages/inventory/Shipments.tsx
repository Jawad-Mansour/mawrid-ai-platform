// Feature: Inventory — Shipments & Arrivals. Track containers for sent POs from
//          dispatch to arrival; when one arrives, receive the goods.
// API:     GET /procurement/purchase-orders · GET/POST /procurement/shipments · PUT /procurement/shipments/{id}/status
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Ship, Plus, Container, CalendarClock, CheckCircle2, ArrowRight, Truck } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiPut, apiErr } from "@/lib/api";
import { Card, SectionTitle, Loading, EmptyState, StatusBadge, Spinner } from "@/components/ui";
import { formatRelativeDate } from "@/lib/utils";

interface PO { po_id: string; po_number: string; status: string }
interface Shipment { shipment_id: string; po_id: string; carrier: string | null; tracking_number: string | null; expected_arrival_date: string | null; status: string; created_at: string }

const STEPS = ["pending_shipment", "shipped", "in_transit", "at_customs", "arrived"];

export function Shipments() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const pos = useQuery({ queryKey: ["purchase-orders"], queryFn: () => apiGet<PO[]>("/procurement/purchase-orders") });
  const ships = useQuery({ queryKey: ["shipments"], queryFn: () => apiGet<Shipment[]>("/procurement/shipments"), refetchInterval: 12_000 });
  const shipList = ships.data ?? [];
  const withShip = new Set(shipList.map((s) => s.po_id));
  const sentPOs = (pos.data ?? []).filter((p) => ["sent", "replied", "confirmed"].includes(p.status) && !withShip.has(p.po_id));

  const [form, setForm] = useState({ po_id: "", carrier: "", tracking_number: "", expected_arrival_date: "" });
  const create = useMutation({
    mutationFn: () => apiPost("/procurement/shipments", form),
    onSuccess: () => { toast.success("Shipment created"); setForm({ po_id: "", carrier: "", tracking_number: "", expected_arrival_date: "" }); qc.invalidateQueries({ queryKey: ["shipments"] }); },
    onError: (e) => toast.error(apiErr(e, "Could not create")),
  });
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => apiPut(`/procurement/shipments/${id}/status`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shipments"] }),
    onError: (e) => toast.error(apiErr(e, "Update failed")),
  });
  const poNum = (id: string) => (pos.data ?? []).find((p) => p.po_id === id)?.po_number ?? id.slice(0, 8);

  return (
    <div className="space-y-6">
      <SectionTitle title="Shipments & Arrivals" subtitle="Track each container from your supplier to your warehouse." />

      <Card>
        <SectionTitle title="New shipment" subtitle="Log a container for a sent purchase order." right={<Ship className="h-5 w-5 text-ink-faint" />} />
        {sentPOs.length === 0 ? <p className="text-sm text-ink-faint">No sent POs awaiting a shipment. Send a purchase order first.</p> : (
          <div className="grid gap-3 sm:grid-cols-5">
            <select className="input sm:col-span-2" value={form.po_id} onChange={(e) => setForm({ ...form, po_id: e.target.value })}>
              <option value="">Purchase order…</option>
              {sentPOs.map((p) => <option key={p.po_id} value={p.po_id}>{p.po_number}</option>)}
            </select>
            <input className="input" placeholder="Carrier" value={form.carrier} onChange={(e) => setForm({ ...form, carrier: e.target.value })} />
            <input className="input" placeholder="Container #" value={form.tracking_number} onChange={(e) => setForm({ ...form, tracking_number: e.target.value })} />
            <input className="input" type="date" value={form.expected_arrival_date} onChange={(e) => setForm({ ...form, expected_arrival_date: e.target.value })} />
            <button className="btn-gold sm:col-span-5" disabled={!form.po_id || create.isPending} onClick={() => create.mutate()}>{create.isPending ? <Spinner className="h-4 w-4" /> : <Plus className="h-4 w-4" />} Create shipment</button>
          </div>
        )}
      </Card>

      <Card>
        <SectionTitle title="In transit & arrived" />
        {ships.isLoading ? <Loading /> : shipList.length === 0 ? (
          <EmptyState icon={<Container className="h-8 w-8" />} title="No shipments yet" hint="Create one above for a sent purchase order." />
        ) : (
          <div className="space-y-3">
            {shipList.map((s) => {
              const stepIdx = STEPS.indexOf(s.status);
              const arrived = s.status === "arrived";
              return (
                <motion.div key={s.shipment_id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="rounded-xl border border-line bg-white/[0.02] p-3.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <motion.div className={`grid h-10 w-10 place-items-center rounded-xl ${arrived ? "bg-emerald/15 text-emerald-soft" : "bg-gold/15 text-gold-soft"}`} animate={arrived ? { rotate: [0, -8, 0] } : {}} transition={{ duration: 0.6 }}>
                        {arrived ? <CheckCircle2 className="h-5 w-5" /> : <Truck className="h-5 w-5" />}
                      </motion.div>
                      <div>
                        <div className="font-mono text-sm font-700 text-ink">{poNum(s.po_id)}</div>
                        <div className="flex flex-wrap items-center gap-x-3 text-[11px] text-ink-soft">
                          {s.carrier && <span>{s.carrier}</span>}{s.tracking_number && <span><Container className="mr-1 inline h-3 w-3" />{s.tracking_number}</span>}
                          {s.expected_arrival_date && <span><CalendarClock className="mr-1 inline h-3 w-3" />ETA {formatRelativeDate(s.expected_arrival_date)}</span>}
                        </div>
                      </div>
                    </div>
                    <StatusBadge status={s.status} />
                  </div>
                  {/* status stepper */}
                  <div className="mt-3 flex flex-wrap items-center gap-1">
                    {STEPS.map((st, i) => (
                      <button key={st} onClick={() => setStatus.mutate({ id: s.shipment_id, status: st })}
                        className={`chip text-[10px] ${i === stepIdx ? "border-gold/50 bg-gold/15 text-gold-soft" : i < stepIdx ? "border-emerald/30 bg-emerald/10 text-emerald-soft" : "border-line bg-white/[0.02] text-ink-faint"}`}>{st.replace(/_/g, " ")}</button>
                    ))}
                    {arrived && <Link to={`/inventory/receive?shipment=${s.shipment_id}`} className="btn-gold !py-1.5 ml-auto text-xs">Receive goods <ArrowRight className="h-3 w-3" /></Link>}
                  </div>
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
