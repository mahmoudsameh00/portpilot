# The PortPilot API / scheduler image (Staging readiness plan P3, ADR-071). One image, two services in
# deploy/compose.yaml: `api` (Serve.py) and `scheduler` (Scheduler_service.py, which runs the scheduled CLIs).
# Build (from the project root):  docker build -f ops/docker/api.Dockerfile -t portpilot-api:<tag> .
# Context rules: ops/docker/api.Dockerfile.dockerignore (no .env, no Data/raw, no caches, no models, no reports).
# Runtime: a non-root user, a read-only root filesystem (compose), the mutable folders as volumes:
#   /app/reports  /app/Data/processed/agents/eval/llm_cache  /app/Data/processed/agents/tool_cache
#   /app/Data/embeddings/gemini-embedding-2/cache_queries  /app/Data/incoming
#   /app/Data/processed/semi-structured/synthetic (the voyage file, git-ignored)  /app/models (the local bge-m3, ro)
# Python = the owner's 3.13.5 (the lock was resolved and every check run on it).

# syntax=docker/dockerfile:1
FROM python:3.13.5-slim-bookworm AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10
# pip's download cache lives in a BuildKit cache mount: it survives a failed build, so a retry on a slow or broken
# line continues from the wheels already fetched (2026-11-17: a 3.6 h build lost 124 wheels to one cut download)
RUN --mount=type=cache,target=/root/.cache/pip pip install uv==0.12.15
WORKDIR /app
COPY pyproject.toml uv.lock ./
# The locked runtime packages only (no dev group: ruff / pyright stay in the CI). uv turns the lock into a hashed
# requirements list (offline); pip installs it with --require-hashes (2026-11-17: uv's own parallel downloads stalled
# on the owner's slow line, pip's did not — same versions, same hash check).
RUN --mount=type=cache,target=/root/.cache/pip \
    uv export --frozen --no-dev --no-emit-project --format requirements-txt -o /tmp/requirements.txt \
    && python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-deps --require-hashes -r /tmp/requirements.txt \
    && /opt/venv/bin/python -m compileall -q /opt/venv/lib

FROM python:3.13.5-slim-bookworm AS run
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    MPLCONFIGDIR=/tmp/matplotlib \
    HOME=/tmp
# No apt: time zones come from the locked `tzdata` wheel through zoneinfo (every schedule names Africa/Cairo
# explicitly); the container clock stays UTC.
RUN groupadd --system --gid 10001 portpilot \
    && useradd --system --uid 10001 --gid portpilot --home-dir /tmp --shell /usr/sbin/nologin portpilot
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY pyproject.toml uv.lock ./
COPY pipelines ./pipelines
COPY Data ./Data
COPY db/migrations ./db/migrations
# the mount points of the volumes, owned by the runtime user (a fresh named volume copies this ownership)
RUN mkdir -p reports/_log Data/processed/agents/eval/llm_cache Data/processed/agents/tool_cache \
             Data/embeddings/gemini-embedding-2/cache_queries Data/incoming \
             Data/processed/semi-structured/synthetic models/onnx \
    && chown -R portpilot:portpilot reports Data/processed/agents/eval/llm_cache Data/processed/agents/tool_cache \
             Data/embeddings/gemini-embedding-2/cache_queries Data/incoming Data/processed/semi-structured/synthetic \
             models
USER portpilot
ENV PORTPILOT_ENV=staging \
    API_BIND_HOST=0.0.0.0
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=4).status == 200 else 1)"]
CMD ["python", "pipelines/scripts/api/Serve.py", "--port", "8000"]
