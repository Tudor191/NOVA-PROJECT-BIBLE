# ADR-032 — Identity confidence is also an authorization signal, not only a recognition output

**Subsystem(s):** `perception-engine` (Phase 2D-B); binding on every future engine
that gates a privileged capability — Action Engine (Phase 3/NAOS), Autonomy Engine
(Phase 4), and any future automation, smart-home, financial, or security-sensitive
workflow, from this point forward
**Status:** Accepted — permanent architectural principle

## Context

At the same approval point that authorized Phase 2D-B implementation to begin —
having just approved `perception-engine`'s Technical Design Document and its
`SINGLE_SIGNAL_CONFIDENCE_CEILING` mechanism (evidence fusion enforced as a
structural constraint, not merely a policy statement) — the user extended the
identity principle explicitly and permanently, stating it in terms that apply to
every future subsystem that will ever act on identity, not just Phase 2D-B's own
recognition pipeline:

> "Identity confidence should never only determine 'who the user is.' It should
> also determine 'what the system is allowed to do.' Future capabilities such as
> automation, smart-home control, financial operations, security-sensitive
> actions, or any privileged workflow should always be gated by configurable
> identity confidence thresholds. Identity is therefore not only a recognition
> problem. It is also an authorization signal."

This follows the same pattern ADR-025, ADR-029, and ADR-031 already established:
a principle first stated at one phase's concrete approval point, then given
permanent, NOVA-wide authority because the user recognized it as a standing rule
rather than a decision local to the phase in front of it.

## Problem

`perception-engine` (Phase 2D-B) produces confidence-scored, tiered identity
observations (`IdentityObservation`, `perception.identity.observed` —
[03-perception-engine.md §4.1, §8](../../design/phase-2d/03-perception-engine.md)).
Nothing yet says what a future engine that *acts* on identity — executing an
automation, controlling a smart-home device, authorizing a financial operation, or
performing any other security-sensitive action — is required to do with that
signal. Without an explicit, standing answer, each future capability-owning engine
(Action Engine, Phase 3; Autonomy Engine, Phase 4; any later integration) would
independently decide whether, and how, to check identity confidence before acting
— inconsistent across engines, unauditable as a set, and at real risk of one future
engine silently treating "probably the user" as "the user," exactly the failure
mode Doc 22 Principle 7 already forbids for recognition but says nothing about for
*authorization*.

## Alternatives considered

- **Leave identity-authorization coupling undefined, decided ad hoc per future
  engine.** Rejected: this is the default failure mode this ADR exists to
  prevent — each future privileged-capability engine inventing its own gating
  logic independently, with no guarantee any of them actually consult identity
  confidence before acting, let alone consult it consistently.
- **Have `perception-engine` itself perform the authorization/gating.** Rejected:
  this violates Bible Part 11's "Perception must remain independent... its
  responsibility is observation, understanding belongs to the higher cognitive
  systems" — the same independence boundary
  [03-perception-engine.md §0.5](../../design/phase-2d/03-perception-engine.md)
  already holds this engine to for addressee detection. `perception-engine`
  producing a confidence-scored signal and a future engine deciding what that
  signal permits is the identical "observe vs. decide" split Master Blueprint §5
  already draws between Phase 2D-B and Phase 2D-C for addressee fusion, applied
  here to authorization instead.
- **Build a centralized "Identity Authorization Engine" now.** Rejected: no
  privileged-capability engine exists yet — Action Engine and Autonomy Engine are
  Phase 3 and Phase 4 respectively. Building a centralized authorization service
  ahead of any real consumer is speculative implementation, the same category of
  premature genericity this project's standing instructions already rule out
  elsewhere (e.g. World Model's own no-embeddings decision, ADR-017).

## Decision

1. **Identity confidence is a first-class authorization input, not merely a
   recognition output**, binding on every future engine that gates a privileged
   capability: automation, smart-home control, financial operations,
   security-sensitive actions, or any future privileged workflow.
2. **Every such future engine must expose a configurable identity-confidence
   threshold per privileged capability (or per capability class)**, never a
   single hardcoded system-wide threshold — different privileged actions warrant
   different confidence bars, the same tiered treatment Doc 23's Confidence
   Expression model already gives to reasoning conclusions, reused here for
   authorization decisions.
3. **`perception-engine` never performs the gating itself.** It remains a pure
   evidence producer (Bible Part 11's boundary, §0.5/§2.2 of its own TDD),
   publishing confidence-scored, tiered identity observations that a future
   capability-owning engine consumes as one input to its own authorization
   decision — the identical "2D-B observes, 2D-C decides" pattern Master
   Blueprint §5 already established for addressee detection, applied here to
   authorization instead of addressee judgment.
4. **This is a NOVA-wide, permanent principle**, binding on every future phase
   that introduces a privileged capability — not scoped to Phase 2D-B, Phase 3,
   or Phase 4 alone.

## Consequences

- `perception-engine`'s own TDD documents this principle as a forward-looking
  constraint on its API/event surface: every identity signal it ever exposes
  carries a confidence value and tier, never a bare boolean — already true of its
  approved design (its own §8), now given permanent authority beyond that one
  document.
- Future Action Engine (Phase 3/NAOS) and Autonomy Engine (Phase 4) design work
  must define their own configurable confidence-threshold gating logic consuming
  `perception-engine`'s identity signal (and its Phase 4 successor's richer
  signal set), rather than inventing an independent identity check or, worse,
  skipping one.
- Any future engine's Gate Review that introduces a privileged capability must
  verify compliance with this ADR explicitly, the same way API consistency
  became a standing Gate Review checkpoint category after the Phase 2D-A Gate
  Review.

## Tradeoffs

- Every future privileged-capability engine takes on its own design burden for
  threshold configuration (policy, storage, UI), rather than a single
  centralized authorization service handling it once. Accepted: matches this
  project's existing "coordination, not ownership" pattern (Executive Cognition
  does not own Reasoning's intelligence; no single engine is made to own every
  other engine's authorization policy here either), and avoids a premature,
  speculative centralized service ahead of any real requirement to shape it
  against.
- A future engine could still, despite this ADR, fail to consult identity
  confidence before acting. Accepted as a design-review responsibility — this
  ADR's enforcement is architectural (checked at each future engine's Gate
  Review), not a single runtime mechanism that guarantees compliance by
  construction the way `SINGLE_SIGNAL_CONFIDENCE_CEILING` mechanically guarantees
  evidence fusion. Runtime-mechanical enforcement remains the preferred pattern
  wherever a future engine's own design can achieve it, per the user's explicit
  preference for mechanical enforcement over documentation alone.

## Future implications

- Phase 3 (Action Engine/NAOS) and Phase 4 (Autonomy Engine) design work must
  cite this ADR explicitly when defining their own execution-gating logic, and
  their TDDs' Doc 22/23 compliance sections should map their threshold design
  back to this principle the same way every TDD maps decisions to governing
  documents.
- If a future phase's design ever finds this principle in tension with a
  different standing priority (e.g. ADR-025's priority order, or a latency
  constraint under ADR-031), that tension is escalated to the user rather than
  resolved silently, the same standing every other permanent principle in this
  project's ADR log is held to.
