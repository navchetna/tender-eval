"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Download, Loader2, Sparkles, Terminal, Upload } from "lucide-react";
import { ApiError, compareBids, exportMatrix, getDefaultPrompts, getNormalizedView, getProjects } from "@/lib/api";
import type { ComparisonResult, DefaultPrompts, NormalizedView, Project, Topic } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Empty } from "@/components/ui/Empty";
import { toneClasses } from "@/lib/tone";
import { useReportActiveStage } from "@/lib/activeStageContext";

type Tab = "technical" | "price" | "comparison";

const TABS: { key: Tab; label: string }[] = [
  { key: "technical", label: "Technical compliance" },
  { key: "price", label: "Price compliance" },
  { key: "comparison", label: "Detailed comparison" },
];

interface BidderGroup {
  bidder: string;
  fields: { col: string; field: string }[];
}

function groupBidColumns(bidColumns: string[]): BidderGroup[] {
  const groups: BidderGroup[] = [];
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

function parseNumber(value: string | null | undefined): number | null {
  if (!value) return null;
  const cleaned = value.replace(/[^0-9.\-]/g, "");
  if (!cleaned) return null;
  const n = parseFloat(cleaned);
  return Number.isFinite(n) ? n : null;
}

/** Cols (bidder: field keys) holding the lowest numeric value per field-name, when 2+ bidders report a number for it. */
function computeLowestCostCols(row: NormalizedView["rows"][number], bidderGroups: BidderGroup[]): Set<string> {
  const byField = new Map<string, { col: string; value: number }[]>();
  for (const g of bidderGroups) {
    for (const { col, field } of g.fields) {
      const num = parseNumber(row.bid_values[col]);
      if (num === null) continue;
      const arr = byField.get(field) ?? [];
      arr.push({ col, value: num });
      byField.set(field, arr);
    }
  }
  const lowest = new Set<string>();
  for (const entries of byField.values()) {
    if (entries.length < 2) continue;
    const min = Math.min(...entries.map((e) => e.value));
    for (const e of entries) if (e.value === min) lowest.add(e.col);
  }
  return lowest;
}

function NormalizedTable({ view, highlightLowestCost }: { view: NormalizedView; highlightLowestCost?: boolean }) {
  const bidderGroups = groupBidColumns(view.bid_columns);
  if (view.rows.length === 0) {
    return <Empty>No rows found in the tender&apos;s parsed table for this section.</Empty>;
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
            {bidderGroups.map((g) => (
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
            {bidderGroups.map((g) =>
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
          {view.rows.map((row, i) => {
            const lowestCols = highlightLowestCost ? computeLowestCostCols(row, bidderGroups) : new Set<string>();
            return (
              <tr key={i} className="border-t-[0.5px] border-line">
                {view.tender_columns.map((col) => (
                  <td key={col} className="sticky left-0 min-w-[160px] border-b-[0.5px] border-line bg-surface px-[14px] py-[10px] align-top text-[12.5px] text-ink">
                    {row.tender_cells[col] || <span className="text-ink-faint">—</span>}
                  </td>
                ))}
                {bidderGroups.map((g) =>
                  g.fields.map(({ col }) => (
                    <td
                      key={col}
                      className={`border-b-[0.5px] border-l-[0.5px] border-line px-[14px] py-[10px] align-top text-[12.5px] text-ink-soft ${
                        lowestCols.has(col) ? "bg-ok-bg" : ""
                      }`}
                    >
                      {row.bid_values[col] || <span className="text-ink-faint italic">no response</span>}
                    </td>
                  ))
                )}
              </tr>
            );
          })}
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
                <span>Upload a tender/RFP so the model can derive its scoring rules from it — coming soon</span>
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

function ComparisonPanel({ result }: { result: ComparisonResult }) {
  if (result.assessments.length === 0) {
    return <Empty>No approved bidder responses to compare yet.</Empty>;
  }
  return (
    <div>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-[12px]">
        {result.assessments.map((a) => {
          const tn = toneClasses[scoreTone(a.score)];
          const isRecommended = a.bidder === result.recommended_bidder;
          return (
            <Card
              key={a.bidder}
              className={`p-[15px] ${isRecommended ? "border-[1.5px] border-ok-dot bg-ok-bg/40" : ""}`}
            >
              <div className="mb-[8px] flex items-center justify-between gap-2">
                <span className="truncate text-[14px] font-semibold text-ink">{a.bidder}</span>
                <div className="flex items-center gap-[6px]">
                  {isRecommended && (
                    <span className="rounded-full bg-ok-dot px-[8px] py-[2px] text-[10.5px] font-semibold text-white">Recommended</span>
                  )}
                  <span className={`shrink-0 rounded-full px-2 py-[2px] text-[12px] font-semibold ${tn.bg} ${tn.fg}`}>{a.score}/100</span>
                </div>
              </div>
              {a.pros.length > 0 && (
                <div className="mb-[8px]">
                  <div className="mb-[3px] text-[10.5px] font-semibold tracking-[0.3px] text-ok-fg uppercase">Pros</div>
                  <ul className="list-disc space-y-[2px] pl-[16px] text-[12px] leading-[1.4] text-ink-soft">
                    {a.pros.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}
              {a.cons.length > 0 && (
                <div className="mb-[8px]">
                  <div className="mb-[3px] text-[10.5px] font-semibold tracking-[0.3px] text-bad-fg uppercase">Cons</div>
                  <ul className="list-disc space-y-[2px] pl-[16px] text-[12px] leading-[1.4] text-ink-soft">
                    {a.cons.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}
              {a.precautions.length > 0 && (
                <div>
                  <div className="mb-[3px] text-[10.5px] font-semibold tracking-[0.3px] text-warn-fg uppercase">Precautions</div>
                  <ul className="list-disc space-y-[2px] pl-[16px] text-[12px] leading-[1.4] text-ink-soft">
                    {a.precautions.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}
            </Card>
          );
        })}
      </div>
      {result.recommendation && (
        <Card className="mt-[12px] p-[15px]">
          <div className="mb-[5px] text-[11px] tracking-[0.3px] text-ink-faint uppercase">Overall recommendation</div>
          <div className="font-serif text-[13.5px] leading-[1.6] text-ink-soft">{result.recommendation}</div>
        </Card>
      )}
    </div>
  );
}

export function MatrixView({ projectId }: { projectId: string }) {
  useReportActiveStage(5);

  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("comparison");
  const [views, setViews] = useState<Partial<Record<Topic, NormalizedView>>>({});
  const [viewErrors, setViewErrors] = useState<Partial<Record<Topic, string>>>({});
  const [loadingView, setLoadingView] = useState<Partial<Record<Topic, boolean>>>({});
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [comparing, setComparing] = useState(false);
  const [comparisonError, setComparisonError] = useState<string | null>(null);
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
      const message = err instanceof ApiError ? err.message : "Failed to load comparison view";
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
    loadView("technical");
    loadView("price");
    onCompare();
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

  const onCompare = async (promptOverride?: string) => {
    if (!project) return;
    setComparing(true);
    setComparisonError(null);
    try {
      const result = await compareBids(projectId, project.current_version, promptOverride);
      setComparison(result);
    } catch (err) {
      setComparisonError(err instanceof ApiError ? err.message : "Comparison failed");
    } finally {
      setComparing(false);
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

      {(tab === "technical" || tab === "price") &&
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
                <Empty>Aligning bid responses against the tender&apos;s {tab} table — this can take a little while.</Empty>
              )}
              {view && (
                <>
                  <div className="mb-[10px] flex items-center justify-between">
                    {tab === "price" && (
                      <div className="flex items-center gap-[6px] text-[12px] text-ink-soft">
                        <span className="inline-block h-[10px] w-[10px] rounded-[3px] bg-ok-bg" />
                        Lowest cost for that line item
                      </div>
                    )}
                    <button
                      onClick={() => loadView(topic)}
                      disabled={isLoading}
                      className="btn ml-auto flex items-center gap-[6px] rounded-[9px] border-[0.5px] border-line-strong bg-surface px-[12px] py-[6px] text-[12px] text-ink disabled:opacity-60"
                    >
                      {isLoading ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
                      {isLoading ? "Reloading…" : "Reload"}
                    </button>
                  </div>
                  <NormalizedTable view={view} highlightLowestCost={tab === "price"} />
                </>
              )}
            </div>
          );
        })()}

      {tab === "comparison" && (
        <div>
          {!comparison && comparisonError && !comparing && (
            <div className="flex flex-col items-start gap-[10px]">
              <div className="rounded-[9px] bg-bad-bg px-3 py-2 text-[12.5px] text-bad-fg">{comparisonError}</div>
              <LoadDataButton label="Retry" loading={comparing} onClick={() => onCompare()} />
            </div>
          )}
          {!comparison && !comparisonError && (
            <Empty>Weighing pros, cons, and precautions across every bidder — this can take a little while.</Empty>
          )}
          {comparison && !comparing && (
            <>
              <div className="mb-[12px] flex justify-end">
                <PromptControl
                  title="Detailed comparison prompt"
                  defaultPrompt={defaultPrompts?.comparison}
                  running={comparing}
                  runLabel="Regenerate"
                  onRun={(override) => onCompare(override)}
                />
              </div>
              <ComparisonPanel result={comparison} />
            </>
          )}
        </div>
      )}
    </div>
  );
}
