// Feature: Procurement — Edit Order. When a supplier asks for changes (quantities,
//          availability) or sets an arrival date, revise the purchase order here.
// API:     GET /procurement/purchase-orders/{id} · PATCH /procurement/purchase-orders/{id}
import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Trash2, Save, ArrowLeft, CalendarCheck, Ship, Building2 } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPatch, apiErr } from "@/lib/api";
import { Card, SectionTitle, Loading, Spinner } from "@/components/ui";
import { formatCurrency } from "@/lib/utils";

interface Line { product_id?: string; product_name?: string; sku?: string | null; quantity: number; unit_price: number; currency?: string }
interface PODetail { po_id: string; po_number: string; supplier_name: string | null; currency: string; line_items: Line[]; arrival_date: string | null; status: string }

export function EditOrder() {
  const { poId } = useParams();
  const navigate = useNavigate();
  const po = useQuery({ queryKey: ["po-detail", poId], queryFn: () => apiGet<PODetail>(`/procurement/purchase-orders/${poId}`), enabled: !!poId });
  const [lines, setLines] = useState<Line[] | null>(null);
  const [arrival, setArrival] = useState("");

  useEffect(() => {
    if (po.data && lines === null) {
      setLines(po.data.line_items.map((l) => ({ ...l, quantity: Number(l.quantity ?? 0), unit_price: Number(l.unit_price ?? 0) })));
      setArrival(po.data.arrival_date ? po.data.arrival_date.slice(0, 10) : "");
    }
  }, [po.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const d = po.data;
  const rows = lines ?? [];
  const currency = d?.currency ?? "USD";
  const total = rows.reduce((s, l) => s + (l.quantity || 0) * (l.unit_price || 0), 0);
  const setLine = (i: number, patch: Partial<Line>) => setLines((ls) => (ls ?? []).map((l, j) => (j === i ? { ...l, ...patch } : l)));

  const saveItems = useMutation({
    mutationFn: () => apiPatch(`/procurement/purchase-orders/${poId}`, { line_items: rows }),
    onSuccess: () => { toast.success("Order updated"); po.refetch(); },
    onError: (e) => toast.error(apiErr(e, "Update failed")),
  });
  const saveArrival = useMutation({
    mutationFn: () => apiPatch(`/procurement/purchase-orders/${poId}`, { agreed_delivery_date: arrival }),
    onSuccess: () => { toast.success("Arrival date saved — track it in Shipments & Arrivals"); po.refetch(); },
    onError: (e) => toast.error(apiErr(e, "Save failed")),
  });

  if (po.isLoading) return <Loading label="Loading order…" />;
  if (!d) return <Card><div className="py-10 text-center text-ink-soft">Order not found.</div></Card>;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <SectionTitle title={`Edit ${d.po_number}`} subtitle="Revise quantities/prices the supplier asked to change, and record the arrival date they set."
        right={<Link to={`/purchase-orders/${poId}`} className="btn-ghost !py-2"><ArrowLeft className="h-4 w-4" /> Back to thread</Link>} />

      <Card>
        <div className="mb-1 flex items-center gap-2 text-sm font-700 text-ink"><Building2 className="h-4 w-4 text-ink-faint" /> {d.supplier_name}</div>
        <SectionTitle title="Line items" subtitle="Adjust or remove what the supplier can't fulfil." />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-line text-left text-xs uppercase tracking-wider text-ink-faint">
              <th className="py-2 pr-2 font-600">Product</th><th className="px-2 text-right font-600">Qty</th><th className="px-2 text-right font-600">Unit</th><th className="px-2 text-right font-600">Total</th><th></th>
            </tr></thead>
            <tbody>
              {rows.map((l, i) => (
                <tr key={i} className="border-b border-line/60">
                  <td className="py-2 pr-2"><div className="line-clamp-1 text-ink">{l.product_name}</div><div className="font-mono text-[10px] text-ink-faint">{l.sku ?? "—"}</div></td>
                  <td className="px-2 text-right"><input type="number" min={0} value={l.quantity} onChange={(e) => setLine(i, { quantity: Math.max(0, Number(e.target.value)) })} className="input w-16 !py-1 text-right text-xs" /></td>
                  <td className="px-2 text-right"><input type="number" min={0} step="0.01" value={l.unit_price} onChange={(e) => setLine(i, { unit_price: Math.max(0, Number(e.target.value)) })} className="input w-20 !py-1 text-right text-xs" /></td>
                  <td className="px-2 text-right font-mono text-ink">{formatCurrency((l.quantity || 0) * (l.unit_price || 0), currency)}</td>
                  <td className="pl-1"><button onClick={() => setLines((ls) => (ls ?? []).filter((_, j) => j !== i))} className="text-ink-faint hover:text-danger"><Trash2 className="h-3.5 w-3.5" /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-3 flex items-center justify-between border-t border-line pt-3">
          <span className="text-base font-800 text-ink">{formatCurrency(total, currency)}</span>
          <button className="btn-gold" disabled={saveItems.isPending} onClick={() => saveItems.mutate()}>{saveItems.isPending ? <Spinner className="h-4 w-4" /> : <Save className="h-4 w-4" />} Save changes</button>
        </div>
      </Card>

      <Card>
        <SectionTitle title="Arrival date" subtitle="The date the supplier confirmed — it flows to Shipments & Arrivals." right={<Ship className="h-5 w-5 text-ink-faint" />} />
        <div className="flex items-end gap-3">
          <div><label className="label">Supplier's arrival date</label><input type="date" className="input" value={arrival} onChange={(e) => setArrival(e.target.value)} /></div>
          <button className="btn-gold" disabled={!arrival || saveArrival.isPending} onClick={() => saveArrival.mutate()}>{saveArrival.isPending ? <Spinner className="h-4 w-4" /> : <CalendarCheck className="h-4 w-4" />} Save arrival date</button>
          <button className="btn-ghost" onClick={() => navigate("/inventory/shipments")}>Go to Shipments <Ship className="h-4 w-4" /></button>
        </div>
      </Card>
    </div>
  );
}
