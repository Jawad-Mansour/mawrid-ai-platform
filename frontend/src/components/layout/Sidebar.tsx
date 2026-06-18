// Feature: Layout — collapsible sectioned navigation with profile card, notifications,
//          theme toggle and sign-out. Sections expand/collapse like dropdowns.
import { useState } from "react";
import { NavLink, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  LayoutDashboard, CheckSquare, Boxes, ScanLine, ClipboardList,
  Store, Banknote, BrainCircuit, Settings, ChevronLeft, ChevronDown, Users, Sparkles, UploadCloud,
  History, ShieldQuestion, LogOut, Bell, Palette, PackageCheck, MessagesSquare, Activity, Map, GitCompare,
  Send, Mailbox, Search, Ship, ClipboardCheck, Warehouse, TrendingUp,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { apiGet } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";
import { useAuth } from "@/hooks/useAuth";
import { useProfile } from "@/stores/profile";
import { THEMES, useThemeStore } from "@/stores/theme";
import type { OperationalMode, DashboardSummary } from "@/lib/types";

interface Item { to: string; label: string; icon: LucideIcon; modes?: OperationalMode[]; badge?: number }
interface Section { title: string; items: Item[] }

export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const user = useAuthStore((s) => s.user);
  const mode = user?.operational_mode;
  const { logout } = useAuth();
  const { avatar, displayName } = useProfile();
  const { theme, setTheme } = useThemeStore();
  const cycleTheme = () => {
    const avail = THEMES.filter((t) => t.available);
    const i = avail.findIndex((t) => t.key === theme);
    setTheme(avail[(i + 1) % avail.length].key);
  };

  const { data: summary } = useQuery({ queryKey: ["summary-bell"], queryFn: () => apiGet<DashboardSummary>("/admin/summary"), refetchInterval: 20_000 });
  const importantCount = (summary?.pending_hitl_count ?? 0) + (summary?.failed_enrichment ?? 0);
  const { data: activity } = useQuery({ queryKey: ["activity-badge"], queryFn: () => apiGet<{ unread: number }>("/notifications?limit=1"), refetchInterval: 15_000 });
  const unread = activity?.unread ?? 0;

  const sections: Section[] = [
    { title: "Main", items: [
      { to: "/", label: "Dashboard", icon: LayoutDashboard },
      { to: "/approvals", label: "HITL Approvals", icon: CheckSquare },
      { to: "/notifications", label: "Notifications", icon: Bell, badge: importantCount },
      { to: "/activity", label: "Activity", icon: Activity, badge: unread },
    ]},
    { title: "Catalog", items: [
      { to: "/upload", label: "Upload Sheet", icon: UploadCloud },
      { to: "/uploads", label: "Upload History", icon: History },
      { to: "/catalog", label: "Catalogue", icon: Boxes },
      { to: "/needs-review", label: "Needs Review", icon: ShieldQuestion },
      { to: "/barcode", label: "Barcode Scanner", icon: ScanLine },
    ]},
    { title: "Procurement", items: [
      { to: "/procurement", label: "Create Order", icon: ClipboardList },
      { to: "/purchase-orders", label: "Purchase Orders", icon: PackageCheck },
      { to: "/supplier-replies", label: "Supplier Replies", icon: MessagesSquare },
    ]},
    { title: "Suppliers", items: [
      { to: "/suppliers/network", label: "Network Map", icon: Map },
      { to: "/suppliers/outreach", label: "Discover & Outreach", icon: Send },
      { to: "/suppliers/inbox", label: "Outreach Inbox", icon: Mailbox },
      { to: "/suppliers/compare", label: "Compare", icon: GitCompare },
      { to: "/suppliers", label: "Our Suppliers", icon: Users },
      { to: "/suppliers/prospects", label: "Prospects", icon: Search },
    ]},
    { title: "Inventory", items: [
      { to: "/inventory/shipments", label: "Shipments & Arrivals", icon: Ship },
      { to: "/inventory/receive", label: "Received Goods", icon: ClipboardCheck },
      { to: "/inventory/stock", label: "Stock Levels", icon: Warehouse },
      { to: "/inventory/demand", label: "Demand Signals", icon: TrendingUp },
    ]},
    { title: "Storefront", items: [
      { to: "/publishing", label: "Storefront Publishing", icon: Store, modes: ["hybrid", "retail_only"] },
    ]},
    { title: "Financial", items: [
      { to: "/dunning", label: "Supplier Dunning", icon: Banknote },
      { to: "/dunning/customer", label: "Customer Dunning", icon: Banknote },
    ]},
    { title: "Intelligence", items: [
      { to: "/intelligence", label: "AI Assistant", icon: Sparkles },
      { to: "/ai-health", label: "AI Model Health", icon: BrainCircuit },
    ]},
    { title: "Settings", items: [{ to: "/settings", label: "Settings", icon: Settings }]},
  ];

  // all sections expanded by default; clicking a header collapses it
  const [closed, setClosed] = useState<Record<string, boolean>>({});
  const toggleSection = (t: string) => setClosed((c) => ({ ...c, [t]: !c[t] }));

  const linkCls = ({ isActive }: { isActive: boolean }) =>
    cn(
      "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-500 transition-all",
      isActive ? "bg-gold/15 text-gold-soft" : "text-ink-soft hover:bg-white/[0.05] hover:text-ink",
    );

  return (
    <aside className={cn("glass sticky top-0 z-30 flex h-screen flex-col rounded-none border-y-0 border-l-0 transition-all duration-300", collapsed ? "w-[76px]" : "w-[256px]")}>
      {/* brand */}
      <div className="flex items-center gap-3 px-4 py-5">
        <img src="/icon.ico" alt="Mawrid" className="h-11 w-11 shrink-0 rounded-2xl shadow-glow" />
        {!collapsed && (
          <div className="min-w-0">
            <div className="truncate text-lg font-800 tracking-tight text-ink">Mawrid</div>
            <div className="truncate text-[10px] uppercase tracking-[0.2em] text-ink-faint">{mode ? mode.replace("_", " ") : "Ops Platform"}</div>
          </div>
        )}
      </div>

      <div className="mx-4 h-px bg-gradient-to-r from-transparent via-gold/25 to-transparent" />

      {/* nav with collapsible sections */}
      <nav className="flex-1 space-y-1.5 overflow-y-auto px-3 py-4">
        {sections.map((section) => {
          const items = section.items.filter((i) => !i.modes || (mode && i.modes.includes(mode)));
          if (!items.length) return null;
          const isOpen = !closed[section.title];
          return (
            <div key={section.title}>
              {!collapsed ? (
                <button onClick={() => toggleSection(section.title)} className="group flex w-full items-center justify-between rounded-lg px-3 py-1.5 text-[10px] font-700 uppercase tracking-[0.18em] text-ink-faint transition-colors hover:bg-white/[0.04] hover:text-ink-soft">
                  <span>{section.title}</span>
                  <span className="grid h-4 w-4 place-items-center rounded-md border border-line text-ink-soft transition-all group-hover:border-gold/50 group-hover:bg-gold/10 group-hover:text-gold-soft">
                    <ChevronDown className={cn("h-2.5 w-2.5 transition-transform", !isOpen && "-rotate-90")} />
                  </span>
                </button>
              ) : <div className="my-1 h-px bg-line" />}
              <AnimatePresence initial={false}>
                {(isOpen || collapsed) && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="space-y-1 overflow-hidden">
                    {items.map((it) => (
                      <NavLink key={it.to} to={it.to} end={it.to === "/"} title={it.label} className={linkCls}>
                        {({ isActive }) => (
                          <>
                            {isActive && <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-gold shadow-glow" />}
                            <it.icon className={cn("h-[18px] w-[18px] shrink-0 transition-all", isActive ? "drop-shadow-[0_0_8px_currentColor]" : "group-hover:drop-shadow-[0_0_6px_currentColor]")} />
                            {!collapsed && <span className="flex-1 truncate">{it.label}</span>}
                            {!!it.badge && it.badge > 0 && (
                              <span className={cn("grid h-5 min-w-5 place-items-center rounded-full bg-gold px-1 text-[10px] font-700 text-bg", collapsed && "absolute right-1 top-1")}>{it.badge}</span>
                            )}
                          </>
                        )}
                      </NavLink>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </nav>

      {/* footer: profile card + theme + sign out + collapse */}
      <div className="space-y-2 border-t border-line p-3">
        <Link to="/profile" className={cn("flex items-center gap-2.5 rounded-xl border border-line bg-white/[0.02] p-2 transition-colors hover:border-gold/30 hover:bg-white/[0.05]", collapsed && "justify-center")} title="Profile">
          <div className="grid h-9 w-9 shrink-0 place-items-center overflow-hidden rounded-lg bg-gradient-to-br from-grape to-gold text-sm font-800 text-bg">
            {avatar ? <img src={avatar} alt="" className="h-full w-full object-cover" /> : (displayName || user?.email || "M")[0]?.toUpperCase()}
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-700 text-ink">{displayName || user?.email || "—"}</div>
              <div className="text-[10px] uppercase tracking-wider text-ink-faint">{user?.role ?? ""}</div>
            </div>
          )}
        </Link>

        <div className={cn("flex gap-2", collapsed && "flex-col")}>
          <button onClick={cycleTheme} title="Switch theme" className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-line bg-white/[0.02] py-2 text-xs text-ink-soft hover:bg-white/[0.06]">
            <Palette className="h-4 w-4" />{!collapsed && "Theme"}
          </button>
          <button onClick={logout} title="Sign out" className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-danger/30 bg-danger/5 py-2 text-xs text-danger hover:bg-danger/15">
            <LogOut className="h-4 w-4" />{!collapsed && "Sign out"}
          </button>
        </div>

        <button onClick={onToggle} className="flex w-full items-center justify-center gap-2 rounded-xl border border-line bg-white/[0.02] py-2 text-xs text-ink-soft hover:bg-white/[0.06]">
          <ChevronLeft className={cn("h-4 w-4 transition-transform", collapsed && "rotate-180")} />{!collapsed && "Collapse"}
        </button>
      </div>
    </aside>
  );
}
