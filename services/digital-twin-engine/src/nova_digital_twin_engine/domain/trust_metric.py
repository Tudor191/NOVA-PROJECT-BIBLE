"""Correction-frequency trust metric (docs/design/phase-2d/
06-personal-companion.md Sec9, Fork C incorporating Fork E) --

    correction_frequency(user_id, window) =
        sum(len(session.corrections) for session in completed_sessions(user_id, within=window))
        / count(completed_sessions(user_id, within=window))

A simple, explicitly-partial trust signal: average corrections per
completed session over a rolling window. `sessions` is the caller's already
-windowed evidence (e.g. the last N completed sessions, or sessions within
the last 30 days) -- this module does not itself select the window, mirroring
`evidence_collection.py`'s own "caller assembles, this module scores"
convention from reasoning-engine.

`clarification_acceptance_rate`/`proactive_suggestion_acceptance_rate`
stay `None` here -- deferred, not fabricated (Fork C, unchanged)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from nova_digital_twin_engine.domain.models import CompletedSessionEvidence, TrustMetric

__all__ = ["compute_correction_frequency", "compute_trust_metric"]


def compute_correction_frequency(sessions: list[CompletedSessionEvidence]) -> float | None:
    """`None` (not `0.0`) with no completed sessions in the window -- "no
    data yet" is not the same claim as "measured zero corrections"."""
    if not sessions:
        return None
    return sum(len(session.corrections) for session in sessions) / len(sessions)


def compute_trust_metric(*, user_id: UUID, sessions: list[CompletedSessionEvidence]) -> TrustMetric:
    return TrustMetric(
        user_id=user_id,
        correction_frequency=compute_correction_frequency(sessions),
        window_session_count=len(sessions),
        computed_at=datetime.now(UTC),
    )
