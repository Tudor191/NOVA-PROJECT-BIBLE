# Phase 2C Technical Design — Executive Cognition Engine

Implements [Bible Part 19](../../bible/part-19-executive-cognition-engine.md),
cross-referencing Part 6 (Cognitive State Engine — a *separate* future service this
design draws an explicit boundary against, §0.4 of the design doc), Part 2 ("AI Core
& Cognitive Architecture," the narrative introduction ADR-002 already resolved into
four concrete services), and `06 §5` ("Executive Cognition Engine — coordination
layer," the summary this document supersedes with full detail).

Status: **Approved. Implementation authorized.** The user approved this document,
then established two further permanent principles before authorizing
implementation to begin — [ADR-028](../../architecture/adr/ADR-028-executive-cognition-defers-to-specialized-engine-authority.md)
(epistemic deference to specialized engines) and
[ADR-029](../../architecture/adr/ADR-029-executive-cognition-optimizes-long-term-user-objectives.md)
(long-term-objective optimization as a Personal Edition default) — both now
incorporated into `00-executive-cognition-engine.md` (§0.5, §6.1, §7, §8, §10, §12,
§24) rather than left as unincorporated prose. This phase followed Phase 2B's exact
precedent through design review: the user designated Executive Cognition one of the
most architecturally consequential engines in NOVA — the one every other AI-layer
engine's own design has already assumed will eventually exist above it (`06 §5`'s
Cognitive Priority Matrix reference, `12 §7`'s Kernel Scheduler resource-allocation
signal, `12 §14`'s Chief Executive boundary) — and validated the architecture in
full, including these two amendments, before any implementation code was written.

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

The two amendments, both permanent and both binding on implementation from the
start: per ADR-028, this engine must always assume specialized engines know their
own domain better than it does — it is policy-driven, not intelligence-driven, and
conflict resolution may only compare signals a specialized engine has already
published, never form its own judgment about which conclusion is correct. Per
ADR-029, arbitration optimizes for the user's long-term objectives, not only the
current request — the Personal Edition's arbitration always prefers, among
otherwise-valid options, whichever best serves the user's long-term goals and
established preferences, operationalizing ADR-025's Priority 1 (Personal
Intelligence) as a concrete scoring mechanism for the first time in this project.
