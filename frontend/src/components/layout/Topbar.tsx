// Feature: Layout — top bar (search, theme, notifications, user)
import { Search, Palette } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { THEMES, useThemeStore } from "@/stores/theme";
import { Notifications } from "@/components/Notifications";

export function Topbar() {
  const { user } = useAuth();
  const { theme, setTheme } = useThemeStore();
  const cycleTheme = () => {
    const avail = THEMES.filter((t) => t.available);
    const i = avail.findIndex((t) => t.key === theme);
    setTheme(avail[(i + 1) % avail.length].key);
  };

  return (
    <header className="glass sticky top-0 z-20 flex items-center gap-4 rounded-none border-x-0 border-t-0 px-6 py-3">
      <div className="relative hidden flex-1 max-w-md md:block">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
        <input className="input pl-9" placeholder="Search products, orders, suppliers…" />
      </div>
      <div className="flex-1 md:hidden" />

      <button
        onClick={cycleTheme}
        className="grid h-10 w-10 place-items-center rounded-xl border border-line bg-white/[0.02] hover:bg-white/[0.06]"
        title="Switch theme"
      >
        <Palette className="h-[18px] w-[18px] text-ink-soft" />
      </button>

      <Notifications />

      <div className="flex items-center gap-3 rounded-xl border border-line bg-white/[0.02] py-1.5 pl-3 pr-3">
        <div className="hidden text-right sm:block">
          <div className="max-w-[160px] truncate text-sm font-600 text-ink">{user?.email ?? "—"}</div>
          <div className="text-[11px] uppercase tracking-wider text-ink-faint">{user?.role ?? ""}</div>
        </div>
        <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-grape to-gold font-700 text-bg">
          {(user?.email ?? "M")[0]?.toUpperCase()}
        </div>
      </div>
    </header>
  );
}
