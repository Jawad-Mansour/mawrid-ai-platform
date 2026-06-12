# Feature: Infrastructure — Backend Container
# Purpose: Multi-stage Docker build for FastAPI backend. Uses uv for
#          dependency installation. Dev stage mounts source; prod stage
#          copies and uses multiple uvicorn workers.

FROM ghcr.io/astral-sh/uv:latest AS uv-binary

FROM python:3.11-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_HTTP_TIMEOUT=300

RUN sed -i 's|http://deb.debian.org/debian$|http://ftp.de.debian.org/debian|' /etc/apt/sources.list.d/debian.sources \
    && echo 'Acquire::Retries "3";' > /etc/apt/apt.conf.d/80-retries \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv-binary /uv /usr/local/bin/uv

WORKDIR /app

# ── Dependencies stage ────────────────────────────────────────────────────────
FROM base AS deps
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev
RUN /opt/venv/bin/python -m spacy download en_core_web_sm && \
    /opt/venv/bin/python -m spacy download fr_core_news_sm

# ── Development stage (used by docker-compose.yml) ───────────────────────────
FROM deps AS development
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --dev
COPY backend/ .
EXPOSE 8000
CMD ["/opt/venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Production stage ──────────────────────────────────────────────────────────
FROM deps AS production
COPY backend/ .
EXPOSE 8000
CMD ["/opt/venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
