# Build context is the repo root (docker build -f agent-os/kernel/Dockerfile .).
#
# Phase 4C milestone 4C.1, decision D-5 -- discharging the containerization
# half of Phase 3E's ratified condition C-3. This is the first container this
# component has ever had, and therefore its first Trivy scan.
#
# Structurally identical to `services/<name>/Dockerfile`; two additions, both
# real runtime requirements rather than style:
#
#   * `agent-os/sdk/python` (`nova-agent-sdk`) is copied because
#     `domain/ports.py`, `domain/scheduler.py` and `domain/execution_backend.py`
#     import it. It was undeclared until 4C.1 -- see this component's own
#     `pyproject.toml` for the full disclosure.
#
#   * `agents/` is copied because `Settings.agents_root` defaults to `"agents"`,
#     resolved against the process's CWD (`/app`), and
#     `InprocessExecutionBackend` loads a dispatched instance's
#     `agents/<manifest id>/src/handler.py` from that root. Agent Packages are
#     not workspace members (doc 02 :162-169) and have no `pyproject.toml`, so
#     they are copied as plain files and never installed. The COPY is placed
#     after `uv sync` deliberately: editing an Agent Package must not
#     invalidate the dependency layer.
FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/nova-contracts/pyproject.toml packages/nova-contracts/pyproject.toml
COPY packages/nova-eventbus-sdk/pyproject.toml packages/nova-eventbus-sdk/pyproject.toml
COPY packages/nova-observability/pyproject.toml packages/nova-observability/pyproject.toml
COPY packages/nova-service-kit/pyproject.toml packages/nova-service-kit/pyproject.toml
COPY agent-os/sdk/python/pyproject.toml agent-os/sdk/python/pyproject.toml
COPY agent-os/kernel/pyproject.toml agent-os/kernel/pyproject.toml

COPY packages/nova-contracts packages/nova-contracts
COPY packages/nova-eventbus-sdk packages/nova-eventbus-sdk
COPY packages/nova-observability packages/nova-observability
COPY packages/nova-service-kit packages/nova-service-kit
COPY agent-os/sdk/python agent-os/sdk/python
COPY agent-os/kernel agent-os/kernel

RUN uv sync --frozen --no-dev --package kernel

COPY agents agents

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

CMD ["uvicorn", "nova_agent_os_kernel.main:app", "--host", "0.0.0.0", "--port", "8000"]
