// Feature: Supplier & Factory Network — shared client state (region, category
//          filters, and the comparison selection carried across pages).
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface NetworkStore {
  region: string;
  selected: string[]; // pin ids chosen for comparison
  setRegion: (r: string) => void;
  toggle: (id: string) => void;
  clear: () => void;
  has: (id: string) => boolean;
}

export const useNetwork = create<NetworkStore>()(
  persist(
    (set, get) => ({
      region: "europe",
      selected: [],
      setRegion: (r) => set({ region: r }),
      toggle: (id) =>
        set((s) => ({ selected: s.selected.includes(id) ? s.selected.filter((x) => x !== id) : [...s.selected, id] })),
      clear: () => set({ selected: [] }),
      has: (id) => get().selected.includes(id),
    }),
    { name: "mawrid-network" },
  ),
);

// stable colour per category (used by map markers + legend + cards)
const PALETTE = ["#d4a373", "#9b6dff", "#3bb273", "#e07a5f", "#3a86ff", "#f4a261", "#ef476f", "#06d6a0", "#8338ec", "#ffbe0b"];
export function colorForCategory(category: string, categories: string[]): string {
  const i = Math.max(0, categories.indexOf(category));
  return PALETTE[i % PALETTE.length];
}
