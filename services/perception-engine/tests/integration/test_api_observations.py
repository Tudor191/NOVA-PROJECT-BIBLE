"""`POST /v1/perception/observations` (docs/design/phase-2d/
05-conversation-intelligence-closure.md Sec3/Sec4, Priorities 1 and 2)
through the real, lifespan-driven FastAPI app and the real `VoiceSensor`/
`CameraSensor` lifecycle -- the actual sensor `state()` machine, the actual
`detect_presence`/`detect_wake_phrase`/`estimate_attention`/
`match_voiceprint`/`match_faceprint` methods, wired to
`FakeAIModelOrchestrationPort` (the only fake in this chain: the real
`ai-model-orchestration-engine` RPC boundary, ADR-020) and
`FakePerceptionRepository`. This is the strongest verification tier this
sandbox can reach for Priorities 1 and 2 -- everything except an actual
captured audio/video window arriving from a real device, and the real
biometric embedding models themselves, is real: the encryption/decryption
round trip (`domain/enrollment.py`/`domain/matching.py`), the cosine-
similarity scoring, and the consent gate all run for real against an
actually-enrolled template.

The window travels as the raw request body (see `api/observations.py`'s own
docstring for why a JSON `bytes` field was rejected during this pass --
Pydantic does not base64-decode it, and would have silently corrupted any
non-ASCII window byte).

`primary_user_id` is configured in every `Settings(...)` construction below
(Priority 2) -- without it, `handle_observation_window` now degrades to
publishing nothing at all (see `test_observation_orchestration.py`'s own
dedicated coverage of that branch), which would silently break every one of
these Priority-1-era assertions if left unset.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from nova_perception_engine.config import Settings
from nova_perception_engine.domain.enrollment import encrypt_embedding
from nova_perception_engine.domain.models import ConsentGrant, EnrolledIdentity
from nova_perception_engine.main import create_app

from tests.fakes.ai_model_port import FakeAIModelOrchestrationPort
from tests.fakes.repository import FakePerceptionRepository

_LOUD_AUDIO = bytes([200]) * 320  # mean byte value 200 >= VoiceSensor's 30.0 energy threshold
_SILENT_AUDIO = bytes([0]) * 320  # mean byte value 0 < threshold -- presence gate rejects
_PRIMARY_USER_ID = uuid4()
_ENCRYPTION_KEY = "3ktMjuHsQ9TNWhEiReuORzkawsz4KEYq2zDMZByQhHo="  # test-only Fernet key


@pytest.fixture
def harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePerceptionRepository()
    app = create_app(
        Settings(primary_user_id=_PRIMARY_USER_ID),
        repository=repository,
        ai_model_port=FakeAIModelOrchestrationPort(),
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
    assert row.payload["identity_id"] is None  # no consent granted in this fixture
    assert row.payload["user_id"] == str(_PRIMARY_USER_ID)


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
        Settings(primary_user_id=_PRIMARY_USER_ID),
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


def test_unconfigured_primary_user_id_publishes_nothing(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Priority 2's explicit degrade, through the real app/sensor lifecycle
    rather than the unit-level `_FakeApp` double."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePerceptionRepository()
    app = create_app(
        Settings(), repository=repository, ai_model_port=FakeAIModelOrchestrationPort()
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/perception/observations", params={"source": "microphone"}, content=_LOUD_AUDIO
        )
        assert response.status_code == 202
        assert response.json()["published"] is False
        assert repository.outbox == {}


def test_enrolled_and_consented_voice_match_reaches_the_payload(  # type: ignore[no-untyped-def]
    monkeypatch,
) -> None:
    """The full Priority 2 identity path through the real `VoiceSensor`:
    an actually-enrolled, actually-encrypted template, actual consent
    granted, the real cosine-similarity match against the real (fake-port-
    supplied) embedding -- everything except the biometric embedding model
    itself and a real captured audio window."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePerceptionRepository()
    embedding = [1.0, 0.0, 0.0]  # matches FakeAIModelOrchestrationPort's own default
    identity = EnrolledIdentity(
        user_id=_PRIMARY_USER_ID,
        modality="voice",
        template_ciphertext=encrypt_embedding(embedding, key=_ENCRYPTION_KEY.encode("utf-8")),
    )
    repository.identities[identity.identity_id] = identity
    repository.consents.append(
        ConsentGrant(user_id=_PRIMARY_USER_ID, source="microphone", scope="identity_matching")
    )
    app = create_app(
        Settings(primary_user_id=_PRIMARY_USER_ID, template_encryption_key=_ENCRYPTION_KEY),
        repository=repository,
        ai_model_port=FakeAIModelOrchestrationPort(voice_embedding=embedding),
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/perception/observations", params={"source": "microphone"}, content=_LOUD_AUDIO
        )
        assert response.status_code == 202
        assert response.json()["published"] is True

        row = next(iter(repository.outbox.values()))
        assert row.payload["identity_id"] == str(identity.identity_id)
        assert row.payload["identity_confidence"] == 0.75  # single-signal confidence ceiling
        assert row.payload["user_id"] == str(_PRIMARY_USER_ID)
