import { Pill } from "@/components/ui/Pill";
import { Empty } from "@/components/ui/Empty";
import type { ReviewStatus } from "@/lib/types";

export function EvaluationSection({
  title,
  content,
  status,
}: {
  title: string | null;
  content: string | null;
  status: ReviewStatus;
}) {
  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <span className="text-[13.5px] font-semibold text-ink">{title ?? "No heading detected"}</span>
        <Pill tone={status === "APPROVED" ? "ok" : "warn"} mono>
          {status.toLowerCase()}
        </Pill>
      </div>
      {content ? (
        <pre className="m-0 font-mono text-[12px] leading-[1.6] whitespace-pre-wrap text-ink-soft">{content}</pre>
      ) : (
        <Empty>No content extracted for this section.</Empty>
      )}
    </div>
  );
}
