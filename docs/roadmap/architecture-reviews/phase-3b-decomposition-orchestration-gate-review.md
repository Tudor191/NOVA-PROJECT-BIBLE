# Phase 3B — `planning-engine` Decomposition Orchestration: Gate Review

**Status: complete, fully verified locally and via real GitHub Actions
(see §6). Covers exactly one PR-sized unit**
(`phase-3b-decomposition-orchestration`, branched from
`phase-3b-planning-domain`) of Phase 3B's multi-PR implementation — not
the whole of Phase 3B. No persistence, API surface, `planning.
task_graph.created` publication, or `planning.decompose.request` RPC
exists yet; those remain later, separately scoped and separately reviewed
PRs (see §7).

---

## 0. Scope executed

`services/planning-engine` gains its first real event-consumption and
model-orchestration path: a subscribed `reasoning.process.completed`
handler (`events/handlers.py`) that, above a confidence threshold, calls a
new `domain/decomposition.py` module to turn `objective_text`/
`chosen_description` into a structurally valid, in-memory `TaskGraph` —
via a new `ModelOrchestrationPort`/`ModelOrchestrationClient` pair
(`domain/ports.py`, `clients/model_orchestration_client.py`), the same
ADR-020 channel `reasoning-engine` already uses for Hypothesis Generation.

The resulting `TaskGraph` is fully computed and validated but, in this PR,
only observed via logs/metrics — it is not yet persisted or published.
Proving the decomposition mechanism itself works correctly, end-to-end,
against a real (faked in tests, real-contract-shaped) model-orchestration
call is this PR's entire purpose; persisting and publishing the result is
the next scoped unit.

## 1. Architecture decision, as approved

**Decomposition algorithm: LLM-backed, via `ModelOrchestrationPort` /
`ai_model.generate.request`** — per the dedicated research pass
(`docs/design/phase-3/11-3b-decomposition-architecture-research.md` §6,
§13, branch `phase-3b-decomposition-research`, commit `654570d`) and this
instruction's explicit approval. ADR-020 already establishes this exact
pattern for "any future engine... needing AI model access" and
`reasoning-engine`'s own `ModelOrchestrationPort`/`ModelOrchestrationClient`
is the direct, reused precedent — not a new architectural dependency
direction, not a new ADR, not an invented heuristic, not the
single-node placeholder the user explicitly rejected in an earlier
instruction.

**Structured output mechanism (the one sub-decision the research pass
explicitly left open, §6): tool-calling, not free-text + regex.**
`reasoning-engine`'s hypothesis generation uses free-text + a numbered-line
regex, since its output (a flat list of strings) doesn't need more.
`TaskGraph`/`TaskNode` is a nested structure with typed fields (IDs,
dependencies, an effort estimate, a risk enum) — the tool-calling mechanism
`nova_contracts.events.ai_model_orchestration` already defines
(`GenerateRequestPayload.tools`/`GenerateReplyPayload.tool_calls`) and
`ai-model-orchestration-engine`'s Anthropic connector already implements
(`connectors/anthropic_connector.py:105-122`, real `tool_use` parsing) is a
materially better fit, and had no real caller before this PR. A single
local, `propose_task_graph` JSON-Schema tool definition
(`domain/decomposition.py`'s own `_TOOL_SCHEMA`) — planning-engine-owned,
not a `nova_contracts` change, per the research doc's own framing.

**No trust extended to the model's own output** (Part 4's explicit
requirement). The model proposes local, string-scoped task IDs (never real
UUIDs — models are unreliable at generating and consistently re-using
random UUIDs within one response); `_build_nodes` mints the real
`TaskNode.id` UUIDs itself and resolves every `depends_on` reference
against its own mapping, rejecting an unknown reference before a
`TaskNode` is ever constructed. Every resulting node set is then checked,
in order, by PR #2's own pure functions — `find_duplicate_ids`,
`find_cycle`, `find_dangling_dependencies`, `compute_critical_path` — with
no redesign of any of the four. `Estimate`/`RiskLevel` field validity is
enforced by their own existing Pydantic/enum construction, not
re-implemented.

## 2. `assigned_agent_category` — implemented as approved (Fork R-1)

The decomposition model may optionally propose `assigned_agent_category`
per task; `TaskNode.assigned_agent_category: str | None` already supports
this without a schema change (§12.3 of the tool schema:
`{"type": ["string", "null"]}`). `planning-engine` does not validate the
category against any registry — no Kernel Scheduler, Supervisor, or the
five agents exist yet, and none are built or stubbed in this PR.

## 3. Idempotency — deferred as approved (Fork R-2)

No dedup mechanism was added. `reasoning.process.completed` is
at-least-once delivery (`docs/architecture/09-event-bus-architecture.md:
126-130`) and this handler is not exactly-once with respect to duplicate
delivery: a redelivered event triggers a second, independent decomposition
attempt (a second model call, a second in-memory `TaskGraph`, neither
persisted). **No fake exactly-once behavior, in-memory deduplication,
process-local UUID sets, global singleton caches, arbitrary TTL maps, or
JetStream-specific dedup workaround was introduced.** This is safe *only*
because nothing in this PR is persisted or published yet — there is no
durable side effect for a duplicate delivery to corrupt. **Persistent
event deduplication becomes a required follow-up when the planning
persistence layer is implemented** (the point at which a duplicate
decomposition would otherwise write two `TaskGraph` rows for one
`reasoning_process_id`); this PR does not implement it and does not
pretend to.

## 4. Verification: implementation did not reveal a persistence-required conflict

Per this instruction's own escalation clause: implementation did **not**
reveal that decomposition literally cannot operate safely without
persistence-backed deduplication in its *current*, unpersisted scope — the
worst outcome of a duplicate `reasoning.process.completed` today is a
redundant model call and a discarded, never-observed second `TaskGraph`,
not data corruption. No architectural conflict to report; §3's deferral
stands.

## 5. New enforcement gap found and closed (Part 9 verification)

Re-verifying the ADR-020 import-linter contract before writing any
production code found `nova_planning_engine` absent from its
`source_modules` list (`pyproject.toml`, the
`"No engine imports an LLM/AI provider SDK directly (ADR-020)"` contract)
— every other model-adjacent engine (`reasoning`, `executive-cognition`,
`personality`, `communication`, `perception`, `digital-twin`) is listed;
`planning-engine` was not, because `tools/scaffold-engine.py` only
auto-registers a new engine against the ADR-004/006/007 contracts (its own
source, confirmed), never ADR-020 — every prior engine's ADR-020
registration was a manual step taken when that engine first gained
model-adjacent code. PR #2 was domain-only, so it correctly wasn't
registered yet. This PR is the one that gives `planning-engine` its first
`ModelOrchestrationPort`, so closing the gap here — a one-line addition to
`source_modules` — is this PR's own responsibility, not a separate CI
maintenance PR: it is the exact per-engine step every model-adjacent
engine before it already took, applied at the point it becomes relevant.
Not an architectural fork, not a pre-existing failure — `lint-imports`
already passed before this change (the gap only meant the *specific* new
code this PR adds was unprotected by the rule it must obey); it passes
identically after.

## 6. Unconfirmed but precedented parameter, flagged (Fork 3B-3)

The decomposition confidence threshold (TDD 3B §7, Fork 3B-3) was never
given an explicit numeric approval in this instruction. TDD 3B's own text
categorizes this as "not so much an architectural fork as a named
implementation parameter requiring a concrete default," with a proposed
default: reuse `reasoning-engine`'s own `DEFAULT_VERIFY_THRESHOLD` (0.6),
avoiding a second, arbitrary constant. Implemented as
`Settings.decomposition_confidence_threshold: float = 0.6`
(env-overridable, `PLANNING_ENGINE_DECOMPOSITION_CONFIDENCE_THRESHOLD`) —
flagged here explicitly, not silently assumed, per TDD 3B's own framing.

## 7. Exact files changed

| File | Change |
|---|---|
| `services/planning-engine/src/nova_planning_engine/domain/ports.py` | New — `ModelOrchestrationPort`, `EventPublisher` Protocols. |
| `services/planning-engine/src/nova_planning_engine/clients/__init__.py`, `clients/model_orchestration_client.py` | New — `ModelOrchestrationClient`, mirrors `reasoning-engine`'s adapter. |
| `services/planning-engine/src/nova_planning_engine/domain/decomposition.py` | New — `decompose()`, `DecompositionError`, `_build_nodes`, the `propose_task_graph` tool schema. |
| `services/planning-engine/src/nova_planning_engine/events/handlers.py` | New — `make_reasoning_process_completed_handler`. |
| `services/planning-engine/src/nova_planning_engine/events/subscribed.py` | `SUBSCRIBABLE_SUBJECTS` gains `reasoning.process.completed`. |
| `services/planning-engine/src/nova_planning_engine/events/published.py` | `PUBLISHABLE_SUBJECTS` gains `ai_model.generate.request` (outbound RPC subject, per `BoundEventBus.request()`'s own allow-list check). |
| `services/planning-engine/src/nova_planning_engine/config.py` | New settings: `decomposition_confidence_threshold`, `decomposition_model_orchestration_timeout_ms`. |
| `services/planning-engine/src/nova_planning_engine/observability.py` | New — `PlanningEngineMetrics`, 4 instruments. |
| `services/planning-engine/src/nova_planning_engine/main.py` | Wires metrics, `ModelOrchestrationClient` (injectable for tests), and the new subscription. |
| `pyproject.toml` | `nova_planning_engine` added to the ADR-020 import-linter contract's `source_modules` (§5 above). |
| `services/planning-engine/tests/__init__.py` | New — was missing; required for `tests.fakes.*` imports to resolve (matches every other engine's own `tests/__init__.py`). |
| `services/planning-engine/tests/fakes/` | New — `FakeModelOrchestrationPort`, `FakeEventPublisher` (mirror `reasoning-engine`'s own fakes). |
| `services/planning-engine/tests/unit/test_decomposition.py`, `test_model_orchestration_client.py` | New — 18 tests total. |
| `services/planning-engine/tests/integration/test_events_reasoning_completed.py` | New — 4 tests, real `create_app()` + real (in-memory) `EventBus`. |
| `docs/design/phase-3/05-tdd-3b-planning-engine.md` | §3: add `ModelOrchestrationPort`. §8: add the model-call-failure row. Top status line corrected (was stale since before PR #2). |

**No changes to**: `nova_contracts` (no new/modified payload — the
existing `GenerateRequestPayload`/`Reply` suffice, confirmed by the
research pass and re-confirmed here), `TaskNode`/`TaskGraph`/`Estimate`/
`RiskLevel` (PR #2's domain model, untouched), any other engine, any CI
workflow file, `docker-compose.local.yml` (planning-engine's service block
already existed from PR #2; still no container to build differently).

## 8. Tests

57 tests total in `services/planning-engine`
(35 pre-existing from PR #2 + 22 new), all fake-backed — never a real
model, never real NATS:

- **`test_decomposition.py` (18 new):** the full happy path (two-node
  graph with a dependency, `assigned_agent_category` both set and `None`,
  correct `critical_path`); `objective_text`/`chosen_description`
  propagation into the prompt context; `chosen_description=None` correctly
  omits the context component (never substituted); model timeout;
  `finish_reason == "error"`; no tool call returned; empty task list;
  malformed task entry (not an object); missing `local_id`; malformed
  `depends_on` (not a list); duplicate local ID; unknown dependency
  reference; malformed `effort_hours`/`confidence`/`risk`
  (parametrized, 3 cases); cycle detection propagating through to
  `DecompositionError(reason="cycle")`.
- **`test_model_orchestration_client.py` (2 new):** reply translation,
  timeout propagation — identical tests to `reasoning-engine`'s own, for
  the identical adapter.
- **`test_events_reasoning_completed.py` (4 new, integration-level):**
  below-threshold skip (no model call made); above-threshold triggers a
  correctly-shaped model call; a model error does not raise out of the
  handler; publishing onto the real (in-memory) `EventBus` under the real
  subject correctly reaches the registered handler (proves `main.py`'s own
  `bus.subscribe(...)` wiring, not just the handler function in isolation).

**Two of PR #2's four structural checks are unreachable through
`decompose()`'s own public entry point, by construction, and are honestly
left uncovered rather than forced:** `find_duplicate_ids` and
`find_dangling_dependencies` can never fire here, because `_build_nodes`
always mints a fresh, unique UUID per resolved local ID and always
resolves every `depends_on` reference before a node is constructed — a
duplicate or dangling *UUID* is structurally impossible from this
function's own construction (unlike a *cycle*, which two mutually-
referencing, individually-valid local IDs can still produce, and which
*is* tested). Both checks remain in `decompose()` anyway, exactly as
Part 12 requires, as defence-in-depth against a future change to
`_build_nodes` — and both are already independently, directly unit-tested
against `TaskNode` lists in PR #2's own `test_task_graph.py`. This is
disclosed, not hidden behind an inflated coverage number.

## 9. Verification classification (5 categories, not collapsed)

| Check | Result | Classification |
|---|---|---|
| `ruff check`/`format`, `planning-engine` | Clean, 20 source files (19 `src/` + tests) | Fully verified |
| `mypy`, `planning-engine` (`uv run --package planning-engine mypy src`, the exact CI invocation) | Clean, 19 source files | Fully verified |
| `planning-engine` test suite | 57/57 passed | Fully verified |
| `planning-engine` domain coverage | 99% branch (`decomposition.py`: 96%, 2 structurally-unreachable lines disclosed in §8; `models.py`/`ports.py`/`task_graph.py`: 100%) vs. 85% gate | Fully verified |
| Full monorepo lint (`pnpm turbo run lint`) | 20/20 packages green | Fully verified |
| Full monorepo test suite (`pnpm turbo run test`) | 20/20 packages green, including `planning-engine`'s 57/57 | Fully verified |
| import-linter (6 contracts, including the extended ADR-020 one) | 6/6 kept | Fully verified |
| `docker-compose config` | Valid; file unmodified by this PR | Fully verified |
| TypeScript codegen | Re-run; zero diff, confirmed not merely assumed (no `nova_contracts` change in this PR) | Fully verified |
| `test_events_reasoning_completed.py`'s 4 integration tests | Real `create_app()`, real (in-memory) `EventBus`, real subject-matching dispatch; only the model-orchestration boundary is faked (`FakeModelOrchestrationPort`) | Local integration verified |
| The structured `ai_model.generate.request`/`.reply` round trip via a real `ai-model-orchestration-engine` process and a real provider | Not exercised — every test above fakes the model-orchestration boundary, matching every prior engine's own precedent (a real provider call is never exercised in this repo's test suite anywhere) | Contract/fake verified only |
| `reasoning.process.completed` -> `planning-engine` over real NATS JetStream (consumer groups, redelivery, durable stream semantics) | Not exercised. `nova-testkit`'s `nats_event_bus` fixture exists (STEP 2.8) but is not used by *any* engine in this codebase for a subject-subscription proof yet — confirmed by repo-wide grep before deciding not to build that pattern for the first time inside this narrowly-scoped PR. What the in-memory `EventBus` test *does* prove: the same `EventBus` Protocol NATS implements, subject-pattern matching, and handler dispatch are all correct — it does not prove anything about JetStream redelivery, consumer-group load balancing, or durable-stream persistence | Genuinely unverified (explicitly, not silently assumed) |
| GitHub Actions — `PR Checks` | `success`, run [31918753085](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/31918753085) | Real-infrastructure verified |
| GitHub Actions — `Build & Scan` | `success`, run [31918751521](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/31918751521) | Real-infrastructure verified |
| GitHub Actions — `Real-Infrastructure Checks` | `success`, run [31918752447](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/31918752447) | Real-infrastructure verified |

## 10. GitHub Actions (confirmed after push, PR #7, head `1bf948d`)

| Workflow | Run ID | Conclusion |
|---|---|---|
| `PR Checks` (`pr-checks.yml`) | [31918753085](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/31918753085) | `success` |
| `Build & Scan` (`build-and-scan.yml`) | [31918751521](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/31918751521) | `success` |
| `Real-Infrastructure Checks` (`real-infra-checks.yml`) | [31918752447](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/31918752447) | `success` |

All 18 individual check runs across the three workflows completed with
`conclusion: success` (`dependency-audit`, `checks`, 11 `build-and-scan`
matrix jobs, 5 `real-infra` matrix jobs) — confirmed via
`pull_request_read(method="get_check_runs")`, not assumed from the
top-level workflow status alone. `planning-engine` has no container image
yet (no `build-and-scan` matrix entry — by design, no persistence/API to
containerize meaningfully differently than the existing scaffold) and no
`real-infra` matrix entry of its own (no Postgres/Redis/Neo4j-backed
repository exists in this PR). PR #7's `mergeable_state` is `clean`.

## 11. Known limitations (of this PR's scope, not defects)

- No persistence — `TaskGraph`s produced here are never written to
  Postgres and cannot be read back; a process restart loses every
  decomposition this PR's own handler ever produced. This is by design
  (§0), not an oversight.
- No `planning.task_graph.created` publication and no
  `planning.decompose.request` RPC — both remain TDD 3B §6.2 items for a
  later PR; no payload for either was added to `nova_contracts` in this PR.
- No persistent idempotency (§3) — a duplicate `reasoning.process.
  completed` delivery triggers a second, independent, unpersisted
  decomposition attempt today. Safe only because nothing is persisted yet;
  becomes a hard requirement the moment persistence exists.
- `MemoryPort`/`KnowledgePort` consultation during decomposition (TDD 3B
  §3's other two ports) is not implemented — `decompose()` uses only
  `objective_text`/`chosen_description`, no memory/knowledge context. Not
  disclosed as a defect: TDD 3B never made those two ports a precondition
  for the decomposition path specifically, and adding them is a
  legitimate, separately-scoped future enrichment, not a correctness gap
  in what this PR claims to do.
- The decomposition confidence threshold's exact value (0.6) is a flagged,
  precedented default, not an explicitly user-approved number (§6).

## 12. Remaining Phase 3 dependencies

- The persistence-layer PR (TDD 3B §4) is the next scoped unit this PR's
  own "Known limitations" point toward — it is also where persistent event
  deduplication (§3) becomes mandatory, not optional.
- TDD 3C/3D/3E remain unaffected: TDD 3C has no technical dependency on
  planning-engine (confirmed at research time, re-confirmed here — nothing
  in this PR changes that). TDD 3D's `Action.risk: RiskLevel` reuses the
  same enum `TaskNode.risk` already used, unaffected by *how* a node's risk
  value was produced. TDD 3E's future Kernel Scheduler will consume
  `TaskNode.assigned_agent_category`/`status` from a *published*
  `TaskGraph` once that exists — this PR produces the value but does not
  yet publish it, so 3E still has nothing to consume from this PR alone.
