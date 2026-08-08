# nova-service-kit Boilerplate Extraction Proposal

**Status: Proposed — pending user review and approval. No implementation, refactor,
or production code change of any kind has been made. This document only.**

**Scope: STEP 3 of the Project Health Review's approved 5-step plan**
([project-health-review-2026-08.md §18](../../roadmap/architecture-reviews/project-health-review-2026-08.md#18-complexity-and-code-duplication-analysis),
[§24 items 5-6](../../roadmap/architecture-reviews/project-health-review-2026-08.md#24-recommended-refactorings),
[§27.2](../../roadmap/architecture-reviews/project-health-review-2026-08.md#272-a-shared-nova-service-kit-package-for-the-700-lines-of-proven-safe-to-extract-boilerplate)).
Per direct instruction: identify, classify, and evaluate the ~700 lines of
boilerplate duplication the Review found; propose what to extract and what to
leave alone; do not implement, refactor, or touch production code, tests, CI,
schemas, or ADRs in this step.

---

## 0. Executive summary

The Project Health Review (August 2026) quantified ~700 lines of pure
structural boilerplate duplicated across four file patterns
(`api/health.py`, `repository/db.py`, `repository/outbox_dispatcher.py`,
`workers/__init__.py`) and separately flagged a smaller, different kind of
duplication risk: five hand-copied domain types shared between
`executive-cognition-engine` and `reasoning-engine`.

This proposal re-verifies every one of those claims directly against the
current code (MD5 hashes, line-by-line diffs, direct reads — not a repeat of
the Review's own numbers) and finds them **substantially accurate, with three
material refinements** that change what should actually be extracted:

1. **`repository/outbox_dispatcher.py`'s divergence is deeper than naming.**
   `memory-engine` doesn't just call its dispatcher something else
   (`dispatch_pending` vs. `dispatch_ready_events`) — it bypasses the
   repository-port abstraction entirely and talks to SQLAlchemy directly. Its
   repository has no `list_dispatch_ready`/`mark_dispatched` methods at all.
   A shared extraction requires fixing this prerequisite first, for one
   engine only.
2. **Of the five "hand-duplicated" domain types the Review named, only three
   are actually safe to unify.** `Goal` has already diverged
   (`executive-cognition-engine` added `goal_tier`; `reasoning-engine` didn't)
   — a real business difference, not an oversight. `HumanOverrideRequest` was
   never actually the same type: it carries different foreign keys pointing
   at different aggregates (`executive_decision_id` vs.
   `reasoning_process_id`) and references two enums
   (`ExecutiveOverrideAction`/`OverrideAction`) that `nova_contracts` already
   keeps **deliberately separate**, by explicit, pre-existing design (§2.6.5
   below). Only `MemoryReference`, `WorldModelSnapshot`, and `PersonalContext`
   are field-for-field identical today.
3. **One additional, smaller duplication exists that the Review didn't name
   as a separate line item**: `BoundEventBus(...)` construction is repeated
   18 times (9 `main.py` + 9 `workers/__init__.py`), 5-6 lines each. Unlike
   the four named patterns, this one already has a correct, existing owner —
   `nova_eventbus_sdk`, which already defines `BoundEventBus` — so it needs
   no new package at all.

Five extractions are proposed, three at near-zero risk, one gated on a
one-engine prerequisite fix, one deferred to a lower-priority track because
it touches domain types rather than pure infrastructure. A `workers/__init__.py`
full-file extraction is evaluated and **explicitly not recommended** — most of
its bulk is legitimate per-engine wiring, not boilerplate, confirmed by direct
inspection of all 8 files (§2.4). A new package, `nova-service-kit`, is
proposed for the three infrastructure extractions that have no correct home
in any existing package — not as a generic dumping ground, but with the same
narrow, single-sentence scope statement every other shared package already
has (§5).

**Net estimated Production SLOC impact: a reduction of roughly 440-520 lines**
across the engines, against the Review's own ~700-line figure — the
difference is that ~700 counts every duplicated copy as pure loss, while this
proposal's estimate nets out the lines that don't disappear but *move* into
the new package's own canonical implementation (§14 gives the extraction-by-
extraction accounting).

---

## 1. Methodology

Every claim in this document was checked against the actual code in this
session, using the same standard applied to Project Health Review and both
Gate Reviews: **verify before trusting documentation, including this
project's own prior documentation.**

- **Byte-identity claims** (`api/health.py`, `repository/db.py`): `md5sum`
  across every engine's copy, then `diff`/`sed`-normalized comparison on the
  code body with docstrings stripped, to distinguish "identical code,
  different docstring" from "actually different."
- **Near-identity claims** (`repository/outbox_dispatcher.py`): the
  `dispatch_ready_events` function body was extracted from each of the 8
  files, type names and the `source_engine` default normalized out via
  `sed`, then hashed — confirming the *logic* is identical even where
  parameter types differ.
- **Domain-type duplication claims** (`Goal`/`MemoryReference`/etc.): every
  named class was read directly, field by field, in both
  `executive-cognition-engine/domain/models.py` and
  `reasoning-engine/domain/models.py`, including tracing `ExecutiveOverrideAction`/
  `OverrideAction`/`ArbitrationOutcome` back to their actual definitions in
  `nova_contracts`.
- **"Where would this live" claims**: `packages/nova-observability/pyproject.toml`
  and `packages/nova-eventbus-sdk/src/`'s actual file list were read directly,
  not assumed from the package names.
- **Scaffold-origin claims**: `tools/scaffold-engine.py` was read in full to
  confirm which of the four boilerplate patterns are machine-perpetuated (the
  scaffold tool writes them into every new engine) versus hand-copied by each
  engine's author.

No claim below is carried forward from the Project Health Review without
independent re-verification this session.

---

## 2. Duplication inventory (verified findings)

### 2.1 `api/health.py`

**Verified: 9 of 10 engines byte-identical (MD5-confirmed), `nova-core`
genuinely different.**

```
908dd2e83d1312b146b264a082a06de7  communication-engine, knowledge-engine, memory-engine,
                                   ai-model-orchestration-engine, reasoning-engine,
                                   executive-cognition-engine, world-model-engine,
                                   personality-engine, perception-engine
7829cb7ac0fce2ac2cf16d773e609939  nova-core  (different hash)
```

The standard copy (27 lines, verbatim in every one of the 9 engines):

```python
router = APIRouter(prefix="/internal", tags=["health"])

class HealthResponse(BaseModel):
    status: str

class ReadinessResponse(BaseModel):
    ready: bool

@router.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status="healthy")

@router.get("/readiness")
async def readiness(request: Request) -> ReadinessResponse:
    return ReadinessResponse(ready=bool(getattr(request.app.state, "ready", False)))
```

`nova-core`'s version (45 lines) is a real, deliberate variant, not drift: it
reads `request.app.state.host` (a `NovaHost`) and adds `uptime_seconds`/
`boot_phase` to both response models — fields no other engine has, because
`nova-core` is the boot-sequence process itself, the one engine where
"healthy" needs boot-phase detail. This must become an explicit override
parameter, not be silently dropped.

**Root cause of the 9x duplication, confirmed**: `tools/scaffold-engine.py`
line ~350 embeds this exact 27-line string as `_HEALTH_PY` and writes it
verbatim into every new engine's `api/health.py`. This is the one pattern of
the four that is machine-perpetuated, not hand-copied — every future engine
scaffolded before this fix ships will add a 10th (or 11th, 12th...) identical
copy.

**Risk: near-zero.** Behavior is provably identical today across all 9; a
shared factory changes nothing observable for any of them.

### 2.2 `repository/db.py`

**Verified: 9 of 9 identical below the module docstring.** Every file's code
from `from __future__ import annotations` onward hashes identically
(`f7c9207a...`); only the two-line module docstring (citing a different
design-doc section per engine) differs.

```python
def create_engine(dsn: str) -> AsyncEngine:
    return create_async_engine(dsn, pool_pre_ping=True)

def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
```

19 lines per file, 9 files (`nova-core` has no Postgres schema and no `repository/`
directory at all — confirmed, it's a pure boot/heartbeat engine).

Unlike `health.py`, this one is **not** scaffold-generated (`scaffold-engine.py`
has no `_DB_PY` template) — each engine's author hand-wrote it, presumably by
copying the previous engine's file and editing the docstring. Zero behavioral
variation found across all 9.

**Risk: near-zero.** No parameters, no engine-specific behavior of any kind.

### 2.3 `repository/outbox_dispatcher.py` — core loop

**Verified: `dispatch_ready_events`'s function body is identical (post type-name
normalization) across 7 of 8 engines that have this file. `memory-engine` is a
real implementation divergence, not just a naming one.**

8 engines have this file (`personality-engine` and `nova-core` don't — neither
runs a transactional outbox: `personality-engine`'s domain has no async
cross-engine side effects to defer, confirmed by grep finding zero
`outbox`/`Outbox` references anywhere in its `src/`). Of the 8:

- **5 engines** (`ai-model-orchestration-engine`, `communication-engine`,
  `executive-cognition-engine`, `perception-engine`, `reasoning-engine`) have
  a single 53-line file containing exactly one function, `dispatch_ready_events`.
- **2 engines** (`knowledge-engine`, `world-model-engine`) have an 82-87 line
  file with *two* functions: `apply_pending_graph_writes` (their own two-phase
  saga's graph-write step — genuinely engine-specific, touches
  `nova_graphstore_sdk` and each engine's own `object_graph`/domain logic) and
  `dispatch_ready_events`, exactly the same shape as the other 5.
- **1 engine** (`memory-engine`) has a 78-line file with a differently-named
  function (`dispatch_pending`) that does not call `repository.list_dispatch_ready()`/
  `repository.mark_dispatched()` at all — it takes a raw `session_factory`
  and issues `select(OutboxEventORM)`/`update(OutboxEventORM)` directly.

Normalizing away repository-type names, metrics-type names, and the
`source_engine` default string, the `dispatch_ready_events` function body
hashes **identically across all 7 engines that have it** — confirmed by direct
hash comparison, not estimation:

```python
async def dispatch_ready_events(
    repository: <Repo>,
    bus: EventBus,
    *,
    source_engine: str = "<engine>",
    batch_size: int = DEFAULT_BATCH_SIZE,
    metrics: <Metrics> | None = None,
) -> int:
    dispatched = 0
    rows = await repository.list_dispatch_ready(limit=batch_size)
    for row in rows:
        envelope = EventEnvelope(
            event_id=row.id, subject=row.subject, source_engine=source_engine,
            correlation_id=row.correlation_id, causation_id=row.causation_id,
            payload=row.payload,
        )
        await bus.publish(envelope)
        await repository.mark_dispatched(row.id)
        dispatched += 1
        if metrics is not None:
            metrics.outbox_dispatched_total.add(1, {"subject": row.subject})
    return dispatched
```

**Root cause of `memory-engine`'s divergence, confirmed**: its
`MemoryRepository` protocol (`domain/ports.py`) simply never grew
`list_dispatch_ready`/`mark_dispatched` methods — grep for both names across
its `domain/ports.py` and `repository/postgres_memory_repository.py` returns
zero matches. This isn't a stylistic choice visible anywhere in the code or
its docstrings; it's an engine that was built before the other 7 converged on
this exact port shape and never got backported.

**Risk: low for 7 engines, requires a one-engine prerequisite for the 8th.**
Extracting the shared loop for the 7 conforming engines is exactly as safe as
§2.1/§2.2. Including `memory-engine` requires first adding the two port
methods to its repository (a small, mechanical, well-precedented change —
every other repository already has this exact shape) — a real but bounded and
low-risk prerequisite, not a blocker to the other 7.

### 2.4 `workers/__init__.py` skeleton

**Verified: a real but partial pattern.** All 8 files that have one
(`personality-engine` and `nova-core` again excluded, same reason as §2.3)
share:

- An identical import block (`arq.cron`, `arq.connections.RedisSettings`,
  `nova_eventbus_sdk.BoundEventBus`/`get_event_bus`,
  `nova_observability.configure_observability`/`get_logger`).
- `_SETTINGS = Settings()` / `logger = get_logger(...)` module-level pair.
- `async def startup(ctx)`'s first three lines (call `configure_observability`,
  log a starting message, comment explaining why a worker process needs its
  own observability setup) and last line (`ctx["metrics"] = create_metrics()`).
- `async def shutdown(ctx)`'s log-and-close-in-reverse-order shape.
- The `class WorkerSettings` skeleton itself (`functions`, `on_startup`,
  `on_shutdown`, `redis_settings` attribute names).

Directly read `perception-engine`'s (74 lines, simplest) and
`knowledge-engine`'s (115 lines, most complex — 3 extra stores: vector index,
graph store, embedding provider, 3 cron jobs instead of 1) files side by side
to confirm: **everything beyond the ~20-25 line skeleton above is genuinely
engine-specific** — which repository/store types get constructed, what extra
resources need connecting (`knowledge-engine`'s vector index and graph store;
`world-model-engine`'s graph store only; most engines, neither), and — the
least compressible part — each engine's own `cron_jobs` list, which varies
from 1 job (most engines) to 3 (`knowledge-engine`: outbox dispatch, embedding
pass, maintenance sweep, three different schedules).

**This confirms the Review's own conclusion**: legitimate but lower-priority.
Line counts range 74-117 across the 8 files specifically *because* the bulk is
real wiring, not copy-paste. A full-file factory extraction here would need
enough parameterization (injectable extra-resource setup/teardown callables,
injectable cron-job lists, injectable extra ctx keys) that the resulting
abstraction would be closer to a small framework than a boilerplate remover —
exactly the "obscures ownership" risk this proposal was asked to guard
against. **Not recommended as a full-file extraction** (§6). The one piece of
this file that *is* cleanly extractable is covered separately, next.

### 2.5 `BoundEventBus` construction (not named as a separate line item in the
Review, found this session)

**Verified: 18 call sites, byte-identical shape, 5-6 lines each** — 9 in each
engine's `main.py`, 9 more in the corresponding `workers/__init__.py` (the
same construction, once for the FastAPI process, once for the worker
process):

```python
bus = BoundEventBus(
    get_event_bus(),
    engine_name="<engine-name>",
    publishable_subjects=PUBLISHABLE_SUBJECTS,
    subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
)
```

Unlike the four patterns above, this one already has a correct, existing
owner: `nova_eventbus_sdk` already defines both `BoundEventBus` and
`get_event_bus` (`packages/nova-eventbus-sdk/src/nova_eventbus_sdk/boundary.py`,
`factory.py`). A one-line convenience factory belongs there, not in a new
package — this is squarely within that package's existing, already-documented
responsibility ("Event Bus abstraction"), not scope creep.

**Risk: near-zero**, same profile as §2.1/§2.2, and it needs no new package
at all.

### 2.6 Hand-duplicated cross-engine domain types — refined findings

The Review (§3.4) named five types hand-duplicated between
`executive-cognition-engine` and `reasoning-engine`'s `domain/models.py`, with
no shared type in `nova_contracts`: `Goal`, `MemoryReference`,
`WorldModelSnapshot`, `PersonalContext`, `HumanOverrideRequest`. Reading all
five, field by field, in both files:

**2.6.1 `Goal` — already diverged, must NOT be unified.**
`executive-cognition-engine`'s copy has an extra field,
`goal_tier: Literal["ad_hoc", "established"] = "ad_hoc"` (added per ADR-029 §8
for its own long-term-alignment scoring); `reasoning-engine`'s does not. This
is exactly the case the Review itself already flagged as unsafe to touch
("not the ones already legitimately diverging") — confirmed by direct
reading, not assumed. A shared type today would either force
`reasoning-engine` to carry a field it has no use for, or require deciding
whether `reasoning-engine` should adopt goal-tier scoring too — a real product
question, not a refactor.

**2.6.2 `MemoryReference` — currently identical, genuine candidate.**
```python
class MemoryReference(BaseModel):
    memory_id: UUID
    summary: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
```
Field-for-field identical in both files (confirmed by direct read), and — a
detail worth naming since it directly matches what this proposal was asked
to pay attention to — this one already *is* the narrow ID+summary pattern
(§2.9), just hand-duplicated instead of shared.

**2.6.3 `WorldModelSnapshot` — currently identical, genuine candidate.**
8 fields (`user_id`, `objective`, `project_id`, `device`, `task`, `activity`,
`confidence`, `degraded`), identical in both files including the
`degraded: bool = False` semantics (both docstrings independently describe it
identically: "not an error, a signal to proceed... rather than failing").

**2.6.4 `PersonalContext` — currently identical, genuine candidate.**
5 fields (`user_id`, `objective`, `project_id`, `device`, `task`), identical
in both files. Both docstrings independently note it's a placeholder pending
a real Digital Twin Engine (Bible Part 16) — a shared type would need exactly
one adapter changed later, not two, when that engine ships.

**2.6.5 `HumanOverrideRequest` — NOT actually a duplicate. Must NOT be
unified.** This is the one place this proposal's verification materially
corrects the Review's framing. The two classes share a name and a similar
shape but reference **different foreign keys pointing at different
aggregates**:

```python
# executive-cognition-engine
executive_decision_id: UUID
action: ExecutiveOverrideAction
redirect_outcome: ArbitrationOutcome | None = None

# reasoning-engine
reasoning_process_id: UUID
action: OverrideAction
redirect_alternative_id: UUID | None = None
```

`executive_decision_id` and `reasoning_process_id` are not the same concept
under different names — they identify two different aggregate roots owned by
two different engines. And critically, `ExecutiveOverrideAction`/
`OverrideAction` — traced to their real definitions in
`nova_contracts.events.executive_cognition`/`nova_contracts.events.reasoning`
— are **already, explicitly, deliberately kept as two separate enums**, with
the reasoning stated directly in `ExecutiveOverrideAction`'s own docstring:

> "identical shape to Reasoning Engine's own `OverrideAction`... redefined
> here rather than imported so each engine's contracts module stays
> self-contained, the same convention every engine's own enums already follow
> even where two engines' vocabularies coincide."

This is a real, pre-existing, already-documented architectural decision this
proposal must respect, not override. Unifying `HumanOverrideRequest` would
mean either forcing two different foreign-key semantics into one type, or
picking one engine's action-vocabulary to be canonical over the other's —
exactly the "hidden cross-engine dependency" this proposal was asked to avoid
creating. **Not a candidate.**

### 2.7 `ConfidenceTier` triple representation

**Verified: three genuinely separate representations of the same 4-value
vocabulary** (`high`/`medium`/`low`/`unknown`):

1. `nova_contracts.events.personality.ConfidenceTier` — a `StrEnum`, the
   closest thing to a canonical definition today.
2. `personality-engine`'s own separate `ConfidenceTier(StrEnum)` in its
   `domain/models.py` — same 4 values, not imported from `nova_contracts`.
3. `perception-engine`'s `ConfidenceTier = Literal["high", "medium", "low",
   "unknown"]` — a bare type alias, not even an enum.

Real duplication, but **not a clean extraction candidate today** for a
structural reason confirmed by reading `nova_contracts`' own layout: every
existing submodule is `nova_contracts.events.<engine-name>` — one per
engine's own event namespace (`ai_model_orchestration.py`, `communication.py`,
..., `personality.py`, `reasoning.py`, etc.). There is currently **no neutral
home** for a vocabulary two unrelated engines both need — importing from
`nova_contracts.events.personality` would misleadingly imply
`perception-engine` depends on personality-engine's event contracts, which it
does not. Fixing this needs a naming/ownership decision (e.g., a new
non-event-specific `nova_contracts` module) before it can be extracted safely
— the same "needs sequencing" caution the Review already applied to the
weighted-composite-scorer pattern below. **Deferred, not proposed for this
pass** (§6).

### 2.8 Weighted composite scorer pattern — restated, not re-litigated

The Review found the same conceptual algorithm ("weighted-sum composite
score, then select/sort") independently implemented three times
(`ai-model-orchestration-engine/domain/router.py`'s `_score`,
`reasoning-engine/domain/confidence.py`'s `_weighted_composite`,
`memory-engine/domain/ranking.py`'s `rank`), each handling a missing input
signal differently (redistribute weight, treat as zero, default to a fixed
midpoint). This is **not boilerplate duplication** — it's three independent,
reasonable domain-logic implementations that happen to share a shape. This
proposal did not re-verify the three missing-data semantics in depth (that
reconciliation is domain-logic work, out of scope for a boilerplate
proposal), but confirms the Review's own conclusion still holds: unifying
before deciding which missing-data policy is correct would silently change
at least two engines' real behavior. **Not a candidate for this proposal.**

### 2.9 The narrow ID+summary cross-engine value-object pattern — verify, then
leave alone

This is the pattern this proposal was specifically asked to examine, and it
is the **strongest argument in the entire codebase for *not* extracting
something**. Directly compared perception-engine's real `IdentityObservation`
(the source) against `world-model-engine`'s `PresentIdentitySignal` (the
cross-engine consumer's local translation):

```python
# perception-engine/domain/models.py — the real thing, 7+ fields
class IdentityObservation(BaseModel):
    observation_id: UUID
    user_id: UUID
    identity_id: UUID | None = None
    fused_confidence: float
    confidence_tier: ConfidenceTier
    per_modality_signals: dict[str, object]
    # ...

# world-model-engine/domain/models.py — the ACL translation, 3 fields
class PresentIdentitySignal(BaseModel):
    identity_id: UUID | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    modality_summary: str
```

`PresentIdentitySignal`'s own docstring states the intent directly: "a direct
pass-through... never a re-interpretation," deliberately omitting
`template_ciphertext`, `per_modality_signals`, and `observation_count`. This
is asymmetric narrowing — one engine's rich internal model translated down to
exactly what a *different* consuming engine needs, and nothing more. It is
categorically different from §2.6's `MemoryReference`/`WorldModelSnapshot`/
`PersonalContext`, which are two *peer* engines independently solving the
*identical* translation problem from the *identical* upstream input and
landing on (for now) the same shape by coincidence, not by asymmetric design.

Sharing `PresentIdentitySignal`-style types would re-couple
`world-model-engine` to `perception-engine`'s exact schema — the opposite of
what this pattern exists to prevent, and a textbook example of the "hidden
cross-engine dependency" this proposal must not introduce. Confirmed present,
identically motivated, in every other cross-engine boundary in the codebase
(`executive-cognition-engine`'s `MemoryReference`/`WorldModelSnapshot` *as
narrowings of Memory/World-Model's own real aggregates*, `reasoning-engine`'s
`KnowledgeReference`). **Must not be touched** — covered in detail in §7.

---

## 3. Evaluation framework

Four questions applied to every duplication pattern found, in order — failing
any one of the first three removes a pattern from consideration regardless of
line count:

1. **Is it actually the same thing, or does it only look the same?**
   (§2.6.5's `HumanOverrideRequest` fails here — same name, different
   aggregates.)
2. **Is the duplication accidental (copy-paste) or intentional (anti-corruption
   translation, deliberate per-engine divergence)?** (§2.9's ACL pattern and
   §2.6.1's `Goal` fail here — intentional, must stay separate.)
3. **Does a correct, narrow, already-motivated owner exist — or would this
   need a brand-new home invented just to hold it?** (§2.5's `BoundEventBus`
   helper passes cleanly via `nova_eventbus_sdk`; §2.7's `ConfidenceTier`
   fails today because no neutral `nova_contracts` home exists yet.)
4. **Does extracting it remove a real, named future cost** (a cross-cutting
   change today requiring N independently-drifting edits) **without adding a
   comparable new one** (a shared abstraction whose own change now requires
   coordinating N engines' releases)?

Only patterns passing all four are proposed below.

---

## 4. Proposed extractions

### Extraction A — `make_health_router()`

- **Current duplication**: §2.1 — 9 byte-identical 27-line files (243 lines)
  + `nova-core`'s own 45-line variant (288 lines total across 10 files).
- **Proposed owner/package**: `nova-service-kit` (new — see §5).
- **Public interface**:
  ```python
  def make_health_router(
      *,
      health_status: Callable[[], str] = lambda: "healthy",
      readiness_check: Callable[[Request], bool] | None = None,
      extra_health_fields: Callable[[], dict[str, object]] | None = None,
  ) -> APIRouter: ...
  ```
  Default behavior reproduces the 9-engine standard exactly (`health_status`
  returns `"healthy"` unconditionally, `readiness_check` defaults to reading
  `request.app.state.ready`). `nova-core` passes `health_status`,
  `readiness_check`, and `extra_health_fields` callables reading from
  `request.app.state.host`, making its divergence an explicit, visible
  parameterization instead of a silent one-off — exactly the outcome the
  Review's own §24 item 5 recommended.
- **Dependency direction**: `nova-service-kit` depends only on `fastapi` and
  `pydantic` (already-shared framework deps every engine already has); no
  engine-specific imports. Each engine's `main.py` imports
  `make_health_router` and calls it — same direction every engine already
  depends on `nova_observability`/`nova_eventbus_sdk`.
- **Affected engines**: all 10 (9 unchanged behavior, `nova-core` explicit
  override).
- **Migration strategy**: (1) build and test `make_health_router()` in
  isolation against the 9-engine default behavior and `nova-core`'s override
  behavior; (2) cut over one low-traffic engine first (recommend
  `perception-engine`, newest, smallest blast radius) and verify its existing
  `tests/integration/test_health.py` passes unmodified against the new
  router; (3) cut over the remaining 8 engines in any order, each independently
  releasable; (4) update `tools/scaffold-engine.py`'s `_HEALTH_PY` template so
  every future engine is born calling the shared factory, closing the
  duplication's actual root cause (§2.1).
- **Testing strategy**: every engine's existing `tests/integration/test_health.py`
  is the regression test — it must pass unmodified (same `/internal/health`,
  `/internal/readiness` responses) after cutover. `nova-service-kit` gets its
  own new unit tests covering the default behavior and each override
  parameter independently. No existing test file needs editing beyond, at
  most, an import-path change if a test imports `HealthResponse` directly
  (none currently do, confirmed by grep).
- **Expected reduction**: 288 lines (10 files) → ~45 lines (canonical, with
  override support) + ~10×2 lines (call sites) ≈ 65 lines. **Net: ~223 lines.**
- **Architectural risks**: none identified beyond the general new-package risk
  covered in §10. `nova-core`'s override path is the only behavioral surface
  requiring real testing attention.
- **Why preferable to duplication**: identical behavior maintained by 9
  independent copies today; the Review's own example still applies — adding a
  readiness sub-check (a real, plausible future need per §27.3's middleware
  discussion) currently means 9-10 separate edits, each a chance to miss one.

### Extraction B — `create_engine_and_session_factory(dsn)`

- **Current duplication**: §2.2 — 9 files × 19 lines = 171 lines, code-identical.
- **Proposed owner/package**: `nova-service-kit`.
- **Public interface**:
  ```python
  def create_engine_and_session_factory(
      dsn: str,
  ) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]: ...
  ```
  (Or two separate functions, `create_engine`/`create_session_factory`,
  matching the current two-function shape exactly — a decision left open for
  implementation-time review, not a proposal-stage architectural question.)
- **Dependency direction**: depends only on `sqlalchemy` (already a direct
  dependency of every engine with a Postgres schema). No engine-specific
  imports.
- **Affected engines**: 9 (all except `nova-core`, which has no Postgres
  schema).
- **Migration strategy**: purely mechanical — replace each engine's
  `repository/db.py` body with an import and re-export (or remove the file
  entirely and have callers import from `nova_service_kit` directly; either
  is low-risk, the choice affects only import-path length, not behavior).
  No prerequisite work, no sequencing dependency on Extraction A or C — can
  ship independently, in any order, same day.
- **Testing strategy**: zero behavioral surface to test beyond "the returned
  engine/session-factory still work" — every engine's existing repository
  integration tests (fake-backed) and, once STEP 2's real-infra checkpoint
  clears, the real-Postgres tests already exercise this function
  transitively. `nova-service-kit` gets one small unit test confirming the
  returned engine has `pool_pre_ping=True` and the session factory has
  `expire_on_commit=False`, the two non-default parameters that actually
  matter.
- **Expected reduction**: 171 lines (9 files) → ~15 lines (canonical) + ~9×2
  lines (call sites, mostly unchanged since callers already call
  `create_engine`/`create_session_factory` by these exact names). **Net:
  ~138 lines.**
- **Architectural risks**: none identified — this is the single lowest-risk
  extraction in this proposal, with zero parameters and zero behavioral
  variation across all 9 existing copies.
- **Why preferable to duplication**: same profile as Extraction A — a future
  change (e.g., adding statement-level timeout configuration, or connection-
  pool tuning learned from the STEP 2/STEP 4 real-Postgres verification work)
  would today require 9 separate edits to files that have never once needed
  to differ.

### Extraction C — shared `dispatch_ready_events()` loop (+ `memory-engine`
prerequisite)

- **Current duplication**: §2.3 — 7 engines' identical 26-line function
  bodies (182 lines) + `memory-engine`'s 78-line divergent file.
- **Proposed owner/package**: `nova-service-kit`.
- **Public interface**: a generic function parameterized over a
  `Protocol` describing exactly the two methods every conforming repository
  already has:
  ```python
  class OutboxRepository(Protocol):
      async def list_dispatch_ready(self, *, limit: int) -> Sequence[OutboxRow]: ...
      async def mark_dispatched(self, row_id: UUID) -> None: ...

  async def dispatch_ready_events(
      repository: OutboxRepository,
      bus: EventBus,
      *,
      source_engine: str,
      batch_size: int = 100,
      metrics: OutboxMetrics | None = None,
  ) -> int: ...
  ```
  `OutboxMetrics` as a small `Protocol` (`outbox_dispatched_total: Counter`-shaped)
  rather than each engine's concrete metrics class, so the shared function
  never imports any engine's own `observability.py`.
- **Dependency direction**: depends on `nova_contracts` (`EventEnvelope`,
  already the shared vocabulary every engine depends on) and
  `nova_eventbus_sdk` (`EventBus`, same). No engine-specific imports — the
  `Protocol`-based repository/metrics parameters are exactly what makes this
  safe: `nova-service-kit` never imports `ReasoningRepository` or
  `WorldHistoryRepository` by name, it only requires the shape.
- **Affected engines**: 7 immediately (`ai-model-orchestration-engine`,
  `communication-engine`, `executive-cognition-engine`, `perception-engine`,
  `reasoning-engine`, `knowledge-engine`, `world-model-engine` — the latter
  two keep their own `apply_pending_graph_writes` untouched, only their
  `dispatch_ready_events` call becomes a thin wrapper around the shared
  function). `memory-engine` is included but requires the prerequisite below.
- **Migration strategy**: (1) ship the shared function and cut the 7
  conforming engines over first, independently, same pattern as Extraction A;
  (2) as a **separate, explicitly-scoped prerequisite change** (not bundled
  into the same PR as the other 7, so it can be reviewed and tested on its
  own merits): add `list_dispatch_ready`/`mark_dispatched` to
  `memory-engine`'s `MemoryRepository` protocol and its
  `postgres_memory_repository.py` implementation, matching every other
  engine's existing method signatures exactly; (3) only then cut
  `memory-engine`'s dispatcher over to the shared function, which also
  resolves the Review's separately-noted naming drift (`dispatch_pending` →
  `dispatch_ready_events`) as a byproduct, not a separate effort.
- **Testing strategy**: every engine with outbox tests already has fake-backed
  integration coverage of "an enqueued event gets dispatched" — these are the
  regression tests, must pass unmodified. `memory-engine`'s prerequisite step
  needs one new test confirming `list_dispatch_ready`/`mark_dispatched`
  against its existing fake repository before the dispatcher cutover, plus
  (once STEP 2's real-infra checkpoint clears) the same real-Postgres check
  the other engines already have via `nova_testkit.postgres`.
- **Expected reduction**: 7 conforming engines: 182 lines → ~30 lines
  (canonical) + 7×~6 lines (thin per-engine wrapper setting the
  `source_engine` default) ≈ 72 lines, **net ~110 lines**. `memory-engine`:
  roughly line-neutral (adds ~15 lines of port methods, removes ~68 lines of
  raw-SQL dispatcher logic in favor of a ~10-line wrapper) — its real value is
  correctness and consistency, not line count, and should be evaluated on
  that basis, not folded into the aggregate SLOC claim.
- **Architectural risks**: the `Protocol`-based design is what keeps this
  extraction from violating engine independence — reviewed explicitly in
  §10. The `memory-engine` prerequisite is a real, if small, behavior change
  (its repository gains two new methods) and should get its own review
  attention, separate from the other 7 engines' pure mechanical cutover.
- **Why preferable to duplication**: this is the Review's own example,
  confirmed directly — adding OpenTelemetry trace-context propagation to
  every engine's outbox dispatch today means 7-9 separate edits (8 if
  `memory-engine`'s prerequisite has already landed by then, 9 if counting
  the two-function saga engines' extra step), each independently forgettable.

### Extraction D — `bind_event_bus()` helper

- **Current duplication**: §2.5 — 18 call sites, 5-6 lines each (~99-108
  lines total).
- **Proposed owner/package**: **`nova_eventbus_sdk`** — not
  `nova-service-kit`. This already owns `BoundEventBus`/`get_event_bus`; a
  convenience wrapper around its own exports is normal package growth, not a
  new architectural surface.
- **Public interface**:
  ```python
  def bind_event_bus(
      engine_name: str,
      *,
      publishable_subjects: frozenset[str],
      subscribable_subjects: frozenset[str],
  ) -> BoundEventBus: ...
  ```
  (Calls `get_event_bus()` internally — the one parameter every call site
  already passes positionally and identically.)
- **Dependency direction**: unchanged — engines already depend on
  `nova_eventbus_sdk` directly; this adds one function to an existing,
  already-imported surface.
- **Affected engines**: 9 (18 call sites across `main.py` + `workers/__init__.py`
  in every engine except `nova-core`, which has no `PUBLISHABLE_SUBJECTS`/
  `SUBSCRIBABLE_SUBJECTS` module of its own — confirmed by its `events/`
  directory containing only stub files).
- **Migration strategy**: mechanical, no prerequisite, no sequencing
  dependency on A/B/C — can ship independently. `await bus.connect()`
  remains a separate, explicit call at each call site (not folded into the
  helper), since `main.py` and `workers/__init__.py` have different shutdown-
  ordering needs that shouldn't be hidden inside a "does everything"
  function.
- **Testing strategy**: `nova_eventbus_sdk` already has its own test suite for
  `BoundEventBus`; add one test confirming `bind_event_bus()` constructs the
  same object the manual call sites do today. No engine's own tests need to
  change — this is an internal wiring simplification with zero external
  behavior change.
- **Expected reduction**: ~99-108 lines → ~10 lines (canonical) + 18×2 lines
  (call sites, since `bus = bind_event_bus(...)` replaces the 4-6 line
  constructor call) ≈ 46 lines. **Net: ~55-60 lines.**
- **Architectural risks**: none identified — smallest, most contained
  extraction in this proposal, and the only one requiring zero new package
  infrastructure.
- **Why preferable to duplication**: lowest-effort win in this entire
  proposal (no new package, no prerequisite, no sequencing) — recommended
  first in the implementation order (§11) precisely because it's free.

### Extraction E — shared reference types (`MemoryReference`,
`WorldModelSnapshot`, `PersonalContext`)

- **Current duplication**: §2.6.2-2.6.4 — 3 types, hand-duplicated once each
  between `executive-cognition-engine` and `reasoning-engine`
  (~8-10 lines per type per engine ≈ 50-60 lines total, plus the ongoing risk
  cost of undetected future drift, which has no line-count expression).
- **Proposed owner/package**: **`nova_contracts`** — not `nova-service-kit`.
  This is domain-shaped shared vocabulary, exactly what `nova_contracts`
  already exists for (per the Review's own §3.4 observation: "`nova_contracts`
  is explicitly the one shared vocabulary layer every engine already depends
  on"), not infrastructure boilerplate. Bundling it into the same package as
  Extractions A-C would blur two genuinely different kinds of sharing
  (infrastructure plumbing vs. domain vocabulary) into one package — exactly
  the "no clear ownership model" failure mode this proposal was asked to
  avoid (task item 8).
- **Public interface**: a new, non-event-specific module — proposed name
  `nova_contracts.reference_types` (naming is an open question for
  implementation-time review, not decided here) — containing the three types
  verbatim as they exist today, each still a plain `BaseModel`, no new
  behavior added:
  ```python
  class MemoryReference(BaseModel):
      memory_id: UUID
      summary: str
      confidence: float | None = Field(default=None, ge=0.0, le=1.0)
  # WorldModelSnapshot, PersonalContext, same treatment
  ```
- **Dependency direction**: both engines already depend on `nova_contracts`
  directly (for `FailureAction`, `ArbitrationOutcome`, etc. — confirmed in
  §2.6.5's import trace). This adds one more import from an already-present
  dependency; no new dependency edge.
- **Affected engines**: 2 (`executive-cognition-engine`, `reasoning-engine`
  only — no other engine currently defines any of these three types).
- **Migration strategy**: this is a domain-type change, not pure
  infrastructure, so it should be sequenced **after** and **separately from**
  Extractions A-D, with its own explicit review — not bundled into the same
  implementation wave. `Goal` and `HumanOverrideRequest` are explicitly
  excluded (§2.6.1, §2.6.5); only the three confirmed-identical types move.
- **Testing strategy**: both engines' existing domain-layer unit tests that
  construct these types (via keyword arguments, not positional) should need
  zero changes if the shared type's field names/types are preserved exactly
  — verify this holds for both engines' actual test files before cutover,
  not assumed.
- **Expected reduction**: modest in raw lines (~50-60), but the real value is
  eliminating a **silent-drift risk that has already materialized once**
  (`Goal`'s `goal_tier`) for the three types where it hasn't happened yet.
- **Architectural risks**: real, and higher than A-D — covered in §10.
  Sequenced as its own, medium-risk tier in §11 for exactly this reason: it
  is the one extraction in this proposal that touches `domain/models.py`
  rather than pure `api/`/`repository/` plumbing, and domain-layer changes
  warrant more caution than infrastructure ones even when the change itself
  is small.
- **Why preferable to duplication**: `Goal` already proves the drift risk is
  not hypothetical — it happened to the one type in this group that *was*
  allowed to diverge locally. The other three are one design decision away
  from the same fate the moment either engine needs a field the other
  doesn't.

---

## 5. The new package: `nova-service-kit`

**Scope statement** (matching the one-sentence pattern every existing shared
package already has in its own `pyproject.toml` — e.g. `nova-observability`'s
"Shared OpenTelemetry (traces/metrics) and structured logging setup used by
every engine"):

> Shared FastAPI/SQLAlchemy infrastructure boilerplate — health/readiness
> routing, Postgres engine/session-factory construction, and the
> transactional-outbox dispatch loop — used identically by every engine that
> has one, with zero engine-specific knowledge of any kind.

**Explicitly out of scope** (so this doesn't become the generic dumping
ground task item 8 warned against):
- No domain types, no business logic of any kind (that's Extraction E's job,
  and it belongs in `nova_contracts`, not here).
- No Event Bus construction helpers (that's `nova_eventbus_sdk`'s job,
  Extraction D).
- No tracing/metrics/logging setup (that's `nova-observability`'s job,
  unchanged).
- No test fixtures of any kind (that's `nova-testkit`'s job, unchanged — and
  per ADR-033, `nova-testkit` must stay test-infra-only; this proposal adds
  no test-infra responsibility to `nova-testkit` and no production
  responsibility to `nova-service-kit`, keeping that boundary exactly where
  ADR-033 drew it).
- Three modules only for the initial scope: `health.py` (Extraction A),
  `db.py` (Extraction B), `outbox.py` (Extraction C). Nothing added
  speculatively "while we're at it."

**Dependency direction**: engines depend on `nova-service-kit`; it depends on
nothing engine-specific — `fastapi`, `pydantic`, `sqlalchemy`,
`nova_contracts`, `nova_eventbus_sdk` only (the same shared-dependency set
`nova-testkit` already has, per ADR-033's own precedent). This is a strict
one-directional dependency edge, identical in shape to every existing shared
package (`nova-observability`, `nova-eventbus-sdk`, `nova-testkit`) — not a
new kind of dependency relationship.

**Proposed import-linter contract** (to be added at implementation time, not
in this step — see §12), modeled directly on ADR-033's existing nova-testkit
contract:

```toml
[[tool.importlinter.contracts]]
name = "nova-service-kit has no engine-specific knowledge: it may not import any engine's own top-level package"
type = "forbidden"
source_modules = ["nova_service_kit"]
forbidden_modules = [
    "nova_core", "nova_memory_engine", "nova_knowledge_engine",
    "nova_world_model_engine", "nova_ai_model_orchestration_engine",
    "nova_reasoning_engine", "nova_executive_cognition_engine",
    "nova_personality_engine", "nova_communication_engine",
    "nova_perception_engine",
]
```

This is not a new kind of rule — it is ADR-033's own nova-testkit boundary,
applied a second time to a second shared package, which is exactly the kind
of "same rule, mechanically enforced again" outcome that keeps a new package
from becoming a hidden coupling point. **Recommend a companion ADR
(ADR-034, next available number) formalizing this as a general rule for
any future shared package**, not just this one — proposed for
implementation time, not written now (§13).

**Does this cross ADR-004?** No — confirmed directly against ADR-004's own
text (`docs/architecture/00-overview-and-decisions.md`): ADR-004 forbids
*engine-to-engine* calls (direct HTTP, direct module imports of another
engine's internals). A shared library dependency is architecturally identical
to every engine's existing dependency on `nova-observability`/
`nova-eventbus-sdk` — infrastructure plumbing, not cross-engine
communication. The Review's own §18 conclusion ("None of this crosses
ADR-004") is confirmed, not merely repeated.

---

## 6. Explicitly rejected extractions

| Pattern | Why rejected |
|---|---|
| **`workers/__init__.py` full-file extraction** (§2.4) | Most of each file's bulk (74-117 lines) is genuine per-engine wiring — which stores to connect, which cron jobs at which schedule. A factory general enough to parameterize all of that would need injectable setup/teardown callables and injectable cron-job lists, becoming a small framework rather than a boilerplate remover. The ~20-25 line skeleton that *is* shared is now mostly captured by Extraction D (the `BoundEventBus` construction) without needing to touch the rest of the file. |
| **`Goal`** (§2.6.1) | Already diverged (`goal_tier`) — a real, deliberate business difference between the two engines, not accidental duplication. Unifying now means either forcing an unwanted field onto `reasoning-engine` or making a product decision about goal-tier scoring that belongs to a design discussion, not a refactor. |
| **`HumanOverrideRequest`** (§2.6.5) | Never actually the same type — different foreign keys pointing at different aggregates, and its underlying action enums are already deliberately kept separate by an existing, explicit design decision recorded in `ExecutiveOverrideAction`'s own docstring. Unifying it would be inventing a false shared abstraction, exactly what task item 8 warned against. |
| **`ConfidenceTier`** (§2.7) | Real triplication, but `nova_contracts` currently has no neutral (non-event-namespace) home for cross-engine vocabulary that isn't already scoped to one engine's own event contracts. Needs an ownership/naming decision first, not a mechanical extraction. |
| **Weighted composite scorer** (§2.8) | Not duplication — three independent, reasonable implementations of a shared *shape* with three different (undecided-as-correct) missing-data policies. Unifying before that reconciliation would silently change at least two engines' real behavior. Restated from the Review, not re-litigated by this proposal (out of scope — domain logic, not boilerplate). |
| **Narrow ID+summary ACL objects generally** (`PresentIdentitySignal`, `KnowledgeReference`, etc., §2.9) | The single strongest pattern in the codebase precisely *because* each is a deliberate, asymmetric narrowing from one engine's rich internal model to exactly what a different consuming engine needs. Sharing these would re-couple engines that this pattern exists to keep decoupled. |
| **A generic catch-all "shared" package** | Not proposed under any name. Every extraction above has a specific, narrow owner (`nova-service-kit` for 3 infrastructure modules only, `nova_eventbus_sdk` for one helper, `nova_contracts` for domain vocabulary) chosen because it already has — or, for `nova-service-kit`, is given — a one-sentence scope statement, not because it's a convenient place to put code. |

---

## 7. What We Should Leave Alone

Stated explicitly, as its own section, so future implementation work doesn't
default to "every repeated pattern becomes an abstraction":

1. **Every narrow ID+summary cross-engine value object** (§2.9) —
   `PresentIdentitySignal`, `MemoryReference`/`WorldModelSnapshot`/
   `PersonalContext` *as consumed by their own engine's domain logic*
   (Extraction E only touches where the *type definition* lives, never how
   each engine's own domain logic treats the value once received),
   `KnowledgeReference`, and any future one of these. If a new engine needs a
   narrow read of another engine's data, the correct move is always a new,
   locally-scoped, deliberately-narrowed type in the consuming engine's own
   `domain/models.py` — never a shared "generic reference" base class, which
   would immediately reintroduce the coupling this pattern exists to prevent.
2. **`Goal` and any other type an engine has deliberately extended beyond its
   peer's copy.** Divergence after a shared start is not automatically drift
   to be corrected — sometimes it's two engines correctly modeling two
   different realities. Check field-by-field before assuming two
   identically-named types are actually the same (§2.6.5's lesson).
3. **The three independent weighted-composite-scorer implementations**
   (§2.8) — until a deliberate, separate design decision reconciles their
   missing-data semantics. This is not a boilerplate question and does not
   belong in a future revision of this proposal.
4. **`workers/__init__.py`'s per-engine wiring** (§2.4) — the cron schedules,
   the extra-store connections, the ctx dict contents. This is legitimate
   configuration, not copy-paste, even though it happens to live in
   structurally similar files.
5. **`nova-core`'s divergent `health.py` behavior itself** (not its
   duplication mechanism, which Extraction A does fix) — it reads real boot
   state because it is the one engine for which boot state is the entire
   point. Extraction A must preserve this exactly via its override
   parameters, never quietly normalize it away to match the other 9.
6. **Any future coincidentally-identical enum values across two engines'
   `nova_contracts` event modules** — the codebase has already made and
   documented this call once (`ExecutiveOverrideAction`/`OverrideAction`,
   §2.6.5). Treat that as standing precedent, not a one-off, until a
   consequential future ADR revisits it.

---

## 8. Cross-cutting migration strategy

- **No big-bang PR.** Every extraction above (A, B, D fully; C for 7 of 8
  engines) is independently shippable, independently revertable, and touches
  exactly one engine's wiring per commit — consistent with how STEP 1's
  7-item cleanup pass and STEP 2's 14-item sequence were both done as
  discrete, individually-verifiable steps, not one large change.
  `memory-engine`'s outbox prerequisite (part of Extraction C) and Extraction
  E (domain types) are explicitly called out as needing their own separate
  review attention, not bundled into the mechanical cutovers around them.
- **`tools/scaffold-engine.py` must be updated as part of Extraction A**
  (and, if built, any future scaffolded pattern for B/C) — otherwise every
  engine scaffolded after this work ships would still be born with the old
  duplicated pattern, undoing the point of the exercise. Confirmed only
  `_HEALTH_PY` currently exists as a scaffold template; `db.py`/
  `outbox_dispatcher.py`/`workers/__init__.py` are not machine-generated
  today, so B/C/D need no scaffold-tool change beyond ensuring any future
  engine's author is pointed at the shared package instead of the old
  now-removed engine copies (a documentation update, covered in §13, not a
  code change).
- **Order engines within each extraction from lowest to highest blast
  radius.** Recommend cutting over `perception-engine` first for each pattern
  (newest, smallest, most recently verified end-to-end) before the 8 older
  engines, so any unexpected interaction surfaces against the codebase's
  best-understood, most recently-tested engine first.

## 9. Cross-cutting testing strategy

- **Existing tests are the regression suite for A, B, D, and 7/8 of C.**
  None of these four extractions change externally observable behavior for
  the engines already conforming to the shared shape — if any existing test
  needs to change beyond an import path, that is itself a signal the
  extraction introduced an unintended behavior change and should stop for
  review, not be pushed through.
- **New unit tests belong in `nova-service-kit`/`nova_eventbus_sdk` themselves**
  for the canonical implementations, covering exactly the parameterization
  surface each public interface exposes (§4's per-extraction "public
  interface" sections) — not duplicating what each engine's own integration
  tests already cover.
- **`memory-engine`'s outbox prerequisite needs new coverage before cutover**:
  a test confirming `list_dispatch_ready`/`mark_dispatched` behave correctly
  against its existing fake repository, mirroring every other engine's
  existing equivalent test, before the dispatcher itself changes.
- **Extraction E needs an explicit before/after check** that both engines'
  existing domain-layer tests constructing `MemoryReference`/
  `WorldModelSnapshot`/`PersonalContext` continue to pass unmodified with the
  shared import — verify, don't assume, exactly as this proposal's own
  methodology (§1) required throughout.
- **Coverage gate impact**: none of these extractions touch `domain/`
  (STEP 2's 85% gate scope) except Extraction E, which moves 3 already-tested
  types without adding new branching logic — expect no measurable coverage
  change, verify this holds at implementation time rather than assuming it.

---

## 10. Architectural risk register

| Risk | Applies to | Severity | Mitigation already designed in |
|---|---|---|---|
| A new package becomes a dumping ground over time, growing scope beyond its original justification | `nova-service-kit` | Medium (long-term, not immediate) | §5's explicit out-of-scope list + the proposed import-linter contract + a companion ADR (§13) recording the boundary rule in a form future sessions must consult, the same way ADR-033 already protects `nova-testkit` |
| Shared `dispatch_ready_events()` accidentally becomes a place engine-specific logic leaks in over time (e.g. an engine needs one extra step mid-loop) | Extraction C | Medium | `Protocol`-based design (not concrete repository types) makes it structurally awkward to add engine-specific branches inside the shared function; an engine needing a genuinely different dispatch shape should keep its own file, not force a special case into the shared one — this is a judgment call for implementation time, flagged here so it isn't made silently |
| `memory-engine`'s new repository methods introduce a real behavior change disguised as a mechanical refactor | Extraction C prerequisite | Medium | Explicitly scoped as its own reviewable change, not bundled (§4 Extraction C, §8) |
| Extraction E's shared types drift back apart the moment one engine needs a field the other doesn't (recurrence of `Goal`'s own history) | Extraction E | Medium | This is expected and correct behavior, not a failure mode — the shared type should be forked back into two local types the moment genuine divergence is needed, exactly as `Goal` already demonstrates is sometimes the right outcome. Documented here so a future session doesn't treat re-divergence as regression to be prevented at all costs |
| `nova-core`'s health-check override parameters get silently dropped or normalized during Extraction A's implementation | Extraction A | Low | §4 Extraction A's public interface is designed specifically to make this explicit and testable; §7 item 5 states it as a "leave alone" requirement |
| New import-linter contract for `nova-service-kit` is forgotten, leaving the boundary unenforced | `nova-service-kit` | Low | Explicit checklist item in §13, modeled directly on ADR-033's existing precedent |

No **high**-severity architectural risks were identified for any extraction
in this proposal — consistent with the Review's own original "near-zero risk"
characterization for A/B, and this proposal's own refinement narrowing C to
"low for 7 engines, one bounded prerequisite for the 8th." Extraction E is
the only one carrying real (medium) risk, which is why it is sequenced last
and separately in §11, not because any single technical risk is severe, but
because it is the one change in this proposal that touches domain modeling
rather than pure infrastructure plumbing.

---

## 11. Recommended implementation order

**Low risk — no prerequisites, no domain-type changes, fully mechanical:**
1. Extraction D (`bind_event_bus()`) — smallest, needs no new package,
   ship first.
2. Extraction B (`create_engine_and_session_factory`) — zero parameters,
   zero behavioral variation across all 9 existing copies.
3. Extraction A (`make_health_router()`) — one parameterization surface
   (`nova-core`'s override), otherwise identical profile to B. Include the
   `scaffold-engine.py` template update in this same piece of work.

**Medium risk — mechanical for most engines, one bounded prerequisite:**
4. Extraction C, 7 conforming engines — same profile as A/B once the shared
   `Protocol` is defined.
5. Extraction C, `memory-engine` prerequisite (repository port methods) —
   reviewed and tested on its own before step 6.
6. Extraction C, `memory-engine` cutover — only after step 5 lands and its
   own tests pass.

**Higher risk — touches domain types, needs its own design sign-off:**
7. Extraction E (`MemoryReference`/`WorldModelSnapshot`/`PersonalContext` →
   `nova_contracts`) — sequenced last and separately, not because the change
   itself is large, but because domain-layer changes warrant more deliberate
   review than infrastructure plumbing even at this scale. Recommend this be
   its own explicit approval checkpoint, not silently included in whatever
   approves 1-6.

**Deferred indefinitely, not scheduled:**
- `ConfidenceTier` unification (§2.7) — needs a `nova_contracts` ownership
  decision first.
- Weighted composite scorer unification (§2.8) — needs a missing-data-
  semantics design decision first.
- `workers/__init__.py` full-file extraction (§2.4) — not recommended at all,
  re-evaluate only if a genuinely new, more compressible pattern emerges
  across a future engine, not on a schedule.

---

## 12. Non-goals — explicitly out of scope for this step

Per direct instruction, none of the following happened in this step and none
are proposed to happen until explicit approval of this document specifically:

- No production code was modified, moved, or refactored.
- No test file was modified.
- No CI workflow was modified.
- No database schema or migration was touched.
- No existing ADR was modified.
- No new package was actually created on disk (`nova-service-kit` does not
  exist yet — this document specifies what it *would* contain).
- No import-linter contract was added (§5's proposed contract text is a
  specification for implementation time, not a change made now).
- Phase 2D-C was not started and is not addressed by this document.
- `docs/architecture/17-cicd-pipeline.md`'s Turborepo affected-graph
  inconsistency (flagged in STEP 2's verification checkpoint as explicitly
  out of scope there too) remains untouched here as well.

## 13. Recommended follow-up artifacts (at implementation time, not now)

If this proposal is approved and implementation begins:

1. **ADR-034** (next available number, confirmed by listing
   `docs/architecture/adr/`) formalizing the general rule this proposal
   applies to `nova-service-kit`: a shared infrastructure package may hold
   only implementation with zero engine-specific knowledge, enforced by an
   import-linter contract mirroring ADR-033's existing nova-testkit rule.
   This generalizes the rule beyond just this one package, the same way
   ADR-004/ADR-006/ADR-007/ADR-020 each generalize one specific boundary
   rather than special-casing it per package.
2. **The import-linter contract specified in §5**, added to root
   `pyproject.toml` alongside the other four existing contracts, at the same
   time `nova-service-kit` is actually created — not before (an empty
   contract for a nonexistent package has nothing to verify).
3. **A short update to `docs/architecture/16-testing-strategy.md` or
   `docs/architecture/03-backend-architecture.md`** (whichever the
   implementation-time session judges the better home) noting
   `nova-service-kit`'s existence and scope, matching how `nova-testkit`'s
   STEP 2 work updated the same class of document — not done now, per this
   step's explicit non-goals (§12).
4. **A one-line addition to `tools/scaffold-engine.py`'s own module
   docstring or a comment near `_HEALTH_PY`** once that template is replaced,
   noting the new pattern for anyone reading the scaffold tool's history
   later — small, but prevents a future reader from wondering why the string
   template disappeared.

None of these four are created in this step. They are named here so
implementation-time work has a checklist, not because any of them exist yet.

---

## 14. Estimated Production SLOC impact

| Extraction | Current (duplicated) | After (canonical + call sites) | Net reduction |
|---|---|---|---|
| A — `make_health_router()` | 288 (10 files) | ~65 | **~223** |
| B — `create_engine_and_session_factory` | 171 (9 files) | ~33 | **~138** |
| C — `dispatch_ready_events` (7 engines) | 182 | ~72 | **~110** |
| C — `memory-engine` prerequisite + cutover | 78 | ~35 (port methods + thin wrapper) | **~roughly neutral, correctness-motivated** |
| D — `bind_event_bus()` | ~104 (18 call sites) | ~46 | **~58** |
| E — shared reference types (deferred to its own approval) | ~55-60 | ~20 | **~35-40** |
| **Total (A+B+C+D, recommended first wave)** | | | **~490-530 lines net reduction** |
| **Total including E** | | | **~525-570 lines net reduction** |

This is presented as a **net** figure — lines removed from engine repos minus
lines added to the new package's own canonical implementations and per-engine
call sites — deliberately more conservative than the Review's own ~700-line
gross-duplication figure, which counted every duplicate copy as pure loss
without netting out what necessarily moves rather than vanishes. At current
Production SLOC (32,262, per STEP 2's verification checkpoint), this
extraction wave represents roughly **1.5-1.7%** of the codebase — a real but
modest reduction, consistent with the Review's own framing of this as a
"low-risk, well-quantified" cleanup opportunity rather than a major
architectural intervention. Its larger value, as the Review itself
emphasized, is not the current line count but the avoided future cost: at a
plausible 20-engine eventual project size, the same unextracted patterns
would compound to roughly double today's duplicated total.

---

## 15. Approval checklist

This document proposes, and does not implement:

- [ ] Extraction A (`make_health_router()`, `nova-service-kit`)
- [ ] Extraction B (`create_engine_and_session_factory`, `nova-service-kit`)
- [ ] Extraction C, 7 conforming engines (`dispatch_ready_events`, `nova-service-kit`)
- [ ] Extraction C, `memory-engine` prerequisite (repository port methods)
- [ ] Extraction C, `memory-engine` cutover (after prerequisite lands)
- [ ] Extraction D (`bind_event_bus()`, `nova_eventbus_sdk`)
- [ ] Extraction E (`MemoryReference`/`WorldModelSnapshot`/`PersonalContext`, `nova_contracts`) — recommend as a separate approval, not bundled with A-D
- [ ] New package `nova-service-kit` scope statement (§5) as the binding
      definition for what may and may not be added to it later
- [ ] Explicitly rejected list (§6) and "leave alone" list (§7) as standing
      guidance, not just this-pass exclusions

**No implementation begins until the user approves this document.** Per
direct instruction, this step stops here.
