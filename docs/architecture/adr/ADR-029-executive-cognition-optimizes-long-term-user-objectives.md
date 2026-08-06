# ADR-029 — Executive Cognition arbitration optimizes for the user's long-term objectives, not only the current request

**Subsystem(s):** Executive Cognition Engine (Phase 2C) — binding on its design doc and every subsequent implementation decision; operationalizes [ADR-025](ADR-025-personal-edition-is-the-flagship.md)'s Priority 1 (Personal Intelligence) inside this engine's arbitration logic
**Status:** Accepted — permanent architectural principle, established ahead of Phase 2C implementation

## Context

The user approved the Phase 2C Technical Design Document and, before authorizing
implementation, established a second permanent principle alongside ADR-028:
"Executive Cognition should optimize for the user's long-term objectives rather than
only the current request. When multiple valid options exist, arbitration should
prefer the option that best aligns with the user's long-term goals, established
preferences and current priorities. This should become one of the defining
characteristics of NOVA as a personal intelligence system... The Personal Edition
should always optimize for its primary user's long-term success."

This is a direct, concrete operationalization of
[ADR-025](ADR-025-personal-edition-is-the-flagship.md)'s Priority 1 — Personal
Intelligence: *"Its purpose is not to answer questions; its purpose is to become
increasingly effective at helping the user accomplish real work"* — inside the one
engine whose entire job is choosing between competing options. ADR-025 established
the principle NOVA-wide; this ADR is the first place it becomes a concrete scoring
mechanism rather than a standing intention.

## Problem

Bible Part 6's seven-factor Cognitive Priority Matrix, already incorporated into the
Phase 2C design doc's §6, scores each contending request substantially on its own
merits — urgency, importance, complexity, risk, learning value, resource cost, user
impact. None of these seven factors distinguishes a request that serves a durable,
ongoing objective from a well-scored but isolated one-off. Two requests that tie on
every one of the seven factors would, under the design doc's existing §7 tie-break
order (deadline, then an arbitrary stable ID), be resolved with no regard for which
one actually serves what the user is trying to accomplish over time — a silent gap
against ADR-025's own Priority 1, discovered only because the user named it
explicitly before implementation began rather than after the fact.

## Alternatives considered

- **Leave long-term alignment implicit inside the existing `importance` factor**,
  trusting each caller to fold long-term considerations into the single number it
  already supplies. Rejected: this conflates two genuinely different signals — how
  important is this request in isolation, versus how well does it serve what the
  user cares about over time — into one caller-supplied number, and gives Executive
  Cognition no way to enforce the user's own stated priority when a caller doesn't,
  or structurally can't, account for it.
- **Defer long-term-alignment scoring entirely to Phase 6**, once a real Planning
  Engine's full goal hierarchy exists to source it from richly. Rejected: the user's
  instruction is explicit that this should apply now, using whatever goal
  information already exists. The Phase 2C design doc's §8 already defines a
  caller-supplied `goal_id` and a goal-correlation boost mechanism — sufficient
  scaffolding for a directionally-correct, honestly-scoped version of this principle
  today, not a reason to wait for Phase 3.
- **Add `long_term_alignment` as an eighth Cognitive Priority Matrix factor**,
  extending Bible Part 6's own seven per this direct, explicit user instruction —
  the same category of reasoned, recorded Bible-extension ADR-025 itself represents
  — and additionally apply it as a tie-break criterion in arbitration ahead of the
  existing arbitrary-ID fallback. Accepted — the decision below, listed here to make
  explicit that it was the seriously-considered and adopted answer, not merely the
  absence of the two rejected alternatives.

## Decision

1. **`CognitivePriorityScore` (design doc §6) gains an eighth factor,
   `long_term_alignment`** (`0.0`-`1.0`), reflecting how strongly a request's
   associated goal (if any, via `goal_id`, design doc §8) ties to a durable,
   ongoing objective rather than an isolated one-off. Sourced from the same
   goal-tier signal §8 already defines for its correlation-boost mechanism — a
   request grouped with other in-flight requests under a shared, established goal
   scores higher than an ungrouped, first-time request; this is not a new upstream
   dependency, it is a new use of data this engine already has.
2. **Arbitration's tie-break order (design doc §7) inserts `long_term_alignment`
   before the arbitrary-correlation-ID fallback**, after the existing deadline
   check: when two contending requests are otherwise tied on composite score and
   neither has a nearer deadline, the one better aligned with a long-term objective
   wins. "When multiple valid options exist" (the user's own phrasing) is read
   precisely as this tie-break scope — this ADR does not let long-term alignment
   override a request that is genuinely more urgent, important, or user-impactful
   right now; it resolves ties among otherwise-comparable options, exactly as
   requested.
3. **This is a Personal Edition default, per ADR-025's own priority order, not a
   tunable knob available today.** The Personal Edition's arbitration always
   optimizes for its primary user's long-term success. A future enterprise edition
   *may* expose the weighting between short-term request quality and long-term
   alignment as a configuration surface — the identical "commercial/enterprise may
   omit or simplify, but the Personal Edition itself must never lose capability"
   relationship ADR-025 already establishes generally, applied here to this one
   specific mechanism.
4. **This is the second concrete place ADR-025's Priority 1 becomes an actual
   mechanism inside an engine**, not merely restated prose (the first being every
   engine's single-user-by-default posture, ADR-025 Consequences). Filed as its own
   ADR because it introduces a genuinely new scoring factor and a new tie-break
   rule, not because it changes anything ADR-025 already decided.

## Consequences

- The design doc's §6 Cognitive Priority Matrix formula gains an eighth weighted
  term, `w_long_term_alignment * long_term_alignment`, `Settings`-tunable like every
  other weight in that formula.
- The design doc's §7 arbitration tie-break sequence becomes: composite score →
  deadline → `long_term_alignment` → correlation ID (deterministic, arbitrary,
  stable) — each step only reached when the prior one ties.
- The design doc's §8 goal-correlation boost mechanism becomes the concrete,
  already-specified source of `long_term_alignment`, not a parallel mechanism
  invented alongside it — one signal serving two purposes (priority-boosting an
  in-flight goal's related requests, *and* now also breaking ties in the winner's
  favor when a goal is genuinely long-lived) rather than two overlapping ones.

## Tradeoffs

- `long_term_alignment` is only as good as the goal-tier signal actually available.
  With no real Planning Engine yet (Phase 3), Phase 2C's own signal is
  caller-supplied and coarse — a flat `goal_id` grouping, not a rich Mission →
  Long-Term-Goal → Project → ... hierarchy (design doc §8's own stated scope).
  Accepted as the honest, buildable slice of this principle today, exactly as every
  other Phase 2C mechanism that depends on a not-yet-built upstream engine is
  honestly scoped (ADR-026's `GoalsPort` precedent) — extended, not redesigned, once
  Planning Engine's real hierarchy exists (design doc §5.9, §24).
- Because this factor only breaks ties, its practical effect in Phase 2C — with
  exactly two real contending engines and no rich goal hierarchy yet — will be
  small and mostly exercised by tests rather than real contention. Accepted: the
  mechanism is specified and tested at full strength now (per the user's explicit
  instruction) so it has real, immediate effect the moment Phase 3's Planning
  Engine and Phase 6's richer request volume give it more to work with, rather than
  being retrofitted later.

## Future implications

- When Planning Engine ships (Phase 3), `long_term_alignment`'s source moves from a
  caller-supplied flat tier to a real multi-level goal-hierarchy signal, without
  changing this ADR's own decision — the identical "future extension point, not a
  redesign" precedent every prior upstream-dependency ADR in this project already
  establishes.
- If a future enterprise edition is built, the weight given to `long_term_alignment`
  relative to request-local factors becomes a named, explicit configuration
  surface — it is never silently removed, and the Personal Edition's own default
  never regresses to ignore long-term alignment in order to make that future edition
  simpler to build, per ADR-025's own binding constraint.
- Every future scoring or arbitration enhancement to this engine should be checked
  against whether it serves — or silently erodes — this principle, the same way
  every future capability is already checked against ADR-027/ADR-028's coordination
  boundary.
