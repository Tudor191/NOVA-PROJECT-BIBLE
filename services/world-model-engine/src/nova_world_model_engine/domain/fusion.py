"""Multi-modal perception fusion -- docs/design/phase-1/03-world-model-engine.md
§3, the canonical example from SAD 10 row 9. Must never fire more than one
`world_model.context.changed` per fused batch (§1's component table) -- that is
this module's entire reason to exist, as opposed to each perception subscriber
updating Active Context independently.

Signal-to-activity inference (e.g. "calendar + voice => meeting") is deliberately
*not* hardcoded here -- that mapping is a property of whatever upstream sensor
adapter translates a raw `perception.*.observed` event into a `PerceptionSignal`
(a Phase 2+ concern once Perception Engine exists, per docs/design/phase-1/
04-cross-engine-integration.md). `fuse_window` only knows how to combine signals
that already carry a `suggested_activity`, computing agreement-weighted
confidence -- the general mechanism §3 describes, not the domain-specific rule
table for one example.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from nova_world_model_engine.domain.context import update_context
from nova_world_model_engine.domain.models import ActiveContext
from nova_world_model_engine.domain.ports import ContextRepository, WorldHistoryRepository

DEFAULT_CORRELATION_WINDOW = timedelta(seconds=5)
AGREEMENT_BONUS = 0.15
MAX_CONFIDENCE = 0.99


@dataclass(frozen=True, slots=True)
class PerceptionSignal:
    source: str
    user_id: UUID
    observed_at: datetime
    suggested_activity: str
    base_confidence: float = 0.5
    device: str | None = None
    task: str | None = None
    project_id: UUID | None = None
    objective: str | None = None


@dataclass(frozen=True, slots=True)
class FusedContextUpdate:
    user_id: UUID
    activity: str
    confidence: float
    device: str | None = None
    task: str | None = None
    project_id: UUID | None = None
    objective: str | None = None


def fuse_window(signals: list[PerceptionSignal]) -> FusedContextUpdate | None:
    """Merges every signal in one correlation window into exactly one context
    update. Confidence increases with signal agreement: every additional signal
    suggesting the *same* activity adds `AGREEMENT_BONUS` on top of the
    strongest single signal's own confidence, capped at `MAX_CONFIDENCE` -- a
    property directly testable as "more agreement never lowers confidence."
    Ties in the vote are broken by earliest-observed activity for determinism.
    """
    if not signals:
        return None
    user_id = signals[0].user_id

    groups: dict[str, list[PerceptionSignal]] = {}
    for signal in signals:
        groups.setdefault(signal.suggested_activity, []).append(signal)
    winning_activity, agreeing = max(
        groups.items(), key=lambda kv: (len(kv[1]), -min(s.observed_at for s in kv[1]).timestamp())
    )

    base = max(s.base_confidence for s in agreeing)
    confidence = min(base + AGREEMENT_BONUS * (len(agreeing) - 1), MAX_CONFIDENCE)
    latest = max(agreeing, key=lambda s: s.observed_at)

    return FusedContextUpdate(
        user_id=user_id,
        activity=winning_activity,
        confidence=confidence,
        device=latest.device,
        task=latest.task,
        project_id=latest.project_id,
        objective=latest.objective,
    )


async def fuse_and_update(
    context_repo: ContextRepository,
    history_repo: WorldHistoryRepository,
    signals: list[PerceptionSignal],
    *,
    correlation_id: UUID,
) -> ActiveContext | None:
    """Fuses `signals` and, if a fused update resulted, applies it via
    `domain/context.py` -- the one call site that actually publishes
    `world_model.context.changed`, keeping the "at most one event per batch"
    guarantee in a single place."""
    fused = fuse_window(signals)
    if fused is None:
        return None
    return await update_context(
        context_repo,
        history_repo,
        user_id=fused.user_id,
        updates={
            "activity": fused.activity,
            "device": fused.device,
            "task": fused.task,
            "project_id": fused.project_id,
            "objective": fused.objective,
        },
        confidence=fused.confidence,
        correlation_id=correlation_id,
    )
