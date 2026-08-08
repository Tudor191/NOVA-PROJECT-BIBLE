"""`POST /v1/perception/observations` (docs/design/phase-2d/
05-conversation-intelligence-closure.md Sec3, Priority 1) through the real,
lifespan-driven FastAPI app and the real `VoiceSensor`/`CameraSensor`
lifecycle -- the actual sensor `state()` machine, the actual
`detect_presence`/`detect_wake_phrase`/`estimate_attention` methods, wired
to `FakeAIModelOrchestrationPort` (the only fake in this chain: the real
`ai-model-orchestration-engine` RPC boundary, ADR-020) and
`FakePerceptionRepository`. This is the strongest verification tier this
sandbox can reach for Priority 1 -- everything except an actual captured
audio/video window arriving from a real device is real.

The window travels as the raw request body (see `api/observations.py`'s own
docstring for why a JSON `bytes` field was rejected during this pass --
Pydantic does not base64-decode it, and would have silently corrupted any
non-ASCII window byte).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from nova_perception_engine.config import Settings
from nova_perception_engine.main import create_app

from tests.fakes.ai_model_port import FakeAIModelOrchestrationPort
from tests.fakes.repository import FakePerceptionRepository

_LOUD_AUDIO = bytes([200]) * 320  # mean byte value 200 >= VoiceSensor's 30.0 energy threshold
_SILENT_AUDIO = bytes([0]) * 320  # mean byte value 0 < threshold -- presence gate rejects


@pytest.fixture
def harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePerceptionRepository()
    app = create_app(
        Settings(), repository=repository, ai_model_port=FakeAIModelOrchestrationPort()
    )
    with TestClient(app) as client:
        yield client, repository


def test_unknown_source_is_404(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    response = client.post("/v1/perception/observations", params={"source": "modem"}, content=b"")
    assert response.status_code == 404


def test_loud_audio_detects_presence_and_publishes_wake_signal(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness
    response = client.post(
        "/v1/perception/observations", params={"source": "microphone"}, content=_LOUD_AUDIO
    )
    assert response.status_code == 202
    body = response.json()
    assert body["sensor_id"] == "voice-sensor-1"
    assert body["presence_detected"] is True
    assert body["published"] is True

    row = next(iter(repository.outbox.values()))
    assert row.subject == "perception.addressee_signal.candidate"
    assert row.payload["wake_word_matched"] is True  # FakeAIModelOrchestrationPort's own default
    assert row.payload["identity_id"] is None  # Priority 2 dependency, disclosed


def test_silent_audio_detects_no_presence_and_publishes_nothing(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness
    response = client.post(
        "/v1/perception/observations", params={"source": "microphone"}, content=_SILENT_AUDIO
    )
    assert response.status_code == 202
    body = response.json()
    assert body["presence_detected"] is False
    assert body["published"] is False
    assert repository.outbox == {}


def test_a_camera_window_publishes_gaze_signal(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness
    response = client.post(
        "/v1/perception/observations", params={"source": "camera"}, content=b"a face crop"
    )
    assert response.status_code == 202
    assert response.json()["published"] is True

    row = next(iter(repository.outbox.values()))
    assert (
        row.payload["gaze_direction"] == "toward_device"
    )  # FakeAIModelOrchestrationPort's default


def test_two_calls_within_the_correlation_window_combine_wake_and_gaze(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness
    client.post("/v1/perception/observations", params={"source": "microphone"}, content=_LOUD_AUDIO)
    client.post("/v1/perception/observations", params={"source": "camera"}, content=b"a face crop")

    assert len(repository.outbox) == 2
    latest = list(repository.outbox.values())[-1]
    assert latest.payload["wake_word_matched"] is True  # still fresh from the first call
    assert latest.payload["gaze_direction"] == "toward_device"


def test_ai_model_orchestration_unavailable_degrades_gracefully_not_a_crash(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePerceptionRepository()
    app = create_app(
        Settings(),
        repository=repository,
        ai_model_port=FakeAIModelOrchestrationPort(available=False),
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/perception/observations", params={"source": "microphone"}, content=_LOUD_AUDIO
        )
        assert response.status_code == 202
        assert response.json()["published"] is True

        row = next(iter(repository.outbox.values()))
        assert row.payload["wake_word_matched"] is False  # Sec12's documented degraded default


def test_a_correlation_id_is_generated_when_the_caller_omits_one(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness
    response = client.post(
        "/v1/perception/observations", params={"source": "microphone"}, content=_LOUD_AUDIO
    )
    assert response.status_code == 202
    row = next(iter(repository.outbox.values()))
    assert row.correlation_id is not None
