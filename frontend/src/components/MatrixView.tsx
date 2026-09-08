"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Download, Loader2, Sparkles, Terminal, Upload } from "lucide-react";
import { ApiError, exportMatrix, getDefaultPrompts, getNormalizedView, getProjects, triageMerchants } from "@/lib/api";
import type { DefaultPrompts, MerchantAssessment, NormalizedView, Project, RiskLevel, RiskTriageResult, Topic } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Empty } from "@/components/ui/Empty";
import { toneClasses } from "@/lib/tone";
import { useReportActiveStage } from "@/lib/activeStageContext";

type Tab = "payment" | "service" | "triage";

const TABS: { key: Tab; label: string }[] = [
  { key: "payment", label: "Payment compliance" },
  { key: "service", label: "Service compliance" },
  { key: "triage", label: "Risk triage" },
];

interface MerchantGroup {
  bidder: string;
  fields: { col: string; field: string }[];
}

function groupSubmissionColumns(bidColumns: string[]): MerchantGroup[] {
  const groups: MerchantGroup[] = [];
  for (const col of bidColumns) {
    const idx = col.indexOf(": ");
    const bidder = idx === -1 ? col : col.slice(0, idx);
    const field = idx === -1 ? col : col.slice(idx + 2);
    let group = groups.find((g) => g.bidder === bidder);
    if (!group) {
      group = { bidder, fields: [] };
      groups.push(group);
    }
    group.fields.push({ col, field });
  }
  return groups;
}

function NormalizedTable({ view }: { view: NormalizedView }) {
  const merchantGroups = groupSubmissionColumns(view.bid_columns);
  if (view.rows.length === 0) {
    return <Empty>No rows found in the circular&apos;s parsed table for this section.</Empty>;
  }
  return (
    <div className="overflow-x-auto rounded-[13px] border-[0.5px] border-line shadow-[0_1px_2px_rgba(30,28,24,.04)]">
      <table className="w-full min-w-[680px] border-collapse">
        <thead>
          <tr className="bg-surface2">
            {view.tender_columns.map((col) => (
              <th
                key={col}
                rowSpan={2}
                className="sticky left-0 min-w-[160px] border-b-[0.5px] border-line bg-surface2 px-[14px] py-[9px] text-left align-bottom text-[12.5px] font-medium text-ink"
              >
                {col}
              </th>
            ))}
            {merchantGroups.map((g) => (
              <th
                key={g.bidder}
                colSpan={g.fields.length}
                className="border-l-[0.5px] border-b-[0.5px] border-line bg-surface2 px-[14px] py-[9px] text-left text-[12.5px] font-semibold text-ink"
              >
                {g.bidder}
              </th>
            ))}
          </tr>
          <tr className="bg-surface2">
            {merchantGroups.map((g) =>
              g.fields.map(({ col, field }) => (
                <th
                  key={col}
                  className="border-l-[0.5px] border-b-[0.5px] border-line bg-surface2 px-[14px] py-[6px] text-left text-[11px] font-medium text-ink-soft"
                >
                  {field}
                </th>
              ))
            )}
          </tr>
        </thead>
        <tbody>
          {view.rows.map((row, i) => (
            <tr key={i} className="border-t-[0.5px] border-line">
              {view.tender_columns.map((col) => (
                <td key={col} className="sticky left-0 min-w-[160px] border-b-[0.5px] border-line bg-surface px-[14px] py-[10px] align-top text-[12.5px] text-ink">
                  {row.tender_cells[col] || <span className="text-ink-faint">—</span>}
                </td>
              ))}
              {merchantGroups.map((g) =>
                g.fields.map(({ col }) => (
                  <td
                    key={col}
                    className="border-b-[0.5px] border-l-[0.5px] border-line px-[14px] py-[10px] align-top text-[12.5px] text-ink-soft"
                  >
                    {row.bid_values[col] || <span className="text-ink-faint italic">no response</span>}
                  </td>
                ))
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LoadDataButton({ label, loading, onClick }: { label: string; loading: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="btn flex items-center gap-[7px] rounded-[9px] border-none bg-accent px-[16px] py-[9px] text-[13px] font-medium text-white disabled:opacity-60"
    >
      {loading ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
      {loading ? "Asking the model…" : label}
    </button>
  );
}

function scoreTone(score: number): "ok" | "warn" | "bad" {
  if (score >= 75) return "ok";
  if (score >= 50) return "warn";
  return "bad";
}

const RISK_TONE: Record<RiskLevel, "ok" | "warn" | "bad"> = {
  high: "bad",
  medium: "warn",
  low: "ok",
};

/** Shows the exact prompt an evaluation/scoring step will use, and lets a reviewer either run
it as-is or override it with their own wording for that one run — never silently guessing on
the model's behalf. Opens as a popup that hovers over the page instead of pushing content
around, and carries the single run/regenerate action itself rather than a second button
sitting beside the trigger. */
function PromptControl({
  title,
  defaultPrompt,
  running,
  runLabel,
  onRun,
}: {
  title: string;
  defaultPrompt: string | undefined;
  running: boolean;
  runLabel: string;
  onRun: (promptOverride?: string) => void;
}) {
  const [open, setOpen] = useState(false);
  // null = showing the default prompt as-is (tracks `defaultPrompt` as it arrives from the
  // API); once the reviewer types, this holds their edit instead and no longer follows it.
  const [edited, setEdited] = useState<string | null>(null);
  const prompt = edited ?? defaultPrompt ?? "";
  const isCustom = edited !== null && defaultPrompt !== undefined && edited.trim() !== defaultPrompt.trim();

  const close = () => setOpen(false);
  const run = () => {
    onRun(isCustom ? prompt : undefined);
    close();
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        disabled={running || defaultPrompt === undefined}
        className="btn flex items-center gap-[6px] rounded-[9px] border-[0.5px] border-line-strong bg-surface px-[12px] py-[6px] text-[12px] text-ink-soft disabled:opacity-60"
      >
        {running ? <Loader2 size={13} className="animate-spin" /> : <Terminal size={13} />}
        {running ? "Working…" : "Show prompt"}
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(32,32,28,.4)] px-4" onClick={close}>
          <div
            className="expand w-full max-w-[560px] rounded-[13px] border-[0.5px] border-line bg-surface p-5 shadow-[0_20px_60px_-15px_rgba(30,28,24,.4)]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-[12px] text-[15px] font-semibold text-ink">{title}</div>
            <textarea
              value={prompt}
              onChange={(e) => setEdited(e.target.value)}
              rows={10}
              className="w-full resize-y rounded-[7px] border-[0.5px] border-line-strong bg-surface2 px-[10px] py-[8px] font-mono text-[11.5px] leading-[1.5] text-ink outline-none focus:border-accent"
            />
            <div className="mt-[6px] flex items-center justify-between gap-2">
              <span className="text-[11px] text-ink-faint">
                {isCustom ? "Custom prompt — runs fresh, not cached." : "Default prompt — edit it to run with your own wording."}
              </span>
              {isCustom && (
                <button
                  type="button"
                  onClick={() => setEdited(null)}
                  className="btn shrink-0 cursor-pointer rounded-md border-none bg-transparent p-0 text-[11px] text-accent"
                >
                  Reset to default
                </button>
              )}
            </div>

            <div className="mt-[16px] flex flex-col gap-[6px] border-t-[0.5px] border-line pt-[14px]">
              <span className="text-[12px] font-medium text-ink-soft">Extract scoring rules from a document</span>
              <div className="flex cursor-not-allowed items-center gap-[8px] rounded-[9px] border-[1.5px] border-dashed border-line-strong bg-surface2 px-3 py-[10px] text-[12px] text-ink-faint opacity-70">
                <Upload size={14} className="shrink-0" />
                <span>Upload a compliance circular so the model can derive its scoring rules from it — coming soon</span>
              </div>
            </div>

            <div className="mt-[18px] flex justify-end gap-2">
              <button
                type="button"
                onClick={close}
                className="btn cursor-pointer rounded-[9px] border-[0.5px] border-line-strong bg-surface px-4 py-2 text-[13px] text-ink"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={run}
                className="btn flex cursor-pointer items-center gap-[6px] rounded-[9px] border-none bg-accent px-4 py-2 text-[13px] font-medium text-white"
              >
                <Sparkles size={14} />
                {isCustom ? "Regenerate" : runLabel}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function TriagePanel({ result }: { result: RiskTriageResult }) {
  if (result.assessments.length === 0) {
    return <Empty>No approved merchant submissions to triage yet.</Empty>;
  }
  // Cards follow the model's audit-priority ranking; any assessment the ranking missed
  // still gets shown, appended after the ranked ones.
  const ranked = result.audit_priority_order
    .map((merchant) => result.assessments.find((a) => a.merchant === merchant))
    .filter((a): a is MerchantAssessment => a != null);
  const unranked = result.assessments.filter((a) => !ranked.includes(a));
  const ordered = [...ranked, ...unranked];
  return (
    <div>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-[12px]">
        {ordered.map((a, i) => {
          const scoreTn = toneClasses[scoreTone(a.score)];
          const riskTn = toneClasses[RISK_TONE[a.risk_level]];
          return (
            <Card key={a.merchant} className="p-[15px]">
              <div className="mb-[8px] flex items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-[7px]">
                  <span className="shrink-0 rounded-full bg-surface2 px-[8px] py-[2px] text-[10.5px] font-semibold text-ink-soft">
                    #{i + 1} audit priority
                  </span>
                  <span className="truncate text-[14px] font-semibold text-ink">{a.merchant}</span>
                </div>
                <div className="flex shrink-0 items-center gap-[6px]">
                  <span className={`rounded-full px-2 py-[2px] text-[10.5px] font-semibold uppercase ${riskTn.bg} ${riskTn.fg}`}>
                    {a.risk_level} risk
                  </span>
                  <span className={`rounded-full px-2 py-[2px] text-[12px] font-semibold ${scoreTn.bg} ${scoreTn.fg}`}>{a.score}/100</span>
                </div>
              </div>
              {a.key_gaps.length > 0 && (
                <div className="mb-[8px]">
                  <div className="mb-[3px] text-[10.5px] font-semibold tracking-[0.3px] text-bad-fg uppercase">Key gaps</div>
                  <ul className="list-disc space-y-[2px] pl-[16px] text-[12px] leading-[1.4] text-ink-soft">
                    {a.key_gaps.map((g, j) => (
                      <li key={j}>{g}</li>
                    ))}
                  </ul>
                </div>
              )}
              {a.remediation_priorities.length > 0 && (
                <div>
                  <div className="mb-[3px] text-[10.5px] font-semibold tracking-[0.3px] text-warn-fg uppercase">Remediation priorities</div>
                  <ol className="list-decimal space-y-[2px] pl-[16px] text-[12px] leading-[1.4] text-ink-soft">
                    {a.remediation_priorities.map((p, j) => (
                      <li key={j}>{p}</li>
                    ))}
                  </ol>
                </div>
              )}
            </Card>
          );
        })}
      </div>
      {result.summary && (
        <Card className="mt-[12px] p-[15px]">
          <div className="mb-[5px] text-[11px] tracking-[0.3px] text-ink-faint uppercase">Audit priority summary</div>
          <div className="font-serif text-[13.5px] leading-[1.6] text-ink-soft">{result.summary}</div>
        </Card>
      )}
    </div>
  );
}

export function MatrixView({ projectId }: { projectId: string }) {
  useReportActiveStage(5);

  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("triage");
  const [views, setViews] = useState<Partial<Record<Topic, NormalizedView>>>({});
  const [viewErrors, setViewErrors] = useState<Partial<Record<Topic, string>>>({});
  const [loadingView, setLoadingView] = useState<Partial<Record<Topic, boolean>>>({});
  const [triage, setTriage] = useState<RiskTriageResult | null>(null);
  const [triaging, setTriaging] = useState(false);
  const [triageError, setTriageError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [defaultPrompts, setDefaultPrompts] = useState<DefaultPrompts | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const projects = await getProjects();
        const found = projects.find((p) => p.project_id === projectId) ?? null;
        if (!cancelled) setProject(found);
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Failed to load project");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    let cancelled = false;
    getDefaultPrompts()
      .then((p) => {
        if (!cancelled) setDefaultPrompts(p);
      })
      .catch(() => undefined); // prompt display is a nicety — a failed fetch just leaves the "Show prompt" control disabled
    return () => {
      cancelled = true;
    };
  }, []);

  const loadView = async (topic: Topic): Promise<NormalizedView | null> => {
    if (!project) return null;
    setLoadingView((prev) => ({ ...prev, [topic]: true }));
    setViewErrors((prev) => ({ ...prev, [topic]: undefined }));
    try {
      const view = await getNormalizedView(projectId, project.current_version, topic);
      setViews((prev) => ({ ...prev, [topic]: view }));
      return view;
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Failed to load compliance view";
      setViewErrors((prev) => ({ ...prev, [topic]: message }));
      return null;
    } finally {
      setLoadingView((prev) => ({ ...prev, [topic]: false }));
    }
  };

  // Kick every result off as soon as the project loads, rather than waiting for a button
  // click — each call returns the cached value instantly if one exists, or computes and caches
  // it otherwise, so this always ends in the data being shown without user interaction.
  useEffect(() => {
    if (!project) return;
    loadView("payment");
    loadView("service");
    onTriage();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project]);

  const onExport = async () => {
    if (!project) return;
    setExporting(true);
    try {
      await exportMatrix(projectId, project.current_version);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  };

  const onTriage = async (promptOverride?: string) => {
    if (!project) return;
    setTriaging(true);
    setTriageError(null);
    try {
      const result = await triageMerchants(projectId, project.current_version, promptOverride);
      setTriage(result);
    } catch (err) {
      setTriageError(err instanceof ApiError ? err.message : "Risk triage failed");
    } finally {
      setTriaging(false);
    }
  };

  if (error) {
    return (
      <div className="px-[30px] py-[22px]">
        <Link href={`/projects/${projectId}`} className="btn mb-3 flex items-center gap-[6px] border-none bg-transparent p-0 text-[13px] text-ink-soft">
          <ArrowLeft size={15} />
          Back
        </Link>
        <div className="rounded-[9px] bg-bad-bg px-3 py-2 text-[12.5px] text-bad-fg">{error}</div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="px-[30px] py-[22px]">
        <Empty>Loading…</Empty>
      </div>
    );
  }

  return (
    <div className="px-[30px] py-[22px]">
      <Link
        href={`/projects/${projectId}`}
        className="btn mb-3 flex items-center gap-[6px] border-none bg-transparent p-0 text-[13px] text-ink-soft"
      >
        <ArrowLeft size={15} />
        {project.project_name}
      </Link>
      <div className="mb-[14px] flex flex-wrap items-center justify-between gap-[10px]">
        <h1 className="m-0 text-[21px] font-semibold text-ink">Compliance matrix</h1>
        <button
          onClick={onExport}
          disabled={exporting}
          className="btn flex items-center gap-[7px] rounded-[9px] border-[0.5px] border-line-strong bg-surface px-[14px] py-[7px] text-[13px] text-ink disabled:opacity-60"
        >
          <Download size={15} />
          {exporting ? "Exporting…" : "Export .xlsx"}
        </button>
      </div>

      <div className="mb-[16px] flex items-center gap-[6px] border-b-[0.5px] border-line">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`btn rounded-t-[9px] border-none bg-transparent px-[16px] py-[9px] text-[13.5px] ${
              tab === t.key ? "font-semibold text-ink shadow-[inset_0_-2px_0_var(--color-accent)]" : "text-ink-soft"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {(tab === "payment" || tab === "service") &&
        (() => {
          const topic = tab as Topic;
          const view = views[topic];
          const isLoading = !!loadingView[topic];
          const viewError = viewErrors[topic];
          return (
            <div>
              {!view && viewError && !isLoading && (
                <div className="flex flex-col items-start gap-[10px]">
                  <div className="rounded-[9px] bg-bad-bg px-3 py-2 text-[12.5px] text-bad-fg">{viewError}</div>
                  <LoadDataButton label="Retry" loading={isLoading} onClick={() => loadView(topic)} />
                </div>
              )}
              {!view && !viewError && (
                <Empty>Aligning merchant responses against the circular&apos;s {tab} compliance table — this can take a little while.</Empty>
              )}
              {view && (
                <>
                  <div className="mb-[10px] flex items-center justify-between">
                    <button
                      onClick={() => loadView(topic)}
                      disabled={isLoading}
                      className="btn ml-auto flex items-center gap-[6px] rounded-[9px] border-[0.5px] border-line-strong bg-surface px-[12px] py-[6px] text-[12px] text-ink disabled:opacity-60"
                    >
                      {isLoading ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
                      {isLoading ? "Reloading…" : "Reload"}
                    </button>
                  </div>
                  <NormalizedTable view={view} />
                </>
              )}
            </div>
          );
        })()}

      {tab === "triage" && (
        <div>
          {!triage && triageError && !triaging && (
            <div className="flex flex-col items-start gap-[10px]">
              <div className="rounded-[9px] bg-bad-bg px-3 py-2 text-[12.5px] text-bad-fg">{triageError}</div>
              <LoadDataButton label="Retry" loading={triaging} onClick={() => onTriage()} />
            </div>
          )}
          {!triage && !triageError && (
            <Empty>Ranking merchants by compliance risk — this can take a little while.</Empty>
          )}
          {triage && !triaging && (
            <>
              <div className="mb-[12px] flex justify-end">
                <PromptControl
                  title="Risk triage prompt"
                  defaultPrompt={defaultPrompts?.triage}
                  running={triaging}
                  runLabel="Regenerate"
                  onRun={(override) => onTriage(override)}
                />
              </div>
              <TriagePanel result={triage} />
            </>
          )}
        </div>
      )}
    </div>
  );
}
