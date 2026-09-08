import type { Seg } from "@/lib/stageStyles";
import type { EvaluationRecord, ProjectFileRecord } from "@/lib/types";

// Derived from the real pipeline data (no dedicated "sections"/"clauses"/"aligned" fields exist
// backend-side — those stages are approximated from file processing_status + evaluation review
// status, since that's genuinely what each milestone depends on):
//   Received  — at least one current-version file exists
//   Parsed    — every current-version file (circular + submissions) has finished parsing
//   Sections  — payment/service compliance sections have been detected for every current-version file
//   Clauses   — the circular's detected sections are fully reviewed/approved
//   Aligned   — at least one merchant submission is also fully approved, so a circular-vs-submission comparison exists
export function computeProjectSegments(
  currentFiles: ProjectFileRecord[],
  circularEvals: EvaluationRecord[],
  submissionEvals: EvaluationRecord[]
): Seg[] {
  const segs: Seg[] = Array(5).fill("todo");
  if (currentFiles.length === 0) return segs;
  segs[0] = "done"; // Received

  const anyFailed = currentFiles.some((f) => f.processing_status === "PARSE_FAILED");
  const allParsed = currentFiles.every((f) => f.processing_status === "PARSED");
  if (anyFailed) {
    segs[1] = "failed";
    return segs;
  }
  if (!allParsed) {
    segs[1] = "active";
    return segs;
  }
  segs[1] = "done"; // Parsed

  const submissionFileCount = currentFiles.filter((f) => f.file_type === "SUBMISSION").length;
  const hasCircularEval = circularEvals.length > 0;
  if (!hasCircularEval || (submissionFileCount > 0 && submissionEvals.length === 0)) {
    segs[2] = "active";
    return segs;
  }
  segs[2] = "done"; // Sections

  const circularApproved = circularEvals.length > 0 && circularEvals.every(isFullyApproved);
  if (!circularApproved) {
    segs[3] = "active";
    return segs;
  }
  segs[3] = "done"; // Clauses

  const anySubmissionApproved = submissionEvals.some(isFullyApproved);
  segs[4] = anySubmissionApproved ? "done" : submissionEvals.length > 0 ? "active" : "todo";
  return segs;
}

export function isFullyApproved(e: EvaluationRecord): boolean {
  return e.payment_status === "APPROVED" && e.service_status === "APPROVED";
}

/** A project is "completed" once it's reached the final (Aligned) stage. */
export function isProjectCompleted(currentFiles: ProjectFileRecord[], circularEvals: EvaluationRecord[], submissionEvals: EvaluationRecord[]): boolean {
  return computeProjectSegments(currentFiles, circularEvals, submissionEvals)[4] === "done";
}

// Maps the 5-segment project ladder onto PipelineRibbon's 6 pipeline stages (Ingest & parse,
// Classify, Locate sections, Extract clauses, Align, Compliance matrix). Classify happens
// automatically the instant parsing finishes, so it has no dedicated segment of its own — it's
// folded into "Ingest & parse" while parsing is still the bottleneck.
const RIBBON_STAGE_FOR_FIRST_INCOMPLETE_SEGMENT = [0, 0, 2, 3, 4];

export function ribbonStageForSegments(segs: Seg[]): number {
  const firstIncomplete = segs.findIndex((s) => s !== "done");
  if (firstIncomplete === -1) return 5; // Compliance matrix — every segment is done
  return RIBBON_STAGE_FOR_FIRST_INCOMPLETE_SEGMENT[firstIncomplete];
}
