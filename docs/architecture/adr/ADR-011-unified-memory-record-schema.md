# ADR-011 — Unified `memory_record` schema over one table per memory type

**Subsystem:** Memory Engine
**Status:** Accepted, implemented

## Context

Bible Part 3 specifies eight distinct kinds of long-term memory (episodic,
semantic, procedural, preference, project, decision) plus short-term and working
tiers — each with its own emphasis (an episodic memory cares about *when* and
*how it felt*; a procedural memory cares about *steps and success rate*; a
preference cares about *strength and stability*). The Phase 1 design package's
review checklist explicitly flagged this as a decision needing sign-off before
implementation: "the unified `memory_record` schema (discriminated by
`memory_type`, extended via `type_data` JSONB) vs. one table per memory type."

## Problem

Should each memory type get its own Postgres table with its own column set, or
should all long-term memory types share one table?

## Alternatives considered

- **One table per memory type** (`episodic_memory`, `semantic_memory`,
  `procedural_memory`, ...). Rejected: every cross-type query Memory Engine needs
  — timeline retrieval across all types, lifecycle sweeps, consolidation's
  duplicate search — would require a `UNION` across eight tables instead of one
  `WHERE memory_type = ...` filter. It also means every new memory type (a real
  possibility per Part 3's own "the system continues learning new categories of
  memory") requires a new migration and a new repository class, not a new enum
  value.
- **A fully generic key-value/JSONB-only table with no typed columns at all.**
  Rejected: the fields every memory type shares (importance score, access count,
  timestamps, embedding, lifecycle state) are queried and indexed constantly
  (lifecycle sweeps, importance-ordered retrieval) — burying them in JSONB would
  mean no index can cover them without a functional/expression index per field,
  which is strictly worse than just having the columns.

## Decision

One Postgres table, `memory.memory_record`, with a `memory_type` discriminator
column and the fields common to every type (importance, lifecycle state, access
metadata, embedding, timestamps) as real typed columns. Fields specific to one or
a few memory types (procedural's step list, preference's strength score, decision's
alternatives-considered text) live in a `type_data JSONB` column. Per-type modules
(`domain/episodic.py`, `domain/semantic.py`, etc.) are thin — they validate and
shape a type's `type_data` payload before handing off to the shared
`domain/long_term.py` write path, rather than each owning independent persistence
logic.

## Consequences

- Every cross-type Memory Engine query (timeline, lifecycle sweep, consolidation's
  duplicate search, importance-ranked retrieval) is a single-table query with a
  `memory_type` filter, not a fan-out across N tables.
- Adding a ninth memory type in a future phase is a new `memory_type` enum value
  and a new thin per-type module, not a schema migration plus a new repository
  class.
- `type_data`'s shape is enforced at the Pydantic domain-model layer
  (`domain/models.py`), not at the database layer — Postgres itself does not
  validate that a `procedural` row's `type_data` actually has a step list.

## Tradeoffs

- Postgres cannot enforce type-specific `NOT NULL`/check constraints on
  `type_data` fields the way it could on real columns in a per-type table. This
  trade is acceptable as long as the Pydantic validation layer is the actual
  gatekeeper for every write path (it is — `domain/long_term.py` never persists
  an unvalidated model) and stays that way; if a future write path ever bypasses
  domain validation, this becomes a real data-integrity gap.
- `type_data` fields cannot be indexed as cheaply as real columns. Acceptable
  today because no type-specific field is currently a hot query filter; would need
  revisiting (a partial/expression index, or promoting that field to a real
  column) if one becomes one.

## Future implications

If a future memory type needs a field queried frequently enough to need its own
index, promote that field out of `type_data` into a real (nullable, since other
types won't have it) column rather than adding a JSONB expression index — keeps
the "shared columns are real columns" invariant intact rather than eroding it
type by type.
