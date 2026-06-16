// Feature: Theming — selectable color themes (CSS-variable driven)
import { useEffect } from "react";
import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface ThemeDef {
  key: string;
  name: string;
  available: boolean;
  swatch: [string, string]; // gradient preview
  hint: string;
}

export const THEMES: ThemeDef[] = [
  { key: "gold", name: "Desert Gold", available: true, swatch: ["#D4A373", "#9D4EDD"], hint: "Warm earth tones — the signature look." },
  { key: "blue", name: "Royal Blue", available: true, swatch: ["#548EFF", "#8264FF"], hint: "Cool, focused, fintech-grade." },
  { key: "emerald", name: "Forest", available: true, swatch: ["#34A86E", "#6ECD98"], hint: "Calm, natural, high-trust green." },
  { key: "light", name: "Daylight", available: true, swatch: ["#2563EB", "#E5E9F2"], hint: "Bright workspace for daytime." },
];

interface ThemeStore {
  theme: string;
  setTheme: (t: string) => void;
}

export const useThemeStore = create<ThemeStore>()(
  persist(
    (set) => ({
      theme: "gold",
      setTheme: (theme) => set({ theme }),
    }),
    { name: "mawrid-theme" },
  ),
);

/** Apply the selected theme to <html data-theme>. Call once at app root. */
export function useApplyTheme() {
  const theme = useThemeStore((s) => s.theme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
}
