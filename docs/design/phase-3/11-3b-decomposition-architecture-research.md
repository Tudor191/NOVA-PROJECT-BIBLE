# Phase 3B Decomposition Architecture — Research Report

**Status: research only. No production code authorized. No implementation branch created.**

Filename note: the requested name (`10-3b-decomposition-architecture-research.md`)
collides with the existing `10-3b-4-resolution-and-preimplementation-verification.md`.
This document uses the next free number, `11`, instead.

---

## 1. Executive summary

The prior pre-implementation verification correctly identified that Phase 3B's
architecture defines decomposition's *input* (`reasoning.process.completed`'s
`objective_text`/`chosen_description`) and *output* (`TaskGraph`/`TaskNode`),
but never its *algorithm*. This report researches that gap directly against
the current repository rather than assuming an answer.

**Finding:** the repository already contains a complete, proven, ADR-approved
mechanism for exactly this kind of work — **ADR-020's "sole legal channel to
any model"** pattern (`ModelOrchestrationPort` + `clients/model_orchestration_client.py`
+ `ai_model.generate.request`/`.reply`), used today by `reasoning-engine` for
its own "AI performs the actual cognitive task" step (Hypothesis Generation).
ADR-020 explicitly anticipates this exact situation: *"Any future engine...
that turns out to need AI model access gets it the same way: through
`ai-model-orchestration-engine`... This ADR is written to need no revision
when that happens."*

**Recommendation: Option A (LLM-backed decomposition through the established
`ModelOrchestrationPort` pattern), scoped narrowly** — planning-engine owns
*orchestrating* decomposition (calling the model, validating the result,
materializing a `TaskGraph`) but not *understanding* the objective itself;
that understanding is the model call's job, identically to how reasoning-engine
already delegates hypothesis generation rather than reasoning about it
structurally.

This is **not a new architectural fork** in the sense of requiring a new ADR,
a new engine dependency direction, or a Phase 3 scope expansion. It **is** an
additive TDD 3B amendment (adding `ModelOrchestrationPort` to §3, and a
model-call-failure row to §8) — the same class of small, disclosed correction
already applied once to this TDD (Fork 3B-4, the `objective_text`/
`chosen_description` enrichment). Two genuinely open items remain and are
reported as forks requiring your approval before implementation: the
**idempotency mechanism** (§10 below) and **`assigned_agent_category`
ownership** (§9.4 below).

---

## 2. Existing architecture

**Event bus is the only legal cross-engine channel (ADR-004,**
`docs/architecture/00-overview-and-decisions.md:182-193`**).** Direct
engine-to-engine calls are forbidden; all interaction is an async event or a
synchronous request/reply RPC *through* the bus, enforced by CI import-linter
contracts, never a raw import or HTTP call into another engine's module.

**AI Model Orchestration Engine is the only legal channel to any model
(ADR-020,** `docs/architecture/adr/ADR-020-sole-legal-llm-provider-channel.md`**).**
No subsystem may import or call a provider SDK directly, for any modality.
Enforced by a dedicated import-linter contract (same mechanism as ADR-004).
The ADR's own "Future implications" section states this applies to *any*
future engine needing model access, unconditionally.

**The established per-engine pattern for consuming this channel** (confirmed
directly in `reasoning-engine`, the one engine that legitimately calls a
model today):

- `domain/ports.py` defines a narrow `ModelOrchestrationPort` Protocol:
  `async def generate(self, request: GenerateRequestPayload) -> GenerateReplyPayload`.
- `clients/model_orchestration_client.py` implements it: one `EventPublisher.request()`
  call to `"ai_model.generate.request"`, `GenerateReplyPayload.model_validate(envelope.payload)`
  on return, a longer-than-default timeout (10s) because generation is slow.
- Exactly one domain module calls it (`hypothesis_generation.py`) — every
  other domain decision in that engine is deliberately model-free and
  structural. The module's own docstring states the discipline explicitly:
  *"Every other scoring mechanism... is deliberately structural and
  model-free; this module is the deliberate, documented exception."*

**Structured-output mechanism already exists in the contract and is already
implemented at the connector layer.** `GenerateRequestPayload.tools:
list[ToolSchemaPayload]` (a JSON-Schema tool definition) and
`GenerateReplyPayload.tool_calls: list[ToolCallPayload]`
(`arguments: dict[str, Any]`) implement Bible Part 7 "Function Calling"
(ADR-023). `nova_ai_model_orchestration_engine/domain/tool_schema.py`
validates schemas and normalizes tool-call arguments across providers;
`connectors/anthropic_connector.py:105-122` genuinely parses `tool_use`
blocks into `ToolCall`s — this is real, working code, not a stub.
**Caveat, disclosed honestly:** no current caller actually exercises this
path. `reasoning-engine`'s own hypothesis generation uses free-text
generation plus regex parsing (`_NUMBERED_LINE`, `_CORRECTION_LINE` in
`hypothesis_generation.py`), not tool-calling. Tool-calling is implemented
and available, not yet proven by a real call site.

**Privacy classification is already a required field on every model
request.** `GenerateRequestPayload.privacy_hint: PrivacyLevel =
PrivacyLevel.INTERNAL` — every existing caller uses this same hardcoded
default; no caller anywhere sets it higher today (confirmed by repo-wide
read of every `ai_model.*.request` payload).

**Event delivery semantics (`docs/architecture/09-event-bus-architecture.md:126-130`):**
"Cognitive/planning/action events" (which `reasoning.process.completed`
belongs to) are **at-least-once, JetStream durable, consumer acks** —
duplicates are an expected, architected possibility, not an edge case.
`EventEnvelope.event_id: UUID` exists as a natural dedup key. No JetStream
native duplicate-detection window (`Nats-Msg-Id`) is wired into
`nova-eventbus-sdk` (confirmed: zero matches for `dedup`/`Nats-Msg-Id`/
`duplicate_window` in `packages/nova-eventbus-sdk/src/nova_eventbus_sdk/backends/nats.py`).

---

## 3. Evidence from current implementation

Files inspected directly for this report (beyond those already covered in
the prior verification pass):

- `services/reasoning-engine/src/nova_reasoning_engine/domain/ports.py` —
  the six-port + `ModelOrchestrationPort` shape.
- `services/reasoning-engine/src/nova_reasoning_engine/clients/model_orchestration_client.py`
  — the concrete adapter.
- `services/reasoning-engine/src/nova_reasoning_engine/domain/hypothesis_generation.py`
  — the one real call site; free-text + regex, not tool-calling.
- `packages/nova-contracts/src/nova_contracts/events/ai_model_orchestration.py`
  — full contract surface (`GenerateRequestPayload`/`Reply`, `ToolSchemaPayload`,
  `ToolCallPayload`, `PrivacyLevel` reuse).
- `services/ai-model-orchestration-engine/src/nova_ai_model_orchestration_engine/domain/tool_schema.py`
  and `connectors/anthropic_connector.py` — tool-calling is real, implemented,
  provider-normalized.
- `docs/architecture/00-overview-and-decisions.md` — ADR-004/005/006 verbatim text.
- `docs/architecture/adr/ADR-020-sole-legal-llm-provider-channel.md` — full text.
- `docs/architecture/09-event-bus-architecture.md:126-130` — delivery-mode table.
- `packages/nova-contracts/src/nova_contracts/envelope.py` — `EventEnvelope` shape.
- `docs/design/phase-3/06-tdd-3c-capability-engine.md`,
  `07-tdd-3d-action-engine.md`, `08-tdd-3e-agent-os.md` — full re-read for
  `TaskNode`/`TaskGraph`/`RiskLevel`/`Estimate`/`assigned_agent_category` usage.
- Repo-wide search for `idempoten*` — no event-processing dedup precedent
  found anywhere (the handful of hits are unrelated "safe to call twice"
  idioms: `connect()`, `start()`, session-pause recovery).

---

## 4. Phase 3B requirements — separated by evidentiary status

| Status | Content |
|---|---|
| **Explicitly specified** | Subject name (`reasoning.process.completed`), payload shape (`objective_text: str`, `chosen_description: str \| None`), output shape (`TaskGraph`/`TaskNode`, doc06 §3 verbatim), that decomposition triggers on a confidence threshold (Fork 3B-3, value proposed not mandated), that mutation happens in place, not regeneration (§4). |
| **Implied, not stated** | That *some* AI-generation step is plausible, given `chosen_description` is described as something that "shapes the first decomposition pass" — a phrase that reads naturally as content-shaping input to a generation step, but TDD 3B never names a mechanism. |
| **Long-term Bible vision, not binding** | Bible Part 9's full "Objective → Mission → Project → ... → Completion" hierarchy, Priority Engine, Resource Allocation, Contingency Planning, Roadmap Generation, Execution Dashboard, Project Templates, Knowledge Reuse, Planning Memory. TDD 3B itself calls the decomposition hierarchy section "informational only" and implements none of these; not binding on Phase 3B. |
| **Proposed, requiring approval** | `Estimate`'s two-field shape (Fork 3B-1, already approved in PR #2), the confidence threshold value (Fork 3B-3), and — this report's own contribution — the recommended `ModelOrchestrationPort` addition to §3. |
| **Currently implemented** | `TaskNode`/`TaskGraph`/`Estimate`/`RiskLevel` domain types and the four structural-invariant functions (`find_cycle`, `find_dangling_dependencies`, `find_duplicate_ids`, `compute_critical_path`) — PR #2, merged. Nothing else. |

---

## 5. Decomposition ownership analysis

**Question:** should planning-engine itself decide how an objective becomes
a `TaskGraph`, or should another engine supply the structured result while
planning-engine validates and materializes it?

**Answer, evidence-based:** planning-engine owns *orchestration* —
constructing the model request, validating the response against domain
invariants, constructing/persisting the `TaskGraph` — but not *content
understanding*. Content understanding (turning natural-language text into
task objectives) is exactly the kind of "actual cognitive task" ADR-020 and
the reasoning-engine precedent reserve for a model call routed through
`ai-model-orchestration-engine`, never performed by the requesting engine's
own code.

This mirrors reasoning-engine's own internal split exactly: reasoning-engine
does not itself "understand" a user's objective by hand-written logic — it
calls a model for the one step that requires genuine understanding
(Hypothesis Generation) and keeps every other step (scoring, evaluation,
confidence blending) structural. Planning-engine's analogous split: call a
model for "propose a task breakdown," then apply the already-built,
already-tested structural checks (`find_cycle`, `find_dangling_dependencies`,
`find_duplicate_ids`, `compute_critical_path`) to whatever the model proposes
— the model never bypasses graph-validity guarantees; it only supplies the
graph's *content*.

This does **not** place content understanding inside `communication-engine`
(no communication-engine involvement in this path at all — TDD 3B §5's own
explicit "`planning-engine` never publishes to `communication.intent.*`"
stands unchanged) and does **not** move reasoning responsibilities into
planning-engine (reasoning-engine already produced its own decision before
this event fires; decomposition is a distinct, later cognitive act on that
decision's *content*, not a re-run of reasoning itself).

---

## 6. Option A analysis — LLM-backed structured decomposition

**Shape:** planning-engine defines `ModelOrchestrationPort` (new, in its own
`domain/ports.py`) + `clients/model_orchestration_client.py` (new — identical
pattern to reasoning-engine's), constructs a `GenerateRequestPayload` whose
`context` carries `objective_text`/`chosen_description`, sends it to
`ai_model.generate.request`, and parses the reply into `TaskNode`s. Structured
output can use the tool-calling mechanism (JSON-Schema-constrained, more
robust) or free-text + parsing (proven precedent, more fragile) — a
sub-decision for the implementation PR, not this research pass.

| Dimension | Finding |
|---|---|
| Architectural precedent | Direct: `reasoning-engine`'s `ModelOrchestrationPort`/`ModelOrchestrationClient`, used today. |
| Required new contracts | None in `nova_contracts.events.ai_model_orchestration` (the existing `GenerateRequestPayload`/`Reply` suffice). A new tool schema (e.g. `propose_task_graph`) if tool-calling is chosen — planning-engine-local, not a `nova-contracts` change. |
| Required ports | New `ModelOrchestrationPort` in `planning-engine`'s own `domain/ports.py` — additive, mirrors precedent exactly. |
| Dependency direction | planning-engine → event bus → ai-model-orchestration-engine, identical direction and mechanism every existing caller already uses. No new direction. |
| Engine ownership | planning-engine owns orchestration/validation; ai-model-orchestration-engine owns the actual model call (unchanged responsibility split). |
| Determinism | The model call itself is non-deterministic (same objective can decompose differently across calls). The *validation* layer around it stays fully deterministic (`find_cycle` etc. unchanged). TDD 3B's own testing strategy already anticipates this split — "scripted dependency shape" for structural unit tests, a fake/canned model reply for those tests, never a real model in unit tests. |
| Testing implications | Unit: fake `ModelOrchestrationPort` returning a scripted reply (exact precedent: reasoning-engine's own `test_connector_swap.py`-style fake-connector contract test, ADR-020's own stated verification method). Real-infra: would need a real ai-model-orchestration-engine + real provider (or its own fake connector) in the loop — see §11. |
| Observability implications | New counters analogous to `planning_task_graph_created_total` (§9 of TDD 3B, already specified) plus a model-call-latency/failure metric, mirroring `ai_model.request.completed`/`.failed`'s existing telemetry the orchestration engine already emits on its own side. |
| Failure/retry behavior | `GenerateReplyPayload.finish_reason == "error"` / `error` field already carries structured failure info (ADR-024 pattern) — planning-engine treats this the same way reasoning-engine's `HypothesisGenerationError` does: routed into this engine's own Failure and degraded behavior table (§8 of TDD 3B), not retried blindly. No new retry mechanism invented — reuses the existing "informative reply, not a bus timeout" pattern. |
| Security implications | None beyond ADR-020's existing boundary (no direct provider access, unchanged). |
| Privacy implications | Uses the same `privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL` default every other caller already uses — not a new privacy boundary (§11 below). |
| Compatibility with 3C | None — capability-engine (registry/sandboxing/built-in capabilities) has no dependency on decomposition mechanism, confirmed by TDD 3C's own "no technical dependency on planning-engine" statement. |
| Compatibility with 3D | `Action.risk: RiskLevel` (TDD 3D §2.1) reuses the same enum `TaskNode.risk` already uses — unaffected by *how* `TaskNode.risk` gets its value. |
| Compatibility with 3E | Kernel Scheduler (TDD 3E) consumes `TaskNode.assigned_agent_category`/`status` from the published `TaskGraph` regardless of how it was produced — unaffected by decomposition mechanism, only by the *shape* of what's published (§9 below). |
| Implementation complexity | Small-to-moderate: one new port, one new client (near-identical to an existing one), one new domain module (`decomposition.py`) containing the prompt-construction + response-validation logic, reusing all four existing structural-invariant functions unchanged. |
| New architectural dependency? | No — reapplies an existing, approved dependency direction to a new engine, exactly as ADR-020's own text anticipates. |
| Requires new ADR? | No. |
| Expands approved Phase 3 scope? | No — "objective decomposition" is TDD 3B's own stated deliverable (§0); this fulfills it rather than adding to it. |

---

## 7. Option B analysis — deterministic single-node placeholder

**Shape:** every `reasoning.process.completed` above threshold produces a
`TaskGraph` with exactly one `TaskNode` (`objective = objective_text`, no
dependencies, a fixed default `Estimate`/`RiskLevel`).

**Explicitly not recommended, per your own prior instruction** — evaluated
here only against TDD 3B's actual acceptance criteria, not for ease of
implementation.

| Dimension | Finding |
|---|---|
| Satisfies acceptance criteria? | Partially, and misleadingly. TDD 3B §13's criterion 1 ("no cycles, `critical_path` non-empty for any graph with more than one node") is technically satisfiable (a single-node graph has no cycles by construction), but a permanently single-node production path means the WBS/dependency-graph/critical-path machinery this TDD exists to build is **never exercised by real events**, only by hand-written multi-node unit-test fixtures. Bible Part 9's "recursively divided" framing and "Dependency Graph"/"Priority Engine" sections (informational, not binding, but the entire *reason* TDD 3B exists) go permanently unfulfilled by production traffic. |
| Architectural precedent | None specific to decomposition; general precedent for honest placeholders exists elsewhere (`GoalsPort` returning caller-supplied data, Phase 2B) — but those are explicitly disclosed as placeholders pending a real backing engine, not permanent production behavior for an engine whose entire Phase 3B deliverable *is* this exact mechanism. |
| Determinism | Fully deterministic — its only real advantage. |
| Testing implications | Trivial to test, but tests only prove the placeholder is a placeholder, not that decomposition works. |
| Risk (your own framing) | Exactly the risk you flagged: "would risk making Phase 3B appear complete while leaving its core semantic responsibility undefined." Confirmed by this analysis, not merely asserted. |

## 8. Option C analysis — deterministic/rule-based decomposition

**Shape:** a hand-written heuristic (e.g., split `chosen_description` on
sentence/clause boundaries, or keyword-triggered sub-task templates) mapping
text to multiple `TaskNode`s without a model call.

| Dimension | Finding |
|---|---|
| Existing precedent? | **None found anywhere in this codebase.** Repo-wide search for any text-parsing-into-structured-domain-object heuristic outside of the model-call pattern (regex-based *response* parsing, e.g. `hypothesis_generation.py`'s numbered-list regex, is parsing a *model's* output, not substituting for one) turned up nothing. Every place this codebase needs "natural language → structured multi-field content," it routes through `ai-model-orchestration-engine` (reasoning-engine's hypothesis generation, and by architectural mandate, everywhere ADR-020 applies). |
| Would this be an invented heuristic? | Yes, unambiguously — exactly the "arbitrary task-generation strategy" your original instruction told me not to invent absent explicit architectural requirement. No document requires or even suggests a rule-based approach anywhere. |
| Determinism | Fully deterministic — same advantage as Option B, same lack of any real "understanding" of the objective. |
| Recommendation | Not viable without a fresh, explicit design (would need its own TDD-level specification of the rule set, which doesn't exist and isn't implied by any current document) — effectively a new, larger design decision, not a smaller one than Option A. |

---

## 9. TaskGraph output ownership

### 9.1 Fields required now (Phase 3B) vs. later

| Field | Required now? | Evidence |
|---|---|---|
| `TaskNode.objective` | Yes | Doc06 §3 schema; the one field with no ambiguity. |
| `TaskNode.depends_on` | Yes | Needed for `find_cycle`/`find_dangling_dependencies`/`compute_critical_path` to have any real input; without it those functions only ever see trivial single-node graphs (Option B's own failure mode). |
| `Estimate` | Yes | Doc06 §3 schema field; `compute_critical_path` requires `effort_hours` on every node to function at all — already load-bearing in PR #2's own shipped code. |
| `RiskLevel` | Yes | Doc06 §3 schema field, required (not optional) on `TaskNode`. |
| `assigned_agent_category` | Optional at the type level (`str \| None`), but genuinely consumed downstream (TDD 3E §Kernel Scheduler: "query Registry for healthy candidates in `assigned_agent_category`") — see §9.4, a separate open fork on *who* sets it, not *whether* it's needed eventually. |
| Completion criteria / Deliverables / Required knowledge / Required tools | **Not required.** TDD 3B Fork 3B-2 already resolved this: doc06 §3 (schema source of truth) omits all four; TDD 3B's own recommendation is "leave absent for Phase 3." Not revisited by this report — expanding `TaskNode` for these would be exactly the "expand `TaskNode` because the Bible mentions it" the current instructions forbid. |
| Task ordering beyond `depends_on`/`critical_path` | Not required — no document specifies anything beyond the dependency graph and the one computed critical path. |
| Confidence (on the decomposition itself, distinct from `ReasoningProcessCompletedPayload.confidence_score`) | Not required — no document names a decomposition-level confidence field on `TaskNode`/`TaskGraph`. |

### 9.2 Estimate — ownership

**Decomposition itself is responsible.** `Estimate` lives on `TaskNode`
(doc06 §3, PR #2), and `compute_critical_path` (already shipped) consumes
`estimated_effort.effort_hours` directly per node — there is no later stage
in any TDD that (re)assigns `Estimate`. No second estimation model exists or
is proposed anywhere; this report does not create one.

### 9.3 RiskLevel — ownership

**Decomposition sets `TaskNode.risk`; this is distinct from, not shared
with, `action-engine`'s own `Action.risk`.** TDD 3D §3.3 explicitly notes
`ActionPriority` and `RiskLevel` are "independent axes," and `Action.risk`
is assigned by action-engine's own "Estimate Risk" pipeline stage (TDD 3D
§3.4, "Check Permissions" → "Estimate Risk" during *action* execution, not
at decomposition time) — a **separate risk classification of a specific
action about to run**, reusing the same `RiskLevel` *scale* (the whole
point of putting `RiskLevel` in `nova_contracts`, per PR #2's own
docstring), never the same *value* copied forward. No second risk model is
created by this report; the existing single scale is reused correctly on
both sides.

### 9.4 `assigned_agent_category` — a separate, smaller fork

**Not resolved by this research — reported as its own fork, per your
instruction #8.**

- **Evidence it's needed downstream:** TDD 3E's Kernel Scheduler explicitly
  keys off it (`08-tdd-3e-agent-os.md:121-125`): "query Registry for healthy
  candidates in `assigned_agent_category`."
- **Evidence it's *not* specified at decomposition time:** no document states
  whether decomposition itself should propose a category (e.g., as part of
  the same model call that proposes `TaskNode.objective`), or whether it
  should be derived deterministically afterward (e.g., a lookup/classifier
  step), or left `None` until agent-os's Kernel Scheduler assigns it at
  dispatch time (TDD 3E doesn't require it to be pre-populated — the
  scheduler *queries* by category, it doesn't require the category to have
  been set by any particular stage).
- **Why this isn't silently resolved here:** three genuinely different
  owners are plausible (decomposition itself, via the same model call;
  planning-engine, via a second deterministic step; agent-os, at dispatch
  time) and no document picks one.
- **Recommendation, not a decision:** the smallest-scope answer is to let
  the same decomposition model call optionally propose
  `assigned_agent_category` (it already has full context on each task's
  objective) and leave it `None` when the model doesn't supply one —
  `TaskNode.assigned_agent_category` is already `str | None` (PR #2), so
  this requires no schema change either way. But this is a recommendation
  for you to approve, not something implemented by this report.

---

## 10. Idempotency analysis

Confirmed premises (§2 above): `reasoning.process.completed` is at-least-once;
`EventEnvelope.event_id` exists; no dedup mechanism exists anywhere in this
codebase or in `nova-eventbus-sdk`'s NATS backend today.

| Option | Correct after restart? | Duplicate behavior | Memory growth | Concurrency | JetStream compatibility | Precedent | Requires persistence? | Expands this PR's scope? |
|---|---|---|---|---|---|---|---|---|
| **1. Defer until persistence exists** | N/A — nothing persisted yet either way | Each redelivery independently produces a `TaskGraph` (transient, in-memory, until the persistence PR lands) — not silently wrong, just not yet durable-correct | None | Trivial (no shared mutable state) | Fully compatible (consumer acks as normal; redelivery is just "run again") | Matches TDD 3B's own PR-splitting: "no mutation/merge logic... deferred to the persistence-layer PR, where 'mutation, not regeneration' is actually meaningful" (PR #2's gate review, §"Known, disclosed limitations") | No, for *this* PR | No — it's the honest absence of a mechanism, not a new one |
| **2. Lightweight in-memory dedup** | **No — lost on restart, the exact false-exactly-once impression you told me not to introduce** | Silently "fixed" only until next restart, then duplicates resume with no signal anything changed | Unbounded without an eviction policy (a new design problem of its own) | Needs a lock/concurrent-safe structure (new complexity) | No interaction with JetStream's own redelivery semantics — purely a local band-aid | None found anywhere in this codebase | No | Yes — invents a mechanism with no precedent, contradicts your stated position |
| **3. Persistent event-id dedup** | Yes | Second delivery recognized and no-op'd (or safely re-validated against the existing row) | Bounded by however long processed-event history is retained (a retention-policy decision) | Standard transactional-write concurrency, same as every other engine's persistence layer | Fully compatible | No direct precedent (no engine has built this exact table yet), but the *shape* — a natural-key check before insert — is the same discipline the transactional-outbox pattern already uses elsewhere in this codebase | **Yes** | Yes, if pulled into this PR — this is real persistence-layer work |
| **4. Existing infra mechanism (JetStream native dedup window)** | Yes, if wired up | Broker-level rejection of the duplicate `Nats-Msg-Id` within the window | Bounded by the configured window | Handled by the broker, not app code | Requires adding `Nats-Msg-Id` header support to `nova-eventbus-sdk`'s NATS backend — **does not exist today** (confirmed, §2) | None — would be new SDK work, shared across every engine, not planning-engine-scoped | No app-level persistence, but *does* require an SDK change outside this PR | Yes — a shared-package change, well beyond planning-engine's own PR |

**Recommendation, matching your own stated position:** **Option 1** for this
scoped PR — explicitly documented as "not yet idempotent, correctly so,
because nothing is persisted yet to be duplicated against" — with **Option 3
flagged as required, non-optional follow-up work for the persistence-layer
PR** (not "maybe," since correctness genuinely requires persistence, exactly
as your instruction anticipated: *"If correct at-least-once handling
requires persistence, explicitly say so."* Said here, explicitly.) Option 4
is a legitimate, cheaper long-term alternative to Option 3, but is
`nova-eventbus-sdk`-level infrastructure work outside any single engine's
scope — worth naming as a project-wide follow-up, not deciding now.

---

## 11. Privacy/security analysis

`objective_text`'s privacy status is unchanged by this research: TDD 3B/PR
#2 already disclose it as "potentially privacy-sensitive," with
`PrivacyLevel` propagation explicitly deferred, not silently added — this
report does not revisit or reopen that decision.

**Does routing `objective_text` through `ai_model.generate.request`
introduce a *new* privacy boundary?** No. Every existing caller of
`ai_model.generate.request` already sends its own request-specific text
through the identical `privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL`
default — including reasoning-engine's own hypothesis generation, which
already embeds the *same* `objective_text` (as `ReasoningRequestPayload.objective_text`,
the request that eventually produces `chosen_description`) in its own model
call today, under the same default. Planning-engine calling the same RPC
with the same text, under the same default, is not a new exposure — it's
the same text crossing the same boundary a second time, via the same
mechanism, under the same already-accepted default.

**No existing mechanism is missing here** — `privacy_hint` exists precisely
for this purpose; it's simply not yet elevated above `INTERNAL` by *any*
caller in the codebase, a pre-existing, already-disclosed, project-wide gap
(not specific to planning-engine, not newly discovered by this report). Per
your own standing instruction, this is not a security fork requiring a STOP
— the required mechanism exists and is used identically to every other
caller; there is no bypass.

---

## 12. Phase 3C/3D/3E dependency analysis

- **3C (capability-engine):** confirmed, no dependency in either direction
  (TDD 3C §0: "confirmed no technical dependency on `planning-engine`").
  Decomposition architecture choice has zero effect on 3C.
- **3D (action-engine):** depends only on the `RiskLevel` *enum* being
  stable (already shipped, unaffected by this research) and on
  `TaskNode`/`TaskGraph` existing as a concept action-engine's own
  `Action.depends_on: list[UUID]` can reference contextually — no field-level
  coupling beyond the shared enum.
- **3E (agent-os):** the only phase with genuine field-level coupling —
  Kernel Scheduler reads `TaskNode.status`/`assigned_agent_category` off the
  published `planning.task_graph.created` event. Whatever decomposition
  mechanism is chosen, the *published event shape* must satisfy this; Option
  A does, by construction (it still produces the same `TaskGraph`/`TaskNode`
  shape PR #2 already defined). The `assigned_agent_category` ownership fork
  (§9.4) is the one open item 3E's design is sensitive to — TDD 3E does not
  itself require the field be populated before dispatch time, so this fork
  does not block 3E's own design, only the completeness of 3B's own output.

---

## 13. Recommended architecture

**Option A**, scoped as follows for the eventual implementation PR:

1. New `ModelOrchestrationPort` in `services/planning-engine/src/nova_planning_engine/domain/ports.py`.
2. New `services/planning-engine/src/nova_planning_engine/clients/model_orchestration_client.py`,
   structurally identical to reasoning-engine's.
3. New `domain/decomposition.py`: builds a `GenerateRequestPayload` from
   `objective_text`/`chosen_description`, calls the port, validates the
   reply against the four existing structural-invariant functions
   (`find_duplicate_ids` → `find_cycle` → `find_dangling_dependencies` →
   `compute_critical_path`, in that order — matching `compute_critical_path`'s
   own already-implemented check ordering), raises a domain-level error
   (mirroring `HypothesisGenerationError`) on an invalid model reply rather
   than silently accepting a broken graph.
4. New `events/handlers.py`: `make_reasoning_process_completed_handler`,
   following the established `make_X_handler(app) -> handle(envelope)` shape,
   validating `ReasoningProcessCompletedPayload`, checking the confidence
   threshold (Fork 3B-3), calling into `decomposition.py`, publishing
   `planning.task_graph.created` (no persistence write in this PR — see §10).
5. `assigned_agent_category`: per §9.4's recommendation (pending your
   approval), let the same model call optionally propose it.

---

## 14. Required contract changes

**None to `nova_contracts`.** `GenerateRequestPayload`/`GenerateReplyPayload`
already suffice; `TaskNode`/`TaskGraph`/`Estimate`/`RiskLevel` already exist
(PR #2). `PlanningTaskGraphCreatedPayload` (named but not yet defined,
per `planning.py`'s own docstring and TDD 3B §11) would be added in the
implementation PR, not this research one — out of scope here since no
production code is authorized.

**Documentation-only change recommended:** an additive amendment to TDD 3B
§3 (add `ModelOrchestrationPort` to the Ports list) and §8 (add a
model-call-failure row, mirroring the existing `MemoryPort`/`KnowledgePort`
timeout row: "Decomposition proceeds with whatever context was retrieved
before the timeout" → analogous "`ai_model.generate.request` failure or
timeout during decomposition: no `TaskGraph` produced this cycle, error
logged, mirrors §8's existing no-silent-degradation discipline"). This
document does not make that edit — it is named here as the concrete,
smallest next step, for your approval.

---

## 15. Required implementation sequence

1. You approve (or amend) this report's recommendation, the `assigned_agent_category`
   fork resolution, and the idempotency-Option-1-now/Option-3-later split.
2. TDD 3B amendment (§3, §8) — small, additive, mirrors Fork 3B-4's precedent.
3. Create `phase-3b-decomposition-orchestration` from `phase-3b-planning-domain`.
4. Implement per §13 above.
5. Tests: unit (fake `ModelOrchestrationPort`, scripted replies, exercising
   every structural-invariant failure mode: cycle, dangling dependency,
   duplicate ID, malformed/missing `objective_text`), contract (payload
   round-trip if `PlanningTaskGraphCreatedPayload` is defined in this PR),
   real-infrastructure classification per §11 below.
6. Explicitly document Option-1 idempotency as "not yet correct, deliberately,
   pending persistence" in the PR's own description — not silently omitted.

---

## 16. New forks requiring your approval

### Fork R-1 — `assigned_agent_category` ownership (§9.4)

**Evidence:** TDD 3E consumes it; no document assigns who sets it.
**Options:** (a) same decomposition model call proposes it optionally, (b) a
separate deterministic classification step in planning-engine, (c) left
`None` until agent-os assigns it at dispatch. **Recommendation:** (a),
smallest scope, no schema change needed. **Blocks Phase 3B?** No — `None`
is already valid; this only affects *how complete* 3B's own output is, not
whether the PR can ship.

### Fork R-2 — idempotency mechanism (§10)

**Evidence:** at-least-once delivery confirmed; no dedup mechanism exists.
**Options:** four analyzed above. **Recommendation:** Option 1 now
(explicitly documented as provisional), Option 3 as required
persistence-layer-PR follow-up, Option 4 as a possible project-wide
`nova-eventbus-sdk` enhancement worth naming but not deciding now.
**Blocks Phase 3B?** No, if Option 1 is accepted and disclosed — blocks only
if you require durable-correct idempotency inside this specific PR, which
would in turn require pulling persistence into this PR's scope (a real
scope-expansion decision, flagged here rather than assumed).

Both forks are **advisory, not blocking**, unlike the original
decomposition-algorithm gap — Option A itself is not gated on either being
resolved before implementation begins, but neither should be silently
decided during implementation either.

---

## 17. Final recommendation

Implement decomposition via **Option A**: planning-engine's own
`ModelOrchestrationPort`, calling `ai_model.generate.request` through the
existing ADR-020 channel, exactly mirroring reasoning-engine's own
established pattern — with `assigned_agent_category` optionally proposed by
the same call (Fork R-1, pending your approval) and idempotency handled as
Option 1-now/Option 3-later (Fork R-2, pending your approval). This is not
a new architectural dependency, does not require a new ADR, does not expand
approved Phase 3 scope, and does not touch any other engine. It does require
a small, additive TDD 3B amendment before implementation begins, consistent
with this project's own established practice for this exact class of
disclosed gap.

No branch was created for implementation. No production code was written.
`main`, `phase-3`, and `phase-3b-planning-domain` were not modified directly
— this report itself lives on a dedicated, non-implementation branch,
`phase-3b-decomposition-research`, branched from `phase-3b-planning-domain`'s
current tip. Awaiting your approval on: the overall Option A recommendation,
Fork R-1, and Fork R-2, before `phase-3b-decomposition-orchestration` is
created.
