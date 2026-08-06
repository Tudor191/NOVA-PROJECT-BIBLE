# ADR-028 — Executive Cognition is policy-driven, not intelligence-driven: specialized engines are epistemically authoritative in their own domain

**Subsystem(s):** Executive Cognition Engine (Phase 2C) — binding on its design doc and every subsequent implementation decision, including every future extension named in that design's §24
**Status:** Accepted — permanent architectural principle, established ahead of Phase 2C implementation

## Context

The user approved the Phase 2C Technical Design Document and, before authorizing
implementation, established an additional permanent principle: Executive Cognition
"should not attempt to outperform the Reasoning Engine. It should not reinterpret
knowledge. It should not invent conclusions... Executive Cognition should always
assume that specialized engines know their own domain better than it does. Its role
is coordination. Not replacement."

[ADR-027](ADR-027-executive-cognition-coordinates-never-owns-intelligence.md)
already establishes that this engine coordinates cognitive subsystems and never
performs their cognitive work (Decision §1: "it never performs the cognitive work of
any subsystem it coordinates"), and the Phase 2C design doc's §10 conflict-resolution
procedure already states "no subsystem overrides another directly." This ADR
sharpens both into an explicit, permanent, non-overridable **epistemic deference**
principle, distinct from ADR-027's functional division of labor: ADR-027 says *what*
Executive Cognition does (coordinate, never think); this ADR says *how* it must
behave the moment it observes disagreement or ambiguity between the specialized
engines it coordinates — defer, never judge.

## Problem

Without this principle stated explicitly and permanently, a specific, realistic
drift risk exists as this engine's own capability grows toward its Phase 6 form
(Meta Reasoning, generalized conflict resolution, per the design doc's §24): it
would be natural, each time conflict resolution's five-signal procedure (design doc
§10) proves inconclusive, to add "just one more heuristic" that lets Executive
Cognition break the tie using its own read of which conclusion seems more plausible.
Each individual addition might look like reasonable "policy tuning." Accumulated,
it reintroduces exactly the re-reasoning ADR-027 already prohibits — just gradually,
and dressed up as policy rather than obviously as thinking. This ADR exists to make
that drift path structurally unavailable, not merely discouraged.

## Alternatives considered

- **Trust ADR-027's existing language as sufficient, file no new ADR.** Rejected:
  the user explicitly requested this as an *additional* principle ahead of
  implementation, and ADR-027's language, while directionally correct, does not
  state the specific behavioral default — conflict resolution may only weigh
  signals a specialized engine has *already published*, never Executive Cognition's
  own independent assessment — precisely enough to survive Phase 6's growth in
  arbitration sophistication without erosion.
- **A configurable "trust level" per coordinated engine**, letting deployment-time
  configuration decide how much weight Executive Cognition's own judgment gets
  relative to a given engine's conclusions. Rejected outright: this *is* the
  substitution-of-judgment risk the user's instruction rules out, only made
  configurable rather than removed. "Assume specialized engines know their own
  domain better than it does" is stated as an unconditional default, not a tunable
  dial with a non-zero setting available.
- **Codify epistemic deference as a hard, non-overridable structural invariant**,
  distinct from the soft, `Settings`-configurable Executive Policies the design
  doc's §12 already defines (which the user's own text, quoting Bible Part 19,
  describes as "absolute unless changed by the user" — i.e., changeable in
  principle). Accepted — the decision below, listed here to make explicit that it
  was the seriously-considered and adopted answer, not merely the absence of the two
  rejected alternatives.

## Decision

1. **Conflict resolution (design doc §10) may only weigh signals a specialized
   engine has already published** — evidence citations, confidence scores,
   historical outcomes — never an independent judgment Executive Cognition forms
   about which conclusion is substantively correct. If a future implementation adds
   a step to that procedure that requires Executive Cognition to evaluate domain
   content on the merits (e.g., "read the two conclusions and decide which reasoning
   is sounder"), that addition violates this ADR regardless of how it is described.
2. **When published signals are inconclusive, Executive Cognition defers — the
   `ESCALATED` outcome (design doc §7, §13) — never breaks the tie using its own
   assessment of domain merit.** A tie is not evidence that either side is wrong; it
   is evidence that this engine's own competence to judge stops here.
3. **This deference default applies symmetrically to every specialized engine**
   this document coordinates today (AI Model Orchestration Engine, Reasoning
   Engine) and every one it will coordinate later (Planning Engine, a future
   Knowledge-consulting capability, NAOS/Action Engine's agents) — there is no
   engine-specific exception where Executive Cognition is "allowed" to second-guess
   because that engine's domain seems simple, well-understood, or low-risk to
   override.
4. **This is a hard architectural invariant, never an Executive Policy** (design
   doc §12). The four policies enumerated there (`user_goals_override_optimization`,
   `safety_overrides_speed`, `privacy_overrides_convenience`,
   `critical_alerts_override_focus_mode`) govern *arbitration outcomes* — which
   already-scored request proceeds — and are legitimately user-configurable.
   Epistemic deference governs *what Executive Cognition is*, not a preference about
   how it operates, and is never exposed as something a policy configuration could
   turn off.

## Consequences

- The design doc's §10 conflict-resolution procedure states the deference default
  explicitly at each of its five steps (evidence, confidence, policy, user
  objectives, historical outcomes), not only as the final fallback — a reader
  working through any single step should be unable to conclude "and here Executive
  Cognition could just decide," at any point in the procedure.
- The design doc's §0 boundary section gains an explicit "assumes domain authority"
  clause, stated alongside its existing "does NOT do" list, so a reader evaluating
  any future addition to this engine has the test available in the same place the
  rest of the boundary already lives.
- Every future capability proposed for this engine that would require it to
  evaluate domain content on the merits must be rejected under this ADR unless it is
  scoped as an actual new specialized engine with its own bounded context (i.e., a
  genuine new reasoning capability, built and boundary-tested the way Reasoning
  Engine itself was under ADR-026) — never folded into Executive Cognition's own
  arbitration logic as "just a heuristic."

## Tradeoffs

- The same tradeoff ADR-027 already named, sharpened rather than changed: Executive
  Cognition alone cannot resolve a conflict where two engines' outputs genuinely
  disagree on the merits and neither has stronger published evidence/confidence/
  historical support — it escalates. This ADR removes any future temptation to
  "improve" that outcome by giving Executive Cognition its own judgment; the
  accepted cost is that some conflicts require a human decision (§13) that a more
  opinionated arbiter might have resolved automatically, in exchange for never
  letting a coordination layer quietly become an unaccountable second opinion on
  every specialized engine's own domain.

## Future implications

- Binding on Phase 6's Meta Reasoning and generalized conflict-resolution work
  (design doc §24): any proposed enhancement to conflict resolution must be checked
  against this ADR's Decision §1 before being accepted, the same way every future
  Reasoning Engine capability must be checked against ADR-026's storage-boundary
  test.
- If a future phase genuinely needs a capability that evaluates domain content on
  the merits (e.g., a real meta-reasoning engine that assesses argument quality),
  it must be designed and boundary-tested as its own specialized engine under its
  own ADR — never absorbed into Executive Cognition, per the identical "does this
  belong here, or does it belong to a bounded context that should own it" test
  [Doc 20](../20-engine-responsibility-boundaries.md) already establishes for every
  other engine in NOVA.
