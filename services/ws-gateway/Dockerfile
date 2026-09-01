# Build context is the repo root (docker build -f services/ws-gateway/Dockerfile .).
FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/nova-contracts/pyproject.toml packages/nova-contracts/pyproject.toml
COPY packages/nova-eventbus-sdk/pyproject.toml packages/nova-eventbus-sdk/pyproject.toml
COPY packages/nova-observability/pyproject.toml packages/nova-observability/pyproject.toml
COPY services/ws-gateway/pyproject.toml services/ws-gateway/pyproject.toml

COPY packages/nova-contracts packages/nova-contracts
COPY packages/nova-eventbus-sdk packages/nova-eventbus-sdk
COPY packages/nova-observability packages/nova-observability
COPY services/ws-gateway services/ws-gateway

RUN uv sync --frozen --no-dev --package ws-gateway

FROM python:3.12-slim
RUN useradd --create-home --uid 1000 nova
WORKDIR /app
COPY --from=builder --chown=nova:nova /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER nova

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/internal/health')"

CMD ["uvicorn", "nova_ws_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
