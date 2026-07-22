import { LABEL_CLASS, SEG_BG, STAGE_LADDER } from "@/lib/stageStyles";
import { computeProjectSegments } from "@/lib/projectStage";
import type { EvaluationRecord, ProjectFileRecord } from "@/lib/types";

export function ProjectStageTrack({
  currentFiles,
  tenderEvals,
  bidEvals,
  compact,
}: {
  currentFiles: ProjectFileRecord[];
  tenderEvals: EvaluationRecord[];
  bidEvals: EvaluationRecord[];
  compact?: boolean;
}) {
  const segs = computeProjectSegments(currentFiles, tenderEvals, bidEvals);
  return (
    <div>
      <div className="flex items-center gap-[3px]">
        {segs.map((st, i) => (
          <div key={i} className={`h-[5px] flex-1 rounded-[3px] ${SEG_BG[st]} ${st === "todo" ? "opacity-55" : "opacity-100"}`} />
        ))}
      </div>
      {!compact && (
        <div className="mt-[5px] flex justify-between">
          {STAGE_LADDER.map((l, i) => (
            <span key={i} className={`text-[9px] tracking-[0.1px] ${LABEL_CLASS[segs[i]]}`}>
              {l}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
