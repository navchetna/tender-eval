import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Traces the minimal set of files/deps needed at runtime into .next/standalone, so the
  // production Docker image doesn't need to ship node_modules or run npm at all.
  output: "standalone",
  // Serves this app under a sub-path of the enterprise agent toolkit's own shared ingress
  // host (ei-api.mg2.eglb.intel.com/tender-eval) instead of needing a separate DNS entry —
  // see install/k8s/ingress.yaml and install/k8s/README.md. Inlined into the client bundle
  // at build time (verified against node_modules/next/dist/docs/.../basePath.md for this
  // project's pinned Next.js 16 — see frontend/AGENTS.md), so changing it requires a rebuild.
  //
  // Sourced from NEXT_PUBLIC_BASE_PATH (build arg — see Dockerfile), same pattern as
  // NEXT_PUBLIC_API_BASE_URL, so this and any component that needs to prefix a plain
  // /public asset path (Next.js does NOT auto-prefix those — see Sidebar.tsx) share one
  // source of truth instead of drifting apart. Empty default preserves plain `npm run dev`
  // behavior (served at "/", no prefix) when the build arg isn't set.
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || "",
};

export default nextConfig;
