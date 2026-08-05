"""Long-term planning mode (docs/design/phase-2b/00-reasoning-engine.md §6,
table row 4).

When used: multi-day or multi-phase objectives that need reasoning about
sequencing and future state, without performing the actual decomposition
(that boundary belongs to Planning Engine, §7.1). Required inputs: objective
plus Current Goals plus a caller-supplied time horizon. Expected outputs: a
reasoned recommendation for *how* to approach the horizon, never a Work
Breakdown Structure itself. Engine interaction: World Model, Goals, AI Model
Orchestration for outcome prediction framing. Cost: high, Level 4 territory.
Confidence: lower default -- long horizons carry more predicted uncertainty
by construction. Explainability: full explanation, with uncertainty called
out explicitly.
"""

from __future__ import annotations

from nova_reasoning_engine.domain.models import ModeConfig, ReasoningMode

CONFIG = ModeConfig(
    mode=ReasoningMode.LONG_TERM_PLANNING,
    minimum_hypotheses=3,
    require_goals=True,
    default_confidence_penalty=0.15,
)
