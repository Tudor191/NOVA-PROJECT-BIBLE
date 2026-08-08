# Phase 2D-C Closure — Priority 3 Gate Review: the communication-engine ↔ reasoning-engine conversation loop

**Scope of this review: Priority 3 only**, per direct instruction. Priorities
1, 2, 4, 5, and 6 of the
[closure design document](../../design/phase-2d/05-conversation-intelligence-closure.md)
are **untouched** — this review does not claim progress on any of them, and
none of their code was modified. Phase 2D-D has not been started.

**Decision: Go**, for Priority 3 as scoped. The previously-unwired
communication-engine ↔ reasoning-engine conversation loop now exists,
end-to-end, using real engine contracts and real implementations — see §6
for exactly what "end-to-end" does and does not mean here.

## 1. What was implemented

The approved design (closure doc §5.3, Fork #1 — **synchronous RPC**,
user-selected over the event-driven alternative):

```
communication.turn.received
  -> communication-engine (conversation_orchestration.handle_conversation_turn)
  -> reasoning-engine (reasoning.reason.request, synchronous RPC)
  -> reasoning result
  -> communication-engine (same function)
  -> intent gate (events.handlers.deliver_content_to_session, reused in-process)
  -> response delivery
```

Concretely:

1. **`domain/ports.py`** — new `ReasoningOutcomeResult` (BaseModel) and
   `ReasoningPort` (Protocol), following the exact shape and docstring
   convention `PersonalityPort`/`WorldModelPort`/`ModelOrchestrationPort`
   already established. `TimeoutError` propagates uncaught from the port,
   by design — mirrors `PersonalityPort.validate_response`'s own documented
   convention.
2. **`clients/reasoning_client.py`** (new) — `ReasoningClient`, calling
   `reasoning.reason.request` via the same `EventPublisher.request(...)`
   pattern `PersonalityClient`/`WorldModelClient`/`ModelOrchestrationClient`
   already use. No new RPC mechanics were invented.
3. **`events/published.py`** — `reasoning.reason.request` added to
   `PUBLISHABLE_SUBJECTS` (this engine is now a caller of that subject, not
   just reasoning-engine's own REST/RPC surface).
4. **`events/handlers.py`** — `make_intent_deliver_handler`'s delivery
   logic (memory-annotation application, `Thinking -> Speaking` transition,
   the intent-gate call itself, `Speaking -> Waiting` transition,
   interruption-resume offer, metrics) was **extracted, unchanged, into a
   new function `deliver_content_to_session`**. `make_intent_deliver_handler`
   is now a thin wrapper around it — a pure refactor, not a behavior change
   (verified: `test_events_communication_request.py`'s existing real-bus
   round-trip test for `communication.intent.deliver.request` passes
   unmodified).
5. **`conversation_orchestration.py`** (new module, deliberately outside
   `domain/` — it needs `app.state`/FastAPI, which `domain/ports.py`'s own
   docstring forbids `domain/` code from importing) —
   `handle_conversation_turn` (the directly-awaitable core logic) and
   `schedule_conversation_turn` (the fire-and-forget production entry
   point, tracked in a module-level `set` of tasks with a completion
   callback so a detached `asyncio.Task` cannot be garbage-collected
   mid-flight — a real `asyncio` footgun, not a hypothetical one).
6. **`main.py`** — wires a fourth upstream port (`reasoning_port`),
   defaulting to a real `ReasoningClient`, overridable for tests exactly
   like the other three.
7. **`config.py`** — `communication_engine_reasoning_rpc_timeout_ms`
   (default 10000ms — longer than the other RPC timeouts, since
   reasoning-engine's own pipeline may itself call memory/knowledge/
   world-model/ai-model before replying).
8. **`api/websocket.py`, `api/sessions.py`** — the three real call sites of
   `session_lifecycle.record_inbound_turn` (`_finalize_utterance`, the
   `InboundMessageKind.TEXT` branch, and `POST /sessions/{id}/messages`)
   now call `schedule_conversation_turn` immediately after recording the
   turn, instead of discarding its return value and doing nothing.

**Not implemented, by design (scope discipline, not an oversight):**
`ReasoningRequestPayload` was **not** extended with response-shaping hints
(style/verbosity/technical_depth). The closure document's own §5.3 sketched
this as part of a fuller design; the user's approval message's own loop
diagram omits it entirely, and building it would touch reasoning-engine's
pipeline internals for a capability neither the approval nor the required
test list asked for. Per Rule 7 ("do not invent new domain concepts if an
existing contract or model already covers the requirement") and the
instruction to keep this pass minimal, `ReasoningRequestPayload` is used
exactly as it already exists (`objective_text`, `user_id`,
`requesting_engine`). **Zero changes were made to reasoning-engine.**
This is a smaller footprint than the closure document's own Sec5.4 named
("reasoning-engine, communication-engine, nova-contracts") — disclosed here
per instruction #16 as a deviation, not decided silently: response-shaping
integration into the reasoning request remains open, undecided, and
unblocked by anything built this pass.

## 2. Exact contracts used

- **`reasoning.reason.request` / `reasoning.reason.reply`**
  (`nova_contracts.events.reasoning.ReasoningRequestPayload`/
  `ReasoningReplyPayload`) — already-registered, already-versioned
  (`schema_version: int = 1`) contracts, used verbatim. No contract change.
- **`communication.intent.deliver.request`'s reply shape**
  (`IntentDeliveryOutcome`, `domain/intent_gate.py`) — reused as the return
  type of both the RPC handler and the new orchestration path.
- **No new Event Bus subject was created.** `reasoning.reason.request` is
  an existing subject this engine is now also permitted to call (added to
  its own `PUBLISHABLE_SUBJECTS`, per ADR-004's declared-allow-list
  discipline) — reasoning-engine's own `SUBSCRIBABLE_SUBJECTS` already
  included it and required no change.

## 3. Architecture decisions

- **Synchronous RPC, not event-driven** (Fork #1, user-approved) —
  confirmed and implemented exactly: `ReasoningClient` uses
  `EventPublisher.request()` (request/reply), never `bus.subscribe()`.
  reasoning-engine gained no new subscription capability.
- **`deliver_content_to_session` is called in-process, not via a
  redundant self-directed bus RPC.** The user's own approval diagram names
  `communication.intent.deliver.request` as a step in the loop; this is
  satisfied by reusing that subject's exact delivery *logic* (extracted
  into a shared function both the RPC handler and the new orchestration
  call), not by communication-engine issuing a network round-trip to its
  own already-running process for a call already inside the same call
  stack. Rationale recorded directly in `events/handlers.py`'s own
  docstring: a same-process bus round-trip would add latency and a new
  failure mode (bus unreachable => can't deliver to a channel already
  live in the same process) for zero decoupling benefit, since ADR-004
  governs *cross-engine* boundaries and this call never crosses one. This
  was a judgment call made explicit rather than decided silently — flagged
  to the user in this review (§7) rather than treated as self-evidently
  correct.
- **Fire-and-forget, not blocking, at the call sites.** `send_message`'s
  own pre-existing docstring already documented "acknowledgment now, answer
  delivered later" as the contract; `schedule_conversation_turn` is what
  makes that already-promised behavior real for the first time, rather than
  changing the contract. The WebSocket loop must stay responsive (barge-in,
  further audio chunks) while reasoning-engine's pipeline runs, which an
  inline `await` would have blocked.
- **Reasoning failure/timeout/malformed-reply/non-`decided` outcome all
  collapse to one honest fallback path** (`FALLBACK_CONTENT`), routed
  *through* the intent gate (personality-validated), not bypassing it —
  because how NOVA describes its own failure to think is itself a
  personality-consistency concern, unlike the transport-level "voice
  unavailable" notice `api/websocket.py` already bypasses the gate for.
- **Confidence-tier mapping reuses `domain.addressee_fusion.
  confidence_tier_label`** rather than re-deriving the same four-tier
  thresholds a second time — justified directly by Doc 22 Principle 7's own
  text (reasoning conclusions and identity confidence share one Confidence
  Expression vocabulary).

## 4. Tests added

All in `services/communication-engine/tests/`:

- `tests/integration/test_conversation_orchestration.py` (new, 9 tests):
  successful reasoning result delivered through the intent gate;
  non-`decided` reasoning outcome falls back; reasoning timeout falls back;
  a `decided` outcome with no content (malformed reply) falls back;
  personality hard-stop rejection; no live channel connection; session gone
  before delivery returns `None` without raising; a **real Event-Bus round
  trip** where a stand-in bus client serves `reasoning.reason.request` for
  real and this engine's own (non-fake) `ReasoningClient` calls it,
  asserting the exact request payload reasoning-engine would receive; and
  an HTTP-triggered test proving `schedule_conversation_turn`'s production
  wiring itself (not just the function it schedules) reaches delivery.
- `tests/fakes/ports.py` — `FakeReasoningPort`, including a `hold:
  asyncio.Event | None` gate so tests can deterministically observe
  in-flight state before a background reasoning call resolves, rather than
  relying on how the event loop happens to schedule an un-gated fake's
  return (this is not a hypothetical concern — it is exactly what broke
  three existing tests during this pass; see §7).
- Every pre-existing `create_app(...)` call site across the integration
  suite now passes a `reasoning_port` (a held-forever fake where a test
  asserts pre-completion state, a plain fake elsewhere) — without this, any
  test exercising `send_message`/WebSocket turn recording would silently
  spin up a real, unserved 10-second Event-Bus RPC wait in the background
  on every run.

Every required scenario from the task's own test list is covered:
successful flow, reasoning failure, timeout/degraded, intent-gate
rejection, malformed/missing response, delivery failure (no live channel),
and correlation-id threading (asserted directly via
`FakeReasoningPort.reason_calls` capturing `(objective_text, user_id,
correlation_id)`, and via the real-bus test capturing the actual
`ReasoningRequestPayload`).

## 5. Verification results

| Check | Result |
|---|---|
| `ruff check` (whole monorepo, `turbo run lint`) | 18/18 packages pass |
| `mypy` (whole monorepo, `turbo run lint`) | 18/18 packages pass, 0 errors |
| Full pytest suite (whole monorepo, `turbo run test`, excludes `real_infra`) | 18/18 packages pass |
| communication-engine domain/ coverage | 99% (gate: 85%) |
| import-linter | 6/6 contracts kept |
| `docker compose config` (`infra/docker/docker-compose.local.yml`) | valid — unchanged, no new service required (everything added this pass is intra-process) |
| TypeScript contract generation | re-run, **zero diff** — no `nova-contracts` payload was added or changed |

## 6. Classification (per the closure document's own four-way standard — never collapsed)

- **Fully verified, real end-to-end**: the loop from an inbound HTTP/WebSocket
  turn through a *real* `ReasoningClient` → real Event-Bus request/reply →
  intent-gate delivery is proven by
  `test_a_real_turn_over_http_reaches_a_real_reasoning_rpc_round_trip` and
  `test_send_message_over_http_schedules_a_background_turn_that_reaches_delivery`
  — real running app, real bus mechanics, real contract serialization. This
  is the one part of Phase 2D-C's conversation stack that is now
  end-to-end-verified **without depending on any hardware or external
  client**, because both ends of the loop are already-running, in-repo
  engines with nothing external in between — exactly the asymmetry the
  closure document's §14 called out in advance.
- **Contract/fake verified**: every failure-mode branch (timeout, non-decided
  outcome, malformed reply, personality rejection, no live channel) — real
  code path, fake reasoning-engine response.
- **Real-infrastructure verified**: not applicable — no new migration, no
  new database interaction this pass (§8 below).
- **Not verified / not claimed**: against a real, deployed
  `reasoning-engine` process over a real network — this sandbox has no
  second running service to test against; the real-bus test's "server side"
  is a stand-in client on the same in-memory bus, not a second OS process.
  This is disclosed, not hidden — see §8.

## 7. A judgment call surfaced, not hidden

Per instruction #16, one implementation-level decision is worth naming
explicitly even though it did not rise to a "genuine architectural fork"
in this reviewer's judgment: **whether `deliver_content_to_session` should
be reached via an actual second Event-Bus RPC hop (communication-engine
calling its own served `communication.intent.deliver.request`) or via a
direct in-process function call.** This review chose the latter (§3) for
the reasons given there. If the user intended the former literally, that is
a small, mechanical change (swap the direct call for
`event_publisher.request("communication.intent.deliver.request", ...)`,
after adding that subject to this engine's own `PUBLISHABLE_SUBJECTS`) —
flagged here for confirmation rather than assumed.

A second thing surfaced during implementation, not anticipated by the
closure document: **three pre-existing tests
(`test_api_sessions.py::test_full_session_lifecycle_through_the_http_api`,
`test_pause_and_resume_through_the_http_api`, and
`test_websocket_text.py::test_websocket_text_frame_is_recorded_as_an_inbound_turn`)
asserted a session stays in `thinking` immediately after a turn is
recorded.** That assumption was true only because nothing previously acted
on a recorded turn. With Priority 3 built, it is genuinely racy (the
background reasoning call can complete before the test's next assertion,
moving the session to `waiting`) — not a bug in the new code, a direct,
disclosed consequence of closing the gap those tests were themselves
implicitly relying on staying open. Fixed by gating those specific tests'
`FakeReasoningPort` on an unset `asyncio.Event`, deterministically holding
the background task before it can progress — not by weakening the
assertions.

## 8. Remaining limitations — explicitly not closed by this pass

- **Priorities 1, 2, 4, 5, 6 of the closure document remain exactly as
  disclosed there.** In particular: perception-engine's sensor→fusion→
  publish chain is still unwired (Priority 1); the `user_id`/session
  correlation gap on `perception.addressee_signal.candidate` is unresolved
  (Priority 2); no cross-context "start listening" mechanism exists
  (Priority 4); `personality-engine`'s `channel` parameter is still inert
  (Priority 5); real-Postgres verification (task #93) is still unexecuted
  anywhere (Priority 6).
- **No real `reasoning-engine` process was exercised.** Every test in this
  pass runs against either `FakeReasoningPort` or a stand-in bus client
  within the same test process — genuine multi-process/multi-container
  verification (e.g., via `docker-compose.local.yml` with both engines
  actually running) has not been performed and is not claimed.
- **Response-shaping integration into the reasoning request was not
  built** (§1) — `personality.style.select`'s output is not yet threaded
  into what reasoning-engine generates. `resolve_response_shaping()` (built
  in Phase 2D-C) remains uncalled from this new path.
- **The fallback utterance's exact copy** (`FALLBACK_CONTENT`) is a
  placeholder honest string, not reviewed against Doc 23's voice
  guidelines in detail — a content/copy question, not an architectural one,
  but disclosed rather than assumed correct.
- **`ConversationDecisionTrace` is not written for a reasoning-driven
  turn.** Addressee-fusion decisions get a trace (Phase 2D-C); a
  reasoning-triggered response delivery does not yet get an equivalent
  explainability record. Not required by this pass's instructions, but a
  real observability gap worth naming.

Phase 2D-D has not been started. Priorities 1, 2, 4, 5, and 6 have not been
touched. Per instruction, this review stops here and awaits the user's
review before any further Priority 1-6 work begins.
