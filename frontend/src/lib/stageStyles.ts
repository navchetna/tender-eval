// Shared 5-stage pipeline ladder used everywhere progress is shown (Projects tiles, Workspace
// per-file rows, Employees workload summary) — kept in one place so the definition of each
// stage stays consistent across views.
export const STAGE_LADDER = ["Received", "Parsed", "Sections", "Clauses", "Aligned"];

export type Seg = "done" | "active" | "failed" | "todo";

export const SEG_BG: Record<Seg, string> = {
  done: "bg-accent",
  active: "bg-accent",
  failed: "bg-bad-dot",
  todo: "bg-line-strong",
};

export const LABEL_CLASS: Record<Seg, string> = {
  done: "text-ink-soft",
  active: "text-ink-soft font-semibold",
  failed: "text-bad-fg",
  todo: "text-ink-faint",
};
