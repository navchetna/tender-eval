import type { Seg } from "@/lib/stageStyles";
import { isFullyApproved } from "@/lib/projectStage";
import type { EvaluationRecord, ProjectFileRecord } from "@/lib/types";

// Same 5-stage ladder as the project-level track (see lib/projectStage.ts), applied to a single
// file. "Aligned" for one file means: this file's own sections are approved, AND the file it's
// compared against (tender <-> bid) is also approved — passed in by the caller as
// `alignmentReady`, since that depends on the *other* side's evaluation, not this file's own.
export function computeFileSegments(file: ProjectFileRecord, evaluation: EvaluationRecord | null, alignmentReady: boolean): Seg[] {
  const segs: Seg[] = Array(5).fill("todo");
  segs[0] = "done"; // Received

  if (file.processing_status === "PARSE_FAILED") {
    segs[1] = "failed";
    return segs;
  }
  if (file.processing_status !== "PARSED") {
    segs[1] = "active";
    return segs;
  }
  segs[1] = "done"; // Parsed

  if (!evaluation) {
    segs[2] = "active";
    return segs;
  }
  segs[2] = "done"; // Sections

  if (!isFullyApproved(evaluation)) {
    segs[3] = "active";
    return segs;
  }
  segs[3] = "done"; // Clauses

  segs[4] = alignmentReady ? "done" : "active";
  return segs;
}
