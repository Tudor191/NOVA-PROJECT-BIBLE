"""`communication.session.completed` subscribed handler and
`digital_twin.preferences.get.request` served RPC handler (docs/design/
phase-2d/06-personal-companion.md Sec7.1, Sec9, Sec11.1).

`make_session_completed_handler` is this engine's one real evidence-
processing path this phase: records the session's raw evidence and a
structural habit signal (never an inferred label -- `domain/models.py`'s
own `HabitSignal` docstring), then recomputes the correction-frequency
trust metric (Fork C's real, evidence-based formula) over the configured
rolling window. It does **not** touch `CommunicationProfile` -- Fork F
(`domain/models.py`'s own module docstring) means no evidence source for
`verbosity`/`technical_depth`/`terminology_preference`/`conversation_pacing`/
`habit_timing_hint` is approved yet, so this handler never calls
`preference_evolution.evolve_field`.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI
from nova_contracts import (
    CommunicationSessionCompletedPayload,
    DigitalTwinPreferencesGetReplyPayload,
    DigitalTwinPreferencesGetRequestPayload,
    EventEnvelope,
)

from nova_digital_twin_engine.domain import trust_metric
from nova_digital_twin_engine.domain.models import (
    CommunicationProfile,
    CompletedSessionEvidence,
    HabitSignal,
    TrustMetricHistoryEntry,
)

__all__ = ["make_preferences_get_handler", "make_session_completed_handler"]


def make_session_completed_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> None:
        state = app.state
        payload = CommunicationSessionCompletedPayload.model_validate(envelope.payload)

        evidence = CompletedSessionEvidence(
            session_id=payload.session_id,
            user_id=payload.user_id,
            turn_count=payload.turn_count,
            corrections=payload.corrections,
            preferences=payload.preferences,
            feedback=payload.feedback,
            decisions=payload.decisions,
            closed_at=payload.closed_at,
        )
        await state.repository.record_completed_session_evidence(evidence)
        await state.repository.record_habit_signal(
            HabitSignal(
                user_id=payload.user_id,
                session_id=payload.session_id,
                turn_count=payload.turn_count,
                observed_at=payload.closed_at,
            )
        )

        recent_sessions = await state.repository.list_recent_completed_sessions(
            payload.user_id, limit=state.settings.trust_metric_window_size
        )
        previous_metric = await state.repository.get_trust_metric(payload.user_id)
        new_metric = trust_metric.compute_trust_metric(
            user_id=payload.user_id, sessions=recent_sessions
        )
        await state.repository.upsert_trust_metric(new_metric)

        changed = (
            previous_metric is None
            or previous_metric.correction_frequency != new_metric.correction_frequency
        )
        if changed:
            await state.repository.create_trust_metric_history_entry(
                TrustMetricHistoryEntry(
                    user_id=payload.user_id,
                    correction_frequency=new_metric.correction_frequency,
                    window_session_count=new_metric.window_session_count,
                )
            )
        state.metrics.trust_metric_recomputed_total.add(
            1, {"outcome": "changed" if changed else "unchanged"}
        )

    return handle


async def _get_or_default_profile(app: FastAPI, user_id: UUID) -> CommunicationProfile:
    profile = await app.state.repository.get_communication_profile(user_id)
    return profile if profile is not None else CommunicationProfile(user_id=user_id)


def make_preferences_get_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> DigitalTwinPreferencesGetReplyPayload:
        payload = DigitalTwinPreferencesGetRequestPayload.model_validate(envelope.payload)
        profile = await _get_or_default_profile(app, payload.user_id)

        # Fork A (Sec8): this RPC serves only digital-twin-owned fields --
        # verbosity/technical_depth/terminology_preference stay on the
        # personality.memory.update-mediated path (personality-engine's own
        # MemoryProfile), never duplicated here.
        return DigitalTwinPreferencesGetReplyPayload(
            user_id=payload.user_id,
            preferences={
                "conversation_pacing": profile.conversation_pacing,
                "habit_timing_hint": profile.habit_timing_hint,
            },
        )

    return handle
