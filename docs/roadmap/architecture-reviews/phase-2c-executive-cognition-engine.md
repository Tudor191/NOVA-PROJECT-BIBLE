# Architecture Review Report — Phase 2C: Executive Cognition Engine

**Phase:** 2C — Executive Cognition Engine (Bible Part 19)
**Completed:** 2026-08-06
**Design document(s):** [docs/design/phase-2c/](../../design/phase-2c/README.md) (00 Executive Cognition Engine, the full Technical Design Document, approved before implementation began, then amended in place with two permanent architectural principles the user established immediately after approval — see §2)
**Author:** Claude (Anthropic), AI-assisted implementation under direct human architectural
direction and review throughout — the design doc's approval, the two permanent
principles established at approval time (policy-driven coordination, long-term
objective optimization), and the standing instruction to pause on any
architecturally-significant fork before proceeding, were all explicit prior user
directives. One such fork was encountered during this phase (a cross-engine Alembic
migration-tracking collision affecting all six engines, discovered during this
phase's own real-Postgres verification) and the user was asked before it was fixed;
every other implementation-time decision recorded below was either a narrow,
in-scope correctness fix or a choice consistent with the already-approved design.

## 1. What was implemented

One independently deployable engine — a full FastAPI service + Arq worker process
pair — plus the `nova-contracts` additions Phase 2C required, plus a cross-cutting
fix to every prior engine's Alembic setup discovered while verifying this one.

**Executive Cognition Engine** (`services/executive-cognition-engine/`) — Bible Part
19. NOVA's coordination layer (ADR-027): it decides which cognitive subsystem should
operate, under which policies, priorities, and constraints — it never produces
reasoning content, knowledge, or plans of its own, and owns no system of record
beyond its own arbitration decisions (`executive_request`, `executive_decision`,
`executive_outcome_report`, `human_override`, plus the standard `outbox_event`).

- **Domain layer** (`domain/`, framework-free, 12 modules): `coordinate.py` (the
  top-level entry point tying scoring, arbitration, goal correlation, and trace
  assembly together for one `ExecutiveRequest`), `priority.py` (the eight-factor
  Cognitive Priority Matrix — Bible Part 6's own seven factors plus
  `long_term_alignment`, ADR-029), `arbitration.py` (§7's ranking algorithm and its
  two runtime policies, `user_goals_override_optimization` and
  `safety_overrides_speed`), `goal_correlation.py` (`long_term_alignment` scoring
  from a request's declared goal and sibling requests sharing it),
  `conflict_resolution.py` (the five-signal procedure — evidence, confidence,
  policy, user objectives, historical outcomes — every step comparing only
  already-published magnitudes, per ADR-028), `context_switching.py`,
  `failure_recovery.py` (reusing Reasoning Engine's own six-action vocabulary),
  `trace.py` (Executive Decision Trace assembly), `contender_registry.py` (the
  bounded, in-process mechanism behind "rank against other in-flight requests," an
  implementation-time addition — see §2), `policy.py` (the three fixed, named
  Executive Policies), `models.py`, `ports.py`.
- **Clients** (`clients/`, one adapter per upstream port): `memory_client.py`,
  `world_model_client.py`, `personal_context_client.py` (projects `WorldModelPort`
  rather than a separate upstream call, the same reuse Reasoning Engine already
  established), `goals_client.py` (an honest Phase 2C placeholder, §5.7). No
  `KnowledgePort` or `CapabilityPort` — named, honest scope omissions (§5.4, §5.8),
  not oversights: this engine has no Phase 2C occasion to consult either.
- **Repository layer**: `PostgresExecutiveRepository` (5 tables; `executive_decision`
  stores the full `ExecutiveDecisionTrace` as one JSONB blob with a handful of
  columns duplicated for querying, mirroring `ReasoningTraceORM`'s own trade-off),
  the standard transactional outbox, a hand-written initial Alembic migration
  matching the design doc's schema exactly.
- **API**: `POST /v1/executive/arbitrate`, `GET /v1/executive/decisions`
  (`/{id}`, `/{id}/explain`), `POST /v1/executive/decisions/{id}/override`. 7 route
  handlers total (5 public, 2 internal) plus 1 mounted metrics endpoint.
- **Events**: publishes `executive.decision.completed`/`.failed`,
  `executive.human_override.applied`; serves `executive.arbitrate.request` and
  `executive.outcome.report` as Event Bus RPCs sharing the exact same
  `coordinate.arbitrate_request` the HTTP route calls.
- **Workers**: `outbox_worker.py` only (every 10s) — the same honest,
  scope-driven one-worker shape Reasoning Engine already established; no other
  domain-specific periodic job exists to run yet.
- **`nova-contracts` additions**: the seven `executive` event-payload subjects
  (`executive.arbitrate.request`/`.reply`, `executive.outcome.report`/`.reply`,
  `executive.decision.completed`/`.failed`, `executive.human_override.applied`),
  `CognitivePriorityScore` (eight factors), `ArbitrationOutcome`,
  `ExecutiveDecisionType`, `ExecutiveOverrideAction`, `OutcomeReportResult`,
  `ContenderSummary`, `ConflictSignals`, and `GoalTier`. Every payload carries
  `schema_version: int = 1` (ADR-024). The generated TypeScript client was
  regenerated and reconfirmed non-stale this review (54 payload files + index,
  zero diff on a fresh regeneration beyond what this phase's own contract changes
  produced).

**66 tests** (44 unit, 13 integration, 9 ADR-023 port-compliance), all passing;
`ruff check` and `mypy` clean across the engine's `src/` and `tests/`; the root
`import-linter`'s existing four contracts all still passing with this engine
included (no fifth contract was needed — this engine introduces no new
forbidden-import class the way ADR-020 did for the AI Model Orchestration Engine).

Two genuine gaps beyond the design doc's literal text were found and fixed during
implementation, both detailed in §2: a missing `user_id` field on
`ExecutiveRequest`/`ExecutiveRequestPayload` (every upstream port this engine calls
is user-scoped, but the wire contract never carried one), and the caller-supplied
`goal_tier` fix that keeps ADR-029's `long_term_alignment` mechanism from being
permanently inert. A third, more significant fix — a cross-engine Alembic
migration-tracking collision — is also detailed in §2, filed as its own item
because it affects five already-shipped engines, not just this one, and was the one
fork this phase paused on before proceeding.

## 2. Why each architectural decision was made

Two new ADRs were filed *before* implementation began, both requested by the user
directly at design-approval time (not discovered during implementation, and already
covered in the amended design doc):

- **ADR-027 (Executive Cognition coordinates, never owns intelligence)** and its
  companions **ADR-028 (defers to specialized-engine authority)** and **ADR-029
  (optimizes long-term user objectives)** together establish the permanent boundary
  this entire engine is built inside: never outperform Reasoning Engine, never
  reinterpret knowledge, never invent conclusions, always assume specialized
  engines know their own domain better than this one does, and always prefer
  whichever valid option best aligns with the user's long-term goals when multiple
  options are otherwise comparable. Every domain module's own docstring names which
  of these three ADRs it exists to satisfy — `conflict_resolution.py` in
  particular is written so every one of its five signals compares only
  already-published magnitudes, never forming an independent judgment.

Three implementation-time corrections went beyond the design doc's literal text.
None rose to the level of a new architecturally-significant decision requiring its
own ADR except the third, which was escalated to the user before being fixed:

- **`ExecutiveRequest`/`ExecutiveRequestPayload` never carried a `user_id`.**
  Found while wiring the API/events layer (task building `domain.coordinate
  .arbitrate_request`'s callers): every port this engine calls (`GoalsPort`, and
  transitively `WorldModelPort`/`MemoryPort`/`PersonalContextPort`) is scoped
  per-user, but the wire contract never carried one — the identical required field
  Reasoning Engine's own `ReasoningRequestPayload.user_id` already carries. Fixed
  by adding it as a required field on both the domain model and the wire payload,
  read directly off the request by `arbitrate_request` rather than threaded as a
  separate parameter, mirroring how Reasoning Engine's own `pipeline.run` reads
  `request.user_id`.
- **`goal_tier` needed to be caller-supplied, not only `GoalsPort`-sourced.**
  Found while building `clients/goals_client.py`: since `GoalsClient.current_goals()`
  is an honest placeholder always returning `[]` (Planning Engine doesn't exist),
  and `domain.coordinate._score_all()` only resolved a contender's goal via that
  port, ADR-029's entire `long_term_alignment` mechanism would have been
  permanently inert (`0.0` for every real request) — silently defeating the second
  permanent principle the user had just established. Fixed by accepting
  `goal_tier` directly on the request, alongside `goal_id`, taking precedence over
  any future `GoalsPort`-sourced value, the same precedence Reasoning Engine's own
  caller-supplied goals already have over its `GoalsPort` result. Verified with a
  regression test asserting non-zero `long_term_alignment` for a caller-supplied
  `goal_tier` even with an empty `GoalsPort`.
- **A cross-engine Alembic version-table collision, affecting all six engines, not
  only this one.** Discovered while verifying this engine's migration against a
  real Postgres instance (this sandbox has one available): every engine's
  `env.py` deliberately keeps `alembic_version` in the connection's default schema
  (a documented, reasoned choice — the engine's own schema doesn't exist yet on a
  fresh database until migration 0001 creates it), but every engine's DSN points at
  the same physical `nova` database, differentiated only by Postgres schema. All
  six engines were therefore sharing one unqualified `alembic_version` table:
  whichever engine's migration ran first against the shared database silently
  claimed the version-tracking row, and every other engine's migration then
  believed it was already at head and created nothing. Verified empirically:
  running all six migrations in sequence against a freshly reset shared database
  produced only one schema (whichever ran first); a bare re-run of the other five
  did nothing. This affects five already-shipped, already-Gate-Reviewed engines
  (Memory, Knowledge, World Model, AI Model Orchestration, Reasoning), not only the
  one built this phase, so the user was asked before it was fixed rather than
  fixed unilaterally. Approved; fixed by giving each engine's `env.py` its own
  `version_table` name (`alembic_version_<engine>`) — no schema or migration
  content changed, only Alembic's own bookkeeping table name. Re-verified against
  the real shared database: all six engines' migrations now run in sequence from a
  clean database and produce all six schemas correctly.

## 3. Tradeoffs considered

- **The contender registry is single-process, in-memory, bounded — not a durable
  admission queue.** §3's Executive Cycle table says "rank against any other
  currently-contending requests" without specifying a mechanism; Phase 2C has no
  durable, cross-process admission queue (that is Phase 6's Cognitive Load
  Management). `domain.contender_registry.ContenderRegistry` is the simplest
  mechanism that makes this real: each served `executive.arbitrate.request` call
  registers itself and returns whatever other requests are still presumed in
  flight, within a `Settings`-tunable TTL (default 30s) or max-entry cap (default
  200). A request leaves the registry when its optional outcome report arrives, or
  once its TTL lapses regardless. This was an implementation-time addition, not
  specified by the design doc's own text — added because "rank against other
  in-flight requests" would otherwise have no real caller-facing mechanism at all,
  and documented back into the design doc as an amendment (§4) once built, the
  same practice every genuine mid-implementation design clarification in this
  project has followed.
- **`ExecutiveDecisionTrace` is one combined object, not a `Decision`/`Trace`
  split like Reasoning Engine's.** The design doc's own §19 data model names
  exactly one table for decisions; `GET /v1/executive/decisions/{id}/explain`
  therefore returns the identical object `GET .../{id}` does, since there is no
  separate, narrower explanation object to return instead — a genuine structural
  difference from Reasoning Engine, not an oversight, documented explicitly in the
  route handler's own docstring.
- **`ESCALATED` is fully modeled with no reachable code path yet.**
  `conflict_resolution.resolve_conflict` (the only function that can produce it) is
  specified in full and unit-tested, but `coordinate.arbitrate_request` never
  calls it — Phase 2C's real, testable scenario (two contenders competing for the
  same resource budget) is resource contention, never genuine conflict between two
  engines' conclusions. Named explicitly rather than silently left unconnected;
  `ArbitrationOutcome.ESCALATED` and Human Override's endpoint are ready for it the
  moment a real conflict source exists.
- **`GoalsPort` remains Phase 2C's honest placeholder** (§5.7): Planning Engine
  doesn't exist yet, so goals are caller-supplied on `ExecutiveRequest` rather than
  fetched from a real RPC — the identical pattern ADR-026 established for
  Reasoning Engine's own `GoalsPort`. The ADR-023 port-compliance suite asserts
  this explicitly, both implementations returning `[]` unconditionally as a
  genuine behavioral identity, not a silently-skipped difference.
- **This engine ships one background worker, not two or three**, matching
  Reasoning Engine's own precedent exactly, for the identical reason: no periodic
  domain job exists to run yet, a direct consequence of scope rather than an
  oversight.

## 4. Known limitations

The engine's own README carries the full list under "Known limitations (Phase 2C)."
Restated here for a reader who doesn't cross-reference:

- **`GoalsPort` is an honest Phase 2C placeholder** (§3) — the caller-supplied
  `goal_tier` fix (§2) keeps `long_term_alignment` real in the meantime.
- **The contender registry is single-process, in-memory, bounded** (§3) — Phase
  6's Cognitive Load Management replaces it wholesale, it does not extend it.
- **No progress-reporting channel exists from Reasoning Engine or AI Model
  Orchestration Engine back to this engine yet** — `context_switching.py` is
  specified in full and unit-tested, but no real caller supplies
  `current_progress`.
- **`ESCALATED` has no reachable code path yet** (§3) — `conflict_resolution.py`
  is real and tested in isolation; nothing in Phase 2C's own arbitration flow
  triggers it.
- **`conflicts_escalated_total` and `failures_total` are declared but not yet
  incremented**, the direct consequence of the point above.
- **No read-through cache** beyond what the Postgres repository provides
  directly, mirroring every prior engine's own accepted gap.
- **`postgres_executive_repository.py` has no committed pytest coverage against a
  real Postgres instance** — every prior engine's own committed suite has the
  identical gap (fakes only). This phase's own ad hoc verification against this
  sandbox's real Postgres 16 instance (§2, §5 of the Gate Review) went further than
  any prior phase — a genuine end-to-end arbitrate → persist → retrieve → override
  round trip, plus the outbox dispatcher publishing through a real event bus
  connection — but it is still not a committed, CI-enforced test.

## 5. Technical debt introduced, if any

None accepted as debt in the traditional sense — consistent with every prior
phase's own finding. The candidates evaluated are all deliberate, documented scope
decisions:

- **`clients/personal_context_client.py` projects `WorldModelPort`'s own
  snapshot**, the identical reuse Reasoning Engine already established, named
  explicitly in the client's own module docstring.
- **Three real gaps were found and fixed during this phase's own work, not left
  open**: the missing `user_id` field, the `goal_tier` precedence fix, and the
  cross-engine Alembic collision (§2). All three are closed, with regression tests
  for the first two and direct, repeated verification against a real shared
  Postgres database for the third.

## 6. Future improvements

- **Wire a real progress-reporting channel from Reasoning Engine / AI Model
  Orchestration Engine** (§3, §4) so `context_switching.py`'s already-specified
  formula has a real `current_progress` signal to evaluate.
- **Once Planning Engine (Phase 3) exists, migrate `GoalsPort` from its Phase 2C
  placeholder to a real RPC-backed port** (§3, §4), per the same migration path
  ADR-026 already named for Reasoning Engine's own `GoalsPort`.
- **Extend `contender_registry.py` into Phase 6's real Cognitive Load Management**
  once a durable, cross-process admission queue is actually needed (§3, §4) —
  replacing it, not extending it in place, per the design doc's own §4 amendment.
- **Increment `conflicts_escalated_total`/`failures_total`** once a real caller
  exercises the conflict-resolution or failure-recovery code paths (§4).
- **Build a committed test suite against a real Postgres instance**, for this
  engine and every prior one (§4) — this phase's own ad hoc verification went
  further than any prior phase (a full round trip including the outbox dispatcher
  against a real event bus) but is still not committed or CI-enforced.
- **Run the now-seven-service compose stack in a Docker-capable environment**
  (carried forward from every prior phase's Gate Review) to capture a first real
  latency measurement — still entirely unmeasured against real infrastructure.

## 7. Risks

- **Operational:** `main.py`/`workers/` have been booted against this sandbox's
  real, native Postgres, verified end to end including the outbox dispatcher
  publishing through a real (in-memory-backed) event bus connection — stronger
  evidence than any prior phase had, but still not against the full seven-service
  Docker Compose stack (no Docker daemon in this environment), so
  first-boot-against-full-real-infra issues (NATS, Redis-backed Arq scheduling,
  seven services running concurrently) remain unverified.
- **Architectural:** the contender registry's TTL-based eviction (§3) means a
  caller that never sends an optional outcome report, and whose request outlives
  the TTL, silently stops being counted as a contender for later arbitrations —
  an accepted tradeoff (better than pinning a stale contender forever) but a real
  behavior a future reader should understand, not just infer from the code.
- **Cross-engine:** the Alembic version-table fix (§2) touches five already-shipped
  engines' `env.py` files. Verified correct against a real shared database this
  review, but this is the first time this exact multi-engine-migration scenario
  has ever been exercised in this project's history — a genuine, previously-latent
  defect that existed silently since Phase 1 and was only caught now because this
  phase's own verification happened to run two engines' migrations back-to-back
  against the same live database for the first time.
- **Scale:** performance targets remain unmeasured against real infrastructure,
  the same unmeasured-until-Docker status every prior phase's performance target
  still carries.

## 8. Compatibility with the NOVA Project Bible

- **Executive Cognition Engine (Bible Part 19):** implemented at the breadth the
  Phase 2C design doc scoped — the Cognitive Priority Matrix in full (§6, all
  eight factors including ADR-029's `long_term_alignment`), the arbitration
  algorithm and both runtime policies (§7), goal correlation (§8), conflict
  resolution's five-signal procedure (§10), context switching (§11), executive
  policies (§12), human override (§13), failure handling (§14), and the Executive
  Decision Trace (§18) as structured metadata, never a copy of a coordinated
  engine's own domain content.
- **ADR-025's Personal Edition principle** required no retrofit: this engine is
  single-user by default and ADR-029's own long-term-optimization principle is
  itself framed explicitly as a Personal Edition default, with future enterprise
  configurability named but not built.
- **ADR-027/028/029's own boundary**, filed specifically to govern this phase,
  held without amendment — verified structurally by direct inspection of every
  domain module's own docstring naming which principle it satisfies, not merely
  asserted by the design doc's prose.
- All Known Limitations (§4) are, per the user's standing instruction carried
  forward from every prior phase, deliberately preferred over any speculative
  implementation of behavior the design doc did not specify.

## Sign-off

- [x] All items in the engine's design-doc review checklist
      ([docs/design/phase-2c/README.md](../../design/phase-2c/README.md)) are
      satisfied — the design was approved before implementation began, amended in
      place with two user-established permanent principles before implementation,
      and no deviation occurred beyond the three corrections noted in §2.
- [x] The phase's Definition of Done
      ([SAD 15 §4](../../architecture/15-development-workflow.md#4-definition-of-done-per-pr))
      was met: implementation, tests, observability, and documentation delivered
      together, not as follow-up work.
- [x] The per-subsystem deliverable checklist
      ([SAD 15 §9](../../architecture/15-development-workflow.md#9-per-subsystem-deliverable-checklist))
      was met for the engine built this phase.
