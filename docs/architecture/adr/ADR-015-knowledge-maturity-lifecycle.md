# ADR-015 — Seven-stage knowledge-maturity lifecycle over a single confidence score

**Subsystem:** Knowledge Engine
**Status:** Accepted, implemented

## Context

Bible Part 10 describes knowledge as something that matures through use — a fact
NOVA learns starts "raw" and becomes progressively more trustworthy and more
embedded in NOVA's reasoning as it gets corroborated, connected to other
knowledge, and actually applied. This is explicitly framed as different from a
single trust number that goes up and down.

## Problem

Should knowledge maturity be represented as a single scalar confidence score
(the same shape Memory Engine uses for importance), or as a discrete staged
progression?

## Alternatives considered

- **A single decaying confidence score (0.0-1.0), mirroring Memory Engine's
  importance score.** Rejected: confidence and maturity are different axes. A
  fact can be highly confident (corroborated by many sources) but never yet
  "applied" in a real decision — Part 10's maturity concept specifically tracks
  *how embedded* a piece of knowledge is in NOVA's actual behavior, not just how
  likely it is to be true. Collapsing both into one number loses the ability to
  answer "which knowledge has NOVA actually used" separately from "which
  knowledge does NOVA trust."
- **Confidence score plus a separate boolean "is this connected to the graph"
  flag**, as a lighter-weight two-axis model. Rejected: this captures only two of
  the meaningfully distinct stages Part 10 describes (raw/processed and
  connected), losing the applied/expert/strategic distinctions that matter for
  a future Reasoning Engine deciding how much weight to give a piece of
  knowledge in a high-stakes decision.

## Decision

`domain/evolution.py` implements a seven-stage state machine: `raw → processed →
verified → connected → applied → expert → strategic`. Each node carries both a
`layer` (this stage) and its own `confidence` score — the two are tracked
independently. Advancement through the stages is driven by real signals:
corroboration events, graph connections (relationship discovery), and usage
signals from `reasoning.process.completed` events. Knowledge never regresses to an earlier
stage — advancement is monotonic, unlike Memory Engine's importance score, which
can both rise and decay.

## Consequences

- A future Reasoning Engine can query "how embedded is this knowledge" (`layer`)
  independently of "how much do we trust it" (`confidence`) — two different
  questions that this model keeps answerable separately.
- `knowledge_engine_layer_advances_total` (labeled by `to_layer`) gives direct
  operational visibility into how knowledge is actually maturing in practice,
  which a single scalar score could not expose as meaningfully.
- The lifecycle has no terminal deletion state, unlike Memory Engine's — this is
  intentional and directly connects to ADR-016 (knowledge is never silently lost).

## Tradeoffs

- Seven stages is more implementation surface than a single score — more state
  to test, more transition logic to get right (`tests/unit/test_evolution.py`).
  Accepted because the extra surface directly answers a real question (Part 10's
  "how embedded is this") that a scalar cannot answer.
- Monotonic-only advancement means there is currently no mechanism for a node to
  regress if it turns out to have been over-corroborated or the usage signal was
  misleading. Acceptable for Phase 1 because no such regression trigger is
  specified in the design doc; would need a real signal (not a guess) before
  adding one.

## Future implications

If a future phase discovers a real need for maturity to *regress* (e.g., a
previously "applied" fact turns out to be systematically wrong), that regression
mechanism should be driven by the same category of real signal that drives
advancement (a corroborated contradiction via ADR-016's contradiction log, not an
ad hoc decay timer) — keeping the lifecycle's "advancement means something
actually happened" property intact rather than reintroducing time-based decay by
the back door.
