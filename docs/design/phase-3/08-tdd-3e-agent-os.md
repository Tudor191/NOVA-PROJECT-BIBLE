# TDD 3E — `agent-os` (Kernel, SDK, Registry, Supervisors), the Five Agents,
## the `engineering` Supervisor, and the `GoalsPort` Migration

**Status: design only, awaiting approval. No production code authorized.**
This is the largest, most integrative TDD in the package — it is the
point at which `3B`/`3C`/`3D`'s independently-buildable engines are
actually exercised together for the first time.

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

**Explicitly not published by any agent or Supervisor directly:**
`communication.intent.*` — per ADR-005/doc 12 §14, an agent's only
output is its `AgentResult`, routed up through its Supervisor → Agent
Kernel → Executive Cognition, which alone decides what (if anything)
reaches the user via `communication-engine`. This TDD does **not** wire
that final Executive-Cognition-to-Communication hop end-to-end — see §14
Non-goals.

---

## 11. Open architectural forks

### Fork 3E-1 — `AgentResult`/`AgentMessage` field shapes (§6)

Already presented with a concrete proposal. **Requires explicit
approval.**

### Fork 3E-2 — Kernel persistence schema (§4)

Already presented with a concrete proposal. **Requires explicit
approval.**

### Fork 3E-3 — `goal_tier` derivation heuristic (§8)

Already presented with a concrete proposal. **Requires explicit
approval.**

### Fork 3E-4 — Scaffolding tooling approach (§3)

New script vs. `--target` flag on the existing one — a pure tooling
implementation detail, **recommendation: new script**
(`tools/scaffold-agent-os-component.py`), since the generated skeleton
differs enough (no FastAPI events/repository template) that branching
inside the existing script would add more conditional complexity than a
small, separate script. **Flagged for approval** since it's a genuine,
if minor, implementation choice.

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
