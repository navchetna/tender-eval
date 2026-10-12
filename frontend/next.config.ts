import type { NextConfig } from "next";

// NEXT_OUTPUT=export builds the desktop app's UI: a fully static site (frontend/out/) that the
// backend process serves itself next to the API (desktop/launcher.py) — no Node.js at runtime.
// trailingSlash emits /projects/index.html rather than /projects.html, so a plain static file
// server resolves every route without rewrite rules.
const desktopExport = process.env.NEXT_OUTPUT === "export";

const nextConfig: NextConfig = desktopExport
  ? { output: "export", trailingSlash: true }
  : {
      // Traces the minimal set of files/deps needed at runtime into .next/standalone, so the
      // production Docker image doesn't need to ship node_modules or run npm at all.
      output: "standalone",
    };

export default nextConfig;
