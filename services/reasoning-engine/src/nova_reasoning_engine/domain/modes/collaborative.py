"""Collaborative mode (docs/design/phase-2b/00-reasoning-engine.md §6, table
row 10).

Reserved for multi-agent scenarios (Bible Part 4, NAOS, Phase 3+) where more
than one reasoning process must agree before a decision is finalized.
**Not implemented in Phase 2B** -- this mode is named and its `ModeConfig`
shape designed for now, so its eventual arrival is a configuration change,
not a redesign (§25). `pipeline.py` must reject a `reasoning_mode_hint` of
`collaborative` with a clear "not yet available" error rather than silently
falling back to a different mode or producing fake per-agent agreement data.
"""

from __future__ import annotations

from nova_reasoning_engine.domain.models import ModeConfig, ReasoningMode

CONFIG = ModeConfig(
    mode=ReasoningMode.COLLABORATIVE,
    minimum_hypotheses=1,
)
