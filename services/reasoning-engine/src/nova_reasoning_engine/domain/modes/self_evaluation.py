"""Self-evaluation mode (docs/design/phase-2b/00-reasoning-engine.md §6,
table row 9).

When used: runs Part 8's "Self Questioning" as a first-class step rather than
an implicit consideration -- used when a caller explicitly requests a
critique of a prior or draft decision, or when confidence from another mode
lands in the "verify" band (§10). Required inputs: a `Decision` (draft or
already-recorded). Expected outputs: a structured critique -- gaps found,
assumptions surfaced, confidence adjustment. Engine interaction: whichever
ports the critique needs to check gaps against (commonly Memory/Knowledge).
Cost: low, a bounded, focused pass, not a full re-run of the original
pipeline. Confidence: produces a `self_evaluation_confidence` distinct from
the original decision's confidence. Explainability: every gap and assumption
found is individually listed in the trace and explanation.

`ModeConfig.engage_self_evaluation` is also set by `confidence.py`'s
medium-confidence band (§10) to trigger this mode automatically as a
verification pass, independent of an explicit caller request.
"""

from __future__ import annotations

from nova_reasoning_engine.domain.models import ModeConfig, ReasoningMode

CONFIG = ModeConfig(
    mode=ReasoningMode.SELF_EVALUATION,
    minimum_hypotheses=1,
    engage_self_evaluation=True,
)
