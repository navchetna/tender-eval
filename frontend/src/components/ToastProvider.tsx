"use client";

import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { Check, Inbox } from "lucide-react";

export type ToastVariant = "success" | "info";

type ToastOptions = { variant?: ToastVariant; duration?: number };

// Options are optional so every existing `toast("message")` call site keeps working unchanged.
type ToastFn = (message: string, options?: ToastOptions) => void;

const DEFAULT_DURATION_MS = 2600;

const ToastContext = createContext<ToastFn | null>(null);

export function useToast(): ToastFn {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a ToastProvider");
  return ctx;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toastState, setToastState] = useState<{ message: string; variant: ToastVariant } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const toast = useCallback<ToastFn>((message, options) => {
    setToastState({ message, variant: options?.variant ?? "success" });
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setToastState(null), options?.duration ?? DEFAULT_DURATION_MS);
  }, []);

  return (
    <ToastContext.Provider value={toast}>
      {children}
      {toastState && (
        <div className="fade absolute bottom-5 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-[10px] bg-ink px-4 py-[9px] text-[13px] text-white shadow-[0_8px_24px_-8px_rgba(0,0,0,.4)]">
          {toastState.variant === "info" ? <Inbox size={14} /> : <Check size={14} />}
          {toastState.message}
        </div>
      )}
    </ToastContext.Provider>
  );
}
