"use client";

import { useEffect, useState } from "react";
import { Check, ChevronRight, FileText, Pencil, X } from "lucide-react";
import { ApiError, getPendingEvaluations, getProjectFiles, getProjects, reviewEvaluation } from "@/lib/api";
import type { EvaluationRecord, Project, Topic } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";
import { Empty } from "@/components/ui/Empty";
import { useToast } from "@/components/ToastProvider";
import { TocPicker } from "@/components/TocPicker";
import { PdfViewer } from "@/components/PdfViewer";

interface SelectedFile {
  projectId: string;
  fileId: string;
  fileName: string | null;
}

type DocType = "tender" | "bid";

function TopicRow({
  docType,
  evaluation,
  topic,
  toc,
  onUpdated,
}: {
  docType: DocType;
  evaluation: EvaluationRecord;
  topic: Topic;
  toc: string | null;
  onUpdated: (updated: EvaluationRecord) => void;
}) {
  const toast = useToast();
  const [correcting, setCorrecting] = useState(false);
  const [heading, setHeading] = useState("");
  const [busy, setBusy] = useState(false);

  const title = topic === "technical" ? evaluation.technical_section_title : evaluation.price_section_title;
  const status = topic === "technical" ? evaluation.technical_status : evaluation.price_status;

  const approve = async () => {
    setBusy(true);
    try {
      const updated = await reviewEvaluation(docType, evaluation.evaluation_id, { topic });
      onUpdated(updated);
      toast(`${topic === "technical" ? "Technical" : "Price"} section approved`);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Failed to approve");
    } finally {
      setBusy(false);
    }
  };

  const correct = async () => {
    if (!heading.trim()) return;
    setBusy(true);
    try {
      const updated = await reviewEvaluation(docType, evaluation.evaluation_id, { topic, corrected_heading: heading.trim() });
      onUpdated(updated);
      setCorrecting(false);
      setHeading("");
      toast(`${topic === "technical" ? "Technical" : "Price"} section corrected`);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Failed to correct");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border-t-[0.5px] border-line py-3 first:border-t-0">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-semibold text-ink-soft capitalize">{topic}</span>
          <span className="text-[13px] text-ink">{title ?? "No heading detected"}</span>
        </div>
        <Pill tone={status === "APPROVED" ? "ok" : "warn"} mono>
          {status.toLowerCase()}
        </Pill>
      </div>
      {status === "SUGGESTED" && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <button
              disabled={busy}
              onClick={approve}
              className="btn flex items-center gap-[6px] rounded-[9px] border-none bg-accent px-3 py-[6px] text-[12.5px] font-medium text-white disabled:opacity-60"
            >
              <Check size={13} />
              Approve
            </button>
            {!correcting && (
              <button
                disabled={busy}
                onClick={() => setCorrecting(true)}
                className="btn flex items-center gap-[6px] rounded-[9px] border-[0.5px] border-line-strong bg-surface px-3 py-[6px] text-[12.5px] text-ink disabled:opacity-60"
              >
                <Pencil size={13} />
                Correct…
              </button>
            )}
          </div>
          {correcting && (
            <div className="flex flex-col gap-2 rounded-[9px] border-[0.5px] border-line p-2">
              {toc ? (
                <>
                  <div className="text-[11px] tracking-[0.3px] text-ink-faint uppercase">
                    Parsed table of contents — click a heading to select it
                  </div>
                  <TocPicker toc={toc} onSelect={setHeading} />
                </>
              ) : (
                <div className="text-[11.5px] text-ink-faint italic">No parsed TOC available for this file — type the heading manually.</div>
              )}
              <div className="flex items-center gap-2">
                <input
                  value={heading}
                  onChange={(e) => setHeading(e.target.value)}
                  placeholder="Correct TOC heading, verbatim"
                  className="flex-1 rounded-[9px] border-[0.5px] border-line-strong bg-surface px-2 py-[6px] text-[12.5px] text-ink outline-none focus:border-accent"
                />
                <button
                  disabled={busy || !heading.trim()}
                  onClick={correct}
                  className="btn cursor-pointer rounded-[9px] border-none bg-accent px-3 py-[6px] text-[12.5px] font-medium text-white disabled:opacity-60"
                >
                  Save
                </button>
                <button
                  disabled={busy}
                  onClick={() => {
                    setCorrecting(false);
                    setHeading("");
                  }}
                  className="btn cursor-pointer rounded-[9px] border-[0.5px] border-line-strong bg-surface px-3 py-[6px] text-[12.5px] text-ink"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface Item {
  docType: DocType;
  evaluation: EvaluationRecord;
}

interface ProjectGroup {
  project: Project;
  items: Item[];
}

function ProjectAccordion({
  group,
  expanded,
  onToggle,
  tocByFileId,
  onUpdated,
  selectedFileId,
  onSelectFile,
}: {
  group: ProjectGroup;
  expanded: boolean;
  onToggle: () => void;
  tocByFileId: Record<string, string | null>;
  onUpdated: (docType: DocType, updated: EvaluationRecord) => void;
  selectedFileId: string | null;
  onSelectFile: (file: SelectedFile) => void;
}) {
  const pendingCount = group.items.filter(
    ({ evaluation }) => evaluation.technical_status === "SUGGESTED" || evaluation.price_status === "SUGGESTED"
  ).length;

  return (
    <Card className="fade mb-[14px] overflow-hidden">
      <button
        onClick={onToggle}
        className="btn flex w-full cursor-pointer items-center justify-between gap-2 border-none bg-transparent px-[19px] py-[15px] text-left"
      >
        <div className="flex items-center gap-[10px]">
          <ChevronRight size={15} className={`text-ink-faint transition-transform ${expanded ? "rotate-90" : ""}`} />
          <span className="text-[15px] font-semibold text-ink">{group.project.project_name}</span>
          <Pill tone="info" mono>
            {group.project.project_code}
          </Pill>
        </div>
        <Pill tone={pendingCount > 0 ? "warn" : "ok"}>{pendingCount > 0 ? `${pendingCount} pending` : "all reviewed"}</Pill>
      </button>
      {expanded && (
        <div className="border-t-[0.5px] border-line px-[19px] pt-[15px] pb-[19px]">
          {group.items.map(({ docType, evaluation }) => (
            <div key={evaluation.evaluation_id} className="mb-[14px] rounded-[9px] border-[0.5px] border-line p-[15px] last:mb-0">
              <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() =>
                    onSelectFile({ projectId: evaluation.project_id, fileId: evaluation.file_id, fileName: evaluation.file_name })
                  }
                  className={`btn flex cursor-pointer items-center gap-[9px] rounded-[7px] border-none bg-transparent px-1 py-[2px] text-left ${
                    selectedFileId === evaluation.file_id ? "bg-accent/10" : ""
                  }`}
                  title="View source PDF"
                >
                  <FileText size={14} className="text-ink-faint" />
                  <span className="text-[14px] font-semibold text-ink underline decoration-line-strong decoration-1 underline-offset-2">
                    {evaluation.file_name}
                  </span>
                  <Pill tone="none" mono>
                    {docType} · v{evaluation.version}
                  </Pill>
                </button>
              </div>
              <TopicRow
                docType={docType}
                evaluation={evaluation}
                topic="technical"
                toc={tocByFileId[evaluation.file_id] ?? null}
                onUpdated={(u) => onUpdated(docType, u)}
              />
              <TopicRow
                docType={docType}
                evaluation={evaluation}
                topic="price"
                toc={tocByFileId[evaluation.file_id] ?? null}
                onUpdated={(u) => onUpdated(docType, u)}
              />
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export default function ReviewPage() {
  const [tender, setTender] = useState<EvaluationRecord[] | null>(null);
  const [bid, setBid] = useState<EvaluationRecord[] | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [tocByFileId, setTocByFileId] = useState<Record<string, string | null>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<SelectedFile | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [t, b, allProjects] = await Promise.all([
          getPendingEvaluations("tender"),
          getPendingEvaluations("bid"),
          getProjects(),
        ]);
        if (cancelled) return;
        setTender(t);
        setBid(b);
        setProjects(allProjects);

        const projectIds = Array.from(new Set([...t, ...b].map((e) => e.project_id)));
        const filesByProject = await Promise.all(projectIds.map((id) => getProjectFiles(id)));
        const tocMap: Record<string, string | null> = {};
        for (const files of filesByProject) {
          for (const file of files) tocMap[file.file_id] = file.parse_toc;
        }
        if (!cancelled) setTocByFileId(tocMap);
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Failed to load review queue");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const updateOne = (docType: DocType, updated: EvaluationRecord) => {
    const setList = docType === "tender" ? setTender : setBid;
    setList((prev) => {
      if (!prev) return prev;
      const stillPending = updated.technical_status === "SUGGESTED" || updated.price_status === "SUGGESTED";
      if (!stillPending) return prev.filter((e) => e.evaluation_id !== updated.evaluation_id);
      return prev.map((e) => (e.evaluation_id === updated.evaluation_id ? updated : e));
    });
  };

  if (error) {
    return (
      <div className="px-[30px] py-[26px]">
        <div className="rounded-[9px] bg-bad-bg px-3 py-2 text-[12.5px] text-bad-fg">{error}</div>
      </div>
    );
  }

  if (tender === null || bid === null) {
    return (
      <div className="px-[30px] py-[26px]">
        <Empty>Loading…</Empty>
      </div>
    );
  }

  const items: Item[] = [
    ...tender.map((evaluation) => ({ docType: "tender" as const, evaluation })),
    ...bid.map((evaluation) => ({ docType: "bid" as const, evaluation })),
  ];

  const groupsByProject = new Map<string, ProjectGroup>();
  for (const item of items) {
    const existing = groupsByProject.get(item.evaluation.project_id);
    if (existing) {
      existing.items.push(item);
      continue;
    }
    const project = projects.find((p) => p.project_id === item.evaluation.project_id);
    if (!project) continue; // shouldn't happen — evaluation always belongs to a real project
    groupsByProject.set(item.evaluation.project_id, { project, items: [item] });
  }
  const groups = Array.from(groupsByProject.values());

  return (
    <div className="px-[30px] py-[26px]">
      <h1 className="m-0 text-[21px] font-semibold text-ink">Review queue</h1>
      <p className="mt-[5px] mb-[22px] text-[13.5px] text-ink-soft">
        Technical and price sections detected by the model, grouped by project — expand a project to review. Click a document
        name to view its source PDF alongside the TOC.
      </p>
      <div className={selectedFile ? "grid grid-cols-[1fr_minmax(360px,42%)] items-start gap-[18px]" : ""}>
        <div>
          {groups.length === 0 && (
            <Card className="p-[42px]">
              <Empty>Nothing waiting. New evaluations appear here once sections are detected.</Empty>
            </Card>
          )}
          {groups.map((group) => (
            <ProjectAccordion
              key={group.project.project_id}
              group={group}
              expanded={!!expanded[group.project.project_id]}
              onToggle={() => setExpanded((prev) => ({ ...prev, [group.project.project_id]: !prev[group.project.project_id] }))}
              tocByFileId={tocByFileId}
              onUpdated={updateOne}
              selectedFileId={selectedFile?.fileId ?? null}
              onSelectFile={(file) => setSelectedFile((prev) => (prev?.fileId === file.fileId ? null : file))}
            />
          ))}
        </div>
        {selectedFile && (
          <div className="sticky top-[16px]">
            <Card className="overflow-hidden p-[13px]">
              <div className="mb-[10px] flex items-center justify-between gap-2">
                <span className="truncate text-[13px] font-semibold text-ink">{selectedFile.fileName ?? "Source PDF"}</span>
                <button
                  type="button"
                  onClick={() => setSelectedFile(null)}
                  className="btn cursor-pointer rounded-md border-none bg-transparent p-1 text-ink-faint"
                  title="Close preview"
                >
                  <X size={15} />
                </button>
              </div>
              <PdfViewer projectId={selectedFile.projectId} fileId={selectedFile.fileId} />
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
