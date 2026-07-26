"use client";

import { Mail, Waypoints, Target, ListChecks, Shuffle, Grid2x2, Check } from "lucide-react";
import type { LucideIcon } from "lucide-react";

type StageDef = {
  icon: LucideIcon;
  label: string;
  caption: string;
  agent?: boolean;
  humanNote?: string;
};

// Static description of the end-to-end agentic pipeline (ingest → matrix). Rendered on every
// authenticated page so reviewers always see where the automated agents sit relative to the
// one manual checkpoint (tender canonicalization), reinforcing that everything else is autonomous.
const STAGES: StageDef[] = [
  { icon: Mail, label: "Ingest & parse", caption: "Gmail → Drive → parser" },
  { icon: Waypoints, label: "Classify", caption: "tender vs bid · versions", agent: true },
  {
    icon: Target,
    label: "Locate sections",
    caption: "Technical / Price",
    agent: true,
    humanNote: "human validates",
  },
  { icon: ListChecks, label: "Extract clauses", caption: "per category", agent: true },
  { icon: Shuffle, label: "Align", caption: "semantic tender ⇄ bid", agent: true },
  { icon: Grid2x2, label: "Compliance matrix", caption: "Excel · per bidder" },
];

export function PipelineRibbon({ activeStage = null }: { activeStage?: number | null }) {
  return (
    <div className="flex shrink-0 flex-col border-b-[0.5px] border-line bg-surface">
      <div className="flex items-start justify-center gap-1 overflow-x-auto px-5 py-[10px]">
      {STAGES.map((stage, i) => {
        const isActive = activeStage != null && i === activeStage;
        const isPast = activeStage != null && i < activeStage;
        return (
        <div key={stage.label} className="flex items-start">
          <div className="flex w-[104px] shrink-0 flex-col items-center text-center">
            {stage.agent ? (
              <span className="mb-[3px] inline-flex items-center rounded-full bg-info-bg px-[6px] py-[1px] text-[8.5px] font-semibold tracking-[0.4px] text-info-fg uppercase">
                Agent
              </span>
            ) : (
              <span className="mb-[3px] inline-block h-[15px]" />
            )}
            <div
              className={`flex h-[34px] w-[34px] items-center justify-center rounded-full border-[1.5px] transition-colors ${
                isActive
                  ? "border-accent bg-accent text-white shadow-[0_0_0_4px_var(--color-accent-bg)]"
                  : isPast
                    ? "border-ok-fg bg-ok-bg text-ok-fg"
                    : stage.agent
                      ? "border-info-fg bg-info-bg text-info-fg"
                      : "border-line-strong bg-surface2 text-ink-faint"
              }`}
            >
              {isPast ? <Check size={16} /> : <stage.icon size={16} />}
            </div>
            <div className={`mt-[6px] text-[11px] leading-tight font-semibold ${isActive ? "text-accent" : "text-ink"}`}>
              {stage.label}
            </div>
            <div className="text-[9.5px] leading-tight text-ink-faint">{stage.caption}</div>
            {stage.humanNote && (
              <div className="mt-[4px] flex items-center gap-[3px] text-[10.5px] font-medium text-warn-fg">
                <Check size={10} />
                {stage.humanNote}
              </div>
            )}
          </div>
          {i < STAGES.length - 1 && (
            <div className={`mt-[34px] h-[1.5px] w-6 shrink-0 self-start transition-colors ${isPast ? "bg-ok-fg" : "bg-line-strong"}`} />
          )}
        </div>
        );
      })}
      </div>
    </div>
  );
}
