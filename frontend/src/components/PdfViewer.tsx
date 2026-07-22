"use client";

import { useEffect, useState } from "react";
import { ApiError, getFilePdfBlobUrl } from "@/lib/api";
import { Empty } from "@/components/ui/Empty";

export function PdfViewer({ projectId, fileId }: { projectId: string; fileId: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    // Reset for the newly-selected file before the new fetch resolves.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setUrl(null);
    setError(null);
    getFilePdfBlobUrl(projectId, fileId)
      .then((blobUrl) => {
        if (cancelled) {
          URL.revokeObjectURL(blobUrl);
          return;
        }
        objectUrl = blobUrl;
        setUrl(blobUrl);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Failed to load PDF");
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [projectId, fileId]);

  if (error) return <Empty>{error}</Empty>;
  if (!url) return <Empty>Loading PDF…</Empty>;

  return <iframe src={url} title="Source PDF" className="h-[85vh] min-h-[600px] w-full rounded-[9px] border-[0.5px] border-line" />;
}
