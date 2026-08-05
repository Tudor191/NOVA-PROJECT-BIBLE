# ADR-026 — The Reasoning Engine is a cognitive bridge, never an isolated subsystem

**Subsystem(s):** Reasoning Engine (Phase 2B) — binding on its design doc and every subsequent implementation decision
**Status:** Accepted — permanent architectural principle, established ahead of Phase 2B design work

## Context

Phase 2A shipped the AI Model Orchestration Engine as a deliberately *isolated*, stateless
gateway (ADR-020, ADR-022): it knows nothing about memory, knowledge, world state, or
goals, and that isolation is exactly what makes it a clean, swappable intelligence
provider. The user has now stated, ahead of Reasoning Engine (Phase 2B) design work
beginning, that this isolation pattern must **not** repeat for the Reasoning Engine.
Reasoning should never exist in isolation. Every significant reasoning process should be
able to reference Long-Term Memory, Knowledge Engine, World Model, Personal Context,
Current Goals, and Available Capabilities. The Reasoning Engine should act as the
cognitive bridge between all of these systems rather than becoming another isolated
subsystem. Its responsibility is not storing information; its responsibility is
transforming information into decisions.

This is the same category of pre-implementation boundary decision ADR-017 made for World
Model Engine ("must not become another Memory Engine or Knowledge Engine") before that
engine was built — stated now, before Reasoning Engine's design doc is written, so the
design doc is produced *against* this constraint rather than needing correction after
the fact.

## Problem

Two failure modes are both live risks for a Reasoning Engine built without this
principle stated up front:

1. **Closed-box shallowness.** A Reasoning Engine built as a thin "prompt in, answer out"
   wrapper around the AI Model Orchestration Engine would be technically functional but
   cognitively shallow — unable to ground its reasoning in the user's actual history,
   validated knowledge, current situation, or goals. This directly fails ADR-025's
   Priority 1 (Personal Intelligence: NOVA continuously learns how the user thinks,
   works, and makes decisions) — a reasoning system that can't reference what NOVA
   already knows about its user isn't personally intelligent, it's a generic chat
   completion with extra steps.
2. **Boundary collapse the other direction.** Without an explicit "what this engine does
   NOT do" constraint, Reasoning Engine could instead absorb storage/retrieval
   responsibility that belongs to Memory, Knowledge, or World Model Engine — becoming
   "another Memory Engine," precisely the failure ADR-017 already named and ruled out
   for World Model, now recurring one layer up the cognitive stack.

## Alternatives considered

- **Reasoning Engine as a stateless pure function over `(prompt, context) -> answer`,
  with all context-gathering left to callers.** Rejected: this pushes the actual
  cognitive-integration work — "how do I gather memory + knowledge + world-model +
  goals context for this reasoning process" — onto every future caller (Executive
  Cognition, Planning, any agent that needs reasoning), duplicating it everywhere
  instead of centralizing it once in the engine Bible Part 8 explicitly names as NOVA's
  "thinking system."
- **Reasoning Engine owns its own cache/copy of memory, knowledge, and world-model data
  for fast local access.** Rejected: this violates the same bounded-context principle
  ADR-017 established (each engine owns exactly one bounded context; cross-engine reads
  happen through ports/RPC, never a private duplicate store) and ADR-022's precedent
  that intelligence-layer engines stay thin over systems of record rather than
  replicating them.
- **Reasoning Engine calls Memory/Knowledge/World Model/Planning/Capability Engine
  directly through the Event Bus's request/reply pattern (ADR-004/ADR-006), receiving
  read-only references, never owning the underlying data.** Accepted — this is the
  decision below, listed here to make explicit that it was the seriously-considered and
  adopted answer, not merely the absence of the two rejected alternatives.

## Decision

1. **Reasoning Engine's domain layer must accept, as first-class inputs to any
   significant reasoning process, references to six sources**: Long-Term Memory (via
   Memory Engine's retrieve RPC), Knowledge Engine (via its retrieve/traverse RPCs),
   World Model (via `world_model.context.request`), Personal Context (situational/
   preference context, sourced from World Model's Active Context and/or a future
   dedicated Personal Context concept), Current Goals (Planning Engine once it exists in
   Phase 3, an explicit caller-supplied parameter until then), and Available
   Capabilities (Capability Engine / Function Registry — what NOVA can actually do,
   relevant to whether a reasoning conclusion is actionable).
2. **Reasoning Engine owns none of these six systems of record.** It is a consumer and
   orchestrator of them, exactly as it is itself a pure consumer of the AI Model
   Orchestration Engine for any model call (ADR-020). Its own persistent state, if any,
   is limited to artifacts of its own reasoning processes (the reasoning-pipeline trace,
   confidence scores, the record of what reasoning happened and why) — never a duplicate
   of another engine's owned data.
3. **"Not storing information, transforming information into decisions" is the literal
   boundary test for every future Reasoning Engine domain module.** If a proposed
   capability's job is to remember something for later, it belongs in Memory Engine; if
   its job is representing validated facts, Knowledge Engine; if its job is current
   state, World Model; if its job is producing a decision, conclusion, or plan from those
   inputs, it belongs in Reasoning Engine.
4. **The Reasoning Engine design doc (produced next, per the user's explicit instruction
   to validate architecture before implementation, as in Phase 1) must include an
   explicit "what this engine does NOT do" section**, naming Memory, Knowledge, World
   Model, Planning, and Capability Engine individually and stating what Reasoning Engine
   delegates to each rather than absorbing — mirroring the AI Model Orchestration Engine
   design doc's §0 boundary section and ADR-017's World Model boundary precedent.

## Consequences

- Reasoning Engine's `domain/ports.py` will define a Protocol for each of the six input
  sources (or a documented subset, formalized incrementally as upstream engines become
  available), each satisfied by an Event-Bus-RPC-backed adapter — the same
  Protocol-per-port pattern every engine built so far already uses.
- The Reasoning Engine design doc's data-flow diagrams must show, for its central
  reasoning pipeline, exactly which upstream RPC each step calls and why — the same
  rigor every Phase 1/2A design doc already provides for its own pipeline.
- Reasoning Engine becomes the most cross-connected engine in NOVA to date (calling out
  to potentially five or six other engines per reasoning process, versus the AI Model
  Orchestration Engine's zero and World Model's near-zero). This is deliberate, not
  scope creep — Bible Part 8 names this engine "the thinking system," and a thinking
  system that cannot reference what NOVA already knows is not one.

## Tradeoffs

- Higher cross-engine call volume and more failure modes to handle gracefully (a
  reasoning process degraded because Knowledge Engine timed out, say) than any engine
  built so far. Accepted: World Model Engine's own `degraded: bool` reply-payload
  pattern (ADR from Phase 1) is the precedent for handling this per source — a
  reasoning process should degrade gracefully per missing input, not fail outright,
  the same discipline already proven at Phase 1's tightest latency budget.
- More design-time complexity up front (six input Protocols instead of one or two) than
  a narrower "just call a model" Reasoning Engine would need. Accepted per ADR-025:
  personal-depth capability wins over simpler-but-shallower design, and this is exactly
  the kind of tradeoff that ADR exists to resolve.

## Future implications

- When Planning Engine (Phase 3) and Capability Engine exist, Reasoning Engine's
  "Current Goals"/"Available Capabilities" inputs move from placeholder or
  caller-supplied parameters to real RPC-backed ports, without changing Reasoning
  Engine's own boundary — the same "future extension point, not a redesign" precedent
  ADR-020 established for future model providers.
- Every future ADR or design decision for Reasoning Engine that considers absorbing a
  storage, retrieval, or fact-validation responsibility must cite this ADR and the
  boundary test in Decision §3 before proceeding.
- The forthcoming Reasoning Engine Technical Design Document is the first artifact this
  ADR is binding on — it should be evaluated against this ADR the same way Phase 1's
  design docs were evaluated against ADR-017 before implementation began.
