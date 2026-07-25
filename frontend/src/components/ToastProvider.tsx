"use client";

import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { Check } from "lucide-react";

type ToastFn = (message: string) => void;

const ToastContext = createContext<ToastFn | null>(null);

export function useToast(): ToastFn {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a ToastProvider");
  return ctx;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const toast = useCallback<ToastFn>((m) => {
    setMessage(m);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setMessage(null), 2600);
  }, []);

  return (
    <ToastContext.Provider value={toast}>
      {children}
      {message && (
        <div className="fade absolute bottom-5 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-[10px] bg-ink px-4 py-[9px] text-[13px] text-white shadow-[0_8px_24px_-8px_rgba(0,0,0,.4)]">
          <Check size={14} />
          {message}
        </div>
      )}
    </ToastContext.Provider>
  );
}
