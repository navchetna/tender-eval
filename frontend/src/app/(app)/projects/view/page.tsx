"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Workspace } from "@/components/Workspace";

function ProjectWorkspace() {
  const projectId = useSearchParams().get("id");
  // Keyed so switching projects remounts with fresh state, as a route change used to.
  return projectId ? <Workspace key={projectId} projectId={projectId} /> : null;
}

export default function ProjectPage() {
  return (
    <Suspense>
      <ProjectWorkspace />
    </Suspense>
  );
}
