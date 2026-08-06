# ADR-027 — Executive Cognition coordinates cognitive subsystems, never owns intelligence

**Subsystem(s):** Executive Cognition Engine (Phase 2C) — binding on its design doc and every subsequent implementation decision
**Status:** Accepted — permanent architectural principle, established ahead of Phase 2C design work

## Context

Phase 2B shipped the Reasoning Engine as NOVA's cognitive bridge (ADR-026): it consumes
six upstream sources and transforms them into decisions, owning nothing but the record
of its own reasoning processes. The user has now approved Phase 2B's close and
authorized Phase 2C — Executive Cognition (Bible Part 19) — with an explicit
instruction, stated ahead of any design work beginning: Executive Cognition "must not
become another Reasoning Engine. It must not become another Memory Engine. It must not
become another Knowledge Engine. It must not become another Planning Engine." Its
responsibility is "coordinating the cognitive systems of NOVA and deciding which
subsystem should perform the next cognitive step," not thinking, storing knowledge, or
executing actions itself.

This is the same category of pre-implementation boundary decision ADR-017 made for
World Model Engine and ADR-026 made for Reasoning Engine, applied now to the one
subsystem in NOVA's architecture whose entire job is to sit *above* every other
cognitive engine and decide what happens next — the highest-leverage place in the whole
system for a boundary mistake to compound, since every other engine's design so far has
assumed Executive Cognition will eventually arbitrate between them (`06 §5`'s
Cognitive Priority Matrix reference, `12 §7`'s Kernel Scheduler resource-allocation
signal, `12 §14`'s Chief Executive boundary on what reaches Communication Engine) without
this ADR yet existing to say precisely what that arbitration is and is not allowed to
do.

## Problem

Three failure modes are live risks for an Executive Cognition Engine built without this
principle stated up front, corresponding to the three ways "coordination" can silently
turn into "ownership":

1. **Re-litigating what other engines already decided.** An Executive Cognition Engine
   that re-evaluates Reasoning Engine's conclusions, second-guesses Knowledge Engine's
   confidence scores, or re-derives a plan Planning Engine already produced would
   duplicate cognitive work NOVA already paid for elsewhere, and would make Executive
   Cognition "another Reasoning Engine" one layer up — precisely the failure this ADR
   exists to rule out.
2. **Absorbing storage responsibility from the engines it coordinates.** Without an
   explicit boundary, Executive Cognition could accumulate its own copy of goal state
   (duplicating a future Planning Engine), its own copy of reasoning traces (duplicating
   Reasoning Engine), or its own copy of "what NOVA is currently aware of" (duplicating
   the *separate*, not-yet-built Cognitive State Engine, Bible Part 6, Phase 4) — the
   same bounded-context violation [Doc 20 §6](../20-engine-responsibility-boundaries.md#6-the-decision-procedure-for-future-subsystems)
   item 4 already warns against for any future engine.
3. **Collapsing into Cognitive State Engine.** Bible Part 6 (Cognitive State Engine) and
   Bible Part 19 (Executive Cognition Engine) describe closely related, textually
   overlapping concerns — both discuss attention, priority, and active goals — and this
   project's own prior documents have at times referred to them with the shorthand
   "Cognitive State Engine / Executive Cognition" (Phase 2B's design doc, its
   boundary section). Without a stated distinction, a future reader could reasonably
   build one service instead of two, contradicting the canonical service table
   ([00-overview-and-decisions.md](../00-overview-and-decisions.md)) and the roadmap's
   own phase assignment (`cognitive-state-engine` in Phase 4; `executive-cognition-engine`
   starting in Phase 2C, extended in Phase 6).

## Alternatives considered

- **A thin priority-queue shim with no real domain model** — just enough to pick between
  two contending resource requests, deferring every other Part 19 responsibility to
  Phase 6 without naming them now. Rejected: the roadmap's own Phase 2C→Phase 6
  relationship is explicit that Phase 6 *extends* Phase 2C's service, not rewrites it
  — a shim with no domain model to extend would force a redesign at Phase 6, exactly
  the outcome the 10x Test exists to prevent.
- **Executive Cognition re-reasons about which action is correct**, using its own
  judgment rather than deferring to the engine whose job that judgment is. Rejected
  outright by the user's explicit instruction: "Its purpose is not to think. Its
  purpose is to coordinate thinking." Executive Cognition may score, rank, and
  sequence *requests* from other engines; it may never produce a competing conclusion
  to one of them.
- **Executive Cognition owns a working copy of goal/priority/attention state**,
  duplicated from whichever engine originates it (Planning Engine's goals, a future
  Cognitive State Engine's attention layers), for fast local access during arbitration.
  Rejected for the same reason ADR-026 rejected an equivalent option for Reasoning
  Engine: this violates the one-writer-per-store principle every engine in NOVA follows,
  and duplicated state drifts from its source of truth the moment either copy updates
  independently.
- **Merge Executive Cognition and Cognitive State Engine into one service now**,
  resolving the two Bible parts' textual overlap by building one engine instead of two.
  Rejected: this would silently rewrite the canonical service table and the roadmap's
  own phase sequencing (Cognitive State Engine is a Phase 4 deliverable, built only
  after Perception and Autonomy exist to feed it; Executive Cognition starts now, in
  Phase 2C, coordinating just two engines) without the user having asked for that
  restructuring. The boundary between them is drawn explicitly below instead (Decision
  §4), so the overlap is resolved by definition, not by merger.
- **Executive Cognition Engine coordinates by direct function call or shared-process
  invocation of the engines it arbitrates**, rather than through the Event Bus.
  Rejected: identical reasoning to every prior engine boundary in this project —
  ADR-004 makes the Event Bus the only legal cross-engine channel, and Executive
  Cognition gets no special exemption for being "above" the engines it coordinates.
- **Executive Cognition Engine as a coordination layer that owns only its own executive
  decision records, exactly as Reasoning Engine owns only its own reasoning-process
  records under ADR-026.** Accepted — the decision below, listed here to make explicit
  that it was the seriously-considered and adopted answer, not merely the absence of
  the four rejected alternatives above.

## Decision

1. **Executive Cognition Engine's domain layer decides *which* cognitive subsystem
   should act, *when*, in *what order*, and *under what constraints* — it never
   performs the cognitive work of any subsystem it coordinates.** Concretely: it may
   score and sequence a request Reasoning Engine or the AI Model Orchestration Engine
   makes for cognitive resources; it may never generate a hypothesis, evaluate
   evidence, or produce a decision content-wise — that is Reasoning Engine's job even
   when Executive Cognition is the one that decided *whether and when* Reasoning
   Engine gets to run.
2. **Executive Cognition Engine owns no system of record for any subsystem's own
   domain.** Not Reasoning Engine's traces, not a future Planning Engine's goals, not a
   future Cognitive State Engine's attention state, not Memory's experiences or
   Knowledge's facts. Its own persistent state, if any, is limited to a structured
   record of its own executive decisions — an **Executive Decision Trace**, the direct
   analog of `ReasoningTrace` under ADR-026's own narrow "records of its own processes,
   never a copy of another engine's owned data" exception, applied here to arbitration
   decisions instead of reasoning processes.
3. **Phase 2C ships a real, minimal slice of this boundary, not a placeholder.**
   Consistent with the roadmap's existing Phase 2C scope: arbitrating exactly two
   contending engines (`ai-model-orchestration-engine`, `reasoning-engine`) via the
   Cognitive Priority Matrix (Bible Part 6: urgency, importance, complexity, risk,
   learning value, resource cost, user impact — the full seven-factor formula, not
   `06 §5`'s five-factor shorthand). Phase 6 extends the *same* service — never a
   rewrite — to goal hierarchy, cognitive load management, delegation, meta-reasoning,
   and generalized cross-engine conflict resolution, once Planning, NAOS, Autonomy,
   Personality, and Communication exist to be coordinated.
4. **Executive Cognition Engine is architecturally distinct from Cognitive State
   Engine (Bible Part 6, Phase 4), resolving the two Bible parts' textual overlap by
   definition rather than by merger:** Cognitive State Engine owns the *descriptive*
   question — "what is NOVA currently aware of, thinking about, and attending to" as
   continuously-updated internal state, a passive record. Executive Cognition Engine
   owns the *decisional* question — "given everything currently competing for
   attention, what should happen next, in what order, under what constraints," an
   active arbitration. Until Cognitive State Engine exists (Phase 4), Executive
   Cognition Engine has no rich external "current attention" feed to consume and
   necessarily observes only the requests made directly to it by the engines it
   coordinates — the same honest, caller-supplied-until-the-real-port-exists pattern
   ADR-026 established for `GoalsPort`. Once Cognitive State Engine ships, Executive
   Cognition consumes its state as a read-only input signal, exactly as it will consume
   a future Planning Engine's goals — it never duplicates Cognitive State Engine's own
   store.
5. **The Executive Cognition Technical Design Document (produced next) must include an
   explicit "what this engine does NOT do" section**, naming Reasoning Engine, Memory
   Engine, Knowledge Engine, World Model Engine, Planning Engine, Action Engine/NAOS,
   Cognitive State Engine, and Communication Engine individually and stating what
   Executive Cognition delegates to each rather than absorbing — mirroring the AI Model
   Orchestration Engine's §0 boundary section and ADR-026's identical requirement for
   Reasoning Engine.

## Consequences

- Executive Cognition Engine's `domain/ports.py` will define a Protocol for each
  coordinated engine's arbitration-relevant surface (a request-for-resources shape, not
  that engine's full domain), the same Protocol-per-port pattern every engine built so
  far already uses, satisfied by an Event-Bus-RPC-backed adapter per ADR-004.
- Executive Cognition Engine becomes the second engine in NOVA (after Reasoning) with a
  genuine cross-engine coordination role, but a categorically different one from
  Reasoning Engine's: Reasoning Engine calls other engines to gather *context* and
  produce *its own* domain decision; Executive Cognition Engine observes other engines'
  *requests* and decides *ordering and resource allocation* among them — it never
  consumes another engine's output to produce a competing domain conclusion of its own.
- The design doc's arbitration examples must show, concretely, which engine "wins" a
  given contention scenario and why (the same Cognitive Priority Matrix scoring shown
  explicitly, not just asserted) — the same rigor every Phase 1/2A/2B design doc already
  provides for its own central algorithm.

## Tradeoffs

- Phase 2C's real scope (two engines) means the design doc necessarily describes
  interactions with several systems that do not yet exist (Planning Engine, Action
  Engine/NAOS, Cognitive State Engine, Communication Engine, a future Conversation
  Manager) as designed-for-but-deferred ports, not yet-real ones — accepted per the
  identical precedent ADR-026 already established for Reasoning Engine's `GoalsPort`.
  Naming these interactions now, even unbuilt, is what lets Phase 6 extend this engine
  rather than redesign it.
- Drawing a hard line against re-reasoning (Decision §1) means Executive Cognition
  cannot, by itself, resolve a case where two engines' *outputs* genuinely conflict on
  the merits (e.g., Reasoning Engine and a future Planning Engine disagreeing about
  which approach is better) — Part 19's own text names this exact scenario
  ("Planning recommends one solution. Knowledge suggests another.") and resolves it via
  evidence, confidence, policy, and historical outcomes, never by Executive Cognition
  substituting its own judgment for either engine's. Accepted: this is the same
  "coordinate thinking, don't do thinking" boundary applied to its hardest case, not an
  exception to it.

## Future implications

- When Cognitive State Engine (Phase 4) ships, Executive Cognition Engine's "current
  attention state" input moves from self-observed/absent to a real RPC-backed port,
  without changing Executive Cognition's own boundary — the same "future extension
  point, not a redesign" precedent ADR-020 established for future model providers and
  ADR-026 established for `GoalsPort`.
- When Planning Engine, Action Engine/NAOS, Personality Engine, and Communication
  Engine (Phases 3-4/2D) exist, Executive Cognition Engine's Cognitive Priority Matrix
  extends from two contending engines to every engine that can request cognitive
  resources, and its arbitration role extends to deciding what reaches the user via
  Communication Engine (per `12 §14`'s already-established Chief Executive boundary) —
  both are Phase 6 extensions of the same service Phase 2C stands up, per the roadmap.
- Every future ADR or design decision for Executive Cognition Engine that considers
  absorbing a storage, re-reasoning, or execution responsibility must cite this ADR
  and the boundary test in Decision §1-2 before proceeding.
- The forthcoming Executive Cognition Engine Technical Design Document is the first
  artifact this ADR is binding on — it should be evaluated against this ADR the same
  way the Reasoning Engine design doc was evaluated against ADR-026 before
  implementation began.
