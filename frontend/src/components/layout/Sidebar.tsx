// Feature: Layout — collapsible sectioned navigation
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, CheckSquare, Boxes, ScanLine, ClipboardList,
  Store, Banknote, BrainCircuit, Settings, ChevronLeft, type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth";
import type { OperationalMode } from "@/lib/types";

interface Item {
  to: string;
  label: string;
  icon: LucideIcon;
  modes?: OperationalMode[];
}
interface Section {
  title: string;
  items: Item[];
}

const SECTIONS: Section[] = [
  { title: "Main", items: [
    { to: "/", label: "Dashboard", icon: LayoutDashboard },
    { to: "/approvals", label: "HITL Approvals", icon: CheckSquare },
  ]},
  { title: "Catalog", items: [
    { to: "/catalog", label: "Enrichment", icon: Boxes },
    { to: "/barcode", label: "Barcode Scanner", icon: ScanLine },
  ]},
  { title: "Procurement", items: [
    { to: "/procurement", label: "Order Drafts", icon: ClipboardList },
    { to: "/publishing", label: "Storefront Publishing", icon: Store, modes: ["hybrid", "retail_only"] },
  ]},
  { title: "Financial", items: [
    { to: "/dunning", label: "Dunning Engine", icon: Banknote },
  ]},
  { title: "Intelligence", items: [
    { to: "/ai-health", label: "AI Model Health", icon: BrainCircuit },
  ]},
  { title: "Settings", items: [
    { to: "/settings", label: "Settings", icon: Settings },
  ]},
];

export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const mode = useAuthStore((s) => s.user?.operational_mode);

  return (
    <aside
      className={cn(
        "glass sticky top-0 z-30 flex h-screen flex-col rounded-none border-y-0 border-l-0 transition-all duration-300",
        collapsed ? "w-[76px]" : "w-[252px]",
      )}
    >
      <div className="flex items-center gap-3 px-4 py-5">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-gold to-grape shadow-glow">
          <span className="font-800 text-bg">M</span>
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <div className="truncate font-800 tracking-tight text-ink">Mawrid</div>
            <div className="truncate text-[11px] uppercase tracking-widest text-ink-faint">
              {mode ? mode.replace("_", " ") : "Ops Platform"}
            </div>
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-2">
        {SECTIONS.map((section) => {
          const items = section.items.filter((i) => !i.modes || (mode && i.modes.includes(mode)));
          if (!items.length) return null;
          return (
            <div key={section.title}>
              {!collapsed && (
                <div className="px-3 pb-1.5 text-[10px] font-700 uppercase tracking-[0.18em] text-ink-faint">
                  {section.title}
                </div>
              )}
              <div className="space-y-1">
                {items.map((it) => (
                  <NavLink
                    key={it.to}
                    to={it.to}
                    end={it.to === "/"}
                    title={it.label}
                    className={({ isActive }) =>
                      cn(
                        "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-500 transition-all",
                        isActive
                          ? "bg-gold/15 text-gold-soft shadow-[inset_0_0_0_1px_rgba(212,163,115,0.3)]"
                          : "text-ink-soft hover:bg-white/[0.05] hover:text-ink",
                      )
                    }
                  >
                    <it.icon className="h-[18px] w-[18px] shrink-0" />
                    {!collapsed && <span className="truncate">{it.label}</span>}
                  </NavLink>
                ))}
              </div>
            </div>
          );
        })}
      </nav>

      <button
        onClick={onToggle}
        className="m-3 flex items-center justify-center gap-2 rounded-xl border border-line bg-white/[0.02] py-2.5 text-xs text-ink-soft hover:bg-white/[0.06]"
      >
        <ChevronLeft className={cn("h-4 w-4 transition-transform", collapsed && "rotate-180")} />
        {!collapsed && "Collapse"}
      </button>
    </aside>
  );
}
