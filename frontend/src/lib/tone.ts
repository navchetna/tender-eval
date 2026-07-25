import type { Tone } from "./types";

export const toneClasses: Record<Tone, { bg: string; fg: string; dot: string }> = {
  ok: { bg: "bg-ok-bg", fg: "text-ok-fg", dot: "bg-ok-dot" },
  warn: { bg: "bg-warn-bg", fg: "text-warn-fg", dot: "bg-warn-dot" },
  bad: { bg: "bg-bad-bg", fg: "text-bad-fg", dot: "bg-bad-dot" },
  none: { bg: "bg-none-bg", fg: "text-none-fg", dot: "bg-none-dot" },
  info: { bg: "bg-info-bg", fg: "text-info-fg", dot: "bg-info-dot" },
};
