// Feature: Authentication
// Layer:   Store
// Purpose: Zustand auth store. Access token lives in sessionStorage (api.ts);
//          this store holds the resolved user/tenant/mode + bootstrap state.

import { create } from "zustand";
import type { MeResponse } from "@/lib/types";

interface AuthStore {
  user: MeResponse | null;
  ready: boolean; // true once the initial /me check has completed
  loggingOut: boolean; // drives the full-screen sign-out animation
  setUser: (user: MeResponse | null) => void;
  setReady: (ready: boolean) => void;
  setLoggingOut: (v: boolean) => void;
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  ready: false,
  loggingOut: false,
  setUser: (user) => set({ user }),
  setReady: (ready) => set({ ready }),
  setLoggingOut: (loggingOut) => set({ loggingOut }),
}));
