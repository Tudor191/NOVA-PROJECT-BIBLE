"""Environment Prediction -- docs/design/phase-1/03-world-model-engine.md §7,
driven by `workers/prediction_worker.py`. Phase 1 implements a structural
heuristic (recurring state-transition patterns), not a learned model -- the
Reasoning Engine (Phase 2+) that could route this through a real inference call
doesn't exist yet, the same constraint ADR-009's context section states for
embeddings and Knowledge Engine's `summarization.py` documents for its own
scope. This keeps the call site and contract correct now; swapping in a
model-backed implementation later is a body-swap, not a redesign.
"""

from __future__ import annotations

from collections import Counter
from uuid import UUID, uuid4

from nova_world_model_engine.domain.models import ObjectStateHistoryEntry, Prediction

MIN_OCCURRENCES = 3
"""A transition must have recurred at least this many times in the observed
history before it's confident enough to predict -- an arbitrary but
conservative floor, not derived from data (none exists yet)."""

BASE_CONFIDENCE = 0.3
CONFIDENCE_PER_OCCURRENCE = 0.1
MAX_CONFIDENCE = 0.8
"""Phase 1 heuristics never claim high certainty -- capped well below 1.0."""


def predict_from_history(
    history: list[ObjectStateHistoryEntry], *, user_id: UUID
) -> list[Prediction]:
    """Finds `(object_label, previous_state, new_state)` transitions that
    recurred at least `MIN_OCCURRENCES` times and predicts they'll recur again
    -- confidence grows with occurrence count, capped at `MAX_CONFIDENCE`."""
    counts: Counter[tuple[str, str | None, str]] = Counter(
        (e.object_label, e.previous_state.value if e.previous_state else None, e.new_state.value)
        for e in history
    )
    predictions: list[Prediction] = []
    for (label, previous, new), count in counts.items():
        if count < MIN_OCCURRENCES:
            continue
        confidence = min(BASE_CONFIDENCE + CONFIDENCE_PER_OCCURRENCE * count, MAX_CONFIDENCE)
        predictions.append(
            Prediction(
                id=uuid4(),
                user_id=user_id,
                prediction=f"{label} will transition {previous or 'unknown'} -> {new} again",
                confidence=confidence,
            )
        )
    return predictions
