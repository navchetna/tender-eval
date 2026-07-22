"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { Check, Clock, Mail, Plus, RefreshCw } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";
import { Empty } from "@/components/ui/Empty";
import { ProjectStageTrack } from "@/components/ProjectStageTrack";
import { useAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/ToastProvider";
import {
  ApiError,
  assignProject,
  createProject,
  getEmployees,
  getEvaluationsByProject,
  getProjectFiles,
  getProjects,
  pollGmail,
  reprocessPendingFiles,
} from "@/lib/api";
import type { Employee, EvaluationRecord, Project, ProjectFileRecord } from "@/lib/types";

interface ProjectSummary {
  project: Project;
  currentFiles: ProjectFileRecord[];
  bidCount: number;
  tenderEvals: EvaluationRecord[];
  bidEvals: EvaluationRecord[];
}

function NewProjectForm({ onCreated }: { onCreated: (p: Project) => void }) {
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const created = await createProject({ project_code: code.trim(), project_name: name.trim() });
      onCreated(created);
      setCode("");
      setName("");
      setOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create project");
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="btn flex items-center gap-[7px] rounded-[9px] border-[0.5px] border-accent bg-accent px-[15px] py-2 text-[13px] font-medium text-white"
      >
        <Plus size={15} />
        New project
      </button>
    );
  }

  return (
    <Card className="p-4">
      <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1">
          <span className="text-[12px] font-medium text-ink-soft">Project code</span>
          <input
            required
            pattern="^[A-Za-z0-9][A-Za-z0-9_\-]*$"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="BPCL-2026-002"
            className="w-[180px] rounded-[9px] border-[0.5px] border-line-strong bg-surface px-3 py-2 text-[13px] text-ink outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[12px] font-medium text-ink-soft">Project name</span>
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Construction of ABC Facility"
            className="w-[280px] rounded-[9px] border-[0.5px] border-line-strong bg-surface px-3 py-2 text-[13px] text-ink outline-none focus:border-accent"
          />
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="btn cursor-pointer rounded-[9px] border-none bg-accent px-4 py-2 text-[13px] font-medium text-white disabled:opacity-60"
        >
          {submitting ? "Creating…" : "Create"}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="btn cursor-pointer rounded-[9px] border-[0.5px] border-line-strong bg-surface px-4 py-2 text-[13px] text-ink"
        >
          Cancel
        </button>
        {error && <div className="w-full rounded-[9px] bg-bad-bg px-3 py-2 text-[12px] text-bad-fg">{error}</div>}
      </form>
    </Card>
  );
}

function AssignSelect({
  project,
  employees,
  onAssigned,
}: {
  project: Project;
  employees: Employee[];
  onAssigned: (projectId: string, employeeId: string) => void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const onChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const employeeId = e.target.value;
    if (!employeeId || employeeId === project.assigned_to) return;
    setBusy(true);
    try {
      const result = await assignProject(project.project_id, employeeId);
      onAssigned(project.project_id, employeeId);
      const emp = employees.find((x) => x.employee_id === employeeId);
      toast(
        result.notified
          ? `Assigned to ${emp?.name ?? "reviewer"} — notification email sent`
          : `Assigned to ${emp?.name ?? "reviewer"} — notification email could not be sent`
      );
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Failed to assign");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
      className="mt-[10px] flex items-center gap-2"
    >
      <span className="text-[11px] text-ink-faint">Assigned to</span>
      <select
        value={project.assigned_to ?? ""}
        disabled={busy}
        onChange={onChange}
        className="flex-1 rounded-md border-[0.5px] border-line-strong bg-surface px-2 py-[3px] text-[11.5px] text-ink-soft outline-none disabled:opacity-60"
      >
        <option value="" disabled>
          Unassigned
        </option>
        {employees.map((emp) => (
          <option key={emp.employee_id} value={emp.employee_id}>
            {emp.name}
          </option>
        ))}
      </select>
    </div>
  );
}

export default function ProjectsPage() {
  const { user } = useAuth();
  const toast = useToast();
  const [summaries, setSummaries] = useState<ProjectSummary[] | null>(null);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [checkingGmail, setCheckingGmail] = useState(false);
  const [parsing, setParsing] = useState(false);

  const load = async () => {
    try {
      const projects = await getProjects();
      const withFiles = await Promise.all(
        projects.map(async (project) => {
          const files = await getProjectFiles(project.project_id);
          const currentFiles = files.filter((f) => f.version === project.current_version);
          const bidCount = currentFiles.filter((f) => f.file_type === "BID").length;
          const [tenderEvals, bidEvals] =
            project.current_version > 0
              ? await Promise.all([
                  getEvaluationsByProject("tender", project.project_id, project.current_version),
                  getEvaluationsByProject("bid", project.project_id, project.current_version),
                ]).catch(() => [[], []] as [EvaluationRecord[], EvaluationRecord[]])
              : [[], []];
          return { project, currentFiles, bidCount, tenderEvals, bidEvals };
        })
      );
      setSummaries(withFiles);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load projects");
    }
  };

  useEffect(() => {
    // load() only sets state inside its own awaited branches, never synchronously in this effect body.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, []);

  useEffect(() => {
    if (user?.role !== "ADMIN") return;
    getEmployees()
      .then(setEmployees)
      .catch(() => setEmployees([]));
  }, [user]);

  const onAssigned = (projectId: string, employeeId: string) => {
    setSummaries((prev) =>
      prev?.map((s) => (s.project.project_id === projectId ? { ...s, project: { ...s.project, assigned_to: employeeId } } : s)) ?? prev
    );
  };

  const onCheckGmail = async () => {
    setCheckingGmail(true);
    try {
      const results = await pollGmail();
      toast(results.length > 0 ? `Found ${results.length} new project email(s) — ingesting into Received` : "No new unread tender/bid emails found");
      await load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Failed to check Gmail");
    } finally {
      setCheckingGmail(false);
    }
  };

  const onParsePending = async () => {
    setParsing(true);
    try {
      const results = await reprocessPendingFiles();
      toast(results.length > 0 ? `Sent ${results.length} document(s) to the parser` : "No documents waiting to be parsed");
      await load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Failed to start parsing");
    } finally {
      setParsing(false);
    }
  };

  return (
    <div className="px-[30px] py-[26px]">
      <div className="mb-[22px] flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="m-0 text-[21px] font-semibold text-ink">Projects</h1>
          <p className="mt-[5px] text-[13.5px] text-ink-soft">
            Each project has one tender and its bidders. Reconciliation runs continuously as documents arrive.
          </p>
        </div>
        {user?.role === "ADMIN" && (
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={onCheckGmail}
              disabled={checkingGmail}
              className="btn flex items-center gap-[7px] rounded-[9px] border-[0.5px] border-line-strong bg-surface px-[14px] py-2 text-[13px] text-ink disabled:opacity-60"
            >
              <Mail size={15} />
              {checkingGmail ? "Checking…" : "Check Gmail for new tenders"}
            </button>
            <button
              onClick={onParsePending}
              disabled={parsing}
              className="btn flex items-center gap-[7px] rounded-[9px] border-[0.5px] border-line-strong bg-surface px-[14px] py-2 text-[13px] text-ink disabled:opacity-60"
            >
              <RefreshCw size={15} />
              {parsing ? "Parsing…" : "Parse pending documents"}
            </button>
            <NewProjectForm onCreated={load} />
          </div>
        )}
      </div>
      {error && <div className="mb-4 rounded-[9px] bg-bad-bg px-3 py-2 text-[12.5px] text-bad-fg">{error}</div>}
      {summaries === null && !error && <Empty>Loading…</Empty>}
      {summaries !== null && summaries.length === 0 && (
        <Empty>
          {user?.role === "ADMIN"
            ? "No projects yet — create one to get started."
            : "No projects have been assigned to you yet — contact your admin to get one assigned."}
        </Empty>
      )}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(310px,1fr))] gap-[15px]">
        {summaries?.map(({ project, currentFiles, bidCount, tenderEvals, bidEvals }) => (
          <Link key={project.project_id} href={`/projects/${project.project_id}`}>
            <Card className="lift cursor-pointer p-[17px]">
              <div className="mb-[11px] flex items-center justify-between">
                <span className="font-mono text-[11px] text-ink-faint">{project.project_code}</span>
                {bidCount > 0 ? (
                  <Pill tone="ok">
                    <Check size={12} />
                    On track
                  </Pill>
                ) : (
                  <Pill tone="info">
                    <Clock size={12} />
                    Intake
                  </Pill>
                )}
              </div>
              <div className="text-[16px] font-semibold text-ink">{project.project_name}</div>
              <div className="my-[10px] flex items-center gap-2 text-[12.5px] text-ink-soft">
                <span>Tender v{project.current_version}</span>
                <span className="text-line-strong">·</span>
                <span>
                  {bidCount} {bidCount === 1 ? "bid" : "bids"}
                </span>
              </div>
              <ProjectStageTrack currentFiles={currentFiles} tenderEvals={tenderEvals} bidEvals={bidEvals} />
              {user?.role === "ADMIN" && <AssignSelect project={project} employees={employees} onAssigned={onAssigned} />}
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
