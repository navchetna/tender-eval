"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { Sidebar } from "@/components/Sidebar";
import { PipelineRibbon } from "@/components/PipelineRibbon";
import { ActiveStageContext } from "@/lib/activeStageContext";
import { PendingReviewCountProvider } from "@/lib/pendingReviewCountContext";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [activeStage, setActiveStage] = useState<number | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) return null;

  return (
    <PendingReviewCountProvider>
      <ActiveStageContext.Provider value={setActiveStage}>
        <div className="relative flex h-screen overflow-hidden bg-canvas">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <PipelineRibbon activeStage={activeStage} />
            <main className="flex-1 overflow-auto">{children}</main>
          </div>
        </div>
      </ActiveStageContext.Provider>
    </PendingReviewCountProvider>
  );
}
