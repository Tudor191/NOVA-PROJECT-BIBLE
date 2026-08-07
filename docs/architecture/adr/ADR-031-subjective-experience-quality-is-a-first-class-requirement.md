# ADR-031 — Subjective experience quality is a first-class requirement, not a tiebreaker of last resort

**Subsystem(s):** NOVA-wide — binding on every engine, every phase, from this point
forward
**Status:** Accepted — permanent architectural principle

## Context

Master Blueprint §13.2 ("Low latency is part of NOVA's personality," Phase 2D)
already established a narrow version of this idea, scoped to response latency
within Phase 2D. At the same approval point that authorized Phase 2D-A
implementation to begin, the user generalized it explicitly and permanently,
stating it in terms that apply to every future subsystem, not just Phase 2D's
communication path: *"The subjective quality of interacting with NOVA is as
important as technical correctness. Whenever multiple implementations satisfy
the requirements, prefer the one that produces the most natural, responsive,
and consistent user experience while remaining faithful to the approved
architecture."*

This follows the same pattern ADR-025 (Personal Edition as flagship) and
ADR-029 (long-term-objective optimization) already established: a principle
first observed in one phase's concrete work, then given permanent, NOVA-wide
authority once the user recognized it as a standing rule rather than a
local decision.

## Problem

Technical correctness (passes tests, satisfies the API contract, matches the
approved architecture) is necessary but not sufficient for NOVA's stated goal
of being a lifelong personal companion, not a generic assistant (ADR-025).
Two implementations of the same requirement can both be "correct" while one
produces a companion that feels sluggish, jarring, or inconsistent to actually
talk to. Without an explicit, standing rule, an implementer (including a
future instance of this same coding agent) has no standing basis to choose
between them beyond whichever is more convenient to build — and "more
convenient to build" systematically loses to "the correct one, but the
first one I thought of" the same way premature-genericity would if ADR-025
didn't exist to rule it out.

## Alternatives considered

- **Treat subjective quality as a nice-to-have, addressed only if there's time
  left after correctness.** Rejected: this is the default failure mode this
  ADR exists to prevent — it quietly deprioritizes exactly the dimension
  ADR-025 says the whole project exists to optimize (a companion the user
  actually wants to use, not merely one that is technically correct).
- **Leave it as a Phase-2D-scoped principle** (Master Blueprint §13.2 alone,
  never generalized). Rejected: the user explicitly generalized it beyond
  communication latency to correctness-preserving implementation choices of
  every kind, in every future subsystem — narrower engines (Perception,
  Digital Twin, Executive Cognition's full form, NAOS/agents) all make
  implementation choices with a perceptible effect on how NOVA feels to use,
  not only the communication-facing ones.
- **Make it override the approved architecture when the two conflict.**
  Rejected, and explicitly foreclosed by the user's own wording ("while
  remaining faithful to the approved architecture") — this is a tiebreaker
  among architecture-compliant options, never a license to deviate from an
  approved TDD in the name of a better feel. A genuinely better architecture
  discovered during implementation still goes through the existing "stop and
  discuss before changing the approved design" rule, unchanged by this ADR.

## Decision

1. **Subjective experience quality — how natural, responsive, and consistent
   an interaction feels — is a first-class requirement, evaluated at the same
   priority as technical correctness, not a secondary concern addressed only
   once correctness is satisfied.**
2. **The standing tiebreaker:** whenever an implementation choice has two or
   more options that are each individually correct and each faithful to the
   approved architecture, the option that produces the more natural,
   responsive, and consistent user experience is the required choice — the
   same standing this ADR set already gives Trust Before Intelligence
   (Doc 23 §2) among personality values, applied here to implementation
   choices generally.
3. **This never licenses an architecture deviation.** If the more
   natural-feeling option would require deviating from the approved TDD, that
   is a proposal to change the design, handled by the existing "stop and
   discuss before changing the approved design" rule — never decided
   unilaterally in the name of better feel.
4. **This is the general form of Master Blueprint §13.2.** That section's
   "low latency is part of NOVA's personality" and its lowest-latency
   tie-break rule remain in force, unchanged, as the Phase 2D-specific,
   latency-focused instance of this broader principle — this ADR does not
   replace it, it generalizes the pattern it already established.

## Consequences

- Every future TDD's "Testing strategy" and "Performance considerations"
  sections should include, where relevant, an explicit note on which
  implementation choices were made for perceived-experience reasons among
  otherwise-equivalent options — the same transparency discipline this
  project already applies to tradeoffs and technical debt, applied to this
  category of decision specifically so it doesn't read as arbitrary in
  hindsight.
- Architecture Review Reports may flag, as a legitimate finding, an
  implementation that is technically correct but demonstrably worse to
  interact with than an equally-architecture-compliant alternative — this is
  not scope creep on the reviewer's part, it is exactly what this ADR asks
  reviewers to check.

## Tradeoffs

- This can cost additional implementation effort choosing between options
  that would otherwise be treated as interchangeable — accepted, the same
  tradeoff ADR-025 already accepted in choosing personal depth over
  generic breadth: NOVA is not optimizing for the cheapest implementation
  effort, it is optimizing for the user's actual day-to-day experience of a
  lifelong companion.
- "More natural, responsive, and consistent" is a qualitative judgment, not a
  metric with a single objective test the way "passes the test suite" is —
  accepted, and mitigated the same way every other qualitative standard in
  this project is: named explicitly in the TDD/review record when it drives a
  choice, so the reasoning is inspectable even though the measure itself
  isn't purely mechanical.

## Future implications

- Any future engine whose implementation choices have a user-perceptible
  effect — response timing, visual/audio smoothness, consistency of tone or
  behavior across sessions, how gracefully a degraded-mode fallback is
  surfaced — is bound by this ADR from its first TDD onward, not only the
  communication-facing engines Phase 2D builds.
- If a future phase ever finds this principle in tension with a different
  standing rule (e.g., ADR-025's personal-depth-over-breadth priority, or a
  security/privacy constraint), that tension should be escalated to the user
  rather than resolved silently — the same standing every other permanent
  principle in this project's ADR log is held to.
