import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Traces the minimal set of files/deps needed at runtime into .next/standalone, so the
  // production Docker image doesn't need to ship node_modules or run npm at all.
  output: "standalone",
};

export default nextConfig;
