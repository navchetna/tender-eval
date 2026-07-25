"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { ApiError, getEvaluationsByProject, getProjectFiles, getProjects, reprocessPendingFiles } from "@/lib/api";
import type { EvaluationRecord, Project, ProjectFileRecord } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";
import { Dot } from "@/components/ui/Dot";
import { Empty } from "@/components/ui/Empty";
import { useToast } from "@/components/ToastProvider";
import { useAuth } from "@/components/AuthProvider";
import { DetailTabs } from "@/components/DetailTabs";

type Filter = "all" | "attention" | "inflight" | "done";

interface Row {
  file: ProjectFileRecord;
  project: Project;
  evaluation: EvaluationRecord | null;
}

const isAttention = (r: Row) => r.file.processing_status === "PARSE_FAILED";
const isInflight = (r: Row) => r.file.processing_status === "RECEIVED" || r.file.processing_status === "PARSING";
const isDone = (r: Row) => r.file.processing_status === "PARSED";

export default function OpsPage() {
  const { user } = useAuth();
  const toast = useToast();
  const [rowsAll, setRowsAll] = useState<Row[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [f, setF] = useState<Filter>("all");
  const [sel, setSel] = useState<Row | null>(null);
  const [reprocessing, setReprocessing] = useState(false);

  const load = async () => {
    try {
      const projects = await getProjects();
      const rows: Row[] = [];
      for (const project of projects) {
        const files = await getProjectFiles(project.project_id);
        const [tenderEvals, bidEvals] = await Promise.all([
          getEvaluationsByProject("tender", project.project_id, project.current_version),
          getEvaluationsByProject("bid", project.project_id, project.current_version),
        ]);
        const evaluations = [...tenderEvals, ...bidEvals];
        for (const file of files) {
          rows.push({ file, project, evaluation: evaluations.find((e) => e.file_id === file.file_id) ?? null });
        }
      }
      setRowsAll(rows);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load documents");
    }
  };

  useEffect(() => {
    // load() only sets state inside its own awaited branches, never synchronously in this effect body.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    // Pipeline runs in the background (parse -> section-detect) — poll so status changes show
    // up without a manual click.
    const interval = setInterval(load, 10_000);
    return () => clearInterval(interval);
  }, []);

  const onReprocess = async () => {
    setReprocessing(true);
    try {
      await reprocessPendingFiles();
      toast("Reprocessing queued for pending files");
      await load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Failed to queue reprocessing");
    } finally {
      setReprocessing(false);
    }
  };

  if (error) {
    return (
      <div className="px-[30px] py-[26px]">
        <div className="rounded-[9px] bg-bad-bg px-3 py-2 text-[12.5px] text-bad-fg">{error}</div>
      </div>
    );
  }

  if (rowsAll === null) {
    return (
      <div className="px-[30px] py-[26px]">
        <Empty>Loading…</Empty>
      </div>
    );
  }

  const rows = rowsAll.filter(
    (r) => f === "all" || (f === "attention" && isAttention(r)) || (f === "inflight" && isInflight(r)) || (f === "done" && isDone(r))
  );
  const filters: [Filter, string, number][] = [
    ["all", "All", rowsAll.length],
    ["attention", "Needs attention", rowsAll.filter(isAttention).length],
    ["inflight", "In progress", rowsAll.filter(isInflight).length],
    ["done", "Parsed", rowsAll.filter(isDone).length],
  ];
  const canView = (r: Row) => r.file.processing_status === "PARSED";

  return (
    <div className="flex h-full">
      <div className="min-w-0 overflow-auto px-[30px] py-[26px] transition-[flex-basis] duration-200" style={{ flex: sel ? "0 0 46%" : "1 1 100%" }}>
        <div className="mb-[18px] flex flex-wrap items-center justify-between gap-[10px]">
          <div>
            <h1 className="m-0 text-[21px] font-semibold text-ink">Operations</h1>
            <p className="mt-[5px] text-[13.5px] text-ink-soft">
              Every document and where it sits in the pipeline. Parsing and section-detection run automatically in the
              background — this list refreshes every 10s.
            </p>
          </div>
          {user?.role === "ADMIN" && (
            <button
              onClick={onReprocess}
              disabled={reprocessing}
              className="btn flex items-center gap-[7px] rounded-[9px] border-[0.5px] border-line-strong bg-surface px-[14px] py-[7px] text-[13px] text-ink disabled:opacity-60"
            >
              <RefreshCw size={14} />
              {reprocessing ? "Queuing…" : "Reprocess pending files"}
            </button>
          )}
        </div>
        <div className="mb-[14px] flex flex-wrap items-center gap-[6px]">
          {filters.map(([k, l, n]) => (
            <button
              key={k}
              onClick={() => setF(k)}
              className={`btn rounded-full px-3 py-[5px] text-[12px] border-[0.5px] ${
                f === k ? "border-accent bg-accent-bg font-semibold text-accent-ink" : "border-line-strong bg-transparent font-normal text-ink-soft"
              }`}
            >
              {l} <span className="text-ink-faint">{n}</span>
            </button>
          ))}
        </div>
        <Card className="overflow-hidden">
          {rows.length === 0 ? (
            <Empty>No documents match this filter.</Empty>
          ) : (
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-surface2">
                  {["Document", "Role", "Stage"].map((h, i) => (
                    <th key={i} className="border-b-[0.5px] border-line px-[14px] py-[9px] text-left text-[11.5px] font-semibold tracking-[0.3px] text-ink-faint uppercase">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => {
                  const fail = r.file.processing_status === "PARSE_FAILED";
                  const wait = r.file.processing_status === "PARSING";
                  const active = sel?.file.file_id === r.file.file_id;
                  return (
                    <tr
                      key={r.file.file_id}
                      className={`rowh ${i ? "border-t-[0.5px] border-line" : ""} ${active ? "rowsel" : ""}`}
                      onClick={() => canView(r) && setSel(active ? null : r)}
                    >
                      <td className="px-[14px] py-[10px]">
                        <div className="font-mono text-[11px] text-ink-faint">
                          {!sel && `${r.project.project_name} · `}v{r.file.version}
                        </div>
                        <div className="text-[12.5px] text-ink">{r.file.file_name}</div>
                        {r.file.parse_error && <div className="mt-[2px] text-[11px] text-bad-fg">{r.file.parse_error}</div>}
                      </td>
                      <td className="px-[14px] py-[10px]">
                        <Pill tone={r.file.file_type === "TENDER" ? "info" : "none"} mono>
                          {r.file.file_type.toLowerCase()}
                        </Pill>
                      </td>
                      <td className="px-[14px] py-[10px]">
                        <div className="flex items-center gap-[7px]">
                          <Dot tone={fail ? "bad" : wait ? "warn" : r.file.processing_status === "PARSED" ? "ok" : "info"} />
                          <span className={`font-mono text-[11px] ${fail ? "text-bad-fg" : wait ? "text-warn-fg" : "text-ink-soft"}`}>
                            {r.file.processing_status.toLowerCase()}
                          </span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Card>
      </div>

      {sel && (
        <div className="slidein min-w-0 border-l-[0.5px] border-line bg-surface2 p-4" style={{ flex: "1 1 54%" }}>
          <DetailTabs file={sel.file} evaluation={sel.evaluation} onClose={() => setSel(null)} />
        </div>
      )}
    </div>
  );
}
