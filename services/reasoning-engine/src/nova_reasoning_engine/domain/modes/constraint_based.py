"""Constraint-based mode (docs/design/phase-2b/00-reasoning-engine.md §6,
table row 6).

When used: any request with hard limits that must never be violated (budget,
privacy tier, time, resource availability) -- makes Constraint Evaluation
(§9) a hard gate before scoring even begins. Required inputs: objective plus
an explicit constraint set. Expected outputs: a decision only from the
constraint-satisfying subset of alternatives, or an explicit "no feasible
alternative" result -- never a constraint-violating decision, no override.
Engine interaction: constraint sources vary. Cost: same as underlying mode
plus up-front filtering cost. Confidence: capped, not just weighted, when the
constraint-satisfying pool is small. Explainability: must name every
constraint that ruled out a rejected alternative.
"""

from __future__ import annotations

from nova_reasoning_engine.domain.models import ModeConfig, ReasoningMode

CONFIG = ModeConfig(
    mode=ReasoningMode.CONSTRAINT_BASED,
    minimum_hypotheses=3,
)
