FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

# Compile bytecode for faster startup, copy instead of hardlinking (the venv is
# moved to another stage), and never download a Python the image doesn't have
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Install dependencies only (cached until pyproject.toml or uv.lock change)
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# Production image
FROM python:3.13-slim-bookworm AS runner

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Install curl for the health check and create a non-root user
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 1001 telescopium

COPY --from=builder --chown=telescopium /app/.venv ./.venv
COPY --chown=telescopium . .

USER telescopium

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=3s --retries=3 --start-period=5s \
    CMD curl -f http://localhost:5000/api/v1/health || exit 1

# Runs the API by default. Use `docker run telescopium solve` to override the command to export to a file.
ENTRYPOINT ["python", "main.py"]
CMD ["api", "0.0.0.0", "5000"]