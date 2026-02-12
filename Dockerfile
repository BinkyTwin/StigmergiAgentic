# =============================================================================
# StigmergiAgentic — Docker image for tests & migrations
# Sprint 2.5 — Reproducible containerized execution
# =============================================================================
#
# Build:   docker build -t stigmergic-poc .
# Test:    docker run --rm stigmergic-poc
# Shell:   docker run --rm -it stigmergic-poc /bin/bash
#

# --------------- Stage 1: builder ---------------
FROM python:3.11-slim AS builder

# Install uv for fast, reproducible dependency resolution
RUN pip install --no-cache-dir uv

WORKDIR /build

# Copy dependency manifest first (layer caching)
COPY requirements.txt .

# Create venv and install dependencies via uv
RUN uv venv /opt/venv --python python3.11 \
    && . /opt/venv/bin/activate \
    && uv pip install -r requirements.txt

# --------------- Stage 2: runner ---------------
FROM python:3.11-slim AS runner

# Install git (needed by agents for Git operations)
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv

# Activate virtualenv
ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV="/opt/venv" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy project source code
COPY . .

# Default: run the full test suite
CMD ["pytest", "tests/", "-v"]
