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
  qty: number;
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
