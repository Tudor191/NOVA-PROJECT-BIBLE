# Build context is the repo root (docker build -f services/cognitive-state-engine/Dockerfile .).
FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/nova-contracts/pyproject.toml packages/nova-contracts/pyproject.toml
COPY packages/nova-eventbus-sdk/pyproject.toml packages/nova-eventbus-sdk/pyproject.toml
COPY packages/nova-observability/pyproject.toml packages/nova-observability/pyproject.toml
COPY packages/nova-service-kit/pyproject.toml packages/nova-service-kit/pyproject.toml
COPY services/cognitive-state-engine/pyproject.toml services/cognitive-state-engine/pyproject.toml

COPY packages/nova-contracts packages/nova-contracts
COPY packages/nova-eventbus-sdk packages/nova-eventbus-sdk
COPY packages/nova-observability packages/nova-observability
COPY packages/nova-service-kit packages/nova-service-kit
COPY services/cognitive-state-engine services/cognitive-state-engine

RUN uv sync --frozen --no-dev --package cognitive-state-engine

FROM python:3.12-slim
# Force OS packages to their latest Debian-patched versions at build time,
# regardless of how stale the base image's own layers are. Established by
# `97fa103` (2026-08-17), which added this exact line to all 12 then-existing
# matrix images to close CVE-2026-53615, and asserted by
# `tools/tests/test_dockerfile_runtime_hardening.py`. Trivy scans every matrix
# image at CRITICAL,HIGH with `exit-code: 1`, so an image without this line
# fails the build the day Debian publishes a fixed CVE against the base.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 1000 nova
WORKDIR /app
COPY --from=builder --chown=nova:nova /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER nova

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/internal/health')"

CMD ["uvicorn", "nova_cognitive_state_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]
