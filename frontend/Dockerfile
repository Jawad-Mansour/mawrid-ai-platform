# Feature: Infrastructure — Frontend Container
# Purpose: Multi-stage Docker build for Vite + React 18 frontend.
#          Dev: vite dev server on port 3000.
#          Production: nginx serving the static dist/ bundle.

FROM node:20-alpine AS base
WORKDIR /app

# ── Dependencies stage ────────────────────────────────────────────────────────
FROM base AS deps
COPY package.json package-lock.json* ./
RUN npm install

# ── Build stage (production only) ─────────────────────────────────────────────
FROM deps AS builder
COPY . .
RUN npm run build

# ── Production stage ──────────────────────────────────────────────────────────
FROM nginx:alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

# ── Development stage ─────────────────────────────────────────────────────────
FROM deps AS development
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
