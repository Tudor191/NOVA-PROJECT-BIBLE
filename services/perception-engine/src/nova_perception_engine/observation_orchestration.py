"""Closes Priority 1 of docs/design/phase-2d/05-conversation-intelligence-closure.md
(user-approved: a real ingestion endpoint, Fork #3 Option 1) -- the missing
sensor -> detection -> fusion -> publish chain behind
`perception.addressee_signal.candidate`:

    already-captured window arrives at POST /v1/perception/observations
    -> this module (handle_observation_window)
    -> the presence-gate cost-avoidance check (already existed, unused)
    -> detect_wake_phrase / estimate_attention (already existed, unused)
    -> WindowCorrelationBuffer (new, domain/correlation_buffer.py)
    -> events.publishers.addressee_signal_candidate (already existed, unused)
    -> the transactional outbox (already existed, unused for this subject)

Lives outside `domain/` -- like `session_activity.py`'s own precedent would
suggest it could live in `domain/`, but this module needs `app.state`
(sensor registry, repository, settings), which `domain/ports.py`'s own
docstring forbids `domain/` code from importing (mirrors
`communication-engine`'s `conversation_orchestration.py`, built for exactly
the same reason during Priority 3).

**Priority 1's disclosed capability limit (closure doc "Finding A"): identity
matching and the session-active lookup were never called here** -- both
require a concrete `user_id`, which Priority 1 explicitly deferred.
**Priority 2 (docs/design/phase-2d/05-conversation-intelligence-closure.md
Sec4, user-confirmed) closes that gap**, using `Settings.primary_user_id`
(ADR-025's single-trusted-user default) as that concrete `user_id`:

    `primary_user_id` unset -> publish nothing at all (an explicit,
    logged degrade -- never a guessed identity, Sec4)
    `primary_user_id` set -> after presence-gated wake/gaze detection,
    check `has_active_consent(user_id, source)` before ever calling
    `match_voiceprint`/`match_faceprint` (Doc 22 Principle 8) -> a match
    (or its absence) feeds `WindowCorrelationBuffer.record_identity_signal`
    -> `current_identity()` fuses it with any still-fresh contribution
    from the other modality -> `SessionActivityTracker.is_active(user_id)`
    resolves `session_active` -> all three reach
    `perception.addressee_signal.candidate` for real.

Consent gates only the matching call, not `detect_wake_phrase`/
`estimate_attention` themselves or sensor `start()` -- those remain the
same pre-existing, disclosed, out-of-scope gaps Priority 2's own review
found and the user chose not to fix this pass (`domain/consent.py`'s own
docstring overstates what `start()` actually checks today). Wake-word and
gaze detection are otherwise fully real, going through the actual
`ai-model-orchestration-engine` RPCs via the Sensor Abstraction Layer,
exactly as they already did before this module existed to call them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from nova_contracts.events.perception import GazeDirection
from nova_observability import get_logger
from pydantic import BaseModel

from nova_perception_engine.domain.sensor import SensorErrorReport
from nova_perception_engine.events.publishers import addressee_signal_candidate

__all__ = ["ObservationOutcome", "handle_observation_window"]

logger = get_logger("perception-engine.observation_orchestration")


class ObservationOutcome(BaseModel):
    sensor_id: str
    presence_detected: bool
    published: bool


async def handle_observation_window(
    app: FastAPI, *, source: str, window: bytes, correlation_id: UUID | None = None
) -> ObservationOutcome | None:
    """Returns `None` when no sensor is registered for `source` (the caller
    maps this to 404 -- an unknown source is a caller error, distinct from
    every other outcome below, which are all legitimate operating states
    for a real, registered sensor)."""
    state = app.state
    sensor = state.sensors_by_source.get(source)
    if sensor is None:
        return None
    sensor_id = sensor.sensor_id
    correlation_id = correlation_id or uuid4()

    if sensor.state() != "running":
        # Paused (e.g. consent revoked mid-session) or not yet started --
        # a legitimate, expected state, not an error (Sec3.6's own "no
        # event is better than a wrong one" applies equally here: silence
        # is the correct response to a sensor that isn't live).
        return ObservationOutcome(sensor_id=sensor_id, presence_detected=False, published=False)

    user_id = state.settings.primary_user_id
    if user_id is None:
        # Priority 2's explicit degrade (design doc Sec4): never guess a
        # user identity for an unconfigured deployment -- publish nothing,
        # the same "no event is better than a wrong one" discipline the
        # non-running-sensor branch above already applies.
        logger.warning("primary_user_id_not_configured", extra={"sensor_id": sensor_id})
        return ObservationOutcome(sensor_id=sensor_id, presence_detected=False, published=False)

    try:
        if not sensor.detect_presence(window):
            # Sec7.2's cost-avoidance gate: no (comparatively expensive)
            # model call is made for a window with no detected change.
            return ObservationOutcome(sensor_id=sensor_id, presence_detected=False, published=False)

        if source == "microphone":
            # `VoiceSensor.detect_wake_phrase` collapses the underlying
            # `WakePhraseResult.confidence` to a bare bool by its own
            # existing, already-tested design -- 1.0/0.0 is the honest
            # confidence this orchestration can report given that
            # already-collapsed signal, not a fabricated precision.
            matched = await sensor.detect_wake_phrase(window, correlation_id=correlation_id)
            state.correlation_buffer.record_wake(
                matched=matched, confidence=1.0 if matched else 0.0
            )
            if await state.repository.has_active_consent(user_id=user_id, source="microphone"):
                voice_signal = await sensor.match_voiceprint(
                    window, user_id=user_id, correlation_id=correlation_id
                )
                if voice_signal is not None:
                    state.correlation_buffer.record_identity_signal(voice_signal)
        else:
            attention = await sensor.estimate_attention(
                window, identity_id=None, correlation_id=correlation_id
            )
            state.correlation_buffer.record_gaze(GazeDirection(attention.gaze_direction))
            if await state.repository.has_active_consent(user_id=user_id, source="camera"):
                face_signal = await sensor.match_faceprint(
                    window, user_id=user_id, correlation_id=correlation_id
                )
                if face_signal is not None:
                    state.correlation_buffer.record_identity_signal(face_signal)

        wake_matched, wake_confidence, gaze_direction = state.correlation_buffer.current(
            window_seconds=state.settings.correlation_window_seconds
        )
        identity_result = state.correlation_buffer.current_identity(
            window_seconds=state.settings.correlation_window_seconds
        )
        session_active = state.session_tracker.is_active(user_id=user_id)

        event = addressee_signal_candidate(
            wake_word_matched=wake_matched,
            wake_word_confidence=wake_confidence,
            identity_id=identity_result.identity_id,
            identity_confidence=identity_result.fused_confidence,
            gaze_direction=gaze_direction.value,
            session_active=session_active,
            user_id=user_id,
            correlation_id=correlation_id,
        )
        await state.repository.enqueue_outbox(event)
    except Exception:
        logger.exception("observation_window_processing_failed", extra={"sensor_id": sensor_id})
        sensor.report_error(
            SensorErrorReport(
                sensor_id=sensor_id,
                message="observation window processing failed",
                occurred_at=datetime.now(UTC).isoformat(),
            )
        )
        return ObservationOutcome(sensor_id=sensor_id, presence_detected=True, published=False)

    return ObservationOutcome(sensor_id=sensor_id, presence_detected=True, published=True)
