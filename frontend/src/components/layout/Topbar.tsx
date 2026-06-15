// Feature: Layout — top bar (search, tenant, HITL bell, user)
import { useQuery } from "@tanstack/react-query";
import { Bell, LogOut, Search } from "lucide-react";
import { apiGet } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { DashboardSummary } from "@/lib/types";

export function Topbar() {
  const { user, logout } = useAuth();
  const { data } = useQuery({
    queryKey: ["summary-bell"],
    queryFn: () => apiGet<DashboardSummary>("/admin/summary"),
    refetchInterval: 30_000,
  });
  const pending = data?.pending_hitl_count ?? 0;

  return (
    <header className="glass sticky top-0 z-20 flex items-center gap-4 rounded-none border-x-0 border-t-0 px-6 py-3">
      <div className="relative hidden flex-1 max-w-md md:block">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
        <input className="input pl-9" placeholder="Search products, orders, suppliers…" />
      </div>
      <div className="flex-1 md:hidden" />

      <a
        href="/approvals"
        className="relative grid h-10 w-10 place-items-center rounded-xl border border-line bg-white/[0.02] hover:bg-white/[0.06]"
        title="HITL approvals"
      >
        <Bell className="h-[18px] w-[18px] text-ink-soft" />
        {pending > 0 && (
          <span className="absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full bg-gold px-1 text-[10px] font-700 text-bg">
            {pending}
          </span>
        )}
      </a>

      <div className="flex items-center gap-3 rounded-xl border border-line bg-white/[0.02] py-1.5 pl-3 pr-1.5">
        <div className="hidden text-right sm:block">
          <div className="max-w-[160px] truncate text-sm font-600 text-ink">{user?.email ?? "—"}</div>
          <div className="text-[11px] uppercase tracking-wider text-ink-faint">{user?.role ?? ""}</div>
        </div>
        <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-grape to-gold font-700 text-bg">
          {(user?.email ?? "M")[0]?.toUpperCase()}
        </div>
        <button
          onClick={logout}
          title="Sign out"
          className="grid h-8 w-8 place-items-center rounded-lg text-ink-faint hover:bg-white/[0.06] hover:text-danger"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
