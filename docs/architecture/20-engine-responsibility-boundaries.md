# 20 — Engine Responsibility Boundaries: Memory, Knowledge, World Model

**Status:** Canonical. Written on completion of Phase 1 (the first three engines built),
per explicit user directive: *"generate the same Architecture Review Report together
with a comparison explaining exactly how the responsibilities of Memory, Knowledge
and World Model differ, including data ownership, lifecycle, APIs and interaction
boundaries. That document will become the canonical reference for every future
subsystem."*

This document is not a retrospective. It is the reference every future engine's
design doc should be checked against before writing a single line of code, whenever
the question "where does this data/responsibility belong?" comes up. Sections 1-5
answer that question for the three engines that exist today; §6 turns the answer into
a reusable decision procedure for engines that don't exist yet.

## 0. The one-sentence version

**Memory** is what NOVA has experienced. **Knowledge** is what NOVA has concluded is
true. **World Model** is what is true right now. Experience accumulates and fades;
conclusions get corroborated or contradicted and mature; the present state simply
*is*, until it changes.

If a future engine's design doc cannot place a piece of data into exactly one of
these three sentences, that data does not belong in any of these three engines.

## 1. Identity

| | Memory Engine | Knowledge Engine | World Model Engine |
|---|---|---|---|
| Bible source | Part 3 | Part 10 | Part 5 + Part 18 (merged, ADR-002) |
| One-line identity | Historical experience — what happened, when, how it felt | Validated facts and relationships — what is true, and why we believe it | Current state of reality — what is true *right now* |
| Time orientation | Past (a timeline that grows) | Atemporal (a fact stays true until contradicted) | Present (a snapshot that changes) |
| Central question it answers | "What has NOVA seen/done/decided before?" | "What does NOVA know, and how confident is it?" | "What is happening right now, and what does the user care about right now?" |
| Central question it does **not** answer | "Is this true?" (Memory records that an event was *experienced*, not that its content was *validated*) | "What just happened?" (Knowledge has no concept of "now") | "Why did this become true?" or "What happened before this?" (World Model keeps a short audit trail via `object_state_history`, but that trail exists to explain the *current* state, not to be a queryable narrative — that is Memory's job) |

## 2. Data ownership

Ownership is exclusive: exactly one engine may write to each store. Every other
engine, including each other, only reads through a published API or event —
never a direct table/label/key access. This is ADR-004 (Event Bus is the only legal
cross-engine channel) applied concretely to storage.

| Store | Memory Engine | Knowledge Engine | World Model Engine |
|---|---|---|---|
| Postgres schema | `memory` (`memory_record` unified table, discriminated by `memory_type`) | `knowledge` (`node`, `edge`, `contradiction_log`, `node_version_history`) | `world_model` (`object_state_history`, `snapshot`, `prediction`, `conflict_log`) |
| Postgres role | Durable record for every memory tier + saga outbox | Durable record for graph node/edge metadata + saga outbox | Durable, always-consistent record of "what is the object's state right now," independent of whether the Neo4j write has landed yet + saga outbox |
| Neo4j labels | *(none — Memory Engine owns no graph)* | `:Project`, `:Person`, `:Concept`, `:Decision`, ... (the validated Knowledge Graph) | `:WorldProject`, `:File`, `:Window`, `:Application`, `:Agent`, `:Task`, `:Device`, `:SystemResource` — **deliberately distinct labels from Knowledge's**, linked only by a shared UUID convention, never by a cross-label traversal (preserves ADR-007's per-engine graph replaceability) |
| Redis keyspace | `mem:*` — Working Memory is a *primary* store here, not a cache | *(none in Phase 1)* | `world:context:*`, `world:attention:*`, `world:attention_ts:*`, `world:presence:*` — Active Context and Attention are *primary* stores, not a cache (same pattern as Memory Engine's Working Memory, reused — see ADR-012) |
| Vector collection | `memory_records` (pgvector, `nomic-embed-text`, 768-dim, per ADR-010) | `knowledge_nodes` (pgvector, same model) | *(none — World Model does not embed, by design; see ADR-017)* |

No engine ever queries another engine's Postgres schema, Neo4j label set, or Redis
keyspace directly. Cross-engine reads happen exclusively through published APIs
(§4) or request/reply events (§5).

## 3. Lifecycle

Each engine's lifecycle model is shaped by what kind of thing it manages — and this
is the single most common place a future engine gets the boundary wrong, by copying
a lifecycle pattern that doesn't fit what it actually owns.

| | Memory Engine | Knowledge Engine | World Model Engine |
|---|---|---|---|
| Lifecycle shape | Linear decay with a terminal state: `active → dormant → archived → scheduled_for_deletion → deleted` | Monotonic maturation, never decay: `raw → processed → verified → connected → applied → expert → strategic` | State machine over the *object's real-world condition*, not over the record's age: `UNKNOWN → ACTIVE → {IDLE, EXECUTING, LEARNING}`, `EXECUTING → {COMPLETED, FAILED, WAITING}` |
| What drives a transition | Time since last access, importance score, explicit triggers (user delete, low confidence, duplicate merge) | Corroboration, usage signals (`reasoning.result`), explicit connection to other nodes | A new observation (perception event, action result) — the world changed, so the record of it must change |
| Can a record be deleted? | Yes — the entire point of the lifecycle is eventual deletion (with a grace period, never immediate) | No — "nothing important should disappear permanently" (Part 10) is a hard constraint; duplicates are flagged, never merged or deleted | Yes, but this means something different: a World Object is *removed from current reality* (`delete_node`, e.g. a closed window), which is not "forgotten" the way a memory is — the historical fact that it existed remains in `object_state_history` forever, exactly because that table is not the record World Model treats as "current" |
| Does importance/confidence decay over time? | Yes — `domain/importance.py`'s explicit decay formula is the mechanism that drives the whole lifecycle | No periodic decay — confidence only updates at acquisition/corroboration time | N/A — Attention decays (§4's `attention.py`), but Attention is not a lifecycle; the *object's* state does not decay with time, only with new observations or (for `ACTIVE → IDLE`) elapsed time without one |

The shared shape to notice: Memory's lifecycle answers "should this experience still
be kept around?" Knowledge's lifecycle answers "how much have we corroborated this
fact?" World Model's lifecycle answers "what is this object doing right now?" These
are three different questions, and a future engine that needs a fourth kind of
lifecycle should derive its own from its own central question — not borrow one of
these three by analogy.

## 4. APIs

| | Memory Engine | Knowledge Engine | World Model Engine |
|---|---|---|---|
| Primary write path | `POST /v1/memories` (mostly system-internal — most writes come from event subscribers) | `POST /v1/knowledge/nodes` (create-or-corroborate) | *(no public write endpoint — objects are written exclusively via `perception.*.observed` / `action.result` event handlers; the world is observed, not manually declared)* |
| Primary read path | `GET /v1/memories/search` (semantic + timeline, fans out and merges) | `GET /v1/knowledge/search` (semantic + graph + name-based, fans out and merges) | `GET /v1/world/context` (Active Context, the highest-QPS Phase 1 read path — p95 < 20ms target) |
| Point lookup | `GET /v1/memories/{id}` | `GET /v1/knowledge/nodes/{id}` | `GET /v1/world/objects/{id}` (reads Postgres `object_state_history` only — see ADR-018 for why this never touches Neo4j) |
| Graph/subgraph query | *(none — Memory Engine owns no graph)* | `GET /v1/knowledge/graph?scope=project:<id>` | `GET /v1/world/graph?scope=project:<id>` |
| Synchronous RPC served | `memory.retrieve.request` | `knowledge.retrieve.request`, `knowledge.traverse.request`, `knowledge.link.request` | `world_model.context.request` (tightest latency budget of the three: p95 < 20ms, called on every Thinking Pipeline execution) |
| Synchronous RPC initiated | `knowledge.link.request` / `knowledge.traverse.request` (into Knowledge Engine, degrades to `None`/`[]` on timeout) | *(none in Phase 1 — Knowledge Engine only serves)* | *(none in Phase 1 — World Model only serves)* |

Notice the asymmetry: Memory Engine is the only *caller* of a cross-engine RPC among
the three. This is deliberate — Memory Engine's relationship data is delegated
entirely to Knowledge Engine (Bible Part 3/Part 10's overlapping "relationship"
language is resolved this way; see the Phase 1 design package's review checklist).
Knowledge Engine and World Model Engine each stay self-contained callees.

## 5. Interaction boundaries

```mermaid
flowchart LR
    Perception["Perception Engine\n(minimal voice+camera slice shipped\nPhase 2D-B; full sensing Phase 4)"] -.perception.*.observed.-> Memory
    Perception -.perception.*.observed.-> WorldModel
    Action["Action / Agent OS\n(later phases)"] -.action.result.-> Memory
    Action -.action.result.-> WorldModel
    Memory["Memory Engine"] -.knowledge.link.request\nknowledge.traverse.request.-> Knowledge["Knowledge Engine"]
    Memory -."memory.long_term.created".-> Knowledge
    Thinking["Reasoning Engine\n(shipped Phase 2B)"] -.world_model.context.request.-> WorldModel["World Model Engine"]
    Thinking -.memory.retrieve.request.-> Memory
    Thinking -.knowledge.retrieve.request\nknowledge.traverse.request.-> Knowledge
```

Updated (Project Health Review, August 2026): this diagram was accurate when this
document was written in Phase 1, when neither Perception nor Reasoning existed
yet. Both have since shipped (Reasoning Engine in Phase 2B, a minimal
voice+camera slice of Perception Engine in Phase 2D-B); this document's own
title still scopes it to Memory/Knowledge/World Model specifically, so the rest
of its analysis is unaffected, but the diagram's labels are corrected here
rather than left describing a "future" that has partly already arrived.

- **Memory → Knowledge:** the only direct engine-to-engine RPC relationship among
  the three, and even this is only ever event-bus-mediated request/reply (ADR-004) —
  never a direct import or HTTP call. Memory asks Knowledge "what do you know about
  this," Knowledge never asks Memory anything.
- **Knowledge ↔ World Model:** **no interaction boundary exists.** This is
  intentional, not an oversight — see §17's uniqueness constraint in the
  design docs. `:Project` (Knowledge) and `:WorldProject` (World Model) share a UUID
  by convention only; no code path in either engine ever traverses from one label set
  into the other. A future Reasoning Engine correlating "what NOVA knows about this
  project" with "what NOVA currently sees in this project" does that correlation
  itself, at the UUID, from outside both engines — neither engine grows a dependency
  on the other to make that correlation possible.
- **Both Memory and World Model publish object/record-changed events; only Knowledge
  Engine publishes a dedicated relationship-created event** (`knowledge.edge.created`).
  World Model has no equivalent — relationships between world objects ride as
  additional graph-write operations on the same outbox row as the object upsert that
  implies them, never as a standalone fabricated event. This is a direct consequence
  of §13's event table in the World Model design doc genuinely having no such event;
  inventing one to mirror Knowledge Engine would have been exactly the kind of
  speculative addition the user's standing instruction rules out.
- **Every one of the three engines is a pure event producer/consumer or RPC
  server/client — never a direct caller of another engine's internal module**, per
  ADR-004. The import-linter contract in the root `pyproject.toml` enforces this at
  CI time for all three (`nova_memory_engine`, `nova_knowledge_engine`,
  `nova_world_model_engine` may not import each other).

## 6. The decision procedure for future subsystems

When a future engine's design raises "does this belong in Memory, Knowledge, World
Model, or somewhere new," apply these questions in order:

1. **Is it a record of something that happened, kept for its own sake as a
   retrievable past experience?** → Memory. (Test: would deleting it after enough
   time/low enough importance be *correct* behavior, not just acceptable? If yes,
   it's Memory-shaped.)
2. **Is it a claim that could be true or false, that gets more or less trustworthy
   as it's corroborated or contradicted, and that should never be silently
   deleted?** → Knowledge. (Test: does "we used to believe X, now we don't" need to
   remain visible as an auditable contradiction rather than just vanishing? If yes,
   it's Knowledge-shaped.)
3. **Is it a fact about the state of something *right now*, that becomes wrong the
   moment reality changes, with no independent value once superseded?** → World
   Model. (Test: is there ever a reason to query "what was this five minutes ago" for
   its own sake, as opposed to just "what is it now"? If the answer is no beyond a
   short operational audit trail, it's World Model-shaped. If the answer is yes — the
   history itself has standalone value — that need is Memory-shaped, not World
   Model-shaped, even if the same object is also tracked in World Model.)
4. **If it satisfies more than one of the above**, it does not mean one engine
   should own all of it. It means the data has facets, and each engine should own its
   own facet, linked by a stable identifier (the UUID-convention pattern used between
   Knowledge's `:Project` and World Model's `:WorldProject`) — never merged into one
   engine's schema for convenience. Reaching for "just put it in one place" is the
   exact failure mode this document exists to prevent.
5. **If it satisfies none of the above**, it is not a Memory/Knowledge/World Model
   concern at all, and belongs in whichever future engine's own central question it
   actually answers (Reasoning, Planning, Perception, etc.) — do not force-fit it
   into one of these three just because they exist today.

When genuinely uncertain even after applying this procedure, the standing
instruction from the user is explicit: **choose the architecture that preserves the
three-way separation, even if it requires additional complexity.** Extra complexity
that keeps the boundary clean is always the correct trade against simplicity that
blurs it.
