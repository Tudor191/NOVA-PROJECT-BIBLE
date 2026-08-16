# capability-engine

Bible Part 15's Capability Engine (`docs/design/phase-3/06-tdd-3c-capability-engine.md`)
-- the registry, real 8-stage installation pipeline, and OS-level
sandboxing for NOVA's capabilities. Owns and executes the four Phase 3
built-in capabilities (`git`, `filesystem`, `terminal`, `http`); every
other engine (`action-engine`, in a later phase) reaches them only via
`capability.resolve.*`/`capability.invoke.*` request/reply RPCs, never by
importing this engine's own execution logic (ADR-004).

## Architecture

**Fork 3C-1/3D-1 (Option A):** this engine's own process owns and executes
every adapter. `action-engine`'s future `CapabilityPort`/client (a
separate, later phase) is the caller, not built here.

**Fork 3C-2 (Option C):** `AgentContext.granted_capabilities` (agent-os,
a separate, later phase) is a declared-intent field only. This engine
introduces no capability cache, subscription, or second authorization
authority -- `action-engine` remains the sole live authorization check.

**Fork 3C-3 (Option B):** rollback/undo of a capability's own side effects
is `action-engine`'s own future responsibility (read-before-write against
this engine's existing non-destructive operations). This engine's adapter
interface has no snapshot/restore primitive.

**Fork 3C-4 (Option B):** `POST /v1/capabilities/install` is idempotent on
the natural key `(name, version)` -- a `UNIQUE (name, version)` Postgres
constraint backs this; a concurrent-install race is caught and treated as
the same idempotent no-op, never a duplicate row or a hard failure.

## Installation pipeline

Eight real stages (`domain/pipeline.py`): Download -> Integrity
Verification -> Dependency Resolution -> Permission Review -> Sandbox
Testing -> Registration -> Health Check -> Activation. Sandbox Testing
runs a real, adversarial out-of-scope probe against the resolved adapter
before a capability is ever registered -- an adapter that fails to block
its own probe never reaches Registration/Activation (TDD 3C's own
acceptance criterion 2).

## Sandboxing

Fork E3's approved lighter OS-level scoping (no gVisor/Firecracker/
container isolation): a filesystem path allow-list (`filesystem`/`git`,
checked against the canonicalized/resolved path), a terminal executable
allow-list (`terminal`/`git`, `asyncio.create_subprocess_exec`, never
`shell=True`), and an outbound-host allow-list (`http`).

**Known, disclosed limitation:** none of these primitives prevent a
`terminal`/`git` capability's own spawned subprocess from making its own
outbound network calls, bypassing the `http` adapter's host allow-list
entirely. Closing that fully would require process-level network
isolation (network namespaces/firewall rules) -- a heavier mechanism than
Fork E3's approved lighter scoping, not implemented here.

## Owned events

| Direction | Subject | Payload |
|---|---|---|
| Served (RPC) | `capability.resolve.request` | Looks up a `Capability` by id. |
| Served (RPC) | `capability.invoke.request` | Invokes an operation against a registered capability's resolved adapter. |
| Requests (outbound, RPC) | `communication.session.lookup_by_user.request`, `communication.intent.deliver.request` | The Permission Review pipeline stage's best-effort install disclosure (Fork D precedent) -- skipped entirely when `CAPABILITY_ENGINE_PRIMARY_USER_ID` is unset. |

See `events/published.py` / `events/subscribed.py` for the enforced
allow-lists.

## Owned APIs

- `GET /v1/capabilities` -- list every registered capability.
- `POST /v1/capabilities/install` -- idempotent install via the real
  8-stage pipeline.
- `DELETE /v1/capabilities/{id}` -- remove a registered capability.
- `GET /internal/health`
- `GET /internal/readiness`
- `GET /internal/metrics`

Exposed directly (no `api-gateway` yet -- same stopgap precedent as every
other Phase 3 engine).

## Bootstrap

The four built-ins are installed through the real pipeline at startup
(`main.py`'s lifespan), not hardcoded pre-registered rows -- deployment
settings (`sandbox_filesystem_root`, `sandbox_terminal_allowed_executables`,
`sandbox_http_allowed_hosts`) determine each one's declared scope.

## Testing

```bash
uv run --package capability-engine pytest -m "not real_infra" services/capability-engine/tests
```

Real-Postgres persistence tests (`tests/integration/test_repository_real_postgres.py`)
are marked `real_infra` and require Docker (`testcontainers`) -- run
explicitly with `-m real_infra`.
