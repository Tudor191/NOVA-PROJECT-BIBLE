"""Strategic mode (docs/design/phase-2b/00-reasoning-engine.md §6, table row 3).

When used: Level 3 -- architecture, system design, business planning,
long-term technical decisions. Required inputs: full context bundle, plus
explicit Current Goals (§8), required, not optional. Expected outputs: a
decision plus a ranked list of rejected alternatives with reasons (§15, in
full). Engine interaction: all six upstream ports; multiple
`ai_model.generate.request` calls. Cost: moderate-to-high, several-seconds
target (§21). Confidence: full formula, Goal Evaluation weighted more heavily
than Analytical. Explainability: full explanation required.
"""

from __future__ import annotations

from nova_reasoning_engine.domain.models import ModeConfig, ReasoningMode

CONFIG = ModeConfig(
    mode=ReasoningMode.STRATEGIC,
    minimum_hypotheses=3,
    require_goals=True,
)
