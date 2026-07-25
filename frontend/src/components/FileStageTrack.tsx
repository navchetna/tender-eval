import { useState } from "react";
import { Loader2 } from "lucide-react";
import { ACTIVE_LABEL, LABEL_CLASS, SEG_BG, STAGE_LADDER } from "@/lib/stageStyles";
import { computeFileSegments } from "@/lib/fileStage";
import { ApiError, getFileStageDetail, getPipelineSchemas, retryFileStage } from "@/lib/api";
import type { EvaluationRecord, FileStageDetail, PipelineSchema, PipelineStage, ProjectFileRecord } from "@/lib/types";
import { StageDetailPopover } from "@/components/StageDetailPopover";
import { useToast } from "@/components/ToastProvider";

const PIPELINE_STAGES: PipelineStage[] = ["received", "parsed", "sections", "clauses"];

const ALIGNED_NOTE: Record<"todo" | "active" | "done" | "failed", string> = {
  todo: "Not reached yet — this file's own technical/price sections must be approved first.",
  active: "Waiting on the other side (tender ↔ bid) to be fully approved too.",
  done: "Ready — both sides are approved and aligned for comparison.",
  failed: "Not reached yet — this file's own technical/price sections must be approved first.",
};

export function FileStageTrack({
  file,
  evaluation,
  alignmentReady,
  compact,
  onRetried,
}: {
  file: ProjectFileRecord;
  evaluation: EvaluationRecord | null;
  alignmentReady: boolean;
  compact?: boolean;
  onRetried?: () => void;
}) {
  const toast = useToast();
  const segs = computeFileSegments(file, evaluation, alignmentReady);
  const [openIdx, setOpenIdx] = useState<number | null>(null);
  const [schema, setSchema] = useState<PipelineSchema | null>(null);
  const [detail, setDetail] = useState<FileStageDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [retrying, setRetrying] = useState(false);

  const fetchDetail = () => {
    setLoading(true);
    return Promise.all([getPipelineSchemas(), getFileStageDetail(file.project_id, file.file_id)])
      .then(([s, d]) => {
        setSchema(s);
        setDetail(d);
      })
      .finally(() => setLoading(false));
  };

  const onSegmentClick = (i: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (compact) return;
    if (openIdx === i) {
      setOpenIdx(null);
      return;
    }
    setOpenIdx(i);
    if (i < 4 && !detail && !loading) fetchDetail();
  };

  // Only the two automated, potentially-transient stages (parsing, section detection) get a
  // retry action — "Clauses" is a human review decision (redo via the review controls, not a
  // retry), and "Received"/"Aligned" have no persisted failure state of their own to retry.
  const onRetry = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setRetrying(true);
    try {
      await retryFileStage(file.project_id, file.file_id);
      await fetchDetail();
      onRetried?.();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Retry failed");
    } finally {
      setRetrying(false);
    }
  };

  const hoverTitle = (i: number): string => {
    const status = segs[i];
    if (i === 4) return ALIGNED_NOTE[status];
    if (status === "failed") {
      const error = i === 1 ? file.parse_error : i === 2 ? file.detection_error : null;
      return error ? `Failed: ${error}` : "Failed";
    }
    return `${STAGE_LADDER[i]}: ${status}`;
  };

  return (
    <div>
      <div className="flex items-center gap-[3px]">
        {segs.map((st, i) => (
          <button
            key={i}
            type="button"
            title={hoverTitle(i)}
            onClick={(e) => onSegmentClick(i, e)}
            className={`h-[5px] flex-1 cursor-pointer rounded-[3px] border-none p-0 transition-transform duration-150 ease-out hover:scale-y-[2] hover:brightness-110 ${SEG_BG[st]} ${st === "todo" ? "opacity-55" : "opacity-100"} ${st === "active" ? "animate-pulse" : ""}`}
          />
        ))}
      </div>
      {!compact && (
        <div className="mt-[5px] flex justify-between">
          {STAGE_LADDER.map((l, i) => (
            <span key={i} className={`flex items-center gap-[3px] text-[9px] tracking-[0.1px] ${LABEL_CLASS[segs[i]]}`}>
              {segs[i] === "active" && <Loader2 size={9} className="animate-spin" />}
              {segs[i] === "active" ? ACTIVE_LABEL[i] : l}
            </span>
          ))}
        </div>
      )}
      {openIdx !== null && (
        <StageDetailPopover
          label={STAGE_LADDER[openIdx]}
          status={segs[openIdx]}
          stage={openIdx < 4 ? PIPELINE_STAGES[openIdx] : "aligned"}
          schema={openIdx < 4 ? schema?.[PIPELINE_STAGES[openIdx]] ?? null : null}
          detail={openIdx < 4 ? detail?.[PIPELINE_STAGES[openIdx]] ?? null : null}
          loading={loading}
          alignedNote={openIdx === 4 ? ALIGNED_NOTE[segs[4]] : undefined}
          canRetry={(openIdx === 1 || openIdx === 2) && segs[openIdx] === "failed"}
          retrying={retrying}
          onRetry={onRetry}
        />
      )}
    </div>
  );
}
