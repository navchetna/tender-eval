"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { MatrixView } from "@/components/MatrixView";

function ProjectMatrix() {
  const projectId = useSearchParams().get("id");
  return projectId ? <MatrixView key={projectId} projectId={projectId} /> : null;
}

export default function MatrixPage() {
  return (
    <Suspense>
      <ProjectMatrix />
    </Suspense>
  );
}
