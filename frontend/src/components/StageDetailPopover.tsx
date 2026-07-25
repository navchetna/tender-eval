import type { Tone } from "@/lib/types";
import type { PipelineStage, StageDetail, StageSchema } from "@/lib/types";
import type { Seg } from "@/lib/stageStyles";
import { Card } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";

const SEG_TONE: Record<Seg, Tone> = { done: "ok", active: "info", failed: "bad", todo: "none" };

function JsonBlock({ label, schema, value }: { label: string; schema: Record<string, unknown> | undefined; value: Record<string, unknown> | null }) {
  return (
    <div className="flex-1 min-w-0">
      <div className="mb-[6px] text-[11px] font-semibold tracking-[0.3px] text-ink-faint uppercase">{label}</div>
      {value ? (
        <pre className="m-0 max-h-[220px] overflow-auto rounded-[9px] bg-surface2 p-[10px] font-mono text-[11px] leading-[1.5] whitespace-pre-wrap text-ink-soft">
          {JSON.stringify(value, null, 2)}
        </pre>
      ) : (
        <div className="rounded-[9px] bg-surface2 p-[10px] text-[12px] text-ink-faint">Not reached yet.</div>
      )}
      {schema && (
        <details className="mt-[6px]">
          <summary className="cursor-pointer text-[11px] text-ink-faint">Schema</summary>
          <pre className="m-0 mt-[6px] max-h-[220px] overflow-auto rounded-[9px] bg-surface2 p-[10px] font-mono text-[11px] leading-[1.5] whitespace-pre-wrap text-ink-faint">
            {JSON.stringify(schema, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}

export function StageDetailPopover({
  label,
  status,
  stage,
  schema,
  detail,
  loading,
  alignedNote,
  canRetry,
  retrying,
  onRetry,
}: {
  label: string;
  status: Seg;
  stage: PipelineStage | "aligned";
  schema: StageSchema | null;
  detail: StageDetail | null;
  loading: boolean;
  alignedNote?: string;
  canRetry?: boolean;
  retrying?: boolean;
  onRetry?: (e: React.MouseEvent) => void;
}) {
  return (
    <Card className="expand mt-[8px] overflow-hidden" onClick={undefined}>
      <div
        className="flex items-center gap-2 border-b-[0.5px] border-line bg-surface2 px-[12px] py-[8px]"
        onClick={(e) => e.stopPropagation()}
      >
        <span className="text-[12.5px] font-semibold text-ink">{label}</span>
        <Pill tone={SEG_TONE[status]} mono>
          {status}
        </Pill>
        {canRetry && (
          <button
            type="button"
            disabled={retrying}
            onClick={onRetry}
            className="btn ml-auto cursor-pointer rounded-[7px] border-[0.5px] border-line-strong bg-surface px-[10px] py-[4px] text-[11.5px] font-medium text-ink disabled:opacity-60"
          >
            {retrying ? "Retrying…" : "Retry"}
          </button>
        )}
      </div>
      <div className="p-[12px]" onClick={(e) => e.stopPropagation()}>
        {stage === "aligned" ? (
          <div className="text-[12.5px] text-ink-soft">{alignedNote}</div>
        ) : loading ? (
          <div className="text-[12.5px] text-ink-faint">Loading…</div>
        ) : (
          <>
            {detail?.error && (
              <div className="mb-[10px] rounded-[9px] bg-bad-bg px-[10px] py-[8px] text-[12px] text-bad-fg">{detail.error}</div>
            )}
            <div className="flex flex-col gap-[10px] sm:flex-row">
              <JsonBlock label="Input" schema={schema?.input} value={detail?.input ?? null} />
              <JsonBlock label="Output" schema={schema?.output} value={detail?.output ?? null} />
            </div>
          </>
        )}
      </div>
    </Card>
  );
}
