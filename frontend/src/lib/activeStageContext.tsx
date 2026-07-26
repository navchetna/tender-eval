"use client";

import { createContext, useContext, useEffect } from "react";

// Lets a project detail view report which pipeline stage (0-5, matching PipelineRibbon's
// STAGES) it's currently at, so the ribbon rendered once in the shared app layout can highlight
// it. Provided by (app)/layout.tsx, which owns the actual state.
export const ActiveStageContext = createContext<((stage: number | null) => void) | null>(null);

export function useReportActiveStage(stage: number | null) {
  const setActiveStage = useContext(ActiveStageContext);
  useEffect(() => {
    setActiveStage?.(stage);
    return () => setActiveStage?.(null);
  }, [setActiveStage, stage]);
}
