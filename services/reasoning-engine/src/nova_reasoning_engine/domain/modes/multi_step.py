"""Multi-step mode (docs/design/phase-2b/00-reasoning-engine.md §6, table row
7, and §11 in full).

When used: Level 3/4 requests whose first pipeline pass produces a decision
that itself depends on an unresolved sub-question. Required inputs:
objective, plus recursion depth budget. Expected outputs: a decision built
from a chain of dependent sub-decisions, each individually traced (§11,
§19). Engine interaction: same ports as the underlying mode, invoked once per
step. Cost: highest, scales with chain length, bounded by `max_depth` (§11).
Confidence: aggregate is the *minimum* across the chain, never an average.
Explainability: full chain explainable step by step, not just the final
decision.
"""

from __future__ import annotations

from nova_reasoning_engine.domain.models import ModeConfig, MultiStepConfig, ReasoningMode

CONFIG = ModeConfig(
    mode=ReasoningMode.MULTI_STEP,
    minimum_hypotheses=3,
    max_step_depth=MultiStepConfig().max_depth,
)
