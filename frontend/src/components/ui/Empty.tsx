import type { ReactNode } from "react";

export function Empty({ children }: { children: ReactNode }) {
  return <div className="p-[26px] text-center text-[13px] text-ink-faint">{children}</div>;
}
