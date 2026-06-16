// Feature: Notifications center — important (act now) vs informational, tabbed.
// API:     GET /admin/summary · GET /catalog/products
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  CheckSquare, AlertTriangle, ShieldQuestion, Sparkles, PackageMinus, BellOff, ChevronRight,
} from "lucide-react";
import { apiGet } from "@/lib/api";
import { cn } from "@/lib/utils";
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
  const [tab, setTab] = useState<"important" | "info">("important");
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

  const list = tab === "important" ? important : info;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <SectionTitle title="Notifications" subtitle="Everything that needs your attention — separated by urgency." />

      {/* tab toggle */}
      <div className="flex gap-1 rounded-2xl border border-line bg-white/[0.02] p-1">
        {([
          { key: "important", label: "Important", count: important.length, dot: "bg-gold" },
          { key: "info", label: "Informational", count: info.length, dot: "bg-ink-faint" },
        ] as const).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              "relative flex flex-1 items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-600 transition-all",
              tab === t.key ? "bg-gold/15 text-gold-soft shadow-[inset_0_0_0_1px_rgba(212,163,115,0.3)]" : "text-ink-soft hover:text-ink",
            )}
          >
            <span className={cn("h-2 w-2 rounded-full", t.dot)} /> {t.label}
            {t.count > 0 && <span className="grid h-5 min-w-5 place-items-center rounded-full bg-gold/20 px-1 text-[10px] font-700 text-gold-soft">{t.count}</span>}
          </button>
        ))}
      </div>

      <div className="space-y-2">
        {list.length ? list.map((n, i) => row(n, i, tab === "important")) : (
          <Card>
            <div className="flex flex-col items-center gap-3 py-12 text-center text-ink-faint">
              <BellOff className="h-9 w-9" />
              <div className="text-base font-700 text-ink">{tab === "important" ? "Nothing urgent 🎉" : "Nothing here"}</div>
              <div className="text-sm">{tab === "important" ? "No approvals or failures need you right now." : "No informational updates at the moment."}</div>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
