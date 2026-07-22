"use client";

import { useEffect, useState } from "react";
import { FileText, X } from "lucide-react";
import type { EvaluationRecord, ProjectFileRecord } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Empty } from "@/components/ui/Empty";
import { EvaluationSection } from "@/components/EvaluationSection";
import { PdfViewer } from "@/components/PdfViewer";
import { ParsedTreeView } from "@/components/ParsedTreeView";
import { getFileTree } from "@/lib/api";

type Tab = "doc" | "tree" | "technical" | "price";

export function DetailTabs({
  file,
  evaluation,
  onClose,
}: {
  file: ProjectFileRecord;
  evaluation: EvaluationRecord | null;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<Tab>("doc");
  const [tree, setTree] = useState<unknown>(null);

  useEffect(() => {
    let cancelled = false;
    // Reset for the newly-selected file — not a React-state sync, just clearing stale data
    // before the new fetch resolves.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTree(null);
    getFileTree(file.project_id, file.file_id).then((result) => {
      if (!cancelled) setTree(result);
    });
    return () => {
      cancelled = true;
    };
  }, [file.project_id, file.file_id]);

  const tabs: [Tab, string][] = [
    ["doc", "Document"],
    ...(tree ? ([["tree", "Parsed tree"]] as [Tab, string][]) : []),
    ["technical", "Technical"],
    ["price", "Price"],
  ];

  return (
    <Card className="fade mt-4 overflow-hidden">
      <div className="flex items-center justify-between border-b-[0.5px] border-line bg-surface2 px-4 py-[11px]">
        <div className="flex items-center gap-[10px]">
          <FileText size={15} className="text-accent" />
          <span className="text-[13.5px] font-semibold text-ink">{file.file_name}</span>
          <span className="font-mono text-[10.5px] text-ink-faint">v{file.version}</span>
        </div>
        <button className="btn cursor-pointer border-none bg-transparent p-1 text-ink-soft" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="flex gap-1 border-b-[0.5px] border-line px-3">
        {tabs.map(([k, label]) => (
          <button
            key={k}
            className={`tab border-none border-b-2 bg-transparent px-[10px] py-[10px] text-[13px] ${
              tab === k ? "border-accent font-semibold text-ink" : "border-transparent font-normal text-ink-soft"
            }`}
            onClick={() => setTab(k)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className={`overflow-auto bg-surface p-4 ${tab === "doc" || tab === "tree" ? "max-h-[90vh]" : "max-h-[420px]"}`}>
        {tab === "doc" && <PdfViewer projectId={file.project_id} fileId={file.file_id} />}
        {tab === "tree" && (tree ? <ParsedTreeView tree={tree} /> : <Empty>No parsed tree available yet.</Empty>)}
        {tab === "technical" &&
          (evaluation ? (
            <EvaluationSection
              title={evaluation.technical_section_title}
              content={evaluation.technical_section_content}
              status={evaluation.technical_status}
            />
          ) : (
            <Empty>Not yet evaluated — technical section hasn&rsquo;t been detected for this file.</Empty>
          ))}
        {tab === "price" &&
          (evaluation ? (
            <EvaluationSection title={evaluation.price_section_title} content={evaluation.price_section_content} status={evaluation.price_status} />
          ) : (
            <Empty>Not yet evaluated — price section hasn&rsquo;t been detected for this file.</Empty>
          ))}
      </div>
    </Card>
  );
}
