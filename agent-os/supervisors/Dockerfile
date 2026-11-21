# Build context is the repo root (docker build -f agent-os/supervisors/Dockerfile .).
#
# Phase 4C milestone 4C.1, decision D-5 -- discharging the containerization
# half of Phase 3E's ratified condition C-3. First container and first Trivy
# scan for this component.
#
# The leanest of the three images, and deliberately so:
#
#   * No `agents/` COPY. This component never resolves an Agent Package from
#     disk -- it has no `agents_root` setting. It serves two RPCs
#     (`agent_os.supervisor.restart_plan.request`,
#     `agent_os.supervisor.peer_review.request`) and holds no filesystem state.
#
#   * No database dependency of any kind. TDD 3E §7 names no persisted state
#     for the Supervisor, `config.py` records that decision in full, and the
#     component has no alembic chain, no `postgres_dsn`, and an empty
#     `repository/`. Phase 4C does not change that (approved 2026-09-07), so
#     this image needs neither `sqlalchemy`, `asyncpg`, nor `alembic`, and the
#     compose service depends on `nats` alone.
FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/nova-contracts/pyproject.toml packages/nova-contracts/pyproject.toml
COPY packages/nova-eventbus-sdk/pyproject.toml packages/nova-eventbus-sdk/pyproject.toml
COPY packages/nova-observability/pyproject.toml packages/nova-observability/pyproject.toml
COPY packages/nova-service-kit/pyproject.toml packages/nova-service-kit/pyproject.toml
COPY agent-os/sdk/python/pyproject.toml agent-os/sdk/python/pyproject.toml
COPY agent-os/supervisors/pyproject.toml agent-os/supervisors/pyproject.toml

COPY packages/nova-contracts packages/nova-contracts
COPY packages/nova-eventbus-sdk packages/nova-eventbus-sdk
COPY packages/nova-observability packages/nova-observability
COPY packages/nova-service-kit packages/nova-service-kit
COPY agent-os/sdk/python agent-os/sdk/python
COPY agent-os/supervisors agent-os/supervisors

RUN uv sync --frozen --no-dev --package supervisors

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

CMD ["uvicorn", "nova_agent_os_supervisors.main:app", "--host", "0.0.0.0", "--port", "8000"]
