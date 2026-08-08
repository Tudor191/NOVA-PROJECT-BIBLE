# nova-service-kit

Shared FastAPI/SQLAlchemy infrastructure boilerplate -- health/readiness
routing, Postgres engine/session-factory construction, and the
transactional-outbox dispatch loop -- used identically by every engine that
has one, with **zero engine-specific knowledge of any kind** (ADR-034).

Built from `docs/design/nova-service-kit/boilerplate-extraction-proposal.md`,
the STEP 3 follow-up to the Project Health Review's (August 2026) ~700-line
structural boilerplate finding (`docs/roadmap/architecture-reviews/
project-health-review-2026-08.md` §18, §27.2).

## Scope

Three modules only, matching the three extractions this package was built to
hold. Nothing is added speculatively:

- **`health`** -- `make_health_router()`, a factory for the standard
  `/internal/health`/`/internal/readiness` router every engine exposes.
- **`db`** -- `create_engine()`/`create_session_factory()`, the standard
  async SQLAlchemy engine + session-factory construction every engine with a
  Postgres schema uses identically.
- **`outbox`** -- `dispatch_ready_events()`, the transactional-outbox
  dispatch loop shared by every engine that has one, parameterized over a
  `Protocol` so this package never imports any engine's own repository or
  metrics types.

## Explicitly out of scope

- No domain types, no business logic (that belongs in each engine's own
  `domain/`, or in `nova_contracts` for genuinely shared cross-engine
  vocabulary -- see the proposal's Extraction E, deliberately deferred).
- No Event Bus construction helpers (`nova_eventbus_sdk`'s
  `bind_event_bus()` already owns that).
- No tracing/metrics/logging setup (`nova-observability`'s job, unchanged).
- No test fixtures of any kind (`nova-testkit`'s job, unchanged -- ADR-033's
  dev-only boundary is untouched by this package's existence).

## Boundary rule (ADR-034)

Enforced by an import-linter contract: `nova_service_kit` may never import
any engine's own top-level package. Unlike `nova-testkit` (ADR-033,
dev/test-only), `nova-service-kit` **is a production dependency** -- every
consuming engine declares it under `[project] dependencies`, not
`[dependency-groups] dev`.

```python
from nova_service_kit.health import make_health_router
from nova_service_kit.db import create_engine, create_session_factory
from nova_service_kit.outbox import dispatch_ready_events, OutboxRepository
```

See `docs/architecture/adr/
ADR-034-shared-infrastructure-packages-carry-zero-engine-specific-knowledge.md`
for the full rationale, and the boilerplate extraction proposal for
per-extraction migration/testing strategy and the patterns deliberately left
duplicated (narrow ID+summary cross-engine value objects, `Goal`,
`HumanOverrideRequest`, the weighted composite scorer, `workers/__init__.py`'s
per-engine wiring).
