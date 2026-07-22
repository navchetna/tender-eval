import { loadAuth } from "./auth-storage";
import type {
  ComparisonResult,
  CurrentUser,
  Employee,
  EmployeeIn,
  EmployeeUpdate,
  EvaluationRecord,
  FileType,
  NormalizedView,
  Project,
  ProjectFileRecord,
  ProjectIn,
  ReviewDecision,
  SectionScoreResult,
  Topic,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8011";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(fn: UnauthorizedHandler | null): void {
  onUnauthorized = fn;
}

async function request<T>(path: string, options: RequestInit = {}, tokenOverride?: string): Promise<T> {
  const token = tokenOverride ?? loadAuth()?.token;
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Basic ${token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    onUnauthorized?.();
    throw new ApiError(401, "Invalid email or password");
  }
  if (!res.ok) {
    const text = await res.text();
    let message = text;
    try {
      message = JSON.parse(text).detail ?? text;
    } catch {
      // not JSON, use raw text
    }
    throw new ApiError(res.status, message || `Request failed (${res.status})`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function whoami(token: string): Promise<CurrentUser> {
  return request<CurrentUser>("/auth/me", {}, token);
}

export const getProjects = () => request<Project[]>("/projects");

export const createProject = (body: ProjectIn) =>
  request<Project>("/projects", { method: "POST", body: JSON.stringify(body) });

export const getProjectFiles = (projectId: string) => request<ProjectFileRecord[]>(`/projects/${projectId}/files`);

export function uploadProjectFiles(
  projectId: string,
  files: File[],
  fileType: FileType,
  newVersion: boolean
): Promise<ProjectFileRecord[]> {
  const form = new FormData();
  form.set("file_type", fileType);
  form.set("new_version", String(newVersion));
  for (const file of files) form.append("files", file);
  return request<ProjectFileRecord[]>(`/projects/${projectId}/files`, { method: "POST", body: form });
}

export const updateFileType = (projectId: string, fileId: string, fileType: FileType) =>
  request<ProjectFileRecord>(`/projects/${projectId}/files/${fileId}`, {
    method: "PATCH",
    body: JSON.stringify({ file_type: fileType }),
  });

export async function getFilePdfBlobUrl(projectId: string, fileId: string): Promise<string> {
  const token = loadAuth()?.token;
  const headers = new Headers();
  if (token) headers.set("Authorization", `Basic ${token}`);
  const res = await fetch(`${BASE_URL}/projects/${projectId}/files/${fileId}/pdf`, { headers });
  if (!res.ok) throw new ApiError(res.status, "Failed to load PDF");
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export async function getFileTree(projectId: string, fileId: string): Promise<unknown | null> {
  try {
    return await request<unknown>(`/projects/${projectId}/files/${fileId}/tree`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export const assignProject = (projectId: string, employeeId: string) =>
  request<{ project_id: string; assigned_to: string; notified: boolean }>(`/projects/${projectId}/assign`, {
    method: "POST",
    body: JSON.stringify({ employee_id: employeeId }),
  });

export const getEvaluationsByProject = (docType: "tender" | "bid", projectId: string, version: number) =>
  request<EvaluationRecord[]>(`/evaluation/${docType}?project_id=${encodeURIComponent(projectId)}&version=${version}`);

export const getPendingEvaluations = (docType: "tender" | "bid") =>
  request<EvaluationRecord[]>(`/evaluation/${docType}/pending`);

export const getEvaluation = (docType: "tender" | "bid", evaluationId: string) =>
  request<EvaluationRecord>(`/evaluation/${docType}/${evaluationId}`);

export const reviewEvaluation = (docType: "tender" | "bid", evaluationId: string, decision: ReviewDecision) =>
  request<EvaluationRecord>(`/evaluation/${docType}/${evaluationId}/review`, {
    method: "POST",
    body: JSON.stringify(decision),
  });

export const notifyEvaluation = (docType: "tender" | "bid", evaluationId: string) =>
  request<{ sent: boolean }>(`/evaluation/${docType}/${evaluationId}/notify`, { method: "POST" });

export const getNormalizedView = (projectId: string, version: number, topic: Topic) =>
  request<NormalizedView>(`/normalization/${projectId}/${version}/${topic}`);

export const scoreSection = (projectId: string, version: number, topic: Topic) =>
  request<SectionScoreResult>(`/normalization/${projectId}/${version}/score/${topic}`, { method: "POST" });

export const compareBids = (projectId: string, version: number) =>
  request<ComparisonResult>(`/normalization/${projectId}/${version}/compare`, { method: "POST" });

export async function exportMatrix(projectId: string, version: number): Promise<void> {
  const token = loadAuth()?.token;
  const headers = new Headers();
  if (token) headers.set("Authorization", `Basic ${token}`);
  const res = await fetch(`${BASE_URL}/normalization/${projectId}/${version}/export`, { headers });
  if (!res.ok) throw new ApiError(res.status, "Export failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `compliance-${projectId}-v${version}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
}

export const getEmployees = () => request<Employee[]>("/employees");

export const createEmployee = (body: EmployeeIn) =>
  request<Employee>("/employees", { method: "POST", body: JSON.stringify(body) });

export const updateEmployee = (employeeId: string, body: EmployeeUpdate) =>
  request<Employee>(`/employees/${employeeId}`, { method: "PATCH", body: JSON.stringify(body) });

export const deleteEmployee = (employeeId: string) =>
  request<void>(`/employees/${employeeId}`, { method: "DELETE" });

export const reprocessPendingFiles = () => request<unknown[]>("/parsing/process-pending", { method: "POST" });

export const pollGmail = () => request<unknown[]>("/ingestion/poll-gmail", { method: "POST" });
