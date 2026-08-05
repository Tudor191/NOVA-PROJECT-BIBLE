"""Goal-driven mode (docs/design/phase-2b/00-reasoning-engine.md §6, table
row 5).

When used: any request where Current Goals materially change which
alternative wins -- makes Goal Evaluation (§8) the dominant scoring factor
rather than one input among several. Required inputs: objective plus Current
Goals, required, not optional -- this mode has no meaningful behavior without
them. Expected outputs: a decision whose explanation foregrounds goal
alignment specifically. Engine interaction: Goals (§7.1) is the primary port.
Cost: same as the underlying Analytical/Strategic mode it wraps. Confidence:
includes a distinct `goal_alignment_confidence` sub-score. Explainability:
must state which goal(s) drove the outcome.
"""

from __future__ import annotations

from nova_reasoning_engine.domain.models import ModeConfig, ReasoningMode

CONFIG = ModeConfig(
    mode=ReasoningMode.GOAL_DRIVEN,
    minimum_hypotheses=3,
    require_goals=True,
    goal_weight_boost=True,
)
