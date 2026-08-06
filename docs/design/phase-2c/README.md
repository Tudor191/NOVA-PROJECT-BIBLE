# Phase 2C Technical Design — Executive Cognition Engine

Implements [Bible Part 19](../../bible/part-19-executive-cognition-engine.md),
cross-referencing Part 6 (Cognitive State Engine — a *separate* future service this
design draws an explicit boundary against, §0.4 of the design doc), Part 2 ("AI Core
& Cognitive Architecture," the narrative introduction ADR-002 already resolved into
four concrete services), and `06 §5` ("Executive Cognition Engine — coordination
layer," the summary this document supersedes with full detail).

Status: **Pending review and approval — implementation must not begin until this
document is explicitly approved**, per direct user instruction, the same
validate-before-build discipline every prior phase has been held to. This phase
follows Phase 2B's exact precedent: the user has designated Executive Cognition one
of the most architecturally consequential engines in NOVA — the one every other
AI-layer engine's own design has already assumed will eventually exist above it
(`06 §5`'s Cognitive Priority Matrix reference, `12 §7`'s Kernel Scheduler
resource-allocation signal, `12 §14`'s Chief Executive boundary) — and wants the
architecture validated before any implementation code is written.

## Contents

| Doc | Covers |
|---|---|
| [00 — Executive Cognition Engine](00-executive-cognition-engine.md) | The complete coordination architecture: the Executive Cycle, the cognitive coordination model, the Cognitive Priority Matrix, decision arbitration, goal management, task orchestration, conflict detection and resolution, context switching, executive policies, human override, failure/recovery, explainability, observability, the twelve named system interactions, the structured Executive Decision Trace, data model, and every dimension the user's directive named |

## The one constraint every section of this design defends

Per [ADR-027](../../architecture/adr/ADR-027-executive-cognition-coordinates-never-owns-intelligence.md),
established at Phase 2B's close specifically ahead of this design work: **Executive
Cognition Engine coordinates cognitive subsystems, never owns intelligence.** It
decides which subsystem should act, when, in what order, and under what
constraints — it never performs the cognitive work of any subsystem it coordinates,
and it owns no system of record for any of them. Its purpose is not to think, but to
coordinate thinking; not to store knowledge, but to coordinate knowledge; not to
execute actions, but to coordinate actions — the user's own words, given ahead of
this design work. Wherever a design choice in `00-executive-cognition-engine.md`
looks unusual (why this engine calls no model at all, unlike every other engine
built so far; why "task orchestration" explicitly excludes agent dispatch this
phase; why four of its twelve named interactions are honestly unbacked
placeholders), it is this constraint — and Phase 2C's own deliberately minimal, but
real, two-engine scope — being defended, and the doc says so explicitly at each such
point rather than leaving the reader to guess.

The second constraint, inherited unchanged from Phase 2A/2B: per
[ADR-020](../../architecture/adr/ADR-020-sole-legal-llm-provider-channel.md), this
engine never imports an LLM/AI provider SDK and never calls one directly — unlike
Reasoning Engine, it has no occasion to generate content at all, so this boundary
holds by construction, not just by discipline.
