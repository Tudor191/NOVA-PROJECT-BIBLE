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

**Disclosed, deliberate capability limit (closure doc "Finding A",
user-confirmed before this was built): identity matching
(`match_voiceprint`/`match_faceprint`) and the session-active lookup
(`SessionActivityTracker.is_active`) are never called here.** Both require
a concrete `user_id`, which is exactly the question Priority 2 (explicitly
out of scope this pass) exists to resolve. Every published signal this
module produces therefore always carries `identity_id=None`,
`identity_confidence=0.0`, `session_active=False` -- real, honest values,
never fabricated, but a structural ceiling: addressee-fusion
(`communication-engine/domain/addressee_fusion.py`) cannot reach its
`high`/`activated` tier from this module's output alone until Priority 2
lands. Wake-word and gaze detection are otherwise fully real, going through
the actual `ai-model-orchestration-engine` RPCs via the Sensor Abstraction
Layer, exactly as they already did before this module existed to call them.
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
        else:
            attention = await sensor.estimate_attention(
                window, identity_id=None, correlation_id=correlation_id
            )
            state.correlation_buffer.record_gaze(GazeDirection(attention.gaze_direction))

        wake_matched, wake_confidence, gaze_direction = state.correlation_buffer.current(
            window_seconds=state.settings.correlation_window_seconds
        )

        event = addressee_signal_candidate(
            wake_word_matched=wake_matched,
            wake_word_confidence=wake_confidence,
            identity_id=None,
            identity_confidence=0.0,
            gaze_direction=gaze_direction.value,
            session_active=False,
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
