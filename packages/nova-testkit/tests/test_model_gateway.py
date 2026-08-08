"""Verifies `FakeModelGateway` (`model_gateway.py`) serves every `ai_model.*.
request` subject with real request/reply behavior through the `event_bus`
fixture -- no network, no testcontainers, no engine import (nova-testkit's own
tests stay as dependency-clean as its `src/`, per ADR-033; the "does a real
consuming engine's own client class work against this fake" proof lives in
that engine's own test suite instead, e.g. reasoning-engine's
`test_model_orchestration_client_against_fake_gateway.py`).
"""

from uuid import uuid4

import pytest
from nova_contracts.events.ai_model_orchestration import (
    EmbedReplyPayload,
    EmbedRequestPayload,
    GazeEstimateReplyPayload,
    GazeEstimateRequestPayload,
    GenerateReplyPayload,
    GenerateRequestPayload,
    TranscribeReplyPayload,
    TranscribeRequestPayload,
    WakePhraseDetectReplyPayload,
    WakePhraseDetectRequestPayload,
)
from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus
from nova_testkit import FakeModelGateway


async def test_generate_returns_deterministic_reply(
    event_bus: InMemoryEventBus, fake_model_gateway: FakeModelGateway
) -> None:
    request = GenerateRequestPayload(
        context=[], requesting_engine="test", correlation_id=uuid4()
    )
    envelope = await event_bus.request(
        "ai_model.generate.request", request, source_engine="test"
    )
    reply = GenerateReplyPayload.model_validate(envelope.payload)

    assert reply.text == "This is a fake response."
    assert reply.finish_reason == "stop"
    assert reply.error is None
    assert fake_model_gateway.calls == ["ai_model.generate.request"]


async def test_generate_honors_should_fail() -> None:
    bus = InMemoryEventBus()
    await bus.connect()
    gateway = FakeModelGateway(should_fail=True)
    await gateway.start(bus)
    try:
        request = GenerateRequestPayload(
            context=[], requesting_engine="test", correlation_id=uuid4()
        )
        envelope = await bus.request("ai_model.generate.request", request, source_engine="test")
        reply = GenerateReplyPayload.model_validate(envelope.payload)

        assert reply.finish_reason == "error"
        assert reply.error == "FakeModelGateway configured to fail"
    finally:
        await gateway.stop()
        await bus.close()


async def test_embed_returns_deterministic_vectors_stable_across_calls(
    event_bus: InMemoryEventBus, fake_model_gateway: FakeModelGateway
) -> None:
    request = EmbedRequestPayload(
        texts=["hello", "hello"], requesting_engine="test", correlation_id=uuid4()
    )
    envelope = await event_bus.request("ai_model.embed.request", request, source_engine="test")
    reply = EmbedReplyPayload.model_validate(envelope.payload)

    assert len(reply.embeddings) == 2
    assert reply.embeddings[0] == reply.embeddings[1]
    assert reply.error is None


async def test_transcribe_uses_configured_transcript_text() -> None:
    bus = InMemoryEventBus()
    await bus.connect()
    gateway = FakeModelGateway(transcript_text="configured transcript")
    await gateway.start(bus)
    try:
        request = TranscribeRequestPayload(
            audio_bytes=b"fake-audio", requesting_engine="test", correlation_id=uuid4()
        )
        envelope = await bus.request(
            "ai_model.transcribe.request", request, source_engine="test"
        )
        reply = TranscribeReplyPayload.model_validate(envelope.payload)

        assert reply.text == "configured transcript"
    finally:
        await gateway.stop()
        await bus.close()


async def test_detect_wake_phrase_uses_configured_match(
    event_bus: InMemoryEventBus,
) -> None:
    gateway = FakeModelGateway(wake_phrase_matches=False)
    await gateway.start(event_bus)
    try:
        request = WakePhraseDetectRequestPayload(
            audio_bytes=b"fake-audio", requesting_engine="test", correlation_id=uuid4()
        )
        envelope = await event_bus.request(
            "ai_model.detect_wake_phrase.request", request, source_engine="test"
        )
        reply = WakePhraseDetectReplyPayload.model_validate(envelope.payload)

        assert reply.matched is False
    finally:
        await gateway.stop()


async def test_estimate_gaze_uses_configured_direction(event_bus: InMemoryEventBus) -> None:
    gateway = FakeModelGateway(gaze_direction="away")
    await gateway.start(event_bus)
    try:
        request = GazeEstimateRequestPayload(
            image_bytes=b"fake-image", requesting_engine="test", correlation_id=uuid4()
        )
        envelope = await event_bus.request(
            "ai_model.estimate_gaze.request", request, source_engine="test"
        )
        reply = GazeEstimateReplyPayload.model_validate(envelope.payload)

        assert reply.gaze_direction == "away"
    finally:
        await gateway.stop()


async def test_stop_unsubscribes_and_further_requests_time_out(
    event_bus: InMemoryEventBus,
) -> None:
    gateway = FakeModelGateway()
    await gateway.start(event_bus)
    await gateway.stop()

    request = GenerateRequestPayload(context=[], requesting_engine="test", correlation_id=uuid4())
    with pytest.raises(TimeoutError):
        await event_bus.request(
            "ai_model.generate.request", request, source_engine="test", timeout_ms=50
        )
