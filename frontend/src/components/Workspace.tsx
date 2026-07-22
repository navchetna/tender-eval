"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { ArrowLeft, ExternalLink, FileText, LayoutGrid, Upload } from "lucide-react";
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
import { SectionLabel } from "@/components/ui/SectionLabel";
import { FileStageTrack } from "@/components/FileStageTrack";
import { DetailTabs } from "@/components/DetailTabs";
import { useAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/ToastProvider";
import { isFullyApproved } from "@/lib/projectStage";

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
      <option value="TENDER">tender</option>
      <option value="BID">bid</option>
      <option value="UNKNOWN">unknown</option>
    </select>
  );
}

function UploadForm({ projectId, onUploaded }: { projectId: string; onUploaded: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [tenderFile, setTenderFile] = useState<File | null>(null);
  const [bidFiles, setBidFiles] = useState<FileList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const bids = bidFiles ? Array.from(bidFiles) : [];
    if (!tenderFile && bids.length === 0) {
      setError("Choose a tender PDF, one or more bid PDFs, or both");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      // Every upload here is a brand-new round: tender + bids submitted together always
      // become one new version, mirroring the fact that a resubmission always replaces
      // both the tender and every bid at once — never a partial addition to an old round.
      let uploadedCount = 0;
      let versionStarted = false;
      if (tenderFile) {
        const uploaded = await uploadProjectFiles(projectId, [tenderFile], "TENDER", true);
        uploadedCount += uploaded.length;
        versionStarted = true;
      }
      if (bids.length > 0) {
        const uploaded = await uploadProjectFiles(projectId, bids, "BID", !versionStarted);
        uploadedCount += uploaded.length;
      }
      toast(`Uploaded ${uploadedCount} file${uploadedCount === 1 ? "" : "s"} as a new version`);
      setTenderFile(null);
      setBidFiles(null);
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
      <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1">
          <span className="text-[12px] font-medium text-ink-soft">Tender PDF</span>
          <input
            type="file"
            accept="application/pdf"
            onChange={(e) => setTenderFile(e.target.files?.[0] ?? null)}
            className="text-[12.5px] text-ink"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[12px] font-medium text-ink-soft">Bid PDFs</span>
          <input
            type="file"
            accept="application/pdf"
            multiple
            onChange={(e) => setBidFiles(e.target.files)}
            className="text-[12.5px] text-ink"
          />
        </label>
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
        {error && <div className="w-full rounded-[9px] bg-bad-bg px-3 py-2 text-[12px] text-bad-fg">{error}</div>}
      </form>
    </Card>
  );
}

export function Workspace({ projectId }: { projectId: string }) {
  const { user } = useAuth();
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

  useEffect(() => {
    if (viewVersion == null) return;
    let cancelled = false;
    (async () => {
      try {
        const [tenderEvals, bidEvals] = await Promise.all([
          getEvaluationsByProject("tender", projectId, viewVersion),
          getEvaluationsByProject("bid", projectId, viewVersion),
        ]);
        if (!cancelled) setEvaluations([...tenderEvals, ...bidEvals]);
      } catch {
        if (!cancelled) setEvaluations([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, viewVersion]);

  const onFileTypeChanged = (updated: ProjectFileRecord) => {
    setFiles((prev) => prev?.map((f) => (f.file_id === updated.file_id ? updated : f)) ?? prev);
  };

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
  const tender = currentFiles.find((f) => f.file_type === "TENDER") ?? null;
  const tenderVersions = files.filter((f) => f.file_type === "TENDER").sort((a, b) => b.version - a.version);
  const bids = currentFiles.filter((f) => f.file_type === "BID");
  const canView = (f: ProjectFileRecord) => f.processing_status === "PARSED";
  const evaluationFor = (fileId: string) => evaluations.find((e) => e.file_id === fileId) ?? null;
  const tenderEvaluation = tender ? evaluationFor(tender.file_id) : null;
  const tenderApproved = tenderEvaluation != null && isFullyApproved(tenderEvaluation);
  const anyBidApproved = bids.some((b) => {
    const e = evaluationFor(b.file_id);
    return e != null && isFullyApproved(e);
  });

  return (
    <div className="px-[30px] py-[22px]">
      <Link href="/projects" className="btn mb-3 flex items-center gap-[6px] border-none bg-transparent p-0 text-[13px] text-ink-soft">
        <ArrowLeft size={15} />
        Projects
      </Link>
      <div className="mb-[18px] flex flex-wrap items-center justify-between gap-[10px]">
        <h1 className="m-0 text-[21px] font-semibold text-ink">{project.project_name}</h1>
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
          <Link
            href={`/projects/${projectId}/matrix`}
            className="btn flex items-center gap-[7px] rounded-[9px] border-[0.5px] border-accent bg-accent px-[15px] py-2 text-[13px] font-medium text-white shadow-[0_2px_8px_-3px_rgba(47,93,138,.5)]"
          >
            <LayoutGrid size={15} />
            Open compliance matrix
          </Link>
        </div>
      </div>

      {user?.role === "ADMIN" && (
        <div className="mb-4">
          <UploadForm projectId={projectId} onUploaded={onUploaded} />
        </div>
      )}

      <div className="grid grid-cols-[1fr_300px] items-start gap-4">
        <div>
          <SectionLabel>Bidders</SectionLabel>
          <Card className="overflow-hidden">
            {bids.length === 0 && <Empty>No bids received yet.</Empty>}
            {bids.map((b, i) => {
              const active = sel?.file_id === b.file_id;
              const evaluation = evaluationFor(b.file_id);
              return (
                <div
                  key={b.file_id}
                  className={`rowh px-[15px] py-[13px] ${i ? "border-t-[0.5px] border-line" : ""} ${active ? "rowsel" : ""}`}
                  onClick={() => canView(b) && setSel(active ? null : b)}
                >
                  <div className="mb-[9px] flex items-center justify-between">
                    <div className="flex items-center gap-[9px]">
                      <span className="text-[13.5px] font-medium text-ink">{b.file_name}</span>
                      <span className="font-mono text-[10.5px] text-ink-faint">v{b.version}</span>
                      {user?.role === "ADMIN" && <TypeSelect file={b} onChanged={onFileTypeChanged} />}
                    </div>
                    {evaluation && evaluation.technical_status === "APPROVED" && evaluation.price_status === "APPROVED" ? (
                      <span className="text-[11px] text-ok-fg">both approved</span>
                    ) : evaluation ? (
                      <span className="text-[11px] text-warn-fg">awaiting review</span>
                    ) : null}
                  </div>
                  <FileStageTrack file={b} evaluation={evaluation} alignmentReady={tenderApproved && evaluation != null && isFullyApproved(evaluation)} />
                </div>
              );
            })}
          </Card>
        </div>

        <div>
          <SectionLabel>Tender</SectionLabel>
          {tender ? (
            <Card
              className={`rowh p-[15px] ${sel?.file_id === tender.file_id ? "rowsel" : ""}`}
              onClick={() => canView(tender) && setSel(sel?.file_id === tender.file_id ? null : tender)}
            >
              <div className="mb-1 flex items-center gap-2">
                <FileText size={15} className="text-accent" />
                <span className="text-[13.5px] font-semibold text-ink">Version {tender.version}</span>
                {user?.role === "ADMIN" && <TypeSelect file={tender} onChanged={onFileTypeChanged} />}
              </div>
              <div className="mb-3 font-mono text-[11px] break-all text-ink-faint">{tender.file_name}</div>
              <FileStageTrack file={tender} evaluation={tenderEvaluation} alignmentReady={anyBidApproved} />
              {tender.drive_web_link && (
                <a
                  href={tender.drive_web_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-3 flex items-center gap-[6px] text-[12px] text-accent"
                >
                  <ExternalLink size={13} />
                  Open in Drive
                </a>
              )}
              {tenderVersions.length > 1 && (
                <div className="mt-4 border-t-[0.5px] border-line pt-[10px]">
                  <div className="mb-2 text-[11px] tracking-[0.4px] text-ink-faint uppercase">Version history</div>
                  {tenderVersions.map((v) => (
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
              <Empty>No tender document yet.</Empty>
            </Card>
          )}
        </div>
      </div>

      {sel && <DetailTabs file={sel} evaluation={evaluationFor(sel.file_id)} onClose={() => setSel(null)} />}
    </div>
  );
}
