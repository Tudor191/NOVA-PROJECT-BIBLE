"""Analytical mode (docs/design/phase-2b/00-reasoning-engine.md §6, table row 2).

When used: Level 2 -- programming, research, writing, document analysis,
simple debugging. Required inputs: objective plus relevant memory/knowledge/
world-model context. Expected outputs: a reasoned answer with at least one
alternative when the task has a genuine choice point. Engine interaction:
Memory, Knowledge, World Model (parallel fan-out) plus AI Model Orchestration
for the analysis itself. Cost: low-to-moderate. Confidence: full formula
(§10), all seven factors weighted normally. Explainability: full decision
explanation (§16) when alternatives existed, a direct-answer explanation
otherwise.
"""

from __future__ import annotations

from nova_reasoning_engine.domain.models import ModeConfig, ReasoningMode

CONFIG = ModeConfig(
    mode=ReasoningMode.ANALYTICAL,
    minimum_hypotheses=3,
)
