"""Reactive mode (docs/design/phase-2b/00-reasoning-engine.md §6, table row 1).

When used: Level 1 requests -- simple factual questions, basic calculations,
low-stakes lookups. Required inputs: objective text only. Expected outputs: a
direct answer, no alternatives generated. Engine interaction: at most one
`KnowledgePort`/`WorldModelPort` lookup. Cost: very low, sub-second target
(§21). Confidence: high by default unless the lookup itself fails.
Explainability: trivial -- answered directly from a named source.
"""

from __future__ import annotations

from nova_reasoning_engine.domain.models import ModeConfig, ReasoningMode

CONFIG = ModeConfig(
    mode=ReasoningMode.REACTIVE,
    minimum_hypotheses=1,
    skip_hypothesis_generation=True,
)
