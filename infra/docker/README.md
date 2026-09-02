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
| `postgres` | 5432 | Relational system of record (docs/architecture/07 §1) |
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

Thirteen engine services are omitted from the table for brevity; each exposes
`8001`-`8013` and its own `/internal/health`.

## Schema bootstrap

`migrations` is a one-shot service that brings all thirteen Postgres-backed
engine schemas to head, in sequence, then exits. Every Postgres-backed service
gates on it with:

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

**Why one container.** Each engine image is built with `uv sync --package
<engine>` and so contains exactly one engine; none can migrate another.
`Dockerfile.migrations` installs the whole workspace, and `run-migrations.sh`
walks the engines in order -- keeping the sequence in one file, and keeping the
migrations strictly sequential by construction rather than by discipline.

**Why one database is safe.** Every engine namespaces its own alembic version
table (`alembic_version_communication`, `alembic_version_memory`, ... -- 13
distinct names) and each migration `0001` issues its own `CREATE SCHEMA`. The
histories are independent by design. `alembic upgrade head` is idempotent, so
re-running the stack is a no-op.

`agent-os/kernel` and `agent-os/registry` have alembic configs but no compose
service, so they are deliberately not migrated here.

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
5. Add it to the `build-and-scan.yml` matrix.
