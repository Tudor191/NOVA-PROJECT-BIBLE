# Build context is the repo root (docker build -f services/planning-engine/Dockerfile .).
FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/nova-contracts/pyproject.toml packages/nova-contracts/pyproject.toml
COPY packages/nova-eventbus-sdk/pyproject.toml packages/nova-eventbus-sdk/pyproject.toml
COPY packages/nova-observability/pyproject.toml packages/nova-observability/pyproject.toml
COPY packages/nova-service-kit/pyproject.toml packages/nova-service-kit/pyproject.toml
COPY services/planning-engine/pyproject.toml services/planning-engine/pyproject.toml

COPY packages/nova-contracts packages/nova-contracts
COPY packages/nova-eventbus-sdk packages/nova-eventbus-sdk
COPY packages/nova-observability packages/nova-observability
COPY packages/nova-service-kit packages/nova-service-kit
COPY services/planning-engine services/planning-engine

RUN uv sync --frozen --no-dev --package planning-engine

FROM python:3.12-slim
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 1000 nova
WORKDIR /app
COPY --from=builder --chown=nova:nova /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER nova

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/internal/health')"

CMD ["uvicorn", "nova_planning_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]
