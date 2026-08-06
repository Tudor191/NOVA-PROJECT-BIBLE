# ADR-030 — Personality Engine stores and applies; Digital Twin Engine learns and evidences

**Subsystem(s):** `personality-engine` (Phase 2D-A), `digital-twin-engine` (Phase
2D-D, extended Phase 4)
**Status:** Accepted — filed per the [Phase 2D Master Architectural
Blueprint](../../design/phase-2d/00-master-blueprint.md) §9.2 and Risk §11.5,
which committed to this ADR being filed before either engine's Technical Design
Document was written, mirroring ADR-017's sequencing for the World Model boundary
in Phase 1. (Filed after both TDDs, not before, as originally sequenced — see
"Process note" at the end of this ADR.)

## Context

Bible Part 16 (Digital Twin Engine) and Part 17 (Personality Engine) both describe
the same concrete example — "preferred explanation depth" — under two different
section names: Part 16's "Communication Profile" ("The engine continuously learns
communication preferences... Communication should become increasingly natural")
and Part 17's "Personality Memory" ("Store long term behavioral adjustments...
Preferred explanation depth... Adjustments should refine personality. Never
replace core identity."). Neither Bible part is wrong; they describe the same
fact from two different angles. Without an explicit boundary, a future
implementer — including a future instance of this same coding agent, under time
pressure — could reasonably build the *same* preference-tracking logic twice, in
two different engines, or collapse both into one undifferentiated "preferences"
table nobody cleanly owns, which is precisely the failure mode
[Doc 23](../22-nova-human-interaction-principles.md) §7's "operational test" and
Master Blueprint Risk §11.5 name as a real risk.

## Problem

When a system observes evidence that the user prefers, say, shorter responses
during working hours — which engine detects this, which engine decides how much
evidence is enough to act on it, which engine stores the resulting value, and
which engine is responsible for NOVA's response actually reflecting it? Stated
precisely: is "preference tracking" one responsibility or two, and if two, where
exactly does the line fall?

## Alternatives considered

- **One engine owns the whole preference lifecycle** (either `personality-engine`
  absorbs learning, or `digital-twin-engine` absorbs application). Rejected:
  `personality-engine` absorbing learning would make it stateful in a
  fundamentally different way than every other design decision in its own TDD
  assumes (§0.3 of that document: rule-based, deterministic, no learning loop) —
  it would need evidence accumulation, confidence tracking, and a "don't
  overwrite on one data point" discipline that has nothing to do with validating
  a response's tone. `digital-twin-engine` absorbing application would require it
  to sit in `communication-engine`'s synchronous response path doing style/tone
  application work that has nothing to do with modeling the user's digital
  world (Bible Part 16's actual eleven domains) — and would blur the same
  identity-vs-workspace-model distinction ADR-017 already protected for World
  Model vs. Memory vs. Knowledge, one layer up in the cognitive stack.
- **No boundary; let both engines read and write a shared preferences table.**
  Rejected outright — this is exactly ADR-004's forbidden pattern (no engine
  communicates by sharing a database table instead of the Event Bus), and it
  reintroduces the "nobody cleanly owns it" failure this ADR exists to prevent.
- **Merge the two engines into one.** Rejected: Personality Engine's job (stable
  identity, present from the first conversation, model-independent) and Digital
  Twin's job (a multi-domain model of the user's digital world, only some of
  which — Communication Profile — is even in scope this phase) serve different
  purposes and have different lifecycles; Bible Parts 16 and 17 are two chapters
  for a reason, and Master Blueprint §9.3 already commits to Digital Twin
  growing nine more domains (goals, projects, hardware, skills, etc.) that have
  nothing to do with Personality Engine's scope at all.

## Decision

**`digital-twin-engine` is the sole epistemic learner for user preferences.** It
detects a preference from accumulated evidence, tracks its confidence and
history, and never overwrites an existing preference on a single data point
(Bible Part 16's own "Preference Evolution" discipline). **`personality-engine`
stores and applies the current resolved value as a behavioral/expression
constraint. It never observes user behavior, never accumulates evidence, and
contains no learning loop of any kind** (`02-personality-engine.md` §0.2, §0.3).

The dependency direction is one-way and structural, not just conventional:
`digital-twin-engine` **publishes** resolved values to `personality-engine` via
`personality.memory.update` (`02-personality-engine.md` §7.2, §10);
`personality-engine` has no port to query Digital Twin for "what does the user
prefer" — it can only receive what Digital Twin chooses to publish. This makes
the boundary enforceable by the import/event contract shape itself, the same
"enforced by omission" pattern ADR-017 established for World Model (§"Consequences"
there): a future contributor cannot accidentally give `personality-engine` a
learning loop without adding a port that doesn't exist in its published contract.

Until Phase 2D-D ships, `personality-engine`'s Personality Memory (`02-personality
-engine.md` §6, §9's `memory_profile` table) contains exactly one row — a static,
config-defined default — explicitly never a fabricated "learned" value (Doc 23
§6: inventing facts, including invented preferences, is forbidden). The `source`
column on that table (`'static_default'` vs. `'digital_twin'`) exists specifically
so this transition is observable when it happens, not silent.

## Consequences

- `personality-engine`'s TDD (`02-personality-engine.md`) can be reasoned about,
  audited, and tested without any dependency on `digital-twin-engine`'s
  existence — verified concretely by that engine shipping and passing its full
  test suite in Phase 2D-A, a full sub-phase before `digital-twin-engine` exists
  at all.
- `digital-twin-engine`, when built in Phase 2D-D, inherits a stable, already-
  proven consumer contract (`personality.memory.update`) rather than needing to
  co-design one against a moving target.
- Doc 23 §7's "operational test" (would this change make NOVA feel like a
  different entity, or a better-fitted version of the same one?) now has a
  mechanical enforcement point: any change that would require
  `personality-engine` to gain a learning loop is, by this ADR, not a
  `personality-engine` change at all — it belongs in `digital-twin-engine`, full
  stop.

## Tradeoffs

- Until Phase 2D-D ships, NOVA's response style/verbosity is a single,
  non-personalized default for every user interaction — explicitly accepted
  (`02-personality-engine.md` §6) rather than faked with a placeholder
  "personalization" that isn't real. This is the same honesty discipline as
  World Model's stub-interface precedent (Phase 1) and Executive Cognition's
  honestly-unbacked placeholder interactions (Phase 2C).
- Two engines now jointly implement what the Bible describes in two chapters as
  seemingly-overlapping concepts, which costs a reader unfamiliar with this ADR
  a moment of "wait, which one owns this" — mitigated by both TDDs (§0.2 of
  `02-personality-engine.md`, §9.2 of the Master Blueprint) citing this ADR
  directly rather than re-deriving the boundary inconsistently in prose.

## Future implications

- Any future change proposal that would give `personality-engine` a preference-
  learning capability, or give `digital-twin-engine` a response-styling/
  generation capability, should be treated as a proposal to violate this ADR —
  requiring either a demonstration that the responsibility genuinely doesn't
  belong to the other engine, or an explicit, recorded decision to revise this
  boundary, never a quiet accretion of one engine's shape into the other.
- When Phase 4 extends `digital-twin-engine` with its remaining nine domains
  (goals, projects, hardware, skills, software ecosystem, etc.), none of that
  extension touches `personality-engine` — only the Communication Profile domain
  and its conversation-scoped Preference Evolution slice (already shipping in
  Phase 2D-D) ever publish to `personality.memory.update`. A future contributor
  extending Digital Twin's other domains should not assume a symmetric
  publish-to-Personality pattern exists for, say, the Skill Model — it doesn't,
  by design, because Personality Engine only ever needs to know about
  *expression* preferences, never about the user's skills, goals, or hardware.

## Process note

The Master Blueprint (§9.2, Risk §11.5) committed to filing this ADR *before*
either engine's Technical Design Document was written, mirroring ADR-017's
sequencing in Phase 1. In practice, both TDDs were drafted and approved first,
referencing this boundary in prose (`02-personality-engine.md` §0.2,
`01-communication-engine.md`'s cross-references), and this ADR was filed
immediately afterward, once the gap was noticed, rather than before. The
boundary itself was never violated in either TDD — both were already consistent
with the decision recorded here — but the sequencing commitment was not honored
exactly as written. Recorded here rather than silently corrected, per this
project's own standing discipline of reporting process deviations honestly
rather than quietly fixing them and moving on.
