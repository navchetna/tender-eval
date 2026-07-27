"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { getPendingReviewCount } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

const PENDING_COUNT_POLL_MS = 20000;

type PendingReviewCountContextValue = {
  count: number;
  refresh: () => void;
};

// Owns the sidebar's "pending review" badge count in one place so any page that submits a
// review decision can refresh it immediately, instead of the badge sitting stale until the
// next poll (see Sidebar.tsx, which just reads `count` from here).
const PendingReviewCountContext = createContext<PendingReviewCountContextValue>({ count: 0, refresh: () => {} });

export function PendingReviewCountProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [count, setCount] = useState(0);

  const refresh = useCallback(() => {
    if (!user) return;
    getPendingReviewCount()
      .then(({ count }) => setCount(count))
      .catch(() => {});
  }, [user]);

  useEffect(() => {
    if (!user) return;
    refresh();
    const id = setInterval(refresh, PENDING_COUNT_POLL_MS);
    return () => clearInterval(id);
  }, [user, refresh]);

  return <PendingReviewCountContext.Provider value={{ count, refresh }}>{children}</PendingReviewCountContext.Provider>;
}

export function usePendingReviewCount() {
  return useContext(PendingReviewCountContext);
}
