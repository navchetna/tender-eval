"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { whoami, setUnauthorizedHandler } from "@/lib/api";
import { clearAuth, loadAuth, saveAuth } from "@/lib/auth-storage";
import type { CurrentUser } from "@/lib/types";

interface AuthContextValue {
  user: CurrentUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // One-time session rehydration from sessionStorage on mount — not a React-state sync.
    const stored = loadAuth();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (stored) setUser(stored.user);
    setLoading(false);
    setUnauthorizedHandler(() => {
      clearAuth();
      setUser(null);
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  const login = async (email: string, password: string) => {
    const token = btoa(`${email}:${password}`);
    const resolvedUser = await whoami(token);
    saveAuth({ token, user: resolvedUser });
    setUser(resolvedUser);
  };

  const logout = () => {
    clearAuth();
    setUser(null);
  };

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}
