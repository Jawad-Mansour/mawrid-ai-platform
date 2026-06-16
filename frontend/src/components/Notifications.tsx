// Feature: Layout — notifications center. Aggregates the important things the
//          operator should act on: HITL approvals, products needing review,
//          enrichment in progress / failed, low stock.
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { Bell, CheckSquare, ShieldQuestion, Sparkles, AlertTriangle, PackageMinus, BellOff } from "lucide-react";
import { apiGet } from "@/lib/api";
import type { DashboardSummary, Product } from "@/lib/types";

interface Note { icon: typeof Bell; title: string; detail: string; to: string; tone: string; count: number; important?: boolean }

function asProducts(d: unknown): Product[] {
  if (Array.isArray(d)) return d as Product[];
  if (d && typeof d === "object" && Array.isArray((d as any).products)) return (d as any).products;
  return [];
}

export function Notifications() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const summary = useQuery({ queryKey: ["summary-bell"], queryFn: () => apiGet<DashboardSummary>("/admin/summary"), refetchInterval: 20_000 });
  const products = useQuery({ queryKey: ["catalog"], queryFn: () => apiGet<unknown>("/catalog/products?limit=300"), refetchInterval: 15_000 });

  useEffect(() => {
    function onDoc(e: MouseEvent) { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const s = summary.data;
  const prods = asProducts(products.data);
  const needsReview = prods.filter((p) => p.enrichment_status === "needs_review").length;
  const enriching = prods.filter((p) => p.enrichment_status === "pending").length;

  const notes: Note[] = [];
  if ((s?.pending_hitl_count ?? 0) > 0) notes.push({ icon: CheckSquare, title: "HITL approvals waiting", detail: `${s!.pending_hitl_count} action(s) need your approval`, to: "/approvals", tone: "text-gold-soft", count: s!.pending_hitl_count, important: true });
  if (needsReview > 0) notes.push({ icon: ShieldQuestion, title: "Products need review", detail: `${needsReview} couldn't be auto-confirmed`, to: "/needs-review", tone: "text-warn", count: needsReview, important: true });
  if (enriching > 0) notes.push({ icon: Sparkles, title: "Enrichment in progress", detail: `${enriching} product(s) being researched`, to: "/upload", tone: "text-grape-soft", count: enriching });
  if ((s?.failed_enrichment ?? 0) > 0) notes.push({ icon: AlertTriangle, title: "Enrichment failed", detail: `${s!.failed_enrichment} product(s) failed`, to: "/catalog", tone: "text-danger", count: s!.failed_enrichment, important: true });
  if ((s?.low_stock_count ?? 0) > 0) notes.push({ icon: PackageMinus, title: "Low stock", detail: `${s!.low_stock_count} product(s) at/below reorder point`, to: "/procurement", tone: "text-warn", count: s!.low_stock_count });

  const badge = notes.filter((n) => n.important).reduce((a, n) => a + n.count, 0);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative grid h-10 w-10 place-items-center rounded-xl border border-line bg-white/[0.02] hover:bg-white/[0.06]"
        title="Notifications"
      >
        <Bell className="h-[18px] w-[18px] text-ink-soft" />
        {badge > 0 && (
          <span className="absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full bg-gold px-1 text-[10px] font-700 text-bg">{badge}</span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={{ type: "spring", stiffness: 320, damping: 26 }}
            className="card absolute right-0 top-12 z-50 w-80 overflow-hidden p-0 shadow-glow"
          >
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <span className="text-sm font-700 text-ink">Notifications</span>
              {badge > 0 && <span className="chip border-gold/30 bg-gold/10 text-gold-soft">{badge} important</span>}
            </div>
            <div className="max-h-[60vh] overflow-y-auto">
              {notes.length === 0 ? (
                <div className="flex flex-col items-center gap-2 px-4 py-10 text-center text-ink-faint">
                  <BellOff className="h-7 w-7" /><span className="text-sm">You're all caught up 🎉</span>
                </div>
              ) : notes.map((n, i) => (
                <button key={i} onClick={() => { setOpen(false); navigate(n.to); }}
                  className="flex w-full items-start gap-3 border-b border-line px-4 py-3 text-left transition-colors hover:bg-white/[0.04]">
                  <div className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white/[0.04] ${n.tone}`}><n.icon className="h-4 w-4" /></div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-600 text-ink">{n.title}</div>
                    <div className="text-xs text-ink-faint">{n.detail}</div>
                  </div>
                  {n.important && <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-gold" />}
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
