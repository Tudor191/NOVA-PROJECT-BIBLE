# infra/docker

Local-first deployment target (docs/architecture/14-deployment-architecture.md §2):
every backing store NOVA needs, plus the full observability stack, at zero cost.

## Quick start

```bash
docker compose -f infra/docker/docker-compose.local.yml up -d
curl localhost:8000/internal/health   # nova-core
open http://localhost:3000            # Grafana (anonymous viewer access enabled)
open http://localhost:9090            # Prometheus
```

No `.env` file is required -- every credential has a dev-only default baked into
`docker-compose.local.yml`. Copy `.env.local.example` to `.env.local` only if you
want to change one.

## What's running

| Service | Port(s) | Purpose |
|---|---|---|
| `postgres` | 5432 | Relational system of record (docs/architecture/07 §1). Image is `pgvector/pgvector:pg16`, **not** plain `postgres` -- memory-engine and knowledge-engine are "PostgreSQL + pgvector" per doc 07 §1/§3 and their migration 0001 opens with `CREATE EXTENSION IF NOT EXISTS vector`, which plain Postgres cannot satisfy |
| `neo4j` | 7474, 7687 | Knowledge Graph / World Object Graph (docs/architecture/07 §4) |
| `redis` | 6379 | Working memory, cache (docs/architecture/07 §5) |
| `minio` | 9000, 9001 | S3-compatible object storage |
| `nats` | 4222, 8222 | Event Bus, default `EventBus` backend (ADR-006) |
| `ollama` | 11434 | Local model inference (Roadmap Phase 2+) |
| `otel-collector` | 4317, 4318 | OTLP trace ingest -> Tempo |
| `tempo` | 3200 | Trace storage |
| `loki` | 3100 | Log storage |
| `prometheus` | 9090 | Metrics -- scrapes every engine's `/internal/metrics` directly |
| `grafana` | 3000 | Dashboards (provisioned: Prometheus/Tempo/Loki datasources + the NOVA Core Heartbeat dashboard) |
| `nova-core` | 8000 | NOVA's nervous system (services/nova-core) |
| `migrations` | -- | One-shot schema bootstrap; exits when done (see below) |
| `api-gateway` | 8014 | The one external REST surface (doc 11 §1) |
| `ws-gateway` | 8015 | The one bus-to-browser bridge (doc 09 §6) |
| `agent-os-kernel` | 8016 | Agent OS control plane (agent-os/kernel) |
| `agent-os-registry` | 8017 | Agent Package registry (agent-os/registry) |
| `agent-os-supervisors` | 8018 | Supervision tree (agent-os/supervisors) |

Thirteen engine services are omitted from the table for brevity; each exposes
`8001`-`8013` and its own `/internal/health`.

The three `agent-os` services were added in **Phase 4C (4C.1, decision D-5)**,
discharging the containerization half of Phase 3E's ratified condition **C-3**
— these components had no Dockerfile, no compose service and no Trivy scan for
their whole existence. `agent-os/sdk/python` is deliberately absent: it is a
library, like everything under `packages/`, and ships no image. Their published
ports are for local `/internal/health` inspection only — none is fronted by
`api-gateway`, whose route table 4C.1 does not touch.

## Schema bootstrap

`migrations` is a one-shot service that brings all fifteen Postgres-backed
component schemas to head, in sequence, then exits — thirteen engines, plus
`agent-os/kernel` and `agent-os/registry` since Phase 4C. Every Postgres-backed
service gates on it with:

```yaml
    depends_on:
      migrations:
        condition: service_completed_successfully
```

so none of them can start against an empty or partially-migrated database.

**Why it exists.** Until Phase 4A this stack had no migration step at all --
engines started against an empty database and exited during lifespan startup
(`relation "communication.conversation_session" does not exist`), which
`restart: unless-stopped` turned into a crash loop. The gap went unnoticed
because nothing had ever started the stack: CI's compose check runs `config
--quiet`, which parses the YAML and starts nothing. Phase 4A's Playwright job
was the first thing to actually run it.

**Why one container.** Each component image is built with `uv sync --package
<name>` and so contains exactly one component; none can migrate another.
`Dockerfile.migrations` installs the whole workspace, and `run-migrations.sh`
walks them in order -- keeping the sequence in one file, and keeping the
migrations strictly sequential by construction rather than by discipline.

**Why one database is safe.** Every component namespaces its own alembic
version table (`alembic_version_communication`, `alembic_version_memory`, ...,
`alembic_version_agent_os_kernel`, `alembic_version_agent_os_registry` -- 15
distinct names) and each migration `0001` issues its own `CREATE SCHEMA`. The
histories are independent by design. `alembic upgrade head` is idempotent, so
re-running the stack is a no-op.

`agent-os/kernel` and `agent-os/registry` are the only pair that share a schema
(`agent_os`); both create it with `IF NOT EXISTS`, so either may run first.
They were excluded from this script until Phase 4C for the reason the script
itself gave -- neither had a compose service -- and 4C.1 removed that premise.
`agent-os/supervisors` remains excluded permanently: it has no alembic config,
no `postgres_dsn` and an empty `repository/` (TDD 3E §7 names no persisted
state for it), so there is nothing to migrate.

## Adding a new engine

1. `uv run python tools/scaffold-engine.py <name>-engine`.
2. Add a service block to this compose file (copy `nova-core`'s, change the
   Dockerfile path and container name).
3. Add a scrape target to `../observability/prometheus.yml`.
4. If the engine is Postgres-backed, add it to the `ENGINES` array in
   `run-migrations.sh` **and** gate its compose service on `migrations` with
   `condition: service_completed_successfully`. Both are checked by
   `tools/tests/test_compose_migrations.py`, which fails if a Postgres-backed
   service is missing from either -- the alternative is an engine that
   crash-loops the moment someone starts the stack.
5. Add it to the `build-and-scan.yml` matrix, as a `{service, dockerfile}`
   entry. `tools/tests/test_build_and_scan_matrix.py` fails if any Dockerfile
   in the repository is in neither the matrix nor that file's `UNSCANNED` map
   -- an unmatrixed image is built by nothing and CVE-scanned by nothing, and
   nothing else reports its absence.

## Adding an `agent-os` component

`tools/scaffold-agent-os-component.py` deliberately generates no Dockerfile and
no compose service: doc 02 is explicit that `agent-os` components are
control-plane infrastructure rather than instances of the standard engine
template, and container wiring is conditional on a component actually shipping
as its own image. When one does, the steps are the engine steps above with two
differences:

- The compose service is named after the full path (`agent-os-kernel`, not
  `kernel`) -- a service called `registry` beside thirteen `*-engine` services
  would say nothing about which subsystem it belongs to.
  `tools/tests/test_compose_migrations.py::_compose_name_for` holds that
  mapping in one place.
- If the component resolves Agent Packages from disk (`Settings.agents_root`),
  its image needs `COPY agents agents`. Skipping it is silent for the Registry:
  `discover_agent_packages` returns `[]` for a missing directory, so the
  container starts, passes its healthcheck, and registers nothing.

`agent-os/sdk/python` is a library and gets neither, exactly like `packages/*`.
