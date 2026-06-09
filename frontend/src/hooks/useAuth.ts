// Feature: Authentication & Tenant Onboarding
// Layer:   Hook
// Purpose: Auth state management. Returns current user, tenant, operational_mode,
//          and login/logout helpers. Reads JWT from httpOnly cookie.
//          operational_mode gates UI: Wholesale Only hides storefront routes.
// API:     GET /api/v1/auth/me, POST /api/v1/auth/refresh

export function useAuth() {
  return {
    user: null,
    tenant: null,
    operationalMode: null,
    isLoading: true,
    login: async () => {},
    logout: async () => {},
  };
}
