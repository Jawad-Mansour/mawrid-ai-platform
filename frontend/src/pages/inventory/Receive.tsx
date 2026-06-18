// Feature: Inventory — Receive Goods. Per-product arrival checklist (received vs
//          ordered, damaged, notes) → atomic stock update → goods-received report
//          PDF → email a thank-you to the supplier, or file a dispute if short/damaged.
// API:     GET /procurement/shipments · GET /procurement/purchase-orders/{po} ·
//          POST /procurement/shipments/{id}/receive · /receipt-pdf · /receipt-email · /dispute
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ClipboardCheck, Package, AlertTriangle, Download, Send, FileWarning, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiErr, apiClient } from "@/lib/api";
import { Card, SectionTitle, Loading, EmptyState, Spinner } from "@/components/ui";

interface Shipment { shipment_id: string; po_id: string; status: string }
interface POLine { product_id: string; product_name: string; sku?: string | null; quantity: number }
interface PODetail { po_id: string; po_number: string; line_items: POLine[]; supplier_email: string | null }
interface Row { product_id: string; product_name: string; sku?: string | null; ordered: number; received: number; damaged: number; note: string }

export function Receive() {
  const [params] = useSearchParams();
  const qc = useQueryClient();
  const [shipId, setShipId] = useState(params.get("shipment") ?? "");
  const [rows, setRows] = useState<Row[] | null>(null);
  const [notes, setNotes] = useState("");
  const [received, setReceived] = useState(false);

  const ships = useQuery({ queryKey: ["shipments"], queryFn: () => apiGet<Shipment[]>("/procurement/shipments") });
  const arrived = (ships.data ?? []).filter((s) => s.status === "arrived");
  const ship = (ships.data ?? []).find((s) => s.shipment_id === shipId);
  const po = useQuery({ queryKey: ["po-detail", ship?.po_id], queryFn: () => apiGet<PODetail>(`/procurement/purchase-orders/${ship!.po_id}`), enabled: !!ship?.po_id });

  useEffect(() => {
    if (po.data && rows === null) setRows(po.data.line_items.map((l) => ({ product_id: l.product_id, product_name: l.product_name, sku: l.sku, ordered: l.quantity, received: l.quantity, damaged: 0, note: "" })));
  }, [po.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const r = rows ?? [];
  const allGood = r.every((x) => x.received >= x.ordered && x.damaged === 0);
  const setRow = (i: number, patch: Partial<Row>) => setRows((rs) => (rs ?? []).map((x, j) => (j === i ? { ...x, ...patch } : x)));

  const submit = useMutation({
    mutationFn: () => apiPost(`/procurement/shipments/${shipId}/receive`, { items: r.map((x) => ({ product_id: x.product_id, qty_received: x.received, qty_damaged: x.damaged })), notes }),
    onSuccess: () => { setReceived(true); toast.success("Stock updated"); qc.invalidateQueries({ queryKey: ["catalog"] }); },
    onError: (e) => toast.error(apiErr(e, "Receive failed")),
  });
  async function downloadReport() {
    try {
      const res = await apiClient.get(`/procurement/shipments/${shipId}/receipt-pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data as Blob); const a = document.createElement("a");
      a.href = url; a.download = `receipt-${po.data?.po_number ?? "report"}.pdf`; a.click(); URL.revokeObjectURL(url);
    } catch (e) { toast.error(apiErr(e, "Download failed")); }
  }
  const sendReceipt = useMutation({
    mutationFn: () => apiPost(`/procurement/shipments/${shipId}/receipt-email`, {}),
    onSuccess: (d: any) => toast.success(d?.outcome === "good" ? "Thank-you receipt sent" : "Report sent (discrepancies noted)"),
    onError: (e) => toast.error(apiErr(e, "Send failed")),
  });
  const fileDispute = useMutation({
    mutationFn: () => apiPost(`/procurement/shipments/${shipId}/dispute`, {
      damaged_items: r.filter((x) => x.damaged > 0 || x.received < x.ordered).map((x) => ({ product_id: x.product_id, product: x.product_name, damaged: x.damaged, short: x.ordered - x.received })),
      damage_description: r.filter((x) => x.damaged > 0 || x.received < x.ordered).map((x) => `${x.product_name}: ${x.damaged} damaged, ${Math.max(0, x.ordered - x.received)} short. ${x.note}`).join("; ") || "Discrepancies on arrival.",
    }),
    onSuccess: () => toast.success("Dispute drafted — approve it in HITL to send"),
    onError: (e) => toast.error(apiErr(e, "Could not file dispute")),
  });

  return (
    <div className="space-y-6">
      <SectionTitle title="Received Goods" subtitle="Check off every product as the container is unloaded — stock updates atomically, then send the report or file a dispute for damage/shortage." />

      {ships.isLoading ? <Loading /> : arrived.length === 0 ? (
        <Card><EmptyState icon={<Package className="h-8 w-8" />} title="No arrived shipments" hint="Mark a shipment 'arrived' in Shipments & Arrivals first." /></Card>
      ) : (
        <Card>
          <label className="label">Arrived shipment</label>
          <select className="input !w-auto" value={shipId} onChange={(e) => { setShipId(e.target.value); setRows(null); setReceived(false); }}>
            <option value="">Select…</option>
            {arrived.map((s) => <option key={s.shipment_id} value={s.shipment_id}>{(ships.data ?? []).find((x) => x.shipment_id === s.shipment_id) ? s.shipment_id.slice(0, 8) : s.shipment_id}</option>)}
          </select>
        </Card>
      )}

      {shipId && po.isLoading && <Loading />}
      {shipId && po.data && (
        <Card>
          <SectionTitle title={`Checklist — ${po.data.po_number}`} subtitle="Received vs ordered, plus any damage." right={<ClipboardCheck className="h-5 w-5 text-ink-faint" />} />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-xs uppercase tracking-wider text-ink-faint">
                <th className="py-2 pr-2 font-600">Product</th><th className="px-2 text-right font-600">Ordered</th><th className="px-2 text-right font-600">Received</th><th className="px-2 text-right font-600">Damaged</th><th className="px-2 font-600">Note</th>
              </tr></thead>
              <tbody>
                {r.map((x, i) => {
                  const issue = x.received < x.ordered || x.damaged > 0;
                  return (
                    <tr key={i} className={`border-b border-line/60 ${issue ? "bg-danger/5" : ""}`}>
                      <td className="py-2 pr-2"><div className="line-clamp-1 text-ink">{x.product_name}</div><div className="font-mono text-[10px] text-ink-faint">{x.sku ?? "—"}</div></td>
                      <td className="px-2 text-right font-mono text-ink-soft">{x.ordered}</td>
                      <td className="px-2 text-right"><input disabled={received} type="number" min={0} value={x.received} onChange={(e) => setRow(i, { received: Math.max(0, Number(e.target.value)) })} className="input w-16 !py-1 text-right text-xs" /></td>
                      <td className="px-2 text-right"><input disabled={received} type="number" min={0} value={x.damaged} onChange={(e) => setRow(i, { damaged: Math.max(0, Number(e.target.value)) })} className="input w-16 !py-1 text-right text-xs" /></td>
                      <td className="px-2"><input disabled={received} value={x.note} onChange={(e) => setRow(i, { note: e.target.value })} placeholder="optional" className="input !py-1 text-xs" /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="mt-3"><label className="label">Overall notes</label><input disabled={received} className="input" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="e.g. container seal intact, two boxes crushed" /></div>

          {!received ? (
            <div className="mt-4 flex items-center justify-between gap-3">
              <div className={`flex items-center gap-2 text-sm ${allGood ? "text-emerald-soft" : "text-warn"}`}>{allGood ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}{allGood ? "All good" : "Discrepancies detected"}</div>
              <button className="btn-gold" disabled={submit.isPending} onClick={() => submit.mutate()}>{submit.isPending ? <Spinner className="h-4 w-4" /> : <ClipboardCheck className="h-4 w-4" />} Confirm receipt & update stock</button>
            </div>
          ) : (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mt-4 space-y-3">
              <div className={`flex items-center gap-2 rounded-xl border p-3 text-sm ${allGood ? "border-emerald/30 bg-emerald/10 text-emerald-soft" : "border-warn/40 bg-warn/10 text-warn"}`}>
                {allGood ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                {allGood ? "Received in full — send a thank-you receipt." : "Issues found — send the report and/or file a dispute (real claim email via HITL)."}
              </div>
              <div className="flex flex-wrap gap-2">
                <button className="btn-ghost" onClick={downloadReport}><Download className="h-4 w-4" /> Download report PDF</button>
                <button className="btn-gold" disabled={!po.data.supplier_email || sendReceipt.isPending} onClick={() => sendReceipt.mutate()}>{sendReceipt.isPending ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />} {allGood ? "Send thank-you + receipt" : "Send report to supplier"}</button>
                {!allGood && <button className="btn-danger" disabled={fileDispute.isPending} onClick={() => fileDispute.mutate()}>{fileDispute.isPending ? <Spinner className="h-4 w-4" /> : <FileWarning className="h-4 w-4" />} File dispute</button>}
              </div>
              {!po.data.supplier_email && <p className="text-xs text-warn">⚠ Add a supplier email to send the receipt.</p>}
            </motion.div>
          )}
        </Card>
      )}
    </div>
  );
}
