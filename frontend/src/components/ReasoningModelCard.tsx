"use client";

import { useEffect, useState } from "react";
import { Cpu } from "lucide-react";
import { ApiError, getReasoningModel, setReasoningModel } from "@/lib/api";
import type { ReasoningChoice, ReasoningModelState } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { useAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/ToastProvider";

const OPTIONS: [ReasoningChoice, string][] = [
  ["auto", "Auto"],
  ["claude", "Claude"],
  ["local", "On-device"],
];

// Which model does the reasoning tier (compliance matrix, scoring, final comparison). Admins can
// switch it; everyone sees what's in effect. Backed by /settings/reasoning-model.
export function ReasoningModelCard() {
  const { user } = useAuth();
  const toast = useToast();
  const [state, setState] = useState<ReasoningModelState | null>(null);
  const [saving, setSaving] = useState(false);
  const isAdmin = user?.role === "ADMIN";

  useEffect(() => {
    getReasoningModel()
      .then(setState)
      .catch(() => setState(null));
  }, []);

  if (!state) return null;

  const onChoose = async (choice: ReasoningChoice) => {
    if (choice === state.choice || saving) return;
    setSaving(true);
    try {
      const next = await setReasoningModel(choice);
      setState(next);
      toast(
        `Reasoning now uses ${next.effective === "claude" ? next.claude_model : `the on-device ${next.local_model}`} — ` +
          "existing matrices and comparisons will be recomputed when next opened",
      );
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Failed to switch the reasoning model");
    } finally {
      setSaving(false);
    }
  };

  const effectiveLabel = state.effective === "claude" ? state.claude_model : `on-device ${state.local_model}`;

  return (
    <Card className="mb-[14px] flex flex-wrap items-center justify-between gap-[12px] px-[16px] py-[12px]">
      <div className="flex min-w-0 items-start gap-[10px]">
        <Cpu size={16} className="mt-[2px] shrink-0 text-ink-soft" />
        <div className="min-w-0">
          <div className="text-[13px] font-semibold text-ink">Reasoning model</div>
          <div className="text-[12px] text-ink-soft">
            Compliance matrix, scoring and comparison use <span className="font-mono text-ink">{effectiveLabel}</span>.
            {!state.claude_configured && " Claude isn't configured, so Auto uses the on-device model."}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-[6px]">
        {OPTIONS.map(([value, label]) => {
          const active = state.choice === value;
          const disabled = !isAdmin || saving || (value === "claude" && !state.claude_configured);
          return (
            <button
              key={value}
              onClick={() => onChoose(value)}
              disabled={disabled && !active}
              title={
                value === "claude" && !state.claude_configured
                  ? "Set ANTHROPIC_API_KEY (and ANTHROPIC_BASE_URL for Azure AI Foundry) in Settings first"
                  : !isAdmin
                    ? "Only admins can change this"
                    : undefined
              }
              className={`btn rounded-full border-[0.5px] px-3 py-[5px] text-[12px] disabled:opacity-50 ${
                active ? "border-accent bg-accent-bg font-semibold text-accent-ink" : "border-line-strong bg-transparent text-ink-soft"
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>
    </Card>
  );
}
