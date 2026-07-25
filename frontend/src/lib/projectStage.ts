import type { Seg } from "@/lib/stageStyles";
import type { EvaluationRecord, ProjectFileRecord } from "@/lib/types";

// Derived from the real pipeline data (no dedicated "sections"/"clauses"/"aligned" fields exist
// backend-side — those stages are approximated from file processing_status + evaluation review
// status, since that's genuinely what each milestone depends on):
//   Received  — at least one current-version file exists
//   Parsed    — every current-version file (tender + bids) has finished parsing
//   Sections  — technical/price sections have been detected for every current-version file
//   Clauses   — the tender's detected sections are fully reviewed/approved
//   Aligned   — at least one bid is also fully approved, so a tender-vs-bid comparison exists
export function computeProjectSegments(
  currentFiles: ProjectFileRecord[],
  tenderEvals: EvaluationRecord[],
  bidEvals: EvaluationRecord[]
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

  const bidFileCount = currentFiles.filter((f) => f.file_type === "BID").length;
  const hasTenderEval = tenderEvals.length > 0;
  if (!hasTenderEval || (bidFileCount > 0 && bidEvals.length === 0)) {
    segs[2] = "active";
    return segs;
  }
  segs[2] = "done"; // Sections

  const tenderApproved = tenderEvals.length > 0 && tenderEvals.every(isFullyApproved);
  if (!tenderApproved) {
    segs[3] = "active";
    return segs;
  }
  segs[3] = "done"; // Clauses

  const anyBidApproved = bidEvals.some(isFullyApproved);
  segs[4] = anyBidApproved ? "done" : bidEvals.length > 0 ? "active" : "todo";
  return segs;
}

export function isFullyApproved(e: EvaluationRecord): boolean {
  return e.technical_status === "APPROVED" && e.price_status === "APPROVED";
}

/** A project is "completed" once it's reached the final (Aligned) stage. */
export function isProjectCompleted(currentFiles: ProjectFileRecord[], tenderEvals: EvaluationRecord[], bidEvals: EvaluationRecord[]): boolean {
  return computeProjectSegments(currentFiles, tenderEvals, bidEvals)[4] === "done";
}
