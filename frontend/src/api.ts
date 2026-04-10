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

/** Turn FastAPI `{"detail": ...}` JSON into a readable message for the UI. */
export function parseFastApiErrorDetail(body: string): string {
  const raw = body?.trim();
  if (!raw) return "";
  try {
    const j = JSON.parse(raw) as { detail?: unknown };
    const d = j.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      return d
        .map((x) => {
          if (x && typeof x === "object" && "msg" in x) return String((x as { msg: string }).msg);
          return JSON.stringify(x);
        })
        .join("; ");
    }
    if (d != null && typeof d === "object") return JSON.stringify(d);
  } catch {
    /* not JSON */
  }
  return raw;
}

/** Same origin prefix as `api()` (e.g. `/api` in Vite dev, `` in prod). Use for FormData fetch. */
export function apiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${BASE}${normalized}`;
}

export type Role = "worker" | "ta" | "client" | "admin";

function roleFromToken(token: string | null): Role | null {
  if (!token) return null;
  try {
    const parts = token.split(".");
    if (parts.length < 2) return null;
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    const payload = JSON.parse(atob(padded)) as { role?: unknown };
    const role = payload.role;
    if (role === "worker" || role === "ta" || role === "client" || role === "admin") {
      return role;
    }
    return null;
  } catch {
    return null;
  }
}

export function getToken(): string | null {
  return localStorage.getItem("mci_token");
}

export function setToken(t: string | null) {
  if (t) localStorage.setItem("mci_token", t);
  else localStorage.removeItem("mci_token");
}

export function getRole(): Role | null {
  const tokenRole = roleFromToken(getToken());
  if (tokenRole) {
    localStorage.setItem("mci_role", tokenRole);
    return tokenRole;
  }
  const r = localStorage.getItem("mci_role");
  if (r === "worker" || r === "ta" || r === "client" || r === "admin") return r;
  return null;
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
      // Authenticated JSON APIs must not reuse cached GET bodies after mutations (e.g. TA worker directory).
      cache: init.cache ?? "no-store",
    });

  let res = await doFetch(BASE);
  // Fallback: if /api proxy is unavailable in current runtime,
  // retry same-origin paths without prefix (Vite dev or custom hosting).
  if (res.status === 404 && BASE === "/api") {
    res = await doFetch("");
  }

  if (!res.ok) {
    if (res.status === 401) {
      clearSession();
      if (typeof window !== "undefined" && window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
    }
    const text = await res.text();
    throw new Error(parseFastApiErrorDetail(text) || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
