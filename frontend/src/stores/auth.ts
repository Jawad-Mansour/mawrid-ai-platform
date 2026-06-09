// Feature: Authentication
// Layer:   Store
// Purpose: Zustand store for auth state (JWT tokens, current user, tenant).
// API:     POST /auth/login, POST /auth/refresh

import { create } from "zustand"
import { persist } from "zustand/middleware"

interface AuthUser {
  userId: string
  tenantId: string
  email: string
  role: "admin" | "importer" | "consumer"
}

interface AuthStore {
  user: AuthUser | null
  accessToken: string | null
  refreshToken: string | null
  setAuth: (user: AuthUser, accessToken: string, refreshToken: string) => void
  clearAuth: () => void
  isAuthenticated: () => boolean
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      setAuth: (user, accessToken, refreshToken) =>
        set({ user, accessToken, refreshToken }),
      clearAuth: () => set({ user: null, accessToken: null, refreshToken: null }),
      isAuthenticated: () => get().accessToken !== null,
    }),
    { name: "mawrid-auth" }
  )
)
