// Mirrors pydantic_backend's real response shapes (see pydantic_backend/app.py,
// evaluation/models.py, ingestion/models.py, normalization/models.py) — no invented fields.

export type Tone = "ok" | "warn" | "bad" | "none" | "info";

export type Role = "ADMIN" | "REVIEWER";

export interface CurrentUser {
  employee_id: string;
  name: string;
  email: string;
  role: Role;
}

export interface Employee {
  employee_id: string;
  name: string;
  email: string;
  role: Role;
}

export interface EmployeeIn {
  name: string;
  email: string;
  password: string;
  litellm_key: string;
  role: Role;
}

export interface EmployeeUpdate {
  name?: string;
  email?: string;
  password?: string;
  litellm_key?: string;
  role?: Role;
}

export interface Project {
  project_id: string;
  project_code: string;
  project_name: string;
  current_version: number;
  status: string;
  assigned_to: string | null;
  evaluation_completed: boolean;
}

export interface ProjectIn {
  project_code: string;
  project_name: string;
}

export type FileType = "CIRCULAR" | "SUBMISSION" | "UNKNOWN";
export type ProcessingStatus = "RECEIVED" | "PARSING" | "PARSED" | "PARSE_FAILED";

export interface ProjectFileRecord {
  file_id: string;
  project_id: string;
  version: number;
  file_name: string;
  file_type: FileType;
  processing_status: string;
  drive_web_link: string | null;
  parse_error: string | null;
  parse_toc: string | null;
  detection_error: string | null;
  created_at: string;
  updated_at: string;
}

export type Topic = "payment" | "service";
export type ReviewStatus = "SUGGESTED" | "APPROVED";

export interface EvaluationRecord {
  evaluation_id: string;
  file_id: string;
  project_id: string;
  version: number;
  file_name: string | null;
  detection_model: string | null;
  payment_section_title: string | null;
  payment_section_content: string | null;
  payment_ai_title: string | null;
  payment_ai_content: string | null;
  payment_status: ReviewStatus;
  payment_corrected: boolean;
  payment_reviewed_by: string | null;
  payment_reviewed_at: string | null;
  service_section_title: string | null;
  service_section_content: string | null;
  service_ai_title: string | null;
  service_ai_content: string | null;
  service_status: ReviewStatus;
  service_corrected: boolean;
  service_reviewed_by: string | null;
  service_reviewed_at: string | null;
  notified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReviewDecision {
  topic: Topic;
  corrected_heading?: string | null;
}

export type PipelineStage = "received" | "parsed" | "sections" | "clauses";

export interface StageSchema {
  input: Record<string, unknown>;
  output: Record<string, unknown>;
}

export type PipelineSchema = Record<PipelineStage, StageSchema>;

export interface StageDetail {
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  error: string | null;
}

export type FileStageDetail = Record<PipelineStage, StageDetail>;

export interface NormalizedRow {
  tender_cells: Record<string, string>;
  bid_values: Record<string, string | null>;
  /** Heading the row's table sits under in the circular ("Level 2:- Home screen checklist"). */
  tender_group?: string | null;
}

export interface NormalizedView {
  project_id: string;
  version: number;
  topic: Topic;
  tender_file_name: string | null;
  tender_columns: string[];
  bid_columns: string[];
  rows: NormalizedRow[];
}

export interface BidScore {
  bidder: string;
  score: number;
  reasoning: string;
}

export interface SectionScoreResult {
  project_id: string;
  version: number;
  topic: Topic;
  scores: BidScore[];
  comparison: string;
}

export type RiskLevel = "high" | "medium" | "low";

export interface MerchantAssessment {
  merchant: string;
  risk_level: RiskLevel;
  score: number;
  key_gaps: string[];
  remediation_priorities: string[];
}

export interface RiskTriageResult {
  project_id: string;
  version: number;
  assessments: MerchantAssessment[];
  audit_priority_order: string[];
  summary: string;
}

export interface DefaultPrompts {
  payment: string;
  service: string;
  triage: string;
}

// Shape of the parser's output_tree.json (see evaluation/tree_utils.py's docstring for the
// confirmed real schema) — a heading's children are single-key dicts keyed by heading text.
export type TreeContentType = "text" | "table" | "image";

export interface TreeContentItem {
  type: TreeContentType;
  content: string;
}

export interface DocumentTreeNode {
  content: TreeContentItem[];
  children: Record<string, DocumentTreeNode>[];
}

export interface DocumentTree {
  root: DocumentTreeNode;
}
