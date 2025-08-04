# Stage 1: Build
FROM node:20-alpine AS builder
ARG SERVER_URL
WORKDIR /app

# Install dependencies and copy source files
COPY ui/ ./
COPY ui/package*.json ./
RUN npm install

COPY . .

# Build the app
ENV VITE_SERVER_URL=$SERVER_URL
RUN npm run build

# Stage 2: Run Vite Preview
FROM node:20-alpine

WORKDIR /app

COPY --from=builder /app ./

EXPOSE 4173

CMD ["npm", "run", "preview"]
