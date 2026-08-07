"""Sensor Abstraction Layer compliance suite (docs/design/phase-2d/
03-perception-engine.md §5, §20) -- `VoiceSensor` and `CameraSensor` both run
against the same shared lifecycle-contract tests, mirroring ADR-023's uniform
connector-compliance discipline applied here to sensors instead of model
connectors. Modality-specific behavior (wake phrase, voiceprint/faceprint
matching, gaze) is tested separately below.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from nova_perception_engine.domain.enrollment import encrypt_embedding
from nova_perception_engine.domain.models import EnrolledIdentity
from nova_perception_engine.sensors.camera_sensor import CameraSensor
from nova_perception_engine.sensors.voice_sensor import VoiceSensor

from tests.fakes.ai_model_port import FakeAIModelOrchestrationPort
from tests.fakes.repository import FakePerceptionRepository

_KEY = Fernet.generate_key()

_SENSOR_CLASSES = [VoiceSensor, CameraSensor]


def _make_sensor(cls, *, ai_model_port=None, repository=None):  # type: ignore[no-untyped-def]
    return cls(
        repository=repository or FakePerceptionRepository(),
        ai_model_port=ai_model_port or FakeAIModelOrchestrationPort(),
        encryption_key=_KEY,
    )


@pytest.mark.parametrize("sensor_cls", _SENSOR_CLASSES)
async def test_starts_uninitialized(sensor_cls) -> None:  # type: ignore[no-untyped-def]
    sensor = _make_sensor(sensor_cls)
    assert sensor.state() == "uninitialized"


@pytest.mark.parametrize("sensor_cls", _SENSOR_CLASSES)
async def test_full_lifecycle_happy_path(sensor_cls) -> None:  # type: ignore[no-untyped-def]
    sensor = _make_sensor(sensor_cls)
    await sensor.initialize()
    assert sensor.state() == "initialized"
    await sensor.start()
    assert sensor.state() == "running"
    await sensor.pause()
    assert sensor.state() == "paused"
    await sensor.resume()
    assert sensor.state() == "running"
    await sensor.stop()
    assert sensor.state() == "stopped"


@pytest.mark.parametrize("sensor_cls", _SENSOR_CLASSES)
async def test_illegal_transition_raises(sensor_cls) -> None:  # type: ignore[no-untyped-def]
    sensor = _make_sensor(sensor_cls)
    with pytest.raises(ValueError):
        await sensor.start()  # cannot start before initialize


@pytest.mark.parametrize("sensor_cls", _SENSOR_CLASSES)
async def test_report_error_transitions_running_sensor_to_failed(sensor_cls) -> None:  # type: ignore[no-untyped-def]
    from nova_perception_engine.domain.sensor import SensorErrorReport

    sensor = _make_sensor(sensor_cls)
    await sensor.initialize()
    await sensor.start()
    sensor.report_error(
        SensorErrorReport(sensor_id=sensor.sensor_id, message="boom", occurred_at="now")
    )
    assert sensor.state() == "failed"

    # Sec12's restart path: failed -> initialize is a legal transition.
    await sensor.initialize()
    assert sensor.state() == "initialized"


@pytest.mark.parametrize("sensor_cls", _SENSOR_CLASSES)
async def test_health_check_reports_available_only_while_running_or_paused(sensor_cls) -> None:  # type: ignore[no-untyped-def]
    repo = FakePerceptionRepository()
    sensor = _make_sensor(sensor_cls, repository=repo)

    assert (await sensor.health_check()).available is False  # uninitialized

    await sensor.initialize()
    await sensor.start()
    assert (await sensor.health_check()).available is True

    await sensor.pause()
    assert (await sensor.health_check()).available is True

    await sensor.stop()
    assert (await sensor.health_check()).available is False

    assert sensor.sensor_id in repo.sensor_health


@pytest.mark.parametrize("sensor_cls", _SENSOR_CLASSES)
async def test_calibrate_succeeds(sensor_cls) -> None:  # type: ignore[no-untyped-def]
    sensor = _make_sensor(sensor_cls)
    result = await sensor.calibrate()
    assert result.success is True


@pytest.mark.parametrize("sensor_cls", _SENSOR_CLASSES)
def test_configuration_reports_sensor_type(sensor_cls) -> None:  # type: ignore[no-untyped-def]
    sensor = _make_sensor(sensor_cls)
    config = sensor.configuration()
    assert config.sensor_id == sensor.sensor_id
    assert config.sensor_type in ("voice", "camera")


@pytest.mark.parametrize("sensor_cls", _SENSOR_CLASSES)
def test_every_capability_is_a_non_empty_string(sensor_cls) -> None:  # type: ignore[no-untyped-def]
    sensor = _make_sensor(sensor_cls)
    capabilities = sensor.capabilities()
    assert capabilities
    assert all(isinstance(c, str) and c for c in capabilities)
    assert "presence" in capabilities


# -- Modality-specific behavior --------------------------------------------


async def test_voice_sensor_detect_presence_gated_by_energy_threshold() -> None:
    sensor = _make_sensor(VoiceSensor)
    assert sensor.detect_presence(b"\x00" * 10) is False  # silence
    assert sensor.detect_presence(bytes([255] * 10)) is True  # loud


async def test_voice_sensor_detect_wake_phrase_reflects_port_result() -> None:
    port = FakeAIModelOrchestrationPort(wake_phrase_matched=True)
    sensor = _make_sensor(VoiceSensor, ai_model_port=port)
    assert await sensor.detect_wake_phrase(b"audio") is True
    assert "detect_wake_phrase" in port.calls


async def test_voice_sensor_detect_wake_phrase_false_when_model_unavailable() -> None:
    port = FakeAIModelOrchestrationPort(available=False)
    sensor = _make_sensor(VoiceSensor, ai_model_port=port)
    assert await sensor.detect_wake_phrase(b"audio") is False


async def test_voice_sensor_match_voiceprint_returns_none_with_no_enrolled_templates() -> None:
    sensor = _make_sensor(VoiceSensor)
    result = await sensor.match_voiceprint(b"audio", user_id=uuid4())
    assert result is None


async def test_voice_sensor_match_voiceprint_matches_enrolled_template() -> None:
    user_id = uuid4()
    embedding = [1.0, 0.0, 0.0]
    repo = FakePerceptionRepository()
    identity = EnrolledIdentity(
        user_id=user_id,
        modality="voice",
        template_ciphertext=encrypt_embedding(embedding, key=_KEY),
    )
    repo.identities[identity.identity_id] = identity
    port = FakeAIModelOrchestrationPort(voice_embedding=embedding)
    sensor = _make_sensor(VoiceSensor, ai_model_port=port, repository=repo)

    result = await sensor.match_voiceprint(b"audio", user_id=user_id)

    assert result is not None
    assert result.candidate_identity_id == identity.identity_id
    assert result.confidence == 1.0


async def test_camera_sensor_detect_presence_gated_by_frame_difference() -> None:
    sensor = _make_sensor(CameraSensor)
    frame = bytes([10] * 20)
    assert sensor.detect_presence(frame) is True  # first frame always "worth checking"
    assert sensor.detect_presence(frame) is False  # identical second frame, no change
    assert sensor.detect_presence(bytes([250] * 20)) is True  # large change


async def test_camera_sensor_match_faceprint_matches_enrolled_template() -> None:
    user_id = uuid4()
    embedding = [0.0, 1.0, 0.0]
    repo = FakePerceptionRepository()
    identity = EnrolledIdentity(
        user_id=user_id, modality="face", template_ciphertext=encrypt_embedding(embedding, key=_KEY)
    )
    repo.identities[identity.identity_id] = identity
    port = FakeAIModelOrchestrationPort(face_embedding=embedding)
    sensor = _make_sensor(CameraSensor, ai_model_port=port, repository=repo)

    result = await sensor.match_faceprint(b"crop", user_id=user_id)

    assert result is not None
    assert result.candidate_identity_id == identity.identity_id


async def test_camera_sensor_estimate_attention_maps_gaze_toward_device_to_engaged() -> None:
    port = FakeAIModelOrchestrationPort(gaze_direction="toward_device", gaze_confidence=0.8)
    sensor = _make_sensor(CameraSensor, ai_model_port=port)

    observation = await sensor.estimate_attention(b"crop", identity_id=None)

    assert observation.attention_state == "engaged"
    assert observation.confidence == 0.8


async def test_camera_sensor_estimate_attention_maps_gaze_away_to_disengaged() -> None:
    port = FakeAIModelOrchestrationPort(gaze_direction="away")
    sensor = _make_sensor(CameraSensor, ai_model_port=port)

    observation = await sensor.estimate_attention(b"crop", identity_id=None)

    assert observation.attention_state == "disengaged"


async def test_camera_sensor_estimate_attention_unknown_when_model_unavailable() -> None:
    port = FakeAIModelOrchestrationPort(available=False)
    sensor = _make_sensor(CameraSensor, ai_model_port=port)

    observation = await sensor.estimate_attention(b"crop", identity_id=None)

    assert observation.attention_state == "unknown"
    assert observation.confidence == 0.0
