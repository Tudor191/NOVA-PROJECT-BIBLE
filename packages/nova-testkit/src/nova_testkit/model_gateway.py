"""`FakeModelGateway` -- a deterministic Event Bus request/reply responder
standing in for `ai-model-orchestration-engine` (docs/design/nova-testkit/
technical-implementation-plan.md §2.5), for any engine's tests that call it over
the bus. Every cross-engine client in this codebase (`ModelOrchestrationClient`,
`MemoryClient`, etc.) is a thin wrapper around `EventBus.request(subject, ...)`
per ADR-004/ADR-020 -- there is no HTTP boundary to fake, so this fakes the
event-bus contract directly.

Deliberately **not** a `ModelConnector` Protocol fake -- that already exists as
`ai-model-orchestration-engine`'s own production `FakeConnector`
(`connector_type = "fake"`). `FakeConnector` fakes the boundary between
`ai-model-orchestration-engine` and an external provider SDK; this fakes the
boundary between `ai-model-orchestration-engine` and every *other* engine, one
layer up. Modeled directly on `FakeConnector`'s own configurability
(deterministic responses, `should_fail`, call tracking), applied to the 8
request/reply subjects `nova_contracts.events.ai_model_orchestration` declares.

Requires no `testcontainers`, no database, no network -- built entirely on
whatever `EventBus` it is given (in practice, the `event_bus` fixture's
`InMemoryEventBus`, already provided by this package).
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

from nova_contracts import EventEnvelope
from nova_contracts.events.ai_model_orchestration import (
    EmbedReplyPayload,
    EmbedRequestPayload,
    FaceEmbedReplyPayload,
    FaceEmbedRequestPayload,
    GazeEstimateReplyPayload,
    GazeEstimateRequestPayload,
    GenerateReplyPayload,
    GenerateRequestPayload,
    SynthesizeReplyPayload,
    SynthesizeRequestPayload,
    ToolCallPayload,
    TranscribeReplyPayload,
    TranscribeRequestPayload,
    VoiceEmbedReplyPayload,
    VoiceEmbedRequestPayload,
    WakePhraseDetectReplyPayload,
    WakePhraseDetectRequestPayload,
)
from nova_eventbus_sdk import EventBus, Subscription
from pydantic import BaseModel

__all__ = ["FakeModelGateway"]

_FAKE_PROVIDER = "fake"
_FAKE_SOURCE_ENGINE = "nova-testkit-fake-model-gateway"
_FAIL_ERROR = "FakeModelGateway configured to fail"


class FakeModelGateway:
    """Serves every `ai_model.*.request` subject with deterministic, scripted
    replies -- the shared responder an engine's test points its real
    event-bus-request client at, instead of running a real
    `ai-model-orchestration-engine` and a real provider.

    Usage: `await gateway.start(event_bus)`, exercise the code under test
    against that same `event_bus`, then assert on `gateway.calls`. The
    `fake_model_gateway` fixture in `plugin.py` does the `start`/`stop`
    lifecycle automatically for the common case.
    """

    def __init__(
        self,
        *,
        response_text: str = "This is a fake response.",
        should_fail: bool = False,
        transcript_text: str = "this is a fake transcript",
        wake_phrase_matches: bool = True,
        gaze_direction: Literal["toward_device", "away", "unknown"] = "toward_device",
        model_id: UUID | None = None,
    ) -> None:
        self.response_text = response_text
        self.should_fail = should_fail
        self.transcript_text = transcript_text
        self.wake_phrase_matches = wake_phrase_matches
        self.gaze_direction = gaze_direction
        self.model_id = model_id or uuid4()
        self.calls: list[str] = []
        """Subjects served, in call order -- e.g. `["ai_model.generate.request"]`."""
        self._subscriptions: list[Subscription] = []

    async def start(self, bus: EventBus) -> None:
        """Register a `serve()` handler for every subject this gateway fakes.
        Call once per `EventBus` instance -- the same one-`serve()`-per-subject
        shape a real engine's own `main.py` uses, just all eight registered
        together."""
        handlers: tuple[tuple[str, object], ...] = (
            ("ai_model.generate.request", self._handle_generate),
            ("ai_model.embed.request", self._handle_embed),
            ("ai_model.transcribe.request", self._handle_transcribe),
            ("ai_model.synthesize.request", self._handle_synthesize),
            ("ai_model.detect_wake_phrase.request", self._handle_detect_wake_phrase),
            ("ai_model.embed_voice.request", self._handle_embed_voice),
            ("ai_model.embed_face.request", self._handle_embed_face),
            ("ai_model.estimate_gaze.request", self._handle_estimate_gaze),
        )
        for subject, handler in handlers:
            subscription = await bus.serve(
                subject,
                handler,  # type: ignore[arg-type]
                source_engine=_FAKE_SOURCE_ENGINE,
            )
            self._subscriptions.append(subscription)

    async def stop(self) -> None:
        """Unsubscribe every handler `start()` registered. Not required before
        the test's `event_bus` fixture closes the whole connection, but
        available for a test that wants to simulate "the gateway went away"
        mid-test."""
        for subscription in self._subscriptions:
            await subscription.unsubscribe()
        self._subscriptions = []

    async def _handle_generate(self, envelope: EventEnvelope) -> BaseModel:
        self.calls.append(envelope.subject)
        request = GenerateRequestPayload.model_validate(envelope.payload)
        if self.should_fail:
            return GenerateReplyPayload(
                text="",
                input_tokens=0,
                output_tokens=0,
                finish_reason="error",
                structural_confidence=0.0,
                model_id=self.model_id,
                provider=_FAKE_PROVIDER,
                error=_FAIL_ERROR,
            )
        tool_calls = [
            ToolCallPayload(id=f"call_{i}", tool_name=tool.name, arguments={})
            for i, tool in enumerate(request.tools)
        ]
        return GenerateReplyPayload(
            text=self.response_text,
            tool_calls=tool_calls,
            input_tokens=sum(c.token_estimate for c in request.context),
            output_tokens=len(self.response_text.split()),
            finish_reason="tool_calls" if tool_calls else "stop",
            structural_confidence=1.0,
            model_id=self.model_id,
            provider=_FAKE_PROVIDER,
        )

    async def _handle_embed(self, envelope: EventEnvelope) -> BaseModel:
        self.calls.append(envelope.subject)
        request = EmbedRequestPayload.model_validate(envelope.payload)
        if self.should_fail:
            return EmbedReplyPayload(
                embeddings=[], model_id=self.model_id, provider=_FAKE_PROVIDER, error=_FAIL_ERROR
            )
        # Deterministic, content-derived vectors -- not semantically meaningful,
        # but stable across calls for the same input, the same fidelity standard
        # ai-model-orchestration-engine's own FakeConnector.embed uses.
        embeddings = [[float(len(t)), float(sum(ord(c) for c in t) % 997)] for t in request.texts]
        return EmbedReplyPayload(
            embeddings=embeddings, model_id=self.model_id, provider=_FAKE_PROVIDER
        )

    async def _handle_transcribe(self, envelope: EventEnvelope) -> BaseModel:
        self.calls.append(envelope.subject)
        TranscribeRequestPayload.model_validate(envelope.payload)
        if self.should_fail:
            return TranscribeReplyPayload(
                text="",
                structural_confidence=0.0,
                model_id=self.model_id,
                provider=_FAKE_PROVIDER,
                error=_FAIL_ERROR,
            )
        return TranscribeReplyPayload(
            text=self.transcript_text,
            detected_language="en",
            structural_confidence=1.0,
            model_id=self.model_id,
            provider=_FAKE_PROVIDER,
        )

    async def _handle_synthesize(self, envelope: EventEnvelope) -> BaseModel:
        self.calls.append(envelope.subject)
        request = SynthesizeRequestPayload.model_validate(envelope.payload)
        if self.should_fail:
            return SynthesizeReplyPayload(
                audio_bytes=b"",
                audio_format=request.audio_format,
                structural_confidence=0.0,
                model_id=self.model_id,
                provider=_FAKE_PROVIDER,
                error=_FAIL_ERROR,
            )
        # Deterministic, content-derived "audio" -- the same fidelity standard
        # ai-model-orchestration-engine's own FakeConnector.synthesize uses.
        return SynthesizeReplyPayload(
            audio_bytes=request.text.encode("utf-8"),
            audio_format=request.audio_format,
            structural_confidence=1.0,
            model_id=self.model_id,
            provider=_FAKE_PROVIDER,
        )

    async def _handle_detect_wake_phrase(self, envelope: EventEnvelope) -> BaseModel:
        self.calls.append(envelope.subject)
        WakePhraseDetectRequestPayload.model_validate(envelope.payload)
        if self.should_fail:
            return WakePhraseDetectReplyPayload(
                matched=False,
                structural_confidence=0.0,
                model_id=self.model_id,
                provider=_FAKE_PROVIDER,
                error=_FAIL_ERROR,
            )
        return WakePhraseDetectReplyPayload(
            matched=self.wake_phrase_matches,
            structural_confidence=1.0,
            model_id=self.model_id,
            provider=_FAKE_PROVIDER,
        )

    async def _handle_embed_voice(self, envelope: EventEnvelope) -> BaseModel:
        self.calls.append(envelope.subject)
        request = VoiceEmbedRequestPayload.model_validate(envelope.payload)
        if self.should_fail:
            return VoiceEmbedReplyPayload(
                embedding=[], model_id=self.model_id, provider=_FAKE_PROVIDER, error=_FAIL_ERROR
            )
        return VoiceEmbedReplyPayload(
            embedding=[float(len(request.audio_bytes)), float(sum(request.audio_bytes) % 997)],
            model_id=self.model_id,
            provider=_FAKE_PROVIDER,
        )

    async def _handle_embed_face(self, envelope: EventEnvelope) -> BaseModel:
        self.calls.append(envelope.subject)
        request = FaceEmbedRequestPayload.model_validate(envelope.payload)
        if self.should_fail:
            return FaceEmbedReplyPayload(
                embedding=[], model_id=self.model_id, provider=_FAKE_PROVIDER, error=_FAIL_ERROR
            )
        return FaceEmbedReplyPayload(
            embedding=[float(len(request.image_bytes)), float(sum(request.image_bytes) % 997)],
            model_id=self.model_id,
            provider=_FAKE_PROVIDER,
        )

    async def _handle_estimate_gaze(self, envelope: EventEnvelope) -> BaseModel:
        self.calls.append(envelope.subject)
        GazeEstimateRequestPayload.model_validate(envelope.payload)
        if self.should_fail:
            return GazeEstimateReplyPayload(
                gaze_direction="unknown",
                structural_confidence=0.0,
                model_id=self.model_id,
                provider=_FAKE_PROVIDER,
                error=_FAIL_ERROR,
            )
        return GazeEstimateReplyPayload(
            gaze_direction=self.gaze_direction,
            structural_confidence=1.0,
            model_id=self.model_id,
            provider=_FAKE_PROVIDER,
        )
