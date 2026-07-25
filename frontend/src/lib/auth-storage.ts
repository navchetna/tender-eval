import type { CurrentUser } from "./types";

const KEY = "reconcile-auth";

export interface StoredAuth {
  token: string; // base64("email:password"), sent as the HTTP Basic Authorization header
  user: CurrentUser;
}

export function loadAuth(): StoredAuth | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredAuth;
  } catch {
    return null;
  }
}

export function saveAuth(auth: StoredAuth): void {
  window.sessionStorage.setItem(KEY, JSON.stringify(auth));
}

export function clearAuth(): void {
  window.sessionStorage.removeItem(KEY);
}
