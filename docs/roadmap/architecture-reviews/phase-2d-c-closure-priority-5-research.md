# Phase 2D-C Closure — Priority 5 Research: personality-engine's inert `channel` parameter

**Status: RESEARCH/PROPOSAL ONLY. Not approved. No production code, test,
contract, ADR, or existing documentation was modified to produce this
document.** Per direct instruction, this is a research deliverable —
implementation does not begin until the forks in §5 are explicitly resolved.

**Scope of this review: Priority 5 only.** Priorities 1-4 are implemented,
closed, and not reopened here except to verify a dependency. Priority 6 is
not touched. Phase 2D-D has not started.

**Headline finding: the closure document's own §7.2 characterization of
Priority 5 as "the smallest, most isolated, lowest-risk item" is true only
for the change *inside personality-engine*. Tracing the full call chain this
session shows that `channel` becoming load-bearing there would still produce
zero observable effect on anything NOVA actually says, because the one
production code path that would carry a channel-resolved value forward
(`communication-engine`'s `resolve_response_shaping()`) is never called by
any live turn — a fact Priority 3's own, already-approved Gate Review already
disclosed but did not connect back to Priority 5. This is not a new problem
Priority 5 creates; it is a pre-existing dependency the closure document's
own §21 table named explicitly (item 4 is "Blocking? Yes — before §7's
channel-appropriate shaping has any effect," and item 5, still fully
unbuilt, is "Blocking? Yes — before §7/§8/§9 have any observable effect on
delivered content").** Full trace in §2.6; the discrepancy with the task
tracker's own history is in §3.

---

## 1. Method

Every claim below is a direct read of current code (`git grep`/`Read`,
services/personality-engine, services/communication-engine,
services/reasoning-engine) or a direct read of the cited design document —
never inference from memory or from a prior session's summary. Where a
prior document's claim could not be re-confirmed against present code, that
is stated as a discrepancy (§3), not silently repeated.

---

## 2. Current-state findings

### 2.1 Where `channel` is defined, accepted, propagated, stored, or ignored (Q1)

The parameter exists at exactly four points, all in `personality-engine`,
and is a bare `str | None` at every one — never `nova_contracts.events.
communication.ChannelType`:

1. **`domain/style_selector.py::select_style(*, situation_hint, channel,
   memory_profile)`** — accepts `channel: str | None`, **never reads it in
   the function body**. The docstring is explicit: *"`channel` is accepted
   for forward compatibility (Master Blueprint §13.6) but does not yet
   influence selection."* Confirmed by reading the full 39-line file: the
   only branch is `_SITUATION_HINT_TO_STYLE.get(situation_hint...)`;
   `channel` is a dead parameter, not merely under-weighted.
2. **`api/style.py::GET /v1/personality/style`** — accepts `channel` as an
   optional query string, passes it straight through to `select_style`.
3. **`events/handlers.py::make_style_select_handler`** — the Event-Bus RPC
   counterpart, reads `payload.channel` from
   `PersonalityStyleSelectRequestPayload`, passes it straight through.
4. **`api/identity.py::GET /v1/personality/identity/snapshot`** — calls
   `select_style(situation_hint=None, channel=None, ...)` with `channel`
   **hardcoded to `None`**, always, since this endpoint returns a cacheable
   summary not tied to any one request's channel.

`channel` is **never persisted anywhere** — no column, no Postgres table,
no in-memory state. It exists only as a function/RPC parameter, computed and
discarded on every call.

### 2.2 Every caller that supplies or omits `channel` (Q2)

- **`communication-engine`'s `domain/response_shaping.py::
  resolve_response_shaping(*, personality_port, channel: str, ...)`** — the
  only caller anywhere in this codebase that can pass a *real*, non-`None`
  channel value (`session.channel.value`, i.e. `"voice"`/`"text"` from
  `nova_contracts.events.communication.ChannelType`). Confirmed by grep:
  this is the sole call site of `PersonalityPort.select_style` in
  `communication-engine`'s `src/`.
- **`personality-engine`'s own `api/identity.py`** — calls it with
  `channel=None`, always (§2.1).
- **Every test** (`personality-engine/tests/unit/test_style_selector.py`,
  `communication-engine/tests/unit/test_response_shaping.py`) — calls it
  directly with literal strings (`"voice"`, `"text"`), never through
  `ChannelType`.
- **No HTTP client, frontend, or other engine ever calls `GET /v1/
  personality/style` or `personality.style.select.request` directly** —
  `communication-engine` is the only consumer of this RPC in the entire
  codebase, confirmed by grep across every `services/*/src` directory for
  `personality.style.select` and `/v1/personality/style`.

**The critical finding (verified by grep across the whole
`communication-engine/src`, not assumption): `resolve_response_shaping()`
and `derive_situation_hint()` are exported from `response_shaping.py` and
**called by nothing in production code** — the only caller anywhere in the
repository is `response_shaping.py`'s own unit test,
`test_response_shaping.py`.** Neither `conversation_orchestration.
handle_conversation_turn` (Priority 3) nor `domain/intent_gate.
deliver_intent` nor `events/handlers.deliver_content_to_session` calls it.
`intent_gate.deliver_intent` calls `personality_port.validate_response(...)`
only — never `select_style`. This means the one function that would ever
supply a real channel value to personality-engine is itself dead code today.

### 2.3 Existing semantic meaning in ADRs, Bible, TDDs, design docs (Q3)

- **`docs/architecture/23-nova-personality-specification.md` §2** (Doc 23),
  the canonical "constant vs. adaptive" table, lists **"Channel (voice vs.
  text) | Adaptive"** as its own row, alongside "Response length |
  Adaptive," "Technical vocabulary depth | Adaptive," and "Formality
  register | Adaptive." This is real, direct textual sanction that
  channel-based *expression* adaptation is within NOVA's own personality
  specification — not a violation of "Personality remains constant" (§2's
  own governing quote). It does **not**, however, say that channel
  specifically determines verbosity, or specify any scale/values — that
  connection is the closure document's own synthesis (§7.2), not a direct
  Doc 23 quote.
- **`docs/design/phase-2d/00-master-blueprint.md` §13.6 ("Progressive
  capability")** and **§13.7 ("Communication quality over feature count")**
  — the two principles `style_selector.py`'s own docstring cites. §13.6
  explicitly names `device_id` (present in the session schema from day one,
  populated for only one device) as the precedent for exactly this kind of
  documented-but-inert forward-compatible field. §13.7 is about *not adding
  a third channel* before the existing two are excellent — it does not
  forbid differentiating behavior *between* the two channels that already
  exist.
- **`docs/design/phase-2d/02-personality-engine.md` §5** (the Style
  Selector's own original design, Phase 2D-A) — lists the rule table as
  "keyed on caller-supplied context hints (channel, an optional
  `situation_hint`...)" in prose, even though the *actual* rule table
  (`_SITUATION_HINT_TO_STYLE`) was, from day one, keyed only on
  `situation_hint`. This is the origin of the ambiguity: the prose named
  `channel` as an intended input; the implementation never wired it in.
- **`docs/design/phase-2d/04-conversation-intelligence.md` §7 item 2**
  (Phase 2D-C's own TDD, written before the closure document existed) is
  the most direct, load-bearing source: *"Required fix inside
  personality-engine itself, disclosed here since this document's own
  design depends on it working: `select_style`'s `channel` parameter is
  currently accepted but inert... For 2D-C's channel-appropriate
  length/pacing to mean anything, personality-engine's rule table needs at
  minimum a channel-based verbosity adjustment (voice responses
  shorter/less punctuation-dense than text, by default). This is
  personality-engine's file to change, disclosed as a small, additive,
  named prerequisite exactly like §0.5/§0.6"* — §0.5/§0.6 are the World
  Model `present_identities` and `perception.*` payload-registration
  prerequisites, both of which **were** built (as Priority 1/2 closure
  work). This one was not.
- **§21's consolidated table (same document)** lists this as **item 4**:
  *"Make `channel` load-bearing in `select_style` | personality-engine |
  Small | Yes — before §7's channel-appropriate shaping has any effect."*
  **Item 5, immediately below it**: *"Consume `ResponseShapingDirective
  Payload`; honor `response_language`/verbosity/technical_depth... |
  reasoning-engine | Unverified — requires reading that engine's generation
  code first | Yes — before §7/§8/§9 have any observable effect on
  delivered content."* The original design document itself already states,
  in its own words, that item 4 alone is insufficient — item 5 is also
  required, and was explicitly flagged as unverified, requiring a read of
  reasoning-engine's own code before any implementation commitment.
- **`docs/design/phase-2d/05-conversation-intelligence-closure.md` §7**
  (the closure document, written after 2D-C, before Priorities 1-4 were
  implemented) restates the same finding and proposes **§7.2: a narrow,
  deterministic, channel-based verbosity adjustment only — never
  style/tone** — `ChannelType.VOICE` capping verbosity below `ChannelType.
  TEXT`'s ceiling, `technical_depth`/`style` unaffected. It states this
  item has "no fork." **This session's own re-verification (§2.6, §3)
  shows that framing needs revisiting**, not because the *personality-
  engine-side* design is wrong, but because a load-bearing assumption
  behind "no fork" (that the surrounding wiring would already exist) did
  not hold once Priority 3 was actually implemented.
- **No ADR governs this.** `ADR-020` ("sole legal LLM provider channel")
  and one passing mention in `ADR-027` both use "channel" to mean the
  Event-Bus/LLM-provider boundary — unrelated to voice/text communication
  channels. No ADR anywhere addresses channel-specific personality or
  response-shaping behavior.

### 2.4 Intentional vs. unfinished (Q4)

Both, at different layers — this is not a single yes/no:

- **Inside `personality-engine` itself**: the *current* inertness is
  **deliberately disclosed**, not an oversight — `style_selector.py`'s own
  docstring, `response_shaping.py`'s own docstring, the personality-engine
  README, and `test_style_selector.py`'s own test name
  (`test_channel_does_not_influence_style_selection_this_phase`) all say so
  explicitly, and consistently, across every layer.
- **At the design-intent layer**: this was always meant to be finished, not
  left permanently inert. §2.3's TDD citations (§7 item 2, §21 item 4) name
  it as a "required," "small, additive" prerequisite — the same weight
  given to two other prerequisites (§0.5, §0.6) that *were* completed. It
  is "intentionally deferred," not "intentionally permanent."
- **Whether finishing *just* item 4 (this engine) would matter today**: no
  — see §2.6. The gap is deliberately incomplete at the system level, even
  though personality-engine's own piece of it is deliberately, honestly
  disclosed.

### 2.5 Existing channel-distinguishing logic elsewhere (Q5)

- **`communication-engine`'s domain model distinguishes `ChannelType.VOICE`/
  `ChannelType.TEXT` extensively** — `ConversationSession.channel`,
  `ConversationTurn.channel`, `InboundMessage`/`OutboundMessage` routing
  through `VoiceChannelAdapter`/`TextChannelAdapter`, VAD/barge-in logic
  (voice-only), `domain/addressee_fusion.py` (explicitly "voice channel
  only — text has no addressee ambiguity"). **All of this is transport/
  session-mechanics differentiation, not personality/response-shaping
  differentiation.** No existing code varies *what NOVA says* or *how
  verbosely* by channel today.
- **`response_shaping.py::resolve_response_shaping`** is the one place a
  channel-aware *content-shaping* decision was designed to happen — and, as
  established, is dead code.
- **Nothing in `reasoning-engine`, `ai-model-orchestration-engine`, or
  `executive-cognition-engine` references channel, style, verbosity, or
  `ResponseShapingDirective` at all** — confirmed by grep across each
  engine's `src/`.

### 2.6 Whether functional `channel` would require changes outside personality-engine (Q6)

**Yes, decisively, to have any observable effect** — this is the
headline finding, traced end to end:

```
select_style(channel=...)                         [personality-engine]
  -> would need to actually vary output by channel  <- Priority 5's own scope
  -> PersonalityClient.select_style (unchanged, already correct passthrough)
  -> resolve_response_shaping(channel=session.channel.value, ...)
       [communication-engine/domain/response_shaping.py]
       -> NEVER CALLED by any production code path today (confirmed §2.2)
  -> [if it were called] ResponseShapingDirectivePayload
       -> "communication.response_shaping.directive" is a REGISTERED
          contract (nova-contracts) but is NOT in communication-engine's
          own PUBLISHABLE_SUBJECTS (events/published.py) -- publishing it
          today would be rejected by bind_event_bus's own allow-list
  -> [even if published] no engine anywhere subscribes to
     "communication.response_shaping.directive" -- confirmed by grep
  -> [the actual mechanism a real turn uses to reach delivered content]
     conversation_orchestration.handle_conversation_turn (Priority 3)
     calls reasoning.reason.request with ReasoningRequestPayload, which
     has NO style/verbosity/technical_depth/channel field of any kind
     (events/reasoning.py:99-117, re-read directly this session)
  -> reasoning-engine's domain/pipeline.py::run() generation step folds in
     nothing from personality-engine -- confirmed no reference to style/
     verbosity/technical_depth/channel anywhere in reasoning-engine's src
```

Making `channel` functional **inside personality-engine alone** would be
implementing a correct, tested, but **completely unreachable** rule — no
different, from the live system's perspective, from `channel` staying
inert, because nothing between a real user's voice/text turn and
`select_style` ever invokes it with a live value today.

**To make channel-based verbosity actually observable in a delivered NOVA
response** requires, at minimum, all of:
1. Personality-engine's own fix (Priority 5's literal scope).
2. `resolve_response_shaping()` wired into the real turn-handling path —
   Priority 3's own §5.3 step 1, which Priority 3's actual, user-approved
   implementation explicitly declined to build (§3 below).
3. An additive field on `ReasoningRequestPayload` (or equivalent) carrying
   the resolved style/verbosity/technical_depth to reasoning-engine —
   Priority 3's own §5.3 step 2/§5.4, also explicitly declined.
4. reasoning-engine's generation/prompt-construction step actually folding
   those hints in — §21 item 5, explicitly still unverified against that
   engine's real code by the original design document's own words, and
   still unverified today (this session did not read reasoning-engine's
   `domain/pipeline.py::run()` generation internals — doing so was not
   necessary to answer *this* question, only to note that it remains an
   open prerequisite).

None of 2-4 are personality-engine's own file to change (§2.3's TDD
citation is explicit that item 4/Priority 5 is "personality-engine's file
to change" — items on the list above beyond that are, respectively,
communication-engine's and reasoning-engine's).

### 2.7 Contract/versioning implications (Q7)

**No `nova-contracts` change is required for personality-engine's own fix
alone.** `PersonalityStyleSelectRequestPayload.channel: str | None` already
exists, already carries the real value when `resolve_response_shaping`
calls it, and needs no schema change — only `select_style`'s own internal
logic (currently ignoring the parameter) would change. The domain-level
Python signature (`channel: str | None`) also needs no change to keep
working end-to-end.

A **type-tightening** opportunity exists but is not required: `channel` is
`str | None` everywhere (API, RPC payload, domain function) rather than
`nova_contracts.events.communication.ChannelType | None`. Tightening it is
a `personality-engine`-internal, backward-compatible refinement (the wire
format is unaffected — `ChannelType` is a `StrEnum`, JSON-identical either
way) — not a contract version bump, and not required to implement Priority
5's own scope correctly, since a plain string comparison
(`channel == "voice"`) works today without it. Flagged as an optional
implementation-time improvement, not a fork.

If a future priority pursues §2.6 items 2-4 (wiring `resolve_response_
shaping()` into delivery and reasoning-engine consumption), *that* work
would require an additive `nova-contracts` change (new field(s) on
`ReasoningRequestPayload` or equivalent) and adding `"communication.
response_shaping.directive"` to `communication-engine`'s own
`PUBLISHABLE_SUBJECTS` — both out of Priority 5's own scope as the user has
framed it (§5, Fork A).

### 2.8 Independence from Priorities 1-4 (Q8)

**Priority 5 is mechanically independent of Priorities 1-4's own code** —
none of the four touched `personality-engine`, `response_shaping.py`,
`select_style`, or any related contract. Grep-confirmed: zero overlap in
files changed.

**It is not independent of Priority 3's own scope decision**, however —
not because Priority 3 introduced a new interaction, but because tracing
Priority 5 in isolation (as this session was asked to do) surfaces that
Priority 3's own, already-approved, already-disclosed scope reduction (not
implementing `resolve_response_shaping` wiring or the `ReasoningRequest
Payload` additive fields — Priority 3 Gate Review §1, §8, directly
verified by re-reading that document this session) is the reason Priority
5's own fix would currently be unobservable. This is **the closure
document's own dependency analysis needing a correction, not a new
dependency Priorities 1-4 created**: §7.2 said "no dependency on P1-P4...
could be done at any point," which is still true in the narrow sense that
nothing *blocks* Priority 5's own code from being written — but it is
misleading in the sense that matters to a reviewer deciding whether to
approve it, because it does not mention that Priority 3 (already
implemented, already approved, before Priority 5 was reached) determined
whether Priority 5's fix would matter. This was knowable at the time the
closure document was written (§21 item 5 already named the dependency); it
was simply not cross-referenced against §7.2's own "no fork" framing.

### 2.9 Smallest production-safe implementation, if activated (Q9)

Constrained to personality-engine's own file, per §2.6/§2.7's finding that
nothing beyond it is in Priority 5's scope as framed:

1. `select_style` gains a single, narrow, deterministic rule: when
   `channel == "voice"` (or `ChannelType.VOICE.value`, see §2.7's optional
   type-tightening), return a fixed, already-precedented "concise"
   verbosity value **instead of** `memory_profile.verbosity`, regardless of
   what the (currently always-static-default) memory profile says; for any
   other channel value (including `None`), behavior is byte-for-byte
   unchanged — `memory_profile.verbosity` passes through exactly as today.
2. `style` and `technical_depth` are **never** touched by `channel` — only
   `verbosity`, matching §7.2's own explicit boundary ("never style/tone").
3. **No ordering/scale is invented.** The closure document's own prose
   ("caps verbosity at a bound below X's ceiling") implies a graduated,
   ordered scale of verbosity levels. **No such scale exists anywhere in
   this codebase or its design documents** — `MemoryProfile.verbosity` is
   an unconstrained `str` (default `"moderate"`), and the only other value
   ever seen anywhere is `"concise"`, used as an example verbosity in
   several `personality-engine` test fixtures (`test_style_selector.py`,
   `test_api_identity.py`, `test_api_memory.py`,
   `test_repository_real_postgres.py` — grep-confirmed, all within
   `personality-engine`, none in `communication-engine`, whose own
   `test_response_shaping.py` fixture happens to use `"verbose"` instead,
   underscoring that neither value is a canonical, cross-codebase
   convention — both are arbitrary test data). Implementing a literal
   graduated "cap" would
   require inventing a taxonomy (e.g., `minimal < concise < moderate <
   detailed < comprehensive`) that no ADR, Bible section, Doc 23, or TDD
   defines — exactly the "inventing channel-specific behavior merely
   because the field exists" the user's instructions warn against. The
   override-to-a-single-precedented-value form above is the most literal,
   least-invented translation of the existing design evidence (Doc 23 §2's
   "channel is adaptive," the TDD's "voice responses shorter... by
   default") into code without fabricating a scale nothing has ever
   specified. This is itself named as Fork B (§5) rather than assumed.
4. `channel`'s type stays `str | None` (or is tightened to `ChannelType |
   None`, optional, §2.7) — no contract change either way.

### 2.10 Test plan that proves the behavior without assuming future channel semantics (Q10)

- **Unit, `personality-engine`** (extending `test_style_selector.py`):
  replace `test_channel_does_not_influence_style_selection_this_phase`
  (which currently documents the *absence* of behavior as correct) with
  tests asserting: `channel="voice"` returns the fixed concise verbosity
  regardless of `memory_profile.verbosity`; `channel="text"` returns
  `memory_profile.verbosity` unchanged; `channel=None` returns
  `memory_profile.verbosity` unchanged (the pre-existing default path,
  regression-proofed); `style`/`technical_depth` are identical across all
  three cases for the same `situation_hint` (proving the "never style/tone"
  boundary is real, not just documented).
  - Reuse the exact same `_PROFILE = MemoryProfile(verbosity="concise",
    ...)` fixture already in the file — since the fixture's own verbosity
    is already `"concise"`, a targeted second fixture with a *different*
    verbosity (e.g. the field's own default, `"moderate"`) is needed to
    prove the voice override actually overrides something, not
    coincidentally matches it.
- **Integration, `personality-engine`** (existing `tests/integration/`
  pattern, real app + lifespan): `GET /v1/personality/style?channel=voice`
  vs `channel=text` through the real HTTP route; the real
  `personality.style.select.request` RPC round trip via `nova_testkit`'s
  existing Event Bus test pattern, confirming the wire payload's `channel`
  field reaches the fix through the same path already tested for
  `situation_hint`.
- **No changes needed in `communication-engine` tests** — `response_
  shaping.py`'s own existing unit test
  (`test_resolve_response_shaping_returns_the_selected_style`) already
  passes `channel="voice"` through a `FakePersonalityPort` and asserts
  whatever `StyleSelection` the fake returns is threaded through
  unchanged; it does not, and should not, start asserting real
  personality-engine behavior, since `response_shaping.py` itself remains
  unreachable from any real turn (§2.6) — changing this test would
  misrepresent what is actually verified.
- **No `real_infra`-marked test is needed** — no schema change, no new
  database interaction (§2.7).
- **What this explicitly does *not* prove, disclosed rather than
  implied**: that a real user speaking to NOVA over voice ever receives a
  more concise response than the same content over text. That claim is
  false today and would remain false after Priority 5 alone, per §2.6 —
  the test plan above proves personality-engine's own rule is correct in
  isolation, not that it is observable end-to-end.

---

## 3. Discrepancies between prior documentation/task history and actual code

1. **This session's own task tracker lists "2D-C-5: Prerequisite —
   reasoning-engine consumes ResponseShapingDirective (§0.7)" as
   `completed`.** Direct code inspection this session (grep across
   `services/reasoning-engine/src` for `style`, `verbosity`,
   `technical_depth`, `response_language`, `ResponseShapingDirective`,
   `CommunicationStyle`, and for a subscription to `communication.turn.
   received` or `communication.response_shaping.directive`) found **zero
   matches** — reasoning-engine subscribes to nothing but its own
   `reasoning.reason.request` RPC (Phase 2B, extended by Priority 3), and
   `ReasoningRequestPayload` (the payload that RPC actually uses) has no
   style/verbosity/technical_depth/channel field. This task's completion
   marker does not match current code. Most likely explanation, stated as
   a hypothesis rather than a confirmed fact (this session did not
   investigate *why* the marker is stale, only *that* it is): Priority 3's
   later, narrower, user-approved implementation (synchronous
   `reasoning.reason.request` RPC, not the event-subscription design §0.7
   originally sketched) superseded whatever the original task believed was
   built, without the task tracker being corrected retroactively. This is
   disclosed here rather than silently left standing, per the user's own
   request to surface discrepancies.
2. **The closure document's §7.2 states this item "has no dependency on
   P1-P4" and needs no fork.** Re-verified this session: technically true
   in the narrow sense that no P1-P4 *code* blocks Priority 5's own change
   from compiling or running — but the framing omits that Priority 3's own
   (already-approved) scope reduction is *why* Priority 5's fix would be
   unobservable once built, a dependency the closure document's own §21
   table had already named (item 5) but did not cross-reference against
   §7.2's "no fork" conclusion. See §2.8, §4.
3. **No other discrepancy found.** Every other claim in `style_selector.
   py`, `response_shaping.py`, the personality-engine README, and the
   closure document's §7.1 was independently re-confirmed against current
   code and found accurate.

---

## 4. Dependencies and risks

- **Dependency**: none, to implement Priority 5's own narrow scope (§2.9) —
  confirmed no code or contract Priority 5 needs is missing or blocked.
- **Risk — false sense of progress**: implementing §2.9 without clearly
  disclosing §2.6's finding could read, in a future review, as "channel-
  aware responses are done," when no user-observable behavior changes.
  Mitigated by this document's own headline finding and by the Gate
  Review this work would produce explicitly restating it (see §6's
  recommended scope).
- **Risk — inventing an unspecified scale**: covered in §2.9/Fork B — the
  override-to-a-single-value design is deliberately chosen to avoid this;
  a graduated multi-level scale (Fork B2) would be a materially higher-risk
  invention.
- **Risk — scope creep into Priority 3/reasoning-engine territory**: real,
  and named explicitly as Fork A (§5) rather than assumed away. The
  temptation this research itself surfaces is to "just also wire
  `resolve_response_shaping()` in, since it's right there" — that is
  Priority 3's own previously-scoped-and-declined work, reopening which is
  the user's call, not this document's to make silently.
- **No risk to existing tests**: `test_channel_does_not_influence_style_
  selection_this_phase` will need to change (it currently documents the
  absence of behavior as the assertion) — already anticipated by the
  closure document itself (§7.2: "that test will need to be rewritten"),
  reconfirmed as necessary and correctly anticipated, not a surprise.

---

## 5. Explicit forks requiring approval

Per instruction, none of these has been resolved. Each recommendation is
offered, not assumed.

### Fork A — whether to implement §2.9's personality-engine-only fix now, given it would be unobservable end-to-end

- **A1 (recommended): implement personality-engine's own fix only** (§2.9),
  strictly scoped to that engine, its own tests, no other engine touched.
  Matches the user's own framing of Priority 5 ("the personality-engine
  channel parameter"); matches real, existing design evidence (Doc 23 §2,
  the TDD's own §7 item 2/§21 item 4); does not reopen Priority 3's own
  already-approved scope reduction. Explicitly disclosed limitation:
  produces no observable change to any delivered NOVA response until a
  future, separate priority completes §2.6 items 2-4.
- **A2: also wire `resolve_response_shaping()` into communication-engine's
  real turn-handling path** (Priority 3's own §5.3 step 1, previously
  declined) — makes the resolved directive reach
  `ResponseShapingDirectivePayload` and get published (requires adding
  `"communication.response_shaping.directive"` to `PUBLISHABLE_SUBJECTS`),
  observable in decision traces/audit logs, but **still does not reach
  delivered content** (§2.6 items 3-4 remain unbuilt) — reopens Priority
  3's scope for a partial, audit-only benefit.
- **A3: build the full chain** (A2 + an additive `ReasoningRequestPayload`
  field + reasoning-engine's generation step folding it in) — the only
  option that would make channel-based verbosity actually observable in a
  delivered response. Requires reading reasoning-engine's `domain/
  pipeline.py::run()` generation internals first (never done; the original
  TDD's own §21 table explicitly flags this as required before any
  implementation commitment) — a materially larger, multi-engine
  undertaking beyond "the personality-engine channel parameter" as framed.
- **A4: do nothing — leave `channel` fully inert**, revisit only once
  response-shaping wiring is itself a separately-scoped, approved future
  priority. Defensible if the user judges an unreachable-but-correct rule
  not worth building yet (Master Blueprint §13.7's own "resist by default"
  spirit, applied to *this* form of progress rather than a new channel).

### Fork B — how to translate "voice caps verbosity below text's ceiling" into code without an existing scale

- **B1 (recommended): a fixed override, not a graduated cap.** `channel ==
  "voice"` forces verbosity to the single, already-precedented value
  `"concise"` (the only non-default verbosity value that already appears
  anywhere in `personality-engine`'s own test fixtures — §2.9); every other
  channel value, including `None`, leaves `memory_profile.verbosity`
  completely untouched. No new taxonomy invented.
- **B2: a defined, ordered verbosity scale** (e.g. `minimal < concise <
  moderate < detailed < comprehensive`), formalized as a new `StrEnum`
  (mirroring `CommunicationStyle`'s own precedent), with `ChannelType.
  VOICE`'s ceiling and `ChannelType.TEXT`'s ceiling both defined, and
  `select_style` clamping `memory_profile.verbosity` against the caller's
  channel ceiling. Closer to the closure document's own literal "caps...
  ceiling" language, structurally consistent with `CommunicationStyle`'s
  existing closed-palette pattern — but invents a value set and ordering
  no ADR, Bible section, Doc 23, or TDD specifies today, and would likely
  require a `MemoryProfile.verbosity`/`ResponseShapingDirectivePayload`/
  `IdentitySnapshot` type change (currently bare `str` in all three) to be
  type-safe, which B1 does not need.
- **B3: decline to implement any verbosity behavior**, treating "no
  canonical scale exists" as itself sufficient reason to leave `channel`
  inert even if Fork A resolves toward implementing something (functionally
  converges with A4 for the verbosity question specifically, while still
  allowing Fork A's other sub-decisions, e.g. type-tightening, if the user
  wants those alone).

### Fork C — whether to also make `resolve_response_shaping()`'s dead-code status itself part of this pass

Discovered during this research, not part of the original Priority 5
framing: `resolve_response_shaping()`/`derive_situation_hint()` are fully
built, tested in isolation, and completely unreachable from production
(§2.2, §2.6). This is not a defect in the Fork-E sense (Priority 4) — it
does not crash anything, it is a previously-disclosed, deliberate Priority
3 scope decision, not a bug. Named here only because this research
surfaced it with more precision than any prior document, and the user's
standing instruction is to disclose rather than silently note-and-move-on.

- **C1 (recommended): leave it exactly as Priority 3 left it — disclosed,
  dead code, out of Priority 5's own scope.** Wiring it in is Fork A's A2/
  A3, already covered above; there is nothing additional for Fork C to
  decide beyond what Fork A already asks.
- **C2: file a standalone note/task for "wire response-shaping into
  delivery" as its own future, separately-approved priority**, distinct
  from both Priority 5 and a reopened Priority 3 — makes the remaining gap
  trackable without deciding, in this pass, whether or when to close it.

---

## 6. Recommended implementation scope, if Fork A → A1 and Fork B → B1

Strictly bounded to `services/personality-engine/`:

| File | Change |
|---|---|
| `domain/style_selector.py` | `select_style` gains the `channel == "voice"` → fixed `"concise"` verbosity override (§2.9); docstring updated to state the new, real behavior and explicitly note it is not yet reachable by any live conversation (linking to this document) |
| `tests/unit/test_style_selector.py` | Replace `test_channel_does_not_influence_style_selection_this_phase` with the four cases in §2.10 |
| `tests/integration/` (existing file, exact name TBD at implementation time from current directory contents) | `GET /v1/personality/style?channel=voice` vs `text` through the real app; real RPC round trip |
| `README.md` | Update the "known gap" section (currently states channel has no effect) to reflect the new behavior and this document's own disclosed end-to-end-unreachability finding |

**Not touched**: `nova-contracts` (§2.7 — no change proven necessary),
`communication-engine` (Fork A1 explicitly excludes it),
`reasoning-engine`, any Alembic migration, `docker-compose.local.yml`,
any other engine.

If the user instead selects A2 or A3, this scope table would need to be
redone with communication-engine's (and, for A3, reasoning-engine's) own
affected-files list — not attempted here, since that would be answering an
unresolved fork rather than presenting it.

---

## 7. Verification plan

Matching the standard applied to Priorities 1-4:

- `ruff check`, `mypy src` (personality-engine; monorepo-wide via `pnpm
  lint` to confirm no cross-engine regression, since none is expected)
- Full monorepo `pnpm test` (expect all 18 packages green — Priority 5's
  own scope touches only personality-engine, but communication-engine's
  `test_response_shaping.py` is re-run unmodified to confirm it still
  passes, proving its own assertions about the *fake*-backed path remain
  correct even though the real path stays unreachable)
- import-linter (expect 6/6 kept, unchanged — no new cross-engine
  dependency)
- personality-engine `domain/` coverage gate (85%, per ADR-033) — expect
  comfortably met, plus a genuine negative control
  (`--cov-fail-under=100`) confirming the gate still enforces, matching
  Priority 4's own precedent
- No `docker-compose` or TypeScript-codegen change expected (no contract,
  no new service) — both still re-run to confirm zero diff, not assumed
- No `real_infra` test needed or added (§2.10)

---

## 8. Explicitly out of scope, not touched, not assumed resolved

- Priorities 1-4 — unmodified, not reopened, re-confirmed independent at
  the code level (§2.8).
- Priority 6 — not referenced as an implementation target.
- Phase 2D-D — not started.
- `resolve_response_shaping()`'s production wiring, the additive
  `ReasoningRequestPayload` fields, and reasoning-engine's own generation-
  prompt integration — all confirmed still unbuilt, named explicitly as
  Fork A's A2/A3, not silently assumed either in or out of this pass.
- Any change to `reasoning-engine`, `ai-model-orchestration-engine`, or
  `executive-cognition-engine` — none proposed, none required for the
  recommended (A1/B1) scope.
