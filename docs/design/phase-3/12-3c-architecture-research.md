# Phase 3C Architecture Research: `capability-engine`

**Status: research only. No production code, no contract changes, no CI changes, no
implementation branch. TDD 3C (`06-tdd-3c-capability-engine.md`) is not modified by
this document.** This is a pre-implementation research pass, produced on a dedicated
`phase-3c-research` branch created from the tip of `phase-3b-planning-domain`
(`c9ab53e`), per the standing research→implementation workflow. It does not authorize
Phase 3C implementation to begin.

All file:line citations below were independently verified against the actual files on
disk as of this branch's tip (`c9ab53e`, 2026-08-16) unless otherwise noted. Two
background research passes fed this document (a deep read of TDD 3C + Bible Part 15;
a downstream trace through TDD 3D, TDD 3E, and the gateway/`3-P` prerequisite doc) plus
direct verification of ADRs, `pyproject.toml`'s import-linter contracts, the actual
`services/` and `packages/nova-contracts/` trees, and `infra/docker/docker-compose.local.yml`.
Where the two research passes and direct verification agree, that is stated as
confirmed fact. Where a document's own internal citation is imprecise, that is flagged
as a documentation-quality issue distinct from an architectural question.

---

## 1. Research scope

This pass covers, in full: `docs/design/phase-3/06-tdd-3c-capability-engine.md` (349
lines, capability-engine's own TDD), `docs/bible/part-15-capability-engine.md` (703
lines, the product-vision chapter), `docs/design/phase-3/02-master-scope.md` (Phase 3C's
place in the overall Phase 3 dependency graph), `docs/design/phase-3/00-research-and-scope.md`
(pre-TDD research, Fork E3's origin), `docs/design/phase-3/01-tdd-preparation-and-fork-resolutions.md`
(Fork E3's formal resolution, the ownership-boundary precedent Fork 3C-1 cites),
`docs/design/phase-3/07-tdd-3d-action-engine.md` (371 lines, the primary downstream
consumer), `docs/design/phase-3/08-tdd-3e-agent-os.md` (438 lines, the second downstream
consumer), and `docs/design/phase-3/03-gateway-web-prerequisite.md` (276 lines, the
`api-gateway`/`ws-gateway`/`apps/web-client` prerequisite). It also covers every ADR
that names capability-engine or "capability" in a binding sense (ADR-032), the actual
`services/`, `packages/nova-contracts/src/nova_contracts/events/`, `pyproject.toml`
import-linter contracts, and `infra/docker/docker-compose.local.yml` as they exist
today, and a repo-wide grep for `capability-engine`/`Capability Engine` across `docs/`
to catch cross-document expectations TDD 3C itself never cites.

Explicitly out of scope for this pass, per the governing instruction: no TDD amendment,
no fork resolution, no scaffolding, no contract types, no implementation branch.

---

## 2. Current Phase 3 state

As of this branch's tip:

| Item | State |
|---|---|
| `main` → `phase-3` → `phase-3b-planning-domain` | Merged, verified, ancestry-clean (PR #2 `bd6dd58`, PR #7 `c9ab53e`) |
| `services/planning-engine` (`3B`) | Domain foundation + decomposition orchestration shipped; two Gate Reviews complete (`phase-3b-domain-foundation-gate-review.md`, `phase-3b-decomposition-orchestration-gate-review.md`) |
| `services/capability-engine` (`3C`) | **Does not exist.** Confirmed by direct `services/` directory listing: `ai-model-orchestration-engine`, `communication-engine`, `digital-twin-engine`, `executive-cognition-engine`, `knowledge-engine`, `memory-engine`, `nova-core`, `perception-engine`, `personality-engine`, `planning-engine`, `reasoning-engine`, `world-model-engine` — 12 engines, no `capability-engine`, no `action-engine` |
| `nova_capability_engine` in root `pyproject.toml` | Absent from `root_packages`, every import-linter contract's `source_modules`/`modules` list, and the workspace member list (confirmed by direct grep) |
| `capability` in `nova_contracts.events` | No `capability.py` file exists (confirmed: directory listing is `ai_model_orchestration.py, communication.py, executive_cognition.py, knowledge.py, memory.py, perception.py, personality.py, planning.py, reasoning.py, system.py, world_model.py` — no `capability.py`) |
| `capability-engine` in `infra/docker/docker-compose.local.yml` | Absent (confirmed by grep — zero matches) |
| Gate Review / architecture-review doc for 3C | None exists (confirmed: `docs/roadmap/architecture-reviews/` contains reviews through `phase-3b-decomposition-orchestration-gate-review.md` only; nothing named `3c`/`capability` anywhere) |
| TDD 3C's own status line | `06-tdd-3c-capability-engine.md:3`: **"Status: design only, awaiting approval. No production code authorized."** — still accurate |
| TDD 3C's age | Committed `e4ea5c0f2c5f3ce8e1a4a48d1df26a971ff60109`, 2026-08-13T23:12:01Z, alongside the whole Phase 3 TDD package (master scope, gateway doc, TDDs 3A–3E) in one commit. Unmodified since (`git log --follow` on the file returns exactly one commit). 3 days old as of today (2026-08-16). |

**What has changed underneath TDD 3C since it was written, relevant to its own
internal reasoning:** `services/planning-engine`'s domain foundation landed
2026-08-14T22:48:51Z and its decomposition orchestration landed 2026-08-16T01:03–01:04Z
— both **after** TDD 3C was committed. As a direct consequence, `RiskLevel` — the type
TDD 3C cites (`06-tdd-3c-capability-engine.md:75-76`) as being in "the same gap class"
(referenced-but-undefined) as its own `CapabilityHandle` — is no longer actually
undefined; it now has a real, committed definition
(`packages/nova-contracts/src/nova_contracts/events/planning.py:33-44`). The precedent
TDD 3C leans on to justify leaving `CapabilityHandle` minimal describes a comparison
case that has since been resolved for its target, while capability-engine's own
instance of the same gap class remains fully open. This is a staleness signal, not a
factual error — flagged here, not corrected in the TDD itself.

---

## 3. Phase 3C objective

TDD 3C does not write a standalone "purpose" paragraph; it opens directly into
scope-and-dependencies. Its own words, `06-tdd-3c-capability-engine.md:9-12` (§0 Scope):

> "**Scope.** Registry, installation pipeline (real, all 8 stages, sandboxed per Fork
> E3's approved lighter OS-level scoping), and a first batch of four built-in
> capabilities (git, filesystem, terminal, HTTP) — per `ENGINEERING_ROADMAP.md:516`
> and Bible Part 15."

The roadmap line it cites, confirmed verbatim (`ENGINEERING_ROADMAP.md:516`): *"`capability-engine`:
registry, installation pipeline (sandboxed), and a first batch of built-in capabilities
(git, filesystem, terminal, HTTP) that agents declare and consume."*

Read across the whole document, TDD 3C's implicit purpose is: **stand up a real
registry, a real 8-stage installation pipeline, and real OS-level sandboxing for
exactly four first-party, bundled built-in capabilities** — nothing about discovery,
marketplace, learning, composition, or dynamic selection.

**Bible Part 15's vision is substantially wider.** It opens (`part-15-capability-engine.md:1-23`):

> "*The Universal Skills and Abilities Framework of NOVA* ... Intelligence without
> capabilities cannot interact effectively with the world. ... Capabilities should be
> independent. Reusable. Versioned. Composable. Continuously improving."

and closes on an explicitly unbounded note (`:653-703`, "THE ULTIMATE GOAL"/"FUTURE
EVOLUTION"): the user should "eventually think about objectives rather than software,"
and the engine "should support capabilities that do not yet exist" (quantum computing
tools, advanced robotics, autonomous vehicles, etc.). None of this appears in TDD 3C.

This is the same Bible-vs-TDD narrowing pattern already established for Phase 3B
(`00-research-and-scope.md:151-161`: *"Each Bible part describes a substantially
larger surface than roadmap Phase 3 actually delivers... the roadmap section... is [the
scope boundary]."*). TDD 3C is **unusually disciplined** about disclosing exactly one
narrowing in detail (the `Capability` model's field list — see §9) while leaving
several other real narrowings implicit rather than named under its own Non-goals
(§25 catalogs these explicitly).

---

## 4. Current architecture

Phase 3C does not yet exist in code, but its documented position in the larger Phase 3
pipeline is fully traceable across TDD 3B/3C/3D/3E. Reconstructed here, each step cited
to its source, since no single document states the full chain in one place:

1. **TaskGraph created** (Phase 3B, shipped) → publishes `planning.task_graph.created`.
2. **Kernel Scheduler** (`agent-os`, TDD 3E) subscribes and, for each ready `TaskNode`,
   queries the **Agent Registry** — not capability-engine — by `assigned_agent_category`
   (`08-tdd-3e-agent-os.md:122-124`, mirroring `12-agent-architecture.md:229-232`
   verbatim).
3. Scores candidates, selects the `inprocess` backend, dispatches a supervised agent
   instance (`08-tdd-3e-agent-os.md:124-131`).
4. The agent instance receives an `AgentContext`, which per doc 12
   (`12-agent-architecture.md:128-136`) includes `granted_capabilities: list[CapabilityHandle]`.
   **Neither TDD 3D nor TDD 3E specifies the mechanism or timing by which this field is
   populated** — see Fork 3C-2, §22.
5. The agent invokes `action-engine` via `action.execute` (RPC), e.g.
   `08-tdd-3e-agent-os.md:293-299`: `coding-agent` "Invokes `action-engine`... using
   granted `filesystem`/`terminal`/`git` capabilities."
6. `action-engine`'s 12-stage Action Principle lifecycle runs
   (`07-tdd-3d-action-engine.md:199-214`): Receive → Validate → Check Permissions
   (ADR-032) → Estimate Risk → **Prepare Resources** → Execute → Monitor → Detect Errors
   → Recover/Rollback → Verify → Report → Store Experience.
7. **`capability-engine` is queried exactly once in the entire documented chain** — at
   stage 5, "Prepare Resources": `07-tdd-3d-action-engine.md:204-205`: "resolve the
   target `Capability` via `CapabilityPort` (§2), confirm it is `health_status="healthy"`."
   Stage 6 then invokes the resolved capability's `execution_adapter`.

**Direct conclusion:** capability-engine, as currently designed, is architecturally a
**passive registry/pipeline service**, queried synchronously and in-process by
`action-engine` at one specific pipeline stage, plus invoked by itself at boot
(bootstrap seed of the four built-ins). It is not, in the current document set, an
event-driven participant in the TaskGraph→action pipeline at all — see §5/§8.

---

## 5. Inputs

**Central finding: TDD 3C documents essentially zero consumed cross-engine inputs.**

The closest thing to an inputs section, `06-tdd-3c-capability-engine.md:186-190` (§5
Ports):

> "No new upstream port needed for `capability-engine` itself — the installation
> pipeline's 'Permission Review' stage surfaces to a human via the existing
> `communication.intent.deliver.request` gate (same precedent as Fork D/TDD 3D — a new
> capability's permission grant is a disclosure-worthy event), not a new mechanism."

This is capability-engine acting as **caller toward** communication-engine (an output,
not an input) — I confirmed `communication.intent.deliver.request` is a real, already-defined
subject (`packages/nova-contracts/src/nova_contracts/events/communication.py`).

The only other input-shaped activity is self-triggered: the four built-in capabilities
go through capability-engine's own install API at first boot
(`06-tdd-3c-capability-engine.md:100-104`) — not an event subscription.

**No event subject, payload type, or publisher engine is documented anywhere in TDD 3C
as something capability-engine subscribes to.**

**A real, cross-document expectation TDD 3C never engages with:**
`docs/architecture/10-inter-engine-communication.md:90` (the canonical Event Bus
scenario table, row 11):

> "| Repository updated | perception-engine (filesystem/git) →
> `perception.filesystem.observed` | ...planning-engine updates roadmap;
> **capability-engine refreshes dependency graph**... |"

This documents capability-engine as a subscriber to `perception.filesystem.observed`.
No payload type name is given anywhere for this, and TDD 3C contains zero references
to `perception.filesystem.observed`, "dependency graph," or any subscription of any
kind. This is a genuine gap between an architecture-doc-level expectation and the TDD
that is supposed to be authoritative for this engine — not resolved here, flagged for
the fork/deferred-decision record (§25).

A second cross-document expectation, directionally an **output** from capability-engine
(covered fully in §6): `docs/architecture/06-ai-layer-architecture.md:126`'s
`PromptAssembly.available_capabilities` read-path.

---

## 6. Outputs

1. **REST API** (§11 below) — `GET /v1/capabilities`, `POST /v1/capabilities/install`,
   `DELETE /v1/capabilities/{id}` (`06-tdd-3c-capability-engine.md:211-215`, verbatim
   match against `docs/architecture/11-api-architecture.md:59-61`).
2. **In-process entity, never published as an event**: `CapabilityHandle`, embedded in
   `AgentContext.granted_capabilities: list[CapabilityHandle]`
   (`06-tdd-3c-capability-engine.md:270-272`). Consumer named only as "potentially...
   `agent-os/kernel`" (`:184-185`) — an explicit hedge, not a commitment (see Fork
   3C-2, §22).
3. **Explicitly not-yet-fixed contract** — `06-tdd-3c-capability-engine.md:272-278`:
   "...whatever install/health-change payloads are needed if `capability-engine`
   publishes state changes (e.g. `CapabilityRegisteredPayload`), exact publish-worthy
   events are a TDD-implementation-time decision, not fixed here." `CapabilityRegisteredPayload`
   is illustrative only, **not a committed type name**.
4. **`action-engine` (TDD 3D) as documented downstream consumer**, via Fork 3C-1/3D-1
   (§22) — `action-engine` defines its own `CapabilityPort` and consumes
   `health_status`/`execution_adapter` (§9 below has the full field trace).
5. **`agent-os` (TDD 3E) as documented downstream consumer** —
   `08-tdd-3e-agent-os.md:19-22`: "`3C` (`capability-engine` — capabilities to grant
   agents)."
6. **Observability metrics** (§16) — four novel counters/histograms, none reused from
   any existing engine.
7. **Cross-document, unaddressed by TDD 3C**: `PromptAssembly.available_capabilities`
   (`06-ai-layer-architecture.md:126`, "from Capability Engine, scoped to the task") and
   ADR-026's inclusion of "Available Capabilities (Capability Engine / Function
   Registry)" as one of six first-class reasoning inputs
   (`ADR-026-reasoning-engine-cognitive-bridge-not-isolated.md:60-61,75-76`). TDD 3C's
   own §25 (Non-goals) addresses the reasoning-engine half of this indirectly (see §25
   below) but never engages with the Prompt-Orchestration half at all.

---

## 7. Contracts

TDD 3C's own contract commitment, `06-tdd-3c-capability-engine.md:270-278` (§11):

> "`nova_contracts.events.capability` (new file): `Capability`, `CapabilityHandle`
> (entities — never independently published; embedded in-process in `AgentContext`)..."

**Nothing has landed in `nova_contracts` yet** — confirmed by direct directory listing
(no `capability.py` in `packages/nova-contracts/src/nova_contracts/events/`) and by
`packages/nova-contracts/src/nova_contracts/events/planning.py:11-14`'s own docstring,
which independently confirms (written for an unrelated reason, during Phase 3B's
implementation): "`06-tdd-3c-capability-engine.md` and `07-tdd-3d-action-engine.md`
neither name `TaskNode` nor `TaskGraph`" — i.e., real code written after TDD 3C already
had occasion to check TDD 3C's text and found no `Capability`/`TaskGraph` cross-reference
in either direction.

**Downstream field-level consumption, verified against TDD 3C's own model (§9's full
schema):**

| Field | Consumed by | Citation |
|---|---|---|
| `health_status: Literal["unknown","healthy","degraded","unhealthy"]` | `action-engine`, stage 5 ("Prepare Resources") | `07-tdd-3d-action-engine.md:204-205` |
| `execution_adapter: str` | `action-engine`, stage 6 ("Execute") | `07-tdd-3d-action-engine.md:206`; also TDD 3C's own Fork 3C-1 reasoning, `:169-171` |
| `CapabilityPort` (the Protocol) | Defined by `action-engine` itself, not by capability-engine (`06-tdd-3c-capability-engine.md:181-183`); "potentially" also needed by `agent-os` (unresolved) |  |
| `CapabilityHandle` (`capability_id`, `name`, `execution_adapter`) | `AgentContext.granted_capabilities` (doc 12) | Never re-derived or mechanized anywhere in TDD 3E's own text — confirmed by exhaustive grep, the string `granted_capabilities` does not appear in `08-tdd-3e-agent-os.md` at all |
| `input_schema` / `output_schema: dict` | **No downstream document references either field at all** — confirmed by full read of TDD 3D and TDD 3E | See Fork-adjacent finding in §18 |

**TS codegen impact:** none yet, since no contract exists. Once `nova_contracts.events.capability`
lands, it will need the same TS-codegen treatment every other `nova_contracts` addition
gets (verified zero-diff generation is part of this project's standard verification
suite for every PR that touches `nova_contracts`).

**ADR-024 (interface versioning) applicability:** whatever payloads eventually land
will need `schema_version: int = 1` per ADR-024's standing rule
(`docs/architecture/adr/ADR-024-interface-versioning-from-day-one.md`) — not yet
relevant since nothing is defined, but a concrete implementation prerequisite (§26).

---

## 8. Events

**Definitive finding, independently confirmed by both research passes: zero
capability-named event subjects exist or are reserved anywhere across TDD 3C, TDD 3D,
TDD 3E, or the gateway doc.**

- TDD 3D's full event-contract list (`07-tdd-3d-action-engine.md:294-307`, §12):
  `Action`, `RetryPolicy`, `RollbackStrategy`, `ActionExecuteRequestPayload`/`ActionResultPayload`,
  `ActionApprovalRequestedPayload`/`ActionApprovalDecidedPayload` — no `capability.*`.
- TDD 3E's full event-contract list (`08-tdd-3e-agent-os.md:308-327`, §10): subscribed
  `planning.task_graph.created`, `agent_os.instance.<instance_id>.inbox`; published
  `agent.<instance_id>.<state>`, `agent_os.health.snapshot`, `agent_os.task.completed`,
  `planning.decompose.request` — no `capability.*`.
- The gateway's `ws-gateway` allow-list (`03-gateway-web-prerequisite.md:117-121`, §3)
  names `planning.task_graph.*` and `agent.*`/`agent_os.*` as **prospective** additions
  once 3B/3E ship, respectively — `capability.*` is never listed, not even
  prospectively, despite 3B and 3E both getting explicit future-tense mentions in the
  same sentence.
- TDD 3C's own §11 (quoted in §7 above) explicitly declines to fix any event subject in
  advance.

**This is favorable for Phase 3C's design latitude:** no downstream consumer currently
depends on any capability-related event subject, so Phase 3C has complete freedom to
design its own event surface (if any) in the implementation phase without breaking an
existing contract. The only hard, cited downstream dependencies are the two in-process
`CapabilityPort` fields (`health_status`, `execution_adapter`) and the passively-fronted
REST surface (§11).

The one real, if indirect, event-driven expectation — capability-engine subscribing to
`perception.filesystem.observed` per `10-inter-engine-communication.md:90` (§5 above)
— remains a genuine, unaddressed gap between that architecture doc and TDD 3C.

---

## 9. Domain responsibilities

### 9.1 `Capability` (`06-tdd-3c-capability-engine.md:31-90`, §2.1)

Bible Part 15 names 18 fields (`part-15-capability-engine.md:157-197`): *Unique
Identifier, Name, Description, Category, Version, Author, Dependencies, Required
Permissions, Required Resources, Supported Platforms, Input Schema, Output Schema,
Execution Adapter, Health Status, Confidence, Performance Metrics, Documentation,
Example Workflows.*

TDD 3C's proposed Phase-3-scoped subset, verbatim (`:45-60`):

```python
class Capability(BaseModel):
    id: UUID
    name: str
    description: str
    category: str
    version: str
    dependencies: list[str] = []
    required_permissions: list[str]
    required_resources: list[str] = []
    input_schema: dict          # JSON Schema, per Input Schema field
    output_schema: dict
    execution_adapter: str      # e.g. "git", "filesystem", "terminal", "http"
    health_status: Literal["unknown", "healthy", "degraded", "unhealthy"]
    installed_at: datetime
```

13 fields. Nine of Bible's 18 names are kept (renamed where noted): `Unique Identifier`→`id`,
`Name`→`name`, `Description`→`description`, `Category`→`category`, `Version`→`version`,
`Dependencies`→`dependencies`, `Required Permissions`→`required_permissions`,
`Input Schema`→`input_schema`, `Output Schema`→`output_schema`,
`Execution Adapter`→`execution_adapter`, `Health Status`→`health_status`;
`Required Resources`→`required_resources`; plus `id`/`installed_at` bookkeeping.

**Explicitly deferred, disclosed** (`:62-69`): `author`, `confidence`, `performance_metrics`,
`documentation`/`example_workflows`, each with a stated reason. **"Flagged for explicit
approval"** — the subset is proposed, not extracted from an authoritative narrower-scope
statement.

**Silently absent, not disclosed as deferred:** `Supported Platforms` — one of Bible's
18 named fields, with no field and no explicit-deferral callout, unlike the other four.

**Cross-document schema conflict, not addressed by TDD 3C anywhere** — a pre-existing
SQL sketch at `docs/architecture/07-database-architecture.md:32-43`:

```sql
CREATE TABLE capability.capability (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    version TEXT NOT NULL,
    permissions JSONB NOT NULL,
    health_status TEXT NOT NULL DEFAULT 'unknown',
    confidence REAL,
    UNIQUE (name, version)
);
```

This includes a `confidence REAL` column directly contradicting TDD 3C's explicit
decision to defer `confidence`; uses singular `permissions JSONB` rather than
`required_permissions: list[str]`; and has no `description`, `dependencies`,
`required_resources`, `input_schema`, `output_schema`, `execution_adapter`, or
`installed_at` columns. TDD 3C never cites this document. This is a documentation
staleness/consistency issue (§25), not treated as an architectural fork (§22 explains
why).

### 9.2 `CapabilityHandle` (`:71-90`, §2.2)

TDD 3C's own resolution of a referenced-but-undefined type — the direct analogue of
TDD 3B's `Estimate`/`RiskLevel` gap. Verbatim (`:73-90`):

```python
class CapabilityHandle(BaseModel):
    capability_id: UUID
    name: str
    execution_adapter: str
```

Deliberately minimal — the full `Capability` record stays in capability-engine's own
registry, never duplicated into every `AgentContext`. **"Flagged for explicit approval."**

**Two citation-precision issues, verified directly:**
- TDD 3C cites `01-tdd-preparation-and-fork-resolutions.md §5.5` as having "already
  established" the `inprocess`-execution-backend reasoning for `AgentContext`. That
  section's actual heading is "5.5 `AgentResult`/`AgentMessage` have no field-level
  definition anywhere yet" (`:652-662`) — about a *different* gap. A full-text grep for
  "AgentContext" in that 880-line document returns zero matches. The closest real
  support is `:582` (§5.1) or the doc-12 execution-backend table quoted in
  `00-research-and-scope.md:193-202` — neither is what TDD 3C actually cites.
- TDD 3C cites `12-agent-architecture.md:136` for `granted_capabilities`; the field is
  actually on line 135 (line 136 is `correlation_id: UUID`). Off by one.

Neither is large, but both are worth carrying into implementation-time verification
rather than trusted at face value.

### 9.3 Capability lifecycle and Installation Pipeline (`:92-113`, §2.3)

Bible lifecycle (`part-15-capability-engine.md:39-81`): *"Discover → Install →
Validate → Register → Learn → Execute → Monitor → Improve → Update → Retire."*

Bible Installation Pipeline (`:241-275`): *"Download → Integrity Verification →
Dependency Resolution → Permission Review → Sandbox Testing → Registration → Health
Check → Activation."*

TDD 3C's design decision (`:100-113`): the four built-ins go through the **real**
8-stage pipeline at first boot via a seed/bootstrap call against capability-engine's
own install API, rather than hardcoded pre-registered rows — proving the pipeline
end-to-end on low-risk, first-party capabilities before any future third-party
capability ever reaches it. For a bundled capability, "Download"/"Integrity
Verification" operate against the package embedded in capability-engine's own container
image, not a network fetch, "since there is no external marketplace to download from in
Phase 3" (internal cross-reference "(§9)" here is imprecise — §9 in the TDD's own
numbering is Observability, not Non-goals; almost certainly means §14/Non-goals).

**Coverage gap (my own analysis, not a TDD claim):** the section header claims the full
10-stage Bible *lifecycle* is "implemented literally," but the body only elaborates the
8-stage *Installation Pipeline*, which maps to 3-4 of the 10 lifecycle stages
(Install/Validate/Register, part of Monitor). **Discover** (beyond the 4 bundled
built-ins), **Learn**, **Improve**, and **Update** have no described mechanism anywhere
in TDD 3C.

### 9.4 Sandboxing design (`:117-137`, §3)

Full table, verbatim:

| Adapter | Scoping mechanism |
|---|---|
| `filesystem` | Path-prefix allow-list validated before every read/write/list call against the capability's `required_resources` declaration. |
| `terminal` | Executable allow-list, restricted working directory, restricted/minimal environment variables, hard timeout, `asyncio.create_subprocess_exec` (never `shell=True`). |
| `git` | Same mechanism as `terminal`, additionally scoped to a declared repository root path — modeled as terminal+filesystem, not a fourth primitive. |
| `http` | Outbound-host allow-list, per-request timeout, no arbitrary redirect-following beyond the allow-list. |

**This depth decision is already resolved, not an open question of this research pass.**
Fork E3 ("Capability sandboxing depth in Phase 3") was raised in
`00-research-and-scope.md §15` and formally decided in
`01-tdd-preparation-and-fork-resolutions.md:236-269`, recording **"User decision:
Option A"** — lighter OS-level scoping, explicitly not gVisor/Firecracker/container
isolation in Phase 3. TDD 3C's own section title makes the two-layer structure
explicit: "## 3. Sandboxing design (Fork E3's approved resolution, made concrete)"
(`:117`). TDD 3C is self-aware of, and explicitly distinguishes itself from, doc13's
gVisor/Firecracker language: `:133-137`, "distinguished clearly from
`docs/architecture/13-auth-and-security.md:90-92`'s gVisor/Firecracker language, which
this design deliberately does not implement (per Fork E3)" (the actual sentence lives
at `13-auth-and-security.md:92-93`, a 2-line citation drift). TDD 3C's own §14
(Non-goals) reiterates: "no `container`/`subprocess`-isolated capability execution
(Fork E3; Phase 7+ for `container`-grade isolation per doc 12 §8)." **This resolves
what could otherwise look like an unaddressed tension between doc12's "container
backend = Phase 7+" and the roadmap's Phase-3 "sandboxed capability execution tests"
line — it is not a tension; TDD 3C already distinguishes its own OS-level mechanism
from the container-grade language elsewhere in the docs.**

What *is* still open is narrower: the **concrete per-adapter mechanism table above** is
a new proposal layered on top of the already-approved depth decision, and is itself
separately marked "flagged for explicit approval" (`:133-134`). See §22 for why this is
not elevated to full fork status.

### 9.5 Domain-concept gap-class summary

TDD 3C's own referenced-but-undefined-elsewhere gap (`CapabilityHandle`) is the direct
analogue of TDD 3B's `Estimate`/`RiskLevel` gap. Both TDD-3B gaps are now resolved in
real code: `RiskLevel` (`packages/nova-contracts/src/nova_contracts/events/planning.py:33-44`)
and `Estimate`/`TaskNode`/`TaskGraph`
(`services/planning-engine/src/nova_planning_engine/domain/models.py:43-93`). TDD 3C's
own analogous gap remains fully unresolved in code, because no capability-engine code
exists at all.

### 9.6 Bible Part 15 narrowing — point-by-point

| Bible Part 15 section | TDD 3C treatment |
|---|---|
| CAPABILITY OBJECT MODEL, 18 fields | 13-field subset; 5 fields explicitly deferred; `Supported Platforms` silently absent |
| CAPABILITY REGISTRY functions (Registration, Version mgmt, Discovery, Compatibility, Health, Dependency resolution, Metadata indexing) | Registration/Version/Health/Dependency-resolution covered; Discovery, Compatibility checks, Metadata indexing not addressed and not itemized as deferred |
| DISCOVERY ENGINE, 6 sources | Fully replaced — explicit first Non-goal |
| INSTALLATION PIPELINE, 8 stages | Implemented "literally" per the TDD's own claim (see §9.3's caveat) |
| DEPENDENCY MANAGEMENT ("circular dependencies should never be allowed") | `dependencies: list[str]` field exists; no cycle-detection algorithm described — silent gap, not a Non-goal |
| SANDBOX EXECUTION (Performance/Security/Permissions/Resource/Stability/Error-handling) | Narrowed to permission/resource-scope enforcement only |
| CAPABILITY COMPOSITION / DYNAMIC SELECTION / LEARNING FROM EXECUTION | Not addressed anywhere |
| CAPABILITY VERSIONING (history, breaking changes, rollback-by-version) | Bare `version: str` only; DELETE-based install-reversal exists but is not version rollback |
| HEALTH MONITORING (Availability/Latency/Error rate/Resource/Dependencies/Update status/Compatibility) | Coarse 4-value `health_status` enum only |
| PERMISSION MODEL, 9 categories (Filesystem/Internet/Camera/Microphone/Desktop/Terminal/Cloud/Databases/IoT) | 4 adapters cover ≤3 of 9; `required_permissions` is a generic string list, not a closed enum |
| SECURITY VALIDATION (Code signing/Hash/Behavior analysis/Dependency scanning/continuous) | Only Integrity Verification + Permission Review survive as pipeline stages |
| PERFORMANCE PROFILING / SELF IMPROVEMENT / CAPABILITY POLICIES | Not addressed |
| CAPABILITY APIs, 9 verbs | 3 of 9 exposed as REST |
| MARKETPLACE READY | Explicit first Non-goal |
| VISUAL CAPABILITY CENTER | Not addressed, and not listed as a Non-goal either — silent omission |
| FAILURE RECOVERY (Disable/Rollback/Notify dependents/Log/Recommend alternatives) | Log + narrow install-rollback covered; "notify dependent capabilities"/"recommend alternatives" absent |
| PERFORMANCE TARGETS ("thousands of installed capabilities") | Phase 3 ships exactly 4; no registry-search-at-scale discussion (contrast `docs/architecture/19-scalability-strategy.md:28`, never cited by TDD 3C) |
| ARCHITECTURAL REQUIREMENTS ("must remain independent from the AI model") | Consistent by omission (§13) but never cited |

**Overall characterization:** TDD 3C narrows Bible Part 15 in the same manner
established as this project's standing TDD-vs-Bible pattern, and is unusually
disciplined about disclosing exactly one narrowing (the `Capability` field list) while
leaving several other equally real narrowings silent. A reader treating TDD 3C's §14
Non-goals as the complete out-of-scope list would miss several real gaps left
undisclosed rather than deferred.

---

## 10. Persistence

`06-tdd-3c-capability-engine.md:194-202` (§6), verbatim:

> "New `capability` Postgres schema: `capability` table (the `Capability` model, §2.1,
> plus `permissions_reviewed_at`/`sandbox_test_passed_at` timestamps recording
> pipeline-stage completion), `capability_installation_event` (append-only log of
> pipeline-stage transitions per install — mirrors `ConversationDecisionTraceORM`'s
> append-only precedent from `communication-engine`)."

Exact names: schema `capability`; tables `capability`, `capability_installation_event`;
two additional timestamp columns beyond the base model.

**The cited precedent is real** — `ConversationDecisionTraceORM` exists in
`services/communication-engine/src/nova_communication_engine/repository/models.py`
(confirmed by grep), so the analogy is grounded in genuinely-existing code.

**The `07-database-architecture.md` schema conflict (§9.1) applies here directly** —
that document's older sketch and TDD 3C's own model disagree on column shape and on
whether `confidence` exists. TDD 3C's §6 does not cite or reconcile against it.

Acceptance criterion 4 (`:329`): "Registry state survives a real-Postgres restart
simulation unchanged" — phrased identically to planning-engine's own bar
(`ENGINEERING_ROADMAP.md:545`).

Failure-mode statement (§8, `:234`): "Postgres unavailable | Registry reads fail
loudly; no capability is invokable without a confirmed-healthy registry entry — never
falls back to an unvalidated in-memory default."

**Whether persistence is genuinely required for Phase 3C itself, vs. required only by
3D/3E, vs. aspirational Bible scope:** genuinely required for 3C — the acceptance
criteria (§20) and the "registry reads fail loudly without Postgres" failure mode both
treat real persistence as load-bearing for capability-engine's own correctness (a
restart must not silently lose which capabilities are installed and healthy). Nothing
in 3D or 3E imposes an *additional* persistence requirement beyond what 3C already
states for itself — 3D/3E only consume the in-process `Capability`/`CapabilityHandle`
objects capability-engine's registry produces, never the tables directly.

No `capability-engine` Docker Compose entry exists yet (confirmed by grep) — consistent
with TDD 3C's own acknowledgment (`:281-282`) that this is standard not-yet-done infra
work, same as for 3B/3D.

---

## 11. API

`06-tdd-3c-capability-engine.md:206-224` (§7), verbatim:

> "Per Bible Part 15's named API verbs (`part-15-capability-engine.md:533-555`) and
> `docs/architecture/11-api-architecture.md:59-61`:
>
> ```
> GET    /v1/capabilities
> POST   /v1/capabilities/install
> DELETE /v1/capabilities/{id}
> ```
>
> Exposed directly (no `api-gateway` yet — same stopgap precedent as TDD 3B/3D).
> Bible's additional verbs (Register/Update/Search/Execute/Benchmark/Validate/Monitor)
> are not all separately exposed as REST endpoints in Phase 3 — `Execute` happens via
> agent/`action-engine` in-process invocation (§4), not a public REST call; `Benchmark`
> has no defined metric to benchmark against yet; the rest are internal pipeline
> stages, not independently callable."

Both citations verified verbatim: `docs/architecture/11-api-architecture.md:59-61`
matches exactly; Bible's `CAPABILITY APIs` section (`:533-555`) names 9 verbs: Register,
Install, Remove, Update, Search, Execute, Benchmark, Validate, Monitor.

The gateway doc's only engagement with Phase 3C (`03-gateway-web-prerequisite.md:47-51`,
§2, REST write path): forwards to `capability-engine`'s already-built `/v1/capabilities`
surface, same pattern as every other engine. No dedicated capability web-client panel
is ever named (only Conversation/Planning/Agent-Activity panels exist in the gateway
doc's scope, `:181-185`).

**A real internal inconsistency in the gateway doc**, flagged for this research (not a
Phase 3C-side fix): its own §0 `3-P.2` scope statement (`:17-20`) names only "The
Planning panel (depends on `3B`) and the Agent Activity panel (depends on `3E`)" —
Phase 3C is never named as a `3-P.2` dependency at the scope-statement level, even
though §2's REST-forwarding table and §5's dependency-mapping table both list
capability-engine's endpoint as something `api-gateway` fronts. The document is
internally inconsistent about whether Phase 3C is formally part of `3-P.2`'s scope or
merely an implicit additive consequence of §2's "purely additive" REST-forwarding
design. This does not require a Phase-3C architectural decision to resolve (the fix is
a `3-P` document correction, out of this branch's scope) but is recorded here since it
bears on when/whether a capability web surface is expected.

---

## 12. Cross-engine boundaries

**ADR-004 (Event Bus only legal cross-engine channel) / import-linter "Engines are
independent" contract:** capability-engine does not exist in `pyproject.toml`'s
`root_packages` or the independence contract's `modules` list yet (confirmed by direct
read of `pyproject.toml:76-90,105-111`). When scaffolded, `tools/scaffold-engine.py`
auto-registers a new engine into `root_packages` and the independence contract per its
own comment (`pyproject.toml:67-73`) — confirmed as real, working tooling by
planning-engine's own Gate Review ("scaffolded via `tools/scaffold-engine.py` (standard
skeleton...)").

**ADR-006 (no direct broker client) / ADR-007 (no direct graph-db client):** both
contracts list every current engine's `source_modules`
(`pyproject.toml:113-136,138-159`); scaffold-engine.py auto-registers new engines here
too, per the same comment.

**ADR-020 (sole legal LLM channel):** the contract at `pyproject.toml:161-182` forbids
`anthropic`/`openai`/`cohere`/`mistralai`/`ollama` imports for every engine except
`nova_ai_model_orchestration_engine` itself. **This contract is NOT auto-registered by
scaffold-engine.py** — confirmed directly during this session's own prior work
(planning-engine had to be added to this specific contract manually as part of PR #7,
a real, previously-undiscovered gap: every model-adjacent engine has needed this same
manual step). Since TDD 3C documents zero relationship to
`ai-model-orchestration-engine` (§13 below), capability-engine should still be added to
this contract's `source_modules` **forbidding** it the same LLM imports every
non-AI-engine is forbidden — making "capability-engine has no AI-model dependency" a
structurally enforced fact rather than merely a documented intention. Concrete
implementation prerequisite, §26.

**ADR-005 (NOVA speaks only through Communication Engine):** capability-engine's one
documented user-facing touchpoint (Permission Review surfacing via
`communication.intent.deliver.request`, §5) already routes through communication-engine,
consistent with ADR-005. No violation found or anticipated.

**Cross-engine field-naming collision, not a documented equivalence:** both
`Capability.category: str` (TDD 3C) and the Agent Registry's `agent_package` table's
own `category` column (TDD 3E, `08-tdd-3e-agent-os.md:165-166`) use the literal field
name `category`; `TaskNode.assigned_agent_category` (TDD 3B, shipped:
`services/planning-engine/src/nova_planning_engine/domain/models.py:73`) also uses the
word "category." **No document anywhere states these are the same namespace, and the
evidence in §18/§19 shows they are architecturally distinct** — `assigned_agent_category`
maps exclusively to the Agent Registry's 5 agent-package categories
(`research-agent`, `coding-agent`, `qa-agent`, `architect-agent`, `documentation-agent`),
never to capability-engine's own `category` field. This is a naming-hygiene
recommendation for implementation time (§26), not an architectural fork — no document
conflates the two incorrectly, but future field-naming should be deliberate about the
collision.

---

## 13. Model access

**TDD 3C names no dependency on `ai-model-orchestration-engine` anywhere, and does not
cite ADR-020.** Confirmed by direct grep of the full TDD text for
`ADR-020|ai-model-orchestration|ai_model_orchestration|model access|AI model` — zero
matches. No client, no port, no event, no mention.

This is consistent with, though never explicitly justified by citing, Bible Part 15's
own architectural requirement (`part-15-capability-engine.md:631`, "ARCHITECTURAL
REQUIREMENTS"): "The Capability Engine must remain independent from the AI model." TDD
3C never quotes this line even though its silence is fully consistent with it — a
missed citation opportunity, not a contradiction.

This is the opposite of sibling engine 3B (`planning-engine`), which does depend on
`ai-model-orchestration-engine` via ADR-020 for decomposition (confirmed:
`services/planning-engine/README.md`'s own description of `ModelOrchestrationPort`/`ai_model.generate.request`).
Among the three new Phase 3 engines, **capability-engine is the one with zero AI-model
dependency** — matching Bible Part 15's stated intent even though TDD 3C never says so
explicitly.

ADR-032 is the only ADR TDD 3C cites at all, and only to explicitly **exclude**
capability-engine from its binding scope (§17 below) — not an ai-model relationship.

**Direct implication for implementation:** capability-engine needs no
`ModelOrchestrationPort`, no `ModelOrchestrationClient`, and should be added to the
ADR-020 import-linter contract's forbidden list (§12) precisely because it has nothing
to import there — the contract exists to make the absence structural, not merely
documented.

---

## 14. Idempotency

**TDD 3C contains no dedicated idempotency section and never uses the words
"idempotent"/"idempotency" anywhere** — confirmed by direct grep, zero matches.

This is a notable silent gap given: (a) TDD 3C documents no consumed events at all
(§5), which may make the topic genuinely moot for event-driven idempotency as currently
scoped; but (b) `POST /v1/capabilities/install` is a mutating, presumably-retriable
REST endpoint, and the append-only `capability_installation_event` log (§10) has no
stated duplicate-delivery/duplicate-call handling; and (c) sibling documents in this
same package do discuss it explicitly — e.g. planning-engine's own Gate Review flags
"No persistence-backed idempotency for `reasoning.process.completed`... becomes a hard
requirement once persistence exists" as a known limitation, showing this project does
treat idempotency as a first-class concern once persistence is real.

In Phase 3's actual realistic call pattern, the only caller of `POST /v1/capabilities/install`
is capability-engine's own bootstrap/seed logic at first boot (§9.3) — there is no
external marketplace and no third-party install path yet. The open question is
therefore narrower than "general API idempotency": what happens if the bootstrap call
runs twice (e.g., on a service restart after a partial install, or a redeploy)? Does a
second `POST` for an already-installed `(name, version)` pair error, no-op, or attempt
a duplicate pipeline run? **This is treated as Fork 3C-4 in §22**, since the available
options have materially different persistence-schema and API-contract shapes.

---

## 15. Retry/failure semantics

Full failure/degraded-behavior table, `06-tdd-3c-capability-engine.md:229-234` (§8),
verbatim:

| Condition | Behavior |
|---|---|
| Sandbox test fails during install | Capability never reaches Registration/Activation — pipeline halts, recorded in `capability_installation_event`, no partial registration. |
| A registered capability's adapter fails at invocation time (e.g., git command exits non-zero) | Structured failure returned to the caller (agent or `action-engine`) — capability-engine itself never retries silently; retry policy is the caller's own concern (mirrors `action-engine`'s own `RetryPolicy` field, TDD 3D). |
| Sandboxing scope violation attempted | Hard refusal at the adapter boundary, logged, `health_status` unaffected (a blocked attempt is not evidence of an unhealthy capability) — never silent partial-execution. |
| Postgres unavailable | Registry reads fail loudly; no capability is invokable without a confirmed-healthy registry entry. |

Retry is explicitly the **caller's** responsibility (`action-engine`'s own
`RetryPolicy`, per TDD 3D), never capability-engine's own concern once an adapter call
fails — a clean, disclosed ownership boundary. No retry policy is described for the
install pipeline itself (distinct from adapter-invocation retries) — this is folded
into the idempotency gap above (Fork 3C-4).

---

## 16. Observability

`06-tdd-3c-capability-engine.md:238-246` (§9), verbatim:

> "- `capability_install_pipeline_stage_total{stage=...}` (counter, one label per of
> the 8 stages).
> - `capability_sandbox_violation_blocked_total{adapter=...}` (counter) — the direct
> metric proving the roadmap's own acceptance bar.
> - `capability_invocation_total{adapter=..., outcome=...}` (counter).
> - `capability_invocation_duration_ms` (histogram, per adapter).
> - Standard health/readiness/metrics via `nova-service-kit`, unmodified."

Confirmed by grep: none of these four metric names appear anywhere else in the
repository — entirely novel to this TDD, not reused from any existing engine's metric
set. `capability_sandbox_violation_blocked_total` is the direct proof metric for the
roadmap's own Phase 3C acceptance bar (`ENGINEERING_ROADMAP.md:536`: "no capability can
escape its declared permission scope").

---

## 17. Security/privacy

`06-tdd-3c-capability-engine.md:250-262` (§10), verbatim:

> "This TDD **is** a security-boundary-defining TDD — §3's sandboxing mechanisms are
> the enforced boundary. `required_permissions` reuses the established
> `PermissionGrant`/`PermissionAction` shape referenced in
> `docs/architecture/13-auth-and-security.md:45-66` conceptually, though `nova-auth`
> itself does not exist yet... so Phase 3's permission checks are necessarily
> local/self-contained, consistent with the same conclusion already reached for
> `action-engine` (TDD 3D §7). ADR-032 does not bind `capability-engine` directly (it
> binds privileged-capability-*gating* engines — `action-engine`, `autonomy-engine` —
> not the registry that catalogs what exists)."

Every factual claim independently verified:
- `13-auth-and-security.md:45-66` does contain `PermissionGrant` (§4, exact field
  match: `principal`, `resource_scope`, `actions: set[PermissionAction]`,
  `autonomy_ceiling`, `granted_by`, `expires_at`).
- `services/nova-auth` genuinely does not exist.
- The placeholder comment is real at the exact cited line:
  `services/nova-core/src/nova_core/domain/boot.py:85` — "# placeholders until
  nova-auth exists (Roadmap Phase 2/7)." (citation drops the `domain/` path segment,
  line number exact).
- ADR-032's own scope (`docs/architecture/adr/ADR-032-identity-confidence-is-also-an-authorization-signal.md:3-6`)
  binds "Action Engine (Phase 3/NAOS), Autonomy Engine (Phase 4)" — capability-engine
  (the registry) is not named as bound, consistent with TDD 3C's reading.

**ADR-032's gate is entirely about identity confidence** (from `perception-engine` via
`world-model-engine`'s `present_identities`), checked by `action-engine`'s own
`IdentityPort` at Action-Principle-lifecycle stage 3 ("Check Permissions") — an
architecturally separate mechanism from capability resolution at stage 5. The word
"capability" in ADR-032's own prose ("binding on every future engine that gates a
privileged capability") is generic security vocabulary, not a reference to Phase 3C's
`Capability` object. TDD 3C's own document explicitly disclaims being what ADR-032
binds, and this is corroborated independently by TDD 3D's own ADR-032 section
(`07-tdd-3d-action-engine.md:218-245`), which implements the identity-confidence gate
entirely within `action-engine`, never invoking capability-engine for it. This overlap
of the English word "capability" between ADR-032's generic vocabulary and Phase 3C's
domain-object name is a naming collision the docs are already aware of and resolve
explicitly — not an open question.

No privacy-specific concerns are documented (capability-engine handles no user PII by
design — its data is entirely about installed software capabilities, not user data).

---

## 18. Phase 3D dependencies

**TDD 3D (`action-engine`) affirmatively, explicitly depends on capability-engine** —
not symmetric with TDD 3C's own "no dependency on 3B" framing. `07-tdd-3d-action-engine.md:15-17`
(§0 Dependencies):

> "**Dependencies.** `capability-engine` (`3C`) — per the roadmap's own stated reason,
> *"depends on capabilities existing to execute against"* (`ENGINEERING_ROADMAP.md:528`),
> sharpened by Fork 3C-1/3D-1 (§2)."

**Field-level consumption** (full detail in §7's table): `health_status` (stage 5,
gates whether execution is attempted at all) and `execution_adapter` (stage 6, the
actual invocation mechanism) are the two hard, field-level dependencies. `CapabilityPort`
itself is defined by `action-engine`, not capability-engine (§7).

**The single most concrete piece of downstream contract-churn evidence in the whole
corpus:** `07-tdd-3d-action-engine.md:47-57` (§2):

> "**A concrete coordination consequence, disclosed here rather than invented
> silently:** `action-engine`'s Rollback Strategy (§4) requires some destructive
> filesystem/terminal operations to be reversible... If Fork 3C-1 resolves to Option A
> (shared adapters), `capability-engine`'s filesystem adapter must support a
> pre-operation snapshot/backup primitive for destructive calls — a requirement on TDD
> 3C's own adapter design that TDD 3C's document (§3) does not currently specify, since
> it was written before this dependency was traced. **This must be reconciled between
> the two TDDs before either begins implementation.**"

This is TDD 3D stating, in its own words, that TDD 3C's filesystem adapter design is
currently incomplete relative to what 3D needs. **Treated as Fork 3C-3 in §22.**

**`input_schema` ambiguity** (traced in TDD 3D, bears on a 3C-owned field):
`07-tdd-3d-action-engine.md:200` (stage 2, "Validate — schema/parameter validation
against `input_schema`") never states whose `input_schema` — `Action.parameters`'s own
schema, or the target `Capability.input_schema`? The pipeline ordering (Validate at
stage 2, Capability first resolved at stage 5) makes the latter reading structurally
awkward without further explanation the document never gives. **Not elevated to a
Phase-3C fork** (see §22's reasoning) since its resolution is internal to TDD 3D's own
stage sequencing and does not require capability-engine's own architecture to change —
recorded here as a heads-up for Phase 3D's own future pre-implementation research.

**Sequencing discrepancy between the two TDDs' own acceptance criteria:** TDD 3C's
acceptance criterion 5 (`06-tdd-3c-capability-engine.md:330-332`) states the Fork
3C-1/3D-1 gate blocks only "`action-engine` (TDD 3D) implementation," while TDD 3D's
own acceptance criterion 6 (`07-tdd-3d-action-engine.md:357-358`) states it must be
reconciled "before **either** implementation begins." Two different claims about the
same gate's scope, worded inconsistently between the two TDDs that jointly own it —
flagged for whoever sequences Phase 3C's actual implementation kickoff (§26).

**No `TaskNode`/`TaskGraph` dependency**: TDD 3D never mentions either type anywhere
(confirmed by exhaustive grep) — action-engine's document contains no reasoning
connecting `assigned_agent_category` to anything; it is entirely silent on Task Graphs.

---

## 19. Phase 3E dependencies

**TDD 3E (`agent-os`) also affirmatively depends on capability-engine** —
`08-tdd-3e-agent-os.md:19-22` (§0 Dependencies): "`3C` (`capability-engine` —
capabilities to grant agents)... All three must exist first; this TDD is the last of
the five engine slices by design."

**The load-bearing, unresolved gap: `AgentContext.granted_capabilities` population.**
TDD 3C hedges (`06-tdd-3c-capability-engine.md:181-185`): "`CapabilityPort` is not
defined by `capability-engine` itself... it is defined by `action-engine`... and
**potentially** by `agent-os/kernel` (TDD 3E, for populating
`AgentContext.granted_capabilities`)." The word "potentially" is a hedge, not a
commitment. **TDD 3E never resolves this hedge — the literal string
`granted_capabilities` does not appear anywhere in `08-tdd-3e-agent-os.md`**, confirmed
by exhaustive grep. The Kernel Scheduler's own 4-step dispatch sequence
(`08-tdd-3e-agent-os.md:122-131`, quoted in full in §4 above) never mentions
capability-engine at all. **Treated as Fork 3C-2 in §22.**

**`assigned_agent_category` maps exclusively to the Agent Registry, never to
capability-engine.** `08-tdd-3e-agent-os.md:121-131` (§4, Kernel Scheduler, quoted in
full in §4 above): step 1 is "query Registry for healthy candidates in
`assigned_agent_category`" — this Registry is the **Agent** Registry
(`agent_package` table keyed on `(category, version)`, `08-tdd-3e-agent-os.md:149-166`,
§5), confirmed against its own authoritative source
(`12-agent-architecture.md:229-232`). No document anywhere states that
`assigned_agent_category` values are expected to map to registered *capabilities* — the
two are architecturally distinct namespaces that happen to share the English word
"category" (§12's naming-collision note applies here too).

**The `http` capability gap:** TDD 3E's five-agent behavior table
(`08-tdd-3e-agent-os.md:293-299`, quoted in full in §6) never has any of the five
Phase-3 agents (`coding-agent`, `qa-agent`, `documentation-agent`,
`research-agent`, `architect-agent`) use the `http` capability — one of TDD 3C's four
built-ins. Unexplained by either document. Recorded as a finding, not elevated to fork
status (no architectural ambiguity is implied — it reads as an oversight or a
deliberately-narrow first agent-behavior set, not a design choice requiring the user's
input).

**Sandbox-testing precedent reuse, confirmed positive:** TDD 3E's own Agent Registry
install pipeline explicitly reuses Fork E3's already-approved depth decision rather
than inventing a new one — `08-tdd-3e-agent-os.md:151-158`: "'Sandbox test run' for an
agent reuses Fork E3's lighter OS-level scoping discipline — no new isolation
technology beyond what TDD 3C already established for capabilities." This is
corroborating evidence that Fork E3's resolution is being treated as stable,
already-decided precedent across multiple Phase 3 TDDs, reinforcing §9.4's conclusion
that the sandboxing *depth* question is not open.

**"Independently-buildable" nuance:** TDD 3E's own opening framing
(`08-tdd-3e-agent-os.md:5-7`) calls 3B/3C/3D "independently-buildable" — this means
independent *of 3E*, not independent *of each other*. TDD 3D's own §0 explicitly names
capability-engine as a real dependency, so reading "independently-buildable" as "3C and
3D have no dependency on each other" would misread this sentence against TDD 3D's own
explicit text.

---

## 20. Testing strategy

`06-tdd-3c-capability-engine.md:294-316` (§12), verbatim:

> "**Unit (fake-backed):** all 8 installation-pipeline stages, including failure at
> each stage (sandbox-test-fails halts correctly, etc.). Sandboxing-scope-violation
> unit tests for each of the 4 adapters (path-prefix escape attempt,
> executable-not-on-allow-list attempt, host-not-on-allow-list attempt) — these are the
> direct proof of the roadmap's acceptance bar and must be adversarial, not just
> happy-path.
>
> **Contract:** payload round-trip tests for whatever `nova-contracts` additions land
> (§11).
>
> **Integration:** full install-to-invoke round trip for each of the 4 built-in
> capabilities against a real (but throwaway/sandboxed) git repo, filesystem temp
> directory, subprocess, and a loopback HTTP endpoint.
>
> **Real-infrastructure:** real-Postgres persistence test for the registry and the
> append-only installation-event log; a real (not mocked) subprocess/filesystem/git
> sandbox-violation test proving the OS-level scoping actually blocks an escape attempt
> in a real process, not just in a fake port's simulated logic — this specific test
> class cannot be meaningfully faked, since the property being proven is about real
> OS-level enforcement."

This refines the two-tier testing convention already established for all Phase 3
engines in `01-tdd-preparation-and-fork-resolutions.md §8`
(`:735`): "**3C** | Registry logic, permission-scope-boundary unit tests. | Sandboxed
execution test proving no capability escapes its declared scope
(`ENGINEERING_ROADMAP.md:536`) needs a real (lightweight) sandboxed process, not a
fake."

Acceptance criteria, `06-tdd-3c-capability-engine.md:320-332` (§13), verbatim:

> "1. All four built-in capabilities install successfully through the real 8-stage
> pipeline at first boot.
> 2. A scripted sandbox-escape attempt for each adapter is blocked and logged, never
> silently succeeds.
> 3. `DELETE /v1/capabilities/{id}` reverses an install cleanly (Bible's own 'every
> installation should be reversible' requirement, `part-15-capability-engine.md:275`).
> 4. Registry state survives a real-Postgres restart simulation unchanged.
> 5. Fork 3C-1/3D-1 is resolved (by the user) before `action-engine` (TDD 3D)
> implementation begins, since `action-engine`'s own adapter design depends on the
> answer."

**Alignment with this project's actual testing pyramid**
(`docs/architecture/16-testing-strategy.md`: Unit → Integration (fake-backed,
PR-gating) → Real-infrastructure (opt-in) → Contract → E2E, 85% domain coverage gate):
fully consistent — TDD 3C's own four tiers map directly onto the established pyramid,
and its explicit call-out that the sandbox-violation real-infra test "cannot be
meaningfully faked" matches this project's own standing distinction between real and
fake-backed verification tiers (the same distinction this session has been careful to
maintain throughout Phase 3B's own Gate Reviews).

---

## 21. Infrastructure requirements

Not yet built, all confirmed absent from the current repo state:

- `services/capability-engine` scaffold (via `tools/scaffold-engine.py`, same tooling
  already proven for `planning-engine`).
- `infra/docker/docker-compose.local.yml` entry (confirmed absent by grep).
- `.github/workflows/build-and-scan.yml` matrix entry (TDD 3C's own §11 acknowledges
  this as standard not-yet-done work, `:281-282`).
- `pyproject.toml` registration: `root_packages`, the ADR-004 independence contract's
  `modules`, the ADR-006/ADR-007 contracts' `source_modules` — all auto-handled by
  `scaffold-engine.py` per its own comment. **The ADR-020 contract's `source_modules`
  is NOT auto-handled** (confirmed gap, §12) and needs the same manual registration
  step planning-engine required in PR #7.
- `capability` Postgres schema + Alembic migration for the two tables (§10).
- No new shared package or SDK is anticipated — capability-engine's sandboxing
  mechanisms (§9.4) are adapter-internal (`asyncio.create_subprocess_exec`, path/host
  allow-lists), not a new infrastructure dependency like a container runtime; this is
  the direct, disclosed consequence of Fork E3's already-approved lighter-scoping
  decision (§9.4) — no gVisor/Firecracker/container infrastructure is required in Phase
  3.

---

## 22. Architectural forks

**Before listing forks: an explicit statement on what this pass did NOT find to be a
fork, correcting a preliminary hypothesis raised earlier in this session.** The
apparent tension between `docs/architecture/12-agent-architecture.md`'s execution-backend
table (`container` = Phase 7+) and the roadmap's Phase-3 "sandboxed capability
execution tests" line is **not** an open architectural fork. It is already resolved by
Fork E3 (`01-tdd-preparation-and-fork-resolutions.md:236-269`, "User decision: Option
A" — lighter OS-level scoping), and TDD 3C's own §3/§14 are explicitly self-aware of
and distinguish themselves from the container-grade language (§9.4 above has the full
citation trail). This does not require the user's judgment again; it is reported here
only to correct the record, not as a fork.

Four items below meet the bar of "ambiguity requiring a choice between materially
different architectures, with real consequences for contracts/testing/infrastructure."
Each follows the required 14-point structure. None are resolved here — all require
explicit approval before Phase 3C implementation begins.

### Fork 3C-1 / 3D-1 — Capability adapter ownership (already named by TDD 3C/3D; independently re-verified here, not re-decided)

1. **Evidence.** The roadmap names overlapping adapter categories for both engines:
   capability-engine gets "a first batch of built-in capabilities (git, filesystem,
   terminal, HTTP)" (`ENGINEERING_ROADMAP.md:516`); action-engine gets "terminal +
   filesystem + git adapters" (`:515`). No document states whether these are the same
   underlying adapter code or two independent implementations.
2. **Relevant files.** `06-tdd-3c-capability-engine.md:143-176` (§4, "Open
   architectural forks"); `07-tdd-3d-action-engine.md:36-57` (§2); `ENGINEERING_ROADMAP.md:515-516`;
   `01-tdd-preparation-and-fork-resolutions.md` (ownership-boundary precedent cited by
   both TDDs).
3. **Exact ambiguity.** Does capability-engine own the one real implementation of
   each git/filesystem/terminal/HTTP adapter, consumed by action-engine through a port
   — or does each engine implement and own its own separate adapter code for the same
   three overlapping targets (git/filesystem/terminal)?
4. **Why the current architecture is insufficient to resolve this silently.** Building
   either engine's adapter layer first commits real code to one of two materially
   different shapes: a single shared implementation behind a port (Option A) versus two
   independent, potentially divergent implementations of "how to run git" (Option B).
   Reversing this after implementation means either a real migration (moving adapter
   code from action-engine into capability-engine, or vice versa) or living with
   duplicated, possibly-inconsistent sandboxing logic in two places — exactly the class
   of decision this project's standing rule requires surfacing before either engine's
   implementation starts.
5. **Options.**
   - **Option A (recommended by both TDD 3C and TDD 3D).** Capability-engine owns the
     one real adapter implementation per target. Action-engine defines its own
     `CapabilityPort` (own Protocol, own client, mirroring the `GoalsPort`/`DigitalTwinPort`
     per-calling-engine convention) and consumes capability-engine's registered
     capabilities.
   - **Option B.** Each engine implements and owns its own separate adapters.
6. **Existing precedent per option.**
   - Option A: the `GoalsPort`/`DigitalTwinPort` pattern is real, shipped precedent —
     `communication-engine` already defines its own Protocol ports and consumes another
     engine's capabilities this way (per TDD 3C's own citation,
     `06-tdd-3c-capability-engine.md:169-171`, and `01-tdd-preparation-and-fork-resolutions.md`'s
     "Capability Engine owns reusable building blocks only, consumed by both [Planning
     and Action]" framing). Bible Part 15's own `execution_adapter` field is written as
     if it's the actual, singular invocation mechanism, not a per-consumer copy.
   - Option B: matches the roadmap's literal per-engine phrasing more directly (each
     deliverables bullet lists its own adapters), but no engine in this codebase
     currently duplicates another engine's adapter/connector logic this way — there is
     no existing precedent for it in the shipped code.
7. **Advantages.**
   - Option A: single sandboxing implementation to audit and harden (the
     `capability_sandbox_violation_blocked_total` metric and its adversarial tests
     cover both callers at once); no risk of the two engines' scoping rules silently
     drifting apart; matches the "reusable building block" framing Bible Part 15 itself
     uses for the Capability Engine's raison d'être.
   - Option B: each engine's adapter can be tuned to its own exact needs without a
     shared-port abstraction; no cross-engine coupling on adapter internals; slightly
     simpler to reason about locally (action-engine doesn't need to trust
     capability-engine's health/adapter state for its own core execution path).
8. **Disadvantages.**
   - Option A: action-engine's execution path now has a real runtime dependency on
     capability-engine being up and its registry entries healthy (`health_status="healthy"` gate)
     — a new availability coupling that doesn't exist under Option B; the shared-adapter
     interface must satisfy both engines' needs (e.g., 3D's rollback requirement, Fork
     3C-3 below), which can pull capability-engine's design in directions it wouldn't
     otherwise need.
   - Option B: duplicated OS-interaction/sandboxing code in two places — a bug fixed in
     one adapter (e.g., a path-traversal escape) doesn't automatically fix the other;
     doubles the adversarial-test surface area required for the same acceptance bar;
     contradicts Bible Part 15's own framing of capabilities as the reusable building
     block.
9. **Impact on Phase 3C.** Determines whether capability-engine's adapters must be
   designed as a genuinely reusable, externally-callable library/port target (Option A)
   or can remain purely internal to capability-engine's own install/invoke flow
   (Option B minimizes cross-engine design pressure on 3C, at the cost of duplication
   elsewhere).
10. **Impact on Phase 3D.** Determines whether action-engine writes any adapter code
    at all (Option A: no, it only writes the risk/approval/rollback/audit wrapper) or
    writes and owns a second, independent git/filesystem/terminal implementation
    (Option B).
11. **Impact on Phase 3E.** Indirect only — agent-os never calls adapters directly in
    either option; it dispatches to action-engine, which is the actual adapter caller.
12. **Impact on contracts.** Option A requires `CapabilityPort` (3D-owned) to be a
    stable, versioned-per-ADR-024 contract from the start, since a second real caller
    depends on it immediately; Option B requires no shared contract at all, at the cost
    of two independent adapter APIs that could diverge without any contract enforcing
    parity.
13. **Impact on testing.** Option A: one adversarial sandbox-violation test suite,
    exercised by both capability-engine's own tests and action-engine's integration
    tests against the same adapter. Option B: two independent adversarial test suites,
    doubling the surface that must be kept adversarially rigorous over time.
14. **Impact on infrastructure.** Option A: no new infrastructure, but action-engine's
    deployment now has a hard runtime dependency on capability-engine's availability.
    Option B: no cross-engine runtime dependency, but two services each need their own
    sandboxing-relevant OS permissions/configuration (allow-lists, subprocess
    execution rights) configured and kept in sync operationally.

**Recommendation.** Option A, matching both TDD 3C's and TDD 3D's own stated
recommendation and this project's established building-block precedent — presented as
a recommendation, not a decision. **Status: explicitly unresolved.** TDD 3C's own §13
acceptance criterion 5 and TDD 3D's own §14 acceptance criterion 6 additionally
disagree on whether this gate blocks only 3D's implementation start or both 3C's and
3D's (§18) — that discrepancy should be resolved in the same approval pass as the fork
itself.

### Fork 3C-2 — `AgentContext.granted_capabilities` population mechanism and timing

1. **Evidence.** `AgentContext.granted_capabilities: list[CapabilityHandle]`
   (`12-agent-architecture.md:135`) is a real, named field with no populating mechanism
   specified anywhere. TDD 3C hedges: "potentially... `agent-os/kernel`"
   (`06-tdd-3c-capability-engine.md:184-185`). TDD 3E's Kernel Scheduler (the only
   plausible "kernel" the hedge could mean) never mentions `granted_capabilities` or
   capability-engine anywhere in its own dispatch-sequence description
   (`08-tdd-3e-agent-os.md:121-131`).
2. **Relevant files.** `docs/architecture/12-agent-architecture.md:128-136` (field
   definition); `06-tdd-3c-capability-engine.md:181-185` (the hedge); `08-tdd-3e-agent-os.md:121-131`
   (Kernel Scheduler dispatch sequence, silent on this field); `07-tdd-3d-action-engine.md:199-206`
   (stage 5, where capability resolution actually, verifiably happens today).
3. **Exact ambiguity.** Who resolves "which capabilities can this agent instance use"
   and when: (a) `agent-os`'s Kernel Scheduler, eagerly, at dispatch time, before the
   agent starts running; (b) a static declaration baked into the Agent Package manifest
   at agent-install time (TDD 3E's own Agent Registry install pipeline already has a
   "Dependency/capability resolution" stage, `08-tdd-3e-agent-os.md:151-158`, though
   confirmed structurally distinct from capability-engine's registry — see §19); or (c)
   nobody eagerly populates a real list at all, and `AgentContext.granted_capabilities`
   is either a coarse permission/name list resolved lazily, per-call, by action-engine's
   already-real stage-5 `CapabilityPort` resolution (§4/§18) — making the field
   effectively redundant with what action-engine already does.
4. **Why the current architecture is insufficient to resolve this silently.** This
   determines whether capability-engine needs a new, currently-undesigned query surface
   (e.g., "list capabilities eligible for agent category X") consumed by agent-os, or
   needs nothing beyond its already-planned 3 REST verbs because action-engine's
   existing stage-5 resolution is the only real capability lookup that ever happens.
   Building agent-os's dispatch loop without deciding this either invents an
   undocumented new capability-engine API surface on the fly during 3E's
   implementation, or ships `AgentContext.granted_capabilities` as permanently empty/unused
   dead weight — both are architecture-shaping outcomes a fork analysis exists to catch
   before they happen silently.
5. **Options.**
   - **Option A.** `agent-os`'s Kernel Scheduler queries capability-engine (via a new
     port/API) at dispatch time and eagerly populates `AgentContext.granted_capabilities`
     with resolved `CapabilityHandle`s before the agent instance starts running.
   - **Option B.** Capability grants are static, declared as part of the Agent Package
     manifest (consumed during the Agent Registry's own install pipeline, TDD 3E §5),
     resolved once at agent-package install time, not re-resolved per dispatch.
   - **Option C.** `AgentContext.granted_capabilities` is populated with only
     lightweight, pre-known identifiers (e.g., capability names an agent package
     declares it needs) with no live health/adapter resolution at dispatch time;
     the actual, authoritative resolution against capability-engine's live registry
     continues to happen exactly where it already does today — action-engine's stage 5
     — making the `AgentContext` field a declared-intent list, not a resolved-capability
     list.
6. **Existing precedent per option.**
   - Option A: no direct precedent in this codebase yet, but it is the shape doc 12's
     field name (`granted_capabilities`, past participle — implying something has
     already been granted by the time the agent has it) most naturally suggests.
   - Option B: real precedent exists — TDD 3E's own Agent Registry install pipeline
     already performs a "Dependency/capability resolution" step at package-install time
     (`08-tdd-3e-agent-os.md:151-158`), so extending it to also resolve/declare
     capability grants at the same point reuses an already-planned pipeline stage
     rather than inventing a new dispatch-time mechanism.
   - Option C: matches what is *already true* in the current document set today —
     action-engine's stage 5 is the only place any real `CapabilityPort` resolution is
     documented to happen (§4/§18) — so Option C is closest to "formalize the status
     quo" rather than "design something new."
7. **Advantages.**
   - Option A: capabilities are always resolved against the live, current registry
     state at the moment they matter (dispatch), so a capability that became unhealthy
     between agent-install and dispatch is caught before the agent even starts.
   - Option B: no new dispatch-time dependency on capability-engine's availability;
     Kernel Scheduler's dispatch loop stays exactly as documented today (§4/§19),
     unmodified.
   - Option C: requires the least new design — `AgentContext.granted_capabilities`
     becomes a thin, cheap-to-populate list; avoids two independent resolution paths
     (dispatch-time and stage-5) ever disagreeing with each other, since there would
     only be one real resolution point (stage 5).
8. **Disadvantages.**
   - Option A: adds a new capability-engine query surface that doesn't exist in any
     current document, and a new runtime dependency from agent-os onto capability-engine
     at dispatch time (on top of the one Fork 3C-1 may already add to action-engine).
   - Option B: capability grants can go stale between agent-package install and any
     individual dispatch (an agent could be dispatched with a `CapabilityHandle` for a
     capability that has since become unhealthy or been removed, only to fail later at
     action-engine's stage 5 anyway) — so this option doesn't actually eliminate the
     need for stage-5's live check, making the eager grant partly redundant.
   - Option C: `AgentContext.granted_capabilities: list[CapabilityHandle]`'s own field
     type (`CapabilityHandle`, not a bare string) implies something more resolved than
     a declared-intent list — this option would read as under-using the type doc 12
     already committed to, or would require doc 12's field type itself to be revisited.
9. **Impact on Phase 3C.** Option A requires a new capability-engine API/port beyond
   the 3 REST verbs already scoped; Options B/C require nothing new from
   capability-engine's own surface — its existing `GET /v1/capabilities` plus
   stage-5's existing `CapabilityPort` are sufficient either way.
10. **Impact on Phase 3D.** None of the three options change action-engine's own
    stage-5 behavior — it continues to resolve `Capability` via its own `CapabilityPort`
    regardless. Options A/B would make `AgentContext.granted_capabilities` an
    additional, earlier signal action-engine could optionally cross-check against, but
    none of the current documents describe action-engine doing so.
11. **Impact on Phase 3E.** Directly determines a piece of the Kernel Scheduler's own
    dispatch-sequence design (§4/§19) that TDD 3E's current text is silent on — whichever
    option is chosen becomes a concrete addition to TDD 3E's own §4/§6 at
    implementation time.
12. **Impact on contracts.** Option A is the only one requiring a new
    `nova_contracts` type/port beyond what TDD 3C already scopes (some
    capability-query request/reply shape consumed by agent-os). Options B/C need no
    new contract beyond `CapabilityHandle` itself.
13. **Impact on testing.** Option A adds a new integration-test surface (agent-os
    ↔ capability-engine, dispatch-time). Options B/C keep the current, already-planned
    test surface (capability-engine's own pipeline tests, action-engine's stage-5
    tests) unchanged.
14. **Impact on infrastructure.** Option A implies agent-os's own service needs a
    capability-engine client/port wired into its runtime dependencies at dispatch time
    — a new operational coupling not currently documented anywhere for `agent-os`.
    Options B/C add no new infrastructure dependency.

**Recommendation.** No option is recommended here — this fork's evidence is genuinely
balanced (each option resolves the hedge differently, and TDD 3E's complete silence on
`granted_capabilities` means there is no existing textual lean to defer to, unlike Fork
3C-1 where both TDDs already state a preference). This is presented as a clean
three-way choice for explicit resolution, likely properly owned by whichever TDD is
revised first between 3C and 3E — flagged, not silently chosen.

### Fork 3C-3 — Rollback/snapshot primitive ownership for destructive capability operations

1. **Evidence.** TDD 3D states, in its own words, that its Rollback Strategy requires
   "some destructive filesystem/terminal operations to be reversible," and that if Fork
   3C-1 resolves to Option A, "`capability-engine`'s filesystem adapter must support a
   pre-operation snapshot/backup primitive for destructive calls — a requirement on TDD
   3C's own adapter design that TDD 3C's document (§3) does not currently specify,
   since it was written before this dependency was traced"
   (`07-tdd-3d-action-engine.md:47-57`).
2. **Relevant files.** `07-tdd-3d-action-engine.md:47-57` (§2, the disclosed
   requirement); `06-tdd-3c-capability-engine.md:117-137` (§3, the current, silent-on-this
   sandboxing/adapter design); TDD 3D's own Rollback Strategy section (§4, referenced
   but not fully quoted by the downstream research pass — worth a direct read at
   implementation time).
3. **Exact ambiguity.** Where does pre-operation-snapshot/rollback capability for
   destructive filesystem/terminal operations live: inside capability-engine's own
   filesystem adapter (as a first-class primitive every caller gets for free), or
   entirely inside action-engine's own Rollback Strategy machinery (capturing state
   itself, outside of and without needing anything new from capability-engine's
   adapter), or is automated rollback simply out of scope for Phase 3 entirely (contradicting
   TDD 3D's stated Rollback Strategy, but potentially defensible if that strategy is
   over-scoped for what Phase 3's actual acceptance bar requires)?
4. **Why the current architecture is insufficient to resolve this silently.** This
   changes the actual public shape of capability-engine's filesystem adapter / the
   `CapabilityPort` interface — a materially different contract depending on which
   option is chosen (an adapter with a snapshot/restore method vs. one without). Since
   Fork 3C-1's Option A (capability-engine owns the one real adapter) is the
   recommended path for that separate fork, this requirement, if accepted, becomes a
   capability-engine-side implementation obligation that TDD 3C's document does not
   currently carry at all — implementing capability-engine's adapters without deciding
   this risks shipping an adapter surface TDD 3D cannot actually build a working
   Rollback Strategy against, forcing a breaking adapter-interface change later.
5. **Options.**
   - **Option A.** Capability-engine's filesystem (and, by extension, terminal/git)
     adapter itself implements a snapshot/backup primitive, exposed as part of the
     adapter's own interface (e.g., a `snapshot()`/`restore()` pair or an
     opt-in "reversible mode" flag on destructive calls), callable by any consumer
     (not just action-engine).
   - **Option B.** Action-engine owns all rollback logic itself, entirely outside
     capability-engine — e.g., action-engine captures its own pre-state (via
     capability-engine's existing, ordinary read/list operations) before invoking a
     destructive call, and restores it itself on failure, without requiring
     capability-engine's adapter to expose anything beyond what TDD 3C's document
     (§3) already specifies.
   - **Option C.** No automated rollback in Phase 3 for capability-invoked destructive
     operations — TDD 3D's Rollback Strategy is scoped down to non-capability-mediated
     actions only (or deferred), and this requirement is removed from TDD 3D's own
     acceptance bar rather than imposed on TDD 3C.
6. **Existing precedent per option.**
   - Option A: no direct precedent in this codebase; would be a genuinely new pattern
     for how an adapter-owning engine exposes safety primitives to its consumers.
   - Option B: consistent with the general ownership boundary Fork 3C-1 itself already
     recommends — "`action-engine`'s own contribution is the risk/approval/rollback/audit
     wrapper around an invocation, not a second copy of 'how to run git'"
     (`06-tdd-3c-capability-engine.md:157-160`) — i.e., rollback is explicitly named as
     action-engine's own wrapper responsibility in the very same sentence that
     recommends Option A for adapter ownership, suggesting the TDD's own authors may
     have already been leaning toward Option B without stating it as the resolution to
     this specific, later-discovered gap.
   - Option C: no direct precedent, but this project has a standing pattern of
     deferring genuinely hard sub-problems explicitly (e.g., Bible's marketplace vision
     deferred to Phase 8+) rather than under-building them silently — Option C would be
     in that same spirit if adopted deliberately, not as a silent drop.
7. **Advantages.**
   - Option A: every capability-engine consumer (not just action-engine) gets safe,
     reversible destructive operations for free — a genuinely reusable building block,
     consistent with Bible Part 15's own framing.
   - Option B: keeps capability-engine's adapter surface exactly as already scoped in
     TDD 3C §3 (no design changes needed there at all); matches the ownership-boundary
     sentence already in TDD 3C's own text (quoted above); action-engine's Rollback
     Strategy can be tuned precisely to its own risk-tiering needs without needing
     capability-engine to anticipate them.
   - Option C: simplest to implement short-term; avoids committing to a rollback
     design neither TDD has actually thought through yet (TDD 3C's document, by its own
     admission, was written before this need was even discovered).
8. **Disadvantages.**
   - Option A: capability-engine's adapter design grows scope specifically to serve
     one downstream consumer's need (action-engine's Rollback Strategy), which is in
     some tension with capability-engine's own documented independence
     (§13's "no ai-model dependency," and more generally its framing as a
     self-contained registry/pipeline service, §0's "no direct technical dependency" on
     3B) — a precedent where 3D's requirements start shaping 3C's own domain model.
   - Option B: action-engine must implement its own snapshot/restore logic using only
     capability-engine's ordinary (non-destructive) read operations, which may be less
     reliable or more complex than a purpose-built primitive inside the adapter that
     actually performs the destructive call (e.g., a race between action-engine's
     "read current state" call and its own subsequent "perform destructive call" is
     possible under Option B in a way it would not be under an atomic-adapter-level
     Option A).
   - Option C: directly contradicts the roadmap's own Phase 3 acceptance criterion
     ("A deliberately risky action... is blocked pending approval... and proceeds only
     after approval," `ENGINEERING_ROADMAP.md:542-546`) if read to require actual
     recoverability, not merely gated approval — would need explicit, deliberate
     rescoping of that acceptance bar, not a quiet omission.
9. **Impact on Phase 3C.** Option A adds a new, currently-unscoped capability to
   capability-engine's filesystem/terminal/git adapters and to its `CapabilityPort`
   contract surface. Options B/C require no change to TDD 3C's current adapter scope
   at all.
10. **Impact on Phase 3D.** Directly determines whether action-engine's own Rollback
    Strategy (§4) can be implemented as currently envisioned (Option A gives it a
    primitive to call), must be implemented entirely in action-engine's own domain
    (Option B), or must be rescoped (Option C).
11. **Impact on Phase 3E.** None directly — this is a 3C/3D-internal coordination
    question; agent-os never touches rollback machinery in any current document.
12. **Impact on contracts.** Option A requires a new method/shape on whatever
    `CapabilityPort`/adapter contract Fork 3C-1 produces (versioned per ADR-024 since
    it is an additive capability, not a breaking one, if added after the base contract
    ships). Options B/C require no capability-engine-side contract change.
13. **Impact on testing.** Option A requires new adversarial/correctness tests
    specifically for the snapshot/restore primitive itself (does restore actually
    reconstruct prior state faithfully, under what failure modes). Option B moves that
    same testing burden into action-engine's own test suite instead. Option C removes
    the testing burden entirely, at the cost of the acceptance-criterion tension noted
    above.
14. **Impact on infrastructure.** Option A may require capability-engine's filesystem
    adapter to reserve local disk/staging space for snapshots (a new operational
    resource not currently budgeted anywhere). Options B/C require no new
    infrastructure.

**Recommendation.** Option B is offered as the more consistent reading of the existing
text — TDD 3C's own Fork 3C-1 reasoning already frames "risk/approval/rollback/audit
wrapper" as action-engine's exclusive contribution, which reads naturally as excluding
rollback primitives from capability-engine's own adapter scope — but this is a
recommendation, not a decision, and TDD 3D's own text explicitly calls this open and
unreconciled ("This must be reconciled between the two TDDs before either begins
implementation"). Given that explicit, TDD-3D-authored instruction, this fork should be
treated as blocking for both 3C's and 3D's implementation starts, not merely a
nice-to-have clarification.

### Fork 3C-4 — Install/bootstrap idempotency semantics

1. **Evidence.** TDD 3C never discusses idempotency anywhere (§14). Its own design
   requires the four built-in capabilities to go through the real 8-stage pipeline "at
   first boot" via a self-triggered bootstrap/seed call
   (`06-tdd-3c-capability-engine.md:100-104`) against its own `POST /v1/capabilities/install`
   endpoint (`:211-215`) — a mutating REST call with no documented duplicate-call
   behavior.
2. **Relevant files.** `06-tdd-3c-capability-engine.md:100-104` (bootstrap design),
   `:206-224` (§7, the API surface, no idempotency language), `:194-202` (§6, the
   append-only `capability_installation_event` log, no dedup language), `:229-234`
   (§8, the failure table, silent on duplicate-call handling).
3. **Exact ambiguity.** What happens when `POST /v1/capabilities/install` is called
   twice for the same `(name, version)` — most concretely, when capability-engine's own
   bootstrap logic runs again on a service restart or redeploy after the four built-ins
   are already installed: does the second call error (requiring the bootstrap caller to
   pre-check via `GET /v1/capabilities` first), silently no-op/return the existing
   record, or run the full 8-stage pipeline again (re-doing sandbox tests, appending
   duplicate `capability_installation_event` rows for an install that already
   succeeded)?
4. **Why the current architecture is insufficient to resolve this silently.** The
   answer changes the persistence schema (whether `(name, version)` needs a real unique
   constraint the API honors gracefully, matching `07-database-architecture.md`'s own
   `UNIQUE (name, version)` sketch — one of the few things that older sketch and TDD 3C
   actually agree on structurally) and the API contract itself (whether callers must
   supply an idempotency key, or whether natural-key uniqueness alone is the mechanism).
   Building the install pipeline without deciding this risks either a crash-looping
   bootstrap sequence on every restart (if duplicate calls error and nothing catches
   it) or silent duplicate pipeline runs/audit-log entries (if nothing dedups).
5. **Options.**
   - **Option A.** Standard idempotency-key pattern: caller supplies a key, dedup
     tracked in a dedicated store/column, replayed calls return the original result
     without re-running the pipeline.
   - **Option B.** Natural-key idempotency: `(name, version)` uniqueness is the dedup
     mechanism itself — a `POST` for an already-installed `(name, version)` returns the
     existing record as a success (HTTP 200, not a fresh 201), without re-running the
     8-stage pipeline or appending new `capability_installation_event` rows.
   - **Option C.** No special handling: every `POST` always attempts the full
     pipeline; the bootstrap caller (capability-engine's own startup code) is
     responsible for checking `GET /v1/capabilities` first and skipping the `POST`
     entirely for already-installed built-ins, keeping the API itself simple at the
     cost of pushing the idempotency concern to every caller.
6. **Existing precedent per option.**
   - Option A: no precedent in this codebase for a dedicated idempotency-key mechanism
     on any engine's REST surface (confirmed: not found in any other engine's API
     during this or prior research passes).
   - Option B: `07-database-architecture.md:32-43`'s own `UNIQUE (name, version)`
     constraint sketch is real, pre-existing precedent for treating `(name, version)`
     as the natural dedup key, even though that document predates TDD 3C and conflicts
     with it on other columns (§9.1) — the uniqueness constraint itself is one place
     the two documents already agree.
   - Option C: matches this project's general precedent of keeping engine-owned REST
     surfaces minimal and pushing orchestration concerns to the caller (e.g.,
     `planning-engine`'s own known-limitation disclosure that redelivery of
     `reasoning.process.completed` triggers "a second, independent, unpersisted
     decomposition attempt," explicitly accepted as a known, disclosed gap rather than
     solved, "safe only because nothing is persisted yet").
7. **Advantages.**
   - Option A: most robust against any caller, not just the known bootstrap case;
     standard, well-understood REST pattern.
   - Option B: no new mechanism required beyond a constraint TDD 3C's own model
     already almost implies (`name`/`version` fields exist, and Option B is exactly
     what `07-database-architecture.md`'s pre-existing sketch already assumed);
     naturally prevents the realistic Phase-3 failure mode (duplicate bootstrap calls)
     with minimal new design.
   - Option C: zero new mechanism in capability-engine itself; keeps the domain model
     and API exactly as already scoped by TDD 3C.
8. **Disadvantages.**
   - Option A: meaningful new design surface (key generation, storage, replay
     semantics) for a problem that, in Phase 3's actual scope (4 known, first-party,
     self-triggered installs, no external caller), may be more machinery than the real
     risk warrants.
   - Option B: a caller who genuinely wants to *reinstall*/*upgrade* a capability at the
     same version (e.g., after fixing a bug in a bundled capability's package, without
     bumping the version string) has no clean path — this option conflates "already
     installed" with "nothing to do," which may not always be true.
   - Option C: the realistic bootstrap-crash-loop or duplicate-audit-log risk (item 4
     above) is left entirely unmitigated at the capability-engine layer, resting on
     every caller (today: only capability-engine's own bootstrap code, but potentially
     others once any external caller exists) to get its own pre-check right every time.
9. **Impact on Phase 3C.** Option A requires new persistence (an idempotency-key
   store) and API surface; Option B requires only that the existing `(name, version)`
   uniqueness be enforced and gracefully handled at the API layer (a small,
   well-scoped addition to the pipeline's own early stages); Option C requires no
   change to capability-engine's own code, only a documented caller responsibility.
10. **Impact on Phase 3D.** None directly — action-engine never calls
    `POST /v1/capabilities/install`; this is entirely a capability-engine/bootstrap
    concern.
11. **Impact on Phase 3E.** None directly, for the same reason.
12. **Impact on contracts.** Option A likely needs a new field (an idempotency key) on
    whatever `nova_contracts` request payload the install endpoint eventually gets, if
    one is even defined (TDD 3C's own §7 doesn't commit `nova_contracts` payloads for
    the REST layer at all, only for the entity types). Options B/C need no contract
    change.
13. **Impact on testing.** All three options are straightforward to test once chosen;
    Option B's test (double-`POST` returns the existing record, pipeline runs exactly
    once) is the cheapest to write and the most directly aligned with TDD 3C's own
    already-stated acceptance criterion 1 ("all four built-in capabilities install
    successfully... at first boot" — implicitly, this should remain true even across
    restarts).
14. **Impact on infrastructure.** None of the three options require new
    infrastructure beyond what §10/§21 already specify.

**Recommendation.** Option B, on the strength of the pre-existing `07-database-architecture.md`
uniqueness-constraint precedent and its minimal new-design footprint relative to the
realistic Phase-3 risk (a self-triggered bootstrap call, not a general public API under
load) — presented as a recommendation, not a decision.

### Considered and explicitly not elevated to fork status

Per the instruction to state explicitly why an apparent ambiguity is not treated as a
fork, rather than silently omitting it:

- **The concrete sandboxing mechanism table (§9.4, TDD 3C §3).** Flagged for approval
  in the TDD's own text, but it is a single, concrete proposal with no documented
  alternative architecture presented anywhere — not a multi-option ambiguity. Treated
  as an approval-pending item (§25), not a fork.
- **The `07-database-architecture.md` vs. TDD 3C schema conflict (§9.1/§10).** A
  documentation-staleness/consistency issue with an obvious resolution direction (TDD
  3C is the more recent, phase-scoped, more carefully-reasoned document; the older
  sketch needs a follow-up correction) rather than a genuine choice between materially
  different implementation architectures. Recorded as a correction item (§25/§26), not
  a fork.
- **TDD 3D's `input_schema` Validate-stage ambiguity (§18).** Real, but internal to
  TDD 3D's own Action-Principle-lifecycle sequencing — its resolution does not require
  capability-engine's own architecture to change either way. Recorded as a heads-up
  for Phase 3D's own future pre-implementation research, not a Phase 3C fork.
- **The `category` field naming collision (§12/§19).** No document conflates the two
  namespaces incorrectly; this is a naming-hygiene recommendation for implementation
  time, not an unresolved architectural choice.
- **Circular-dependency detection for `Capability.dependencies` (§9.6).** The Bible is
  unambiguous ("circular dependencies should never be allowed"), and this project
  already has a directly-reusable precedent for exactly this kind of check
  (`find_cycle`, used for `TaskGraph` validation in planning-engine's own domain layer,
  PR #2). This is a small, low-ambiguity implementation gap to fix during 3C's own
  implementation, not a fork requiring the user's architectural judgment — recorded as
  an implementation prerequisite (§26), not a fork.
- **Multiple citation/line-number precision errors** (§9.2's `§5.5` and
  `12-agent-architecture.md:136` citations, §9.3's internal `(§9)` cross-reference,
  §11's second `(§9)` cross-reference, §9.4's `13-auth-and-security.md:90-92` citation).
  Documentation-quality issues, not architectural questions. Recorded for
  implementation-time correction (§25), not forks.
- **The `http` capability's absence from TDD 3E's five-agent table (§19).** Recorded
  as an unexplained gap, but nothing in the evidence suggests it reflects an
  unresolved architectural choice (as opposed to an incomplete first-draft agent
  roster) — not elevated to fork status.

---

## 23. Options

A consolidated decision menu across the four forks in §22, for at-a-glance review
alongside the full analysis:

| Fork | Option A | Option B | Option C |
|---|---|---|---|
| **3C-1/3D-1** — adapter ownership | Capability-engine owns the one real adapter per target; action-engine consumes via `CapabilityPort` | Each engine implements its own separate adapters | — (two-option fork) |
| **3C-2** — `granted_capabilities` population | Agent-os queries capability-engine eagerly at dispatch time | Static grant declared in the Agent Package manifest, resolved at install time | `AgentContext.granted_capabilities` holds only declared-intent identifiers; live resolution stays exclusively at action-engine's stage 5, as it already is today |
| **3C-3** — rollback/snapshot ownership | Capability-engine's filesystem adapter gains a snapshot/restore primitive | Action-engine owns all rollback logic itself, outside capability-engine | No automated rollback for capability-invoked destructive operations in Phase 3; TDD 3D's Rollback Strategy is rescoped |
| **3C-4** — install idempotency | Idempotency-key mechanism | Natural-key `(name, version)` uniqueness returns the existing record | No special handling; caller (bootstrap code) pre-checks via `GET` before every `POST` |

---

## 24. Recommendation

Consolidated, cross-referenced to each fork's full reasoning in §22 — every item below
is a recommendation only, none are decisions:

1. **Fork 3C-1/3D-1: Option A.** Matches both TDD 3C's and TDD 3D's own stated
   preference and this project's established building-block/port-consumption
   precedent.
2. **Fork 3C-2: no recommendation offered.** The evidence is genuinely balanced and
   no existing document leans toward any of the three options — this is presented as
   an open three-way choice.
3. **Fork 3C-3: Option B**, on the strength of TDD 3C's own "risk/approval/rollback/audit
   wrapper" sentence already framing rollback as action-engine's exclusive
   responsibility — but TDD 3D's own text calls this explicitly unreconciled, so this
   fork should block both 3C's and 3D's implementation starts regardless of which way
   it resolves.
4. **Fork 3C-4: Option B**, on the strength of the pre-existing
   `07-database-architecture.md` natural-key precedent and its minimal footprint
   relative to Phase 3's actual (self-triggered, low-volume) install-call pattern.

**None of these four recommendations should be read as authorization to proceed** —
per the governing instruction, all four remain open until explicitly approved.

---

## 25. Explicitly deferred decisions

Items flagged by TDD 3C itself as "flagged for explicit approval" but not treated as
multi-option forks in §22 (single concrete proposals awaiting approval, not
ambiguities), plus documentation-correction items surfaced by this research pass:

1. **The `Capability` model's 13-field subset** (§9.1) — TDD 3C's own words: "flagged
   for explicit approval — this subset is proposed, not extracted from an authoritative
   narrower-scope statement." Includes the silently-absent `Supported Platforms` field,
   which this research recommends either adding back explicitly or naming as a sixth
   disclosed deferral alongside `author`/`confidence`/`performance_metrics`/`documentation`/`example_workflows`.
2. **The `CapabilityHandle` 3-field shape** (§9.2) — TDD 3C's own words: "flagged for
   explicit approval."
3. **The concrete per-adapter sandboxing mechanism table** (§9.4) — TDD 3C's own
   words: "a genuinely new, disclosed proposal... flagged for explicit approval,"
   layered on top of the already-approved Fork E3 depth decision (not itself reopened).
4. **The `07-database-architecture.md` vs. TDD 3C `Capability` schema conflict**
   (§9.1/§10) — recommend TDD 3C's model be treated as authoritative (it is the more
   recent, phase-scoped, more deliberately-reasoned document) and `07-database-architecture.md`'s
   older sketch be corrected to match at a future documentation pass — not
   this branch's own scope to fix, since this branch is research-only and does not
   modify any document other than adding this one.
5. **The `perception.filesystem.observed` subscription expectation**
   (`10-inter-engine-communication.md:90`, §5/§8) — a real architecture-doc-level
   expectation TDD 3C never engages with. Recommend either TDD 3C be amended at
   implementation-approval time to address it, or the architecture doc's scenario table
   be corrected if the expectation is no longer intended for Phase 3C specifically.
   Not resolved here.
6. **The `PromptAssembly.available_capabilities` / ADR-026 read-path**
   (`06-ai-layer-architecture.md:126`, §6) — an expected output TDD 3C never engages
   with. Recommend the same treatment as item 5: reconcile at implementation-approval
   time, not silently in this research pass.
7. **Multiple internal citation-precision issues** across TDD 3C (§9.2's `§5.5` and
   `12-agent-architecture.md:136` citations; §9.3's and §11's `(§9)`
   cross-reference, both almost certainly meaning `§14`; `13-auth-and-security.md:90-92`'s
   2-line drift) — none large enough to change any conclusion in this research, but
   worth a light-touch correction pass alongside whatever document eventually
   incorporates this research's findings.
8. **Silent (non-disclosed) Bible-Part-15 narrowings** cataloged in full in §9.6 —
   most notably the absent-not-deferred `Supported Platforms` field (item 1 above),
   Visual Capability Center (no panel named, and not listed as a Non-goal), and
   registry-search-at-scale (`19-scalability-strategy.md:28`'s "thousands of entries"
   expectation, never cited by TDD 3C). None block Phase 3's 4-capability scope; all
   are worth an explicit Non-goals amendment at the same future pass as item 7, so a
   reader trusts TDD 3C's §14 as the complete out-of-scope list.
9. **The gateway doc's internal `3-P.2` scope inconsistency regarding Phase 3C**
   (§11) — a `03-gateway-web-prerequisite.md`-side correction, not this branch's scope.
10. **The Fork 3C-1/3D-1 acceptance-criteria scope discrepancy** (§18/§22) — TDD 3C's
    own acceptance criterion 5 and TDD 3D's own acceptance criterion 6 state two
    different scopes for what the fork's resolution gates. Recommend both TDDs be
    reconciled to state the same scope when the fork itself is resolved.

---

## 26. Implementation prerequisites

Concrete, low-ambiguity items that should happen as part of Phase 3C's implementation
(once approved), distinct from the forks in §22 (which need the user's decision
first):

1. Resolve Fork 3C-1/3D-1, Fork 3C-2, Fork 3C-3, and Fork 3C-4 (§22) before or at the
   start of implementation — per TDD 3C's own acceptance criterion 5 and TDD 3D's own
   acceptance criterion 6 (worded inconsistently with each other, §18/§25 item 10),
   Fork 3C-1/3D-1 at minimum gates action-engine's implementation start, and per TDD
   3D's own explicit text, Fork 3C-3 gates "either" 3C's or 3D's implementation start.
2. Scaffold `services/capability-engine` via `tools/scaffold-engine.py`, the same
   tooling already proven for `planning-engine`.
3. Register `nova_capability_engine` in `pyproject.toml`'s `root_packages`, the
   ADR-004 independence contract, the ADR-006 and ADR-007 forbidden-import contracts
   (auto-handled by scaffold-engine.py) — **and manually add it to the ADR-020
   forbidden-import contract's `source_modules`** (§12/§13; not auto-handled, a
   confirmed real gap every model-adjacent engine has had to close by hand, most
   recently `planning-engine` in PR #7).
4. Add a cycle-detection check to the Dependency Resolution installation-pipeline
   stage for `Capability.dependencies: list[str]`, reusing the `find_cycle` pattern
   already proven for `TaskGraph` validation in planning-engine's domain layer (PR #2)
   — per §22's "considered and not elevated" reasoning, this is a low-ambiguity gap fix,
   not a fork.
5. Add `infra/docker/docker-compose.local.yml` and `.github/workflows/build-and-scan.yml`
   entries, same pattern as every prior engine (TDD 3C's own §11 already discloses this
   as needed).
6. Create the `capability` Postgres schema + Alembic migration for `capability` and
   `capability_installation_event` (§10), incorporating whatever Fork 3C-4 resolution
   is approved (§22) into the table's uniqueness/idempotency handling from the start.
7. Land `nova_contracts.events.capability` (`Capability`, `CapabilityHandle`) with
   `schema_version: int = 1` per ADR-024 (§7), and verify TS codegen produces a
   zero-diff/expected-diff result per this project's standard PR-verification suite.
8. Write the adversarial sandbox-violation tests (path-prefix escape, executable
   not on allow-list, host not on allow-list) as real, not-fakeable real-infrastructure
   tests per TDD 3C's own testing strategy (§20) — this is the direct proof of the
   roadmap's Phase 3C acceptance bar and should not be treated as satisfied by
   fake-backed unit tests alone.
9. If Fork 3C-2 resolves to Option A, design and land whatever new capability-engine
   query surface agent-os needs, as an explicit, reviewed addition to TDD 3C's §5
   Ports — not invented ad hoc during 3E's own implementation.
10. If Fork 3C-3 resolves to Option A, design the snapshot/restore primitive as part
    of the initial adapter contract, not bolted on after action-engine's Rollback
    Strategy is already built against a primitive-less adapter.

---

## 27. Final readiness assessment

**Phase 3C is NOT ready for implementation.** Four architectural forks (§22) remain
genuinely unresolved, one of which (Fork 3C-1/3D-1) TDD 3C and TDD 3D both already
independently flag as blocking, and one of which (Fork 3C-3) TDD 3D explicitly states
must be reconciled "before either [TDD 3C's or TDD 3D's] implementation begins." Beyond
the forks, ten items are recorded as explicitly deferred decisions (§25) requiring
either explicit approval (the TDD's own three "flagged for explicit approval" items) or
a documentation-correction pass (cross-document conflicts and citation-precision
issues) before or alongside implementation.

**What this research pass positively confirms is healthy about Phase 3C's design,
weighed against the forks/gaps above:**
- Zero capability-named event-bus contract currently exists anywhere downstream (§8)
  — Phase 3C has complete latitude to design its own event surface without breaking an
  existing consumer.
- The sandboxing *depth* question (OS-level scoping vs. container/gVisor isolation) is
  genuinely already resolved (Fork E3, §9.4/§22) — not a live ambiguity this pass
  reopens.
- TDD 3C has zero AI-model dependency, consistent with Bible Part 15's own explicit
  architectural requirement (§13) — a real, structurally clean boundary once the ADR-020
  import-linter contract is extended to it (§26 item 3).
- The persistence precedent it cites (`ConversationDecisionTraceORM`) is real, shipped
  code, not a hypothetical analogy (§10).
- The testing strategy (§20) is already well-aligned with this project's established
  testing pyramid and correctly identifies which of its own test classes cannot be
  meaningfully faked.

**What blocks a green light:** the four forks in §22, most acutely Fork 3C-1/3D-1
(shared with TDD 3D, already flagged by both documents as unresolved) and Fork 3C-3
(the snapshot/backup primitive TDD 3D discovered TDD 3C's own adapter design doesn't
yet specify). Fork 3C-2 (`granted_capabilities` population) additionally has no
existing textual lean toward any resolution in either TDD 3C or TDD 3E, meaning it
cannot be resolved by inference from the current documents at all — it requires a
genuine, fresh decision.

**Recommended next step:** present §22/§23/§24 to the user for explicit resolution of
all four forks (and, ideally, the three TDD-3C-native "flagged for explicit approval"
items in §25 at the same time, since they are cheap to approve alongside the forks and
currently block nothing but do block a clean subsequent Gate Review). Only after that
approval should a dedicated `phase-3c-implementation` branch be created from the
current tip of `phase-3b-planning-domain`, per the standing research→implementation→PR→review→merge→sync→cleanup
workflow — not from this research branch, which per the governing instruction remains
a small, documentation-only artifact.

Phase 3C implementation has **not** started. No production code, no contract types, no
CI changes, and no scaffolding exist anywhere in this branch or any other branch in
this repository as of this research pass.
