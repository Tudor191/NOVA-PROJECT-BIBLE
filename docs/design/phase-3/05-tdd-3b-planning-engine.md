# TDD 3B — `planning-engine`

**Status: partially implemented.** Domain foundation (§2: `TaskNode`/
`TaskGraph`/`Estimate`/`RiskLevel`, graph invariants, critical-path
computation) shipped in PR #2. Objective Decomposition (§6.1's
`reasoning.process.completed` -> `TaskGraph` path, via the
`ModelOrchestrationPort` added to §3) shipped in the decomposition-
orchestration unit that follows PR #2. Persistence (§4), the API surface
(§5), and `planning.task_graph.created`/`planning.decompose.request`
(§6.2) shipped in the `phase-3b-planning-persistence` precursor PR that
follows the decomposition-orchestration unit -- see that PR's own Gate
Review for exact scope, tests, and CI evidence. Only the
`agent_os.task.completed` subscription (§6.1) remains unbuilt, correctly
deferred: its only real caller (`agent-os/kernel`) does not exist until
Phase 3E's own implementation PR.

---

## 0. Scope and dependencies

**Scope.** Stand up `planning-engine`: objective decomposition, Work
Breakdown Structure, the `TaskNode`/`TaskGraph` data model (doc 06 §3),
dependency/critical-path analysis, and Postgres-backed persistence
supporting Dynamic Replanning by mutation — per
`ENGINEERING_ROADMAP.md:509`, doc 06 §3, and Bible Part 9.

**Dependencies.** `reasoning-engine` (existing, Phase 2B —
`reasoning.process.completed` is the input `planning-engine` consumes;
corrected from this TDD's original, nonexistent `reasoning.result`
reference — see `docs/design/phase-3/09-3b-preimplementation-verification.md`
§1 and `10-3b-4-resolution-and-preimplementation-verification.md` for the
full investigation) and
`communication-engine` (existing, Phase 2D-A — consumes
`planning.task_graph.created` if it chooses to notify the user; see §6).
**Does not depend on `capability-engine`, `action-engine`, or `agent-os`
existing** — per roadmap's own implementation-order step 1: *"`planning-engine`
Task Graph model + decomposition (no agents yet — output inspected
manually)."*

---

## 1. Existing capability vs. what's being built

**Existing:** `reasoning-engine` already publishes `reasoning.process.completed`
(`nova_contracts.events.reasoning.ReasoningProcessCompletedPayload`, Phase 2B,
additively enriched with `objective_text`/`chosen_description` for this TDD's
own purposes per Fork 3B-4's resolution); `communication-engine`
already owns the only legal `communication.intent.*` gate (ADR-005). No
part of `planning-engine` itself exists — confirmed by directory listing
(`services/` contains no `planning-engine`) and by `nova-contracts`
having no `Planning*`/`TaskGraph*`/`TaskNode*` type anywhere (confirmed
by repo-wide grep, zero hits beyond the doc06 §3 code block and one
prose reference in the Phase 3 research doc).

**Being built, entirely new:** the full engine — domain layer, Postgres
repository, API, event contracts, worker.

---

## 2. Domain model

### 2.1 `TaskNode`/`TaskGraph` — doc 06 §3, verbatim, the schema source of truth

```python
class TaskNode(BaseModel):
    id: UUID
    objective: str
    depends_on: list[UUID]
    assigned_agent_category: str | None   # e.g. "coding-agent"
    estimated_effort: Estimate
    risk: RiskLevel
    status: Literal["pending","ready","running","blocked","completed","failed"]

class TaskGraph(BaseModel):
    id: UUID
    root_objective: str
    nodes: list[TaskNode]
    critical_path: list[UUID]
```

**Two referenced types, `Estimate` and `RiskLevel`, are named in doc 06
§3's own code block but never defined anywhere in the documentation** —
confirmed by repo-wide grep, zero hits for either as a class definition.
This is a genuine, disclosed gap this TDD must fill, not silently invent
past:

- **`RiskLevel`** — proposed: reuse the one canonical risk-tier scale
  documented anywhere in this project, Bible Part 14's *"Negligible. Low.
  Moderate. High. Critical."* (`part-14-autonomy-engine.md:267-281`),
  rather than inventing a second, parallel scale. This is the same scale
  `action-engine` (TDD 3D) will use for its own risk classification —
  reuse here keeps a `TaskNode.risk` value directly comparable to an
  `action-engine` risk classification once agents dispatch actions
  against a node.
- **`Estimate`** — no canonical definition exists anywhere. Proposed
  minimal shape, grounded in Bible Part 9's WBS field list (*"Estimated
  effort"* is one of seven named WBS fields, `part-09-planning-engine.md:159-179`,
  with no further schema given):
  ```python
  class Estimate(BaseModel):
      effort_hours: float
      confidence: float = Field(ge=0.0, le=1.0)
  ```
  **Flagged explicitly: this is proposed, not extracted from any
  document, and requires explicit approval before implementation** — the
  two fields are the minimum needed to support Critical Path Analysis
  (which needs a duration figure) while acknowledging effort estimates
  are inherently uncertain (Bible's own "No task should remain too large
  for accurate estimation" framing, `part-09-planning-engine.md:107-156`,
  implies estimation confidence matters).

### 2.2 Objective Decomposition hierarchy — Bible Part 9, informational only

`part-09-planning-engine.md:107-156`: *"Objective ↓ Mission ↓ Project ↓
Milestone ↓ Epic ↓ Feature ↓ Task ↓ Subtask ↓ Action ↓ Execution Step ↓
Verification ↓ Completion."* **No field definitions exist per level in
the Bible.** `TaskNode` (doc 06 §3) is the one concrete, already-specified
data structure — it does not itself carry a "hierarchy level" field.
**Design decision, not a fork:** `planning-engine`'s Phase 3 implementation
represents the decomposition as a flat `TaskGraph` of `TaskNode`s linked
by `depends_on`, without a separate explicit hierarchy-level enum —
consistent with doc 06 §3 being the schema source of truth and the
twelve-level Bible list having no accompanying schema to implement
literally. A `TaskNode.objective` free-text field carries whatever
granularity a given node represents (Mission-level, Task-level, etc.),
mirroring how `ReasoningRequest.objective_text` already works elsewhere
in this codebase.

### 2.3 Work Breakdown Structure fields — mapped to `TaskNode`, gaps disclosed

Bible's seven named WBS fields (`part-09-planning-engine.md:159-179`) map
onto `TaskNode` as follows — four map directly, three do not exist on the
doc-06 schema and are **not added** without approval (adding them would
be scope expansion beyond doc 06 §3's already-specified fields):

| WBS field | `TaskNode` mapping |
|---|---|
| Estimated effort | `estimated_effort: Estimate` |
| Dependencies | `depends_on: list[UUID]` |
| Responsible agents | `assigned_agent_category: str \| None` |
| Completion criteria | *(no field — not on doc 06 §3's schema)* |
| Deliverables | *(no field — not on doc 06 §3's schema)* |
| Required knowledge | *(no field — not on doc 06 §3's schema)* |
| Required tools | *(no field — not on doc 06 §3's schema)* |

**Not silently resolved:** whether these three gaps should be added as
new, additive `TaskNode` fields is left as an open question for the user,
not decided here — doc 06 §3 is the schema source of truth and was
written after Bible Part 9, deliberately narrower; adding fields back in
without an explicit instruction would be exactly the kind of
undocumented invention this TDD is required to avoid.

---

## 3. Ports (upstream dependencies `planning-engine` defines for itself)

Following the established per-calling-engine Port convention (confirmed
precedent: `GoalsPort`/`DigitalTwinPort`, each defined locally in the
calling engine's own `domain/ports.py`, never centralized):

- **`MemoryPort`** — consults Memory Engine's existing
  `memory.retrieve.request`/`.reply` RPC (already defined in
  `nova-contracts`) during decomposition, per doc 10's dotted
  "Memory -.consulted by.-> Planning" edge.
- **`KnowledgePort`** — same pattern, `knowledge.retrieve.request`/`.reply`,
  per doc 10's "Knowledge -.consulted by.-> Planning" edge.
- **`ModelOrchestrationPort`** (added post-approval, per
  `docs/design/phase-3/11-3b-decomposition-architecture-research.md` §6/§13
  and the decomposition-orchestration Gate Review) — ADR-020's sole legal
  channel to any model, a thin Protocol wrapping `ai_model.generate.request`.
  Used only by `domain/decomposition.py` (Objective Decomposition, §6.1) to
  turn `objective_text`/`chosen_description` into a structured `TaskGraph`
  proposal via the tool-calling mechanism `nova_contracts.events.
  ai_model_orchestration` already defines — the identical pattern
  `reasoning-engine`'s own `ModelOrchestrationPort`/`ModelOrchestrationClient`
  already establishes for Hypothesis Generation. Not a new architectural
  fork: this TDD's original text left the decomposition mechanism
  unspecified (Fork 3B-4-adjacent); the research pass resolved it as
  LLM-backed decomposition through this already-approved channel, not an
  invented heuristic or placeholder.

**No `GoalsPort` consumer role** — `planning-engine` is the future real
backing for `GoalsPort` (ADR-026), not a caller of it.
**No `CommunicationPort`** — see §6; `planning-engine` never touches
`communication.intent.*`.

---

## 4. Persistence

New `planning` Postgres schema, hand-written `0001_initial_schema.py`
migration mirroring the established per-engine convention:

- **`task_graph`**: `id` (PK), `root_objective`, `critical_path` (JSONB
  array of UUIDs), `approved_at` (nullable, §5), `created_at`, `updated_at`.
- **`task_node`**: `id` (PK), `task_graph_id` (FK), `objective`,
  `depends_on` (JSONB array of UUIDs — consistent with the existing
  precedent of storing list-typed domain fields as JSONB, e.g.
  `communication.conversation_session.pending_questions`), `assigned_agent_category`
  (nullable), `estimated_effort` (JSONB, embedding `Estimate`), `risk`,
  `status`, `created_at`, `updated_at`.

**Mutation, not regeneration** (doc 06 §3's explicit requirement): Dynamic
Replanning updates existing `task_node` rows' `status`/`depends_on`/
`estimated_effort` in place and appends new nodes when decomposition
reveals previously-unknown subtasks — it never deletes and recreates the
whole graph. `outbox_event` table follows the standard transactional-
outbox pattern every prior engine uses (`nova-service-kit`'s
`dispatch_ready_events`, reused unmodified per ADR-034).

---

## 5. API surface

Per `docs/architecture/11-api-architecture.md:49-50` (already-documented,
not phase-specific):

```
GET  /v1/plans/{task_graph_id}          # read a Task Graph
POST /v1/plans/{task_graph_id}/approve  # Part 9 "Collaborative Planning"
```

Exposed directly at `planning-engine`'s own FastAPI app (no `api-gateway`
exists yet — see `03-gateway-web-prerequisite.md`; to be fronted by
`api-gateway` once built, additive, not a redesign, per the same stopgap
precedent established for `action-engine`'s approval endpoint, TDD 3D
§2).

**Scoped honestly:** `POST /v1/plans/{id}/approve` records an approval
decision on the `TaskGraph` (`approved_at` timestamp) in Phase 3. Whether
approval *gates* `agent-os/kernel` picking up a graph for dispatch is an
integration question that cannot be fully wired until `agent-os/kernel`
(TDD 3E) exists to consume it — TDD 3E must read and honor
`TaskGraph.approved_at` before dispatching, not invented here as
already-enforced behavior.

---

## 6. Event contracts

### 6.1 Subscribed

- **`reasoning.process.completed`** (existing payload, Phase 2B, additively
  enriched with `objective_text`/`chosen_description` per Fork 3B-4 —
  corrected from this TDD's original, nonexistent `reasoning.result`
  reference) — triggers decomposition: `planning-engine` consumes a
  completed, sufficiently-confident reasoning result (`objective_text`
  seeds `TaskGraph.root_objective`; `chosen_description` shapes the first
  decomposition pass) and produces or mutates a `TaskGraph`. Exact
  confidence threshold for triggering decomposition vs. discarding a
  low-confidence result is a TDD-implementation-time parameter (not an
  architectural fork — mirrors the "implementation-time parameter, not a
  fork" precedent already established for `completed_session_evidence`
  and the proactive-delivery window size in Phase 2D-D).
- **`agent_os.task.completed`** (new subject, owned by `agent-os/kernel`,
  defined in TDD 3E, not yet existing) — `planning-engine` subscribes to
  mutate the corresponding `TaskNode.status`. **This subscription cannot
  be exercised in real conditions until TDD 3E ships** — `planning-engine`
  defines and tests the handler now (fake-bus precedent), consistent
  with the "real code, no real caller yet" idiom already established for
  `GoalsPort`/`DigitalTwinPort`/Fork D.

### 6.2 Published

- **`planning.task_graph.created`** (new, defined here in
  `nova_contracts.events.planning`) — published on graph creation/major
  mutation, per doc 10 row 6. **`planning-engine` never publishes to
  `communication.intent.*`** — row 6's own text attributes the
  notification decision to `communication-engine` ("communication-engine
  **may** notify user of roadmap"), not to `planning-engine`. This keeps
  `planning-engine` fully consistent with ADR-005 without needing its own
  `CommunicationPort` at all — a cleaner boundary than Fork D's
  proactive-delivery precedent required, because here the *consuming*
  engine (communication-engine), not the producing one, owns the
  decision to surface anything to the user. Whether `communication-engine`
  actually subscribes and acts on this event is explicitly **out of TDD
  3B's scope** — `communication-engine`'s own future extension, not
  blocking this TDD's build or verification.
- **`planning.decompose.request`/`.reply`** (new, served by
  `planning-engine`) — per doc 12 §11: *"a Supervisor receiving a Task
  Graph node still too coarse for a single leaf agent can itself request
  further decomposition... scoped to that subtree."* `planning-engine`
  defines and serves this RPC now; its only real caller (an `agent-os`
  Supervisor) does not exist until TDD 3E. Tested via the established
  "second `BoundEventBus` as external caller" pattern (Phase 2D-D
  precedent) rather than left unbuilt.

**Explicitly NOT defined by this TDD:** any `communication.intent.*`
payload, and no scope creep into `communication-engine`'s own decision
logic.

**Note (2026-08-19), additive — new `planning.goals.current.request`/`.reply`
RPC, discovered during Phase 3E's own architecture research pass, not
originally specified by this TDD.** TDD 3E's `GoalsPort` real-RPC
migration (both `reasoning-engine` and `executive-cognition-engine`)
requires `planning-engine` to serve one small, additive RPC mapping each
of a user's active `TaskGraph`s to a `Goal`:
`Goal(id=task_graph.id, description=task_graph.root_objective,
priority=<derived>, goal_tier=<derived>)`. Two new pure derivation
functions back this RPC, both operating on already-persisted `TaskGraph`
state and neither persisting a new field:

- **`goal_tier`** — `"established"` iff `len(task_graph.nodes) > 1`, else
  `"ad_hoc"`, derived at read time, never persisted. Full rationale:
  [`14-3e-agent-os-research.md`](14-3e-agent-os-research.md) §5,
  resolution recorded in `08-tdd-3e-agent-os.md` §8.
- **`priority`** — `1.0 - (rank_index / max(1, len(active_task_graphs) - 1))`,
  ranking a user's currently active `TaskGraph`s descending by
  critical-path effort sum (`sum(node.estimated_effort.effort_hours for
  node in graph.nodes if node.id in graph.critical_path)`), tie-broken by
  `TaskGraph.id`. Full derivation:
  [`14-3e-agent-os-research.md`](14-3e-agent-os-research.md) §8b,
  resolution recorded in `08-tdd-3e-agent-os.md` §8.

This RPC and both derivation functions are **approved and resolved
(2026-08-19)** as architectural decisions, mirroring the "genuinely
discovered during implementation/research necessity, disclosed via an
additive extension" treatment already given to the
`proactive_delivery_record` precedent (Fork D, Phase 2D-D) — this TDD's
own `TaskGraph`/`TaskNode`/`Estimate` models are unchanged; only a new
read-time RPC handler and two pure functions are added. Not yet
implemented — implementation is authorized only once Phase 3E's own
implementation PR is separately approved.

---

## 7. Open architectural forks

**Note (2026-08-20), additive — all three forks below are now resolved;
this section's original proposal text is left unchanged (historical
record of what was proposed), with each fork's resolution and owning PR
noted inline.** A 2026-08-20 documentation-consistency audit of the
`phase-3b-planning-persistence` PR found this section still read as if
all three were open, which could wrongly suggest that PR rests on an
unapproved decision — it does not; PR #18 only reuses the schemas these
three forks already fixed, in the Domain Foundation and Decomposition
Orchestration PRs, both of which shipped before it.

### Fork 3B-1 — `Estimate`/`RiskLevel` field shape (§2.1)

Already presented above with a concrete proposal. **Requires explicit
approval** — genuinely undocumented, not extracted.

**Resolved (Domain Foundation PR, `phase-3b-planning-domain`, PR #2):**
implemented exactly as proposed above. See
`docs/roadmap/architecture-reviews/phase-3b-domain-foundation-gate-review.md`
§2 ("Fork 3B-1 ... implemented as approved").

### Fork 3B-2 — WBS field gaps (§2.3)

Whether `completion_criteria`/`deliverables`/`required_knowledge`/
`required_tools` should be added to `TaskNode` as new, additive fields,
or left absent (matching doc 06 §3's narrower, already-approved schema).
**Recommendation: leave absent for Phase 3**, consistent with the
roadmap's own narrower-than-Bible scoping pattern found throughout this
project (§1.3 of `00-research-and-scope.md`) — but **not silently
decided**; flagged for explicit confirmation.

**Resolved (Domain Foundation PR, `phase-3b-planning-domain`, PR #2):**
the recommendation (leave absent) was adopted, locked in with a
regression test. See the Domain Foundation Gate Review §3 ("Fork 3B-2 ...
implemented as approved").

### Fork 3B-3 — reasoning-result-to-decomposition confidence threshold

Not an architectural fork so much as a named implementation parameter
requiring a concrete default before code can be written. Proposed:
reuse `DEFAULT_VERIFY_THRESHOLD` (0.6, already defined in
`reasoning-engine`'s `pipeline.py:69`) as `planning-engine`'s own default
minimum-confidence-to-decompose threshold, avoiding a second, arbitrary
constant. **Flagged for approval**, not silently assumed.

**Resolved (Decomposition Orchestration PR, `phase-3b-decomposition-orchestration`,
PR #7):** implemented exactly as proposed
(`Settings.decomposition_confidence_threshold: float = 0.6`). See the
decomposition-orchestration Gate Review §6 ("Unconfirmed but precedented
parameter, flagged").

---

## 8. Failure and degraded behavior

| Condition | Behavior |
|---|---|
| `reasoning.process.completed` below the decomposition confidence threshold (Fork 3B-3) | No `TaskGraph` created; no error — mirrors the existing "no action" pattern for below-threshold signals elsewhere in this codebase. |
| `MemoryPort`/`KnowledgePort` timeout during decomposition | Decomposition proceeds with whatever context was retrieved before the timeout — degrades, never blocks indefinitely (same discipline as every existing port timeout handler in this codebase). |
| `ModelOrchestrationPort.generate` times out, returns `finish_reason == "error"`, or returns no/malformed structured `propose_task_graph` tool call, or the resulting nodes fail PR #2's structural checks (duplicate IDs, cycle, dangling dependencies) | No `TaskGraph` produced for this `reasoning.process.completed`; the event is logged and metriced as a failed decomposition attempt (labeled by a stable `reason`) and considered handled — never raised as an unhandled exception, which would trigger NATS JetStream redelivery of an event whose failure is not transient (mirrors `reasoning-engine`'s own `HypothesisGenerationError` handling). |
| `planning.decompose.request` for a subtree that cannot be further decomposed | Replies with the original node unchanged and a structured "already minimal" reason — never a silent no-op reply indistinguishable from success. |
| Postgres unavailable at `task_graph`/`task_node` write time | Standard per-engine failure mode — the request fails loudly (not silently degraded), consistent with every other engine's persistence-layer error handling; Task Graph correctness (never partially/incorrectly persisted) is a hard requirement given restart-survival depends on it (`ENGINEERING_ROADMAP.md:545`). |

---

## 9. Observability

- `planning_task_graph_created_total`, `planning_task_graph_mutated_total`
  (counters).
- `planning_decompose_request_served_total`,
  `planning_decompose_request_already_minimal_total` (counters).
- `planning_critical_path_length` (histogram, per graph).
- Standard `/internal/health`, `/internal/readiness`, `/internal/metrics`
  via `nova-service-kit`'s `make_health_router()` (unmodified reuse, per
  ADR-034).

---

## 10. Security boundaries

No privileged-capability gating occurs in `planning-engine` itself —
ADR-032 does not directly bind this TDD (it binds `action-engine`,
TDD 3D). `POST /v1/plans/{id}/approve` is a human-approval-recording
endpoint, not an execution-authorization one; no identity-confidence
threshold logic is required here. Standard engine-boundary rules apply
(no direct message-broker/graph-DB client imports, per the existing
import-linter contracts extended per §11).

---

## 11. Required workspace/contract changes

- New `services/planning-engine` (via `tools/scaffold-engine.py` —
  `planning-engine` satisfies the existing `-engine` suffix requirement,
  no scaffolding-tool change needed, unlike `agent-os/kernel` in TDD 3E).
- `nova_contracts.events.planning` (new file):
  `TaskNode`, `TaskGraph`, `Estimate`, `RiskLevel` (entities, following
  the extraction-E rule from `01-tdd-preparation-and-fork-resolutions.md`
  §2's Fork-adjacent finding — `TaskGraph` is wire-published via
  `planning.task_graph.created`, so it belongs in `events/`, not
  `entities.py`), `PlanningTaskGraphCreatedPayload`,
  `PlanningDecomposeRequestPayload`/`PlanningDecomposeReplyPayload`.
- Root `pyproject.toml` `root_packages` and the three ADR-004/006/007
  import-linter contracts gain `nova_planning_engine` (automatic via
  `tools/scaffold-engine.py`, per its own documented behavior).
- `infra/docker/docker-compose.local.yml`: new `planning-engine` +
  `planning-engine-worker` service blocks, next available host port.
- `.github/workflows/build-and-scan.yml` matrix: new `planning-engine`
  entry.

---

## 12. Testing strategy

**Unit (fake-backed):** decomposition logic (given a `reasoning.process.completed`,
produces a structurally valid `TaskGraph` — no cycles, `critical_path`
computed correctly for a scripted dependency shape, per
`ENGINEERING_ROADMAP.md:535`'s own structural-verification framing).
Critical-path algorithm unit tests (longest-path-by-effort over a DAG,
standard algorithm, no invention needed beyond implementing it).
Mutation-not-regeneration unit tests (a second decomposition call against
an existing graph updates in place).

**Contract:** `nova_contracts.events.planning` payload round-trip tests,
mirroring every prior phase's contract-test convention.

**Integration (fake ports, real FastAPI app):** `planning.decompose.request`
served correctly via the "second `BoundEventBus` as external caller"
pattern (§6.2). `POST /v1/plans/{id}/approve` round trip.

**Real-infrastructure:** restart-survival test — create a `TaskGraph`,
kill and restart the process (simulated via a fresh repository instance
against the same real Postgres), confirm the graph is read back
unchanged. This directly proves the roadmap's own acceptance criterion
(`ENGINEERING_ROADMAP.md:545`) at the persistence-layer level, ahead of
`agent-os/kernel` existing to prove it at the full-execution level in
TDD 3E.

---

## 13. Acceptance criteria

1. A scripted `reasoning.process.completed` at or above the decomposition-confidence
   threshold (Fork 3B-3) produces a structurally valid `TaskGraph` — no
   cycles, `critical_path` non-empty for any graph with more than one
   node.
2. A second decomposition call against an existing `TaskGraph` mutates
   it in place — confirmed by primary-key stability across the call, not
   a newly-generated graph ID.
3. `planning.decompose.request` served correctly, including the
   "already minimal" non-decomposable case.
4. `TaskGraph`/`TaskNode` state survives a real-Postgres restart
   simulation unchanged.
5. `POST /v1/plans/{id}/approve` round-trips through a real FastAPI app
   and correctly sets `approved_at`.

---

## 14. Non-goals / explicitly deferred

- `agent-os/kernel` actually consuming `planning.task_graph.created` and
  dispatching agent instances — TDD 3E.
- `communication-engine` actually subscribing to `planning.task_graph.created`
  and notifying the user — explicitly out of scope, `communication-engine`'s
  own future decision (§6.2).
- The synchronous "planning request as part of an active conversation
  turn, routed via Executive Cognition to `communication.intent.ready`"
  path named in doc 10 row 14 — not built in Phase 3; only the
  asynchronous `planning.task_graph.created` path (row 6) is in scope.
- Any Bible-Part-9 field not already on doc 06 §3's `TaskNode` schema
  (Fork 3B-2) unless explicitly approved.
- Full Dynamic Replanning triggered automatically by agent
  execution results — depends on `agent_os.task.completed` having a real
  publisher (TDD 3E); this TDD ships the mutation-capable persistence and
  the subscription handler, not the end-to-end automatic trigger.
