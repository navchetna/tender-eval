# Build context is the repo root (see install/docker/docker-compose.yaml).
#
# NEXT_PUBLIC_API_BASE_URL is a build-time value: Next.js inlines every NEXT_PUBLIC_* var into
# the compiled JS during `next build`, so it cannot be changed by an env var at container start
# — pointing this image at a different backend requires rebuilding it with a different --build-arg.

FROM node:24-slim AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM node:24-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend .
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
# Same build-time-inlining caveat as above — see next.config.ts's basePath and Sidebar.tsx.
ARG NEXT_PUBLIC_BASE_PATH
ENV NEXT_PUBLIC_BASE_PATH=$NEXT_PUBLIC_BASE_PATH
RUN npm run build

# next.config.ts sets output: "standalone", so .next/standalone already contains a minimal
# server.js plus only the node_modules it actually needs — no npm/full node_modules required here.
FROM node:24-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
