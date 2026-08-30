# TDD 3E — `agent-os` (Kernel, SDK, Registry, Supervisors), the Five Agents,
## the `engineering` Supervisor, and the `GoalsPort` Migration

**Status: design complete, architectural decisions approved/resolved
(2026-08-19) — see §11 and each section's own resolution note. No
production code authorized.**

> **Status update, 2026-08-29 (Phase 3E Gate Review), additive.** The
> banner above is preserved as originally written; "no production code
> authorized" describes the state on 2026-08-19 and is no longer current.
> Phase 3E was subsequently implemented on branch `phase-3e-agent-os`
> (last production-source commit `60934ac`; **PR #20 open, unmerged; CI green
> — 27/27 Check Runs success against head SHA `733a31d`, 2026-08-30**). Gate
> verdict: **GO** (2026-08-30; CONDITIONAL-GO on 2026-08-29, upgraded when
> condition C-1 was discharged by that CI run — the six ratified narrowings
> in §4/§10 and the deferred obligation in §15 are unchanged by it) — see
> [`phase-3e-agent-os-gate-review.md`](../../roadmap/architecture-reviews/phase-3e-agent-os-gate-review.md).
> Three sections carry implementation-deviation notes added by that
> review and not previously disclosed anywhere: **§4** (the Scheduler's
> scoring step is not implemented), **§10** (three of six event contracts
> are not implemented), and **§14** (criteria #2 and #3 are met with
> disclosed narrowing, not by full-path E2E). §9 already carried its own
> D5 implementation note from 2026-08-29. Read those four notes before
> treating any other section of this document as a description of the
> shipped system.

This is the largest, most integrative TDD
in the package — it is the point at which `3B`/`3C`/`3D`'s
independently-buildable engines are actually exercised together for the
first time. Approval of the architectural decisions recorded here is a
separate step from approving the start of Phase 3E's own implementation
PR; the latter has not been given.

---

## 0. Scope and dependencies

**Scope.** `agent-os/{kernel,sdk/python,registry,supervisors}`
(ADR-008), the five named Agent Packages (`research-agent`,
`coding-agent`, `qa-agent`, `architect-agent`, `documentation-agent`),
the `engineering` Supervisor, and the real-RPC migration of `GoalsPort`
in both `reasoning-engine` and `executive-cognition-engine` — per
`ENGINEERING_ROADMAP.md:510-514,517` and `docs/architecture/12-agent-architecture.md`.

**Dependencies.** `3B` (`planning-engine` — Task Graphs to consume),
`3C` (`capability-engine` — capabilities to grant agents), `3D`
(`action-engine` — action dispatch target for agents that act). All
three must exist first; this TDD is the last of the five engine slices
by design.

---

## 1. Existing capability vs. what's being built

Nothing exists — confirmed: no `agent-os/` or `agents/` anywhere in the
repo (fresh directory check, this pass); no `AgentHandler`/`AgentResult`/
`AgentMessage`/`TaskGraph`-consuming code anywhere. `GoalsPort` exists in
both `reasoning-engine` and `executive-cognition-engine` today as an
honest placeholder returning caller-supplied/empty data (verbatim
Protocol confirmed identical in both engines; the `Goal` type each
returns has already diverged by one field, `goal_tier`, per ADR-029 —
see §8).

---

## 2. Target repository structure — doc 02, already specified

`docs/architecture/02-repository-and-folder-structure.md:53-83` (not
invented here, already authoritative):

```
agent-os/
├── kernel/                # process manager, scheduler, supervision, health
├── registry/               # discovery, install pipeline, versioning, hot load/unload
├── sdk/
│   └── python/              # nova-agent-sdk — AgentHandler Protocol, AgentContext, AgentMessage
└── supervisors/             # built-in domain supervisor agents

agents/
├── research-agent/
├── architect-agent/
├── coding-agent/
├── qa-agent/
└── documentation-agent/
```

Doc 02 (`:162-169`) is explicit: **neither `agent-os/kernel` nor
`agents/<name>-agent` is an instance of the standard engine template.**
`agent-os/kernel` is control-plane infrastructure; `agents/<name>-agent`
is a dynamically loadable Agent Package. Per the user's explicit
instruction this turn, `tools/scaffold-engine.py` is **not** forced onto
either — see §3.

`agent-os/execution-backends/` (`inprocess/subprocess/container/remote`)
is doc 02's full target, but **Phase 3 implements `inprocess` only** —
the `subprocess/container/remote` subdirectories are not created by this
TDD (Fork E3-adjacent discipline: don't build infrastructure ahead of
its documented phase).

---

## 3. Scaffolding/tooling gap — documented, not forced

Confirmed this pass (fresh read): `tools/scaffold-engine.py`'s
`_NAME_PATTERN` (line 28) requires a `-engine` suffix; `SERVICES_DIR`
(line 25) is hardcoded to `services/`; the generated skeleton assumes an
always-on FastAPI/uvicorn service with a Dockerfile `EXPOSE 8000`.
`agent-os/kernel` matches none of these assumptions.

**Required tooling change (not implemented by this TDD — a documented
prerequisite for `3E`'s own implementation, same treatment as `3B`/`3C`/
`3D`'s own contract-addition lists):**

1. A separate, small scaffold path (either a new
   `tools/scaffold-agent-os-component.py` or a `--target agent-os`
   flag on the existing script) that: creates under `agent-os/<name>/`
   instead of `services/`; does not require the `-engine` suffix;
   generates a **minimal** skeleton (§4's health-only FastAPI surface,
   not the full REST/events/repository template); still updates
   `root_packages` and the relevant import-linter contracts (generalizing
   `_update_root_pyproject`'s contract-matching, currently keyed to
   engine-specific contract-name strings, §3 of
   `01-tdd-preparation-and-fork-resolutions.md`'s finding).
2. A separate, distinct Agent Package scaffold for `agents/<name>-agent/`
   (doc 12 §3's `agent.yaml` + `src/handler.py` + `tests/` layout,
   `12-agent-architecture.md:53-91`) — structurally nothing like either
   the engine template or the agent-os component template.

**Flagged for approval** — this is real, disclosed tooling work that
must land before `3E`'s own code can be scaffolded, distinct from the
five engines' own straightforward use of the existing (unmodified)
`scaffold-engine.py`.

**RESOLVED (2026-08-19), additive note — Fork 3E-4.** Approved: two new,
separate scripts — `tools/scaffold-agent-os-component.py` (for
`agent-os/<name>/`, no `-engine` suffix, minimal health-only skeleton)
and a second, distinct `tools/scaffold-agent-package.py` (for
`agents/<name>-agent/`, the `agent.yaml` + `src/handler.py` + `tests/`
layout). The `--target` flag alternative is rejected — see
[`14-3e-agent-os-research.md`](14-3e-agent-os-research.md) §6 for the
full rationale (branching one script across three structurally distinct
templates was found to add more conditional complexity than two small,
separate scripts). `tools/scaffold-engine.py` itself is unchanged. This
note does not alter the proposal text above, which is preserved as
originally written.

---

## 4. `agent-os/kernel` — design

**Minimal health surface, not a full engine.** Per doc 02's own
"not an instance of this template" instruction (§2), `agent-os/kernel`
gets `nova-service-kit`'s `make_health_router()` (unmodified reuse,
confirmed domain-agnostic in `01-tdd-preparation-and-fork-resolutions.md`
§5.4) for `/internal/health`/`/internal/readiness`/`/internal/metrics`
only — no `/v1/...` public REST surface, since the Kernel's actual work
is Event-Bus-driven and internal-async-loop-driven, not request/reply.

**Kernel Scheduler** (`12-agent-architecture.md:229-238`, implemented
literally): on `planning.task_graph.created` (subscribed), for each
`TaskNode` with `status="ready"` (all `depends_on` complete): (1) query
Registry for healthy candidates in `assigned_agent_category`; (2) score
by historical performance (from `AgentMetrics`) + current load +
resource availability + Executive Cognition's Cognitive Priority Matrix
(consumed via the existing `executive-cognition-engine` scoring
mechanism, per `docs/design/phase-2c/00-executive-cognition-engine.md`
§5.10's own forward-stated boundary — this TDD is where that boundary
becomes real); (3) select `inprocess` (the only enabled backend); (4)
dispatch as a supervised instance under the owning Supervisor.

**Fork 3C-2 — RESOLVED: Option C, declared-intent only (approved; full
resolution record in `docs/design/phase-3/06-tdd-3c-capability-engine.md` §4).**
`action-engine`'s own stage 5 (TDD 3D §6) remains the sole live authority
for capability resolution and `health_status` checking at execution
time — unchanged by this resolution. The Kernel Scheduler's four-step
dispatch loop above is exactly as specified: it does **not** query
`capability-engine`, does not maintain a capability cache or registry
subscription, and gains no new step for `AgentContext.granted_capabilities`.
This field is not populated, synchronized, or otherwise given any runtime
mechanism by this TDD — it remains available only as declared-intent
context per doc 12's own (unchanged) field definition, never a second
source of capability authorization. Whether or how it is ever populated
is left as an undecided, separately-scoped future design question, not
invented here.

**Kernel persistence — new, since doc 12 names no persistence
technology for the Kernel's own state** (confirmed by full-file grep,
`01-tdd-preparation-and-fork-resolutions.md` §5.4). Proposed `agent_os`
Postgres schema: `agent_instance` (`id`, `agent_package_id`, `category`,
`execution_backend`, `status`, `assigned_task_node_id`, `supervisor_id`,
`started_at`, `health_status`) — this is what makes the roadmap's own
restart-survival acceptance criterion (`ENGINEERING_ROADMAP.md:545`)
possible: on Kernel restart, every `agent_instance` row still marked
`status="running"` (whose actual `inprocess` asyncio task died with the
Kernel process) is re-queued — its `assigned_task_node_id` is reset to
`"ready"` in `planning-engine` (via the same event path §7 uses) for
redispatch, never silently lost. **Flagged for approval** — this schema
is proposed, not extracted from any document.

**Implementation deviation, disclosed 2026-08-29 (Phase 3E Gate Review) —
the Scheduler's step (2), scoring.** The four-step dispatch loop above is
implemented as **three** steps, not four:
`agent-os/kernel/domain/scheduler.py::dispatch_task_node` performs (1) the
Registry query (`registry_port.find_healthy_package(category=...)`),
(3) backend selection (trivially — `inprocess` is the only backend), and
(4) dispatch. **Step (2) — "score by historical performance (from
`AgentMetrics`) + current load + resource availability + Executive
Cognition's Cognitive Priority Matrix" — is not implemented.** The
Registry's own selection policy (highest `healthy` version by
dotted-integer comparison, `agent-os/registry/domain/selection.py`) is the
sole selection input; there is no scoring function in the Kernel, and
`agent-os/kernel` makes no call to `executive-cognition-engine` (verified
by grep: no reference to `executive`, `arbitrate`, or `cognitive_priority`
anywhere under `agent-os/kernel/src/`).

Half of this gap was already disclosed, in
[`16-3e-hot-load-design-decision.md`](16-3e-hot-load-design-decision.md)
§5's "Registry scoring beyond version+health" bullet, which records that
`agent_package` stores no metrics columns and that "version and health are
the only selection inputs in Phase 3". That bullet cites doc 12 §6 and
names only the `AgentMetrics` inputs. **The remaining three inputs this
section names — current load, resource availability, and the Cognitive
Priority Matrix — were not disclosed anywhere until this note.** Recorded
here so the gap is visible against the section that actually specifies it.

**RATIFIED (2026-08-29) — an explicit Phase 3E narrowing, by the user's
decision in the Gate Review closure pass.** The three-step dispatch loop
is **approved as Phase 3E's scope**; the existing implementation is
preserved and the scoring step is **not** built by Phase 3E. The
four-input scoring design above remains the target architecture — the
narrowing is to Phase 3's scope, not to the design.

Two facts make this a cheap ratification rather than a concession. First,
**no acceptance criterion in §14 turns on scoring**, so the gate is not
weakened. Second, **the inputs do not exist to score with**: `agent_package`
persists no metrics columns (see
[`16-3e-hot-load-design-decision.md`](16-3e-hot-load-design-decision.md)
§5), the Kernel tracks no per-instance load or resource figures, and no
`executive-cognition-engine` RPC for the Cognitive Priority Matrix is
defined in any document. Building scoring in Phase 3 would therefore mean
first inventing three data sources — squarely the kind of architectural
invention this TDD refuses elsewhere. Re-scoped to the phase that gives
`AgentMetrics` real persistence. Recorded in
[`phase-3e-agent-os-gate-review.md`](../../roadmap/architecture-reviews/phase-3e-agent-os-gate-review.md)
§2 and §10 (condition C-4, now closed).

**RESOLVED (2026-08-19), additive note — Fork 3E-2.** Approved: the
proposed `agent_os` Postgres schema, `agent_instance` + `agent_package`
tables, adopted as-is. Independently re-verified against the
`action-engine` per-engine-schema and natural-key-idempotency precedent
in [`14-3e-agent-os-research.md`](14-3e-agent-os-research.md) §4 (exact
SQLAlchemy ORM given there). This note does not alter the proposal text
above, which is preserved as originally written.

---

## 5. `agent-os/registry` — design

Implements doc 12 §6's 8-step pipeline literally (Discover → Fetch →
Integrity verification → Manifest validation → Dependency/capability
resolution → Permission review → Sandbox test run → Register →
`on_load` → Idle). **Filesystem-only discovery in Phase 3** (doc 12 §15's
own table — Git/HTTP/marketplace discovery is Phase 8+). "Sandbox test
run" for an agent reuses Fork E3's lighter OS-level scoping discipline —
no new isolation technology beyond what TDD 3C already established for
capabilities.

**Multi-version coexistence** — mechanism exists from Phase 3 per doc 12
§15's own table (`:421`: *"mechanism exists from Phase 3, exercised as
soon as two versions of one agent actually need to coexist"*) — the
Registry's persistence keys on `(category, version)`, not `category`
alone, from day one, even though Phase 3 ships exactly one version per
agent. New `agent_package` table: `id`, `category`, `version`,
`manifest_json`, `installed_at`, `health_status`.

**RESOLVED (2026-08-19), additive note — item 5, `nova-auth` (a
previously-undisclosed dependency gap, not one of the four named forks
above — see
[`14-3e-agent-os-research.md`](14-3e-agent-os-research.md) §8/§8a).**
`packages/nova-auth` does not exist and is not built by Phase 3E. The
"Permission review" step of the 8-step pipeline above is implemented as a
local diff-and-display: an installing `agent.yaml`'s `required_permissions`
is compared against the previously-installed version's own declared list
(or the empty list, for a first install) and anything new/elevated is
surfaced to the user — no `nova-auth.authorize()` call. This is the same
declared-intent-only precedent already established, independently, by
`capability-engine`'s TDD 3C §10 and `action-engine`'s TDD 3D §7/§11 for
the identical `nova-auth`-does-not-exist-yet situation. Kernel-side
`execute()`-time permission re-validation (doc 12 §7) is correspondingly
**not implemented** in Phase 3 — an explicitly disclosed, deferred gap,
not a silently skipped check.

---

## 6. `agent-os/sdk/python` — filling the `AgentResult`/`AgentMessage` gap

Confirmed this pass: doc 12 references `AgentResult` and `AgentMessage`
throughout (§4, §8, §10) but **never gives either a field-level
definition anywhere** — the only fully-specified type in that family is
`AgentMessageType` (the enum). This TDD must define both; proposed
shapes, grounded directly in what doc 12's own prose says each type must
carry:

```python
class AgentResult(BaseModel):
    """§5, §9 -- what a Supervisor collects for the primary result AND
    for every peer-review round (`PEER_REVIEW_RESULT`, §10)."""
    agent_instance_id: UUID
    task_node_id: UUID
    status: Literal["success", "failure", "needs_revision"]
    output: dict
    confidence: float | None = None
    self_validation_passed: bool
    correlation_id: UUID

class AgentMessage(BaseModel):
    """§10 -- the Agent Mailbox envelope."""
    message_type: AgentMessageType   # already fully specified, doc12 §10
    from_instance_id: UUID | None    # None for Kernel/Supervisor-originated
    to_instance_id: UUID
    payload: dict
    correlation_id: UUID
```

**Flagged for approval** — both are proposed, not extracted; this is the
same disclosure discipline already applied to `Estimate`/`RiskLevel`
(`3B`), `CapabilityHandle` (`3C`), `RetryPolicy`/`RollbackStrategy`
(`3D`).

**RESOLVED (2026-08-19), additive note — Fork 3E-1.** Approved: both
shapes adopted as proposed above, with the placement split confirmed by
independent re-verification —
[`14-3e-agent-os-research.md`](14-3e-agent-os-research.md) §3 confirms
`AgentResult` belongs in `nova_contracts.entities` (never independently
published) and `AgentMessage` belongs in `nova_contracts.events.agent_os`
(`schema_version: int = 1`, `@register_payload`), per this project's own
Extraction-E placement rule. This note does not alter the proposal text
above, which is preserved as originally written.

**`AgentHandler` Protocol, `AgentContext`, `AgentHealth`, `AgentMetrics`**
— used verbatim from doc 12 §4 (`12-agent-architecture.md:108-149`), no
proposed changes; already fully specified there.

**Placement in `nova-contracts`.** Per the extraction-E rule (never
independently published on the Event Bus → `entities.py`; the
`inprocess` backend passes `AgentContext` as a live Python object, never
serialized, confirmed in `01-tdd-preparation-and-fork-resolutions.md`
§5.5's Fact 4): `AgentContext`, `AgentHealth`, `AgentMetrics`,
`AgentResult` (when passed in-process) live in `nova_contracts.entities`.
**`AgentMessage` is the one exception** — Agent Mailbox messages route
over `agent_os.instance.<instance_id>.inbox`, a real Event Bus subject
(doc 12 §10), so `AgentMessage` belongs in
`nova_contracts.events.agent_os`, not `entities.py`. A published,
aggregate `agent_os.health.snapshot` payload (doc 12 §13) also lives in
`events/agent_os.py`, distinct from the in-process-only `AgentHealth`
per-instance type.

---

## 7. `agent-os/supervisors` — the `engineering` Supervisor

Implements doc 12 §9 literally — this project's own research (this
pass) already extracted the exact mechanics, quoted here as the binding
spec, not re-derived:

- **Restart strategies:** `one_for_one` (default — restart only the
  failed instance), `one_for_all` (siblings sharing state), `rest_for_one`
  (pipeline-shaped groups) — `engineering` Supervisor uses `one_for_one`
  by default for its four agent categories (`coding-agent`, `qa-agent`,
  `architect-agent`, `documentation-agent`; `research-agent` is
  independently supervised for the initial single-agent bring-up, §9).
- **Peer review:** the Supervisor sends `PEER_REVIEW_REQUEST` (Agent
  Mailbox) to a reviewer instance, collects its `AgentResult` (§6) before
  accepting the primary result — implemented once at the Supervisor
  level, per doc 12's own "every domain supervisor gets peer review for
  free" design.
- **Conflict resolution:** exactly two levels — escalates first to the
  owning Supervisor (which can often resolve it directly using domain
  context); only escalates further to `reasoning-engine` (an evidence-
  weighted decision, existing RPC) when the Supervisor itself cannot
  resolve it. Recorded to Decision Memory either way.

**Phase 3 ships exactly one Supervisor** (`engineering`) — proving the
pattern, per doc 12 §15's own table, before Research/Operations
Supervisors are added in later phases (not built by this TDD).

---

## 8. `GoalsPort` migration — both engines, now that `planning-engine` exists

**Existing placeholder** (confirmed identical Protocol signature in both
engines, `Goal` type already diverged by `goal_tier`): `current_goals(self, *, user_id, scope=None, correlation_id=None) -> list[Goal]`.

**Migration design.** `planning-engine` (`3B`) did not originally define
a "current goals" RPC — Task Graphs, not a `Goal` list, are its native
data shape. This TDD adds one small, additive extension to
`planning-engine`'s own contract surface (disclosed here, not silently
assumed into `3B`'s already-written document, mirroring the Fork
D/`proactive_delivery_record` precedent for a genuinely-discovered-during-
implementation necessity):

- New `planning.goals.current.request`/`.reply` RPC, served by
  `planning-engine`, mapping each of a user's active `TaskGraph`s to one
  `Goal`: `Goal(id=task_graph.id, description=task_graph.root_objective,
  priority=<derived from critical-path position>, goal_tier=<"established"
  if the graph came from a multi-node decomposition, else "ad_hoc">)`.
  **The `goal_tier` derivation heuristic is proposed, not extracted —
  flagged for explicit approval**, since no document specifies how a
  Task Graph's shape should map to ADR-029's ad_hoc/established
  distinction.
- Both `reasoning-engine`'s and `executive-cognition-engine`'s
  `clients/goals_client.py` are swapped from caller-supplied-passthrough
  to a real RPC call against this new subject — the `GoalsPort` Protocol
  itself, and every caller of `current_goals()`, is **unchanged** (the
  "swap the placeholder implementation for a real RPC-backed one without
  changing the Protocol's own shape or any caller" precedent, already
  established for `PersonalContextPort` in Phase 2D-D).

**RESOLVED (2026-08-19), additive note — Fork 3E-3 and item 6
(`priority` formula).** Approved: `goal_tier = "established"` iff
`len(task_graph.nodes) > 1`, else `"ad_hoc"`, derived at read time inside
`planning-engine`'s new RPC handler, never persisted — confirmed by
independent re-verification against ADR-029's tie-break-only scope in
[`14-3e-agent-os-research.md`](14-3e-agent-os-research.md) §5. `priority`
is set to `1.0 - (rank_index / max(1, len(active_task_graphs) - 1))`,
ranking a user's active `TaskGraph`s descending by critical-path effort
sum (tie-broken by `TaskGraph.id`) — full derivation and rationale in
that document's §8b. Both derivations are additive to `05-tdd-3b-planning-engine.md`,
which carries its own corresponding note. This note does not alter the
proposal text above, which is preserved as originally written.

---

## 9. The five agents — deliberately minimal Phase 3 scope

Per doc 12 §15's own discipline ("prove the pattern before adding more")
and the roadmap's own scripted acceptance test (§13), each agent's
Phase 3 `AgentHandler.execute()` is scoped tightly to what that one
scripted objective needs — not general-purpose agent intelligence:

| Agent | Phase 3 `execute()` behavior |
|---|---|
| `research-agent` | Given `AgentContext.task.objective`, consults `relevant_memory`/`relevant_knowledge` (already pre-scoped, per doc 12 §4) and calls `ai-model-orchestration-engine` (existing) to produce a structured finding. **Brought up and validated first, alone**, per roadmap step 4 — the "single trivial agent" proving the full Kernel→Supervisor→instance loop before the other four are added. |
| `coding-agent` | Invokes `action-engine` (via `action.execute`, `3D`) using granted `filesystem`/`terminal`/`git` capabilities to make a scripted code change. |
| `qa-agent` | Invokes `action-engine`'s `terminal` capability to run a test suite; `AgentResult.status` reflects pass/fail directly, not interpreted. |
| `architect-agent` | The scripted peer-review reviewer — consumes `coding-agent`'s `AgentResult` via `PEER_REVIEW_REQUEST`, produces a structured review verdict. |
| `documentation-agent` | Calls `ai-model-orchestration-engine` to produce documentation content, writes it via `action-engine`'s `filesystem` capability. |

No agent in Phase 3 does open-ended, unscoped work — each is validated
against the one scripted end-to-end objective (§13), consistent with
"ship a real but intentionally minimal instance of the full
architecture" (roadmap's own Phase 3 framing, `:506`).

**Implementation note added 2026-08-29 (Phase 3E Slice 4, decision D5).**
The `coding-agent` row above is unchanged and was not reopened; this records
what "a scripted code change" was implemented as. §13's own acceptance
objective ends in "a real git commit in a throwaway repo", which a
filesystem write alone cannot satisfy — the working tree would be dirty and
nothing committed. `coding-agent` therefore issues **three** `action.execute`
requests per task, in order: the filesystem `write`, then `git add` of
exactly that path, then `git commit -m "coding-agent: <objective>"`.

Two consequences worth recording, neither of them a contract change:

- **git is reached as `action_type="terminal"` plus
  `execution_target="git"`**, per `ActionType`'s own docstring rule that git
  is an adapter over Terminal/Filesystem Actions and never a third type
  value. No `repo_root` is sent, so `GitAdapter` scopes to its capability's
  declared root — decision D7's target repository.
- **The agent checks `exit_code` itself.** TDD 3C §8 makes a non-zero git
  exit a *structured* failure, so `action-engine` reports
  `status="completed"` and only `result["exit_code"]` distinguishes a real
  commit from a refused one. Without that check a failed commit would reach
  the Supervisor — and §13's acceptance criterion — as a successful code
  change. This mirrors `qa-agent`'s already-shipped `pytest` convention.

Verified against real git: `git add`/`git commit` need no `HOME` in the
subprocess environment, so Slice 3's single-`PATH` environment is unchanged
and no new setting was introduced. The target repository must carry a
**local** `user.name`/`user.email`, which D5 assigns to the fixture.

---

## 10. Event contracts — full list for this TDD

**Subscribed:** `planning.task_graph.created` (Kernel Scheduler trigger,
§4); `agent_os.instance.<instance_id>.inbox` (Agent Mailbox, per-instance).

**Published:** `agent.<instance_id>.<state>` (lifecycle transitions, doc
12 §5); `agent_os.health.snapshot` (aggregated health, doc 12 §13);
`agent_os.task.completed` (doc 10 row 15 — consumed by `planning-engine`,
already anticipated in `3B` §6.1); `planning.decompose.request` (Kernel/
Supervisor-initiated, served by `planning-engine`, already defined in
`3B` — this TDD is the RPC's first real caller).

**Implementation status of this section, disclosed 2026-08-29 (Phase 3E
Gate Review).** Verified subject by subject against
`agent-os/*/src/*/events/{published,subscribed}.py`,
`packages/nova-contracts/src/nova_contracts/events/agent_os.py`, and the
generated TypeScript. Three of the six subjects above are **not
implemented**, and until this note none of the three was disclosed
anywhere:

| Subject | §10 role | Status in the shipped code |
|---|---|---|
| `planning.task_graph.created` | Subscribed | **Implemented** — `agent-os/kernel/main.py:112`, the Scheduler's trigger. |
| `agent_os.instance.<instance_id>.inbox` | Subscribed | **Partially implemented, already disclosed.** `AgentMessage` is a registered payload and `agent-os/supervisors/events/published.py` declares the glob `agent_os.instance.*.inbox`, but that file's own docstring records it "has no live receiver yet". The Phase 3 peer-review round delivers its `AgentMessage` **in-process**, through `InprocessExecutionBackend.spawn_and_review()` calling the reviewer Handler's `on_message()` directly — correct for the only enabled backend, since §6/`01-tdd-preparation-and-fork-resolutions.md` §5.5 Fact 4 already establish that `inprocess` passes these objects live rather than serialized. |
| `agent_os.task.completed` | Published | **Implemented** — `agent-os/kernel/events/published.py`, consumed by `planning-engine`. |
| `agent.<instance_id>.<state>` (lifecycle transitions, doc 12 §5) | Published | **NOT IMPLEMENTED.** No payload exists in `nova-contracts`, no subject appears in any `PUBLISHABLE_SUBJECTS` set, and nothing publishes it. Instance lifecycle state is persisted to `agent_os.agent_instance.status` and is otherwise unobservable from outside the Kernel. |
| `agent_os.health.snapshot` (aggregated health, doc 12 §13) | Published | **NOT IMPLEMENTED.** No payload exists in `nova-contracts` — §6 above states this payload "also lives in `events/agent_os.py`"; it does not. Nothing aggregates or publishes health. Per-package `health_status` is written by the Registry install pipeline and per-instance `health_status` by the Kernel, but neither is ever published. |
| `planning.decompose.request` | Published (RPC, "this TDD is the RPC's first real caller") | **NOT CALLED.** The RPC is served by `planning-engine` and is exercised by that engine's own tests, but no `agent-os` component ever calls it. §12's "`planning.decompose.request` for an already-minimal node" row therefore describes a path that does not execute in the shipped system. |

None of these three gaps affects a §14 acceptance criterion, and none was
introduced by a later slice reversing an earlier one — they were never
built.

**RATIFIED (2026-08-29) — explicit Phase 3E narrowings, by the user's
decision in the Gate Review closure pass.** DEV-2
(`agent.<instance_id>.<state>`), DEV-3 (`agent_os.health.snapshot`) and
DEV-4 (`planning.decompose.request` never called) are **approved as
Phase 3E narrowings**. The existing implementation is preserved; the
deferred functionality is **not** built by Phase 3E. The three subjects
remain specified by this section and by doc 12 §5/§13 as the target
architecture — the narrowing is to Phase 3's scope, not to the design.

Consequences recorded so nothing is lost:

- **DEV-2 and DEV-3 are re-scoped to the phase that builds the Agent
  Activity panel.** That panel
  ([`03-gateway-web-prerequisite.md`](03-gateway-web-prerequisite.md) §5)
  is the only named consumer of either subject anywhere in the
  documentation. Publishing lifecycle events and health snapshots with no
  subscriber would be exactly the build-ahead-of-its-phase discipline §2
  of this document already refuses for
  `agent-os/execution-backends/`. Neither payload exists in
  `nova-contracts`; adding them is that phase's work, not a debt against
  this one.
- **DEV-4 costs nothing to ratify.** `planning.decompose.request` is
  served, contract-tested and exercised by `planning-engine`'s own tests
  today. Only the `agent-os`-side *caller* is absent. §12's
  "already-minimal node" row therefore describes a path that does not
  execute in Phase 3, and is now read as forward-looking rather than as a
  description of shipped behaviour.
- **No acceptance criterion in §14 depends on any of the three**, which is
  why ratification does not weaken the gate.

**Two further narrowings, ratified in the same pass**, both already
disclosed in source but absent from the original deviation register:

- **`AgentMessage` mailbox transport.** `agent_os.instance.<id>.inbox` has
  no subscriber in any component — verified against the real allow-lists,
  `agent-os/kernel`'s `{"planning.task_graph.created"}` and
  `agent-os/supervisors`' `{"agent_os.supervisor.restart_plan.request",
  "agent_os.supervisor.peer_review.request"}`. Phase 3's peer-review round
  delivers its `AgentMessage` **in-process** via
  `InprocessExecutionBackend.spawn_and_review()`, which is correct for the
  only enabled backend per §6 and
  [`01-tdd-preparation-and-fork-resolutions.md`](01-tdd-preparation-and-fork-resolutions.md)
  §5.5 Fact 4. Ratified as-is.
- **`DecisionMemoryPort` is a structured-log stub, not a cross-engine
  call.** Doc 12 §9's "Recorded to Decision Memory either way" is honoured
  at the Supervisor's own boundary — every conflict resolution really
  calls the port — but its default implementation
  (`agent-os/supervisors/clients/decision_memory_client.py`) writes a
  structured log line. `memory-engine` exposes **no inbound
  decision-record RPC or subscription** for another engine to call
  (verified this pass: it *publishes* `memory.decision.recorded` but
  subscribes to nothing of the kind), and §10 above names no subject for
  it either. Ratified as a Phase 3E narrowing; wiring a real
  `memory-engine` inbound path is that engine's own separate follow-up.

All five narrowings are recorded in
[`phase-3e-agent-os-gate-review.md`](../../roadmap/architecture-reviews/phase-3e-agent-os-gate-review.md)
§2 and §10 (condition C-4, now closed).

**Explicitly not published by any agent or Supervisor directly:**
`communication.intent.*` — per ADR-005/doc 12 §14, an agent's only
output is its `AgentResult`, routed up through its Supervisor → Agent
Kernel → Executive Cognition, which alone decides what (if anything)
reaches the user via `communication-engine`. This TDD does **not** wire
that final Executive-Cognition-to-Communication hop end-to-end — see §14
Non-goals.

---

## 11. Open architectural forks

**Note (2026-08-19), additive — all four forks below are now RESOLVED.**
A dedicated research/decision pass,
[`14-3e-agent-os-research.md`](14-3e-agent-os-research.md), independently
re-verified each proposal below against the current repository (source
code, contracts, persistence patterns, and the cited architecture
documents) and recorded a recommended option for each, plus one additional,
previously-undisclosed dependency gap (`packages/nova-auth` does not
exist — see that document's §8/§8a). **All four forks are APPROVED by the
user (2026-08-19), and items 5 (`nova-auth`) and 6 (`priority` formula)
are RESOLVED (2026-08-19, §8a/§8b).** Approval of these architectural
decisions does not, by itself, authorize starting Phase 3E's own
implementation PR — that remains a separate approval, not yet given. The
fork descriptions immediately below are preserved exactly as originally
written; each now carries its own resolution note (§3, §4, §5, §6, §8
above).

### Fork 3E-1 — `AgentResult`/`AgentMessage` field shapes (§6)

Already presented with a concrete proposal. **RESOLVED (2026-08-19) —
approved as proposed; see §6's resolution note and
`14-3e-agent-os-research.md` §3.**

### Fork 3E-2 — Kernel persistence schema (§4)

Already presented with a concrete proposal. **RESOLVED (2026-08-19) —
approved as proposed; see §4's resolution note and
`14-3e-agent-os-research.md` §4.**

### Fork 3E-3 — `goal_tier` derivation heuristic (§8)

Already presented with a concrete proposal. **RESOLVED (2026-08-19) —
approved as proposed; see §8's resolution note and
`14-3e-agent-os-research.md` §5.**

### Fork 3E-4 — Scaffolding tooling approach (§3)

New script vs. `--target` flag on the existing one — a pure tooling
implementation detail, **recommendation: new script**
(`tools/scaffold-agent-os-component.py`), since the generated skeleton
differs enough (no FastAPI events/repository template) that branching
inside the existing script would add more conditional complexity than a
small, separate script. **RESOLVED (2026-08-19) — approved: two new,
separate scripts; see §3's resolution note and
`14-3e-agent-os-research.md` §6.**

### Item 5 (not a named fork) — `nova-auth` (§8, §5 above)

Whether `agent.yaml` permissions are declared-intent-only or enforced via
a new `packages/nova-auth`. **RESOLVED (2026-08-19) — Option (a),
declared-intent-only; no `packages/nova-auth` is built. See §5's
resolution note and `14-3e-agent-os-research.md` §8a for full rationale,
including the two independent precedents (TDD 3C §10, TDD 3D §7/§11)
that decided it.**

### Item 6 — `priority`'s critical-path-position formula (§8 above)

**RESOLVED (2026-08-19) —**
`priority = 1.0 - (rank_index / max(1, len(active_task_graphs) - 1))`,
ranking a user's active `TaskGraph`s by critical-path effort sum,
tie-broken by `TaskGraph.id`. See §8's resolution note and
`14-3e-agent-os-research.md` §8b for full derivation.

---

## 12. Failure and degraded behavior

| Condition | Behavior |
|---|---|
| Agent instance crashes mid-task | Owning Supervisor applies its configured restart strategy (`one_for_one` default) — the crashed instance's `TaskNode` reverts to `"ready"` for redispatch, never left `"running"` forever. |
| Kernel process itself restarts | §4's `agent_instance` reconciliation — every `"running"` row is re-queued. |
| Peer review reviewer instance times out | Supervisor proceeds with the primary result flagged `self_validation_passed=True, peer_validation="timed_out"` (not silently treated as an approving review) — exact timeout policy is a configuration value, not hardcoded. |
| Conflict the Supervisor cannot resolve | Escalates to `reasoning-engine` (existing RPC) exactly once — no further escalation path exists in Phase 3 (Executive Cognition arbitration beyond this is not built here). |
| `planning.decompose.request` for an already-minimal node | `planning-engine`'s existing `3B`-defined behavior (§6.1 there) — Kernel/Supervisor treats the reply as "cannot decompose further," assigns the node as-is. |

---

## 13. Testing strategy

**Unit (fake-backed):** Kernel Scheduler scoring logic; restart-strategy
unit tests (force a crash, assert `one_for_one`/`one_for_all`/
`rest_for_one` behavior per doc 12 §9); Agent SDK contract tests — every
one of the five agents' manifest and handler validated against
`AgentHandler` before registration (`ENGINEERING_ROADMAP.md:537`, direct
requirement).

**Contract:** `AgentResult`/`AgentMessage`/`agent_os.health.snapshot`
payload round-trips.

**Integration:** Registry's 8-step install pipeline for each of the five
Agent Packages; Kernel↔Supervisor↔instance dispatch loop for
`research-agent` alone first (roadmap step 4), then the remaining four.

**Real-infrastructure — the roadmap's own named acceptance test**
(`ENGINEERING_ROADMAP.md:538`, quoted verbatim as the binding spec, not
re-derived): *"a real, scripted end-to-end objective ('add a health-check
endpoint to a sample repo') flows through Reasoning → Planning → NAOS
(Kernel → Engineering Supervisor → agent instances, including a peer-
review round) → Action Engine → a real git commit in a throwaway repo."*
This is the single largest real-infra test in the Phase 3 package,
exercising `3A`(reasoning)/`3B`/`3C`/`3D`/`3E` together for the first
time. Also: real-Postgres restart-survival test for `agent_instance`
(§4, §12).

---

## 14. Acceptance criteria

Reproduced from `ENGINEERING_ROADMAP.md:542-546`, the binding spec:

1. A non-trivial multi-step coding objective produces a correct Task
   Graph, executes via at least two agent instances working in parallel
   where dependencies allow, includes at least one real peer-review round
   (`architect-agent` reviewing `coding-agent`'s output), and produces a
   verifiable result (a passing test suite in the target repo).
2. Killing `agent-os-kernel` mid-execution and restarting resumes
   in-flight Task Graph work rather than restarting it from scratch.
3. Installing `coding-agent@1.1.0` → `1.2.0` hot-loads without a kernel
   restart and without dropping in-flight instances of the old version.

Plus, specific to this TDD's own additions:

4. `GoalsPort`'s real-RPC migration is provably transparent to both
   calling engines — no change to either engine's own `current_goals()`
   call sites, confirmed by an unmodified-caller regression test.
5. Every one of the five agents' manifest validates against
   `AgentHandler` before the Registry will register it.

**Verification status, 2026-08-29 (Phase 3E Gate Review), additive — 3 of
5 Met, 2 Met with disclosed narrowing.** Full evidence in that document's
§9; summarised here so this section is not read as unverified.

| # | Status | Evidence |
|---|---|---|
| 1 | **Met** | `agent-os/kernel/tests/integration/test_phase_3e_end_to_end_acceptance.py` (7 tests) and its `real_infra` twin `…_real_postgres.py` (1 test). The real-Postgres variant runs six engines' Alembic chains on one PostgreSQL 16.13 database, is driven only by `POST /v1/reasoning/reason`, and asserts a real commit read from git's own history, a `pytest` exit-0 in the target repository, `concurrent_peak == 2`, and one real peer-review round. Passed 10/10 consecutive runs. |
| 2 | **Met with disclosed narrowing** | Proven at unit + integration + real-Postgres level, not by a full-path E2E. Kernel half: `tests/integration/test_restart_reconciliation.py` (a real `create_app()` lifespan restart really publishes `agent_os.task.completed` with `outcome="interrupted"`) + `tests/unit/test_reconciliation.py`. Planning half: `planning-engine`'s `test_events_agent_os_task_completed.py::test_kernel_restart_then_planning_resume_round_trip`. The two halves never import each other's production code (ADR-004) and are joined by an asserted payload shape, not by one executing process. **No test kills a running `agent-os-kernel` OS process mid-execution**; "restart" is a fresh `create_app()` entering its lifespan. |
| 3 | **Met with disclosed narrowing** | `tests/integration/test_hot_load_version_pinning.py` + `agent-os/registry` `tests/unit/test_selection.py` and `tests/integration/test_repository_real_postgres.py` (13 real-Postgres tests incl. two-version coexistence and healthy-fallback). Narrowing recorded in [`16-3e-hot-load-design-decision.md`](16-3e-hot-load-design-decision.md) §2 and approved 2026-08-28: this is **version pinning and scheduling hot-load, not simultaneous execution of two bytecode versions** — `InprocessExecutionBackend` resolves handler code by manifest `id` alone and no per-version directory exists. Also note the criterion names `coding-agent@1.1.0 → 1.2.0`; the shipped package is `0.1.0`, and the test uses synthetic `1.1.0`/`1.2.0` `agent_package` rows. |
| 4 | **Met** | Both `GoalsPort` Protocols and every `current_goals()` call site are byte-identical to their pre-migration form (`reasoning-engine/domain/ports.py:113`, `domain/context_assembly.py:68`; `executive-cognition-engine/domain/ports.py:91`, `domain/coordinate.py:117`); only the two `clients/goals_client.py` adapters changed. `reasoning-engine/tests/contract/test_port_compliance.py` is the unmodified-caller regression test. Disclosed limitation, recorded at `planning-engine/domain/ports.py::PlanningRepository.list_all`: `task_graph` carries no ownership column, so the reply is not filtered by `user_id`. |
| 5 | **Met** | `agent-os/registry/domain/pipeline.py:311` — `issubclass(handler_class, AgentHandler)` gates Register; failure raises before the row is written. Exercised against all five real on-disk packages by `tests/integration/test_real_*_agent_installs.py`. |

---

## 15. Non-goals / explicitly deferred

- Research/Operations Supervisors (later phases; only `engineering` ships
  now, per doc 12 §15).
- `subprocess`/`container`/`remote` execution backends (Phase 4+/7+/8).
- The full Executive-Cognition-to-`communication.intent.ready` hop for
  agent/Task-Graph progress reaching the user (doc 10 row 14) — this TDD
  wires agents up to `agent_os.task.completed` and `AgentResult`
  reporting, not the final "does the user see this in conversation"
  integration, which is `communication-engine`'s and Executive
  Cognition's own future decision, mirroring `3B`'s identical deferral
  for `planning.task_graph.created`.
- Any agent category beyond the five named (Bible Part 04's remaining
  ~19 categories are additive packages, per doc 12 §15's own table).
- Git/HTTP/marketplace Agent Registry discovery (Phase 8+).

**Added 2026-08-29 (Phase 3E Gate Review closure pass) — `agent-os`
deployment, explicitly deferred, by the user's decision.**

**No Dockerfile, no `build-and-scan.yml` matrix entry, no
`docker-compose.local.yml` service, and no deployment architecture is
introduced for any `agent-os` component by Phase 3E.** The four components
(`kernel`, `registry`, `supervisors`, `sdk/python`) remain buildable and
testable as workspace packages but are not containerised, not image-scanned
by Trivy, and not runnable via the local compose stack. This is a
**deferred obligation for a future phase**, recorded here rather than
closed.

**Why it is not required by Phase 3E's acceptance criteria.** Checked
criterion by criterion against §14, not asserted:

| Criterion | Does it need a deployed `agent-os` container? |
|---|---|
| 1 — multi-step objective, ≥2 parallel agents, peer review, passing target-repo suite | **No.** Proven by `agent-os/kernel/tests/integration/test_phase_3e_end_to_end_acceptance.py` and its `real_infra` twin, which stand every component up through its own real `create_app()` in-process. The `inprocess` execution backend — the only backend §2 enables — runs agent instances inside the Kernel process by definition, so a container boundary would add nothing the criterion asks about. |
| 2 — kill and restart resumes in-flight work | **No.** The restart under test is a `create_app()` lifespan restart, exercising `reconcile_running_instances` and the real `agent_os.task.completed` publish. Container orchestration is a different concern from the reconciliation logic the criterion names. |
| 3 — hot-load without kernel restart | **No.** The criterion turns on which `agent_package` row a new dispatch pins to, proven against the real selection policy, the real served RPC and real Postgres. Nothing about it is containerisation-dependent. |
| 4 — `GoalsPort` migration transparent | **No.** A Protocol-and-caller invariant, verified by source inspection and a regression test. |
| 5 — every manifest validates against `AgentHandler` before registration | **No.** Enforced inside the Registry's own install pipeline. |

**Neither TDD 3E nor doc 12 mentions Dockerfiles for `agent-os` anywhere**
— §0's scope list, §4's Kernel design and §5's Registry design are all
silent on packaging and deployment. The assumption that everything
deployable lives under `services/` is `build-and-scan.yml`'s own matrix
comment ("One entry per `services/<name>/Dockerfile`"), which predates
`agent-os/` existing; correcting that assumption is part of the deferred
work, not of Phase 3E.

**What the deferring phase inherits**, so this is a real obligation and not
a shrug: four Dockerfiles (or a reasoned decision that `sdk/python` is
library-shaped and needs none), four `build-and-scan.yml` matrix entries
plus a matrix comment that no longer says `services/*` only, four
`docker-compose.local.yml` services, the first Trivy results for any
`agent-os` image, and updates to
[`14-deployment-architecture.md`](../../architecture/14-deployment-architecture.md)
and `infra/docker/README.md`. Tracked as Gate Review condition **C-3**.
