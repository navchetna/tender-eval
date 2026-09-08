"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import Link from "next/link";
import { ArrowLeft, Award, ExternalLink, FileText, LayoutGrid, Upload, UserPlus, Users, X } from "lucide-react";
import {
  ApiError,
  getEvaluationsByProject,
  getProjectFiles,
  getProjects,
  updateFileType,
  uploadProjectFiles,
} from "@/lib/api";
import type { EvaluationRecord, FileType, Project, ProjectFileRecord } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Empty } from "@/components/ui/Empty";
import { Pill } from "@/components/ui/Pill";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { FileStageTrack } from "@/components/FileStageTrack";
import { DetailTabs } from "@/components/DetailTabs";
import { useAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/ToastProvider";
import { computeProjectSegments, isFullyApproved, ribbonStageForSegments } from "@/lib/projectStage";
import { computeFileSegments } from "@/lib/fileStage";
import { STAGE_LADDER, type Seg } from "@/lib/stageStyles";
import { useReportActiveStage } from "@/lib/activeStageContext";

function TypeSelect({
  file,
  onChanged,
}: {
  file: ProjectFileRecord;
  onChanged: (updated: ProjectFileRecord) => void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const onChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const next = e.target.value as FileType;
    if (next === file.file_type) return;
    setBusy(true);
    try {
      const updated = await updateFileType(file.project_id, file.file_id, next);
      onChanged(updated);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Failed to update file type");
    } finally {
      setBusy(false);
    }
  };

  return (
    <select
      value={file.file_type}
      disabled={busy}
      onClick={(e) => e.stopPropagation()}
      onChange={onChange}
      className="rounded-md border-[0.5px] border-line-strong bg-surface px-[6px] py-[2px] text-[11px] text-ink-soft outline-none disabled:opacity-60"
    >
      <option value="CIRCULAR">Circular</option>
      <option value="SUBMISSION">Merchant submission</option>
      <option value="UNKNOWN">Unknown</option>
    </select>
  );
}

function IconBadge({ icon }: { icon: ReactNode }) {
  return (
    <span className="flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-[8px] bg-accent-bg text-accent">
      {icon}
    </span>
  );
}

function FileDropzone({
  label,
  icon,
  accept,
  multiple,
  files,
  onPick,
  onRemove,
}: {
  label: string;
  icon: ReactNode;
  accept: string;
  multiple?: boolean;
  files: File[];
  onPick: (files: FileList | null) => void;
  onRemove: (index: number) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex min-w-[240px] flex-1 flex-col gap-[7px]">
      <span className="flex items-center gap-[8px] text-[12px] font-medium text-ink-soft">
        <IconBadge icon={icon} />
        {label}
      </span>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="btn flex cursor-pointer items-center gap-[8px] rounded-[9px] border-[1.5px] border-dashed border-line-strong bg-surface2 px-3 py-[10px] text-left text-[12.5px] text-ink-faint hover:border-accent hover:text-accent"
      >
        <Upload size={14} className="shrink-0" />
        {multiple ? "Click to choose PDFs" : "Click to choose a PDF"}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={(e) => {
          onPick(e.target.files);
          e.target.value = "";
        }}
        className="hidden"
      />
      {files.length > 0 && (
        <div className="flex flex-col gap-[5px]">
          {files.map((f, i) => (
            <div
              key={`${f.name}-${i}`}
              className="flex items-center gap-[6px] rounded-[7px] bg-accent-bg px-[8px] py-[5px] text-[11.5px] text-accent-ink"
            >
              <FileText size={12} className="shrink-0" />
              <span className="flex-1 truncate font-mono">{f.name}</span>
              <button
                type="button"
                onClick={() => onRemove(i)}
                className="btn cursor-pointer rounded-md border-none bg-transparent p-[2px] text-accent-ink/70 hover:text-bad-fg"
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function UploadForm({ projectId, onUploaded }: { projectId: string; onUploaded: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [circularFile, setCircularFile] = useState<File | null>(null);
  const [submissionFiles, setSubmissionFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const submissions = submissionFiles;
    if (!circularFile && submissions.length === 0) {
      setError("Choose a circular PDF, one or more merchant submission PDFs, or both");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      // Every upload here is a brand-new round: circular + submissions submitted together always
      // become one new version, mirroring the fact that a resubmission always replaces
      // both the circular and every merchant submission at once — never a partial addition to an old round.
      let uploadedCount = 0;
      let versionStarted = false;
      if (circularFile) {
        const uploaded = await uploadProjectFiles(projectId, [circularFile], "CIRCULAR", true);
        uploadedCount += uploaded.length;
        versionStarted = true;
      }
      if (submissions.length > 0) {
        const uploaded = await uploadProjectFiles(projectId, submissions, "SUBMISSION", !versionStarted);
        uploadedCount += uploaded.length;
      }
      toast(`Uploaded ${uploadedCount} file${uploadedCount === 1 ? "" : "s"} as a new version`);
      setCircularFile(null);
      setSubmissionFiles([]);
      setOpen(false);
      onUploaded();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="btn flex items-center gap-[7px] rounded-[9px] border-[0.5px] border-line-strong bg-surface px-[14px] py-2 text-[13px] text-ink"
      >
        <Upload size={15} />
        Upload new round
      </button>
    );
  }

  return (
    <Card className="mb-4 p-4">
      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        <div className="flex flex-wrap items-start gap-3">
          <FileDropzone
            label="Compliance circular PDF"
            icon={<FileText size={14} />}
            accept="application/pdf"
            files={circularFile ? [circularFile] : []}
            onPick={(files) => setCircularFile(files?.[0] ?? null)}
            onRemove={() => setCircularFile(null)}
          />
          <FileDropzone
            label="Merchant self-certification PDFs"
            icon={<Users size={14} />}
            accept="application/pdf"
            multiple
            files={submissionFiles}
            onPick={(files) => {
              const picked = files ? Array.from(files) : [];
              setSubmissionFiles((prev) => [...prev, ...picked]);
            }}
            onRemove={(index) => setSubmissionFiles((prev) => prev.filter((_, i) => i !== index))}
          />
        </div>
        <div className="flex items-center gap-2">
          <button
            type="submit"
            disabled={submitting}
            className="btn cursor-pointer rounded-[9px] border-none bg-accent px-4 py-2 text-[13px] font-medium text-white disabled:opacity-60"
          >
            {submitting ? "Uploading…" : "Upload as new version"}
          </button>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="btn cursor-pointer rounded-[9px] border-[0.5px] border-line-strong bg-surface px-4 py-2 text-[13px] text-ink"
          >
            Cancel
          </button>
        </div>
        {error && <div className="rounded-[9px] bg-bad-bg px-3 py-2 text-[12px] text-bad-fg">{error}</div>}
      </form>
    </Card>
  );
}

function AddMerchantForm({ projectId, onUploaded }: { projectId: string; onUploaded: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [submissionFiles, setSubmissionFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const close = () => {
    setOpen(false);
    setSubmissionFiles([]);
    setError(null);
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (submissionFiles.length === 0) {
      setError("Choose one or more merchant submission PDFs");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      // new_version=false: these merchants join the current round's existing Drive folder,
      // instead of UploadForm's "new round" path which always starts a fresh version.
      const uploaded = await uploadProjectFiles(projectId, submissionFiles, "SUBMISSION", false);
      toast(`Added ${uploaded.length} merchant${uploaded.length === 1 ? "" : "s"} to the current round`);
      close();
      onUploaded();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="btn flex cursor-pointer items-center gap-[6px] rounded-[8px] border-[0.5px] border-line-strong bg-surface px-[10px] py-[5px] text-[11.5px] text-ink"
      >
        <UserPlus size={13} />
        Add merchant
      </button>
      {open && (
        // Rendered as a fixed overlay (not inline) so opening it never reflows the
        // Merchants card or anything else on the page.
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(32,32,28,.4)] px-4" onClick={close}>
          <div
            className="expand w-full max-w-[440px] rounded-[13px] border-[0.5px] border-line bg-surface p-5 shadow-[0_20px_60px_-15px_rgba(30,28,24,.4)]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 text-[15px] font-semibold text-ink">Add merchant to the current round</div>
            <form onSubmit={onSubmit} className="flex flex-col gap-[12px]">
              <FileDropzone
                label="Merchant self-certification PDFs"
                icon={<Users size={14} />}
                accept="application/pdf"
                multiple
                files={submissionFiles}
                onPick={(files) => {
                  const picked = files ? Array.from(files) : [];
                  setSubmissionFiles((prev) => [...prev, ...picked]);
                }}
                onRemove={(index) => setSubmissionFiles((prev) => prev.filter((_, i) => i !== index))}
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={close}
                  disabled={submitting}
                  className="btn cursor-pointer rounded-[9px] border-[0.5px] border-line-strong bg-surface px-4 py-2 text-[13px] text-ink disabled:opacity-60"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn cursor-pointer rounded-[9px] border-none bg-accent px-4 py-2 text-[13px] font-medium text-white disabled:opacity-60"
                >
                  {submitting ? "Adding…" : "Add to current round"}
                </button>
              </div>
              {error && <div className="rounded-[9px] bg-bad-bg px-3 py-2 text-[12px] text-bad-fg">{error}</div>}
            </form>
          </div>
        </div>
      )}
    </>
  );
}

export function Workspace({ projectId }: { projectId: string }) {
  const { user } = useAuth();
  const toast = useToast();
  const [project, setProject] = useState<Project | null>(null);
  const [files, setFiles] = useState<ProjectFileRecord[] | null>(null);
  const [evaluations, setEvaluations] = useState<EvaluationRecord[]>([]);
  const [viewVersion, setViewVersion] = useState<number | null>(null);
  const [sel, setSel] = useState<ProjectFileRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const [projects, projectFiles] = await Promise.all([getProjects(), getProjectFiles(projectId)]);
      const found = projects.find((p) => p.project_id === projectId) ?? null;
      setProject(found);
      setFiles(projectFiles);
      setViewVersion((prev) => prev ?? found?.current_version ?? null);
      return found;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load project");
      return null;
    }
  };

  const onUploaded = async () => {
    const found = await load();
    if (found) setViewVersion(found.current_version); // jump to the version just uploaded to
  };

  useEffect(() => {
    // load() only sets state inside its own awaited branches, never synchronously in this effect body.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const loadEvaluations = async (version: number) => {
    try {
      const [circularEvals, submissionEvals] = await Promise.all([
        getEvaluationsByProject("circular", projectId, version),
        getEvaluationsByProject("submission", projectId, version),
      ]);
      setEvaluations([...circularEvals, ...submissionEvals]);
    } catch {
      setEvaluations([]);
    }
  };

  useEffect(() => {
    if (viewVersion == null) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadEvaluations(viewVersion);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, viewVersion]);

  // Parsing and section-detection run in the background worker, with no user action to trigger
  // a refresh. Diff each file's stage ladder against its previous snapshot to toast completions
  // and failures, and track whether anything is still mid-flight so the poll below knows to run.
  const prevSegsRef = useRef<Map<string, Seg[]>>(new Map());
  const [pipelineBusy, setPipelineBusy] = useState(false);

  useEffect(() => {
    if (!files || viewVersion == null) return;
    const currentFiles = files.filter((f) => f.version === viewVersion);
    const circularFile = currentFiles.find((f) => f.file_type === "CIRCULAR") ?? null;
    const submissionFiles = currentFiles.filter((f) => f.file_type === "SUBMISSION");
    const evalFor = (fileId: string) => evaluations.find((e) => e.file_id === fileId) ?? null;
    const circularEval = circularFile ? evalFor(circularFile.file_id) : null;
    const circularDone = circularEval != null && isFullyApproved(circularEval);
    const anySubmissionDone = submissionFiles.some((s) => {
      const e = evalFor(s.file_id);
      return e != null && isFullyApproved(e);
    });

    const rows = [
      ...(circularFile ? [{ file: circularFile, evaluation: circularEval, alignmentReady: anySubmissionDone }] : []),
      ...submissionFiles.map((s) => {
        const e = evalFor(s.file_id);
        return { file: s, evaluation: e, alignmentReady: circularDone && e != null && isFullyApproved(e) };
      }),
    ];

    let busy = false;
    for (const { file, evaluation, alignmentReady } of rows) {
      const segs = computeFileSegments(file, evaluation, alignmentReady);
      if (segs[1] === "active" || segs[2] === "active") busy = true;
      const prev = prevSegsRef.current.get(file.file_id);
      if (prev) {
        segs.forEach((seg, i) => {
          if (seg === prev[i]) return;
          if (seg === "done" && prev[i] === "active") toast(`${file.file_name} — ${STAGE_LADDER[i]} complete`);
          else if (seg === "failed") toast(`${file.file_name} — ${STAGE_LADDER[i]} failed`);
        });
      }
      prevSegsRef.current.set(file.file_id, segs);
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPipelineBusy(busy);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [files, evaluations, viewVersion]);

  useEffect(() => {
    if (!pipelineBusy) return;
    const id = setInterval(async () => {
      await load();
      if (viewVersion != null) await loadEvaluations(viewVersion);
    }, 4000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pipelineBusy, projectId, viewVersion]);

  const onFileTypeChanged = (updated: ProjectFileRecord) => {
    setFiles((prev) => prev?.map((f) => (f.file_id === updated.file_id ? updated : f)) ?? prev);
  };

  // A stage retry can change the file's processing_status and/or create a brand-new
  // evaluation row (e.g. a failed section-detection succeeding on retry) — both files and
  // evaluations need a full refetch, not just a local patch like onFileTypeChanged does.
  const onRetried = async () => {
    await load();
    if (viewVersion != null) await loadEvaluations(viewVersion);
  };

  // Reports this project's pipeline progress up to the shared PipelineRibbon in the app layout,
  // so the reviewer sees where their currently-open project sits relative to the whole pipeline.
  const stageCurrentFiles = files?.filter((f) => f.version === viewVersion) ?? [];
  const stageCircular = stageCurrentFiles.find((f) => f.file_type === "CIRCULAR") ?? null;
  const stageCircularEval = stageCircular ? (evaluations.find((e) => e.file_id === stageCircular.file_id) ?? null) : null;
  const stageSubmissionEvals = stageCurrentFiles
    .filter((f) => f.file_type === "SUBMISSION")
    .map((f) => evaluations.find((e) => e.file_id === f.file_id))
    .filter((e): e is EvaluationRecord => e != null);
  const stageSegs = computeProjectSegments(stageCurrentFiles, stageCircularEval ? [stageCircularEval] : [], stageSubmissionEvals);
  useReportActiveStage(files && viewVersion != null ? ribbonStageForSegments(stageSegs) : null);

  if (error) {
    return (
      <div className="px-[30px] py-[22px]">
        <Link href="/projects" className="btn mb-3 flex items-center gap-[6px] border-none bg-transparent p-0 text-[13px] text-ink-soft">
          <ArrowLeft size={15} />
          Projects
        </Link>
        <div className="rounded-[9px] bg-bad-bg px-3 py-2 text-[12.5px] text-bad-fg">{error}</div>
      </div>
    );
  }

  if (!project || !files || viewVersion == null) {
    return (
      <div className="px-[30px] py-[22px]">
        <Empty>Loading…</Empty>
      </div>
    );
  }

  const versions = Array.from(new Set(files.map((f) => f.version))).sort((a, b) => b - a);
  const currentFiles = files.filter((f) => f.version === viewVersion);
  const circular = currentFiles.find((f) => f.file_type === "CIRCULAR") ?? null;
  const circularVersions = files.filter((f) => f.file_type === "CIRCULAR").sort((a, b) => b.version - a.version);
  const submissions = currentFiles.filter((f) => f.file_type === "SUBMISSION");
  const canView = (f: ProjectFileRecord) => f.processing_status === "PARSED";
  const evaluationFor = (fileId: string) => evaluations.find((e) => e.file_id === fileId) ?? null;
  const circularEvaluation = circular ? evaluationFor(circular.file_id) : null;
  const circularApproved = circularEvaluation != null && isFullyApproved(circularEvaluation);
  const anySubmissionApproved = submissions.some((s) => {
    const e = evaluationFor(s.file_id);
    return e != null && isFullyApproved(e);
  });

  return (
    <div className="px-[30px] py-[22px]">
      <Link href="/projects" className="btn mb-3 flex items-center gap-[6px] border-none bg-transparent p-0 text-[13px] text-ink-soft">
        <ArrowLeft size={15} />
        Projects
      </Link>
      <div className="mb-[18px] flex flex-wrap items-center justify-between gap-[10px]">
        <div className="flex items-center gap-[10px]">
          <h1 className="m-0 text-[21px] font-semibold text-ink">{project.project_name}</h1>
          {project.evaluation_completed && viewVersion === project.current_version && (
            <Pill tone="ok">
              <Award size={12} />
              Evaluation completed
            </Pill>
          )}
        </div>
        <div className="flex items-center gap-2">
          {versions.length > 0 && (
            <select
              value={viewVersion}
              onChange={(e) => setViewVersion(Number(e.target.value))}
              className="rounded-[9px] border-[0.5px] border-line-strong bg-surface px-3 py-2 text-[13px] text-ink outline-none focus:border-accent"
            >
              {versions.map((v) => (
                <option key={v} value={v}>
                  Version {v}
                  {v === project.current_version ? " (current)" : ""}
                </option>
              ))}
            </select>
          )}
          {circularApproved ? (
            <Link
              href={`/projects/${projectId}/matrix`}
              className="btn flex items-center gap-[7px] rounded-[9px] border-[0.5px] border-accent bg-accent px-[15px] py-2 text-[13px] font-medium text-white shadow-[0_2px_8px_-3px_rgba(47,93,138,.5)]"
            >
              <LayoutGrid size={15} />
              Open compliance matrix
            </Link>
          ) : (
            <span
              title="The circular's payment and service compliance sections must be reviewed and approved before the compliance matrix has anything to compare."
              className="flex cursor-not-allowed items-center gap-[7px] rounded-[9px] border-[0.5px] border-line-strong bg-surface px-[15px] py-2 text-[13px] font-medium text-ink-faint opacity-60"
            >
              <LayoutGrid size={15} />
              Open compliance matrix
            </span>
          )}
        </div>
      </div>

      {user?.role === "ADMIN" && (
        <div className="mb-4">
          <UploadForm projectId={projectId} onUploaded={onUploaded} />
        </div>
      )}

      <div className="grid grid-cols-[2fr_3fr] items-start gap-4">
        <div>
          <SectionLabel>Circular</SectionLabel>
          {circular ? (
            <Card
              className={`rowh p-[15px] ${sel?.file_id === circular.file_id ? "rowsel" : ""}`}
              onClick={() => canView(circular) && setSel(sel?.file_id === circular.file_id ? null : circular)}
            >
              <div className="mb-1 flex items-center gap-2">
                <FileText size={15} className="text-accent" />
                <span className="text-[13.5px] font-semibold text-ink">Version {circular.version}</span>
                {user?.role === "ADMIN" && <TypeSelect file={circular} onChanged={onFileTypeChanged} />}
              </div>
              <div className="mb-3 font-mono text-[11px] break-all text-ink-faint">{circular.file_name}</div>
              <FileStageTrack file={circular} evaluation={circularEvaluation} alignmentReady={anySubmissionApproved} onRetried={onRetried} />
              {circular.drive_web_link && (
                <a
                  href={circular.drive_web_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-3 flex items-center gap-[6px] text-[12px] text-accent"
                >
                  <ExternalLink size={13} />
                  Open in Drive
                </a>
              )}
              {circularVersions.length > 1 && (
                <div className="mt-4 border-t-[0.5px] border-line pt-[10px]">
                  <div className="mb-2 text-[11px] tracking-[0.4px] text-ink-faint uppercase">Version history</div>
                  {circularVersions.map((v) => (
                    <div key={v.file_id} className="flex items-center justify-between py-[5px] text-[12.5px]">
                      <span className={v.version === project.current_version ? "font-medium text-ink" : "text-ink-faint"}>v{v.version}</span>
                      <span className={`text-[11px] ${v.version === project.current_version ? "text-ok-fg" : "text-ink-faint"}`}>
                        {v.version === project.current_version ? "current" : "superseded"}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          ) : (
            <Card className="p-[15px]">
              <Empty>No compliance circular yet.</Empty>
            </Card>
          )}
        </div>

        <div>
          <div className="mb-[9px] flex items-center justify-between">
            <SectionLabel>Merchants</SectionLabel>
            {user?.role === "ADMIN" && viewVersion === project.current_version && (
              <AddMerchantForm projectId={projectId} onUploaded={onUploaded} />
            )}
          </div>
          <Card className="overflow-hidden">
            {submissions.length === 0 && <Empty>No merchant submissions received yet.</Empty>}
            {submissions.map((s, i) => {
              const active = sel?.file_id === s.file_id;
              const evaluation = evaluationFor(s.file_id);
              return (
                <div
                  key={s.file_id}
                  className={`rowh px-[15px] py-[13px] ${i ? "border-t-[0.5px] border-line" : ""} ${active ? "rowsel" : ""}`}
                  onClick={() => canView(s) && setSel(active ? null : s)}
                >
                  <div className="mb-[9px] flex items-center justify-between">
                    <div className="flex items-center gap-[9px]">
                      <span className="text-[13.5px] font-medium text-ink">{s.file_name}</span>
                      <span className="font-mono text-[10.5px] text-ink-faint">v{s.version}</span>
                      {user?.role === "ADMIN" && <TypeSelect file={s} onChanged={onFileTypeChanged} />}
                    </div>
                    {evaluation && evaluation.payment_status === "APPROVED" && evaluation.service_status === "APPROVED" ? (
                      <span className="text-[11px] text-ok-fg">both approved</span>
                    ) : evaluation ? (
                      <span className="text-[11px] text-warn-fg">awaiting review</span>
                    ) : null}
                  </div>
                  <FileStageTrack
                    file={s}
                    evaluation={evaluation}
                    alignmentReady={circularApproved && evaluation != null && isFullyApproved(evaluation)}
                    onRetried={onRetried}
                  />
                </div>
              );
            })}
          </Card>
        </div>
      </div>

      {sel && <DetailTabs file={sel} evaluation={evaluationFor(sel.file_id)} onClose={() => setSel(null)} />}
    </div>
  );
}
