// Feature: Authentication & Tenant Onboarding
// Layer:   Hook
// Purpose: Auth helpers: bootstrap (/me on load), signup, login, logout.
//          operational_mode gates nav (Wholesale Only hides storefront).
// API:     POST /auth/signup, POST /auth/login, GET /auth/me

import { useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet, apiPost, setToken } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";
import type { MeResponse, OperationalMode, TokenResponse } from "@/lib/types";

export function useAuth() {
  const { user, ready, setUser, setReady } = useAuthStore();
  const navigate = useNavigate();

  const refreshMe = useCallback(async () => {
    try {
      const me = await apiGet<MeResponse>("/auth/me");
      setUser(me);
      return me;
    } catch {
      setUser(null);
      return null;
    }
  }, [setUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const tok = await apiPost<TokenResponse>("/auth/login", { email, password });
      setToken(tok.access_token);
      const me = await refreshMe();
      navigate("/");
      return me;
    },
    [navigate, refreshMe],
  );

  const signup = useCallback(
    async (company_name: string, email: string, password: string, _mode: OperationalMode) => {
      const tok = await apiPost<TokenResponse>("/auth/signup", { company_name, email, password });
      setToken(tok.access_token);
      const me = await refreshMe();
      navigate("/");
      return me;
    },
    [navigate, refreshMe],
  );

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    navigate("/login");
  }, [navigate, setUser]);

  return { user, ready, setReady, refreshMe, login, signup, logout };
}

/** Runs once at app root: resolve session from an existing token. */
export function useBootstrapAuth() {
  const { setUser, setReady, ready } = useAuthStore();
  useEffect(() => {
    let active = true;
    (async () => {
      if (!sessionStorage.getItem("access_token")) {
        if (active) setReady(true);
        return;
      }
      try {
        const me = await apiGet<MeResponse>("/auth/me");
        if (active) setUser(me);
      } catch {
        if (active) setUser(null);
      } finally {
        if (active) setReady(true);
      }
    })();
    return () => {
      active = false;
    };
  }, [setUser, setReady]);
  return ready;
}
