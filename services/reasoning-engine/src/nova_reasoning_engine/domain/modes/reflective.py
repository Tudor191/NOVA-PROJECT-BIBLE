"""Reflective mode (docs/design/phase-2b/00-reasoning-engine.md §6, table row
8).

When used: invoked on a *past* `ReasoningProcess` (via its trace ID), not a
fresh objective -- re-evaluates a prior decision against new evidence or a
reported outcome. Required inputs: a `reasoning_process_id` reference plus
new evidence/outcome. Expected outputs: an updated confidence score and, if
warranted, a superseding `Decision` referencing the original. Engine
interaction: `ReasoningRepository` (read the original trace) plus whichever
ports the new evidence requires. Cost: low-to-moderate, bounded by the
original decision's own complexity. Confidence: explicitly comparative --
"revised from X to Y because...". Explainability: must reference the
original decision and state what changed.

Not dispatched by `resolve_mode_and_level` (§4) -- reached only through a
dedicated re-evaluation entry point (`api/decisions.py`, task #66), since it
operates on an existing process rather than a fresh objective.
"""

from __future__ import annotations

from nova_reasoning_engine.domain.models import ModeConfig, ReasoningMode

CONFIG = ModeConfig(
    mode=ReasoningMode.REFLECTIVE,
    minimum_hypotheses=1,
)
