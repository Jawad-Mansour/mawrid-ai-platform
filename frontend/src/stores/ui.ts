// Feature: All features (cross-cutting UI state)
// Layer:   Store
// Purpose: Zustand store for transient UI state (sidebar, modals, toasts).
// API:     None

import { create } from "zustand"

interface Toast {
  id: string
  message: string
  type: "success" | "error" | "info"
}

interface UIStore {
  sidebarOpen: boolean
  toasts: Toast[]
  setSidebarOpen: (open: boolean) => void
  addToast: (message: string, type: Toast["type"]) => void
  removeToast: (id: string) => void
}

export const useUIStore = create<UIStore>((set) => ({
  sidebarOpen: true,
  toasts: [],
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  addToast: (message, type) =>
    set((state) => ({
      toasts: [
        ...state.toasts,
        { id: crypto.randomUUID(), message, type },
      ],
    })),
  removeToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}))
