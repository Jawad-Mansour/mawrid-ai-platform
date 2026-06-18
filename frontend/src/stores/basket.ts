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
  document_id: string | null; // which sheet this was noted from (per-sheet orders)
  supplier_name: string | null;
  qty: number;
}

// Available comes from the backend (parsed from the sheet); fall back to scanning specs.
function readAvailable(p: Product): number | null {
  if (p.available_qty != null && p.available_qty > 0) return p.available_qty;
  const specs = p.specifications ?? {};
  for (const k of Object.keys(specs)) {
    if (/qty|quantit|stock|available|on.?hand/i.test(k)) {
      const n = parseInt(String(specs[k]).replace(/[^0-9]/g, ""), 10);
      if (!Number.isNaN(n) && n > 0) return n;
    }
  }
  return null;
}

// Clamp a requested quantity to [1, available] (available null = no cap).
function clampQty(qty: number, available: number | null): number {
  const n = Math.max(1, Math.floor(Number.isFinite(qty) ? qty : 1));
  return available != null ? Math.min(n, available) : n;
}

interface BasketStore {
  items: BasketItem[];
  add: (p: Product, documentId?: string | null) => void;
  remove: (product_id: string) => void;
  setQty: (product_id: string, qty: number) => void;
  has: (product_id: string) => boolean;
  clear: () => void;
}

export const useBasket = create<BasketStore>()(
  persist(
    (set, get) => ({
      items: [],
      add: (p, documentId) =>
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
                    document_id: documentId ?? p.document_ids?.[0] ?? null,
                    supplier_name: p.supplier_names?.[0] ?? null,
                    qty: 1,
                  },
                ],
              },
        ),
      remove: (id) => set((s) => ({ items: s.items.filter((i) => i.product_id !== id) })),
      setQty: (id, qty) =>
        set((s) => ({
          items: s.items.map((i) => (i.product_id === id ? { ...i, qty: clampQty(qty, i.available) } : i)),
        })),
      has: (id) => get().items.some((i) => i.product_id === id),
      clear: () => set({ items: [] }),
    }),
    { name: "mawrid-basket" },
  ),
);
