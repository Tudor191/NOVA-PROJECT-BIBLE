# Phase 3 — Research & Scope Report (pre-TDD)

**Status: research only. No production code was written or modified during
this pass. This document establishes documented scope; it is not itself a
Technical Design Document and does not authorize implementation.**

Produced in response to an explicit request to research Phase 3 across the
Bible, roadmap, ADRs, design docs, and current implementation before any
Phase 3 TDD is drafted, and before any code is written. Three parallel
research passes (Bible/architecture docs; codebase scan; Phase 2D-D
dependencies and security/boundary docs) were run and are consolidated here.
Every finding below is sourced to an exact file and line range.

---

## 0. Phase 2D-D closure status (checked first, per explicit instruction)

**Not yet formally closed.** The `phase-2d-d-gate-review.md` recorded one
open item: the Step 10 timestamp-tie fix (commit `812faf0`) had no
real-infrastructure confirmation, because manual `workflow_dispatch` is
blocked for this session's GitHub integration (`403 Resource not accessible
by integration`).

Checked again at the start of this research pass: the most recent
`real-infra-checks.yml` run on `claude/new-session-e1cseg`
(`31671523896`, `2026-08-13T05:47:18Z`) is still against commit `cd44be0` —
**no run has yet executed against the fix commit (`812faf0`) or the Gate
Review commit (`d57db18`)**. No new run has appeared. A follow-up check is
already scheduled for the next likely nightly firing.

**Conclusion: do not treat Phase 2D-D as closed.** This research pass
proceeds anyway per explicit instruction ("research only, no
implementation"), but no Phase 3 code should be authorized until Phase
2D-D's real-infra confirmation lands and the Gate Review is updated
accordingly.

---

## 1–4. Official scope, Bible sections, roadmap entries, and ADRs

### 1.1 The canonical roadmap definition

`docs/roadmap/ENGINEERING_ROADMAP.md:503-548`, quoted in full:

> "## Phase 3 — Planning & the NOVA Agent Operating System (NAOS)
>
> **Objectives**
> - Implement `planning-engine`, the **NOVA Agent Operating System**
>   ([12](../architecture/12-agent-architecture.md), ADR-008) — Agent
>   Kernel, Agent Registry, Agent SDK, and the `inprocess` execution
>   backend — plus the first concrete agents, `action-engine`, and
>   `capability-engine`. This is the point at which NOVA moves from
>   "answers questions" to "does work," and where NAOS ships as a real
>   but intentionally minimal instance of the full architecture in
>   [12 §15](../architecture/12-agent-architecture.md#15-what-ships-in-phase-3-vs-what-the-architecture-already-supports).
>
> **Deliverables**
> - `planning-engine`: objective decomposition, Work Breakdown Structure,
>   Task Graph data model + dependency/critical-path analysis, per
>   [06 §3](../architecture/06-ai-layer-architecture.md#3-planning-engine).
> - `agent-os/kernel`: process/instance management, Kernel Scheduler,
>   health monitoring, the `inprocess` execution backend (only backend
>   enabled this phase).
> - `agent-os/sdk/python`: the `AgentHandler` Protocol, `AgentContext`,
>   `AgentMessage` types — published in `nova-contracts`.
> - `agent-os/registry`: filesystem-based discovery/install pipeline,
>   versioning, Agent Package manifest validation.
> - `agent-os/supervisors`: one supervisor (`engineering`) implemented to
>   prove hierarchical supervision, peer review, and conflict-resolution
>   escalation end-to-end before more supervisors are added in later
>   phases.
> - First agent set (as Agent Packages under `agents/`): `research-agent`,
>   `coding-agent`, `qa-agent`, `architect-agent`, `documentation-agent` —
>   five of the Part 4 categories, enough to prove the pattern before
>   building the rest.
> - `action-engine`: Action Object Model, validation/risk pipeline,
>   terminal + filesystem + git adapters, rollback for reversible
>   actions, Action Queue.
> - `capability-engine`: registry, installation pipeline (sandboxed), and
>   a first batch of built-in capabilities (git, filesystem, terminal,
>   HTTP) that agents declare and consume.
> - `reasoning-engine` extended to Levels 3–4 (now that Planning/NAOS
>   exist to delegate to).
> - `apps/web-client`: Planning + Agent Activity panels added.
>
> **Dependencies:** Phases 2A–2D complete (`reasoning-engine` from 2B must
> exist to feed Planning; `communication-engine` from 2D to report
> progress/results)."

Implementation order, testing strategy, and acceptance criteria are all
already specified by the roadmap itself (`ENGINEERING_ROADMAP.md:524-546`)
— quoted in full in the summary in §14 below.

### 1.2 The naming-collision resolution — read this before anything else

`docs/design/phase-2d/00-master-blueprint.md:22-50`:

> "## 0. A note on naming — reconciling 'Phase 3' with the existing roadmap
>
> This blueprint was requested under the working name 'Phase 3' — divided
> into sub-phases 3A (Voice & Communication Foundation), 3B (Identity &
> Presence), 3C (Conversation Intelligence), and 3D (Personal Companion).
> Before drafting, this name was checked against `ENGINEERING_ROADMAP.md`
> and found to collide with an already-existing, unrelated **Phase 3**
> ('Planning & the NOVA Agent Operating System' — `planning-engine`, NAOS,
> `action-engine`, `capability-engine`), which has zero thematic overlap
> with voice, identity, or conversation. ... Per explicit user decision,
> the roadmap's numbering is preserved: this work is **Phase 2D**...
> Every reference to 'Phase 3' in this project from this point forward
> means the existing NAOS/Planning/Agents phase, unchanged."

This means what shipped in this repo as "Phase 2D-A/B/C/D" (everything
this session has built to date) is **not** an earlier version of "Phase
3" — Phase 3 has never been started. There is exactly one canonical Phase
3, and it is NAOS/Planning/Agents/Action/Capability.

### 1.3 Bible sections defining Phase 3 (all four read in full)

The Bible itself carries **no phasing language at all** — confirmed by
grep returning zero "Phase" matches in every part read. Phase boundaries
are entirely an architecture-doc/roadmap/ADR-layer construct layered on
top of phase-agnostic Bible specs. The Bible parts Phase 3 draws from:

- `docs/bible/part-04-multi-agent-intelligence-system.md` (801 lines) —
  Agent Orchestrator responsibilities, Agent Lifecycle (Idle → Assigned →
  Context Loading → Memory Retrieval → Knowledge Retrieval → Execution →
  Self Validation → Peer Validation → Result Submission → Learning →
  Idle), ~24 agent categories, and the explicit scale target: "10 agents.
  100 agents. 1,000 agents. 10,000 micro-agents. Without redesigning the
  core orchestration system." (part-04:791-799) — this is the exact
  sentence ADR-008 cites as the reason NAOS was promoted out of
  `services/`.
- `docs/bible/part-09-planning-engine.md` (643 lines) — Objective
  Decomposition hierarchy (Objective → Mission → Project → Milestone →
  Epic → Feature → Task → Subtask → Action → Execution Step →
  Verification → Completion), Work Breakdown Structure fields, and an
  explicit architectural rule: "The Planning Engine must remain
  independent from execution... Execution belongs to the Multi Agent
  System. Reasoning belongs to the Reasoning Engine." (part-09:605-615)
- `docs/bible/part-12-action-engine.md` (697 lines) — the Action Principle
  lifecycle (Receive → Validate → Check Permissions → Estimate Risk →
  Prepare Resources → Execute → Monitor → Detect Errors → Recover →
  Verify → Report → Store Experience), Action Object Model fields, 13
  Action Types (only 3 — terminal/filesystem/git — are in Phase 3 scope).
- `docs/bible/part-15-capability-engine.md` (703 lines) — Capability
  lifecycle, Capability Object Model, Installation Pipeline (Download →
  Integrity Verification → Dependency Resolution → Permission Review →
  Sandbox Testing → Registration → Health Check → Activation), and a full
  marketplace vision (deferred to Phase 8+ per doc 12 §15).

**Each Bible part describes a substantially larger surface than roadmap
Phase 3 actually delivers** (~24 agent categories vs. 5; 13 Action Types
vs. 3; full marketplace vs. 4 built-in capabilities; Planning's project
templates/dashboards/long-horizon memory not called out at all). This
narrowing is architecture-doc-acknowledged (doc 12 §15's table, ADR-008,
the 10x Test) as deliberate extensibility design, not a silent omission —
but it means **the Bible is not, by itself, the scope boundary for Phase
3; the roadmap section quoted in §1.1 is.** Per your own instruction to
use documented project scope rather than the Bible's full eventual vision
as the source of truth, §1.1's roadmap deliverable list is what Phase 3
actually builds.

`docs/bible/part-14-autonomy-engine.md` was also checked (opening/scope
only): confirmed the Bible itself does not assign Autonomy Engine to any
phase; "Phase 4" is stated only in the roadmap (`ENGINEERING_ROADMAP.md:550`)
and ADR-032 (`ADR-032-identity-confidence-is-also-an-authorization-signal.md:3-6`).

### 1.4 The core architecture document: `docs/architecture/12-agent-architecture.md`

422 lines, read in full — this is the authoritative NAOS design, written
in advance of any Phase 3 code, and explicitly **supersedes** an earlier
v1 design:

> "Status note: this document supersedes the v1 'Agent Orchestrator as one
> more engine' design, per ADR-008... NAOS is designed, from Phase 3
> onward, as an operating system whose processes happen to be agents —
> not a job queue with agent-shaped jobs." (12-agent-architecture.md:3-10)

Key data models (all quoted verbatim, file:line preserved for
traceability):

**`AgentHandler` Protocol** (12-agent-architecture.md:108-126) — the
interface every agent implements: `on_load`, `on_unload`, `on_assign`,
`execute`, `on_pause`, `on_resume`, `self_validate`, `health_check`,
`on_message`, `metrics_snapshot`.

**`AgentContext`** (12-agent-architecture.md:128-136) — `task: TaskNode`,
`world_model_slice`, `relevant_memory`, `relevant_knowledge`,
`granted_permissions`, `granted_capabilities`, `correlation_id`. An agent
never queries Memory/Knowledge/World Model directly — everything arrives
pre-scoped (12-agent-architecture.md:152-157).

**`AgentExecutionBackend` Protocol** (12-agent-architecture.md:258-263) —
`spawn`, `send`, `health`, `terminate`. Four implementations behind one
interface (12-agent-architecture.md:265-270):

| Backend | Isolation | Introduced |
|---|---|---|
| `inprocess` | None (asyncio task in the kernel process) | **Phase 3 — the only backend enabled** |
| `subprocess` | OS process boundary | Phase 4+ |
| `container` | Docker/Firecracker | Phase 7+ |
| `remote` | Separate machine (`agent-os-worker`) | Phase 8 |

**Agent Package manifest layout** (12-agent-architecture.md:53-91):
```
agents/<name>-agent/
├── agent.yaml       # id, version, category, required_capabilities,
│                     # required_permissions, supported_execution_backends,
│                     # resource_profile, health_check, compatibility
├── src/handler.py    # implements AgentHandler
└── tests/
```

**Supervisor hierarchy** (§9, 12-agent-architecture.md:285-339) —
supervisors are themselves agents (category `supervisor`), living in
`agent-os/supervisors/`; restart strategies `one_for_one` (default),
`one_for_all`, `rest_for_one`; peer review, conflict resolution
(escalates to owning Supervisor, then `reasoning-engine`), delegation
(Executive Cognition delegates at the Supervisor level, never to
individual instances).

**§15 — "What ships in Phase 3 vs. what the architecture already
supports"** (12-agent-architecture.md:410-423), the table the roadmap's
own Objectives paragraph cites directly:

| Capability | Phase 3 (v1) | Already designed for |
|---|---|---|
| Execution backend | `inprocess` only | subprocess/container/remote — P4/P7/P8 |
| Supervision | Flat; Kernel supervises leaf instances | Multi-level trees — P3 ships one supervisor (`engineering`) to prove the pattern |
| Registry | Filesystem-based | Git/HTTP/marketplace — P8+ |
| Peer review | Supervisor-level, first 5 agents | Scales by configuration |
| Versioning | Single version per agent | Multi-version coexistence exists from P3 |
| Agents shipped | 5 named | Remaining Part 4 categories are additive packages |

**§14 — the Chief Executive boundary (ADR-005), binding on every agent
output** (12-agent-architecture.md:401-408):

> "Per ADR-005, no agent, supervisor, or kernel component may publish
> `communication.intent.*` events directly... an agent's only output is
> its `AgentResult`, routed up through its Supervisor to the Agent
> Kernel, then to Executive Cognition Engine, which alone decides what
> (if anything) reaches the user via Communication Engine."

### 1.5 `docs/architecture/06-ai-layer-architecture.md` §3 — the `TaskGraph` model

Full verbatim quote (06-ai-layer-architecture.md:86-112):

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
    critical_path: list[UUID]             # Part 9 "Critical Path Analysis"
```

> "Independent nodes (no shared `depends_on` edges) are dispatched to the
> Agent Orchestrator in parallel... The graph is persisted (Postgres) so
> long-running plans survive process restarts and support Dynamic
> Replanning (Part 9) by mutation rather than regeneration from scratch."

**Note (see §9 discrepancies below):** this section still says "Agent
Orchestrator," the pre-ADR-008 name — a stale-terminology gap doc 12 does
not fully propagate back into doc 06.

### 1.6 `docs/architecture/16-testing-strategy.md` §5 — testing philosophy

Full verbatim quote (16-testing-strategy.md:107-121):

> "Because agent behavior involves LLM-driven decisions (inherently
> non-deterministic), testing follows Part 8's own verification
> philosophy — structural verification, not output-string matching:
> - Assert that the Reasoning Engine's pipeline visited every required
>   stage... not the exact wording of the model's output.
> - Assert the Task Graph produced for a scripted objective has the
>   expected dependency shape and no cycles — not that Planning Engine
>   'picked the right words.'
> - Golden-scenario replays..."

### 1.7 ADR-008 — the founding decision (inline in `00-overview-and-decisions.md:282-329`, not in `adr/`)

> "**Decision.** The Agent Orchestrator is promoted from 'one engine among
> seventeen' to a standalone framework — the NOVA Agent Operating System
> (NAOS) — living in its own top-level `agent-os/` directory, **not
> `services/`**... NAOS has five parts: Agent Kernel, Agent SDK, Agent
> Registry, Execution Backends, Supervision Trees.
>
> **Consequence.** `services/agent-orchestrator` is removed from the
> Service Inventory; `agent-os/` becomes a new top-level pillar alongside
> `apps/`, `services/`, `companion/`... The v1 (Phase 3) implementation
> stays intentionally simple — in-process execution backend only, a flat
> supervision tree, a filesystem-based registry — but every extension
> point needed to reach the full design... is an addition behind an
> existing interface, never a redesign."

This is architecturally significant and easy to miss: **`agent-os/` is a
new top-level repository directory**, a sibling of `services/`,
`packages/`, `apps/` — not a new service inside `services/`. See §8
(prerequisites) for the concrete infra consequence.

### 1.8 The 10x Test — why Phase 3 gets unusual design care

`docs/architecture/00-overview-and-decisions.md:75-102`, in full:

> "Will this still be the correct design if NOVA becomes ten times larger
> in five years? If the answer is no, redesign it before implementation.
> ...Part 4's '10,000 micro-agents... without redesigning the core
> orchestration system' is the most extreme such target in the entire
> Bible. ADR-008 redesigns the Agent Orchestrator accordingly."

The roadmap's own Phase 3 "Estimated complexity" note cites this
explicitly (`ENGINEERING_ROADMAP.md:523`).

### 1.9 Every ADR relevant to Phase 3

| ADR | Relevance |
|---|---|
| **ADR-008** | The founding NAOS decision — §1.7 above. |
| ADR-021 | Deterministic/explainable-routing pattern named as a template for a future Capability Engine agent-selection decision. |
| ADR-025 | Confirms the Phase 2A→6 roadmap sequence (incl. "Voice → Planning/NAOS → Perception/Autonomy...") is unchanged by Personal Edition flagship status. |
| ADR-026 | `GoalsPort` is Reasoning Engine's honest placeholder for Planning Engine (Phase 3); names "Available Capabilities" as a future Capability Engine input. |
| ADR-027 | Requires Executive Cognition's TDD to name Planning Engine and Action Engine/NAOS explicitly in a "what this does NOT do" section; states the Cognitive Priority Matrix extends to every Phase-3-onward engine. |
| ADR-028 | Epistemic-deference default extends symmetrically to Planning Engine and NAOS/Action Engine's agents once they exist. |
| ADR-029 | `long_term_alignment` scoring stays coarse/caller-supplied until "a real Planning Engine's full goal hierarchy exists" (Phase 3). |
| **ADR-032** | Explicitly binding on Phase 3: "binding on every future engine that gates a privileged capability — Action Engine (Phase 3/NAOS), Autonomy Engine (Phase 4)... Future Action Engine (Phase 3/NAOS)... design work must define their own configurable confidence-threshold gating logic consuming perception-engine's identity signal... Phase 3 (Action Engine/NAOS)... design work must cite this ADR explicitly when defining their own execution-gating logic." |
| ADR-033/034 | No direct Phase 3 mention, but establish the two-tier testing and shared-infra-package conventions Phase 3's own repositories/tests are expected to follow (see §12). |

No ADR defines "Task Graph" or "Supervisor" terminology directly — those
are doc-12-only constructs (confirmed via case-insensitive grep across
`docs/architecture/adr/`, zero matches).

---

## 5. What Phase 3 touches — engines, packages, contracts, infra

**New top-level engines/services (per roadmap §1.1):** `planning-engine`,
`action-engine`, `capability-engine` — each presumably gets its own
Postgres schema, hand-written `0001_initial_schema.py`, and outbox-worker
pair, mirroring every prior engine's established pattern (§12).

**New top-level directory (not inside `services/`):** `agent-os/`
(`kernel/`, `sdk/python/`, `registry/`, `supervisors/`), per ADR-008.

**New top-level directory:** `agents/` (Agent Packages:
`research-agent`, `coding-agent`, `qa-agent`, `architect-agent`,
`documentation-agent`).

**New/extended `apps/`:** `apps/web-client` gets Planning + Agent
Activity panels (`apps/` does not exist on disk yet at all — see §6).

**`nova-contracts` additions:** `AgentHandler`-adjacent types
(`AgentContext`, `AgentMessage`, `AgentHealth`, `AgentMetrics`),
`TaskNode`/`TaskGraph`, Action Object Model, Capability Object Model, and
whatever new Event Bus subjects planning/action/capability/agent-os
introduce (e.g. `planning.decompose.request`, referenced at
12-agent-architecture.md:369, though not yet defined as a payload class
anywhere).

**Existing engines extended, not rebuilt:**
- `reasoning-engine` — Levels 3–4 completion (see §6/§9 — smaller than it
  sounds), and `GoalsPort` migrated off its Phase 2B placeholder.
- `executive-cognition-engine` — `GoalsPort` migration; Cognitive
  Priority Matrix becomes an input to the Kernel Scheduler
  (`docs/design/phase-2c/00-executive-cognition-engine.md:597-622`,
  quoted in full in §7).
- `communication-engine` — receives agent/planning progress reports via
  its existing `communication.intent.deliver.request` gate (no new
  delivery mechanism per doc 12 §14 — ADR-005 still applies).

**Untouched, confirmed by both roadmap and design docs:**
`memory-engine`, `knowledge-engine`, `world-model-engine`,
`ai-model-orchestration-engine`, `perception-engine`,
`personality-engine`, `digital-twin-engine` (Phase 2D-D's own build is
not touched or extended by Phase 3 — its extension is Phase 4).

---

## 6. What already exists in the codebase for Phase 3

**Nothing has been built.** Confirmed via exhaustive directory/Glob/grep
search — every one of the following returns zero results:
`services/planning-engine`, `services/action-engine`,
`services/capability-engine`, `agent-os/` (anywhere in the repo),
`agents/` (repo root), `apps/` (does not exist on disk at all — see below),
`docs/design/phase-3/` (did not exist before this document),
`docs/roadmap/architecture-reviews/*phase-3*`, and no `Planning*`,
`Agent*`, `Action*`, `Capability*`, `TaskGraph*`, `NAOS*`, `Supervisor*`
class/type exists anywhere in `packages/nova-contracts`. `git log --all`
across the repo's one existing ref shows zero commits touching Phase 3
work.

**One forward-declared, currently-inert infra trace:** `pnpm-workspace.yaml`
(repo root) already globs `apps/*`, `packages/*`, `services/*` — the
`apps/*` entry has no matching directory yet. Harmless today; noted as a
placeholder consistent with Phase 3's `apps/web-client` deliverable.

**Root `pyproject.toml`'s `root_packages`/import-linter contracts** list
exactly the 11 existing engines (plus `nova_testkit`, `nova_service_kit`)
— no placeholder entries for any Phase 3 package. `tools/scaffold-engine.py`
adds entries automatically at scaffold time, per its own existing
convention.

**`docker-compose.local.yml` and all three GitHub Actions workflows**
contain zero references, commented or otherwise, to any Phase 3 service.

---

## 7. Complete / partial / dormant / incorrectly-wired / missing

### 7.1 Complete
Nothing — no Phase 3 code exists (§6).

### 7.2 Partial — the one genuine surprise in this research

**`reasoning-engine`'s "reasoning levels" mechanism is not a stub.** The
roadmap frames Phase 3 as extending reasoning-engine "to Levels 3–4," and
the Phase 2B roadmap objective explicitly scoped only "Levels 1–2"
(`ENGINEERING_ROADMAP.md:334-341`) — but the actual Phase 2B code already
structurally handles all four levels:

- `services/reasoning-engine/src/nova_reasoning_engine/domain/modes/__init__.py:53-84`
  (`resolve_mode_and_level`) already routes level 3 → `STRATEGIC` and
  level ≥4 → `MULTI_STEP`, using a plain `int` field
  (`reasoning_level_hint: int | None`, `ge=1, le=4`) that has never been
  restricted to 1–2 in code.
- `domain/modes/strategic.py`, `long_term_planning.py`, `multi_step.py`
  already exist as real `ModeConfig`s and self-document as "Level 3" /
  "Level 4 territory."

**What is genuinely missing** is narrower than "Levels 3-4 don't exist":
1. `multi_step.py`'s actual recursion trigger — confirmed as open,
   explicitly deferred work in
   `docs/roadmap/architecture-reviews/phase-2b-gate-review.md:560-561`:
   "Implement Multi-step mode's recursion trigger... once a real caller
   exercises Level 3/4 requests that plausibly need it."
2. `GoalsPort`'s migration off its Phase 2B/2C caller-supplied placeholder
   to a real Planning Engine RPC (same gate review, line 558-559).

This changes the shape of implementation-order step 7 (§14) — it is a
much smaller, largely self-contained piece of work than "extend
reasoning-engine to Levels 3-4" sounds like, and does not itself require
`planning-engine` to exist first for the recursion-trigger half.

### 7.3 Dormant — a consistent, deliberate set of forward-declared seams

Both `reasoning-engine` and `executive-cognition-engine` carry the exact
same "honest placeholder for a not-yet-built future engine" idiom already
established and resolved once before (`PersonalContextPort` → Digital
Twin Engine, Phase 2D-D). The Phase-3-facing instances:

- **`GoalsPort`** (real Protocol + real client in both engines) — always
  returns `[]`/caller-supplied goals.
  `services/reasoning-engine/src/nova_reasoning_engine/domain/ports.py:105-114`;
  `services/executive-cognition-engine/src/nova_executive_cognition_engine/domain/ports.py:82-91`.
- **`FailureAction.DELEGATE`** — enum value exists
  (`packages/nova-contracts/src/nova_contracts/events/reasoning.py:56`)
  but is never selected by either engine's `recommend_recovery`; both
  modules' docstrings name it as "a named future extension point...
  depends on NAOS, Phase 3."
- **`ReasoningTrace.selected_capabilities`** — always empty; docstring:
  "placeholder field until Capability Engine (Bible Part 15) exists"
  (`domain/models.py:340-341`).
- **`ReasoningMode.COLLABORATIVE`** — a real `ModeConfig` exists
  (`domain/modes/collaborative.py:17-20`) but `config_for()` deliberately
  raises `NotImplementedModeError("Collaborative mode depends on NAOS
  (Phase 3+) and is not implemented in Phase 2B.")`
  (`domain/modes/__init__.py:40-49`).
- **Decision Matrix** — 9 of 12 Bible-named scoring criteria score at a
  fixed neutral midpoint pending "a Capability Engine or richer
  `Alternative` metadata" (`domain/decision_matrix.py:6-17`).
- **`pipeline.py`'s "Execute" step** — explicitly documented as never
  meaning literal action-taking ("Action Engine/NAOS's job",
  `domain/pipeline.py:6-8`).
- **`CapabilityPort`** — named in `executive-cognition-engine`'s
  `domain/ports.py` module docstring only, never defined as an actual
  Protocol class ("`KnowledgePort` and a `CapabilityPort` are
  deliberately absent this phase").

### 7.4 Incorrectly wired
None found. This is a genuinely clean "nothing built yet" state, not a
half-wired one.

### 7.5 Missing
Everything named in §1.1's deliverable list, in full.

---

## 8. Phase 2D-D outputs Phase 3 depends on

Per the roadmap's own Phase 3 "Dependencies" line and the Master
Blueprint's dependency graph (`docs/design/phase-2d/00-master-blueprint.md:515-520`):

> "**What depends on Phase 2D:** Phase 3 (NAOS/Planning/Agents) —
> already documented in the existing roadmap: 'communication-engine from
> 2D to report progress/results.' Agent supervisors' peer-review
> escalations and Planning's status updates become user-visible only
> through Phase 2D's `communication.intent` gate. No change to this
> dependency."

Concretely: Phase 3 depends on `communication-engine`'s existing,
already-shipped `communication.intent.deliver.request` gate (Phase
2D-A) as the *only* legal path for any agent/planning/action output to
reach the user (ADR-005, doc 12 §14) — no new delivery mechanism, and no
dependency on `digital-twin-engine`, `personality-engine`, or any other
Phase 2D-D-specific output. Phase 2D-D's own explicit non-goals
(`docs/design/phase-2d/06-personal-companion.md:739-762`) confirm this:
every excluded item is framed as **Phase 4** (autonomy-engine, the
remaining Digital Twin domains, execution-trust) — Phase 2D-D names zero
dependencies in the Phase 3 direction.

**Reasoning-engine's own dependency on Phase 3, in the other direction:**
`GoalsPort`'s migration and Multi-step mode's recursion trigger (§7.2)
are the only two concrete pieces of *existing* code Phase 3 will change.

---

## 9. Discrepancies between Bible / roadmap / task tracker / design docs / code

1. **Doc 06 §3 still says "Agent Orchestrator," not NAOS/Agent Kernel**
   (`06-ai-layer-architecture.md:108-109`), even though doc 12's own
   status note says this design is *superseded* by NAOS per ADR-008
   (`12-agent-architecture.md:3-4`). A stale-terminology gap, not a
   contradiction in substance — doc 06 does link to doc 12 for Level 4
   delegation (`06-ai-layer-architecture.md:69`).
2. **`reasoning-engine`'s level-dispatch machinery already structurally
   handles levels 3–4** (§7.2), ahead of the roadmap's stated Phase 2B
   (Levels 1–2) / Phase 3 (Levels 3–4) split. Not a contradiction so much
   as the roadmap prose overstating how much net-new work remains.
3. **Doc 20 (`engine-responsibility-boundaries.md`) does not cover Phase
   3 at all.** Its own text states its scope is Memory/Knowledge/World
   Model only (`20-engine-responsibility-boundaries.md:10-14`); Action/
   Agent OS appears exactly once, labeled "(later phases)" in a diagram
   (lines 98-99). **The actual Phase-3-relevant boundary document is
   `docs/design/phase-2c/00-executive-cognition-engine.md` §5.7–§5.10**
   (quoted in full in §1.9/§8's linked material), not doc 20 — worth
   flagging explicitly so doc 20 is not mistaken for authoritative here.
4. **Task tracker has zero Phase 3 entries** (tasks #1–203, this session)
   — accurate, not stale; nothing has been claimed about Phase 3 that
   isn't true. One pre-existing, cross-phase item remains open regardless
   of Phase 3: task #93, "Real-Postgres verification of
   personality-engine, communication-engine & perception-engine repo
   layers," unresolved since Phase 2D-A, resolved only via GitHub Actions
   evidence on a per-phase basis, same as documented throughout Phase
   2D-D's own Gate Review §8.
5. **The Phase 2D-D Gate Review contains zero Phase 3 mentions** — this
   is correct, not a gap; Phase 2D-D's own forward references are all to
   Phase 4 (§8 above).
6. **Bible Parts 04/09/12/15 each describe substantially more than
   roadmap Phase 3 delivers** (§1.3) — architecture-doc-acknowledged
   intentional narrowing, not a silent contradiction, but worth stating
   plainly since Bible-only reading would over-scope Phase 3.
7. **The historical "Phase 3" naming collision** (§1.2) is fully resolved
   in the Master Blueprint, but is worth restating here since "Phase 3"
   appears informally attached to two different things across this
   project's documentation history — only one is canonical going forward.

---

## 10. Stale task-tracker claims

None found specific to Phase 3 (§9 item 4). The one open, non-Phase-3
item worth carrying forward is task #93 (real-Postgres verification for
three Phase 2D engines) — still not formally closed by local means,
though real-infra CI evidence has substantively covered it since
Priority 6 and the Phase 2D-D real-infra run (§0).

---

## 11. Existing architectural precedents that should govern Phase 3

1. **Additive extension over rewrite** — the same pattern already used
   for `executive-cognition-engine` (Phase 2C → Phase 6) and
   `digital-twin-engine`/`perception-engine` (Phase 2D → Phase 4) applies
   to `reasoning-engine`'s Level 3-4 completion: extend, never redesign
   the existing pipeline/mode-dispatch.
2. **"Honest placeholder, not fabricated behavior"** — the `GoalsPort`/
   `CapabilityPort`/`FailureAction.DELEGATE`/`ReasoningMode.COLLABORATIVE`
   pattern (§7.3) is the established idiom for how Phase 3 should migrate
   these seams: swap the placeholder implementation for a real RPC-backed
   one without changing the Protocol's own shape or any caller — exactly
   as `PersonalContextPort` was resolved in Phase 2D-D.
3. **Per-engine schema + transactional outbox + `nova-service-kit`
   dispatcher** — every engine since the STEP3 extraction wave uses this
   identical repository/worker pattern; `planning-engine`,
   `action-engine`, and `capability-engine` should follow it exactly
   (ADR-034 makes `nova-service-kit` the binding shared-infra contract).
4. **Two-tier testing (ADR-033)** — fake-backed default suite +
   `@pytest.mark.real_infra`, 85% domain-coverage gate, real-infra CI
   matrix entry per new engine — applies unchanged to all three new
   engines.
5. **ADR-005 (Chief Executive boundary)** — no agent, supervisor, or
   kernel component may publish `communication.intent.*` directly (doc
   12 §14); all Phase 3 output reaches the user exclusively through the
   existing, unmodified `communication-engine` gate.
6. **ADR-024 (interface versioning)** — every new `nova-contracts`
   payload (Task Graph, Agent messages, Action/Capability objects) is
   additive/versioned from its first commit, same as every prior phase.
7. **Doc 22/23 standing directives** — "every interruption has a
   measurable cognitive cost" (doc 22 §4) and "Lifelong Consistency"
   (doc 23) are explicitly, by name, binding on "any agent or capability
   whose result eventually reaches the user through communication-engine"
   (`docs/architecture/23-nova-personality-specification.md:474-500`) —
   every future agent/capability-result-reporting design must be checked
   against both documents, the same discipline every engine's TDD has
   followed since Phase 2D-A.
8. **Stop-and-present-forks discipline** — the same standing instruction
   this entire session has followed (Fork A–F in Phase 2D-D, Forks in
   Priority 4/6) applies to Phase 3's genuinely open questions; see §13.

---

## 12. Security, ownership, persistence, event-contract, API, and boundary implications

**Security/authorization.** `docs/architecture/13-auth-and-security.md`
§7 ("Sandboxing capabilities and agent execution", lines 90-98) already
specifies the model Phase 3 must implement:

> "New capabilities run in a gVisor/Firecracker-isolated sandbox on
> install and on every execution until explicitly promoted to trusted
> status by the user. Action Engine's risk classification (Negligible →
> Critical, Part 12) gates whether an action executes automatically,
> requires confirmation, or is refused outright by policy — enforced in
> `action-engine` *and* re-checked by `autonomy-engine` (defense in
> depth: two engines must agree, neither can unilaterally authorize a
> Critical action)."

**This names a two-engine defense-in-depth model, but `autonomy-engine`
is Phase 4 and does not exist during Phase 3.** This is Fork 2 in §13 —
it requires an explicit decision about what Phase 3's `action-engine`
does alone.

`PermissionGrant` (doc 13 §4, lines 52-60) is the authorization data
model Phase 3's capability/action permission checks plug into; `nova-auth`
itself (the engine that enforces it at runtime) is not built until
Phase 4, so Phase 3's own permission checks are necessarily partial/local
until then, consistent with the additive-extension precedent (§11.1).

**Ownership boundaries.** Established, not open: Planning owns
decomposition only, never execution (Bible Part 9); Action Engine owns
execution only, never planning (Bible Part 12); Capability Engine owns
reusable building blocks only, consumed by both (Bible Part 15); NAOS
(Agent Kernel/SDK/Registry/Supervisors) owns *running* agents, never
domain logic (doc 12 §7: "the kernel itself [stays] free of domain
logic"). Executive Cognition coordinates cognitive-resource contention
between Reasoning/Planning/NAOS but never itself spawns or supervises an
agent (`docs/design/phase-2c/00-executive-cognition-engine.md:597-622`,
§5.10, quoted in full above).

**Persistence.** Task Graphs are persisted to Postgres specifically so
they "survive process restarts" and support Dynamic Replanning by
mutation (doc 06 §3). This is a hard requirement, not an implementation
detail — the roadmap's own acceptance criteria demands it explicitly:
"Killing `agent-os-kernel` mid-execution and restarting resumes in-flight
Task Graph work rather than restarting it from scratch"
(`ENGINEERING_ROADMAP.md:545`). This means `agent-os/kernel` needs its
own real, Postgres-backed persistence for Task Graph + Agent Instance
state — unlike, e.g., `communication-engine`'s `SessionRegistry`, which
is deliberately pure in-memory (per-instance, ADR-025 single-user scope).
Each of `planning-engine`, `action-engine`, and `capability-engine` gets
its own schema, per the established per-engine-schema convention (§11.3).

**Event contracts.** No planning/action/capability/agent subject is
defined in `nova-contracts` yet (§6). `planning.decompose.request` is
named in prose (doc 12 §11) but not defined as a payload class anywhere
— an early Phase 3 deliverable, following the same "define the contract
type, register the subject, write the round-trip test" pattern used for
every prior phase's `nova-contracts` step.

**API surface.** Bible Parts 9/12/15 each name a full CRUD-plus-lifecycle
API (Create/Execute/Pause/Resume/Cancel/Retry/Verify/Rollback/Query/
Replay for Actions; Register/Install/Remove/Update/Search/Execute/
Benchmark/Validate/Monitor for Capabilities) — roadmap Phase 3 scope is
narrower (§1.3); the exact API surface for the Phase 3 slice is a TDD
question, not yet answered by any existing document.

**Boundary confirmation.** No `PlanningPort`/`ActionPort`/`CapabilityPort`
Protocol class is defined anywhere in code yet — only `GoalsPort` (a real
placeholder) and a docstring-only mention of `CapabilityPort` exist
(§7.3). Defining these two missing ports (in `reasoning-engine` and/or
`executive-cognition-engine`, per the same pattern `GoalsPort` already
establishes) is itself a piece of Phase 3-adjacent work, not yet done.

---

## 13. Infrastructure and real-infrastructure verification requirements

1. **New top-level directory registration.** `agent-os/` is a new
   top-level pillar (§1.7), not nested under `services/` — this means
   `pnpm-workspace.yaml` needs a new `"agent-os/*"` glob entry (currently
   only `apps/*`, `packages/*`, `services/*`), and the root `uv` workspace
   configuration in `pyproject.toml` needs equivalent treatment. This is
   a genuine, concrete infra prerequisite `tools/scaffold-engine.py` does
   not currently handle (it scaffolds into `services/`).
2. **`apps/` does not exist on disk at all.** Creating `apps/web-client`
   is a first-of-its-kind addition to this repo's structure — no existing
   frontend scaffold/tooling precedent exists to follow; this needs its
   own design decision (Fork 5, §14) before implementation.
3. **Real-infra CI matrix** (`.github/workflows/real-infra-checks.yml`)
   needs new entries for `planning-engine`, `action-engine`,
   `capability-engine`, following the exact pattern already used for the
   11 existing engines.
4. **`docker-compose.local.yml`** needs new service entries for all three
   engines plus their outbox workers, mirroring `digital-twin-engine`'s
   exact Phase 2D-D pattern (worker deployed from day one).
5. **Sandboxing infrastructure** (gVisor/Firecracker, doc 13 §7) is a
   genuinely new infrastructure dependency this project has not needed
   before — no existing engine sandboxes untrusted code. This is a real
   new capability to stand up, not a reuse of an existing pattern (Fork 2,
   §14).
6. **Phase 2D-D's own real-infra confirmation is still outstanding**
   (§0) — should close before Phase 3 work begins, consistent with "do
   not mark [a phase] complete until the relevant real-infrastructure
   evidence supports the claim," which was explicitly this session's
   Phase 2D-D discipline and should carry forward.

---

## 14. Recommended dependency/implementation order

The roadmap already specifies one (`ENGINEERING_ROADMAP.md:524-531`),
quoted here in full since it is the starting point for any TDD:

> "1. `planning-engine` Task Graph model + decomposition (no agents yet
>    — output inspected manually).
> 2. `capability-engine` registry + sandboxing + the four foundational
>    capabilities.
> 3. `action-engine` (depends on capabilities existing to execute
>    against).
> 4. `agent-os/sdk` + `agent-os/kernel` (inprocess backend only) +
>    `agent-os/registry`, validated with a single trivial agent
>    (`research-agent`) to prove the full loop before adding more.
> 5. Remaining four agents.
> 6. `engineering` Supervisor: peer review + conflict resolution
>    (escalating to Reasoning Engine only when the Supervisor can't
>    resolve it itself).
> 7. `reasoning-engine` Levels 3–4."

**One evidence-based adjustment worth considering** (see Fork 3, §15):
given §7.2's finding that reasoning-engine's Level 3-4 dispatch mechanism
already exists and only Multi-step's recursion trigger is genuinely
missing, that piece of step 7 could be pulled forward and done
independently/early (it needs no Planning Engine to exist for the
recursion-trigger half) — leaving only the `GoalsPort` real-RPC migration
genuinely last, once `planning-engine` exists to migrate it to.

**Prerequisite step 0, not in the roadmap's own list but required by this
session's standing discipline:** close Phase 2D-D's open real-infra item
(§0) before starting.

---

## 15. Architectural forks requiring explicit approval

Presented as explicit forks per instruction — none of these have been
resolved by existing documentation; each recommendation is grounded in
the ADR/precedent cited.

### Fork 1 — Combined Phase 3 TDD, or split by major component?

Every prior multi-engine phase in this project has been split into
sub-phase TDDs once complexity crossed a threshold (Phase 2D → 2D-A/B/C/D,
each with its own TDD and Gate Review). Phase 3's roadmap "Estimated
complexity: Very High... integrates the most engines simultaneously" and
its own 7-step implementation order spans 4 new services/directories
(`planning-engine`, `agent-os/*`, `action-engine`, `capability-engine`)
plus 5 agent packages plus a new `apps/web-client`.

- **Option A (recommended):** Split into sub-phase TDDs mirroring the
  roadmap's own 7-step order — e.g., 3A (`planning-engine`), 3B
  (`capability-engine` + `action-engine`), 3C (`agent-os` kernel/SDK/
  registry + first agent), 3D (remaining agents + `engineering`
  supervisor), 3E (`reasoning-engine` Levels 3-4 completion). Matches the
  precedent set by Phase 2D and keeps each Gate Review's blast radius
  reviewable.
- **Option B:** One combined TDD covering all of Phase 3 at once, closer
  to how Phase 2A/2B/2C (single-engine phases) were handled.

**Recommendation: Option A**, on the direct precedent of Phase 2D (the
only prior phase of comparable multi-engine complexity) and the
roadmap's own admission that this phase "deliberately spends more design
care than its immediate feature scope would otherwise justify."

### Fork 2 — Action Engine's Critical-risk approval gate without Autonomy Engine

Doc 13 §7 describes a **two-engine** defense-in-depth model
(`action-engine` classification + `autonomy-engine` re-check) for
Critical-risk actions, but `autonomy-engine` is Phase 4 and does not
exist during Phase 3. The roadmap's own Phase 3 acceptance criteria
nonetheless requires a real, working approval gate now: "A deliberately
risky action... is blocked pending approval per its risk classification,
and proceeds only after approval — end-to-end proof of Part 12's Safety
Layers, **ahead of the full Autonomy Engine (Phase 4) providing the
policy layer around it**" (`ENGINEERING_ROADMAP.md:544`).

- **Option A (recommended):** `action-engine` implements the full,
  genuine approval loop alone in Phase 3 (risk classification →
  block/require-confirmation/refuse → confirmation delivered/collected
  via the existing `communication.intent` gate) as a real, single-engine
  safety mechanism. Phase 4's `autonomy-engine` is added **additively**
  as a second, independent check later — exactly the "extension point,
  never a redesign" pattern ADR-008 and the additive-extension precedent
  (§11.1) already establish for this exact kind of two-phase engine
  relationship.
- **Option B:** Defer any real approval gate to Phase 4 and ship Phase
  3's `action-engine` with only risk *classification*, no enforcement,
  explicitly disclosed as partial.

**Recommendation: Option A** — the roadmap's acceptance criteria leaves
no real room for Option B (it explicitly demands proceeds-only-after-
approval behavior in Phase 3 itself), and Option A is the only reading
consistent with ADR-008's own stated design discipline.

### Fork 3 — Capability sandboxing depth in Phase 3

Doc 13 §7 states new capabilities "run in a gVisor/Firecracker-isolated
sandbox on install and on every execution" — but doc 12 §8/§15 places
the `container` execution backend (Docker/Firecracker, the same
isolation technology) at **Phase 7+** for *agents*, with only `inprocess`
enabled in Phase 3. It's not written anywhere whether *capability*
sandboxing (Bible Part 15, roadmap's "capability-engine: ...installation
pipeline (sandboxed)") is expected to reach full gVisor/Firecracker-grade
isolation in Phase 3 itself, or whether Phase 3 ships a lighter mechanism
(e.g., OS-level permission scoping, restricted subprocess execution) with
heavy sandboxing infrastructure arriving alongside the `container` agent
backend in Phase 7+.

- **Option A (recommended):** Phase 3 ships a real but lighter-weight
  sandbox for the four foundational capabilities (git/filesystem/
  terminal/HTTP) — OS-level permission/resource scoping sufficient to
  prevent a capability from escaping its declared permission scope (the
  roadmap's own testing-strategy line: "Sandboxed capability execution
  tests proving no capability can escape its declared permission scope,"
  `ENGINEERING_ROADMAP.md:533`) — with gVisor/Firecracker-grade isolation
  deferred to Phase 7+ alongside the `container` execution backend,
  consistent with doc 12 §15's own extension-point discipline.
- **Option B:** Stand up real gVisor/Firecracker sandboxing in Phase 3
  itself, ahead of doc 12's own stated Phase 7+ timeline for that
  isolation technology.

**Recommendation: Option A** — Option B would mean building genuinely new,
heavyweight infrastructure (nothing in this project has ever sandboxed
untrusted code before) years ahead of doc 12's own explicit schedule for
the identical isolation technology, which is inconsistent with every
other "ship the interface now, the heavy backend later" decision this
architecture makes.

### Fork 4 — `apps/web-client` scaffolding approach

`apps/` does not exist anywhere in this repository. No prior phase has
built a frontend. This is a first-of-its-kind addition with no internal
precedent to follow (framework choice, build tooling, how it fits the
pnpm/turbo monorepo pipeline).

- **Option A:** Scope `apps/web-client`'s Planning + Agent Activity
  panels as a genuinely minimal, framework-light UI (consistent with
  "the v1 implementation stays intentionally simple" applied to the
  frontend too), deferring any richer frontend architecture decision.
- **Option B:** Treat this as its own small, dedicated research/design
  pass (framework, state management, how it talks to the backend engines)
  before folding it into whichever Phase 3 sub-phase TDD covers it.

**No recommendation offered** — this is a technology-choice fork with no
governing ADR or Bible guidance found in this research pass; it should be
raised explicitly rather than defaulted.

### Fork 5 — Sequencing reasoning-engine's Level 3-4 completion

Per §7.2/§14: the roadmap's implementation order places "reasoning-engine
Levels 3-4" last (step 7), but the actual missing work (Multi-step mode's
recursion trigger) does not require `planning-engine` to exist first —
only the separate `GoalsPort` migration does.

- **Option A (recommended):** Split step 7 into two pieces —
  Multi-step's recursion trigger done early/independently (low risk,
  self-contained, closes an already-identified Phase 2B gate-review
  recommendation), `GoalsPort`'s real-RPC migration done last once
  `planning-engine` exists (unchanged from the roadmap's own step 7
  placement).
- **Option B:** Keep step 7 as a single, undivided unit at the end of
  the sequence, exactly as the roadmap states it.

**Recommendation: Option A** — matches the evidence in §7.2 exactly and
closes a piece of already-documented Phase 2B technical debt earlier
rather than bundling it with unrelated, later-dependent work.

### Fork 6 — Doc 06 §3's stale "Agent Orchestrator" wording

Should this terminology be corrected (Agent Orchestrator → NAOS/Agent
Kernel) as a small, disclosed documentation fix at the start of Phase 3's
own design work, or left as-is until Phase 3's own TDD naturally
supersedes it?

**Recommendation:** Fix it as a trivial, one-line documentation
correction alongside whichever Phase 3 sub-phase TDD first references
doc 06 §3 — not worth a standalone pass, but also not worth leaving
silently inconsistent once Phase 3 work actually begins citing that
section.

---

## Executive summary

**Phase 2D-D is not yet formally closed** — real-infra confirmation of
the Step 10 fix is still pending; no new GitHub Actions run has fired
against it as of this research pass. A follow-up check is already
scheduled.

**Phase 3 is unambiguous and well-specified in the documentation, and
completely unbuilt in code.** The canonical scope is
`ENGINEERING_ROADMAP.md`'s "Phase 3 — Planning & the NOVA Agent Operating
System (NAOS)" section: `planning-engine`, `agent-os/{kernel,sdk,registry,
supervisors}`, five named agents, `action-engine`, `capability-engine`,
`reasoning-engine` Levels 3-4, and `apps/web-client`. This is backed by a
detailed, pre-written architecture document (`docs/architecture/
12-agent-architecture.md`, superseding an earlier design per ADR-008),
a `TaskNode`/`TaskGraph` data model (doc 06 §3), and seven ADRs that
already name Planning/Action/Capability/NAOS as forward-looking
dependencies of already-shipped engines. Every Bible part Phase 3 draws
from (04, 09, 12, 15) describes a substantially larger eventual system
than roadmap Phase 3 actually delivers — the roadmap, not the Bible's
full vision, is the correct scope boundary, consistent with your
instruction.

Nothing has been built yet — confirmed by exhaustive search, not
assumed — but the codebase is not silent about Phase 3: `reasoning-engine`
and `executive-cognition-engine` both carry a consistent, deliberate set
of "honest placeholder" seams (`GoalsPort`, `FailureAction.DELEGATE`,
`ReasoningMode.COLLABORATIVE`, `selected_capabilities`) explicitly
awaiting Phase 3, following the exact same idiom `PersonalContextPort`
used before Phase 2D-D resolved it. One genuine, evidence-based surprise:
`reasoning-engine`'s reasoning-level dispatch already structurally
handles levels 3-4 in code today; what's actually missing is narrower
(Multi-step's recursion trigger, `GoalsPort`'s RPC migration) than the
roadmap prose implies.

Six explicit forks are presented for decision in §15 — most with a
recommendation grounded in existing ADRs/precedent, two (Fork 4, the
`apps/web-client` frontend approach) with no governing precedent found
and no recommendation offered. No Phase 3 TDD exists yet to review
against current implementation, since none has ever been written.

**No code was written or modified during this pass.**
