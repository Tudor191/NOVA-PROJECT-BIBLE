"""`observation_orchestration.handle_observation_window` (docs/design/
phase-2d/05-conversation-intelligence-closure.md Sec3/Sec4, Priorities 1
and 2) -- every branch: presence-gate short-circuit, wake-only publish,
gaze-only publish, cross-sensor correlation combining a still-fresh
contribution from the other sensor, an unknown source, a sensor that isn't
`running`, a detection call that raises, an unconfigured `primary_user_id`
degrade, consent-gated identity matching (granted/withheld/no-match), and
`session_active` resolution via `SessionActivityTracker`.

Uses `FakeSensor` directly rather than `create_app`+`TestClient` (that is
`tests/integration/test_api_observations.py`'s job) -- this file isolates
the orchestration function's own branching logic with precise, deterministic
control over each failure mode, mirroring `communication-engine`'s own
`conversation_orchestration` unit-test split between direct-function and
real-app-and-bus tests during Priority 3.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from nova_contracts.events.perception import GazeDirection
from nova_perception_engine.domain.correlation_buffer import WindowCorrelationBuffer
from nova_perception_engine.domain.identity_fusion import ModalitySignal
from nova_perception_engine.domain.models import AttentionObservation, ConsentGrant
from nova_perception_engine.domain.session_activity import SessionActivityTracker
from nova_perception_engine.observation_orchestration import handle_observation_window

from tests.fakes.repository import FakePerceptionRepository
from tests.fakes.sensor import FakeSensor

_DEFAULT_PRIMARY_USER_ID = uuid4()


class _FakeApp:
    def __init__(
        self,
        *,
        sensors_by_source: dict,
        repository,
        correlation_window_seconds: float = 2.5,
        primary_user_id: UUID | None = _DEFAULT_PRIMARY_USER_ID,
        session_tracker: SessionActivityTracker | None = None,
    ):
        self.state = SimpleNamespace(
            sensors_by_source=sensors_by_source,
            repository=repository,
            correlation_buffer=WindowCorrelationBuffer(),
            settings=SimpleNamespace(
                correlation_window_seconds=correlation_window_seconds,
                primary_user_id=primary_user_id,
            ),
            session_tracker=session_tracker or SessionActivityTracker(),
        )


async def test_unknown_source_returns_none() -> None:
    app = _FakeApp(sensors_by_source={}, repository=FakePerceptionRepository())
    outcome = await handle_observation_window(app, source="microphone", window=b"audio")
    assert outcome is None


async def test_sensor_not_running_is_a_no_op_not_an_error() -> None:
    sensor = FakeSensor(state="paused")
    app = _FakeApp(sensors_by_source={"microphone": sensor}, repository=FakePerceptionRepository())
    outcome = await handle_observation_window(app, source="microphone", window=b"audio")
    assert outcome is not None
    assert outcome.presence_detected is False
    assert outcome.published is False
    assert sensor.presence_calls == []  # never even reached the presence gate


async def test_presence_gate_short_circuits_and_publishes_nothing() -> None:
    sensor = FakeSensor(presence=False)
    repository = FakePerceptionRepository()
    app = _FakeApp(sensors_by_source={"microphone": sensor}, repository=repository)
    outcome = await handle_observation_window(app, source="microphone", window=b"\x00" * 10)
    assert outcome is not None
    assert outcome.presence_detected is False
    assert outcome.published is False
    assert repository.outbox == {}


async def test_a_wake_only_window_publishes_addressee_signal_candidate() -> None:
    sensor = FakeSensor(wake_matched=True)
    repository = FakePerceptionRepository()
    app = _FakeApp(sensors_by_source={"microphone": sensor}, repository=repository)
    outcome = await handle_observation_window(
        app, source="microphone", window=b"loud audio", correlation_id=uuid4()
    )
    assert outcome is not None
    assert outcome.published is True

    row = next(iter(repository.outbox.values()))
    assert row.subject == "perception.addressee_signal.candidate"
    assert row.payload["wake_word_matched"] is True
    assert row.payload["wake_word_confidence"] == 1.0
    assert row.payload["gaze_direction"] == "unknown"  # no camera contribution yet
    assert row.payload["identity_id"] is None
    assert row.payload["identity_confidence"] == 0.0
    assert row.payload["session_active"] is False


async def test_a_gaze_only_window_publishes_addressee_signal_candidate() -> None:
    sensor = FakeSensor(
        attention=AttentionObservation(
            identity_id=None,
            attention_state="engaged",
            gaze_direction="toward_device",
            confidence=0.9,
        )
    )
    repository = FakePerceptionRepository()
    app = _FakeApp(sensors_by_source={"camera": sensor}, repository=repository)
    outcome = await handle_observation_window(app, source="camera", window=b"face crop bytes")
    assert outcome is not None
    assert outcome.published is True

    row = next(iter(repository.outbox.values()))
    assert row.payload["gaze_direction"] == "toward_device"
    assert row.payload["wake_word_matched"] is False  # no microphone contribution yet


async def test_a_fresh_contribution_from_the_other_sensor_is_combined() -> None:
    """The core reason `WindowCorrelationBuffer` exists: two separate,
    single-sensor ingestion calls, both within the correlation window,
    combine into the same-shaped signal a true synchronized capture would
    have produced in one call."""
    voice_sensor = FakeSensor(wake_matched=True)
    camera_sensor = FakeSensor(
        attention=AttentionObservation(
            identity_id=None,
            attention_state="engaged",
            gaze_direction="toward_device",
            confidence=0.9,
        )
    )
    repository = FakePerceptionRepository()
    app = _FakeApp(
        sensors_by_source={"microphone": voice_sensor, "camera": camera_sensor},
        repository=repository,
    )

    await handle_observation_window(app, source="microphone", window=b"audio")
    await handle_observation_window(app, source="camera", window=b"frame")

    assert len(repository.outbox) == 2
    latest = list(repository.outbox.values())[-1]
    assert latest.payload["wake_word_matched"] is True
    assert latest.payload["gaze_direction"] == "toward_device"


async def test_an_expired_contribution_from_the_other_sensor_is_not_combined() -> None:
    from datetime import UTC, datetime, timedelta

    voice_sensor = FakeSensor(wake_matched=True)
    repository = FakePerceptionRepository()
    app = _FakeApp(sensors_by_source={"microphone": voice_sensor}, repository=repository)
    stale_gaze_time = datetime.now(UTC) - timedelta(seconds=10)
    app.state.correlation_buffer.record_gaze(GazeDirection.TOWARD_DEVICE, now=stale_gaze_time)

    outcome = await handle_observation_window(app, source="microphone", window=b"audio")
    assert outcome is not None
    row = next(iter(repository.outbox.values()))
    assert row.payload["gaze_direction"] == "unknown"  # too old (correlation_window_seconds=2.5)


async def test_a_raising_detection_call_reports_the_sensor_error_and_publishes_nothing() -> None:
    sensor = FakeSensor(raise_on_detect=True)
    repository = FakePerceptionRepository()
    app = _FakeApp(sensors_by_source={"microphone": sensor}, repository=repository)
    outcome = await handle_observation_window(app, source="microphone", window=b"audio")
    assert outcome is not None
    assert outcome.presence_detected is True
    assert outcome.published is False
    assert repository.outbox == {}
    assert sensor.state() == "failed"
    assert len(sensor.errors) == 1


async def test_an_empty_window_is_handled_gracefully_not_as_a_crash() -> None:
    """An 'invalid window' this environment can actually construct: zero
    bytes. Real malformed-audio/malformed-image handling beyond this is a
    model-input-validation concern belonging to `ai-model-orchestration-
    engine`, not this orchestration -- this test proves the orchestration
    itself never crashes or corrupts state on garbage input, not that every
    possible malformed byte string is meaningfully classified."""
    sensor = FakeSensor(presence=False)  # a real presence-gate would reject empty audio
    repository = FakePerceptionRepository()
    app = _FakeApp(sensors_by_source={"microphone": sensor}, repository=repository)
    outcome = await handle_observation_window(app, source="microphone", window=b"")
    assert outcome is not None
    assert outcome.published is False


async def test_duplicate_windows_are_each_processed_and_published_independently() -> None:
    """No idempotency/dedup key exists anywhere in this codebase's outbox
    convention (confirmed by direct inspection of every other engine's own
    outbox usage) -- a duplicate ingestion call (e.g. a client retry) is
    expected to produce a duplicate event, the same at-least-once,
    idempotent-consumer-expected semantics every other engine's outbox
    already has. Documented here as accepted behavior, not a gap."""
    sensor = FakeSensor(wake_matched=True)
    repository = FakePerceptionRepository()
    app = _FakeApp(sensors_by_source={"microphone": sensor}, repository=repository)
    correlation_id = uuid4()

    await handle_observation_window(
        app, source="microphone", window=b"audio", correlation_id=correlation_id
    )
    await handle_observation_window(
        app, source="microphone", window=b"audio", correlation_id=correlation_id
    )

    assert len(repository.outbox) == 2


async def test_unconfigured_primary_user_id_publishes_nothing() -> None:
    """Priority 2's explicit degrade (closure doc Sec4): an unconfigured
    deployment never guesses a user identity -- it publishes nothing at
    all, not even the wake/gaze-only signal Priority 1 would have."""
    sensor = FakeSensor(wake_matched=True)
    repository = FakePerceptionRepository()
    app = _FakeApp(
        sensors_by_source={"microphone": sensor}, repository=repository, primary_user_id=None
    )
    outcome = await handle_observation_window(app, source="microphone", window=b"audio")
    assert outcome is not None
    assert outcome.published is False
    assert repository.outbox == {}
    assert sensor.presence_calls == []  # never even reached the presence gate


async def test_identity_matching_is_skipped_without_active_consent() -> None:
    """Doc 22 Principle 8 -- matching never runs before consent is
    verified, even though wake-word detection (a different, disclosed,
    unfixed gap) proceeds unconditionally."""
    identity_id = uuid4()
    sensor = FakeSensor(
        wake_matched=True,
        identity_signal=ModalitySignal(
            modality="voice", candidate_identity_id=identity_id, confidence=0.9
        ),
    )
    repository = FakePerceptionRepository()  # no consent granted
    app = _FakeApp(sensors_by_source={"microphone": sensor}, repository=repository)

    outcome = await handle_observation_window(app, source="microphone", window=b"audio")
    assert outcome is not None
    assert outcome.published is True
    assert sensor.match_calls == []  # matching never attempted

    row = next(iter(repository.outbox.values()))
    assert row.payload["identity_id"] is None
    assert row.payload["identity_confidence"] == 0.0
    assert row.payload["wake_word_matched"] is True  # unaffected by the missing consent


async def test_identity_matching_runs_and_publishes_with_active_consent() -> None:
    identity_id = uuid4()
    sensor = FakeSensor(
        wake_matched=True,
        identity_signal=ModalitySignal(
            modality="voice", candidate_identity_id=identity_id, confidence=0.9
        ),
    )
    repository = FakePerceptionRepository()
    app = _FakeApp(sensors_by_source={"microphone": sensor}, repository=repository)
    primary_user_id = app.state.settings.primary_user_id
    repository.consents.append(
        ConsentGrant(user_id=primary_user_id, source="microphone", scope="identity_matching")
    )

    outcome = await handle_observation_window(app, source="microphone", window=b"audio")
    assert outcome is not None
    assert outcome.published is True
    assert sensor.match_calls == [primary_user_id]

    row = next(iter(repository.outbox.values()))
    assert row.payload["identity_id"] == str(identity_id)
    assert row.payload["identity_confidence"] == 0.75  # single-signal confidence ceiling
    assert row.payload["user_id"] == str(primary_user_id)


async def test_a_no_match_result_publishes_no_identity_even_with_consent() -> None:
    sensor = FakeSensor(wake_matched=True, identity_signal=None)
    repository = FakePerceptionRepository()
    app = _FakeApp(sensors_by_source={"microphone": sensor}, repository=repository)
    primary_user_id = app.state.settings.primary_user_id
    repository.consents.append(
        ConsentGrant(user_id=primary_user_id, source="microphone", scope="identity_matching")
    )

    outcome = await handle_observation_window(app, source="microphone", window=b"audio")
    assert outcome is not None
    assert sensor.match_calls == [primary_user_id]

    row = next(iter(repository.outbox.values()))
    assert row.payload["identity_id"] is None
    assert row.payload["identity_confidence"] == 0.0


async def test_session_active_reflects_the_session_tracker() -> None:
    sensor = FakeSensor(wake_matched=True)
    repository = FakePerceptionRepository()
    tracker = SessionActivityTracker()
    app = _FakeApp(
        sensors_by_source={"microphone": sensor}, repository=repository, session_tracker=tracker
    )
    primary_user_id = app.state.settings.primary_user_id
    tracker.session_created(user_id=primary_user_id, session_id=uuid4())

    outcome = await handle_observation_window(app, source="microphone", window=b"audio")
    assert outcome is not None
    row = next(iter(repository.outbox.values()))
    assert row.payload["session_active"] is True


async def test_identity_signals_from_both_modalities_are_fused_across_calls() -> None:
    """The identity-signal counterpart to the existing wake/gaze
    cross-sensor correlation test: a voice match from one call and a face
    match (the same identity) from another, both still fresh, agree and
    raise fused confidence above either single-modality's own ceiling."""
    identity_id = uuid4()
    voice_sensor = FakeSensor(
        wake_matched=True,
        identity_signal=ModalitySignal(
            modality="voice", candidate_identity_id=identity_id, confidence=0.9
        ),
    )
    camera_sensor = FakeSensor(
        identity_signal=ModalitySignal(
            modality="face", candidate_identity_id=identity_id, confidence=0.9
        ),
    )
    repository = FakePerceptionRepository()
    app = _FakeApp(
        sensors_by_source={"microphone": voice_sensor, "camera": camera_sensor},
        repository=repository,
    )
    primary_user_id = app.state.settings.primary_user_id
    repository.consents.append(
        ConsentGrant(user_id=primary_user_id, source="microphone", scope="identity_matching")
    )
    repository.consents.append(
        ConsentGrant(user_id=primary_user_id, source="camera", scope="identity_matching")
    )

    await handle_observation_window(app, source="microphone", window=b"audio")
    await handle_observation_window(app, source="camera", window=b"frame")

    latest = list(repository.outbox.values())[-1]
    assert latest.payload["identity_id"] == str(identity_id)
    assert latest.payload["identity_confidence"] > 0.75  # agreement bonus, above the single ceiling
