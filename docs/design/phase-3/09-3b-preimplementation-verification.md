# 09 — Phase 3B Pre-Implementation Verification Report

**Status: research only. No production code, no test changes, no contract
changes. Nothing in this document is authorized for implementation until
explicitly approved.** This document performs the evidence-driven
re-verification of `05-tdd-3b-planning-engine.md` requested before
`planning-engine` implementation begins, against the repository as it
stands after Phase 3A (`2f064bd`). It follows the same discipline as
`01-tdd-preparation-and-fork-resolutions.md`: every claim below is checked
against the actual repository, not assumed from the TDD, the roadmap, the
task tracker, or prior research.

---

## 0. Method

Every document TDD 3B cites was re-read in full: `docs/architecture/06-ai-layer-architecture.md`
§3, `docs/architecture/10-inter-engine-communication.md` (rows 5, 6, 14, the
dependency graph, the dotted "consulted by" edges), `docs/architecture/12-agent-architecture.md`
§11, `docs/architecture/11-api-architecture.md` §2, `docs/bible/part-09-planning-engine.md`
(full text), `docs/bible/part-14-autonomy-engine.md` (risk classification
section), `docs/design/phase-3/00-research-and-scope.md` §1.3, `01-tdd-preparation-and-fork-resolutions.md`
§2, ADR-004, ADR-005, ADR-026, ADR-032, ADR-034, TDD 3D (`07-tdd-3d-action-engine.md`),
and TDD 3E (`08-tdd-3e-agent-os.md`). Every code claim was checked directly:
`services/reasoning-engine`, `services/executive-cognition-engine`,
`packages/nova-contracts`, `packages/nova-testkit`, `packages/nova-service-kit`,
`tools/scaffold-engine.py`, root `pyproject.toml`, `infra/docker/docker-compose.local.yml`,
`.github/workflows/build-and-scan.yml`.

**Headline result: TDD 3B's domain model, ports, persistence design, API
surface, ownership boundaries, and workspace/scaffolding claims all verify
correctly against current code and documentation. One load-bearing
assumption — the event TDD 3B is designed to consume — does not: it names a
subject that does not exist in this codebase and never has.** This is
reported per the standing instruction to treat this as a defect discovered
in another engine, not fixed here, and not silently corrected into the
plan. §1 covers it in full before anything else, since it blocks 3B exactly
as designed in §6.1 of the TDD.

---

## 1. Headline finding: a genuine defect blocking 3B as designed

### 1.1 `reasoning.result` does not exist. The real subject is `reasoning.process.completed`.

TDD 3B states three times that `reasoning-engine` "already publishes
`reasoning.result`" (§0 Dependencies, §1 Existing capability, §6.1
Subscribed) and designs `planning-engine`'s entire trigger mechanism around
subscribing to it. This is factually wrong, and the error is independently
verifiable four ways:

1. **`nova_contracts/events/reasoning.py` registers no such subject.**
   `grep -n "register_payload" packages/nova-contracts/src/nova_contracts/events/reasoning.py`
   returns exactly five subjects: `reasoning.reason.request`,
   `reasoning.reason.reply`, `reasoning.process.completed`,
   `reasoning.process.failed`, `reasoning.human_override.applied`. No
   `reasoning.result`.
2. **`reasoning-engine`'s own publish call site uses the real name.**
   `domain/pipeline.py:594-595`: `_completed_outbox_event` constructs
   `OutboxEvent(subject="reasoning.process.completed", payload=ReasoningProcessCompletedPayload(...))`
   — a literal string, unchanged since Phase 2B, confirmed untouched by
   Phase 3A (see §10 below).
3. **This exact mistake was already found and partly fixed once.** The
   Project Health Review (August 2026) documented (`docs/roadmap/architecture-reviews/project-health-review-2026-08.md:213`):
   *"`knowledge-engine`... and `memory-engine`... both subscribe to
   `reasoning.result`, live-wired... `reasoning-engine` — a real, shipped
   engine — does not publish this subject. Its actual completion events are
   `reasoning.process.completed`/`.failed`/`.human_override.applied`."*
   Cleanup Step 1 item 4 (task #109, completed) removed both stale
   subscriptions; `services/knowledge-engine/src/nova_knowledge_engine/events/subscribed.py:14-19`
   and the equivalent file in `memory-engine` now carry an explicit
   docstring recording exactly this history.
4. **The architecture docs TDD 3B's authors drew from were never
   corrected and still say `reasoning.result` today** —
   `docs/architecture/06-ai-layer-architecture.md:81`,
   `docs/architecture/10-inter-engine-communication.md:84` (row 5, the row
   TDD 3B's §0/§6.1 build on), and `docs/architecture/20-engine-responsibility-boundaries.md:64`
   all still reference the nonexistent name. The Project Health Review's own
   fix list (item 7, line 391) recommended reconciling the *subscriptions*,
   which happened; it never flagged the architecture *documentation* itself
   as needing the same fix, so the stale name survived into every document
   written after it, including this TDD.

**Consequence if built as written:** `planning-engine` would subscribe to a
subject nothing ever publishes — the identical "stale subscription, zero
real producer" bug Cleanup Step 1 just removed from two other engines,
reintroduced fresh in a brand-new one. Decomposition would never trigger
under real conditions; only the TDD's own "scripted `reasoning.result`"
acceptance test (§13.1) would appear to pass, since a scripted test can
publish a payload under any subject name.

**Resolution is not ambiguous** — `planning-engine` should subscribe to
`reasoning.process.completed` (`ReasoningProcessCompletedPayload`) instead —
but this is a correction to TDD 3B's own text in three places, not a
same-meaning rewording, and per the standing rule ("if you find a
discrepancy between the TDD and the actual code, stop and report it") it is
reported here for explicit acknowledgment rather than silently written
correctly at implementation time.

### 1.2 Even with the correct subject, the payload carries no content to decompose

This is a second, independent, more consequential gap. `ReasoningProcessCompletedPayload`
(`nova_contracts/events/reasoning.py:154-169`) carries exactly:

```python
reasoning_process_id: UUID
correlation_id: UUID
requesting_engine: str
user_id: UUID
reasoning_mode: ReasoningMode
reasoning_level: int
confidence_score: float
execution_duration_ms: float
outcome: ReasoningOutcome
schema_version: int = 1
```

No `objective_text`. No description of what was decided. `confidence_score`
is exactly what Fork 3B-3's threshold check needs — but nothing in this
payload can become `TaskGraph.root_objective` or seed `TaskNode` generation.
This is not a narrow gap that a clever mapping closes: the payload is
IDs, scores, and enums only, by design (§19 of the reasoning-engine design
doc: `ReasoningTrace` — the richest object reasoning-engine builds per
process — is explicitly "metadata *about* the process, not a... transcript
*of* it").

**Checked and confirmed there is no other current path to the content
either:**
- `GET /v1/reasoning/decisions/{decision_id}` (`api/decisions.py:20-25`) is
  keyed by `decision_id`, which `ReasoningProcessCompletedPayload` does not
  carry — only `reasoning_process_id`.
- `GET /v1/reasoning/traces/{trace_id}` (`api/traces.py`) is keyed by
  `trace_id`, same problem.
- The repository Protocol (`domain/ports.py:198-204`) does have
  `get_decision_for_process(reasoning_process_id)` and
  `get_trace_for_process(reasoning_process_id)` — but neither is exposed at
  the API or event boundary anywhere. They are internal-only today.
- Even if they were exposed: `Decision` (`domain/models.py:279-289`) carries
  `explanation.chosen_reason` (why an alternative was picked) but not the
  objective text either; only `ReasoningProcess.objective_text`
  (`domain/models.py:166`) has it, and `ReasoningProcess` has no API route
  at all.

**This blocks `planning-engine`'s core mechanism (§6.1: "consumes a
completed, sufficiently-confident reasoning result and produces or mutates
a `TaskGraph`") as literally designed**, independent of and in addition to
§1.1's naming error. Both are reported together because both sit on the
same integration point and a single decision resolves both.

**Options, not resolved here:**

| Option | Shape | Cost | Precedent |
|---|---|---|---|
| **A — additive payload fields (recommended)** | Add `objective_text: str` and `chosen_description: str \| None = None` to `ReasoningProcessCompletedPayload`; populate both in `_completed_outbox_event` from the already-in-scope `process`/`chosen` values. | One `nova-contracts` additive change + a few lines in `reasoning-engine`'s existing construction site. | Identical shape to Priority 3's "reasoning-engine additive contract fields for response-shaping hints" (task #164) and Phase 2D-D's `CommunicationSessionCompletedPayload` enrichment (task #197) — both already-used, already-accepted patterns in this project. |
| **B — new read path keyed by `reasoning_process_id`** | Expose `get_decision_for_process`/`get_trace_for_process` via a new REST route or RPC on `reasoning-engine`; `planning-engine` calls it after receiving the completion event. | New API surface + a `PlanningEngine`-side port and client, more moving parts than A for the same outcome. | No exact precedent; conceptually closer to `MemoryPort`/`KnowledgePort`'s "consult on demand" pattern, but those ports fetch *additional* context, not the primary content a triggering event should already carry. |

Both options touch `reasoning-engine`, which is out of scope for this pass
per explicit instruction ("keep Phase 3A untouched unless a genuine defect
is discovered that blocks 3B... report it separately instead of fixing
it"). **This is that report.** Neither option is implemented here.

---

## 2. Confirmed assumptions (verified accurate, no action needed)

- No `services/planning-engine` directory exists; no `TaskNode`/`TaskGraph`/`RiskLevel`/`Estimate`
  type exists anywhere in `nova-contracts` (repo-wide grep, zero hits beyond
  TDD/doc prose) — TDD 3B §1's claim is accurate.
- `docs/architecture/06-ai-layer-architecture.md` §3's `TaskNode`/`TaskGraph`
  code block is byte-identical to TDD 3B §2.1's own block — genuinely the
  schema source of truth, not a TDD invention.
- Bible Part 9's WBS field list (7 fields, `part-09-planning-engine.md:159-179`),
  the 12-level Objective Decomposition hierarchy (lines 107-156), Dynamic
  Replanning (lines 385-405), and Collaborative Planning ("NOVA proposes.
  The user approves.", lines 489-497) all confirmed present exactly as
  cited.
- Bible Part 14's risk scale — Negligible / Low / Moderate / High / Critical
  (`part-14-autonomy-engine.md:271-279`) — confirmed present at the cited
  location.
- `docs/architecture/10-inter-engine-communication.md` row 6 ("Plan ready" →
  `planning.task_graph.created`), row 14 ("Response ready", attributing the
  notify-user decision to the *consuming* engine), and the "Memory
  -.consulted by.-> Planning" / "Knowledge -.consulted by.-> Planning"
  dotted edges all confirmed present exactly as TDD 3B §3/§6.2 cite them.
- `docs/architecture/12-agent-architecture.md` §11 "Autonomous task
  decomposition" confirmed matches TDD 3B §6.2's description of
  `planning.decompose.request` (a Supervisor requesting further
  decomposition of a coarse subtree) word for word.
- ADR-004, ADR-005, ADR-026, ADR-032, ADR-034 all confirmed to say what TDD
  3B cites them for. In particular:
  - ADR-026 confirms "Current Goals (Planning Engine once it exists in
    Phase 3, an explicit caller-supplied parameter until then)" and "move
    from placeholder... to real RPC-backed ports" — consistent with TDD 3B
    §3's "planning-engine is the future real backing for `GoalsPort`, not a
    caller of it."
  - ADR-032 genuinely does not bind `planning-engine` — its subsystem line
    names Action Engine (Phase 3) and Autonomy Engine (Phase 4) only,
    confirming TDD 3B §10's claim.
  - ADR-034 confirms `dispatch_ready_events`/`make_health_router()` are
    real, reusable, zero-engine-specific shared mechanisms (verified
    directly, §4 below).
- `docs/architecture/11-api-architecture.md:49-50` is verbatim
  `GET /v1/plans/{task_graph_id}` / `POST /v1/plans/{task_graph_id}/approve`
  — TDD 3B §5's API surface is not invented.
- `tools/scaffold-engine.py`'s `_NAME_PATTERN` (`^[a-z][a-z0-9]*(-[a-z0-9]+)*-engine$`)
  accepts `planning-engine` — confirming TDD 3B §11's claim that, unlike
  `agent-os/kernel` in TDD 3E, no scaffolding-tool change is needed.
- Root `pyproject.toml`'s `root_packages` (11 engines + `nova_testkit` +
  `nova_service_kit`) and the three ADR-004/006/007 import-linter contracts
  do not yet list `nova_planning_engine` — confirming TDD 3B §11's claim
  this needs to be added (automatic via the scaffolding tool).
- `infra/docker/docker-compose.local.yml` and `.github/workflows/build-and-scan.yml`
  both confirmed to have no `planning-engine` entries today — TDD 3B §11's
  workspace-change claims are accurate, nothing has drifted since the TDD
  was written.
- `nova-service-kit` genuinely exports `dispatch_ready_events` (`outbox.py:77-111`,
  parameterized entirely over structural Protocols, zero engine-specific
  imports, exactly as ADR-034 requires) and `make_health_router()`
  (`health.py:25`) — TDD 3B §4/§9's reuse claims are accurate, not
  aspirational.
- The "second `BoundEventBus` as external caller" RPC-testing pattern TDD
  3B §12 cites as precedent for testing `planning.decompose.request` is
  real, not a paraphrase — confirmed verbatim in
  `services/executive-cognition-engine/tests/integration/test_events_arbitrate_request.py`,
  which wraps the same in-memory bus instance in a second `BoundEventBus`
  standing in for an external caller.
- No `apps/` directory and no gateway service exist yet — the `3-P`
  prerequisite slice remains design-only, so TDD 3B §5's "no `api-gateway`
  exists yet" is still current, nothing has shipped since the TDD package
  was written that would change this.
- TDD 3D (`07-tdd-3d-action-engine.md:81,117-121,202,235`) genuinely reuses
  `RiskLevel` "from TDD 3B, Bible Part 14" and builds a
  `minimum_confidence_by_risk: dict[RiskLevel, float]` policy on top of it
  — confirming Fork 3B-1's resolution is not 3B-local; TDD 3D is already
  written assuming Fork 3B-1 resolves the way TDD 3B proposes.

## 3. Corrected assumptions / discrepancies

Beyond §1's headline finding:

- **Minor mis-citation, no technical impact.** TDD 3B §11 attributes the
  "`TaskGraph` belongs in `events/`, not `entities.py`" rule to
  "`01-tdd-preparation-and-fork-resolutions.md` §2's Fork-adjacent
  finding." §2 of that document is "Decision matrix — Forks E1-E6" (lines
  91-457) — the frontend-stack/action-engine/sandboxing forks, nothing
  about entity placement. This looks like a naming collision ("Fork E"
  vs. the unrelated, separately-named "Extraction E" of the
  `nova-service-kit` boilerplate proposal). **The underlying technical
  conclusion is still correct** — independently verified against
  `packages/nova-contracts/src/nova_contracts/entities.py`'s own docstring:
  *"never published on the Event Bus directly... unlike everything under
  `events/`."* `TaskGraph` is wire-published via `planning.task_graph.created`,
  so it does belong in `events/planning.py`. No action needed beyond noting
  the citation is wrong; the design decision it supports is sound.
- **Clarification, not a discrepancy.** Both `reasoning-engine`'s and
  `executive-cognition-engine`'s `GoalsClient` docstrings say the migration
  happens "the moment Planning Engine ships" / "once Planning Engine
  ships," phrasing that could be misread as assigning the migration to 3B.
  Checked directly against TDD 3E §8 (`08-tdd-3e-agent-os.md:259-282`):
  *"`planning-engine` (`3B`) did not originally define a 'current goals'
  RPC... This TDD adds one small, additive extension to `planning-engine`'s
  own contract surface."* TDD 3E already explicitly, transparently owns
  this migration and already discloses that 3B does not build it. **No
  fork here** — already resolved by the existing package, confirmed
  consistent on inspection. Included only because the research instructions
  asked whether Phase 3A changed anything relevant to 3B and this is the
  adjacent GoalsPort question that comes up in the same search.

## 4. Existing reusable mechanisms (confirmed, not reinvented)

- `nova-service-kit.dispatch_ready_events` — the transactional-outbox
  dispatch loop, reused unmodified (ADR-034).
- `nova-service-kit.make_health_router()` — `/internal/health`,
  `/internal/readiness`, `/internal/metrics`, reused unmodified.
- `nova-service-kit.create_engine`/`create_session_factory` — Postgres
  engine/session-factory boilerplate.
- The per-calling-engine Port convention (`MemoryPort`/`KnowledgePort`
  defined locally in `planning-engine`'s own `domain/ports.py`, never
  centralized) — identical shape to every existing engine's `domain/ports.py`
  (confirmed directly against `reasoning-engine`'s own `GoalsPort`/`MemoryPort`/etc.).
- The "second `BoundEventBus` as external caller" integration-test pattern
  for RPC-served subjects with no real caller yet (confirmed real, §2
  above).
- The "real code, no real caller yet" idiom already established for
  `GoalsPort`, `DigitalTwinPort`, and Fork D — directly reusable for
  `planning-engine`'s own `agent_os.task.completed` subscription handler
  (TDD 3B §6.1), whose real publisher doesn't exist until TDD 3E.
- The hand-written `0001_initial_schema.py` Alembic migration convention,
  JSONB-for-list-typed-fields convention (e.g.
  `communication.conversation_session.pending_questions`), and
  transactional-outbox `outbox_event` table shape — all confirmed as the
  established per-engine pattern via direct precedent in shipped engines,
  not TDD invention.
- `tools/scaffold-engine.py` itself — confirmed to already auto-populate
  `root_packages` and the three ADR-004/006/007 import-linter contracts on
  first scaffold (§2 above), so no manual contract editing is needed beyond
  running the tool, contrary to what a literal reading of TDD 3B §11's
  bullet list might suggest.

## 5. Genuinely missing pieces (net new work 3B must build)

Everything TDD 3B §0/§1 already says is net new remains net new, confirmed
by the same repo-wide search that found zero existing `TaskNode`/`TaskGraph`
hits:

- The entire `services/planning-engine` package (domain, repository, API,
  events, workers, observability, tests) — nothing to extend, a clean
  build.
- `nova_contracts.events.planning` — `TaskNode`, `TaskGraph`, `Estimate`,
  `RiskLevel`, `PlanningTaskGraphCreatedPayload`,
  `PlanningDecomposeRequestPayload`/`Reply` — none exist today.
- The critical-path algorithm (longest-path-by-effort over a DAG) — no
  existing implementation anywhere in the repo to reuse (checked: no other
  engine does graph-critical-path analysis; `knowledge-engine`/`world-model-engine`
  graph work is traversal/storage, not scheduling).
- Whatever resolves §1's defect (new payload fields or a new read path) —
  net new regardless of which option is chosen, and cross-engine either
  way.

## 6. Required contract changes

Same as TDD 3B §11 proposed, confirmed still accurate and still entirely
additive (no existing type is modified):

- New `nova_contracts/events/planning.py`: `TaskNode`, `TaskGraph`,
  `Estimate`, `RiskLevel` (entities), `PlanningTaskGraphCreatedPayload`,
  `PlanningDecomposeRequestPayload`/`PlanningDecomposeReplyPayload`.

**Plus, pending the user's resolution of §1.2's fork**, one of:
- Option A: two new optional/required fields on the existing
  `ReasoningProcessCompletedPayload` (an out-of-3B-scope, cross-engine,
  additive `nova-contracts` + `reasoning-engine` change), or
- Option B: a new RPC pair (e.g. `reasoning.process.request`/`.reply`) or
  REST route on `reasoning-engine`, also out-of-3B-scope and cross-engine.

No other contract touches `reasoning-engine`'s or any other existing
engine's already-shipped payloads. `GoalsPort`'s real migration is
correctly excluded (§3 above, confirmed TDD 3E's job).

## 7. Dependency graph (confirmed against `02-master-scope.md`)

```
Phase 2D-D (closed) ──▶ 3A (done, 2f064bd, isolated leaf)
                    ├──▶ 3-P.1 (not started — no gateway/apps/ exists)
                    └──▶ 3B (planning-engine)
                              │
                              ├─ requires: reasoning-engine's
                              │  reasoning.process.completed
                              │  (real, confirmed) + either Option A or B
                              │  from §1.2 (missing today, cross-engine)
                              │
                              ├─ requires: MemoryPort/KnowledgePort RPCs
                              │  (memory.retrieve.request /
                              │  knowledge.retrieve.request, both real,
                              │  confirmed shipped since Phase 1)
                              │
                              ├─ defines but cannot yet exercise live:
                              │  agent_os.task.completed subscription
                              │  (real publisher is 3E)
                              │
                              └──▶ 3C ──▶ 3D ──▶ 3E (needs 3B's TaskGraphs)
                                                  └─ adds planning.goals.current.request
                                                     to planning-engine (confirmed 3E's
                                                     job, not 3B's, §3 above)
```

No change from `02-master-scope.md` §2's own graph. `3A` remains an
isolated leaf with zero relationship to `3B` in either direction (confirmed
directly: Phase 3A's diff never touches `GoalsPort`, `ReasoningProcessCompletedPayload`,
or `DEFAULT_VERIFY_THRESHOLD`'s value — see §10).

## 8. Open architectural forks — re-checked, plus one newly surfaced

### Fork 3B-1 — `Estimate`/`RiskLevel` field shape

**Status: unchanged, still open, still requires explicit approval.**
`RiskLevel` proposed as Bible Part 14's 5-tier scale (Negligible/Low/Moderate/High/Critical)
— confirmed still the only canonical risk scale in the project, and now
additionally confirmed **load-bearing for TDD 3D**, which already assumes
this exact resolution (§2 above). `Estimate` proposed as
`{effort_hours: float, confidence: float}` — confirmed still genuinely
undocumented anywhere (no canonical shape exists to extract instead).
**No new evidence changes this fork's proposal or its open status.**

### Fork 3B-2 — WBS field gaps (`completion_criteria`/`deliverables`/`required_knowledge`/`required_tools`)

**Status: unchanged, still open, still requires explicit approval.**
Re-confirmed against Bible Part 9's WBS list (§2 above) and doc 06 §3's
narrower schema (byte-identical to TDD 3B's own block). TDD 3B's
recommendation (leave absent for Phase 3, matching the roadmap's
established narrower-than-Bible pattern, `00-research-and-scope.md` §1.3 —
confirmed genuinely about this exact tension, not a mis-citation) stands.
**No new evidence changes this fork.**

### Fork 3B-3 — reasoning-result-to-decomposition confidence threshold

**Status: mechanism confirmed sound; naming needs updating to match §1.1's
fix; substance unchanged.** `DEFAULT_VERIFY_THRESHOLD = 0.6`
(`reasoning-engine/domain/pipeline.py:69`) confirmed unchanged by Phase 3A
— still a valid, reusable default. One clarifying, non-fork observation
from this pass: `_completed_outbox_event`'s own docstring
(`pipeline.py:592-593`) confirms `reasoning.process.completed` fires for
**both** `decided` and `degraded` outcomes (never `failed`/`abandoned`,
which route to `reasoning.process.failed` instead) — so planning-engine's
threshold check is a genuine second gate on top of reasoning-engine's own
already-applied verify/override thresholds, not a redundant re-check of the
same boundary. Worth stating explicitly in the TDD text when it's updated,
not a new decision to make.

### Fork 3B-4 (new, surfaced by this pass) — how planning-engine actually gets triggerable content

This is §1's finding, restated as a fork for the decision table below: does
resolving §1.2 mean extending `ReasoningProcessCompletedPayload` (Option A)
or adding a new read path to `reasoning-engine` (Option B)? Not resolved in
this document — it is a cross-engine change and the user's own instruction
for this pass is explicit that such a change must stop for approval rather
than be silently decided.

## 9. Recommendation per fork

| Fork | Recommendation | Confidence | Requires |
|---|---|---|---|
| 3B-1 (`Estimate`/`RiskLevel` shape) | Approve as proposed in TDD 3B §2.1 — `RiskLevel` = Bible Part 14's 5-tier scale; `Estimate = {effort_hours: float, confidence: float}`. | High — no competing shape exists anywhere, and TDD 3D already depends on this exact resolution. | Explicit user approval (genuinely undocumented, per TDD's own flag). |
| 3B-2 (WBS field gaps) | Approve TDD 3B's recommendation — leave `completion_criteria`/`deliverables`/`required_knowledge`/`required_tools` absent from `TaskNode` for Phase 3. | High — consistent with this project's own established narrower-than-Bible scoping pattern, confirmed genuine via `00-research-and-scope.md` §1.3, not asserted. | Explicit user confirmation (TDD already flags this as not-silently-decided). |
| 3B-3 (confidence threshold) | Approve `DEFAULT_VERIFY_THRESHOLD` (0.6) reuse, subject name updated per Fork 3B-4's resolution. | High — value unaffected by Phase 3A; only the subject it's read alongside changes. | Bundled with Fork 3B-4's resolution below. |
| **3B-4 (new — trigger subject + content)** | Correct the subject to `reasoning.process.completed` (not a fork — factually required either way). For content: **recommend Option A** (additive `objective_text`/`chosen_description` fields on `ReasoningProcessCompletedPayload`) over Option B (new read path) — smaller surface, direct precedent (tasks #164, #197), and avoids adding a second RPC pair whose only purpose is recovering content a completion event should already carry. | Medium — subject-name correction is not in question; the A-vs-B choice is a genuine, first-time design decision this pass surfaced, not a re-confirmation of prior work. | **Explicit user decision required before 3B can be implemented as designed** — this is a cross-engine (`reasoning-engine` + `nova-contracts`) change outside this pass's authorized scope. |

## 10. Did Phase 3A change anything relevant to 3B?

**No.** Directly verified against Phase 3A's actual diff (`git show 2f064bd --stat`):
the six touched `reasoning-engine` files are `domain/models.py` (added
`multistep_recursion_exhausted`), `domain/trace.py` (added `chain_depth()`),
`domain/pipeline.py` (recursion trigger + `depth` param), `observability.py`
(three new metrics), `api/reason.py` and `events/handlers.py` (call the new
metrics function). None of these touch `_completed_outbox_event`,
`ReasoningProcessCompletedPayload`, `GoalsPort`/`GoalsClient`, or
`DEFAULT_VERIFY_THRESHOLD`'s value — all directly re-confirmed by reading
the current file contents at their exact line numbers, not inferred from
the commit message. **§1's defect predates Phase 3A entirely** and was
never previously surfaced because nothing has attempted to consume
`reasoning.process.completed` from outside `reasoning-engine` until this
research pass looked for it on `planning-engine`'s behalf.

## 11. Workspace/scaffolding readiness check

Confirmed ready, no gaps beyond what TDD 3B §11 already anticipated:

- `tools/scaffold-engine.py` accepts `planning-engine` with zero tool
  changes (§2 above) and auto-populates `root_packages` + the three
  ADR-004/006/007 contracts on first run.
- `docker-compose.local.yml` and `build-and-scan.yml` both confirmed to
  still have no `planning-engine` entries — need adding by hand (or via the
  scaffolding tool's own generated instructions), exactly as TDD 3B §11
  says, nothing has changed since it was written.
- `nova-service-kit` and `nova-testkit` both confirmed to have zero
  `planning-engine`-specific knowledge today (checked directly — neither
  package's source references any planning concept), so no shared-package
  changes are needed to stand the new engine up, consistent with ADR-034.

## 12. Implementation order (once §1's fork is resolved)

Unchanged in shape from TDD 3B §12/§13's own testing strategy, sequenced to
front-load the part that depends on the user's decision:

1. **Resolve Fork 3B-4** (subject name + Option A/B) — blocks everything
   downstream of it; nothing else in this list depends on which option is
   chosen, only on it being decided.
2. Resolve Forks 3B-1/3B-2 (can happen in parallel with step 1 — genuinely
   independent decisions).
3. `nova_contracts.events.planning` (contracts first, per this project's
   own established convention).
4. Scaffold `services/planning-engine` via `tools/scaffold-engine.py`.
5. Domain layer: `TaskNode`/`TaskGraph`/critical-path algorithm/mutation
   logic — independently unit-testable without persistence or the Event
   Bus, per this project's established layering.
6. Repository layer + `0001_initial_schema.py` migration.
7. API (`GET`/`POST /v1/plans/...`) + events (subscribe
   `reasoning.process.completed`, `agent_os.task.completed`; serve
   `planning.decompose.request`; publish `planning.task_graph.created`).
8. Observability + workspace wiring (docker-compose, CI matrix).
9. Tests across all four tiers (§13 below) + Gate Review.

## 13. Verification strategy

Unchanged from TDD 3B §12, confirmed all four tiers have real, reusable
precedent in this codebase (not proposed in the abstract):

- **Unit (fake-backed):** decomposition + critical-path + mutation-not-regeneration.
- **Contract:** `nova_contracts.events.planning` payload round-trips,
  mirroring every prior phase's contract-test convention.
- **Integration (fake ports, real FastAPI app):**
  `planning.decompose.request` via the confirmed-real "second `BoundEventBus`"
  pattern (§2 above); `POST /v1/plans/{id}/approve` round trip.
- **Real-infrastructure:** restart-survival test against real Postgres,
  directly proving `ENGINEERING_ROADMAP.md:545`'s acceptance criterion at
  the persistence layer.

One addition this pass surfaces: whichever Fork 3B-4 option is chosen needs
its own test at the boundary — either a contract round-trip test for the
two new `ReasoningProcessCompletedPayload` fields (Option A) or an
integration test for the new read path (Option B) — not scoped to 3B's own
test suite alone if the change lands in `reasoning-engine`.

## 14. Explicit scope exclusions (unchanged, reconfirmed)

- No Phase 3C/3D/3E work of any kind.
- No `agent-os/kernel` consumption of `planning.task_graph.created` —
  confirmed still nonexistent (no `services/agent-os` or equivalent).
- No `communication-engine` subscription to `planning.task_graph.created`
  — confirmed `communication-engine`'s current event surface has no such
  subscription today (out of scope either way, per TDD 3B §6.2).
- No synchronous "planning as part of a conversation turn" path (doc 10 row
  14) — only the asynchronous `planning.task_graph.created` path is in
  scope, unchanged.
- No Bible-Part-9 field beyond doc 06 §3's schema unless Fork 3B-2 is
  explicitly approved otherwise.
- No fix to `docs/architecture/06-ai-layer-architecture.md:81`,
  `10-inter-engine-communication.md:84`, or
  `20-engine-responsibility-boundaries.md:64`'s stale `reasoning.result`
  references — flagged in §1.1 as a documentation defect, not corrected
  here (unrelated technical debt, and correcting architecture docs is not
  what this pass was asked to do).
- No modification to `reasoning-engine`, `executive-cognition-engine`,
  or any other already-shipped engine — §1's defect is reported, not
  fixed, per explicit instruction.
- No production code, no test changes, no contract changes of any kind in
  this document.

---

## 15. Summary — what's needed from the user before 3B implementation can start

1. **A decision on Fork 3B-4**: approve Option A (additive
   `ReasoningProcessCompletedPayload` fields) or Option B (new
   `reasoning-engine` read path), or propose a third option — this is a
   cross-engine change this pass is not authorized to make unilaterally.
2. Confirmation that TDD 3B's subject-name references (`reasoning.result` →
   `reasoning.process.completed`) should be corrected in the TDD text
   itself as part of implementation.
3. Approval of Fork 3B-1 (`Estimate`/`RiskLevel` shape) as proposed.
4. Approval of Fork 3B-2 (WBS field gaps left absent) as proposed.
5. Optionally, a decision on whether the three stale `docs/architecture/*.md`
   references to `reasoning.result` (§1.1, §14) should be fixed at some
   point — flagged, not blocking, not part of this pass either way.

Every other part of TDD 3B — domain model, persistence design, port
convention, API surface, ownership/boundary claims, workspace/scaffolding
requirements, and testing strategy — is verified accurate against the
current repository and ready to implement once the above are resolved.
