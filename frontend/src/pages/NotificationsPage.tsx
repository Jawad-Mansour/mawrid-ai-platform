// Feature: Notifications center — important (act now) vs informational.
// API:     GET /admin/summary · GET /catalog/products
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  CheckSquare, AlertTriangle, ShieldQuestion, Sparkles, PackageMinus, BellOff, ChevronRight,
} from "lucide-react";
import { apiGet } from "@/lib/api";
import { Card, SectionTitle } from "@/components/ui";
import type { DashboardSummary, Product } from "@/lib/types";

interface Note { icon: typeof CheckSquare; title: string; detail: string; to: string; tone: string }

function asProducts(d: unknown): Product[] {
  if (Array.isArray(d)) return d as Product[];
  if (d && typeof d === "object" && Array.isArray((d as any).products)) return (d as any).products;
  return [];
}

export function NotificationsPage() {
  const navigate = useNavigate();
  const summary = useQuery({ queryKey: ["summary-bell"], queryFn: () => apiGet<DashboardSummary>("/admin/summary"), refetchInterval: 15_000 });
  const products = useQuery({ queryKey: ["catalog"], queryFn: () => apiGet<unknown>("/catalog/products?limit=300"), refetchInterval: 10_000 });

  const s = summary.data;
  const prods = asProducts(products.data);
  const needsReview = prods.filter((p) => p.enrichment_status === "needs_review").length;
  const enriching = prods.filter((p) => p.enrichment_status === "pending").length;

  const important: Note[] = [];
  if ((s?.pending_hitl_count ?? 0) > 0) important.push({ icon: CheckSquare, title: "HITL approvals waiting", detail: `${s!.pending_hitl_count} action(s) need your approval before anything is sent or ordered`, to: "/approvals", tone: "text-gold-soft" });
  if ((s?.failed_enrichment ?? 0) > 0) important.push({ icon: AlertTriangle, title: "Enrichment failed", detail: `${s!.failed_enrichment} product(s) failed and need attention`, to: "/catalog", tone: "text-danger" });
  // Dunning + container tracking notifications will be added here later.

  const info: Note[] = [];
  if (enriching > 0) info.push({ icon: Sparkles, title: "Enrichment in progress", detail: `${enriching} product(s) being researched one-by-one`, to: "/upload", tone: "text-grape-soft" });
  if (needsReview > 0) info.push({ icon: ShieldQuestion, title: "Products awaiting review", detail: `${needsReview} couldn't be auto-confirmed — review or edit them`, to: "/needs-review", tone: "text-warn" });
  if ((s?.low_stock_count ?? 0) > 0) info.push({ icon: PackageMinus, title: "Low stock", detail: `${s!.low_stock_count} product(s) at/below their reorder point`, to: "/procurement", tone: "text-warn" });

  const row = (n: Note, i: number, important: boolean) => (
    <motion.button
      key={n.title} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}
      onClick={() => navigate(n.to)}
      className="flex w-full items-center gap-3 rounded-xl border border-line bg-white/[0.02] px-4 py-3.5 text-left transition-all hover:-translate-y-0.5 hover:border-gold/30 hover:shadow-glow"
    >
      <div className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/[0.04] ${n.tone}`}><n.icon className="h-5 w-5" /></div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-sm font-700 text-ink">{n.title}{important && <span className="h-2 w-2 rounded-full bg-gold" />}</div>
        <div className="text-xs text-ink-soft">{n.detail}</div>
      </div>
      <ChevronRight className="h-4 w-4 shrink-0 text-ink-faint" />
    </motion.button>
  );

  const empty = important.length === 0 && info.length === 0;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <SectionTitle title="Notifications" subtitle="Everything that needs your attention — separated by urgency." />

      {empty ? (
        <Card>
          <div className="flex flex-col items-center gap-3 py-14 text-center text-ink-faint">
            <BellOff className="h-9 w-9" />
            <div className="text-base font-700 text-ink">You're all caught up 🎉</div>
            <div className="text-sm">No approvals, reviews, or alerts right now.</div>
          </div>
        </Card>
      ) : (
        <>
          <div>
            <div className="mb-2 flex items-center gap-2 text-xs font-700 uppercase tracking-wider text-gold-soft">
              <span className="h-2 w-2 rounded-full bg-gold" /> Important · act now
            </div>
            <div className="space-y-2">
              {important.length ? important.map((n, i) => row(n, i, true)) : <p className="rounded-xl border border-dashed border-line px-4 py-6 text-center text-sm text-ink-faint">Nothing urgent.</p>}
            </div>
          </div>
          <div>
            <div className="mb-2 flex items-center gap-2 text-xs font-700 uppercase tracking-wider text-ink-soft">
              <span className="h-2 w-2 rounded-full bg-ink-faint" /> Informational
            </div>
            <div className="space-y-2">
              {info.length ? info.map((n, i) => row(n, i, false)) : <p className="rounded-xl border border-dashed border-line px-4 py-6 text-center text-sm text-ink-faint">Nothing here.</p>}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
