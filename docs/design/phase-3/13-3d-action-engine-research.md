# Phase 3D Research & Implementation Plan — `action-engine`

**Status: research and planning complete. Three implementation-time decisions APPROVED (§5). No production code authorized by this document — implementation happens in a separate PR.**

**Baseline.** `phase-3b-planning-domain` @ `a943b0abec6b12d84d0cc7e52e3ba4dccee88c98` (post PR #9 and PR #11 — Project Health system and the resolved Phase 3C/3D/3E documentation are both canonical as of this baseline). This document does not re-litigate any decision already marked RESOLVED in `06-tdd-3c-capability-engine.md` or `07-tdd-3d-action-engine.md` — those documents' fork resolutions are treated as authoritative throughout.

**Sync note (2026-08-18), added when this document was merged into canonical
lineage — the original text above and below is otherwise unchanged.** This
document (PR #12) was deliberately held out of canonical lineage until
Phase 3D's implementation (PR #13) and its documentation-closure pass
(PR #14) both merged, per the same sequencing precedent PR #11 established
for `phase-3c-research`. That condition is now satisfied — PR #13 merged
2026-08-18 as squash commit `ac285bc3533fb24d0434d7675b8fc3af2db1d079`, PR
#14 merged the same day as merge commit
`e9ea3b8c6ae99c645e6eb41b98fbe34c55f8ec39`. Two things worth recording
for a reader arriving at this document after the fact:

- **All three approved decisions (§5.1-§5.3) shipped exactly as described
  here.** `execution_target` resolves by capability `name` via the
  additive `CapabilityResolveRequestPayload.name` field and
  `find_by_name` (§5.1); the stage-2/stage-5 validation split (§5.2) is
  implemented in `domain/parameter_validation.py`; natural-key
  idempotency on `Action.id` (§5.3) is implemented, including the
  concurrent-retry-race path. See the
  [Phase 3D Gate Review](../../roadmap/architecture-reviews/phase-3d-action-engine-gate-review.md)
  for the full, verified account of each.
- **§13's own "Acceptance criteria (final)" list below numbers 9 items,
  not 7 — this does not contradict the "7 of 7" figure used everywhere
  else in this project's documentation (Gate Review, Project Health,
  roadmap).** TDD 3D's own canonical §14 tracks a *different*, 7-item
  acceptance-criteria list (items 1-5 there correspond directly to items
  1-5 below; TDD 3D §14 item 7 corresponds to item 7 below, the
  stage-2/5 validation split). Items 6 (`execution_target` resolves by
  name) and 8-9 (the dedicated idempotency test; full local+CI
  verification green) below were implemented and verified — see the
  Gate Review §10/§13 — but were never folded into TDD 3D §14's own
  numbered list; they remain this document's own, narrower PR-scoped
  verification bar, tracked separately rather than merged into the
  headline count. Both lists are fully satisfied; the numbering simply
  never lined up 1:1, and is clarified here rather than silently
  reconciled by renumbering either document.

---

## 0. Scope of this document

Research-and-planning pass, now finalized with the three decisions in §5 approved by the user. No application code is included in this PR. This revision incorporates: (a) the approved decisions with rationale and consequences recorded explicitly, (b) a correction to TDD 3C's stale claim about the capability RPCs being undefined (companion change to `06-tdd-3c-capability-engine.md` in this same PR, additive-only, no re-design), (c) exact, source-verified contract/handler/test-pattern detail action-engine will consume, (d) the complete file/module list, test plan, CI/Docker requirements, and Project Health update requirements for the implementation PR that follows this one.

---

## 1. Documents read and their status

| Document | Length | Status found |
|---|---|---|
| `docs/design/phase-3/07-tdd-3d-action-engine.md` | 417 lines | Design only, awaiting approval. Reconciliation pass complete — Fork 3C-1/3D-1 and its rollback consequence both marked RESOLVED. Re-read in full for this revision; no changes needed to this document itself (the three approved decisions extend it, they don't contradict it). |
| `docs/design/phase-3/06-tdd-3c-capability-engine.md` | 741 lines | Design only, awaiting approval. All four Phase 3C forks RESOLVED and approved (§4). **This revision adds a small, additive correction note to §4/§11** — see §4 below. |
| `docs/design/phase-3/12-3c-architecture-research.md` | 1,673 lines | The research trail both reconciliation passes above are based on. §18/§19 specifically trace Phase 3D's and Phase 3E's dependencies on Phase 3C. |
| `docs/design/phase-3/11-3b-decomposition-architecture-research.md` | 514 lines | Not Phase-3D-relevant in substance; read for completeness. |
| `docs/bible/part-12-action-engine.md` | 697 lines | Source-of-truth for the Action Object Model and Action Principle lifecycle; spot-verified against TDD 3D's citations (§3 below). |
| `docs/project-health/` (all 14 files) | — | Read in full; baseline established in §2. |
| `docs/roadmap/ENGINEERING_ROADMAP.md` (Phase 3 section, lines 505-550) | — | Cross-checked against TDD 3D's own dependency/sequencing claims. |

---

## 2. Project Health baseline for Phase 3D

- `docs/project-health/` is canonical (merged via PR #9): `README.md`, `project-health-master.md`, and 12 per-phase snapshot files.
- **SLOC methodology remains explicitly unresolved.** `project-health-master.md` §2's open choice — Option A (restore `scc`) vs. Option B (formally adopt `cloc`) — is unchanged. Not decided by this document; no Phase-3D SLOC figure exists yet (no code).
- **Current classification: `ACTIVE BUT NOT REPORTED`**, unchanged.
- **Stale field, not corrected here:** `docs/project-health/phase-3c.md` field 17 still records the pre-PR#11 documentation-sync gap as open; it closed with PR #11. Left as-is per the Project Health system's "written once" contract — flagged for a future one-line correction, at the user's discretion.
- **`docs/project-health/phase-3d.md` required at implementation completion** — see §9 for the exact 23-field content plan.

---

## 3. Fidelity check: TDD 3D and TDD 3C against Bible Part 12/15

Spot-verified directly against source, not taken on the TDDs' own word:
- The 12-stage Action Principle lifecycle (Bible `part-12-action-engine.md:43-93`) matches TDD 3D §6's mapping exactly.
- The Safety Layers example list (`part-12-action-engine.md:453-471`) matches TDD 3D §4's citation exactly.
- No new fidelity issues found beyond what TDD 3C/3D's own reconciliation passes already disclosed.

---

## 4. Phase 3D → Phase 3C dependency verification, with exact current contract surface

### 4.1 The documentation-precision gap, and its correction

TDD 3C §4/§11 describes `capability.resolve.request`/`.reply` and `capability.invoke.request`/`.reply` as "illustrative... exact subject names and payload field shapes are implementation-time work, not fixed here." **This is stale.** These RPCs are implemented, tested, and shipped on canonical, using exactly the illustrative names TDD 3C proposed. Per the user's explicit instruction: **this is not redesigned.** `capability.resolve.request`/`capability.invoke.request` are treated as the existing, canonical, unmodified server contract (except for the single additive field in §5.1). A short, additive correction note is added to `06-tdd-3c-capability-engine.md` §4 and §11 in this same PR — following this project's own established convention (used throughout TDD 3C's own reconciliation pass) of appending a dated correction rather than silently rewriting the original text. The note reads, verbatim, as it will appear in that document:

> **Correction, Phase 3D research pass (this note, not a re-opening of Fork 3C-1/3D-1):** the RPC subjects and payloads described above as "illustrative... not fixed here" were, in fact, implemented and tested during Phase 3C's own implementation (PR #8) — see `nova_contracts.events.capability` and `services/capability-engine/src/nova_capability_engine/main.py`'s `_make_resolve_request_handler`/`_make_invoke_request_handler`. The illustrative names match exactly what shipped. Phase 3D's `action-engine` implements the consumer side against this existing, canonical server contract — it does not redesign it.

### 4.2 The existing server contract, exact and verified (re-read directly for this revision, not from memory)

**`packages/nova-contracts/src/nova_contracts/events/capability.py`** — exact current content:

```python
CapabilityHealthStatus = Literal["unknown", "healthy", "degraded", "unhealthy"]
CapabilityInvokeOutcome = Literal["success", "failure", "sandbox_violation"]

class Capability(BaseModel):
    id: UUID
    name: str
    description: str
    category: str
    version: str
    dependencies: list[str] = Field(default_factory=list)
    required_permissions: list[str]
    required_resources: list[str] = Field(default_factory=list)
    input_schema: dict
    output_schema: dict
    execution_adapter: str
    health_status: CapabilityHealthStatus
    installed_at: datetime

class CapabilityHandle(BaseModel):
    capability_id: UUID
    name: str
    execution_adapter: str

@register_payload("capability.resolve.request")
class CapabilityResolveRequestPayload(BaseModel):
    capability_id: UUID
    requesting_engine: str
    correlation_id: UUID
    schema_version: int = 1

@register_payload("capability.resolve.reply")
class CapabilityResolveReplyPayload(BaseModel):
    found: bool
    capability: Capability | None = None
    schema_version: int = 1

@register_payload("capability.invoke.request")
class CapabilityInvokeRequestPayload(BaseModel):
    capability_id: UUID
    operation: str
    parameters: dict = Field(default_factory=dict)
    requesting_engine: str
    correlation_id: UUID
    schema_version: int = 1

@register_payload("capability.invoke.reply")
class CapabilityInvokeReplyPayload(BaseModel):
    outcome: CapabilityInvokeOutcome        # "success" | "failure" | "sandbox_violation"
    result: dict | None = None
    error: str | None = None                 # set only when outcome != "success"
    schema_version: int = 1
```

**`services/capability-engine/src/nova_capability_engine/events/subscribed.py`** — exact:
```python
SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset({
    "capability.resolve.request",
    "capability.invoke.request",
})
```

**`services/capability-engine/src/nova_capability_engine/main.py`** — exact handler bodies (re-read directly for this revision):
```python
def _make_resolve_request_handler(app: FastAPI):
    async def handle(envelope: EventEnvelope) -> CapabilityResolveReplyPayload:
        state = app.state
        payload = CapabilityResolveRequestPayload.model_validate(envelope.payload)
        capability = await state.repository.find_by_id(payload.capability_id)
        return CapabilityResolveReplyPayload(found=capability is not None, capability=capability)
    return handle

def _make_invoke_request_handler(app: FastAPI):
    async def handle(envelope: EventEnvelope) -> CapabilityInvokeReplyPayload:
        state = app.state
        payload = CapabilityInvokeRequestPayload.model_validate(envelope.payload)
        capability = await state.repository.find_by_id(payload.capability_id)
        if capability is None:
            return CapabilityInvokeReplyPayload(outcome="failure", error="capability not found")
        adapter = state.adapters.get(capability.execution_adapter)
        if adapter is None:
            return CapabilityInvokeReplyPayload(outcome="failure", error=f"no adapter registered for {capability.execution_adapter!r}")
        try:
            result = await adapter.invoke(payload.operation, payload.parameters, required_resources=capability.required_resources)
        except SandboxViolation as exc:
            return CapabilityInvokeReplyPayload(outcome="sandbox_violation", error=str(exc))
        except Exception as exc:
            return CapabilityInvokeReplyPayload(outcome="failure", error=str(exc))
        # ... metrics recorded via state.metrics.{invocation_total,invocation_duration_ms,sandbox_violation_blocked_total}
    return handle
```
Both registered via `await bus.serve("capability.resolve.request", _make_resolve_request_handler(app), source_engine="capability-engine")` and the equivalent `.invoke.request` call in `main.py`'s lifespan.

**TypeScript codegen** — confirmed present: `packages/nova-contracts/typescript/CapabilityResolveRequestPayload.ts`, `CapabilityResolveReplyPayload.ts`, `CapabilityInvokeRequestPayload.ts`, `CapabilityInvokeReplyPayload.ts`.

**Existing integration-test pattern to mirror** — `services/capability-engine/tests/integration/test_events_capability_resolve_and_invoke.py`: stands up a real in-memory `BoundEventBus`, uses a **second** `BoundEventBus` instance as the calling side (explicitly documented in that file as standing in for action-engine's future client), sends a real `CapabilityResolveRequestPayload`/`CapabilityInvokeRequestPayload` via `.request(...)`, asserts on the typed reply. Action-engine's own integration tests for `CapabilityPort` will follow this exact "second bus" shape (also the same pattern TDD 3D §5 already specifies for testing `action.execute` itself, since no real caller exists until Phase 3E).

**Event-bus behavior confirmed** (`nova_eventbus_sdk.BoundEventBus`): `.request(subject, payload, *, source_engine, correlation_id=None, timeout_ms=2000)` checks the subject against the caller's own `PUBLISHABLE_SUBJECTS` allow-list before sending; `.serve(subject, handler, source_engine=...)` checks against `SUBSCRIBABLE_SUBJECTS`. `action-engine`'s own `events/published.py` will need `capability.resolve.request` and `capability.invoke.request` (plus `communication.intent.deliver.request`, `world_model.context.request`) in its allow-list before any of these calls will be permitted — this is a required, not optional, file.

### 4.3 Consequence for Phase 3D's implementation scope

Confirmed unchanged from the prior revision: Phase 3D implements the **consumer side only** — `action-engine`'s own `CapabilityPort` Protocol plus a concrete client calling the contract shown in §4.2 above, unmodified except for §5.1's single additive field.

### 4.4 Other dependencies verified (unchanged from prior revision, re-confirmed)

| Dependency | Repository state | Verified |
|---|---|---|
| `capability-engine`'s `health_status`/`execution_adapter` fields | Present on `Capability` exactly as shown in §4.2 | ✅ |
| `communication.intent.deliver.request` gate | Served in `services/communication-engine/src/nova_communication_engine/events/handlers.py` (`make_intent_deliver_handler`); reply carries `rejection_reason` distinguishing personality hard-stop from channel/session failure | ✅ |
| `world_model.context.request` / `present_identities` | Served in `world-model-engine`; `present_identities: list[PresentIdentityPayload]` on `ContextReplyPayload` | ✅, zero existing consumers (§5.4) |
| `RiskLevel` reuse | Lives in `nova_contracts.events.planning.RiskLevel` (`StrEnum`), already consumed by `planning-engine`'s `TaskNode.risk` | ✅ |
| `GoalsPort`/`DigitalTwinPort` per-consumer convention | `GoalsPort` independently defined in `reasoning-engine` and `executive-cognition-engine`; `DigitalTwinPort` defined in the consumer (`communication-engine`) | ✅ real precedent for `CapabilityPort` |
| `FakeCommunicationPort` precedent | `services/capability-engine/tests/fakes/communication_port.py`, 34 lines, complete | ✅ |

**No Phase 3D→3C dependency was found broken, missing, or contradicted.**

---

## 5. Approved decisions

The three decisions proposed in the prior revision of this document are **approved by the user**, effective this revision. Each is recorded below with its rationale and its concrete consequences for the implementation plan in §6-§9. These are now binding for the implementation PR, in the same sense TDD 3C's RESOLVED forks are binding — not re-opened without a fresh architectural reason.

### 5.1 APPROVED — `execution_target` semantics

**Decision.** `Action.execution_target: str` holds the target capability's stable `name` field (e.g. `"git"`, `"filesystem"`, `"terminal"`, `"http"`), not its `capability_id: UUID`. Resolution against the existing `capability.resolve.request` RPC (§4.2) is via a **backward-compatible additive extension**: `CapabilityResolveRequestPayload` gains `name: str | None = None`, alongside the existing `capability_id: UUID | None` (also loosened from required to optional). `capability-engine`'s existing resolve handler is extended to accept either field and resolve by whichever is provided (exactly one required — validated at the payload level, e.g. a Pydantic `model_validator`).

**Rationale.** A capability's `capability_id` is Postgres-generated at install time — nothing in the current architecture gives an `Action`'s caller (an agent, eventually via Phase 3E's Supervisor) a way to know it in advance. `name` is the stable, human/agent-legible identifier that already exists on `Capability` and that an agent would naturally declare intent against ("run git"). ADR-024 explicitly states "adding a field to an existing payload is never a version bump" — this is the smallest correct extension, not a new RPC pair, and does not reopen Fork 3C-1/3D-1's ownership resolution.

**Consequences.**
- `packages/nova-contracts/src/nova_contracts/events/capability.py`: `CapabilityResolveRequestPayload.capability_id` becomes `UUID | None = None`; new `name: str | None = None`; add a model-level validator requiring exactly one of the two to be set.
- `services/capability-engine/src/nova_capability_engine/main.py`'s `_make_resolve_request_handler`: branch on which field is set — `repository.find_by_id(capability_id)` (existing path, unchanged) or a new `repository.find_by_name(name)` (new repository method, small addition to `services/capability-engine/src/nova_capability_engine/domain/ports.py`'s `CapabilityRepository` Protocol and its `PostgresCapabilityRepository`/`FakeCapabilityRepository` implementations).
- No change to `capability.invoke.request` — it already takes `capability_id: UUID` (obtained from the prior resolve reply's `Capability.id`), which is correct and unaffected.
- `capability-engine`'s own existing contract test (`tests/contract/test_capability_payloads.py`) needs one new round-trip case for the by-name request shape; its existing by-id round-trip case is unaffected (the field is now optional, not removed).

### 5.2 APPROVED — Validate-stage schema ownership

**Decision.** Stage 2 ("Validate") performs **structural validation of the `Action` object only** — automatic via Pydantic at RPC-payload parse time (`ActionExecuteRequestPayload.model_validate(...)`), nothing bespoke. Deep parameter-shape validation of `Action.parameters` against the target `Capability.input_schema` happens at stage 5 ("Prepare Resources"), immediately after `CapabilityPort.resolve()` returns the `Capability` and its `input_schema` is known.

**Rationale.** The `Capability` — and therefore its `input_schema` — does not exist to action-engine until stage 5's resolution completes; validating against it at stage 2 is not merely premature but structurally impossible without either resolving early (out of lifecycle order) or duplicating capability-specific schema knowledge inside action-engine (explicitly rejected by the user's instruction: "do not duplicate capability-specific validation inside action-engine"). Splitting validation this way keeps `capability-engine` the sole owner of what a valid `parameters` shape looks like for its own capabilities — action-engine only ever validates against a schema it received from capability-engine, never one it invented locally.

**Consequences.**
- `action-engine`'s `domain/pipeline.py`: stage 2 implementation is effectively a no-op beyond payload parsing (Pydantic already did the structural check) — no dedicated "stage 2 validator" module needed.
- Stage 5's implementation performs `jsonschema`-style validation (or equivalent) of `Action.parameters` against the resolved `Capability.input_schema` dict, immediately before proceeding to stage 6 (Execute). A validation failure at this point is a distinct, named outcome (`status="failed"`, not `status="denied"` — this is a parameter-shape failure, not an approval-loop denial) reported via `action.result`.
- No new dependency on `capability-engine`'s own code — action-engine validates using the `input_schema` dict it already receives on the `Capability` entity from `capability.resolve.reply` (§4.2), never a direct import or duplication of capability-engine's own schema definitions.

### 5.3 APPROVED — `action.execute` idempotency

**Decision.** Natural-key idempotency on `Action.id` (already the model's UUID primary key), mirroring Fork 3C-4's exact resolved pattern for `POST /v1/capabilities/install`. A second `action.execute` request for an `Action.id` already present in the `action` table in a terminal state (`completed`, `failed`, `rolled_back`, `denied`) returns the existing recorded `ActionResultPayload` without re-executing, re-invoking capabilities, or re-triggering the approval loop.

**Rationale.** TDD 3D specifies no idempotency behavior at all for `action.execute`, unlike capability-engine's own already-resolved Fork 3C-4 precedent for its structurally analogous mutating, retry-prone `POST /v1/capabilities/install` endpoint. Without a guard, a network-level retry of `action.execute` (the caller times out and resends, believing the first attempt was lost) could re-execute a destructive filesystem/terminal operation a second time — a real correctness and safety gap, not a hypothetical one, given this engine's entire purpose is executing potentially-destructive operations. Fork 3C-4's exact resolved mechanism (existence check on a natural key, no bespoke idempotency-key framework, no duplicate side effects) is directly reusable here with `Action.id` playing the role `(name, version)` plays for capabilities.

**Consequences.**
- `action` table (repository layer): before starting stage 1 ("Receive Request") of a fresh `action.execute` invocation, check whether `Action.id` already exists with a terminal `status`. If so, short-circuit: return the stored `action_execution_history`'s recorded outcome as the `ActionResultPayload`, skip every subsequent stage (2 through 12) entirely — including the approval loop, which must not re-fire for an idempotent replay.
- Unlike Fork 3C-4 (a Postgres `UNIQUE (name, version)` constraint catching a concurrent-insert race), `Action.id` is already the primary key, so the natural-key check here is a straightforward existence read, not a constraint-violation-catch pattern — no schema change beyond what §6.5's persistence design (unchanged from the prior revision) already specifies.
- A request for an `Action.id` that exists but is **not yet terminal** (e.g. mid-execution, or `approval_required`) is a distinct case from the terminal-state short-circuit above — it must not silently re-execute *or* silently no-op; the correct behavior (reject as a conflicting concurrent request vs. return current in-flight status) is an implementation-time detail for stage 1's handler, not re-opened as a fork here since both sub-options are small, non-architectural, and don't affect any other component.
- Dedicated idempotency test required (§8.4).

---

## 6. Architecture (unchanged in substance from the prior revision, restated with §5's decisions folded in)

```
action-engine (NEW, leaf service — nothing depends on it yet; Phase 3E's Kernel Scheduler will add an edge into it later)
  ├─ requires ──▶ capability-engine    [capability.resolve.request/.reply (EXTENDED per §5.1), capability.invoke.request/.reply (UNCHANGED)]  — EXISTS, tested
  ├─ requires ──▶ communication-engine [communication.intent.deliver.request/.reply]                                                            — EXISTS, tested
  ├─ requires ──▶ world-model-engine   [world_model.context.request/.reply → present_identities]                                                — EXISTS, tested, first-ever consumer
  ├─ imports ───▶ nova_contracts.events.planning.RiskLevel                                                                                      — EXISTS, reused by planning-engine
  ├─ imports ───▶ nova_eventbus_sdk.BoundEventBus.request() / .serve()                                                                          — EXISTS, standard pattern
  ├─ imports ───▶ nova_service_kit (health router, engine+session factory, dispatch_ready_events)                                               — EXISTS, standard pattern
  └─ serves ────  action.execute  (idempotent on Action.id per §5.3; no real caller until Phase 3E)
```

---

## 7. Components and responsibilities

| Component | Responsibility |
|---|---|
| `domain/models.py` | `Action`, `RetryPolicy`, `RollbackStrategy`, `PendingApproval`, `IdentityConfidencePolicy` |
| `domain/pipeline.py` | The 12-stage Action Principle lifecycle; stage 2 structural-only (§5.2), stage 5 deep validation + capability resolution + idempotency short-circuit (§5.3) |
| `domain/ports.py` | `CapabilityPort`, `CommunicationPort`, `IdentityPort` Protocols — each independently defined here, per the `GoalsPort`/`DigitalTwinPort` per-consumer convention |
| `clients/capability_client.py` | Concrete `CapabilityPort` — calls `capability.resolve.request` (by `name`, per §5.1) and `capability.invoke.request` (unchanged) |
| `clients/communication_client.py` | Concrete `CommunicationPort` — mirrors `capability-engine`'s own `CommunicationClient` |
| `clients/identity_client.py` | Concrete `IdentityPort` — `world_model.context.request`, reads `present_identities` |
| `api/approvals.py` | Stopgap `POST /v1/action/approvals/{id}/decide` |
| `events/subscribed.py` | `SUBSCRIBABLE_SUBJECTS = frozenset({"action.execute"})` |
| `events/published.py` | `PUBLISHABLE_SUBJECTS = frozenset({"capability.resolve.request", "capability.invoke.request", "communication.intent.deliver.request", "world_model.context.request", "action.result", "action.approval.requested", "action.approval.decided"})` |
| `repository/` | SQLAlchemy models + Alembic migration for the 4 tables (§6.5 of the prior revision, unchanged) — plus the terminal-state existence check for §5.3 |

---

## 8. Exact files/modules the implementation PR will create or modify

### 8.1 New files (packages/contracts)
- `packages/nova-contracts/src/nova_contracts/events/action.py` — `Action`, `RetryPolicy`, `RollbackStrategy` (entities); `ActionExecuteRequestPayload`/`ActionResultPayload`; `ActionApprovalRequestedPayload`/`ActionApprovalDecidedPayload`. All `schema_version: int = 1`.

### 8.2 Modified files (existing contracts and capability-engine, per §5.1)
- `packages/nova-contracts/src/nova_contracts/events/capability.py` — `CapabilityResolveRequestPayload.capability_id` → `UUID | None`; add `name: str | None`; add exactly-one-of validator.
- `services/capability-engine/src/nova_capability_engine/main.py` — `_make_resolve_request_handler` branches on `capability_id`/`name`.
- `services/capability-engine/src/nova_capability_engine/domain/ports.py` — `CapabilityRepository` Protocol gains `find_by_name`.
- `services/capability-engine/src/nova_capability_engine/repository/postgres_capability_repository.py` and `tests/fakes/repository.py` — implement `find_by_name`.
- `services/capability-engine/tests/contract/test_capability_payloads.py` — new by-name round-trip case.
- `packages/nova-contracts/typescript/CapabilityResolveRequestPayload.ts` — regenerated (additive field, TS codegen must be re-run, consistency re-checked per this project's standing verification step).

### 8.3 New service scaffold — `services/action-engine/`
```
services/action-engine/
  Dockerfile, README.md, alembic.ini, package.json, pyproject.toml
  alembic/env.py, alembic/script.py.mako, alembic/versions/0001_initial_schema.py
  src/nova_action_engine/
    __init__.py, config.py, main.py, observability.py, py.typed
    domain/   (__init__.py, models.py, pipeline.py, ports.py)
    clients/  (__init__.py, capability_client.py, communication_client.py, identity_client.py)
    api/      (__init__.py, health.py, approvals.py)
    events/   (__init__.py, published.py, subscribed.py)
    repository/ (__init__.py, models.py, postgres_action_repository.py)
  tests/
    unit/        (test_pipeline.py, test_risk_classification.py, test_approval_state_machine.py,
                   test_adr032_gate.py, test_rollback.py)
    contract/    (test_action_payloads.py)
    integration/ (test_health.py, test_events_action_execute.py, test_approval_loop_round_trip.py,
                  test_capability_client.py, test_communication_client.py, test_identity_client.py)
    fakes/       (capability_port.py, communication_port.py, identity_port.py, repository.py)
    real_infra/  (test_repository_real_postgres.py, test_approval_real_communication_engine.py,
                  test_critical_risk_blocked_real_timing.py)
```
(Mirrors `capability-engine`'s own directory shape exactly — see the prior revision's §4 findings for that precedent.)

### 8.4 Infra/CI files modified
- `infra/docker/docker-compose.local.yml` — new `action-engine` service block, port `8012`, `depends_on: {nats, postgres}` (both healthy).
- `.github/workflows/build-and-scan.yml` — one new matrix line, `action-engine`.
- `.github/workflows/real-infra-checks.yml` — one new matrix line, `action-engine` (checked proactively per §5.5 of the prior revision's finding).
- Root `pyproject.toml` — `nova_action_engine` added to `[tool.importlinter].root_packages`; contracts 1/2/3 auto-registered if scaffolded correctly; contract 6 (ADR-034) added manually; contract 4 (ADR-020) — `nova_action_engine` added to `source_modules` manually.

### 8.5 Documentation files modified
- `docs/design/phase-3/06-tdd-3c-capability-engine.md` — §4.1's correction note (this PR, not the implementation PR).
- `docs/design/phase-3/07-tdd-3d-action-engine.md` — at implementation time, updated to reference §5's approved decisions concretely (e.g. `execution_target`'s exact resolved semantics) rather than leaving them as open proposals.
- `docs/project-health/phase-3d.md` — new, at implementation completion (§9).
- `docs/project-health/project-health-master.md` — new Phase 3D row.

---

## 9. Complete test plan

| Tier | File | Coverage |
|---|---|---|
| Unit | `tests/unit/test_risk_classification.py` | `RiskLevel` classification for scripted parameter sets |
| Unit | `tests/unit/test_approval_state_machine.py` | requested → approved/denied/timeout transitions; timeout defaults to denied (fail-closed) |
| Unit | `tests/unit/test_adr032_gate.py` | confidence above/below threshold per risk tier; absent-policy fail-closed case; per-risk-tier configurability exercised (not one global threshold) |
| Unit | `tests/unit/test_rollback.py` | rollback invocation per `RollbackStrategy.kind`, using `FakeCapabilityPort` |
| Unit | `tests/unit/test_pipeline.py` | stage 2 structural-only validation (§5.2); stage 5 deep parameter validation against a fake-resolved `input_schema`; **idempotency short-circuit for a terminal-state `Action.id` (§5.3)**, including the distinct in-flight-vs-terminal case |
| Contract | `tests/contract/test_action_payloads.py` | round-trips for `Action`, `RetryPolicy`, `RollbackStrategy`, `ActionExecuteRequestPayload`/`ActionResultPayload`, `ActionApprovalRequestedPayload`/`ActionApprovalDecidedPayload`; **direct assertion** `ActionApprovalRequestedPayload`'s registered subject is `"action.approval.requested"`, never `"autonomy.approval.requested"` |
| Integration | `tests/integration/test_events_action_execute.py` | `action.execute` served correctly via the "second `BoundEventBus`" pattern (§4.2); **idempotency**: two `action.execute` calls for the same `Action.id` after the first reaches a terminal state produce one execution and two identical replies |
| Integration | `tests/integration/test_approval_loop_round_trip.py` | full approval-loop round trip against `FakeCommunicationPort` (mirroring `capability-engine`'s own fake exactly): critical-risk action → `action.approval.requested` published → `communication.intent.deliver.request` called → decide-endpoint resolves → `action.approval.decided` published → execution proceeds or `status="denied"` |
| Integration | `tests/integration/test_capability_client.py` | `CapabilityPort` client against a real in-memory bus paired with capability-engine's own served handlers (§4.2's pattern) — resolve-by-name (§5.1), invoke, and the read-before-write rollback-capture call |
| Integration | `tests/integration/test_communication_client.py`, `test_identity_client.py` | Same "second bus" pattern for the other two ports |
| Real-infra | `tests/real_infra/test_repository_real_postgres.py` | real Postgres round trip for all 4 tables; idempotency check surviving a real restart |
| Real-infra | `tests/real_infra/test_approval_real_communication_engine.py` | real end-to-end approval round trip against a real `communication-engine` instance |
| Real-infra | `tests/real_infra/test_critical_risk_blocked_real_timing.py` | scripted Critical-risk filesystem delete blocked pending approval, verified against real timing, not a fake clock — the named acceptance-criterion test from TDD 3D §14 |

Fake ports (`tests/fakes/{capability_port,communication_port,identity_port}.py`) live in `action-engine`'s own `tests/fakes/`, mirroring `capability-engine`'s own `tests/fakes/communication_port.py` structurally (injectable failure modes, e.g. `raise_timeout`) — not a shared `nova-testkit` type, consistent with this project's confirmed convention.

---

## 10. CI and Docker/runtime requirements (final)

- `build-and-scan.yml` — new `action-engine` matrix line, identical pattern to all 12 current engines (`docker/build-push-action@v6` + `aquasecurity/trivy-action@v0.34.0`, `severity: CRITICAL,HIGH`, `exit-code: "1"`, `ignore-unfixed: true`).
- `real-infra-checks.yml` — new `action-engine` matrix line, checked explicitly before declaring CI green (capability-engine's own gate review caught exactly this omission mid-review; not repeating it).
- `services/action-engine/Dockerfile` — standard scaffold pattern, including the CVE-2026-53615 `apt-get update && apt-get upgrade -y` line present in all 12 other engines' Dockerfiles.
- `infra/docker/docker-compose.local.yml` — port `8012`, `depends_on: {nats: healthy, postgres: healthy}` (this engine owns 4 Postgres tables per §6.5 of the prior revision).
- import-linter registration exactly as listed in §8.4.

---

## 11. Project Health update required for Phase 3D

At implementation completion:
- `docs/project-health/phase-3d.md` — the standard 23-field snapshot, citing the Phase 3D Gate Review by line number, following `phase-3c.md`'s exact shape as the most recent precedent.
- `docs/project-health/project-health-master.md` — new Phase 3D row in the master timeline table; §2's SLOC-methodology-history section extended only if a figure is measured and only with its tool/scope explicitly disclosed (still not decided by this document).
- Explicitly **not** measured or recorded by this research pass — no implementation exists yet.

---

## 12. Implementation order (final)

1. `nova_contracts.events.action` additions + the §5.1 additive extension to `CapabilityResolveRequestPayload` and `capability-engine`'s resolve handler/repository (§8.2) — smallest, most foundational change, touches an existing shipped engine.
2. Scaffold `services/action-engine` via `tools/scaffold-engine.py`.
3. Domain layer: `Action`/`RetryPolicy`/`RollbackStrategy` models, risk classification, the 12-stage pipeline skeleton with §5.2's validation split and §5.3's idempotency short-circuit.
4. Ports + clients: `CapabilityPort`, `CommunicationPort`, `IdentityPort`.
5. Approval loop: `PendingApproval` persistence, `action.approval.*` events, the stopgap decide-endpoint.
6. Rollback mechanism (read-before-write via `CapabilityPort`).
7. ADR-032 gate (`IdentityConfidencePolicy`, fail-closed default).
8. Persistence layer: SQLAlchemy models + Alembic migration, all 4 tables + the idempotency existence-check query.
9. `action.execute` RPC handler, served, tested via the "second `BoundEventBus`" pattern, idempotent per §5.3.
10. Observability wiring (6 metrics, TDD 3D §9, unchanged).
11. Infra wiring per §10.
12. Full test suite per §9.
13. Gate Review + README + `docs/project-health/phase-3d.md` per §11.

---

## 13. Acceptance criteria (final)

1. A deliberately risky action (Bible's own example: deleting a file) is blocked pending approval and proceeds only after approval.
2. An approval timeout denies, never auto-approves.
3. `action.approval.*` subjects are never confused with `autonomy.approval.*` — tested directly.
4. ADR-032's identity-confidence gate correctly blocks a low-confidence-identity execution attempt for at least one Critical-risk action, with per-risk-tier configurability exercised.
5. A forced mid-execution failure triggers the configured `RollbackStrategy` and restores prior state.
6. `execution_target` resolves correctly by capability `name` against the extended `capability.resolve.request` RPC (§5.1), with a passing contract test for both the by-id and by-name request shapes.
7. Stage 2/stage 5 validation split (§5.2) is implemented as specified — no capability-specific schema logic duplicated inside action-engine.
8. `action.execute` idempotency (§5.3) is proven by a dedicated integration test: two calls for the same `Action.id` after terminal state produce exactly one execution and two identical replies, with no duplicate side effects and no duplicate approval-loop firing.
9. Full local verification suite green (ruff, mypy, pytest, import-linter, docker-compose config, TypeScript codegen consistency — including the regenerated `CapabilityResolveRequestPayload.ts`) and real GitHub Actions CI green across every matrix job including `action-engine`, mirroring `capability-engine`'s own verification bar exactly.

---

## 14. Summary — what the next PR will implement

Everything in §8 (exact files), §9 (exact tests), §10 (CI/Docker), §11 (Project Health), and §12 (order), against the three decisions approved in §5. No further architectural ambiguity remains open (§5.6 of the prior revision's finding — no fork — still stands; re-verified in this revision, nothing new surfaced). **Proposed branch:** `phase-3d-action-engine`, from `phase-3b-planning-domain`. **Proposed PR structure:** one PR against `phase-3b-planning-domain`, covering the whole of Phase 3D's authorized scope, mirroring PR #8's shape — unless the user prefers §8.2's `capability-engine` contract extension to land and merge as an independent precursor PR first, since it touches an already-shipped engine rather than being purely additive to a new one.
