# Build context is the repo root (docker build -f agent-os/registry/Dockerfile .).
#
# Phase 4C milestone 4C.1, decision D-5 -- discharging the containerization
# half of Phase 3E's ratified condition C-3. First container and first Trivy
# scan for this component.
#
# `agents/` is copied for a stronger reason here than in the Kernel image:
# `main.py`'s lifespan calls `discover_agent_packages(Path(settings.agents_root))`
# at startup and runs the real 8-step install pipeline over what it finds, and
# `discover_agent_packages` returns `[]` for a missing directory rather than
# raising. Without this COPY the container would start cleanly, pass its
# healthcheck, and register zero Agent Packages -- a silent no-op, which is the
# worst of the available failure modes. Agent Packages are not workspace
# members (doc 02 :162-169), so they are copied as plain files and never
# installed; the pipeline's Sandbox Test stage imports `src/handler.py`
# dynamically, and those handlers import only `nova_agent_sdk` and
# `nova_contracts`, both of which this image already carries. The COPY is
# placed after `uv sync` so editing an Agent Package does not invalidate the
# dependency layer.
FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/nova-contracts/pyproject.toml packages/nova-contracts/pyproject.toml
COPY packages/nova-eventbus-sdk/pyproject.toml packages/nova-eventbus-sdk/pyproject.toml
COPY packages/nova-observability/pyproject.toml packages/nova-observability/pyproject.toml
COPY packages/nova-service-kit/pyproject.toml packages/nova-service-kit/pyproject.toml
COPY agent-os/sdk/python/pyproject.toml agent-os/sdk/python/pyproject.toml
COPY agent-os/registry/pyproject.toml agent-os/registry/pyproject.toml

COPY packages/nova-contracts packages/nova-contracts
COPY packages/nova-eventbus-sdk packages/nova-eventbus-sdk
COPY packages/nova-observability packages/nova-observability
COPY packages/nova-service-kit packages/nova-service-kit
COPY agent-os/sdk/python agent-os/sdk/python
COPY agent-os/registry agent-os/registry

RUN uv sync --frozen --no-dev --package registry

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

CMD ["uvicorn", "nova_agent_os_registry.main:app", "--host", "0.0.0.0", "--port", "8000"]
