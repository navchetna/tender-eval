# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies and copy source files
COPY ui/ ./
RUN \
  if [ -f package-lock.json ]; then npm ci; \
  elif [ -f pnpm-lock.yaml ]; then npm install -g pnpm && pnpm install; \
  elif [ -f yarn.lock ]; then yarn install --frozen-lockfile; \
  else npm install; fi

COPY . .

# Build the app
RUN npm run build

# Stage 2: Run Vite Preview
FROM node:20-alpine

WORKDIR /app

COPY --from=builder /app ./

EXPOSE 4173

CMD ["npm", "run", "preview"]
