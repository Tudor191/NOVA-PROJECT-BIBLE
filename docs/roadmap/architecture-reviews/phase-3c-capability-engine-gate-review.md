# Phase 3C — `capability-engine`: Gate Review

**Status: implementation complete, locally verified, real GitHub Actions
CI green. Covers the whole of Phase 3C's scope as authorized** (branch
`phase-3c-capability-engine`, based directly on `phase-3b-planning-domain`)
— a single PR, not split across multiple units. Real-infrastructure
(Postgres) and Docker-build verification could not run in this local
environment (no reachable Docker daemon); real GitHub Actions CI supplied
that verification instead — see §9 for exactly what ran where.

**Post-initial-review correction:** PR #8's first CI run showed "Real
-Infrastructure Checks" green, but that workflow's matrix did not include
`capability-engine` at all — its "success" covered five other packages,
not this engine's own real-Postgres tests. Fixed by adding a
`capability-engine` matrix entry (`.github/workflows/real-infra-checks.yml`);
§9 reflects the corrected, re-verified state, not the original
misleading-green result.

---

## 0. Scope executed

Full implementation of TDD 3C (`docs/design/phase-3/06-tdd-3c-capability-engine.md`):

- `nova_contracts.events.capability` — `Capability`, `CapabilityHandle`,
  `capability.resolve.*`/`capability.invoke.*` request/reply payloads.
- `services/capability-engine` — domain layer (`Capability`/`CapabilityHandle`
  usage, `CapabilityManifest`, the real 8-stage installation pipeline,
  sandboxing primitives, the four built-in adapters), PostgreSQL
  persistence (`capability` schema, hand-written Alembic migration),
  `GET`/`POST /install`/`DELETE /v1/capabilities`, served
  `capability.resolve.request`/`capability.invoke.request` RPCs, an
  outbound `CommunicationClient` for the Permission Review disclosure,
  observability metrics, and the full test suite (unit/contract/
  integration/real-infra).
- Infra wiring: `docker-compose.local.yml`, `build-and-scan.yml` matrix,
  `Dockerfile` (missing `nova-service-kit` copy step, fixed — same defect
  class `fix-dockerfiles-nova-service-kit` fixed for every prior engine;
  `capability-engine` did not exist yet when that PR ran).

## 1. Architectural decisions implemented, exactly as approved

**Fork 3C-1/3D-1 (Option A):** `capability-engine`'s own process owns and
executes every adapter (`adapters/filesystem_adapter.py`,
`terminal_adapter.py`, `git_adapter.py`, `http_adapter.py`). No
`action-engine`-side `CapabilityPort`/client is built here — `main.py`
only serves `capability.resolve.request`/`capability.invoke.request` via
`BoundEventBus.serve()`, mirroring `ai-model-orchestration-engine`'s own
`ai_model.generate.request` precedent exactly.

**Fork 3C-2 (Option C):** not implemented here by design — `AgentContext`/
`granted_capabilities` live in `agent-os` (Phase 3E), out of this PR's
scope entirely. Nothing in this implementation introduces a capability
cache, a subscription, or a second authorization authority.

**Fork 3C-3 (Option B):** no rollback/snapshot primitive exists on
`AdapterPort` or anywhere in this engine. `domain/ports.py`'s own
`AdapterPort.invoke()` docstring states this explicitly.

**Fork 3C-4 (Option B):** `install_capability()`
(`domain/pipeline.py`) checks `find_by_name_version` before running any
stage and returns the existing row unchanged if found. The Postgres
schema enforces `UNIQUE (name, version)`
(`uq_capability_name_version`); a concurrent-install race that beats the
pre-check is caught via `CapabilityAlreadyExistsError` and resolved
identically to the pre-check path — verified directly by
`test_a_concurrent_install_race_is_treated_as_the_same_idempotent_no_op`
(`tests/unit/test_pipeline.py`), not merely asserted.

## 2. Capability model and `CapabilityHandle`

Implemented verbatim per the approved 13-field shape
(`nova_contracts.events.capability.Capability`): `id`, `name`,
`description`, `category`, `version`, `dependencies`,
`required_permissions`, `required_resources`, `input_schema`,
`output_schema`, `execution_adapter`, `health_status`, `installed_at`.
`Supported Platforms` stays deferred, as approved. `CapabilityHandle`
(`capability_id`, `name`, `execution_adapter`) is a separate, minimal
type — never independently published as an Event Bus payload, embedded
in-process only (per the `inprocess`-backend reasoning already settled in
research).

## 3. Contracts added

`packages/nova-contracts/src/nova_contracts/events/capability.py` (new
module):

| Type | Registered subject | Notes |
|---|---|---|
| `Capability` | — (entity, not a payload) | The 13-field model above. |
| `CapabilityHandle` | — (entity, not a payload) | |
| `CapabilityResolveRequestPayload` | `capability.resolve.request` | `capability_id`, `requesting_engine`, `correlation_id`, `schema_version`. |
| `CapabilityResolveReplyPayload` | `capability.resolve.reply` | `found: bool`, `capability: Capability \| None`. |
| `CapabilityInvokeRequestPayload` | `capability.invoke.request` | `capability_id`, `operation`, `parameters`, `requesting_engine`, `correlation_id`, `schema_version`. |
| `CapabilityInvokeReplyPayload` | `capability.invoke.reply` | `outcome: "success" \| "failure" \| "sandbox_violation"`, `result`, `error`. |

No capability pub/sub events were created (these are request/reply RPC
subjects only, per explicit instruction). No Phase 3D/3E contracts were
added.

## 4. Persistence

New `capability` Postgres schema (`repository/models.py`,
`alembic/versions/0001_initial_schema.py`, hand-written to match the ORM
model exactly, `version_table="alembic_version_capability"` per this
project's cross-engine-Alembic-collision convention):

- `capability.capability` — the `Capability` model's 13 fields plus
  `permissions_reviewed_at`/`sandbox_test_passed_at` pipeline-stage
  bookkeeping (TDD 3C §6). `UNIQUE (name, version)` — Fork 3C-4's
  enforcement mechanism.
- `capability.capability_installation_event` — append-only pipeline-stage
  transition log (`ConversationDecisionTraceORM` precedent).

`PostgresCapabilityRepository` implements `domain.ports.CapabilityRepository`
in full, including the `IntegrityError` -> `CapabilityAlreadyExistsError`
translation Fork 3C-4 depends on — the first such uniqueness-violation
translation in this codebase (mechanical consequence of an already-approved
decision, not a new architectural choice).

## 5. Installation pipeline

`domain/pipeline.py::install_capability()` implements the real 8 stages
(Download -> Integrity Verification -> Dependency Resolution -> Permission
Review -> Sandbox Testing -> Registration -> Health Check -> Activation):

- **Dependency Resolution** checks every declared dependency is already
  registered and that the resulting graph stays acyclic
  (`_find_dependency_cycle`, a local DFS reimplementation of
  `planning-engine`'s own `TaskGraph.find_cycle` pattern — closes a gap
  TDD 3C's own text leaves silent).
- **Permission Review** is a best-effort disclosure via the existing
  `communication.intent.deliver.request` gate (Fork D precedent), gated
  by `Settings.primary_user_id` (unset = skipped, not silently sent
  nowhere — `perception-engine`'s own precedent, reused verbatim).
  `TimeoutError` is caught here and recorded, never propagated as a
  pipeline failure.
- **Sandbox Testing** runs a real, adversarial out-of-scope probe
  (`_out_of_scope_probe`/`_sandbox_self_test`) against the resolved
  adapter before any capability is registered. An adapter that fails to
  block its own probe halts the pipeline with `InstallationError` — never
  silently registers (TDD 3C's own acceptance criterion 2, verified by
  `test_an_adapter_that_fails_to_enforce_its_own_sandbox_never_reaches_registration`
  against a deliberately broken fake adapter).
- **Health Check** is a registry-persistence readback, distinct from
  Sandbox Testing's already-completed scope check.

`on_stage` is an optional callback parameter (mirrors `reasoning-engine`'s
own `pipeline.run`'s `on_stage` precedent) so `main.py` can increment
`capability_install_pipeline_stage_total{stage=..., outcome=...}` without
`domain/` importing an observability framework.

## 6. Sandboxing (Fork E3, made concrete)

`domain/sandbox.py`: `resolve_within_roots` (canonicalized-path
allow-list, closes a `../`/symlink-traversal gap), `check_executable_allowed`,
`check_host_allowed`. Composed by all four adapters — never a fifth,
independent mechanism.

- **`filesystem`**: path-prefix allow-list, checked against the resolved
  path, on every read/write/list.
- **`terminal`**: executable allow-list, restricted minimal environment,
  hard timeout, `asyncio.create_subprocess_exec` (never `shell=True`).
- **`git`**: git-subcommand allow-list plus filesystem-style repo-root
  scoping; composes `TerminalAdapter.run_subprocess` directly (a public
  method, not a private-attribute reach-through).
- **`http`**: outbound-host allow-list, checked before any request is
  made; `httpx.AsyncClient` lazily imported and injectable
  (`httpx.MockTransport`-testable, mirrors `ollama_connector.py`).

**Disclosed limitation, unchanged from TDD 3C's own text:** none of these
primitives prevent a `terminal`/`git` capability's own spawned subprocess
from making its own outbound network calls, bypassing the `http`
adapter's host allow-list entirely. Closing that fully requires
process-level network isolation — a heavier mechanism than Fork E3's
approved lighter scoping, not implemented here, and not silently implied
to be full isolation.

## 7. API surface

Exposed directly (no `api-gateway` yet, same stopgap as every Phase 3
engine): `GET /v1/capabilities`, `POST /v1/capabilities/install`
(idempotent, 201, returns the existing row on repeat), `DELETE
/v1/capabilities/{id}` (204, 404 if unknown). Plus the standard
`nova-service-kit`-style `/internal/health`, `/internal/readiness`,
`/internal/metrics`.

## 8. Event-bus request/reply implementation

`main.py`'s `_make_resolve_request_handler`/`_make_invoke_request_handler`
mirror `ai-model-orchestration-engine`'s own `_make_generate_request_handler`
pattern exactly: registered via `bus.serve(subject, handler,
source_engine=...)` inside `create_app`'s lifespan, right after
`bus.connect()`. The invoke handler resolves the adapter via
`capability.execution_adapter`, catches `SandboxViolation` (->
`outcome="sandbox_violation"`, increments
`capability_sandbox_violation_blocked_total`) and any other adapter
exception (-> `outcome="failure"`, TDD 3C §8's "structured failure
returned to the caller," never a crash) separately from a genuine
success. `events/published.py`/`events/subscribed.py` enforce the
allow-lists in both directions.

## 9. Testing and verification results

| Check | Result | Classification |
|---|---|---|
| `capability-engine` ruff + mypy (`src`) | Clean, 28 source files | Fully verified |
| `capability-engine` test suite (`-m "not real_infra"`) | 59/59 passed | Fully verified |
| `capability-engine` domain coverage | 97% (`domain/pipeline.py` 96%, every other domain module 100%) vs. 85% gate | Fully verified (`--cov-report=term-missing`, branch coverage per root `pyproject.toml`) |
| Full monorepo test suite (12 Python-engine packages) | All green, no regressions from this PR's `nova_contracts`/root-`pyproject.toml` changes | Fully verified |
| import-linter | 6/6 contracts kept — `nova_capability_engine` correctly independent, and (ADR-020) forbidden from importing any AI-provider SDK | Fully verified |
| `docker-compose config` | Valid with the new `capability-engine` service block | Fully verified (syntax only — no daemon reachable to actually start it) |
| TypeScript codegen | 80 files generated, 4 new (`CapabilityInvokeReplyPayload`, `CapabilityInvokeRequestPayload`, `CapabilityResolveReplyPayload`, `CapabilityResolveRequestPayload`), `index.ts` updated | Fully verified |
| Alembic migration | Hand-written, matches `repository/models.py` field-for-field; executed for real by CI's `real-infra (capability-engine, ...)` job (`run_alembic_upgrade` against a real, throwaway `postgres:16-alpine` testcontainer) | Real-infrastructure-verified (GitHub Actions, run `32005017275`, job `95312607118`, green) |
| Real-Postgres persistence (`tests/integration/test_repository_real_postgres.py`) | 6 tests (insert/find/list/delete/duplicate-rejection/installation-event), `@pytest.mark.real_infra` | **Real-infrastructure-verified** — not run locally (no Docker daemon in this environment) but run for real by CI after `.github/workflows/real-infra-checks.yml`'s matrix was corrected to include `capability-engine` (see the correction note above); passed |
| Real sandbox-violation behavior | Real filesystem path-traversal, real disallowed-executable subprocess-start refusal, real git-subcommand refusal, real disallowed-host refusal — all exercised with actual OS calls (`tmp_path`, real `git`/`python3` subprocesses), never mocked, both at the unit-adapter level and through a full RPC round trip (`test_invoke_request_reports_a_real_sandbox_violation_for_an_out_of_scope_read`) | Fully verified |
| Real Event Bus RPC round trips | `capability.resolve.request`/`capability.invoke.request` (server side, via a second in-memory caller `BoundEventBus`) and `communication.session.lookup_by_user.request`/`communication.intent.deliver.request` (client side, via a serving stand-in) — both directions exercised over the real in-memory Event Bus backend, not bypassed by dependency injection | Fully verified |
| Docker build (`services/capability-engine/Dockerfile`) | Fixed a missing `nova-service-kit` copy step (same defect class as the prior `fix-dockerfiles-nova-service-kit` PR, predating this engine's existence) | Real-infrastructure-verified — CI's `build-and-scan (capability-engine)` job actually built the image (GitHub Actions, run `32005017282`, job `95312607250`, green); not built locally (no Docker daemon in this environment) |
| GitHub Actions CI (all 3 workflows: PR Checks, Build & Scan, Real-Infrastructure Checks) | 20/20 check runs green on PR #8 at commit `6aee23d` (after the real-infra matrix correction) | Real-infrastructure-verified |

**No contract/fake-only-verified items remain unclassified.** Every item
above is either fully verified locally, real-infrastructure-verified via
CI (explicitly labeled, with the run/job reference), or (nothing in the
final state) genuinely unverified.

## 10. Known limitations (of this PR's scope, not defects)

- No marketplace, capability composition, or learning/discovery system —
  explicitly deferred (TDD 3C §14).
- `Supported Platforms` remains deferred, per the already-approved
  Capability model decision.
- No provider SDK / AI model integration anywhere in this engine
  (confirmed zero dependency, matches TDD 3C §H).
- `execution_adapter` invocation retries are the caller's own concern
  (`action-engine`'s future retry policy) — this engine never retries
  silently, per TDD 3C §8's own failure table.

## 11. Phase 3D contamination check

**None.** No `action-engine`, no `CapabilityPort`/client implementation,
no capability-selection logic, no `Action.execution_target` semantics, no
rollback/snapshot primitive on any adapter. Grepped `services/` for any
new `action-engine`-related file — none exist; `services/action-engine`
itself does not exist in this branch.

## 12. Phase 3E contamination check

**None.** No `agent-os`, no `AgentContext` runtime population, no Kernel
Scheduler capability logic, no capability authorization inside `agent-os`,
no agent registry changes. `granted_capabilities` is not referenced
anywhere in this PR's diff. `services/agent-os` does not exist in this
branch.

## 13. Remaining Phase 3 dependencies

- `action-engine` (TDD 3D) can now build its own `CapabilityPort`/client
  against the real `capability.resolve.*`/`capability.invoke.*` RPCs this
  PR implements — the contracts, subjects, and reply shapes are stable
  and tested.
- `agent-os` (TDD 3E) can populate `AgentContext.granted_capabilities` as
  declared intent whenever that phase begins; nothing in this PR needs to
  change to support that (Fork 3C-2's resolution already accounted for
  this).
