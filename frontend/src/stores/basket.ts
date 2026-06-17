// Feature: Procurement — "note aside" basket carried from catalog listing to the order page
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Product } from "@/lib/types";

export interface BasketItem {
  product_id: string;
  product_name: string;
  sku: string | null;
  image_url: string | null;
  price: number | null;
  currency: string | null;
  available: number | null; // max orderable, from the supplier sheet QTY
  qty: number;
}

// The sheet quantity lands in specifications under varying keys — find a number.
function readAvailable(p: Product): number | null {
  const specs = p.specifications ?? {};
  for (const k of Object.keys(specs)) {
    if (/qty|quantity/i.test(k)) {
      const n = parseInt(String(specs[k]).replace(/[^0-9]/g, ""), 10);
      if (!Number.isNaN(n) && n > 0) return n;
    }
  }
  return null;
}

interface BasketStore {
  items: BasketItem[];
  add: (p: Product) => void;
  remove: (product_id: string) => void;
  setQty: (product_id: string, qty: number) => void;
  has: (product_id: string) => boolean;
  clear: () => void;
}

export const useBasket = create<BasketStore>()(
  persist(
    (set, get) => ({
      items: [],
      add: (p) =>
        set((s) =>
          s.items.some((i) => i.product_id === p.product_id)
            ? { items: s.items.filter((i) => i.product_id !== p.product_id) } // toggle off
            : {
                items: [
                  ...s.items,
                  {
                    product_id: p.product_id,
                    product_name: p.product_name,
                    sku: p.sku,
                    image_url: p.image_url ?? null,
                    price: p.price ?? p.retail_price ?? null,
                    currency: p.currency ?? "USD",
                    available: readAvailable(p),
                    qty: 1,
                  },
                ],
              },
        ),
      remove: (id) => set((s) => ({ items: s.items.filter((i) => i.product_id !== id) })),
      setQty: (id, qty) =>
        set((s) => ({ items: s.items.map((i) => (i.product_id === id ? { ...i, qty: Math.max(1, qty) } : i)) })),
      has: (id) => get().items.some((i) => i.product_id === id),
      clear: () => set({ items: [] }),
    }),
    { name: "mawrid-basket" },
  ),
);
