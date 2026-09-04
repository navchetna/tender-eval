"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { pollGmail } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/ToastProvider";
import type { IngestionResult } from "@/lib/types";

// Heavier than the pending-count poll: every tick is a real Gmail API query, and a tick that
// finds mail also uploads to Drive. 30s keeps a demo feeling live without hammering either API.
const GMAIL_POLL_MS = 30000;
const INGEST_TOAST_MS = 5000;
// A failing poll can still take ~40s (attachments are downloaded before the failure), so
// retrying every tick would keep the backend permanently busy. Back off instead.
const BACKOFF_MAX_MS = 300000;

type GmailWatchContextValue = {
  /** Bumped once per poll that ingested something new — pages watch it to refetch. */
  ingestSignal: number;
  /** Documents ingested by the most recent non-empty poll. */
  lastIngest: IngestionResult[] | null;
};

const GmailWatchContext = createContext<GmailWatchContextValue>({ ingestSignal: 0, lastIngest: null });

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

/** "2 new bids for ACME-01 — processing started" */
export function describeIngest(results: IngestionResult[]): string {
  const files = results.flatMap((r) => r.files);
  const bids = files.filter((f) => f.file_type === "BID").length;
  const tenders = files.filter((f) => f.file_type === "TENDER").length;

  const parts: string[] = [];
  if (tenders) parts.push(plural(tenders, "new tender"));
  if (bids) parts.push(plural(bids, "new bid"));
  // Files whose name matched neither "tender" nor "bid" still land as UNKNOWN.
  if (!parts.length) parts.push(plural(files.length, "new document"));

  const codes = Array.from(new Set(results.map((r) => r.context.project_code)));
  const scope = codes.length === 1 ? ` for ${codes[0]}` : codes.length > 1 ? ` across ${plural(codes.length, "project")}` : "";

  return `${parts.join(" + ")}${scope} — processing started`;
}

/**
 * Watches Gmail for new tender/bid submissions and surfaces them as a toast.
 *
 * The backend has no Gmail poller of its own (only parse/detect run on a timer), so discovery
 * has to be driven from here. Polling is admin-only because /ingestion/poll-gmail is
 * require_admin — a reviewer session would just collect 403s.
 */
export function GmailWatchProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const toast = useToast();
  const [ingestSignal, setIngestSignal] = useState(0);
  const [lastIngest, setLastIngest] = useState<IngestionResult[] | null>(null);
  // A tick that finds mail can outlast the interval (Drive uploads), so skip overlapping runs.
  const inFlight = useRef(false);
  const failures = useRef(0);
  const nextAllowedAt = useRef(0);

  const tick = useCallback(async () => {
    if (inFlight.current || Date.now() < nextAllowedAt.current) return;
    inFlight.current = true;
    try {
      const results = await pollGmail();
      failures.current = 0;
      nextAllowedAt.current = 0;
      if (results.length > 0) {
        setLastIngest(results);
        setIngestSignal((n) => n + 1);
        toast(describeIngest(results), { variant: "info", duration: INGEST_TOAST_MS });
      }
    } catch {
      // Gmail not authorized yet, backend restarting, transient network — or a persistent
      // server-side error. Either way, widen the gap before trying again.
      failures.current += 1;
      nextAllowedAt.current = Date.now() + Math.min(GMAIL_POLL_MS * 2 ** failures.current, BACKOFF_MAX_MS);
    } finally {
      inFlight.current = false;
    }
  }, [toast]);

  useEffect(() => {
    if (user?.role !== "ADMIN") return;
    const id = setInterval(tick, GMAIL_POLL_MS);
    return () => clearInterval(id);
  }, [user, tick]);

  return <GmailWatchContext.Provider value={{ ingestSignal, lastIngest }}>{children}</GmailWatchContext.Provider>;
}

export function useGmailWatch() {
  return useContext(GmailWatchContext);
}
