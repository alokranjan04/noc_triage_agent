FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency resolution.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching.
COPY pyproject.toml uv.lock README.md ./

# Install dependencies (no dev deps in production).
RUN uv sync --no-dev --frozen

# Copy application code.
COPY noc_triage_agent/ noc_triage_agent/
COPY ui/ ui/
COPY evals/cases.yaml evals/cases.yaml

# Cloud Run sets PORT env var (default 8080).
ENV PORT=8080

EXPOSE 8080

CMD ["uv", "run", "python", "ui/app.py"]
