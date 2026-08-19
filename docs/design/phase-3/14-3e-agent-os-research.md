# Phase 3E Research & Decision Document — `agent-os`, the Five Agents, the `engineering` Supervisor, and the `GoalsPort` Migration

**Status: research and decision pass complete. Four architectural forks (3E-1
through 3E-4) resolved below, each with a recommended option and full
rationale — but none of them is yet approved by the user. No production
code is authorized by this document.** Implementation may not begin until
the user has explicitly approved these recommendations, per standing
instruction.

**Baseline.** `phase-3b-planning-domain` @ `a600bf1ef29b96df7eb4f6d271e0ae175ed06d78`
(post PR #13/#14/#15/#16 — Phase 3D, including its documentation-closure and
research-sync passes, is fully canonical and closed as of this baseline).
This document does not re-litigate anything already RESOLVED in
`07-tdd-3d-action-engine.md`, `06-tdd-3c-capability-engine.md`, or
`05-tdd-3b-planning-engine.md` — those documents' fork resolutions are
treated as authoritative and are cited, not re-derived.

---

## 0. Scope of this document

A dedicated research and decision pass for Phase 3E's own four open
architectural forks (`08-tdd-3e-agent-os.md` §11), following the same
discipline already used for Phase 3C (`12-3c-architecture-research.md`) and
Phase 3D (`13-3d-action-engine-research.md`): every claim in the TDD is
independently re-verified against the actual, current state of the
repository — source code, contracts, tests, persistence schemas, event
definitions, and architecture documents — not taken on the TDD's own word,
even where the TDD's own proposals turn out to be well-grounded. Where the
TDD's own proposal is confirmed sound, that confirmation is recorded
explicitly, with the concrete evidence, rather than silently assumed. Where
independent verification surfaces something the TDD itself did not
disclose, it is flagged as a new finding (§8).

---

## 1. Documents and files inspected

| Document / file | What it was checked for |
|---|---|
| `docs/design/phase-3/08-tdd-3e-agent-os.md` (full, all 15 sections) | The complete Phase 3E design — scope, dependencies, target structure, all four forks' own proposals, event contracts, testing strategy, acceptance criteria, non-goals |
| `docs/architecture/12-agent-architecture.md` (full, all 15 sections) | The canonical NAOS architecture TDD 3E implements — `AgentHandler`/`AgentContext`/`AgentHealth`/`AgentMetrics` field-level shapes (§4), lifecycle state machine (§5), Registry pipeline (§6), Kernel Scheduler (§7), execution backends (§8), Supervision Trees (§9), Agent Mailbox and `AgentMessageType` (§10), permissions (§12), health monitoring (§13), Chief Executive boundary (§14), Phase 3 vs. full-architecture scope table (§15) |
| `docs/architecture/02-repository-and-folder-structure.md` (relevant sections) | `agent-os/`/`agents/` target layout, confirmed neither is a standard-engine-template instance |
| `docs/architecture/00-overview-and-decisions.md` | ADR-005 (inline, not a separate file) — verified its exact text against TDD 3E's and doc 12's citations |
| `docs/architecture/13-auth-and-security.md` | `nova-auth` / `PermissionGrant` model doc 12 §12 depends on |
| `docs/architecture/adr/ADR-024-interface-versioning-from-day-one.md` | Schema-versioning convention, for `AgentMessage`'s placement in `events/agent_os.py` |
| `docs/architecture/adr/ADR-029-executive-cognition-optimizes-long-term-user-objectives.md` (full) | The actual policy behind `goal_tier` — what "ad_hoc" vs. "established" is supposed to mean and why it exists |
| `packages/nova-contracts/src/nova_contracts/entities.py` (full) | The Extraction-E "shared, never-serialized entity" pattern `AgentContext`/`AgentHealth`/`AgentMetrics`/in-process `AgentResult` must follow; confirms `Goal`'s prior divergence |
| `services/reasoning-engine/src/nova_reasoning_engine/clients/goals_client.py`, `domain/models.py` (`Goal`) | Exact current `GoalsPort` placeholder shape and `Goal` fields |
| `services/executive-cognition-engine/src/nova_executive_cognition_engine/clients/goals_client.py`, `domain/models.py` (`Goal`) | Same, for the engine whose `Goal` already carries `goal_tier` |
| `services/planning-engine/src/nova_planning_engine/domain/models.py` (`TaskGraph`, `TaskNode`, `Estimate`) | Exact fields available to derive `goal_tier` from a `TaskGraph` |
| `services/action-engine/src/nova_action_engine/repository/models.py`, `domain/pipeline.py` (rollback section) | The established per-engine Postgres-schema/SQLAlchemy pattern, and the natural-key idempotency/terminal-state-check precedent Fork 3E-2 must follow |
| `services/capability-engine/src/nova_capability_engine/adapters/git_adapter.py`, `domain/builtin_capabilities.py`, `adapters/registry.py`, `config.py` | Whether a `git` capability already exists for the end-to-end acceptance test's "real git commit" step |
| `tools/scaffold-engine.py` (header, `_NAME_PATTERN`, `SERVICES_DIR`) | Exact scaffolding constraints Fork 3E-4 must work around |
| `docs/design/phase-3/01-tdd-preparation-and-fork-resolutions.md` §5.4/§5.5 | Two facts TDD 3E cites without re-deriving: that no persistence technology is named anywhere for the Kernel, and that `AgentContext` is never serialized in the `inprocess` backend |
| `docs/roadmap/ENGINEERING_ROADMAP.md:505-550` | The binding acceptance-criteria spec TDD 3E §14 quotes verbatim |

---

## 2. Repository evidence discovered (summary, detail folded into each fork below)

- **`GoalsPort`'s current placeholder is real and confirmed identical** in
  both engines: `current_goals(self, *, user_id: UUID, scope: str | None = None, correlation_id: UUID | None = None) -> list[Goal]`, both bodies `return []`, both docstrings independently describe themselves as "an honest placeholder, not a real RPC," both citing the same "becomes a real RPC without changing this port's own shape or any caller" precedent.
- **`Goal` has already diverged, exactly as TDD 3E claims**, and `nova_contracts/entities.py`'s own docstring is the authoritative record of *why* it was excluded from the Extraction-E shared-entity pass: `reasoning-engine`'s `Goal` is `{id, description, priority}`; `executive-cognition-engine`'s is `{id, description, priority, goal_tier: Literal["ad_hoc", "established"] = "ad_hoc"}`.
- **`TaskGraph` carries exactly the fields TDD 3E's heuristic needs**: `root_objective: str`, `nodes: list[TaskNode]`, `critical_path: list[UUID]` — `nodes` in particular gives a direct, deterministic multi-node-vs-single-node signal (§5 below).
- **`tools/scaffold-engine.py`'s constraints are exactly as TDD 3E describes**: `_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*-engine$")` (hard `-engine` suffix requirement) and `SERVICES_DIR = REPO_ROOT / "services"` (hardcoded).
- **The established per-engine persistence pattern** (`action-engine`'s `Base.metadata = MetaData(schema="action")`, one dedicated Postgres schema per engine, natural-key idempotency via the primary key alone) is a direct, reusable precedent for Fork 3E-2 — not a pattern that needs to be invented.
- **A `git` capability adapter already exists and is already wired into `capability-engine`'s registry** (`adapters/registry.py`: `"git": GitAdapter(terminal=terminal)`), executing via `terminal.run_subprocess("git", args, cwd=...)`, with `git` present in `sandbox_terminal_allowed_executables`. This is a materially significant finding for §7 below — the "real git commit" step of TDD 3E's own binding end-to-end acceptance criterion is **already fully supported** by the existing `capability-engine`/`action-engine` pair; Phase 3E adds no new capability-layer work for that specific step.
- **A genuine, previously-undisclosed dependency gap: `packages/nova-auth` does not exist.** Doc 12 §12 requires every `agent.yaml`'s `required_permissions` be "checked against `nova-auth`'s Permission Grant model... at install time... and re-validated at every `execute()` invocation." `docs/architecture/13-auth-and-security.md` §4 defines the intended `PermissionGrant` model and `nova-auth.authorize(principal, resource, action)` call — but no `packages/nova-auth` directory, and no `PermissionGrant`/`PermissionSet` type, exists anywhere in the repository (confirmed by a repo-wide search). TDD 3E itself never mentions this gap. See §8.

---

## 3. Fork 3E-1 — `AgentResult`/`AgentMessage` field shapes

### Current repository evidence

- Doc 12 §4 already fully specifies `AgentHandler.execute(self) -> AgentResult`, `AgentHandler.self_validate(self, result: AgentResult) -> ValidationOutcome`, and `AgentHandler.on_message(self, message: AgentMessage) -> AgentMessage | None` — so both types are consumed as function arguments/return values in the one fully-specified contract that already exists, but neither is given field-level definition there or anywhere else in doc 12 (confirmed: grepped every mention of `AgentResult`/`AgentMessage` across doc 12's 422 lines — every occurrence is a bare type reference, never a class body).
- Doc 12 §4 does fully specify `AgentContext.correlation_id: UUID` — confirming a `correlation_id` field is already an established part of the same request/response family `AgentResult`/`AgentMessage` belong to, not a new concept TDD 3E would be introducing.
- Doc 12 §10 fully specifies `AgentMessageType` as a closed `Enum` with 8 members (`ASSIGN`, `PAUSE`, `RESUME`, `PEER_REVIEW_REQUEST`, `PEER_REVIEW_RESULT`, `CONFLICT_ESCALATION`, `DELEGATION`, `HEALTH_PING`) and states messages route over `agent_os.instance.<instance_id>.inbox`, a real Event Bus subject.
- Every existing RPC request/reply payload pair in this repository (`ActionExecuteRequestPayload`/`ActionResultPayload`, `CapabilityResolveRequestPayload`/`.ReplyPayload`, etc.) carries a `correlation_id: UUID` and `schema_version: int = 1` (ADR-024), and is registered via `@register_payload("<subject>")`.
- `nova_contracts/entities.py`'s own docstring states the Extraction-E rule precisely: a type is `entities.py`-eligible only if it is "never published on the Event Bus directly (no `@register_payload`)." `AgentMessage` **is** published (over the per-instance inbox subject) — it therefore does not qualify for `entities.py` by this project's own already-applied test, and belongs in `events/agent_os.py` instead, `@register_payload`-decorated and `schema_version`-carrying like every other wire payload.
- `AgentResult`, by contrast, is consumed in two different ways depending on caller: (a) in-process, as `AgentHandler.execute()`'s direct return value (never serialized, per `01-tdd-preparation-and-fork-resolutions.md` §5.5's confirmed "inprocess backend passes `AgentContext` as a live Python object" fact, which applies identically to `AgentResult` since both cross the same in-process boundary); and (b) carried *inside* an `AgentMessage.payload: dict` when a `PEER_REVIEW_RESULT` message is sent — at which point it is being serialized, but as the payload of an already-versioned envelope, not independently.

### Existing architectural constraints

- ADR-004 (engine independence) / the Agent SDK boundary (doc 12 §4's closing line: "an agent never imports the Event Bus SDK directly for peer communication — all... communication goes through `on_message`") — `AgentResult` itself must never be independently published; only `AgentMessage` (its envelope) is.
- ADR-024 (interface versioning from day one) — anything that crosses the wire needs `schema_version: int = 1`; anything that doesn't, doesn't (matching `entities.py`'s own existing types, none of which carry `schema_version`).
- The already-established "disclose the proposed shape, do not silently invent it into an already-approved document" discipline used for `Estimate`/`RiskLevel` (3B), `CapabilityHandle` (3C), and `RetryPolicy`/`RollbackStrategy` (3D) — TDD 3E's own §6 already follows this discipline for its proposal; this document's job is to verify, not to redesign from a blank page.

### Options considered

1. **Adopt TDD 3E §6's proposed shapes as-is.**
2. **Merge `AgentResult` and `AgentMessage` into one type**, since `AgentResult` is always transmitted via an `AgentMessage.payload` when it crosses a process boundary. Rejected: this would conflate two genuinely different concerns — `AgentResult` is *what an agent produced*, independent of how it travels; `AgentMessage` is *the mailbox envelope*, used for eight different message types of which `PEER_REVIEW_RESULT` (carrying an `AgentResult`) is only one. `ASSIGN`/`PAUSE`/`RESUME`/`HEALTH_PING` messages carry no `AgentResult` at all. Merging the two would force every `AgentMessage` consumer to reason about `AgentResult`-shaped fields it doesn't need seven-eighths of the time.
3. **Give `AgentResult` its own `schema_version` even though it is only ever serialized indirectly (inside `AgentMessage.payload: dict`).** Rejected: `AgentMessage` itself is the versioned envelope; the `payload: dict` it carries is deliberately untyped at the envelope level (matching every existing Event Bus pattern where a `dict` payload is validated by its *specific* consumer, not by the envelope), so a second, redundant version field on `AgentResult` would version something the envelope already versions.

### Recommended option

**Option 1 — adopt TDD 3E §6's proposed shapes, confirmed correct by this independent pass, with one placement clarification already implicit but worth stating explicitly: `AgentResult` lives in `nova_contracts.entities` (no `schema_version`, no `@register_payload`); `AgentMessage` lives in `nova_contracts.events.agent_os` (`schema_version: int = 1`, `@register_payload("agent_os.instance.<instance_id>.inbox")`).**

```python
# nova_contracts/entities.py addition
class AgentResult(BaseModel):
    """What an agent produced for one task assignment or one peer-review
    round. Never independently published -- travels in-process as
    AgentHandler.execute()'s return value, or (only when a peer-review
    round needs it elsewhere) inside an AgentMessage.payload."""

    agent_instance_id: UUID
    task_node_id: UUID
    status: Literal["success", "failure", "needs_revision"]
    output: dict
    confidence: float | None = None
    self_validation_passed: bool
    correlation_id: UUID


# nova_contracts/events/agent_os.py addition
@register_payload("agent_os.instance.<instance_id>.inbox")  # actual subject templated per-instance at publish time
class AgentMessage(BaseModel):
    message_type: AgentMessageType
    from_instance_id: UUID | None
    to_instance_id: UUID
    payload: dict
    correlation_id: UUID
    schema_version: int = 1
```

### Exact rationale

Both shapes were independently checked field-by-field against every place doc 12 actually constrains them (§4, §5, §9, §10) and found consistent — no field doc 12 requires is missing, and no field present has no traceable requirement. The placement split (`entities.py` vs. `events/agent_os.py`) is not a new judgment call; it is the direct, mechanical application of a test this project already wrote down and already applied once (`entities.py`'s own docstring) to a new pair of types.

### Consequences for implementation

- New file `packages/nova-contracts/src/nova_contracts/events/agent_os.py` — `AgentMessage`, `AgentMessageType` (moved/re-exported from wherever doc 12 originally sketched it — confirmed not yet implemented anywhere in the repo), plus the aggregate `agent_os.health.snapshot` payload (doc 12 §13) and `agent_os.task.completed` payload (already anticipated by `3B` §6.1, confirmed present as a forward reference in `planning-engine`'s own domain, not yet a real registered payload).
- `nova_contracts/entities.py` gains `AgentResult`, `AgentContext`, `AgentHealth`, `AgentMetrics` (all four, since none of them cross the wire independently).
- TypeScript codegen must be re-run and re-verified zero-drift once these land, per this project's standing verification step.

### Required contract/code/schema changes

- `packages/nova-contracts/src/nova_contracts/entities.py`: add `AgentResult`, `AgentContext`, `AgentHealth`, `AgentMetrics`.
- `packages/nova-contracts/src/nova_contracts/events/agent_os.py` (new): `AgentMessage`, `AgentMessageType`, `AgentOsHealthSnapshotPayload`, `AgentOsTaskCompletedPayload`.

### Required tests

- Contract round-trip tests for `AgentMessage` (all 8 `AgentMessageType` values), `agent_os.health.snapshot`, `agent_os.task.completed` — mirroring `test_action_payloads.py`'s/`test_capability_payloads.py`'s existing pattern.
- A direct assertion that `AgentResult` has no `@register_payload` decorator and no `schema_version` field (guarding against a future accidental promotion to a wire type), mirroring the existing `entities.py` types' own lack of such tests today (none of the four currently-extracted types have this specific guard — worth adding for all of `entities.py`, not just the new additions, as a small hardening improvement flagged for the user's awareness, not a blocking requirement).

### Required documentation updates

- TDD 3E §6 gets a short additive note recording that this document independently re-verified and confirmed its proposal (§10 below covers the exact wording).

---

## 4. Fork 3E-2 — Kernel persistence schema

### Current repository evidence

- `01-tdd-preparation-and-fork-resolutions.md` §5.4 (cited, not re-derived, per this pass's own re-check): a full-file grep of doc 12 confirms it names no persistence technology anywhere for the Kernel's own state.
- The established pattern, confirmed directly in `action-engine`'s own `repository/models.py`: one dedicated Postgres **schema** per engine (`Base.metadata = MetaData(schema="action")`), SQLAlchemy `DeclarativeBase` models with `PG_UUID(as_uuid=True)` primary keys, an Alembic `versions/0001_initial_schema.py` hand-written to match the ORM models "precisely, the same convention as every prior engine" (the file's own docstring). `capability-engine` and `planning-engine` follow the identical pattern (each with its own schema name).
- The natural-key idempotency precedent, confirmed directly in the same file: `Action.id` is both the domain identifier and the Postgres primary key, and its primary-key uniqueness alone is "the actual concurrent-retry safety net" (no separate idempotency-key table, no application-level locking) — the exact mechanism Fork 3C-4 established first and Fork 3D §5.3 (already implemented, Phase 3D closed) reused verbatim.
- Doc 12 §7's restart-survival requirement ("Killing `agent-os-kernel` mid-execution and restarting resumes in-flight Task Graph work rather than restarting it from scratch," `ENGINEERING_ROADMAP.md:545`) requires *some* persistent record of which `TaskNode`s are currently assigned to which agent instances, surviving a process restart — this cannot be satisfied by in-memory-only Kernel state, confirming persistence is required, not merely convenient.
- `action-engine`'s own real-Postgres restart-survival precedent already exists for a structurally similar problem: `services/action-engine/tests/integration/test_repository_real_postgres.py` proves idempotency "surviving a real restart" (per `13-3d-action-engine-research.md` §9's own test-plan entry, confirmed implemented and passing per Phase 3D's closure). This is the direct testing-pattern precedent for Fork 3E-2's own restart-survival requirement, not a new testing approach that needs to be invented.

### Existing architectural constraints

- Fork 3C-2 (RESOLVED, Option C, declared-intent only): the Kernel Scheduler does **not** query `capability-engine`, maintain a capability cache, or gain any new step for `AgentContext.granted_capabilities` — confirmed still correctly unaffected by this fork; `agent_instance` persistence carries no capability-related columns.
- "Avoid duplicating state already owned by another engine" (this task's own explicit instruction, matching this project's established boundary discipline, e.g. Fork 3C-1/3D-1's adapter-ownership resolution): `TaskNode` state itself (`status`, `depends_on`, etc.) is already owned and persisted by `planning-engine` — the Kernel must never maintain its own parallel copy of a `TaskNode`'s status. It may only reference a `TaskNode` by `id` and publish/consume the existing events that mutate that status in `planning-engine` itself.

### Options considered

1. **Adopt TDD 3E §4's proposed `agent_os` schema (`agent_instance` + `agent_package` tables) as-is.**
2. **Reuse `planning-engine`'s own Postgres schema for `agent_instance`, since the Kernel's restart-reconciliation logic reads/writes `TaskNode.status`.** Rejected: `agent_instance` is Kernel-owned state about *which process is running what*, not `planning-engine`-owned state about *what the task graph looks like* — these are genuinely different aggregates with different lifecycles (an `agent_instance` row is meaningless once its process instance dies; a `TaskNode` row persists across many different agent instances that might attempt it over time). Colocating them in one schema would blur an ownership boundary this project has consistently kept sharp (every engine owns exactly its own schema; cross-engine reads happen over RPC, never a shared table).
3. **No Kernel persistence at all — treat `inprocess` execution as inherently best-effort, and let `planning-engine`'s own eventual re-scheduling (if any) recover from a Kernel crash.** Rejected: `planning-engine`'s own `TaskNode.status` has no mechanism today to detect "an agent instance that was assigned this node has silently disappeared" — without Kernel-side persistence, a Kernel crash mid-task would leave the `TaskNode` permanently stuck at `"assigned"`/whatever intermediate status the Kernel last reported, with nothing to ever re-queue it. This directly fails the roadmap's own named, binding acceptance criterion (`ENGINEERING_ROADMAP.md:545`).

### Recommended option

**Option 1 — adopt TDD 3E §4's proposed schema, confirmed to follow this project's own established per-engine-schema and natural-key-idempotency conventions precisely, with the ownership boundary from Fork 3C-2 (declared-intent-only `granted_capabilities`) explicitly re-confirmed as unaffected.**

```python
# agent-os/kernel's own Postgres schema: "agent_os"
class AgentInstanceORM(Base):  # Base.metadata = MetaData(schema="agent_os")
    __tablename__ = "agent_instance"
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    agent_package_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    execution_backend: Mapped[str] = mapped_column(Text, nullable=False)  # "inprocess" only, Phase 3
    status: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_task_node_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    supervisor_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    health_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="unknown")

class AgentPackageORM(Base):
    __tablename__ = "agent_package"
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    health_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="unknown")
    __table_args__ = (UniqueConstraint("category", "version"),)
```

### Exact rationale

Every structural choice here — one dedicated schema, `DeclarativeBase` + `PG_UUID` primary keys, an id-only foreign reference to `TaskNode` rather than a copy of its status — is the direct, mechanical continuation of a pattern this project has now applied identically across `capability-engine`, `action-engine`, and (implicitly) `planning-engine`. Nothing here is a new architectural pattern; it is the fourth application of an already-three-times-proven one. The `(category, version)` unique constraint on `agent_package` directly implements doc 12 §6's own multi-version-coexistence requirement ("mechanism exists from Phase 3") using the identical keying strategy `capability-engine`'s own install-idempotency (Fork 3C-4) already established for its own `(name, version)` pair.

### Consequences for implementation

- `agent-os/kernel/repository/` (new): SQLAlchemy models above, an Alembic migration, and a `PostgresAgentInstanceRepository`/`PostgresAgentPackageRepository` pair — same shape as every existing engine's own repository layer.
- Kernel-restart reconciliation logic: on boot, `SELECT * FROM agent_instance WHERE status = 'running'`; for each row, publish the existing `planning-engine`-consumed event that resets `TaskNode.status` back to `"ready"` (the exact mechanism §4 of the TDD already names, reusing the event path §7/§11 of doc 12 already define — not a new event).
- Because `agent-os/kernel` is explicitly *not* a standard-engine-template instance (doc 02 §2, TDD 3E §2), this repository layer cannot reuse `tools/scaffold-engine.py`'s generated repository boilerplate verbatim — it is hand-written following the same `models.py`/`postgres_*_repository.py`/`alembic/versions/0001_initial_schema.py` file layout, not generated by the existing tool. This is directly related to, and reinforces the need resolved in, Fork 3E-4 below.

### Required contract/code/schema changes

- `agent-os/kernel/repository/models.py`, `postgres_agent_instance_repository.py`, `postgres_agent_package_repository.py`, `alembic/env.py`, `alembic/versions/0001_initial_schema.py`.
- `infra/docker/docker-compose.local.yml`: the Kernel's Postgres database/schema needs a place to live — confirm whether it reuses the existing shared `postgres` service (with its own `agent_os` schema, matching every other engine's own-schema-in-shared-instance pattern) or needs its own container. Given every other engine to date shares the one `postgres` service with a per-engine schema, the same pattern applies here with no new infrastructure — flagged for confirmation during implementation planning, not itself an open fork.

### Required tests

- Unit: reconciliation logic (a stuck `"running"` row correctly re-queues its `TaskNode`; a `"completed"`/`"failed"` row is left alone).
- Real-infrastructure: restart-survival test mirroring `action-engine`'s own `test_repository_real_postgres.py` pattern — insert an `agent_instance` row as `"running"`, simulate a Kernel restart (fresh repository instance against the same database), assert the reconciliation query correctly identifies it.
- Integration: `agent_package`'s `(category, version)` uniqueness — a second install attempt for an already-installed `(category, version)` pair is idempotent, not a duplicate-row error surfaced to the caller (mirroring Fork 3C-4's own already-tested concurrent-install-race handling).

### Required documentation updates

- `docs/architecture/07-database-architecture.md` gains a new `agent_os` schema section, following the exact structure its existing `action`/`capability`/`planning` sections already use.
- TDD 3E §4 gets a short additive note recording independent confirmation (§10 below).

---

## 5. Fork 3E-3 — `goal_tier` derivation heuristic

### Current repository evidence

- `Goal.goal_tier: Literal["ad_hoc", "established"] = "ad_hoc"` — confirmed, exact type and both members, in `executive-cognition-engine`'s own `domain/models.py`. There are exactly two supported tiers; no third value exists anywhere in the codebase.
- ADR-029 (read in full) is the authoritative statement of what the distinction is *for*: `long_term_alignment` scoring "reflecting how strongly a request's associated goal... ties to a durable, ongoing objective rather than an isolated one-off," used only as a late tie-break in arbitration (composite score → deadline → `long_term_alignment` → correlation-ID fallback), and explicitly scoped today as "caller-supplied and coarse... not a rich Mission → Long-Term-Goal → Project → ... hierarchy," to be extended "once Planning Engine's real hierarchy exists" — this is precisely the extension point TDD 3E's own §8 is now filling.
- `TaskGraph` (`services/planning-engine/src/nova_planning_engine/domain/models.py`) carries `root_objective: str`, `nodes: list[TaskNode]`, `critical_path: list[UUID]` — `nodes` is populated by `planning-engine`'s own existing decomposition pipeline (Phase 3B); a `TaskGraph` produced by a genuine multi-step decomposition necessarily has `len(nodes) > 1`, while a graph that was never decomposed (the caller's objective was already atomic, or decomposition determined no further breakdown was needed) has `len(nodes) == 1` (the root task itself, undecomposed) — this is a real, already-existing, deterministic signal, not a value TDD 3E would need `planning-engine` to add.

### Existing architectural constraints

- ADR-029's own scope statement above is binding: this is a **tie-break-only** signal, not a primary priority driver — a heuristic that over- or under-classifies goals cannot silently change which request "wins" outright, only which of two otherwise-tied requests wins. This bounds how much precision the heuristic actually needs to get right.
- The Goal-mapping RPC itself (`planning.goals.current.request`/`.reply`) is new API surface on an already-shipped, closed engine (`planning-engine`, Phase 3B) — per this project's own "additive, never re-opens a closed decision" discipline (the same discipline applied to `capability-engine`'s `find_by_name` addition in Phase 3D), it must not touch any existing `TaskGraph`/`TaskNode` field or behavior.

### Options considered

1. **`goal_tier = "established"` iff `len(task_graph.nodes) > 1`, else `"ad_hoc"`** (TDD 3E's own proposal, restated precisely).
2. **Derive from `critical_path` non-emptiness instead of `nodes` count.** Rejected on inspection: `critical_path` is a plain, caller-supplied field (per `TaskGraph`'s own docstring, computed by the separate pure function `compute_critical_path()`, not auto-populated) — using it as the primary signal would make `goal_tier` depend on whether a caller happened to also compute and attach a critical path, which is a weaker, more accidental signal than the graph's own `nodes` count (always populated, by construction, the moment decomposition runs).
3. **A three-or-more-tier scheme** (e.g., adding a "major" tier for graphs above some node-count threshold). Rejected: `Goal.goal_tier`'s type is already fixed as a two-member `Literal` in an already-shipped engine (`executive-cognition-engine`); introducing a third value would be a breaking change to a closed Phase 2C decision, wildly out of proportion to what ADR-029's tie-break-only usage actually needs, and not requested by any document.
4. **Persist `goal_tier` on the `TaskGraph`/`TaskNode` model itself**, rather than deriving it fresh on every `planning.goals.current.request` call. Rejected: `goal_tier` is entirely a pure function of already-persisted `TaskGraph` state (`len(nodes)`); persisting a second, derived copy would create exactly the kind of "two sources of truth that can drift" problem this project's boundary discipline (§4 above) already avoids elsewhere. Deriving it at read time is also strictly cheaper to keep correct — there is no migration or backfill question if the heuristic itself is ever refined later.

### Recommended option

**Option 1 — `goal_tier = "established"` iff `len(task_graph.nodes) > 1`, else `"ad_hoc"`, computed at read time inside `planning-engine`'s new `planning.goals.current.request` handler, never persisted.**

- **Inputs:** the requesting `TaskGraph`'s own `nodes: list[TaskNode]` field (already in the database, already loaded to build the reply).
- **Deterministic rule:** `"established"` if `len(nodes) > 1`; `"established"` is not derived from the calling engine, the task's risk level, or any other field this fork was tempted to fold in but that ADR-029 never asked for.
- **Supported tiers:** exactly the two `Goal.goal_tier` already supports — no new tier introduced.
- **Fallback for invalid/unknown input:** not reachable — `len()` of a list is always defined and non-negative; there is no invalid input this function can receive short of a malformed `TaskGraph`, which would already have failed Pydantic validation upstream before this heuristic ever runs.
- **Persisted or derived:** derived, every call, never persisted — see option 4's rejection above.
- **Component:** `planning-engine` itself (inside its own new RPC handler), not the Kernel or a Supervisor — `planning-engine` already owns `TaskGraph`, this is a pure read-time projection of data it already has, and placing it anywhere else would require exporting `TaskGraph.nodes` to a component that has no other reason to see it.
- **Tests required:** a unit test asserting the exact boundary (`len(nodes) == 1` → `"ad_hoc"`; `len(nodes) == 2` → `"established"`; empty `nodes` list, an edge case not explicitly named by the TDD but worth pinning down explicitly — treated as `"ad_hoc"`, consistent with "not yet decomposed into anything" reading no differently from "decomposed into exactly the root itself"), plus a contract test on the `planning.goals.current.request`/`.reply` round-trip itself.

### Exact rationale

The heuristic is fully explainable in one sentence ("a goal is `established` the moment its task graph shows real, multi-step decomposition, and `ad_hoc` otherwise"), uses a field that already exists for an unrelated reason (Critical Path Analysis, Fork 3B-1) rather than introducing new state, and is bounded in its actual consequences by ADR-029's own tie-break-only scope — exactly the "honest, buildable slice... extended, not redesigned, once Planning Engine's real hierarchy exists" posture ADR-029 itself anticipates.

### Consequences for implementation

- New RPC `planning.goals.current.request`/`.reply`, served by `planning-engine`, mapping each of a user's active `TaskGraph`s to one `Goal(id=task_graph.id, description=task_graph.root_objective, priority=<derived from critical-path position>, goal_tier=<per this heuristic>)`.
- `reasoning-engine`'s and `executive-cognition-engine`'s `clients/goals_client.py` are each swapped from the `return []` placeholder to a real RPC call — `GoalsPort`'s own Protocol signature, and every one of its callers, is unchanged (confirmed: the docstrings in both current placeholder files already assert this transition was designed for from day one).
- `priority`'s own derivation ("from critical-path position") is a separate, smaller design detail the TDD's §8 leaves implicit — recommended as: a `TaskNode`'s position in `critical_path` (earlier = higher priority; a node not on the critical path at all gets a lower default), a direct, small extension of data the `TaskGraph` already carries, not itself a fork requiring separate approval, but flagged here for visibility since it wasn't spelled out in TDD 3E's own text.

### Required contract/code/schema changes

- `nova_contracts/events/planning.py`: `PlanningGoalsCurrentRequestPayload`/`.ReplyPayload` (new, additive, `schema_version: int = 1`).
- `services/planning-engine/src/nova_planning_engine/main.py`: new RPC handler.
- `services/planning-engine/src/nova_planning_engine/domain/`: the pure `goal_tier`/`priority` derivation functions (kept as plain functions operating on `TaskGraph`, matching this codebase's established "domain functions operate on and return plain models" style — the same style `TaskGraph`'s own docstring already documents for `compute_critical_path()`).
- `services/reasoning-engine/.../clients/goals_client.py`, `services/executive-cognition-engine/.../clients/goals_client.py`: real RPC calls replacing the `return []` placeholders.

### Required tests

- Unit (goal_tier boundary, as above).
- Contract round-trip for the new RPC payload pair.
- Integration: `GoalsClient.current_goals()` against a real in-memory bus paired with `planning-engine`'s served handler (the established "second `BoundEventBus`" pattern used throughout Phase 3C/3D).
- Regression: an unmodified-caller test in both `reasoning-engine` and `executive-cognition-engine` proving `GoalsPort`'s own callers needed zero changes (this is TDD 3E §14's own acceptance criterion 4, restated here as the corresponding test requirement).

### Required documentation updates

- `docs/design/phase-3/05-tdd-3b-planning-engine.md` gains a short additive note disclosing the new `planning.goals.current.request` RPC — the same "genuinely-discovered-during-implementation necessity" treatment already given to the Fork D/`proactive_delivery_record` precedent TDD 3E's own §8 cites.
- TDD 3E §8 gets a short additive note recording independent confirmation (§10 below).

---

## 6. Fork 3E-4 — Scaffolding tooling approach

### Current repository evidence

- `tools/scaffold-engine.py`'s exact constraints, read directly: `_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*-engine$")` (line 28, hard requirement — a name that doesn't end in `-engine` is rejected outright, not merely discouraged) and `SERVICES_DIR = REPO_ROOT / "services"` (line 25, hardcoded, not a parameter). The script's own module docstring confirms its generated output "boots (FastAPI + lifespan-managed EventBus connection), exposes `/internal/health`, `/internal/readiness`, `/internal/metrics`... and ships with one passing smoke test" — a full engine template, not a minimal one.
- Doc 02 §2 (cited by TDD 3E) is explicit that neither `agent-os/kernel` nor `agents/<name>-agent` is an instance of this template — confirmed consistent with the constraints above: `agent-os/kernel` needs the *minimal* health-only surface (TDD 3E §4), not the full REST/events/repository template the existing script always generates, and `agents/<name>-agent` needs an `agent.yaml` + `src/handler.py` + `tests/` layout (doc 12 §3) that has nothing structurally in common with either template.
- The one precedent for a scaffold-adjacent tooling extension already in this repository's own history, `01-tdd-preparation-and-fork-resolutions.md` §3's finding about `_update_root_pyproject`'s contract-matching being "currently keyed to engine-specific contract-name strings" — a real, already-disclosed generalization gap in the existing script, independent of Phase 3E, that either approach below would need to touch.

### Options considered

1. **A new, separate script, `tools/scaffold-agent-os-component.py`**, for `agent-os/<name>/` components, plus a second, distinct scaffold for `agents/<name>-agent/` Agent Packages.
2. **A `--target agent-os` (and `--target agent`) flag on the existing `scaffold-engine.py`**, branching internally to generate the appropriate skeleton.

### Advantages and disadvantages

| | New script(s) | Flag on existing script |
|---|---|---|
| **Advantage** | `_NAME_PATTERN`, `SERVICES_DIR`, and the always-on-FastAPI-service assumption never need a single conditional carve-out inside the one script every one of the 13 existing engines' own CI depends on being unchanged and stable — zero regression risk to the proven, working engine-scaffolding path. | One fewer file for a future maintainer to discover; `tools/` stays smaller. |
| **Disadvantage** | Three logically-related scaffold entry points (`scaffold-engine.py`, `scaffold-agent-os-component.py`, and a third for `agents/<name>-agent/`) instead of one. | Every one of `_NAME_PATTERN`'s validation, `SERVICES_DIR`'s hardcoded path, and the FastAPI-template generation logic must grow an `if target == "agent-os"` / `elif target == "agent"` branch — for skeletons that, per doc 02 §2's own explicit statement, are **not** the same template at all (no REST surface, no events/repository layers, different directory root entirely). This is exactly the "branching inside the existing script would add more conditional complexity than a small, separate script" risk TDD 3E's own §3 already names. |

### Recommendation

**New, separate scripts — one for `agent-os/<name>/` components, a second, distinct one for `agents/<name>-agent/` Agent Packages — confirmed by this independent pass, not merely restated from TDD 3E's own recommendation.**

The disqualifying fact for the flag approach is structural, not stylistic: `agent-os/kernel` (minimal health-only FastAPI) and `agents/<name>-agent` (`agent.yaml` + `src/handler.py` + `tests/`, no FastAPI surface at all) are not two variations on one template — they are two additional, genuinely different templates, on top of the one `scaffold-engine.py` already generates. A single script generating three structurally distinct skeletons via one dispatch flag would make every future reader of that script's own code carry all three templates' worth of complexity in one file, for a maintenance cost `tools/scaffold-engine.py`'s own precedent (one script, one template, in production stably since Phase 1) never had to pay. Both new scripts are still required, this pass confirms, to update `root_packages` and the relevant import-linter contracts, generalizing `_update_root_pyproject`'s already-disclosed contract-matching gap — the same requirement TDD 3E's own §3 already names, unaffected by which tooling shape wins.

### Consequences for implementation

- `tools/scaffold-agent-os-component.py` (new): generates under `agent-os/<name>/`, no `-engine` suffix requirement, minimal health-only skeleton, updates `root_packages`/import-linter.
- `tools/scaffold-agent-package.py` (new, distinct): generates under `agents/<name>-agent/`, `agent.yaml` + `src/handler.py` + `tests/` layout per doc 12 §3, updates `root_packages`/import-linter identically.
- `tools/scaffold-engine.py` itself: **zero changes** — this recommendation's entire point is that the existing, proven script for the 13 already-shipped engines stays exactly as it is.
- `_update_root_pyproject`'s contract-matching generalization (the pre-existing gap both new scripts need) is shared, reusable logic — worth factoring into one small shared helper both new scripts import, rather than duplicating the fix twice.

### Required test/CI changes

- A smoke test for each new script (mirroring however `scaffold-engine.py`'s own generation is currently verified, if at all — flagged: no existing test was found that actually invokes `scaffold-engine.py` end-to-end and asserts the generated engine passes `turbo run lint test`; the two new scripts should not regress below that same, already-accepted bar).

### Required documentation updates

- `docs/architecture/02-repository-and-folder-structure.md` §3 (or a new adjacent section) documents both new scaffold entry points, mirroring how §3 already documents `scaffold-engine.py` itself.
- TDD 3E §3 gets a short additive note recording independent confirmation (§10 below).

---

## 7. Phase 3E scope verification against the repository

| Scope item | Status |
|---|---|
| `agent-os/kernel` | Does not exist. Confirmed via fresh directory check. |
| `agent-os/sdk/python` | Does not exist. |
| `agent-os/registry` | Does not exist. |
| `agent-os/supervisors` | Does not exist. |
| `research-agent`, `coding-agent`, `qa-agent`, `architect-agent`, `documentation-agent` (`agents/`) | None exist. |
| `engineering` Supervisor | Does not exist (it is one of the five agent-adjacent packages above, category `supervisor`). |
| `GoalsPort` real-RPC migration, `reasoning-engine` | Not yet migrated — confirmed still the `return []` placeholder, exactly as TDD 3E states. |
| `GoalsPort` real-RPC migration, `executive-cognition-engine` | Same — confirmed still the `return []` placeholder. |

**Dependencies (`3B`, `3C`, `3D`) — all satisfied.** `planning-engine` (3B, both sub-units), `capability-engine` (3C), and `action-engine` (3D) are all merged into canonical `phase-3b-planning-domain`, closed, Gate-Reviewed Go, with Project Health records. Nothing in this scope-verification pass found a dependency Phase 3E needs that is not already shipped, **except** the `nova-auth` gap in §8 below, which is not one of TDD 3E's own three named dependencies but is required by the architecture doc (12 §12) TDD 3E itself implements.

---

## 8. New finding: `packages/nova-auth` does not exist

**Not one of the four named forks — a dependency gap this independent pass
found, that TDD 3E itself does not disclose or discuss.**

Doc 12 §12 (Permissions) states every `agent.yaml`'s `required_permissions`
is "checked against `nova-auth`'s Permission Grant model... at install time
(Registry, §6) and re-validated at every `execute()` invocation (Kernel,
§7)." `docs/architecture/13-auth-and-security.md` §4 defines the intended
`PermissionGrant` model and a `nova-auth.authorize(principal, resource,
action)` call, all "implemented behind one `packages/nova-auth`
interface." A repository-wide search confirms: **no `packages/nova-auth`
directory, and no `PermissionGrant`/`PermissionSet` type, exists anywhere
in this codebase.** This is not a Phase 3E-specific gap — `nova-auth` has
never been built in any phase to date — but Phase 3E is the first phase
whose own architecture document (doc 12 §12) names it as a required,
concrete dependency for a specific mechanism (permission enforcement at
Registry-install-time and Kernel-execute-time).

This is structurally the same shape of question Fork 3C-2
(`granted_capabilities`, resolved as Option C — "declared-intent only," no
runtime enforcement mechanism built) already answered once for a different
field on the same `AgentContext`/`Capability` boundary. Given that
precedent, and that TDD 3E's own §14 acceptance criteria and §13 testing
strategy never mention permission enforcement as something Phase 3E must
prove, the two live options are:

- **(a)** Treat `agent.yaml`'s `required_permissions` the same way Fork 3C-2
  treated `granted_capabilities` — declared in the manifest, surfaced to
  the user at Registry install-time (§6's own "Permission review —
  surfaced to user if new/elevated" step, which needs no `nova-auth` call
  to implement as a simple diff-and-display), but **not** enforced by a
  real `nova-auth.authorize()` call at every `execute()` — an explicitly
  disclosed, deferred gap, not a silently skipped one.
- **(b)** Build a minimal `packages/nova-auth` (just enough for
  `authorize(principal, resource, action)` and `PermissionGrant`) as an
  in-scope prerequisite of Phase 3E's own implementation PR, the same way
  Phase 3D added a small additive extension to `capability-engine`'s
  contract surface as an in-scope prerequisite of its own implementation.

**This document does not resolve this question — it is flagged for the
user's explicit decision alongside the four named forks (§9).** Unlike
Forks 3E-1 through 3E-4, no concrete proposal for this exists anywhere in
TDD 3E's own text to independently verify or refine; a genuine, unproposed
scope decision, not a proposal-verification.

---

## 9. Unresolved decisions requiring the user's approval

1. **Fork 3E-1** (`AgentResult`/`AgentMessage` shapes) — recommended:
   adopt TDD 3E §6's proposal as-is, with the `entities.py` vs.
   `events/agent_os.py` placement split confirmed correct. **Awaiting
   approval.**
2. **Fork 3E-2** (Kernel persistence schema) — recommended: adopt TDD 3E
   §4's proposed `agent_os` schema (`agent_instance` + `agent_package`)
   as-is, confirmed to follow the established per-engine-schema and
   natural-key-idempotency conventions. **Awaiting approval.**
3. **Fork 3E-3** (`goal_tier` derivation) — recommended:
   `"established"` iff `len(task_graph.nodes) > 1`, else `"ad_hoc"`,
   derived at read time in `planning-engine`, never persisted. **Awaiting
   approval.**
4. **Fork 3E-4** (scaffolding tooling) — recommended: two new, separate
   scripts (`scaffold-agent-os-component.py`, `scaffold-agent-package.py`);
   `scaffold-engine.py` itself unchanged. **Awaiting approval.**
5. **New finding, not a named fork** (§8): whether `agent.yaml`
   permissions are (a) declared-intent-only in Phase 3E (mirroring Fork
   3C-2's precedent, no `nova-auth` build required), or (b) actually
   enforced via a new, minimal `packages/nova-auth` built as an in-scope
   Phase 3E prerequisite. **Awaiting the user's decision — no
   recommendation is made here, since either is architecturally
   defensible and the choice is a scope decision, not a technical one
   this pass can resolve on the evidence alone.**
6. **`priority`'s exact critical-path-position formula** (§5's
   "Consequences" section) — a small implementation-time detail flagged
   for visibility, not requiring the same weight of approval as items 1-5,
   but noted here so it is not silently decided during implementation
   without the user having seen it named.

**None of these six items blocks Phase 3D's own closure or any other
phase** — Phase 3D is fully closed and unaffected by this document. They
block only the start of Phase 3E's own implementation PR.

---

## 10. Proposed TDD 3E additive notes (not yet applied — for the user's approval alongside the forks above)

If forks 1-4 are approved as recommended, the following short, additive,
dated notes would be added to `08-tdd-3e-agent-os.md` (original text
preserved in every case, per this project's standing reconciliation
convention) — listed here rather than applied now, since applying them
before approval would misrepresent unapproved recommendations as decided:

- §3 (Scaffolding gap): a note recording Fork 3E-4's resolution and this
  document's citation.
- §4 (`agent-os/kernel` design): a note recording Fork 3E-2's resolution.
- §6 (`AgentResult`/`AgentMessage`): a note recording Fork 3E-1's
  resolution.
- §8 (`GoalsPort` migration): a note recording Fork 3E-3's resolution.
- §11 (Open architectural forks): each of the four fork entries gets a
  "Resolved, see `14-3e-agent-os-research.md` §N — pending final user
  approval" pointer, mirroring the exact struck-through-plus-resolution-note
  pattern already used for Phase 3D's own Fork §16 item 1.

---

## 11. Proposed implementation branch and PR structure (for later, once approved)

Following the exact precedent Phase 3D's own research document set: one
implementation branch, `phase-3e-agent-os`, based directly on
`phase-3b-planning-domain`, one PR against the same base, covering the
whole of Phase 3E's authorized scope (mirroring PR #8's and PR #13's
shape) — **unless** decision item 5 above resolves to option (b) (build
`nova-auth`), in which case a small, independent precursor PR for the
minimal `nova-auth` package (touching a package no other engine currently
depends on) is the safer sequencing, the same reasoning already applied to
Phase 3D's own `capability-engine` contract extension.

This section is descriptive, not authorizing — no branch has been created
by this document.
