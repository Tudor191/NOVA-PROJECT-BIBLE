# 10 — Fork 3B-4 Resolution: the Reasoning → Planning Boundary

**Status: research only. No production code, test, contract, or workspace
configuration changes. Nothing here is authorized for implementation until
explicitly approved.** This document performs the dedicated, full
investigation of Fork 3B-4 (first surfaced in
`09-3b-preimplementation-verification.md` §1) requested before any Phase 3B
implementation begins: exactly how `planning-engine` should obtain the
content it needs when a reasoning process completes. Every claim is
verified directly against the repository as it stands after Phase 3A
(`2f064bd`) and the Phase 3B research pass (`1379f80`) — nothing is taken
from architecture documents alone.

---

## Executive Summary

`planning-engine` as designed in `05-tdd-3b-planning-engine.md` cannot
build a `TaskGraph` from what `reasoning-engine` actually publishes today,
for two independent, both-confirmed reasons: the TDD names a subject
(`reasoning.result`) that has never existed in this codebase, and even the
real subject's payload carries no objective or decision content at all —
only IDs, scores, and enums. This document traces the complete path in
code (§2-3), enumerates exactly what `planning-engine` needs (§4), and
evaluates the two previously identified resolution options plus a search
for a third (§5-7) against eleven separate architectural dimensions (§8-12).

**Recommendation: Option A** — additively extend
`ReasoningProcessCompletedPayload` with `objective_text: str` and
`chosen_description: str | None`, following the exact precedent already
set by `CommunicationSessionCompletedPayload`'s own enrichment in Phase
2D-D. `reasoning.process.completed` currently has **zero subscribers
anywhere in the codebase** — this is a genuinely un-risky additive change,
not a modification to a working integration. Option B (a new
`reasoning_process_id`-keyed read path) is rejected: it has no precedent
anywhere in this repository for this exact shape, it introduces a
synchronous, liveness-coupled dependency where the architecture's own
consistency model (`docs/architecture/10-inter-engine-communication.md`
§4) calls for eventual consistency, and it adds a second RPC pair for no
benefit Option A doesn't already provide. One additional, disclosed
refinement to Option A is recommended and flagged for approval: also
propagate `privacy_hint: PrivacyLevel`, since `objective_text` can
plausibly be privacy-sensitive and no reasoning-engine payload propagates
this classification today (§10).

Both the subject-name correction and the payload enrichment require a
small, precisely-scoped change to `reasoning-engine` and `nova-contracts`
— classified in §17 as a **required prerequisite for 3B**, not optional,
not unrelated debt. Nothing is implemented in this pass.

---

## 1. Verified Current-State Evidence

Every fact below is a direct code read, not an inference from a document.

| Claim | Verified at |
|---|---|
| The registered subjects for `reasoning-engine`'s completion events are `reasoning.reason.request`, `reasoning.reason.reply`, `reasoning.process.completed`, `reasoning.process.failed`, `reasoning.human_override.applied` | `packages/nova-contracts/src/nova_contracts/events/reasoning.py:98,129,154,172,187` (`@register_payload` decorators) |
| No subject named `reasoning.result` is registered anywhere | Same file, full-file grep for `register_payload`, 5 hits, none matching |
| `reasoning-engine`'s own publish call site uses the literal string `"reasoning.process.completed"` | `services/reasoning-engine/src/nova_reasoning_engine/domain/pipeline.py:594-595` (`_completed_outbox_event`, `subject="reasoning.process.completed"`) |
| `reasoning-engine`'s declared publishable-subjects allow-list matches exactly, no `reasoning.result` | `services/reasoning-engine/src/nova_reasoning_engine/events/published.py:19-30` |
| Phase 3A did not touch `_completed_outbox_event`, the payload class, `GoalsPort`, or `DEFAULT_VERIFY_THRESHOLD` | Direct read of current file contents at cited line numbers, cross-checked against `git show 2f064bd --stat`'s file list (§10 below) |
| **Zero engines currently subscribe to `reasoning.process.completed` or `.failed`** | Full-repo grep of every `services/*/src/*/events/subscribed.py`'s `SUBSCRIBABLE_SUBJECTS` — 9 files checked, none list either subject |
| The stale `reasoning.result` subscriptions in `knowledge-engine`/`memory-engine` were removed, not rewired to the real subject | `services/knowledge-engine/src/nova_knowledge_engine/events/subscribed.py:13-20`, equivalent in `memory-engine`; both leave an explanatory comment, neither lists `reasoning.process.completed` in `SUBSCRIBABLE_SUBJECTS` |
| Architecture docs still say `reasoning.result` today, uncorrected since the Project Health Review | `docs/architecture/06-ai-layer-architecture.md:81`, `docs/architecture/10-inter-engine-communication.md:84`, `docs/architecture/20-engine-responsibility-boundaries.md:64` |
| `communication-engine` is the **only** current caller of `reasoning.reason.request` (the synchronous RPC path) | `services/communication-engine/src/nova_communication_engine/clients/reasoning_client.py:41-53`; repo-wide grep for `reasoning.reason.request` finds no other caller |
| `executive-cognition-engine` has **no** Reasoning-related port, client, or call site at all | Grep of `services/executive-cognition-engine/src/` for `ReasoningPort`/`reasoning.reason.request`/`ReasoningProcessCompletedPayload` — zero hits |
| The synchronous RPC reply (`ReasoningReplyPayload`) already carries `chosen_description`/`explanation`, unlike the broadcast completion payload | `packages/nova-contracts/src/nova_contracts/events/reasoning.py:129-151` |

**Implication:** today, exactly one real path into `reasoning-engine`
exists in production code — `communication-engine`'s synchronous
`reasoning.reason.request`/`.reply` during a conversation turn — and the
engine that originates that call already receives full content back
directly, with no need for a completion-event subscription at all. The
asynchronous "reasoning concludes → downstream engine reacts" path
`planning-engine` is designed around (`docs/architecture/10-inter-engine-communication.md`
row 5) has **never yet been exercised by any real consumer**. This
materially changes the risk profile of both options (§8-12): there is no
existing behavior to preserve or break.

## 2. Exact Reasoning → Planning Data Flow (as designed, before any fix)

```
reasoning-engine (pipeline.run(), any mode/outcome)
   └─ terminal outcome "decided" or "degraded"
        └─ domain/pipeline.py:589-608  _completed_outbox_event(process, confidence_score, outcome, execution_duration_ms)
             └─ OutboxEvent(subject="reasoning.process.completed",
                             payload=ReasoningProcessCompletedPayload(
                                 reasoning_process_id, correlation_id, requesting_engine,
                                 user_id, reasoning_mode, reasoning_level,
                                 confidence_score, execution_duration_ms, outcome
                             ))
             └─ repository.finalize(...) persists the outbox row transactionally
        └─ nova_service_kit.dispatch_ready_events() (worker loop) publishes it
             for real onto the Event Bus under "reasoning.process.completed"

planning-engine (as TDD 3B §6.1 designs it)
   └─ subscribes to "reasoning.result"  ◄── DOES NOT EXIST (§1)
   └─ (even if corrected to "reasoning.process.completed") receives a
      payload with reasoning_process_id, confidence_score, outcome, mode,
      level, duration -- and nothing else
   └─ cannot construct TaskGraph.root_objective or any TaskNode without
      the objective/decision content this payload does not carry
```

Terminal outcome semantics, confirmed directly:
`_completed_outbox_event`'s own docstring (`pipeline.py:592-593`) states it
is "published for every terminal outcome that produced a decision --
`decided` or `degraded` alike." `failed`/`abandoned` route to
`reasoning.process.failed` instead (`pipeline.py`, `_failed_outbox_event`
equivalent construction, confirmed via the same publishable-subjects list).
This means `planning-engine`'s eventual confidence-threshold check (Fork
3B-3) is a genuine second gate layered on top of reasoning-engine's own
already-applied verify/override thresholds — a `degraded` outcome has
already failed reasoning-engine's own verify bar once before
`planning-engine` ever sees it.

## 3. Required Planning Inputs

Traced directly from `TaskGraph`/`TaskNode` (`docs/architecture/06-ai-layer-architecture.md`
§3, byte-identical in TDD 3B §2.1) and planning-engine's own responsibilities
(TDD 3B §6.1, Bible Part 9's Objective Understanding/Decomposition
sections):

| Field | Mandatory or optional | Source needed |
|---|---|---|
| `TaskGraph.root_objective: str` | **Mandatory** — this is the entire seed for decomposition; Bible Part 9's own "Objective Understanding" section is explicit that planning cannot begin without knowing "the true objective." | The reasoning process's `objective_text` — not persisted or exposed anywhere downstream today (§1). |
| A signal of *what was concluded* (used to shape the first-pass decomposition, not just trigger it) | **Mandatory in practice**, though TDD 3B §6.1 does not say so explicitly — a `TaskGraph` seeded from the objective alone but blind to what reasoning actually decided would decompose the *question*, not the *answer* to it, which is not what "Reasoning concludes → Planning consumes" (`10-inter-engine-communication.md` row 5) describes. | The reasoning process's chosen `Alternative.description` / `Decision.explanation.chosen_reason` — same non-existence problem. |
| `TaskGraph.critical_path`, individual `TaskNode`s, `Estimate`, `RiskLevel` | **Not inputs from reasoning-engine at all** — these are planning-engine's own decomposition output, computed from the objective/decision content above, not received pre-formed. | N/A — internal to `planning-engine`. |
| Trigger signal (that a process completed, and how confident it was) | **Mandatory**, already fully satisfied by the real, existing `reasoning.process.completed` payload once the subject name is corrected. | `reasoning_process_id`, `confidence_score`, `outcome`, `reasoning_mode`/`level` — all already present, no gap. |
| `requesting_engine`, `user_id`, `correlation_id` | **Mandatory for correct scoping/tracing** — already present on the existing payload, no gap. | Already satisfied. |
| Anything else on `ReasoningTrace`/`Decision` (evidence IDs, confidence breakdown, hypothesis history, model used) | **Optional / not needed** — `TaskGraph`/`TaskNode` have no field for any of this (confirmed against doc 06 §3's schema, §2.1 of TDD 3B), and Bible Part 9 never asks planning to justify its plan against reasoning's internal evidence trail. | Not required; explicitly excluded from scope by this analysis. |

**Conclusion: exactly two pieces of content are missing and mandatory** —
`objective_text` and a decision-level description (`chosen_description`,
mirroring the field name and shape `ReasoningReplyPayload` already uses for
the identical concept on the synchronous path). Nothing else on
`ReasoningProcess`/`Decision`/`ReasoningTrace` is needed by `planning-engine`
as designed.

## 4. Option A Analysis — additive payload fields

**Shape:** add `objective_text: str` and `chosen_description: str | None = None`
to `ReasoningProcessCompletedPayload`; populate both in
`_completed_outbox_event` from `process.objective_text` and the already
locally-available chosen `Alternative.description` (the same value
`ReasoningReplyPayload.chosen_description` is already populated from
elsewhere in `pipeline.py`).

- **ADRs:** squarely inside ADR-024's own decision (`docs/architecture/adr/ADR-024-interface-versioning-from-day-one.md:52-57`):
  *"Adding a field to an existing payload is never a version bump... this is
  the additive case, and it is the default, expected kind of change."*
  No `schema_version` bump needed; ADR-024 explicitly classifies this as
  the *unremarkable* case, not an exception requiring justification.
- **RPC patterns:** none needed — this stays a pure async publish/subscribe
  change, the pattern already governing this exact edge (`ReasoningProcessCompletedPayload`
  is only ever outbox-published, never RPC-replied).
- **Payload conventions:** direct precedent, not analogy — Phase 2D-D's
  `CommunicationSessionCompletedPayload` enrichment (task #197) added
  `corrections`/`preferences`/`feedback`/`decisions: list[str]`
  ("sourced verbatim from the session's own `ConversationMemory` at close
  time") to a completion event specifically so `digital-twin-engine` could
  learn from it **without a callback to `communication-engine`**. This is
  the identical shape: substantive content added directly to a terminal
  completion payload for exactly the downstream consumer that needs it.
  Priority 3's own "reasoning-engine additive contract fields" work (task
  #164) is the same pattern applied to `reasoning-engine` itself, one phase
  earlier.
- **Ownership:** `objective_text` is already owned data — it lives on
  `ReasoningProcess`, which `reasoning-engine` already owns exclusively
  (ADR-026 §2: "Reasoning Engine owns none of [the six upstream] systems...
  Its own persistent state... is limited to artifacts of its own reasoning
  processes"). Publishing it doesn't create a new ownership question; it
  exposes existing owned data the same way every other completion payload
  in this codebase already does.
- **`nova-contracts` conventions:** additive-only, one file
  (`events/reasoning.py`), no new file, no new registration mechanism — the
  smallest possible `nova-contracts` change of the two options.
- **Persistence/repository patterns:** zero new persistence anywhere.
  `process.objective_text` and the chosen alternative are already local
  variables in scope at the exact point `_completed_outbox_event` is
  called (confirmed: `pipeline.py`'s `run()` holds both `process` and
  `chosen` for the entire non-Reactive path). No new column, no new
  migration, no new repository method.
- **Security/identity boundary:** the substantive finding of this pass —
  see §10 (dedicated section, both options analyzed there together).
- **Failure/degraded-mode behavior:** none introduced. `objective_text` is
  a required field on `ReasoningProcess` (`domain/models.py:166`, no
  default, always populated at request time) — there is no code path where
  it could be missing when `_completed_outbox_event` runs. `chosen_description`
  mirrors the existing optionality already proven correct for
  `ReasoningReplyPayload.chosen_description` (`None` for `abandoned`/`failed`
  outcomes, which never reach this function anyway since only
  `decided`/`degraded` do).
- **Testability:** one contract round-trip test
  (`nova_contracts.events.planning`-style test, mirroring every existing
  payload contract test in this codebase) plus updating whichever
  `reasoning-engine` unit test currently asserts on `_completed_outbox_event`'s
  payload shape (if any — needs to be checked at implementation time, not
  assumed).
- **Real-infra verification:** no new real-infra surface. The event still
  flows through the exact same outbox-dispatch mechanism every other
  engine's completion event already uses and already has real-infra
  coverage for.
- **New architectural dependency direction: none.** The edge stays exactly
  `reasoning-engine → event → planning-engine`, one-directional, async,
  matching `docs/architecture/10-inter-engine-communication.md` row 5 and
  its own §4 consistency model verbatim ("eventually consistent across
  engines"). `planning-engine`'s liveness/availability remains fully
  decoupled from `reasoning-engine`'s at consumption time — it processes
  whatever the event carries whenever it happens to be running, the same
  as every other subscriber in this system.

## 5. Option B Analysis — new read path keyed by `reasoning_process_id`

**Shape:** keep `ReasoningProcessCompletedPayload` as-is; `planning-engine`
resolves `reasoning_process_id` into content via a new synchronous call
back to `reasoning-engine` (REST or a new RPC pair) after receiving the
completion event.

- **ADRs:** no ADR forbids this shape outright, but none of ADR-004
  (event bus is the only *cross-engine* channel — satisfied either way,
  since even Option B's "read path" would have to be RPC-over-the-bus, not
  a direct call, per ADR-004's own absolute wording), ADR-024, or ADR-026
  specifically endorses it either. ADR-026's own boundary test ("not
  storing information, transforming information into decisions") is
  satisfied by `reasoning-engine` either way; this isn't an ownership
  violation, just a different transport shape for the same owned data.
- **RPC patterns:** would need a **new** request/reply pair
  (`reasoning.process.request`/`.reply`, or similar) or a new REST route —
  neither exists today. The closest existing shape,
  `reasoning.reason.request`/`.reply`, is not reusable as-is: it *starts* a
  new reasoning process (`ReasoningRequestPayload.objective_text` is a
  required input, not something you'd have on hand if you're trying to
  look up a process that already ran), so it cannot double as a
  "resolve an existing process's content" query without its own new
  request/reply shape.
- **Payload conventions:** **no precedent found anywhere in this
  repository** for "engine B receives a terminal/completion event carrying
  only an ID from engine A, then engine B calls back into engine A to
  resolve that ID into content." Every existing cross-engine RPC pull
  pattern in this codebase (`MemoryPort`, `KnowledgePort`, `DigitalTwinPort`
  — checked directly, `services/communication-engine/src/nova_communication_engine/clients/digital_twin_client.py:34-54`)
  is a **proactive, query-shaped pull** keyed by something the caller
  already independently knows (`user_id`, a search query) *before* forming
  its own conclusion — never a **resolve-the-ID-from-an-event-I-just-received**
  pattern. This is a materially different shape from every existing Port
  in this codebase, not a reuse of one.
- **Ownership:** no violation, but it does add new public surface to
  `reasoning-engine` (a new route or RPC) whose only purpose is serving
  content a completion event could have carried directly — a second way to
  get the same information out, which this codebase has consistently
  avoided elsewhere (confirmed: no other engine maintains both an enriched
  completion event *and* a separate by-ID content-resolution endpoint for
  the same data).
- **`nova-contracts` conventions:** a strictly larger change than Option A
  — a new request payload, a new reply payload, plus registering both,
  versus Option A's two fields on an existing payload.
- **Persistence/repository patterns:** no new persistence needed (reuses
  already-existing `get_decision_for_process`/`get_trace_for_process`
  repository methods, `domain/ports.py:198-204`) — but those methods would
  need to be newly exposed at the API/event boundary, which is new surface
  regardless of the persistence layer being reused.
- **Security/identity boundary:** see §10 — largely the same exposure
  profile as Option A for the content itself, but with one additional
  concern Option A doesn't have (an unauthenticated-by-default internal
  RPC surface resolving arbitrary `reasoning_process_id`s, unless scoped —
  see §10).
- **Failure/degraded-mode behavior:** genuinely new failure modes Option A
  does not have. `planning-engine` would need explicit timeout/degraded
  handling for the resolve-call (mirroring `MemoryPort`/`KnowledgePort`'s
  500ms-timeout-then-degrade convention, `docs/architecture/10-inter-engine-communication.md:109`)
  — meaning decomposition could now fail or degrade for a reason entirely
  unrelated to the reasoning process's own outcome (reasoning-engine being
  transiently unavailable at the moment planning-engine tries to resolve
  it), a failure mode Option A structurally cannot have once the event is
  received.
- **Testability:** larger surface — a new fake port
  (`FakeReasoningProcessLookupPort` or similar) in `planning-engine`'s own
  test fakes, plus an integration test proving the round trip, plus a
  timeout/degraded-mode test. Confirmed as strictly more test surface than
  Option A's single contract round-trip test.
- **Real-infra verification:** introduces a **new** real-infra-relevant
  scenario Option A does not have — reasoning-engine down/unreachable at
  decomposition time — requiring its own coverage, not something the
  existing restart-survival test (TDD 3B §12) already exercises.
- **New architectural dependency direction:** this is the material
  finding. The edge direction (`Planning depends on Reasoning`) does not
  reverse, but its **coupling strength changes** — from `10-inter-engine-communication.md`
  §4's "eventually consistent across engines" async model to a
  synchronous, liveness-coupled call at the exact moment `planning-engine`
  tries to act on an event it already received. This is a **strictly
  stronger coupling than the architecture's own stated consistency model
  calls for on this edge**, introduced solely to work around a payload gap
  Option A closes without any coupling change at all.

## 6. Any Repository-Backed Alternative

Searched specifically for a third option with **concrete precedent**, per
the explicit instruction not to invent one. Two candidates were considered
and rejected for lack of precedent or for requiring an actual redesign
(out of scope for a Fork 3B-4 resolution pass):

- **Route reasoning-triggered planning through `executive-cognition-engine`**
  (which per `docs/architecture/10-inter-engine-communication.md` row 4 already
  orchestrates upstream context calls) rather than a direct
  `reasoning-engine → planning-engine` event. **Rejected — no precedent.**
  Directly checked: `executive-cognition-engine` has zero Reasoning-related
  port or call site today (§1 table). Building one would mean
  redesigning doc 10 row 5's own documented edge
  (`reasoning-engine → reasoning.result → planning-engine`, direct,
  producer-to-consumer), which is a genuine architecture change to an
  already-approved cross-engine flow, not a Fork-3B-4-scoped fix.
- **Have the *requesting* engine (today, only `communication-engine`)
  forward the content it already receives synchronously.**
  **Rejected — no precedent, and wrong shape.** `communication-engine`
  already has the full `ReasoningReplyPayload` content via its own
  `ReasoningClient` — but doc 10 row 6 is explicit that the "may notify
  user of roadmap" decision belongs to `communication-engine` acting on
  `planning.task_graph.created` (the *output* of planning, not an input
  to it) — nothing in this codebase's design ever routes planning inputs
  through the conversational layer, and doing so would make
  `planning-engine`'s trigger depend on which engine happened to originate
  the reasoning call, breaking the "any reasoning process, any origin, can
  seed a `TaskGraph`" generality doc 10 row 5 depicts.

**No third option with concrete repository precedent was found.** The
choice is between Option A and Option B as originally identified.

## 7. Contract and Ownership Analysis (both options together)

Both options keep `reasoning-engine` as the sole owner and sole writer of
`ReasoningProcess`/`Decision`/`ReasoningTrace` — neither creates a
duplicate store or a second source of truth. The distinction is purely
**how** already-owned data crosses the boundary once:

- Option A: crosses once, at publish time, as part of the event
  `reasoning-engine` already produces for this exact purpose.
- Option B: crosses on demand, at `planning-engine`'s request, via new
  surface built specifically to serve it.

Neither option gives `planning-engine` write access to anything in
`reasoning-engine`'s schema, and neither requires `reasoning-engine` to
know anything about `planning-engine`'s own existence beyond "something
may subscribe to this event" (Option A) or "something may call this route"
(Option B) — both preserve ADR-004's "engines never call each other
directly" rule equally (Option B's call would still have to be RPC-over-the-bus,
not a direct import or HTTP call bypassing the bus).

## 8. Security Analysis

This is the most substantive finding of this pass beyond the original
subject-name/content gap, and it applies to **both** options equally since
both cross the same content across the same boundary — only the transport
differs.

**`objective_text` and `chosen_description` are user-content-derived and
can plausibly be privacy-sensitive.** Confirmed via
`communication-engine/clients/reasoning_client.py:36-49`: `objective_text`
is passed straight through from whatever the user said in conversation
(`ReasoningRequestPayload.objective_text`), with no sanitization or
classification applied anywhere in that path.

**`reasoning-engine` already tracks a privacy classification, but it is
inert today.** `PrivacyLevel` (`packages/nova-contracts/src/nova_contracts/events/memory.py:61-70`,
"Bible Part 7's privacy classification, propagated on every entity") has
four tiers: `public`/`internal`/`confidential`/`highly_sensitive`.
`pipeline.run()` accepts `privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL`
(`domain/pipeline.py:171`), threaded into hypothesis/alternative generation
for model-routing purposes (ADR-020's "highly sensitive → local connectors
only"). **But `privacy_hint` is not a field on `ReasoningProcess`,
`Decision`, or `ReasoningTrace`** (confirmed absent from all three classes
in `domain/models.py`), **is not exposed on `ReasoningRequestPayload`**
(confirmed absent, `events/reasoning.py:99-126`), and **is not read
anywhere in `api/reason.py` or `events/handlers.py`** (confirmed via grep,
zero hits in either file). Every reasoning process reachable through the
real, public API or event surface today silently runs at the
`PrivacyLevel.INTERNAL` default — there is currently no way for any real
caller to mark a process `confidential`/`highly_sensitive` at all, which
bounds the *current* practical risk (nothing flowing through production
code today is above `internal`) but does not make the underlying gap
disappear, since this is a hardcoded default, not an enforced ceiling.

**This is already, today, a live exposure on the synchronous path** —
`ReasoningReplyPayload.chosen_description` (`events/reasoning.py:133`)
already carries this exact class of content back to `communication-engine`
on every `reasoning.reason.request` call, with zero privacy gating. Option
A does not introduce a new *kind* of exposure; it changes its *scope*: a
synchronous reply goes to exactly the one engine that originated the
request (which, by definition, already possesses the objective text — it
supplied it); a broadcast event goes to every current and future
subscriber, most of which will not have originated the request and would
not otherwise see this content. **This scope change is real and should be
weighed, not dismissed** — it is the reason `objective_text` should not be
added to the payload silently as a bare string with no accompanying
classification.

**Recommendation for the smallest appropriate representation (per
instruction 7):** truncating or summarizing `objective_text` would defeat
`planning-engine`'s actual functional requirement — Bible Part 9's
"Objective Understanding" is explicit that planning cannot proceed without
the *true* objective, and a redacted stand-in would not let planning-engine
do its job (§4 above). Summarization is therefore not viable as a privacy
mitigation here. Instead, the smallest *additional* change that
meaningfully mitigates the scope increase is to **also propagate
`privacy_hint: PrivacyLevel` alongside the two content fields**, so that
`planning-engine` (and any future subscriber) can make its own
policy decision — e.g., decline to decompose, or decline to further
propagate full text on `planning.task_graph.created`, for
`confidential`/`highly_sensitive` processes — the same "the engine that
receives the signal decides what to do with it" pattern ADR-032 already
establishes for identity confidence, applied here to privacy instead. This
is flagged as a recommended refinement, not a resolved decision — see §16.

**Not found:** any existing document or ADR that treats `objective_text`
specifically as forbidden-to-cross-boundary. Nothing in ADR-032 (identity/authorization,
confirmed non-binding on this boundary in `09-3b-preimplementation-verification.md`
§2) or elsewhere prohibits this content from ever leaving `reasoning-engine`
— it is already designed to leave (via the synchronous reply). The finding
here is about scope and classification, not about a prohibition being
violated.

## 9. Failure and Degraded-Mode Analysis

Already covered per-option in §4/§5; summarized together:

| Scenario | Option A | Option B |
|---|---|---|
| `objective_text` missing at publish time | Cannot happen — required field, always populated (`domain/models.py:166`). | N/A (payload unchanged). |
| Chosen alternative absent (`abandoned`/`failed` outcome) | N/A — those outcomes never reach `_completed_outbox_event` (routed to `.failed` instead). | N/A (payload unchanged either way). |
| `reasoning-engine` unavailable at the moment `planning-engine` needs the content | Not a new failure mode — `planning-engine` either has the event (already fully self-contained) or doesn't (nothing to degrade). | **New failure mode**: the resolve-call can time out or fail independent of the reasoning process's own outcome; requires new degraded-mode handling (`10-inter-engine-communication.md:109`'s 500ms-timeout-then-degrade convention would need to be replicated here). |
| Decomposition proceeding with partial/stale content | Not applicable — content arrives atomically with the trigger. | Possible new class of bug: event received, resolve-call succeeds later against a since-mutated process (unlikely given `ReasoningProcess` is immutable post-completion, but a new code path to reason about that Option A does not introduce at all). |

## 10. Verification/Testability Analysis

Already covered per-option in §4/§5. Net comparison: Option A needs one
new contract round-trip test (matching every existing payload-contract
test in this codebase) and a check of whichever existing
`reasoning-engine` unit test asserts on the payload's field set. Option B
needs a new fake port, a new integration test for the RPC round trip, and
a new degraded-mode/timeout test — strictly more surface for the identical
functional outcome.

## 11. Dependency Impact

Neither option changes which engines depend on which in the direction
already established (`planning-engine` depends on `reasoning-engine`,
never the reverse, per `02-master-scope.md` §2's own graph). The
difference is coupling *strength* on that one edge, covered in full in §4/§5's
"New architectural dependency direction" rows — Option A preserves the
existing async/eventually-consistent shape; Option B would introduce the
only synchronous, liveness-coupled dependency on this specific edge in the
entire Phase 3 dependency graph.

## 12. Fork 3B-1 Revalidation (`Estimate`/`RiskLevel` shape)

**Re-checked against current repository. Unchanged, still open, still
requires explicit approval; no new evidence from this pass affects it.**

- `RiskLevel` proposal (Bible Part 14's 5-tier scale) — still the only
  canonical risk scale anywhere in this project (re-confirmed, no new
  scale introduced since `09-3b-preimplementation-verification.md`).
- `Estimate` proposal (`{effort_hours: float, confidence: float}`) — still
  genuinely undocumented anywhere; no canonical shape to extract instead.
- **New in this pass:** confirmed precisely which downstream TDDs actually
  depend on which half of this fork — see §14. `Estimate` has **zero**
  cross-TDD dependents; only `RiskLevel` does, and only from TDD 3D.

## 13. Fork 3B-2 Revalidation (WBS field gaps)

**Re-checked against current repository and Bible Part 9. Unchanged, still
open, still requires explicit approval; no new evidence from this pass
affects it.** `completion_criteria`/`deliverables`/`required_knowledge`/`required_tools`
remain absent from doc 06 §3's `TaskNode` schema (re-confirmed
byte-identical to TDD 3B §2.1's own block); TDD 3B's recommendation to
leave them absent for Phase 3, consistent with this project's own
established narrower-than-Bible scoping pattern
(`00-research-and-scope.md` §1.3, re-confirmed genuinely on-topic, not a
mis-citation), stands unchanged.

## 14. 3C/3D Dependency Revalidation

Re-checked directly against both TDDs' current text (not assumed from the
master scope doc):

- **`06-tdd-3c-capability-engine.md`**: confirmed **zero** technical
  dependency on any 3B output. Line 15: *"no technical dependency on
  `planning-engine` (`3B`); kept second in the [sequencing]..."* Lines
  75-76 mention `Estimate`/`RiskLevel` only as an analogous "same gap
  class" comparison for `CapabilityHandle`'s own, unrelated estimation
  problem — not a reuse or dependency. **3C depends on 3B for roadmap
  sequencing only, not for any concrete type, field, or contract.**
- **`07-tdd-3d-action-engine.md`**: confirmed a real, concrete dependency
  on exactly one 3B output — `RiskLevel`, reused verbatim (`ActionObject.risk: RiskLevel # reused from TDD 3B, Bible Part 14`,
  line 81), used again in §3.3's `ActionPriority`-vs-`RiskLevel`
  distinction (lines 117-121), in the "Estimate Risk" Action Principle
  stage (line 202), and in the ADR-032 policy gate
  `minimum_confidence_by_risk: dict[RiskLevel, float]` (line 235). **TDD
  3D does not reference or reuse `Estimate` anywhere** — its own line 68
  mentions "3B's `Estimate`" only as a comparison point for its own,
  separate `CapabilityHandle`-estimation gap, identical in shape to 3C's
  line 75-76 mention, not a dependency.

**Conclusion, correcting the prior report's looser framing:** Fork 3B-1's
`RiskLevel` half is the only piece of `planning-engine`'s output surface
with a real cross-TDD dependent (TDD 3D only). `Estimate`'s shape is
3B-local — approving or changing it affects nothing outside
`planning-engine` itself. This means `RiskLevel`'s resolution carries
materially more downstream weight than `Estimate`'s and should be flagged
as such when approval is sought.

---

## 15. Recommended Resolution

**Option A — additively extend `ReasoningProcessCompletedPayload`.**
Ranked against every criterion the task specified:

- **Architectural consistency** — preserves the existing async,
  one-directional, eventually-consistent edge exactly as
  `10-inter-engine-communication.md` §4 already establishes it for this
  boundary.
- **Minimum scope** — two fields on one existing payload class, zero new
  RPC pairs, zero new API routes, zero new ports.
- **Existing repository precedent** — direct, on-point precedent
  (`CommunicationSessionCompletedPayload` enrichment, task #197; Priority
  3's reasoning-engine additive fields, task #164). Option B has **no**
  precedent of its own shape anywhere in this codebase (§6).
- **Clean ownership** — no ownership boundary crossed differently than it
  already is on the synchronous path today.
- **Real end-to-end verifiability** — one contract test, no new real-infra
  scenario, no new degraded-mode logic to prove correct.
- **Avoiding duplicated state** — neither option duplicates state; this
  criterion doesn't distinguish them, but Option A avoids duplicating
  *access paths* (one way to get the content, not two).
- **Avoiding unnecessary new contracts** — Option A's contract change is
  the smaller of the two by a wide margin (§4 vs §5's contract-convention
  rows).
- **Avoiding leakage of internal reasoning details** — both options
  surface the same two fields; Option A does not leak *more* than Option
  B would, and the recommended `privacy_hint` addition (§10) mitigates the
  one legitimate scope-increase concern identified, for either option
  equally.

Option B is not recommended: it is the only path that introduces a new,
unprecedented RPC shape, a new synchronous liveness coupling on an edge
the architecture's own consistency model says should stay async, and
strictly more implementation/test/real-infra surface for an identical
functional outcome.

## 16. Exact Implementation Scope If Approved

**Not implemented in this pass. If approved, the scope would be:**

1. `packages/nova-contracts/src/nova_contracts/events/reasoning.py`:
   add `objective_text: str` and `chosen_description: str | None = None`
   to `ReasoningProcessCompletedPayload`. **Pending explicit confirmation**:
   also add `privacy_hint: PrivacyLevel` (§10's recommended refinement) —
   this would additionally require threading `privacy_hint` onto
   `ReasoningProcess` (currently absent, `domain/models.py:157-171`) and
   exposing it on `ReasoningRequestPayload` (currently absent) so a real
   caller could ever set it above the hardcoded `INTERNAL` default — a
   larger, second-order change the user should explicitly decide whether
   to fold into this fix or defer.
2. `services/reasoning-engine/src/nova_reasoning_engine/domain/pipeline.py`:
   populate both new fields in `_completed_outbox_event`
   (`pipeline.py:589-608`) from the already-in-scope `process`/`chosen`
   local values.
3. `05-tdd-3b-planning-engine.md`: correct all three `reasoning.result`
   references (§0, §1, §6.1) to `reasoning.process.completed`, and update
   §6.1 to name the two new fields as the decomposition seed.
4. `docs/architecture/06-ai-layer-architecture.md:81`,
   `10-inter-engine-communication.md:84`, `20-engine-responsibility-boundaries.md:64`:
   correct the stale `reasoning.result` references — **optional**, flagged
   as follow-up documentation cleanup, not blocking (§14/§17
   classification below).
5. A new contract round-trip test for the two (or three) new fields, plus
   a check of any existing `reasoning-engine` test asserting on
   `_completed_outbox_event`'s current field set.

## 17. Classification of Required `reasoning-engine` Changes (per instruction 9)

| Change | Classification |
|---|---|
| Add `objective_text`/`chosen_description` to `ReasoningProcessCompletedPayload` + populate in `_completed_outbox_event` | **Required prerequisite for 3B** — 3B cannot function as designed without this; blocks TDD 3B's core mechanism outright. |
| Correct TDD 3B's own `reasoning.result` references | **Required prerequisite for 3B** — implementing against a nonexistent subject name is not viable regardless of the payload-content question. |
| Add `privacy_hint: PrivacyLevel` to the same payload | **Optional follow-up**, recommended but not blocking — 3B can proceed without it if the user accepts the current-state risk bound (§10: nothing above `INTERNAL` reaches production callers today). |
| Thread `privacy_hint` onto `ReasoningProcess`/`ReasoningRequestPayload` so a real caller could set it above the hardcoded default | **Unrelated debt** — a pre-existing gap (privacy classification is inert for every real caller today), not created or worsened by 3B, out of scope for this fix regardless of which option is chosen. |
| Fix the three stale `docs/architecture/*.md` references to `reasoning.result` | **Unrelated debt** — documentation-only, does not block any implementation, already flagged once in `09-3b-preimplementation-verification.md` §14. |

---

## 18. Explicit Non-Goals

- No implementation of Option A, Option B, or any variant in this pass.
- No modification to `reasoning-engine`, `nova-contracts`, or any other
  package's actual code, tests, or migrations.
- No resolution of Fork 3B-1 or Fork 3B-2 — both re-confirmed open,
  neither decided here.
- No decision on whether to also fix the stale architecture-doc references
  — flagged, not resolved.
- No decision on the `privacy_hint`-propagation follow-up (§16 item 1,
  §17) — flagged as optional, not resolved.
- No Phase 3B, 3C, 3D, 3E, or 3-P implementation work of any kind.
- No workspace/scaffolding/CI changes.

## 19. Remaining Decisions Requiring Approval

1. **Approve Option A** (additive `ReasoningProcessCompletedPayload`
   fields) as the resolution to Fork 3B-4, or direct a different path.
2. **Decide whether to include `privacy_hint: PrivacyLevel`** in the same
   change (§10, §16 item 1) — and if so, whether to also thread it onto
   `ReasoningProcess`/`ReasoningRequestPayload` now or defer that as
   separately-tracked unrelated debt.
3. **Approve Fork 3B-1** (`Estimate`/`RiskLevel` shape) as originally
   proposed — now confirmed to specifically gate TDD 3D's own design, not
   TDD 3C's.
4. **Approve Fork 3B-2** (WBS field gaps left absent) as originally
   proposed.
5. **Decide whether the stale `docs/architecture/06/10/20.md` references**
   to `reasoning.result` should be corrected now, alongside this fix, or
   left as separately-tracked documentation debt.

---

## Summary for the user

1. **What is actually broken:** `planning-engine`, as designed in TDD 3B,
   subscribes to an event that does not exist (`reasoning.result`), and
   even the real event (`reasoning.process.completed`) carries no
   objective or decision content — only IDs, scores, and enums. Both facts
   are confirmed directly in code, not inferred from documentation.
2. **Why 3B cannot safely proceed as designed:** its entire trigger
   mechanism is non-functional against the real event surface, and even
   once pointed at the right subject, it has nothing to decompose from.
3. **Recommended option:** Option A — additively enrich
   `ReasoningProcessCompletedPayload` with `objective_text` and
   `chosen_description`, following the exact precedent already set by
   `CommunicationSessionCompletedPayload`'s own Phase 2D-D enrichment.
   Option B (a new read-back RPC) is rejected — no precedent anywhere in
   this repository, and it introduces a synchronous coupling this specific
   architectural edge was explicitly designed not to have.
4. **Exactly what would need to change:** two new fields in
   `nova-contracts`, a few lines populating them in `reasoning-engine`'s
   existing `_completed_outbox_event`, TDD 3B's own subject-name
   references corrected, and one new contract test — all classified as a
   required prerequisite for 3B, not optional.
5. **Decisions needed from you:** approve Option A; decide on the
   `privacy_hint` follow-up; approve Forks 3B-1 and 3B-2 as proposed
   (3B-1's `RiskLevel` half now confirmed to specifically gate TDD 3D);
   decide whether to fix the stale architecture-doc references now or
   later.

No production code, tests, or contracts have been changed. Stopping here
per instruction, awaiting approval before any implementation — including
the `reasoning-engine` prerequisite fix itself — begins.
