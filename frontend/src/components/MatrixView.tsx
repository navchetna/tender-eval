"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Download, Loader2, Sparkles } from "lucide-react";
import { ApiError, compareBids, exportMatrix, getNormalizedView, getProjects } from "@/lib/api";
import type { ComparisonResult, NormalizedView, Project, Topic } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Empty } from "@/components/ui/Empty";
import { toneClasses } from "@/lib/tone";

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
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("technical");
  const [views, setViews] = useState<Partial<Record<Topic, NormalizedView>>>({});
  const [viewErrors, setViewErrors] = useState<Partial<Record<Topic, string>>>({});
  const [loadingView, setLoadingView] = useState<Partial<Record<Topic, boolean>>>({});
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [comparing, setComparing] = useState(false);
  const [comparisonError, setComparisonError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

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

  const onCompare = async () => {
    if (!project) return;
    setComparing(true);
    setComparisonError(null);
    try {
      const result = await compareBids(projectId, project.current_version);
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
              {!view && (
                <div className="flex flex-col items-start gap-[10px]">
                  <p className="text-[12.5px] text-ink-soft">
                    Aligning bid responses against the tender&apos;s {tab} table requires an LLM pass — nothing runs until
                    you ask for it.
                  </p>
                  <LoadDataButton
                    label={`Show ${tab} comparison`}
                    loading={isLoading}
                    onClick={() => loadView(topic)}
                  />
                  {viewError && !isLoading && <div className="rounded-[9px] bg-bad-bg px-3 py-2 text-[12.5px] text-bad-fg">{viewError}</div>}
                </div>
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
          {!comparison && (
            <div className="flex flex-col items-start gap-[10px]">
              <p className="text-[12.5px] text-ink-soft">
                Ask the model for a detailed overview across both technical and price sections together — a score per
                bidder, explicit pros/cons/precautions, and one overall recommendation.
              </p>
              <LoadDataButton label="Generate comparison" loading={comparing} onClick={onCompare} />
              {comparisonError && !comparing && (
                <div className="rounded-[9px] bg-bad-bg px-3 py-2 text-[12.5px] text-bad-fg">{comparisonError}</div>
              )}
            </div>
          )}
          {comparing && <Empty>Weighing pros, cons, and precautions across every bidder — this can take a little while.</Empty>}
          {comparison && !comparing && (
            <>
              <div className="mb-[12px] flex justify-end">
                <button
                  onClick={onCompare}
                  className="btn flex items-center gap-[6px] rounded-[9px] border-[0.5px] border-line-strong bg-surface px-[12px] py-[6px] text-[12px] text-ink"
                >
                  <Sparkles size={13} />
                  Regenerate
                </button>
              </div>
              <ComparisonPanel result={comparison} />
            </>
          )}
        </div>
      )}
    </div>
  );
}
