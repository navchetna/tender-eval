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
  role: Role;
}

export interface EmployeeUpdate {
  name?: string;
  email?: string;
  password?: string;
  role?: Role;
}

export interface Project {
  project_id: string;
  project_code: string;
  project_name: string;
  current_version: number;
  status: string;
  assigned_to: string | null;
}

export interface ProjectIn {
  project_code: string;
  project_name: string;
}

export type FileType = "TENDER" | "BID" | "UNKNOWN";
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
  created_at: string;
  updated_at: string;
}

export type Topic = "technical" | "price";
export type ReviewStatus = "SUGGESTED" | "APPROVED";

export interface EvaluationRecord {
  evaluation_id: string;
  file_id: string;
  project_id: string;
  version: number;
  file_name: string | null;
  detection_model: string | null;
  technical_section_title: string | null;
  technical_section_content: string | null;
  technical_status: ReviewStatus;
  technical_corrected: boolean;
  technical_reviewed_by: string | null;
  technical_reviewed_at: string | null;
  price_section_title: string | null;
  price_section_content: string | null;
  price_status: ReviewStatus;
  price_corrected: boolean;
  price_reviewed_by: string | null;
  price_reviewed_at: string | null;
  notified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReviewDecision {
  topic: Topic;
  corrected_heading?: string | null;
}

export interface NormalizedRow {
  tender_cells: Record<string, string>;
  bid_values: Record<string, string | null>;
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

export interface BidAssessment {
  bidder: string;
  score: number;
  pros: string[];
  cons: string[];
  precautions: string[];
}

export interface ComparisonResult {
  project_id: string;
  version: number;
  assessments: BidAssessment[];
  recommended_bidder: string | null;
  recommendation: string;
}
