# Architecture Review Report — Phase 2B: Reasoning Engine

**Phase:** 2B — Reasoning Engine (Bible Part 8)
**Completed:** 2026-08-05
**Design document(s):** [docs/design/phase-2b/](../../design/phase-2b/README.md) (00 Reasoning Engine, the full 25-section Technical Design Document approved before implementation began)
**Author:** Claude (Anthropic), AI-assisted implementation under direct human architectural
direction and review throughout — the design doc's approval, and the standing
instruction to pause on any architecturally-significant fork before proceeding, were
both explicit prior user directives. No such fork was encountered during this phase;
every implementation-time decision recorded below was either a narrow, in-scope
correctness fix or a choice consistent with the already-approved design, never a new
architectural direction decided unilaterally.

## 1. What was implemented

One independently deployable engine — a full FastAPI service + Arq worker process
pair — plus the `nova-contracts` additions Phase 2B required.

**Reasoning Engine** (`services/reasoning-engine/`) — Bible Part 8. NOVA's cognitive
bridge (ADR-026): it transforms Memory, Knowledge, World Model, Personal Context,
Current Goals, and Available Capabilities into decisions, and owns no system of
record for any of those six inputs — only records of its own reasoning processes
(`reasoning_process`, `hypothesis`, `evidence`, `alternative`, `decision`,
`reasoning_trace`, plus the standard `outbox_event`).

- **Domain layer** (`domain/`, framework-free, 20 modules): `pipeline.py` (the
  fourteen-step Cognitive Pipeline, §4, the engine's single entry point),
  `modes/` (one `ModeConfig` per reasoning mode — Reactive, Analytical, Strategic,
  Long-term planning, Goal-driven, Constraint-based, Multi-step, Reflective,
  Self-evaluation, Collaborative — plus `resolve_mode_and_level`'s structural
  intent-classification heuristic), `context_assembly.py` (the five-upstream-port
  parallel fan-out), `hypothesis_generation.py` (the one step that legitimately
  calls a model), `evidence_collection.py`, `alternative_generation.py`,
  `constraint_evaluator.py` (hard gate), `decision_matrix.py`, `goal_evaluator.py`,
  `confidence.py` (the seven-factor structural formula), `explanation.py`,
  `failure_recovery.py`, `trace.py`.
- **Clients** (`clients/`, one adapter per upstream port): `memory_client.py`,
  `knowledge_client.py`, `world_model_client.py`, `personal_context_client.py`
  (projects `WorldModelPort` rather than a separate upstream call — Personal Context
  has no dedicated engine yet), `goals_client.py` (an honest Phase 2B placeholder,
  §7.1), `model_orchestration_client.py`.
- **Repository layer**: `PostgresReasoningRepository` (7 tables, all UUID primary
  keys, all domain-supplied — see §11 below), the standard transactional outbox,
  a hand-written initial Alembic migration matching the design doc's schema exactly.
- **API**: `POST /v1/reasoning/reason`(`/stream`), `GET /v1/reasoning/traces`(`/{id}`),
  `GET /v1/reasoning/decisions/{id}`(`/explain`), `POST /v1/reasoning/decisions/{id}/override`.
  9 route handlers total (7 public, 2 internal) plus 1 mounted metrics endpoint.
- **Events**: publishes `reasoning.process.completed`/`.failed`,
  `reasoning.human_override.applied`; serves `reasoning.reason.request` as an Event
  Bus RPC sharing the exact same `pipeline.run` the HTTP route calls. Streaming is
  deliberately not an Event Bus contract (HTTP/SSE only), the same precedent the AI
  Model Orchestration Engine's own generate/stream endpoint established.
- **Workers**: `outbox_worker.py` only (every 5s) — this engine has no other
  domain-specific periodic worker (no analog to Memory Engine's consolidation
  worker or the AI Model Orchestration Engine's health-monitor/benchmark workers),
  because §25's "Review results"/"Learn" pipeline steps are explicitly out of a
  synchronous call's scope and no outcome-reporting mechanism exists yet to drive a
  periodic job against.
- **`nova-contracts` additions**: the five `reasoning` event-payload subjects
  (`reasoning.reason.request`/`.reply`, `reasoning.process.completed`/`.failed`,
  `reasoning.human_override.applied`), `ReasoningMode`'s ten-mode taxonomy, kept
  distinct from the plain-int `reasoning_level` cost/depth dial and the free-text
  `thinking_mode_hint` per the design doc's reconciliation of Bible Part 8's three
  overlapping taxonomies. Every payload carries `schema_version: int = 1` (ADR-024).
  The generated TypeScript client was regenerated and reconfirmed non-stale this
  review (46 payload files + index, zero diff on a fresh regeneration).

**69 tests** (43 unit, 11 integration, 15 ADR-023 port-compliance), all passing;
`ruff check` and `mypy` clean across the engine's `src/` and `tests/`; the root
`import-linter`'s existing four contracts all still passing with this engine included
(no fifth contract was needed — this engine introduces no new forbidden-import class
the way ADR-020 did for the AI Model Orchestration Engine).

No design changed from what
[docs/design/phase-2b/00-reasoning-engine.md](../../design/phase-2b/00-reasoning-engine.md)
specified. One real, if narrow, implementation-time correction went beyond the design
doc's literal text and is detailed in §2 below (`context_assembly.py`'s per-port
isolation) — a bug fix that makes an already-specified state transition (§5's
`degraded --> decided`) actually reachable, not a new design decision.

## 2. Why each architectural decision was made

No new ADR was filed this phase. ADR-026 (Reasoning Engine as cognitive bridge, never
an isolated subsystem, never owning data except records of its own reasoning
processes) was deliberately filed at Phase 2A's close, ahead of this design work,
per that phase's own Gate Review recommendation — and it required no amendment here;
every implementation decision in this phase fit inside the boundary ADR-026 already
drew. No implementation-time decision this phase rose to the level of a new
architecturally-significant choice requiring its own ADR; the two items below are
correctness fixes, not design decisions.

- **`context_assembly.py`'s five upstream calls are isolated from each other**
  (`asyncio.gather(..., return_exceptions=True)`, replacing a bare `gather()`).
  Found while writing a test for §5's `degraded --> decided: reduced-confidence
  decision still produced` transition: the original implementation's top-level
  `try/except` around the *entire* fan-out meant any single port raising (breaking
  its own documented graceful-degradation contract, §7.2/§7.3 — an empty result on
  timeout, never an exception) wiped the *whole* `ContextBundle`, not just that
  port's own contribution. With zero memories/knowledge/world-model data surviving,
  every hypothesis fails evidence collection deterministically, so `degraded -->
  decided` was unreachable dead code outside Reactive mode — the pipeline could
  only ever reach `degraded --> failed` in practice, silently narrower than what
  §5's own state diagram specifies. Fixed by isolating each of the five calls: a
  single misbehaving port now degrades only its own contribution, and the design
  doc's own two-branch `degraded` semantics are both genuinely reachable. This is a
  correctness fix that makes existing, already-specified behavior real, not a new
  design decision — filed here rather than as an ADR because it doesn't change what
  was decided, only makes the decision actually hold.
- **`OutboxEventORM.id` needed a Python-side `default=uuid.uuid4`, the other six
  ORM classes correctly do not.** Discovered by booting the engine against this
  sandbox's native Postgres 16 (a first for any engine in this project — no prior
  phase had real Postgres available) and hitting a `FlushError` on the first
  `finalize()` call with an outbox event. Root-caused by direct inspection of
  `postgres_reasoning_repository.py`: the other six ORM classes are always
  constructed with an explicit `id=<domain object>.id` (the domain Pydantic model
  already generated one via `Field(default_factory=uuid4)`), but `OutboxEvent` (the
  port-level value object) deliberately carries no `id` field — the design doc
  treats the outbox row's identity as a pure persistence-layer concern the domain
  layer shouldn't need to invent. That asymmetry is correct; the missing default
  on the one class that actually needed it was the bug. The identical bug existed
  in the already-shipped, already-Gate-Reviewed `ai-model-orchestration-engine`
  (same `OutboxEventORM` shape, same missing default) and was fixed in the same
  commit — a genuine cross-cutting fix this review's own real-Postgres verification
  surfaced, not something the fake-repository test suite could have caught (see §5).

## 3. Tradeoffs considered

- **Multi-step mode runs a single pipeline pass, not yet a recursive chain.** §11
  specifies recursion with a hard depth cap, each step its own `ReasoningProcess`
  row linked via `parent_process_id`, aggregate confidence as the minimum across
  the chain. `modes/multi_step.py`'s `ModeConfig` is wired and selectable end to
  end, but `pipeline.run` does not yet detect an unresolved sub-question mid-analysis
  and recurse. Named and tested as an honest gap
  (`test_multi_step_mode_runs_a_single_pass_not_yet_a_chain`) rather than silently
  claimed — building the recursion trigger without a real multi-step caller to
  validate against would be exactly the speculative-behavior risk this project's
  standing instructions rule out.
- **Constraint Evaluation's hard gate is real; the per-alternative check behind it
  is a documented no-op.** `constraint_evaluator.apply_hard_constraints` — the
  gate, the rejection recording, the "never silently drop a violating alternative"
  guarantee — is real and tested. `_violates` always returns `False`, because Phase
  2B has no per-alternative structured cost/privacy/time/resource metadata to check
  a constraint against yet (real wiring depends on the AI Model Orchestration
  Engine's own budget concept, itself deferred per that engine's Known Limitations).
  Named explicitly in the function's own docstring rather than faking a check with
  nothing real to evaluate.
- **Human Override's `redirect` action updates the winning alternative, but does
  not re-score.** `POST .../override` with `action: "redirect"` sets
  `Decision.selected_alternative_id` to the human-chosen alternative; it does not
  re-derive `DecisionMatrixScores`/`DecisionExplanation` for it, because no
  repository method exists to look up an `Alternative`'s original scoring inputs by
  ID. The row's `human_override` field records this as a human correction — "never
  presented as if the matrix itself had chosen it" (§18's own phrasing) — rather
  than silently faking a re-score.
- **`GoalsPort` remains Phase 2B's honest placeholder** (§7.1, restated from the
  design doc, unchanged by implementation): Planning Engine doesn't exist yet, so
  goals are caller-supplied on `ReasoningRequest` rather than fetched from a real
  RPC. The ADR-023 port-compliance suite asserts this explicitly — both the fake
  and the real-client implementation return `[]` unconditionally — as a genuine
  behavioral identity, not a silently-skipped difference.
- **This engine has one worker, not three.** Every prior Phase 1/2A engine shipped
  at least two domain-specific periodic workers beyond the outbox dispatcher
  (consolidation, embedding, maintenance, health-monitoring, benchmarking). This
  engine ships none, because nothing in Part 8's own scope for Phase 2B calls for
  a periodic job — Cognitive Pipeline runs are synchronous, request-triggered, and
  the "Review results"/"Learn" steps this engine would eventually schedule
  periodically depend on an outcome-reporting mechanism that doesn't exist yet
  (§25). Fewer workers here is a direct, honest consequence of scope, not an
  oversight.

## 4. Known limitations

The engine's own README carries the full list under "Known limitations (Phase 2B)."
Restated here for a reader who doesn't cross-reference:

- **`GoalsPort` is an honest Phase 2B placeholder** (§3) — migration path named in
  ADR-026's own Future Implications.
  **Multi-step mode is single-pass, not yet recursive** (§3) — named, tested, and
  scoped, not stubbed with fake chaining behavior.
- **Constraint Evaluation's per-alternative check is a documented no-op** (§3) —
  the gate mechanism is real; the check has nothing real to evaluate yet.
- **`KnowledgeClient.traverse()` uses a fixed placeholder confidence (0.5).**
  `knowledge.traverse.reply` (Phase 1) returns bare `connected_node_ids`, no
  per-node name/layer/confidence — labeling each result with its own node ID and a
  clearly-named neutral confidence, rather than fabricating data with no basis, an
  honest wire-contract gap not currently exercised by any pipeline path (§13 uses
  only `retrieve()`'s results).
- **Human Override's `redirect` action does not re-score** (§3).
- **Most `ReasoningEngineMetrics` counters are declared but not yet incremented.**
  `reasoning_requests_total`, `confidence_score`, and
  `reasoning_request_duration_seconds` are live; the six per-stage counters
  (`hypotheses_generated_total`, `alternatives_generated_total`,
  `alternatives_below_minimum_total`, `constraint_violations_total`,
  `human_overrides_total`, `failures_total`) are defined and unit-testable but
  nothing yet calls `.add()` on them.
- **`postgres_reasoning_repository.py` has no committed pytest coverage against a
  real Postgres instance** — every prior engine's own committed suite has the
  identical gap (fakes only). This phase is the first to verify the real
  repository layer at all, via an ad hoc, not-committed script against this
  sandbox's native Postgres (§2, §5) — a stronger verification posture than any
  prior phase had available, but still not a committed, CI-enforced test.
- **No read-through cache** beyond what the Postgres repository provides directly,
  mirroring every prior engine's own accepted gap.

## 5. Technical debt introduced, if any

None accepted as debt in the traditional sense — consistent with every prior phase's
own finding. The candidates evaluated are all deliberate, documented scope decisions:

- **`clients/personal_context_client.py` projects `WorldModelPort`'s own snapshot**
  rather than calling a dedicated Personal Context engine, because Personal Context
  (Bible Part 6) has no dedicated engine yet. Named explicitly in the client's own
  module docstring as reuse, not a hidden shortcut.
- **`_TRAVERSE_PLACEHOLDER_CONFIDENCE` in `knowledge_client.py`** (§4) is an
  explicitly-labeled approximation for a real wire-contract gap, not a claimed
  precise value — the same honesty standard the AI Model Orchestration Engine's
  `approximate_token_count` set in Phase 2A, applied here to a different gap.
- **Two real bugs were found and fixed during this phase's own work, not left
  open**: the `context_assembly.py` all-or-nothing degradation (§2) and the missing
  `OutboxEventORM.id` default, in both this engine and the already-shipped
  `ai-model-orchestration-engine` (§2). Both are closed, with tests
  (`test_context_assembly_failure_downgrades_an_otherwise_decided_outcome`) and,
  for the Postgres bug, direct verification against a live database confirming the
  fix, not just a fake-repository test that could have masked it again.

## 6. Future improvements

- **Implement Multi-step mode's recursion trigger** (§3, §4) once a real caller
  exercises Level 3/4 requests that plausibly need it — building the "detect an
  unresolved sub-question" heuristic without a real signal to validate it against
  would be exactly the speculative behavior this project avoids.
- **Wire real per-alternative structured metadata into Constraint Evaluation**
  (§3, §4) once the AI Model Orchestration Engine's budget concept (Phase 2A Known
  Limitations) is wired in — the two gaps are linked, not independent.
- **Add a repository method to look up an `Alternative`'s original scoring inputs
  by ID**, enabling Human Override's `redirect` action to genuinely re-score
  rather than only reassign `selected_alternative_id` (§3, §4).
- **Increment the six declared-but-unused `ReasoningEngineMetrics` counters** (§4)
  at their respective pipeline stages.
- **Build a committed test suite against a real Postgres instance** (§4) — this
  phase's ad hoc verification found one real, previously undetectable bug (§2);
  making that verification a permanent, CI-enforced part of the suite (for this
  engine and every prior one) would catch the next one automatically rather than
  depending on a reviewer happening to have real infrastructure available.
- **Run the six-service compose stack in a Docker-capable environment** (carried
  forward from every prior phase's Gate Review) to capture a first real latency
  measurement against Part 8's stated performance targets (§21: under one second
  for Reactive, several seconds for Analytical, correctness-over-speed with
  visible progress for Strategic/Multi-step) — still entirely unmeasured.

## 7. Risks

- **Operational:** `main.py`/`workers/` have been booted against this sandbox's
  real, native Postgres for the first time in this project's history (§2, §5) —
  stronger evidence than any prior phase had, but still not against the full
  six-service Docker Compose stack (no Docker daemon in this environment), so
  first-boot-against-full-real-infra issues (NATS, Redis-backed Arq scheduling,
  the six services running concurrently) remain unverified.
- **Architectural:** `context_assembly.py`'s per-port isolation (§2) is the
  mechanism that makes graceful degradation real rather than theoretical, but it
  depends on every upstream client continuing to honor its own documented
  contract (return an empty/`None` result on timeout, never propagate a raw
  exception) — verified true today for all five clients by direct inspection, but
  nothing prevents a future client change from silently reintroducing a raised
  exception that this engine would still handle safely (via the outer
  catastrophic-failure fallback) but less gracefully (full-bundle wipe instead of
  single-port degradation) than intended.
- **Scale:** Part 8's stated performance targets (§21) have not been load-tested;
  they are design-time targets, not measured results, the same unmeasured-until-
  Docker status every performance target in this project still carries.
- **Dependency:** this engine is the first real caller of the AI Model
  Orchestration Engine's `ai_model.generate.request` RPC under genuine (if still
  synthetic-test-only) load — the Phase 2A Gate Review named this as a named,
  mitigated-but-unproven migration risk, and this phase's port-compliance suite
  (mock-transport-backed, no live model) is consistent with, but does not close,
  that open item.

## 8. Compatibility with the NOVA Project Bible

- **Reasoning Engine (Bible Part 8):** implemented at the breadth the Phase 2B
  design doc scoped — the Cognitive Pipeline in full (§4), the Decision Lifecycle
  state machine (§5), all ten reasoning modes as selectable strategies (§6, with
  Collaborative correctly raising `NotImplementedModeError` rather than faked
  agreement behavior, and Multi-step correctly scoped to single-pass per §3),
  Goal Evaluation (§8), Constraint Evaluation (§9), Confidence Estimation's
  seven-factor formula (§10), Hypothesis Generation as the one legitimate model
  call (§12), the Decision Matrix (§15), Decision Explanation (§16), Failure
  Handling (§17), Human Override (§18), and the Reasoning Trace (§19) as
  structured metadata, never chain-of-thought exposure.
- **ADR-025's Personal Edition principle** required no retrofit: this engine is
  single-user by default, carries no multi-tenant assumption, and its one
  deviation from every prior engine's shape (one worker instead of several) is a
  direct, honest consequence of scope rather than a compatibility gap.
- **ADR-026's own boundary**, filed specifically to govern this phase, held
  without amendment (§2) — the engine owns no system of record for any of its six
  inputs, verified structurally by direct inspection of every repository and
  client module, not merely asserted by the design doc's prose.
- All Known Limitations (§4) are, per the user's standing instruction carried
  forward from every prior phase, deliberately preferred over any speculative
  implementation of behavior the design doc did not specify.

## Sign-off

- [x] All items in the engine's design-doc review checklist
      ([docs/design/phase-2b/README.md](../../design/phase-2b/README.md)) are
      satisfied — the design was approved before implementation began and no
      deviation occurred beyond the two correctness fixes noted in §2.
- [x] The phase's Definition of Done
      ([SAD 15 §4](../../architecture/15-development-workflow.md#4-definition-of-done-per-pr))
      was met: implementation, tests, observability, and documentation delivered
      together, not as follow-up work.
- [x] The per-subsystem deliverable checklist
      ([SAD 15 §9](../../architecture/15-development-workflow.md#9-per-subsystem-deliverable-checklist))
      was met for the engine built this phase.
