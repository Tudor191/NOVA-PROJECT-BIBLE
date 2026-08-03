# nova-core

NOVA's nervous system (Bible Part 20). Owns no business logic, stores no domain
knowledge, performs no reasoning -- its responsibility is orchestration.

## Responsibility

- The 7-phase boot sequence (`domain/boot.py`): bootstrap → data engines → cognitive
  engines → agents/capabilities → health checks → context sync → ready.
- The Module Registry (`domain/registry.py`): what engines exist and which boot phase
  they belong to. Empty in Phase 0 -- populated starting Roadmap Phase 1 as real
  engines are built.
- The Heartbeat (`domain/heartbeat.py`): periodic `nova.heartbeat` publication.

## Owned events

| Direction | Subject | Payload |
|---|---|---|
| Publishes | `nova.heartbeat` | `HeartbeatPayload` |
| Publishes | `nova.module.status_changed` | `ModuleStatusChangedPayload` |
| Publishes | `nova.mode.changed` | `ModeChangedPayload` (not yet emitted in Phase 0 -- no execution-mode switch exists until an engine needs one) |

See `events/published.py` / `events/subscribed.py` for the enforced allow-lists.

## Owned APIs

- `GET /internal/health` -- current status + uptime + boot phase.
- `GET /internal/readiness` -- whether the boot sequence reached `READY`.
- `GET /internal/metrics` -- Prometheus scrape endpoint.

Never exposed through the public API Gateway (docs/architecture/11-api-architecture.md §3).

## Running locally

```bash
# from the repo root
docker compose -f infra/docker/docker-compose.local.yml up -d nats
uv run --package nova-core uvicorn nova_core.main:app --reload --port 8000
curl localhost:8000/internal/health
```

Or, without a real NATS server, for quick local iteration:

```bash
EVENT_BUS_BACKEND=in_memory uv run --package nova-core uvicorn nova_core.main:app --port 8000
```

## Testing

```bash
uv run --package nova-core pytest services/nova-core/tests
```

`tests/unit/` exercises the boot sequence and heartbeat against the in-memory Event
Bus backend (no external services required). `tests/integration/` boots the real
FastAPI app (lifespan-driven) and hits its actual HTTP endpoints.
