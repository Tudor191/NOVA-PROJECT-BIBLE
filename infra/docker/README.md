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

## Adding a new engine

1. `uv run python tools/scaffold-engine.py <name>-engine`.
2. Add a service block to this compose file (copy `nova-core`'s, change the
   Dockerfile path and container name).
3. Add a scrape target to `../observability/prometheus.yml`.
