// Feature: All features (cross-cutting)
// Layer:   Lib / API Client
// Purpose: Axios instance with JWT Bearer attachment and automatic 401->refresh
//          retry. Base URL from VITE_API_URL env. Access token in memory/session;
//          refresh token is an httpOnly cookie set by the backend.
// API:     All /api/v1/* endpoints

import axios, { type AxiosRequestConfig } from "axios";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

export const apiClient = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
});

// localStorage so the session survives a page refresh AND new tabs (the refresh
// cookie renews it after the 15-min access-token expiry).
export function setToken(token: string | null) {
  if (token) localStorage.setItem("access_token", token);
  else localStorage.removeItem("access_token");
}
export function getToken(): string | null {
  return localStorage.getItem("access_token");
}

apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

apiClient.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    const url: string = original?.url ?? "";
    // Never try to refresh the auth calls themselves (avoids redirect loops)
    const isAuthCall = url.includes("/auth/login") || url.includes("/auth/refresh") || url.includes("/auth/signup");
    if (error.response?.status === 401 && !original._retried && !isAuthCall) {
      original._retried = true;
      try {
        const { data } = await axios.post(`${BASE_URL}/auth/refresh`, {}, { withCredentials: true });
        setToken(data.access_token);
        original.headers.Authorization = `Bearer ${data.access_token}`;
        return apiClient(original);
      } catch {
        // Clear the token and let the route guard redirect — a hard
        // window.location redirect during a background query is jarring and
        // can interrupt other in-flight requests.
        setToken(null);
      }
    }
    return Promise.reject(error);
  },
);

export async function apiGet<T>(path: string, config?: AxiosRequestConfig): Promise<T> {
  return (await apiClient.get<T>(path, config)).data;
}
export async function apiPost<T>(path: string, body?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return (await apiClient.post<T>(path, body, config)).data;
}
export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return (await apiClient.put<T>(path, body)).data;
}
export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  return (await apiClient.patch<T>(path, body)).data;
}
export async function apiDelete<T>(path: string): Promise<T> {
  return (await apiClient.delete<T>(path)).data;
}
export async function apiUpload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  return (await apiClient.post<T>(path, form, { headers: { "Content-Type": "multipart/form-data" } })).data;
}

export function apiErr(e: unknown, fallback = "Something went wrong"): string {
  if (axios.isAxiosError(e)) {
    const d = e.response?.data as { detail?: unknown } | undefined;
    if (typeof d?.detail === "string") return d.detail;
    if (Array.isArray(d?.detail)) return d.detail.map((x: any) => x.msg ?? "").join(", ") || fallback;
    return e.message || fallback;
  }
  return fallback;
}
