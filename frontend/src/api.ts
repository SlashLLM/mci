/**
 * - Vite dev: `/api` (proxy to backend).
 * - Production build in Docker: same origin, empty base (`VITE_API_BASE` unset or "").
 * - Absolute `VITE_API_BASE` for split hosting.
 *
 * Must use direct `import.meta.env.*` access so Vite can replace them at build time;
 * `const m = import.meta; m.env.X` leaves `m.env` undefined in production.
 */
function apiBase(): string {
  const raw = import.meta.env.VITE_API_BASE;
  if (raw === "") return "";
  if (raw != null && raw !== "/") {
    return raw.replace(/\/$/, "");
  }
  if (import.meta.env.DEV) return "/api";
  return "";
}

const BASE = apiBase();

/** Same origin prefix as `api()` (e.g. `/api` in Vite dev, `` in prod). Use for FormData fetch. */
export function apiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${BASE}${normalized}`;
}

export type Role = "worker" | "ta" | "client" | "admin";

export function getToken(): string | null {
  return localStorage.getItem("mci_token");
}

export function setToken(t: string | null) {
  if (t) localStorage.setItem("mci_token", t);
  else localStorage.removeItem("mci_token");
}

export function getRole(): Role | null {
  const r = localStorage.getItem("mci_role") as Role | null;
  return r;
}

export function setSession(token: string, role: string) {
  setToken(token);
  localStorage.setItem("mci_role", role);
}

export function clearSession() {
  setToken(null);
  localStorage.removeItem("mci_role");
}

export async function api<T>(
  path: string,
  init: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (init.json !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  const doFetch = (base: string) =>
    fetch(`${base}${path}`, {
      ...init,
      headers,
      body: init.json !== undefined ? JSON.stringify(init.json) : init.body,
    });

  let res = await doFetch(BASE);
  // Fallback: if /api proxy is unavailable in current runtime,
  // retry same-origin paths without prefix (Vite dev or custom hosting).
  if (res.status === 404 && BASE === "/api") {
    res = await doFetch("");
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
