// Feature: Procurement — Purchase Orders: PO drafts awaiting review/send + sent POs.
// API:     GET /hitl/actions?action_type=purchase_order_send · GET /procurement/purchase-orders
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ClipboardList, Send, ArrowRight, Plus } from "lucide-react";
import { apiGet } from "@/lib/api";
import { Card, SectionTitle, Loading, EmptyState, StatusBadge } from "@/components/ui";
import { formatCurrency, formatRelativeDate } from "@/lib/utils";

interface HITLAction { action_id: string; status: string; payload: Record<string, any>; created_at: string }
interface PO { po_id: string; po_number: string; supplier_id: string; status: string; total_amount: number | null; currency: string; created_at: string }

export function PurchaseOrders() {
  const pending = useQuery({ queryKey: ["po-pending"], queryFn: () => apiGet<HITLAction[]>("/hitl/actions?action_type=purchase_order_send"), refetchInterval: 10_000 });
  const pos = useQuery({ queryKey: ["purchase-orders"], queryFn: () => apiGet<PO[]>("/procurement/purchase-orders"), refetchInterval: 12_000 });

  const pendingList = Array.isArray(pending.data) ? pending.data : [];
  const poList = Array.isArray(pos.data) ? pos.data : [];

  return (
    <div className="space-y-6">
      <SectionTitle title="Purchase Orders" subtitle="Draft requests awaiting your approval, and orders already sent to suppliers."
        right={<Link to="/procurement" className="btn-gold !py-2"><Plus className="h-4 w-4" /> New order</Link>} />

      {/* awaiting review */}
      <Card>
        <SectionTitle title="Awaiting review & send" subtitle="The AI drafted these — approve to email the supplier." />
        {pending.isLoading ? <Loading /> : pendingList.length === 0 ? (
          <EmptyState icon={<Send className="h-8 w-8" />} title="Nothing to send" hint="Create an order from the catalogue to draft a request." />
        ) : (
          <div className="space-y-2">
            {pendingList.map((a) => (
              <Link key={a.action_id} to={`/procurement/review/${a.action_id}`}
                className="flex items-center gap-3 rounded-xl border border-gold/30 bg-gold/[0.05] p-3.5 transition-all hover:-translate-y-0.5 hover:shadow-glow">
                <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-gold/15 text-gold-soft"><ClipboardList className="h-5 w-5" /></div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-700 text-ink">{a.payload.po_number} · {a.payload.supplier_name}</div>
                  <div className="text-xs text-ink-soft">{(a.payload.line_items?.length ?? 0)} line(s) · {formatCurrency(Number(a.payload.total ?? 0), a.payload.currency ?? "USD")} · {formatRelativeDate(a.created_at)}</div>
                </div>
                <span className="chip border-gold/40 bg-gold/10 text-gold-soft">Review &amp; send <ArrowRight className="h-3 w-3" /></span>
              </Link>
            ))}
          </div>
        )}
      </Card>

      {/* sent / history */}
      <Card>
        <SectionTitle title="Sent purchase orders" />
        {pos.isLoading ? <Loading /> : poList.length === 0 ? (
          <EmptyState title="No purchase orders yet" hint="Approved orders appear here." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-xs uppercase tracking-wider text-ink-faint">
                <th className="py-2.5 pr-3 font-600">PO</th><th className="px-3 font-600">Total</th>
                <th className="px-3 font-600">Status</th><th className="px-3 font-600">Created</th>
              </tr></thead>
              <tbody>
                {poList.map((p) => (
                  <tr key={p.po_id} className="table-row">
                    <td className="py-3 pr-3 font-mono text-xs text-ink">{p.po_number}</td>
                    <td className="px-3 text-ink-soft">{p.total_amount != null ? formatCurrency(p.total_amount, p.currency) : "—"}</td>
                    <td className="px-3"><StatusBadge status={p.status} /></td>
                    <td className="px-3 text-ink-faint">{formatRelativeDate(p.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
