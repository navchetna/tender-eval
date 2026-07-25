import type { ReactNode } from "react";

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="mb-[9px] text-[11px] font-semibold text-ink-faint uppercase tracking-[0.5px]">
      {children}
    </div>
  );
}
