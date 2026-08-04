"""World Simulation -- interface only, Phase 1 stub (docs/design/phase-1/
03-world-model-engine.md §20). Ships the real contract now so callers (Action
Engine, Phase 3+) can already code against it; the actual simulation logic
(Part 5's "what happens if this file is deleted") arrives once there's enough
World Model + Reasoning Engine maturity to make it meaningful, without changing
the interface. This file's entire job is honesty: a caller must be able to
tell "not implemented" from "confidently predicted nothing will happen," which
is why the stub returns `confidence=0.0` with an explicit reason rather than a
plausible-looking fake answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ProposedAction:
    action_type: str
    target_object_id: str | None = None
    parameters: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class PredictedOutcome:
    confidence: float
    reason: str
    predicted_state: dict[str, Any] | None = None


async def simulate(action: ProposedAction) -> PredictedOutcome:
    """Phase 1 stub. Never called from any Phase 1 write path; exists purely as
    the contract future callers build against."""
    del action  # unused -- see module docstring
    return PredictedOutcome(confidence=0.0, reason="simulation not yet implemented")
