import type { ReactNode } from "react";
import type { Tone } from "@/lib/types";
import { toneClasses } from "@/lib/tone";

export function Pill({ tone = "none", children, mono }: { tone?: Tone; children: ReactNode; mono?: boolean }) {
  const c = toneClasses[tone];
  return (
    <span
      className={`inline-flex items-center gap-[5px] rounded-full px-[9px] py-[2px] text-[11.5px] font-medium whitespace-nowrap ${c.bg} ${c.fg} ${mono ? "font-mono" : "font-sans"}`}
    >
      {children}
    </span>
  );
}
