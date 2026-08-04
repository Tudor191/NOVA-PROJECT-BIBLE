# Build context is the repo root (docker build -f services/world-model-engine/Dockerfile .).
FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/nova-contracts/pyproject.toml packages/nova-contracts/pyproject.toml
COPY packages/nova-eventbus-sdk/pyproject.toml packages/nova-eventbus-sdk/pyproject.toml
COPY packages/nova-observability/pyproject.toml packages/nova-observability/pyproject.toml
COPY packages/nova-graphstore-sdk/pyproject.toml packages/nova-graphstore-sdk/pyproject.toml
COPY services/world-model-engine/pyproject.toml services/world-model-engine/pyproject.toml

COPY packages/nova-contracts packages/nova-contracts
COPY packages/nova-eventbus-sdk packages/nova-eventbus-sdk
COPY packages/nova-observability packages/nova-observability
COPY packages/nova-graphstore-sdk packages/nova-graphstore-sdk
COPY services/world-model-engine services/world-model-engine

RUN uv sync --frozen --no-dev --package world-model-engine

FROM python:3.12-slim
RUN useradd --create-home --uid 1000 nova
WORKDIR /app
COPY --from=builder --chown=nova:nova /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER nova

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/internal/health')"

CMD ["uvicorn", "nova_world_model_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]
