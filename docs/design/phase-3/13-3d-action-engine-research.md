# Phase 3D Research & Implementation Plan — `action-engine`

**Status: research and planning only. No production code authorized by this document.**

**Baseline.** `phase-3b-planning-domain` @ `a943b0abec6b12d84d0cc7e52e3ba4dccee88c98` (post PR #9 and PR #11 — Project Health system and the resolved Phase 3C/3D/3E documentation are both canonical as of this baseline). This document does not re-litigate any decision already marked RESOLVED in `06-tdd-3c-capability-engine.md` or `07-tdd-3d-action-engine.md` — those documents' fork resolutions are treated as authoritative throughout.

---

## 0. Scope of this document

Per the requesting instruction, this is a research-and-planning pass only: read the finalized TDD 3D and all relevant TDD 3C documentation and research, read the Project Health baseline, inspect the existing `capability-engine` implementation and its RPC/contract surface, inspect existing architecture/shared-package/testing/CI/Docker conventions, verify every Phase 3D→3C dependency against actual repository state (not assumed from documentation), identify remaining ambiguities without silently resolving anything that requires the user's architectural judgment, and produce a detailed implementation plan. No application code is included in this PR.

---

## 1. Documents read and their status

| Document | Length | Status found |
|---|---|---|
| `docs/design/phase-3/07-tdd-3d-action-engine.md` | 417 lines | Design only, awaiting approval. Reconciliation pass complete — Fork 3C-1/3D-1 and its rollback consequence both marked RESOLVED. |
| `docs/design/phase-3/06-tdd-3c-capability-engine.md` | 741 lines | Design only, awaiting approval. All four Phase 3C forks RESOLVED and approved (§4). |
| `docs/design/phase-3/12-3c-architecture-research.md` | 1,673 lines | The research trail both reconciliation passes above are based on. §18/§19 specifically trace Phase 3D's and Phase 3E's dependencies on Phase 3C. |
| `docs/design/phase-3/11-3b-decomposition-architecture-research.md` | 514 lines | Not Phase-3D-relevant in substance (Phase 3B decomposition orchestration); read for completeness per the standing instruction to treat all Phase 3 research as in scope. |
| `docs/bible/part-12-action-engine.md` | 697 lines | Source-of-truth for the Action Object Model and Action Principle lifecycle; spot-verified against TDD 3D's citations (see §3 below). |
| `docs/project-health/` (all 14 files) | — | Read in full; baseline established in §2. |
| `docs/roadmap/ENGINEERING_ROADMAP.md` (Phase 3 section, lines 505-550) | — | Cross-checked against TDD 3D's own dependency/sequencing claims. |

---

## 2. Project Health baseline for Phase 3D

- `docs/project-health/` is canonical (merged via PR #9): `README.md`, `project-health-master.md`, and 12 per-phase snapshot files.
- **SLOC methodology remains explicitly unresolved.** `project-health-master.md` §2's open choice — Option A (restore `scc`) vs. Option B (formally adopt `cloc`) — is unchanged. This document does not decide it, does not measure any Phase-3D SLOC figure (there is no Phase 3D code yet), and does not silently continue either historical series.
- **Current classification: `ACTIVE BUT NOT REPORTED`**, unchanged. The SAD 15 §10 Project Metrics requirement remains standing policy, not rescinded, still absent from the last several phase reports.
- **A stale field was found, not corrected here (documentation-only, read-mostly turn for this file):** `docs/project-health/phase-3c.md` field 17 ("Documentation health") still records the pre-PR#11 documentation-sync gap as open. That gap closed when PR #11 merged the resolved TDD 3C/3D/research documents into canonical. Per the Project Health system's own contract (`README.md`: "written once, extended only by that phase's own author"), this document does not retroactively edit `phase-3c.md` — flagging it as a one-line correction worth making explicitly, either alongside Phase 3D's own eventual `phase-3d.md` or as a small separate documentation fix, at the user's discretion.
- **Phase 3D will need its own `docs/project-health/phase-3d.md`** (23-field standard shape) at the close of implementation, per the standing update contract in `README.md`. Not created by this document — no implementation exists yet to snapshot.

---

## 3. Fidelity check: TDD 3D and TDD 3C against Bible Part 12/15

Spot-verified directly against source, not taken on the TDDs' own word:

- The 12-stage Action Principle lifecycle (Bible `part-12-action-engine.md:43-93`) matches TDD 3D §6's stage-by-stage mapping exactly — confirmed by direct read of both.
- The Safety Layers example list (Bible `part-12-action-engine.md:453-471`: delete files, format storage, system shutdown, credential modification, production deployment, financial transactions) matches TDD 3D §4's citation exactly.
- TDD 3C §2.2's `AgentContext.granted_capabilities` citation was itself corrected during TDD 3C's own reconciliation pass (originally cited line 136, corrected to line 135) — verified this correction is now consistent in the canonical document.
- No new fidelity issues found beyond what TDD 3C/3D's own reconciliation passes already disclosed.

---

## 4. Phase 3D → Phase 3C dependency verification (against actual repository state, not documentation claims)

This is the most consequential finding of this research pass.

### 4.1 What TDD 3C/3D's text claims

TDD 3C §4 (Fork 3C-1/3D-1 resolution) and §11 describe `capability.resolve.request`/`.reply` and `capability.invoke.request`/`.reply` as "illustrative" — *"exact subject names and payload field shapes are implementation-time work, not fixed here."*

### 4.2 What the repository actually contains

**These RPCs are already fully implemented, tested, and TypeScript-codegen'd on the canonical branch.** Verified directly:

- `packages/nova-contracts/src/nova_contracts/events/capability.py` defines `Capability`, `CapabilityHandle` (entities) and four `@register_payload`-decorated RPC payloads — `CapabilityResolveRequestPayload`/`CapabilityResolveReplyPayload`, `CapabilityInvokeRequestPayload`/`CapabilityInvokeReplyPayload` — every one `schema_version: int = 1` per ADR-024.
- `services/capability-engine/src/nova_capability_engine/main.py` serves both subjects: `bus.serve("capability.resolve.request", ...)` and `bus.serve("capability.invoke.request", ...)`, registered in `events/subscribed.py`'s `SUBSCRIBABLE_SUBJECTS`.
- `services/capability-engine/tests/integration/test_events_capability_resolve_and_invoke.py` round-trips both RPCs against a real in-memory Event Bus, using a second `BoundEventBus` explicitly documented as standing in for *"the kind of external caller (`action-engine`'s future `CapabilityPort`/client)."*
- TypeScript types for all four payloads already exist under `packages/nova-contracts/typescript/`.
- The illustrative subject names TDD 3D used (`capability.resolve.request`/`capability.invoke.request`) are the exact names actually shipped — no naming conflict, no redesign required.

### 4.3 Consequence for Phase 3D's scope

**Phase 3D does not need to co-design or implement these RPCs.** They exist, are tested, and are stable. Phase 3D's actual remaining work against this dependency is narrower than TDD 3D's own text implies: implement the **consumer side only** — a `CapabilityPort` Protocol (owned by `action-engine`, per Fork 3C-1/3D-1's resolution) plus a concrete client calling the already-shipped server contract. This is a documentation-precision finding, not an architectural fork — there is no competing design; the code has already settled the question TDD 3C's text still describes as open.

### 4.4 Other dependencies verified

| Dependency | TDD 3D's claim | Repository state | Verified |
|---|---|---|---|
| `capability-engine`'s `health_status`/`execution_adapter` fields | Gate execution / select invocation mechanism | Both fields present on `Capability` exactly as specified in TDD 3C §2.1, confirmed in `nova_contracts.events.capability.Capability` | ✅ |
| `communication.intent.deliver.request` gate | Approval-loop human-notification step | Exists, served in `services/communication-engine/src/nova_communication_engine/events/handlers.py` (`make_intent_deliver_handler`), payload shape includes `rejection_reason` distinguishing personality hard-stop from channel/session failure | ✅ |
| `world_model.context.request` / `present_identities` | ADR-032 identity-confidence signal | RPC exists and is served (`world-model-engine`, highest-QPS RPC in the codebase, p95 < 20ms budget); `present_identities: list[PresentIdentityPayload]` field exists on `ContextReplyPayload` | ✅, but see §5.3 below — **zero existing consumers** |
| `RiskLevel` reuse (Bible Part 14 scale) | TDD 3D §3.1 reuses it "from TDD 3B" | Actually lives in `nova_contracts.events.planning.RiskLevel` (a `StrEnum`), not `entities.py` — already consumed by `planning-engine`'s `TaskNode.risk`, a real, working precedent for a second engine (`action-engine`) importing it the same way | ✅, location corrected from TDD 3D's imprecise phrasing |
| `GoalsPort`/`DigitalTwinPort` per-consumer convention (cited as precedent for `CapabilityPort`) | Each consuming engine defines its own Protocol independently | Confirmed: `GoalsPort` is independently, byte-identically defined in both `reasoning-engine/.../domain/ports.py:106` and `executive-cognition-engine/.../domain/ports.py:83` — genuinely separate class definitions, zero shared import. `DigitalTwinPort` is defined in the consumer (`communication-engine/.../domain/ports.py:129`), not the provider. | ✅ real, working precedent |
| `FakeCommunicationPort` testing precedent (TDD 3D §13 cites "`digital-twin-engine`'s exact Fork D precedent") | Per-engine fake port test doubles | `services/capability-engine/tests/fakes/communication_port.py` is a complete, working example (34 lines) already in this exact codebase — a closer, more recent precedent than digital-twin-engine's original. Confirmed: `nova-testkit` itself ships only infrastructure fakes (`FakeModelGateway`, `FakePerceptionSignalSource`, etc.), never per-port fakes — those live per-engine, as `capability-engine`'s own does. | ✅ |

**No Phase 3D→3C dependency was found broken, missing, or contradicted.** Every dependency TDD 3D names is real and verifiable in the current codebase; the one drift found (§4.2-4.3) makes Phase 3D's job *smaller*, not harder.

---

## 5. Ambiguities, gaps, and inconsistencies found — none silently resolved

Per the explicit instruction not to choose silently between architectural alternatives: everything below is either (a) reported as a finding requiring no decision, (b) a precision gap with one clearly-best precedented answer, proposed and flagged for approval (the same disclosure discipline TDD 3D itself already used for `RetryPolicy`/`RollbackStrategy`/`IdentityConfidencePolicy`), or (c) explicitly escalated as needing your architectural judgment. **Nothing in category (c) was found in this pass** — see §5.6.

### 5.1 Gap A — `execution_target: str` semantics

TDD 3D §2 itself flags this: `execution_target` is "the closest candidate" for naming which `Capability` an `Action` targets, but "its exact semantics for capability-selection are not spelled out." The existing, already-shipped `CapabilityResolveRequestPayload` requires a `capability_id: UUID` — but nothing in the current architecture gives an `Action`'s caller (an agent, eventually via Phase 3E's Supervisor) a way to know a capability's UUID in advance; UUIDs are Postgres-generated at install time, not stable, predictable identifiers a static agent configuration could reasonably hardcode.

**Proposed (flagged for approval, not decided):** `execution_target` holds the capability's stable `name` field (e.g. `"git"`, `"filesystem"`) — human/agent-legible, matching how an agent would naturally declare intent ("I want to run git"). Resolve it by extending the **existing** `CapabilityResolveRequestPayload` additively — `name: str | None = None` alongside the existing `capability_id: UUID | None` — which is a pure field addition, never a version bump under ADR-024's own stated rule ("adding a field to an existing payload is never a version bump"). This requires a small, backward-compatible change to `capability-engine`'s existing resolve handler (accept either field, require exactly one), not a new RPC pair and not a re-opening of Fork 3C-1.

### 5.2 Gap B — stage 2 ("Validate") vs. stage 5 ("Prepare Resources"): whose `input_schema`?

TDD 3D §6 stage 2 says "schema/parameter validation against `input_schema`" without stating whose — `Action.parameters`'s own schema, or the target `Capability.input_schema`? The pipeline ordering makes the latter reading structurally awkward as written, since the `Capability` isn't resolved until stage 5. This exact gap is independently named in `12-3c-architecture-research.md` §18 as "recorded here as a heads-up for Phase 3D's own future pre-implementation research" — explicitly **not** elevated to a Phase 3C fork there, since its resolution doesn't require `capability-engine`'s own architecture to change.

**Proposed (flagged for approval, not decided):** split what "Validate" (stage 2) checks. Stage 2 validates only the `Action` object's own structural shape — handled automatically by Pydantic at RPC-payload parse time, nothing bespoke needed. Deep parameter validation against the resolved `Capability.input_schema` moves to stage 5 ("Prepare Resources"), immediately after resolution, when the schema to validate against actually exists.

### 5.3 Gap C — `action.execute` idempotency (a real omission, not previously flagged anywhere)

TDD 3D specifies no idempotency behavior at all for the `action.execute` RPC — unlike `capability-engine`'s own, already-resolved Fork 3C-4 precedent for `POST /v1/capabilities/install`. A network-level retry of `action.execute` for the same logical action, without any idempotency guard, could re-execute a destructive filesystem/terminal operation twice.

**Proposed (flagged for approval, not decided):** mirror Fork 3C-4's exact resolved pattern — natural-key idempotency on `Action.id` (already a UUID field on the model). A second `action.execute` for an `Action.id` already in a terminal state (`completed`/`failed`/`rolled_back`/`denied`) returns the existing recorded result rather than re-executing.

### 5.4 Finding — `IdentityPort` has zero existing precedent to reuse

`world_model.context.request`'s `present_identities` field exists and is served, but repo-wide grep confirms no current engine (`ai-model-orchestration-engine`, `communication-engine`, `executive-cognition-engine`, `reasoning-engine` — the four current callers of this RPC) reads that field; every existing `WorldModelClient`/`WorldModelPort` only touches the flat context fields. `action-engine`'s `IdentityPort` would be the **first** consumer of `present_identities` anywhere in the codebase. Not a fork — TDD 3D §7's proposed shape (`IdentityConfidencePolicy`, fail-closed default) is sound and precedented by `ProactiveBoundaryPolicy`'s identical absent-policy-fails-closed idiom — but flagged as a fact worth knowing: there is no existing consumer code to imitate structurally beyond the general Port/Client convention already covered in §4.4.

### 5.5 Finding — a pre-existing, unrelated CI gap worth not repeating

`.github/workflows/build-and-scan.yml`'s matrix is missing `planning-engine` entirely, despite it existing in the codebase and being registered in the import-linter's `root_packages`. This is a pre-existing gap, unrelated to and not caused by Phase 3D — flagged only so a new `action-engine` matrix entry doesn't get added correctly while this pre-existing omission is overlooked as though it weren't there. Not fixed by this document (out of scope for a research pass); worth a one-line follow-up whenever convenient.

### 5.6 No genuine architectural fork found

Every one of Phase 3C's four forks (3C-1/3D-1, 3C-2, 3C-3, 3C-4) is resolved, internally consistent, and re-verified against fresh reads of both TDDs in this pass — no contradiction found. The three gaps above (§5.1-5.3) are precision gaps with one clearly-best, precedented answer each, not competing architectures with a genuine tradeoff — the same class of gap already handled by proposing `RetryPolicy`/`RollbackStrategy`/`IdentityConfidencePolicy` in TDD 3D's own existing text. **Nothing in this research pass requires a stop-and-choose-between-options decision from the user.** What does require the user's approval is simply ratifying the three proposals above before they become authoritative — the same gate every prior new type in this TDD package has already passed through.

---

## 6. Implementation plan

### 6.1 Architecture

```
action-engine (NEW, leaf service — nothing depends on it yet; Phase 3E's Kernel Scheduler will add an edge into it later)
  ├─ requires ──▶ capability-engine    [capability.resolve.request/.reply (extended, §5.1), capability.invoke.request/.reply]  — EXISTS, tested
  ├─ requires ──▶ communication-engine [communication.intent.deliver.request/.reply]                                          — EXISTS, tested
  ├─ requires ──▶ world-model-engine   [world_model.context.request/.reply → present_identities]                              — EXISTS, tested, first-ever consumer
  ├─ imports ───▶ nova_contracts.events.planning.RiskLevel                                                                    — EXISTS, reused by planning-engine
  ├─ imports ───▶ nova_eventbus_sdk.BoundEventBus.request() / .serve()                                                        — EXISTS, standard pattern
  ├─ imports ───▶ nova_service_kit (health router, engine+session factory, dispatch_ready_events)                             — EXISTS, standard pattern
  └─ serves ────  action.execute  (no real caller until Phase 3E's Kernel Scheduler)
```

### 6.2 Components and responsibilities

| Component | Responsibility |
|---|---|
| `domain/models.py` | `Action`, `RetryPolicy`, `RollbackStrategy`, `PendingApproval`, `IdentityConfidencePolicy` |
| `domain/pipeline.py` | The 12-stage Action Principle lifecycle, orchestrating ports |
| `domain/ports.py` | `CapabilityPort`, `CommunicationPort`, `IdentityPort` Protocols — each independently defined here, never imported from another engine, per the confirmed-real `GoalsPort`/`DigitalTwinPort` per-consumer convention |
| `clients/capability_client.py` | Concrete `CapabilityPort` implementation — `capability.resolve.request`/`capability.invoke.request` RPC calls |
| `clients/communication_client.py` | Concrete `CommunicationPort` implementation — mirrors `capability-engine`'s own `CommunicationClient` (§4.4) |
| `clients/identity_client.py` | Concrete `IdentityPort` implementation — `world_model.context.request`, reads `present_identities` |
| `api/approvals.py` | Stopgap `POST /v1/action/approvals/{id}/decide` |
| `events/subscribed.py` | Serves `action.execute` |
| `events/published.py` | Publishes `action.result`, `action.approval.requested`, `action.approval.decided` |
| `repository/` | SQLAlchemy models + Alembic migration for the 4 tables (§6.5) |

### 6.3 Contracts and interfaces

- **New:** `nova_contracts.events.action` — `Action`, `RetryPolicy`, `RollbackStrategy` (entities); `ActionExecuteRequestPayload`/`ActionResultPayload`; `ActionApprovalRequestedPayload`/`ActionApprovalDecidedPayload`. All `schema_version: int = 1` per ADR-024. **Explicitly not defined:** `autonomy.approval.requested`/`.decision.made` — reserved for Phase 4 per Fork E2.
- **Additive change to an existing contract:** `CapabilityResolveRequestPayload` gains optional `name: str | None` (§5.1) — a small, backward-compatible change to `capability-engine`'s own resolve handler, not a re-implementation of anything RESOLVED.

### 6.4 RPC/API surface

```
action.execute (served, no real caller until 3E)
  → CapabilityPort.resolve(name=execution_target)         [capability.resolve.request/.reply, extended per §5.1]
  → [if risk == "critical"] action.approval.requested → communication.intent.deliver.request/.reply → action.approval.decided
  → CapabilityPort.invoke(capability_id, operation, parameters)   [capability.invoke.request/.reply, EXISTING, unmodified]
  → [on destructive-op failure] rollback: CapabilityPort.invoke(read op) captures pre-state → restore via same RPC
  → action.result (published)

IdentityPort.check(user_id) → world_model.context.request/.reply → present_identities → ADR-032 confidence gate

Stopgap REST: POST /v1/action/approvals/{id}/decide  (body: {approved: bool, reason: str | None})
```

### 6.5 Database requirements

New `action` Postgres schema (TDD 3D §8, unchanged by this research):
- `action` — the `Action` model.
- `pending_approval` — the approval-loop state machine record.
- `action_execution_history` — append-only, mirrors `capability_installation_event`'s precedent (audit trail, "Store Experience" stage).
- `identity_confidence_policy` — per-user, per-risk-tier threshold configuration.
- **Per §5.3's proposal:** `action.id` (already the primary key) is the natural-key idempotency guard for `action.execute` retries — no separate idempotency table needed, mirroring Fork 3C-4's `UNIQUE (name, version)` mechanism exactly (a uniqueness/existence check on an existing key, not a bespoke idempotency-key framework).

### 6.6 Action execution model

The 12-stage Action Principle lifecycle (Bible `part-12-action-engine.md:43-93`, TDD 3D §6, fidelity-checked in §3 above): Receive Request → Validate (structural only, per §5.2) → Check Permissions (ADR-032, §7 of TDD 3D) → Estimate Risk → Prepare Resources (capability resolution + deep parameter validation, per §5.2) → Execute (blocked pending approval if `risk="critical"`) → Monitor Progress (timeout) → Detect Errors → Recover if Necessary (rollback) → Verify Result → Report Outcome → Store Experience.

### 6.7 `CapabilityPort` integration

Per Fork 3C-1/3D-1's resolution (Option A, RESOLVED): `action-engine` defines its own `CapabilityPort` Protocol; `capability-engine`'s process is the sole executor of every adapter call. Concretely, against the **already-shipped** RPCs (§4.2): resolve by name (§5.1's extension) at stage 5, confirm `health_status == "healthy"` before proceeding, invoke via `capability.invoke.request` at stage 6. No new capability on `capability-engine`'s adapter interface is required — confirmed by Fork 3C-3's own resolution (§6.8 below).

### 6.8 Rollback ownership and `RollbackStrategy`

Per Fork 3C-3's resolution (Option B, RESOLVED): `action-engine` owns rollback entirely, outside `capability-engine`. Mechanism: capture pre-state via `capability-engine`'s existing, already-scoped, non-destructive read/list operation (the same `capability.invoke.request` RPC, targeting a read first) before issuing a destructive call; restore via the same mechanism on failure. `RollbackStrategy.kind: Literal["restore_file", "undo_configuration", "restart_service", "manual"]` (TDD 3D §3.1) is unaffected by this research — only the *mechanism* behind `"restore_file"` was made concrete during TDD 3C/3D's own reconciliation pass, not revisited here.

### 6.9 Error handling

Per TDD 3D §10's table (unchanged, re-verified sound): capability-unhealthy fails fast at stage 5 (never attempts execution against a known-unhealthy adapter); approval timeout denies, never auto-approves (fail-closed); `IdentityPort` timeout is treated as zero confidence (fail-closed, never silently bypasses the gate); mid-execution failure triggers the configured `RollbackStrategy`, with rollback failure recorded distinctly from the original execution failure; Postgres-unavailable is standard loud-failure, consistent with every other engine.

### 6.10 Validation

Two-stage, per §5.2's proposal: structural validation of the `Action` object at stage 2 (automatic via Pydantic at RPC-payload parse time); deep parameter-shape validation against the resolved `Capability.input_schema` at stage 5, once the schema is actually known.

### 6.11 Security considerations

- ADR-032 (identity-confidence as authorization signal) — binding, cited by name. Requires a **configurable threshold per risk tier** (point 2 of the ADR's decision), never one global hardcoded value; `action-engine` never performs identity recognition itself (point 3) — pure consumption of `perception-engine`'s (via World Model's) already-scored signal.
- `required_permissions` — locally enforced (no `nova-auth` yet), same reasoning already established for `capability-engine` (TDD 3C §10).
- The approval loop itself is a second, orthogonal safety layer for critical-risk actions, independent of the identity-confidence gate.
- `action.approval.*` is a new, Phase-3-owned namespace, never `autonomy.approval.*` (reserved for Phase 4, per Fork E2) — this namespace boundary must be a **tested** property (TDD 3D §13), not just a documented one.

### 6.12 Testing strategy

Per TDD 3D §13, re-verified sound and now made concrete against real precedent (§4.4):
- **Unit (fake-backed):** risk classification; approval-loop state machine; ADR-032 gate (confidence above/below threshold per risk tier, absent-policy fail-closed case); rollback-invocation per `RollbackStrategy.kind`. Fake ports (`FakeCapabilityPort`, `FakeCommunicationPort`, `FakeIdentityPort`) live in `action-engine`'s own `tests/fakes/`, mirroring `capability-engine`'s own `tests/fakes/communication_port.py` exactly — not a shared `nova-testkit` type.
- **Contract:** all new payload round-trips; a dedicated, direct assertion (not just an absence check) that `ActionApprovalRequestedPayload`'s subject is `action.approval.requested`, never `autonomy.approval.requested`.
- **Integration:** `action.execute` served correctly via the established "second `BoundEventBus`" pattern (no real caller exists until 3E); full approval-loop round trip against a fake `CommunicationPort`.
- **Real-infrastructure:** real end-to-end approval round trip (real Postgres for `pending_approval`, real `communication-engine` call); a real, scripted Critical-risk filesystem delete blocked pending approval, verified against real timing, not a fake clock.

### 6.13 CI requirements

- `.github/workflows/build-and-scan.yml` — one new matrix line, `action-engine`, following the exact pattern already used for all 12 current engines (per-service `docker/build-push-action@v6` build + `aquasecurity/trivy-action@v0.34.0` scan, `severity: CRITICAL,HIGH`, `exit-code: "1"`, `ignore-unfixed: true`).
- `real-infra-checks.yml` — must explicitly include `action-engine` in its own matrix. `capability-engine`'s own gate review caught exactly this gap mid-review (a first "green" run that had not actually covered the new engine) — worth checking for proactively this time.
- import-linter (`pyproject.toml`): `nova_action_engine` added to `root_packages`; contracts 1 (ADR-004 independence), 2 (ADR-006 no message broker), 3 (ADR-007 no graph DB) are auto-registered by `tools/scaffold-engine.py` if the engine is scaffolded as `action-engine`. Contract 6 (ADR-034, nova-service-kit boundary) requires a **manual** addition — confirmed not auto-registered by the script. Contract 4 (ADR-020, no LLM SDK) requires a **manual judgment call** — `action-engine` should be added to `source_modules` (forbidden from importing an LLM SDK directly), consistent with every engine except `ai-model-orchestration-engine`. Contract 5 (ADR-033, nova-testkit boundary) is already stale relative to `planning-engine`/`capability-engine` — a pre-existing gap, not Phase 3D's to fix, noted so it isn't mistaken for something this phase caused.

### 6.14 Docker/runtime requirements

- New `services/action-engine/Dockerfile`, following the standard scaffold pattern, including the CVE-2026-53615 `apt-get update && apt-get upgrade -y` line already present in all 12 other engines' Dockerfiles (must not be omitted for a newly-scaffolded engine).
- `infra/docker/docker-compose.local.yml` — new service block, next free host port **8012** (following `capability-engine`'s `8011`), `depends_on: nats` (healthy) at minimum; whether `action-engine` needs its own Postgres schema (`depends_on: postgres`) follows directly from §6.5's persistence requirements — yes, it does own 4 tables, so `depends_on: postgres` (healthy) is required, mirroring every other stateful engine's compose entry.

### 6.15 Project Health metrics to record

At Phase 3D's completion (not now — no implementation exists to measure): `docs/project-health/phase-3d.md`, 23-field standard shape, citing the eventual Gate Review by line number. SLOC figure only if measured with an explicitly disclosed tool/scope (per §2's still-open methodology question) — never silently continuing either historical series. `project-health-master.md`'s summary table gains a Phase 3D row and, if the SLOC methodology question is resolved as part of this work, §2's history section is extended accordingly (not decided by this document).

### 6.16 Documentation updates required at implementation time

- `docs/design/phase-3/07-tdd-3d-action-engine.md` — correct the stale claim that the capability RPCs are undefined (§4.2-4.3 above); reconcile the acceptance-criterion wording inconsistency already found in `12-3c-architecture-research.md` §18 (TDD 3C's own criterion 5 says the Fork 3C-1/3D-1 gate blocks only "action-engine implementation"; TDD 3D's own criterion 6 says "before either implementation begins" — cosmetic now since the gate is already resolved, but worth reconciling for future readers).
- `docs/project-health/phase-3c.md` field 17 — optional, one-line correction noting the documentation-sync gap it records is now closed (§2 above).

### 6.17 Implementation order (proposed sequence, not yet executed)

1. `nova_contracts.events.action` additions + the §5.1 additive extension to `CapabilityResolveRequestPayload` (small, backward-compatible touch to `capability-engine`'s existing handler).
2. Scaffold `services/action-engine` via `tools/scaffold-engine.py`.
3. Domain layer: `Action`/`RetryPolicy`/`RollbackStrategy` models, risk classification, the 12-stage pipeline skeleton.
4. Ports + clients: `CapabilityPort`, `CommunicationPort`, `IdentityPort` and their concrete implementations.
5. Approval loop: `PendingApproval` persistence, `action.approval.*` events, the stopgap decide-endpoint.
6. Rollback mechanism (read-before-write via `CapabilityPort`).
7. ADR-032 gate (`IdentityConfidencePolicy`, fail-closed default).
8. Persistence layer: SQLAlchemy models + Alembic migration, all 4 tables.
9. `action.execute` RPC handler, served, tested via the "second `BoundEventBus`" pattern.
10. Observability wiring (the 6 metrics named in TDD 3D §9, unchanged by this research).
11. Infra wiring: docker-compose entry, `build-and-scan.yml` + `real-infra-checks.yml` matrix entries, import-linter registration (§6.13).
12. Full test suite (unit/contract/integration/real-infra), §6.12.
13. Gate Review + README + `docs/project-health/phase-3d.md`.

### 6.18 Acceptance criteria

Per TDD 3D §14, re-verified sound, restated here as the plan's own Definition of Done:
1. A deliberately risky action (Bible's own example: deleting a file) is blocked pending approval and proceeds only after approval.
2. An approval timeout denies, never auto-approves.
3. `action.approval.*` subjects are never confused with `autonomy.approval.*` — tested, not just documented.
4. ADR-032's identity-confidence gate correctly blocks a low-confidence-identity execution attempt for at least one Critical-risk action, with per-risk-tier configurability exercised (not just a single global threshold).
5. A forced mid-execution failure triggers the configured `RollbackStrategy` and restores prior state.
6. **Added by this research pass:** the three proposed resolutions in §5.1-5.3 (execution_target semantics, validation-stage split, `action.execute` idempotency) are explicitly approved before implementation begins on the affected pipeline stages.
7. Full local verification suite green (ruff, mypy, pytest, import-linter, docker-compose config, TypeScript codegen consistency) and real GitHub Actions CI green across every matrix job including `action-engine`, mirroring `capability-engine`'s own verification bar exactly.

---

## 7. Summary

- **Readiness: READY, pending approval of §5.1-5.3.** No genuine architectural fork blocks implementation start (§5.6) — all four Phase 3C forks remain resolved and were re-verified consistent in this pass.
- **Files that would change at implementation time:** `packages/nova-contracts/src/nova_contracts/events/capability.py` (§5.1's additive field); `services/capability-engine/src/nova_capability_engine/events/subscribed.py` and its resolve handler (accept resolve-by-name); root `pyproject.toml` (import-linter registration); `infra/docker/docker-compose.local.yml`; `.github/workflows/build-and-scan.yml` and `real-infra-checks.yml`.
- **New files/directories:** `packages/nova-contracts/src/nova_contracts/events/action.py`; the full `services/action-engine/` scaffold; `docs/project-health/phase-3d.md` (at completion).
- **Proposed branch for implementation:** `phase-3d-action-engine`, from `phase-3b-planning-domain`, mirroring `phase-3c-capability-engine`'s naming and branch-from-canonical convention.
- **Proposed PR structure:** one PR against `phase-3b-planning-domain`, mirroring PR #8's shape (single PR covering the whole of Phase 3D's authorized scope) — unless the user prefers the §5.1 contract extension to land and merge independently first, as a small precursor PR.
