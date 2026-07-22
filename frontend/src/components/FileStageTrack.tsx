import { LABEL_CLASS, SEG_BG, STAGE_LADDER } from "@/lib/stageStyles";
import { computeFileSegments } from "@/lib/fileStage";
import type { EvaluationRecord, ProjectFileRecord } from "@/lib/types";

export function FileStageTrack({
  file,
  evaluation,
  alignmentReady,
  compact,
}: {
  file: ProjectFileRecord;
  evaluation: EvaluationRecord | null;
  alignmentReady: boolean;
  compact?: boolean;
}) {
  const segs = computeFileSegments(file, evaluation, alignmentReady);
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
