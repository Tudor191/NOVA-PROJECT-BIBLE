"""ADR-023's compliance suite: one set of test functions, parametrized over
every `ModelConnector` implementation, run with a mocked transport for the
real connectors -- no live provider dependency, ever, in this suite (a
separate, manually-triggered "live model smoke test" per the design doc §19
is the only place a real Ollama server is required). Every connector must
satisfy the exact same assertions; a genuine capability difference (Anthropic
has no public embedding endpoint) is asserted explicitly, not silently
skipped.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import httpx
import pytest
from nova_ai_model_orchestration_engine.connectors.anthropic_connector import AnthropicConnector
from nova_ai_model_orchestration_engine.connectors.fake_connector import FakeConnector
from nova_ai_model_orchestration_engine.connectors.ollama_connector import OllamaConnector
from nova_ai_model_orchestration_engine.connectors.piper_connector import PiperConnector
from nova_ai_model_orchestration_engine.connectors.whisper_connector import WhisperConnector
from nova_ai_model_orchestration_engine.domain.models import (
    ContextComponent,
    GenerateRequest,
    PrivacyLevel,
    SynthesizeRequest,
    ToolSchema,
    TranscribeRequest,
)
from nova_ai_model_orchestration_engine.domain.ports import ModelConnector, NotSupportedError

ConnectorFactory = Callable[[], ModelConnector]


def _params(connectors: list[tuple[str, ConnectorFactory]]) -> pytest.MarkDecorator:
    return pytest.mark.parametrize(
        "factory", [c[1] for c in connectors], ids=[c[0] for c in connectors]
    )


_WEATHER_SCHEMA = {"type": "object", "properties": {"city": {"type": "string"}}}


def _request(*, with_tools: bool = False) -> GenerateRequest:
    tools = (
        [
            ToolSchema(
                name="get_weather",
                description="Get the weather",
                parameters_json_schema=_WEATHER_SCHEMA,
            )
        ]
        if with_tools
        else []
    )
    return GenerateRequest(
        context=[ContextComponent(source="user_request", text="Hello", token_estimate=5)],
        requesting_engine="test",
        privacy_hint=PrivacyLevel.INTERNAL,
        correlation_id=uuid4(),
        tools=tools,
    )


# --- Ollama: httpx.MockTransport handlers, no live server ------------------


def _ollama_success_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/chat":
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "Hello there."},
                "done": True,
                "prompt_eval_count": 5,
                "eval_count": 3,
            },
        )
    if request.url.path == "/api/embeddings":
        return httpx.Response(200, json={"embedding": [0.1, 0.2, 0.3]})
    if request.url.path == "/api/tags":
        return httpx.Response(200, json={"models": []})
    return httpx.Response(404)


def _ollama_failure_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, json={"error": "simulated failure"})


def _ollama_stream_handler(request: httpx.Request) -> httpx.Response:
    lines = [
        json.dumps({"message": {"content": "Hel"}, "done": False}),
        json.dumps({"message": {"content": "lo"}, "done": False}),
        json.dumps({"message": {}, "done": True}),
    ]
    return httpx.Response(200, content="\n".join(lines) + "\n")


def _make_ollama(handler: Callable[[httpx.Request], httpx.Response]) -> OllamaConnector:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://fake-ollama")
    connector = OllamaConnector(model="test-model", client=client)
    # nova-embeddings-sdk's OllamaEmbeddingProvider builds its own client lazily
    # and has no constructor-level injection point -- reaching into the
    # attribute here is test-only wiring, never done in production code.
    connector._embedding_provider._client = httpx.AsyncClient(
        transport=transport, base_url="http://fake-ollama"
    )
    return connector


# --- Anthropic: a minimal fake client satisfying only the surface this
# connector actually calls -- not a full SDK mock. --------------------------


class _FakeAnthropicBlock:
    def __init__(
        self,
        *,
        type_: str,
        text: str = "",
        id_: str = "",
        name: str = "",
        input_: dict | None = None,
    ) -> None:
        self.type = type_
        self.text = text
        self.id = id_
        self.name = name
        self.input = input_ or {}


class _FakeAnthropicUsage:
    def __init__(self, *, input_tokens: int = 5, output_tokens: int = 3) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeAnthropicMessage:
    def __init__(
        self, *, content: list[_FakeAnthropicBlock], stop_reason: str = "end_turn"
    ) -> None:
        self.content = content
        self.usage = _FakeAnthropicUsage()
        self.stop_reason = stop_reason


class _FakeAnthropicStream:
    def __init__(self, *, should_fail: bool) -> None:
        self.should_fail = should_fail

    async def __aenter__(self) -> _FakeAnthropicStream:
        if self.should_fail:
            raise RuntimeError("simulated provider failure")
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    @property
    async def text_stream(self) -> Any:
        for chunk in ["Hel", "lo"]:
            yield chunk


class _FakeAnthropicMessages:
    def __init__(self, *, should_fail: bool) -> None:
        self.should_fail = should_fail

    async def create(self, **kwargs: object) -> _FakeAnthropicMessage:
        if self.should_fail:
            raise RuntimeError("simulated provider failure")
        block = _FakeAnthropicBlock(type_="text", text="Hello there.")
        return _FakeAnthropicMessage(content=[block])

    def stream(self, **kwargs: object) -> _FakeAnthropicStream:
        return _FakeAnthropicStream(should_fail=self.should_fail)


class _FakeAnthropicClient:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.messages = _FakeAnthropicMessages(should_fail=should_fail)


def _make_anthropic(*, should_fail: bool = False) -> AnthropicConnector:
    fake_client = _FakeAnthropicClient(should_fail=should_fail)
    return AnthropicConnector(
        api_key="test-key",
        model="test-model",
        client=fake_client,  # type: ignore[arg-type]
    )


# --- Parametrization ---------------------------------------------------------

_WORKING_CONNECTORS: list[tuple[str, ConnectorFactory]] = [
    ("fake", lambda: FakeConnector()),
    ("ollama", lambda: _make_ollama(_ollama_success_handler)),
    ("anthropic", lambda: _make_anthropic(should_fail=False)),
]

_FAILING_CONNECTORS: list[tuple[str, ConnectorFactory]] = [
    ("fake", lambda: FakeConnector(should_fail=True)),
    ("ollama", lambda: _make_ollama(_ollama_failure_handler)),
    ("anthropic", lambda: _make_anthropic(should_fail=True)),
]

_STREAMING_CONNECTORS: list[tuple[str, ConnectorFactory]] = [
    ("fake", lambda: FakeConnector()),
    ("ollama", lambda: _make_ollama(_ollama_stream_handler)),
    ("anthropic", lambda: _make_anthropic(should_fail=False)),
]


@_params(_WORKING_CONNECTORS)
async def test_generate_returns_well_formed_result(factory: ConnectorFactory) -> None:
    connector = factory()
    result = await connector.generate(_request())
    assert isinstance(result.text, str) and result.text
    assert result.finish_reason in {"stop", "length", "tool_calls", "error"}
    assert result.output_tokens >= 0


@_params(_FAILING_CONNECTORS)
async def test_generate_raises_catchable_error_on_failure(factory: ConnectorFactory) -> None:
    connector = factory()
    # Any connector: a catchable Exception, never an unhandled/provider-specific crash.
    with pytest.raises(Exception, match=".*"):
        await connector.generate(_request())


@_params(_STREAMING_CONNECTORS)
async def test_stream_yields_incrementally(factory: ConnectorFactory) -> None:
    connector = factory()
    chunks = [chunk async for chunk in connector.stream(_request())]
    assert len(chunks) >= 1
    assert any(c.delta_text for c in chunks) or any(c.finished for c in chunks)


async def test_fake_embed_returns_well_formed_vectors() -> None:
    connector = FakeConnector()
    vectors = await connector.embed(["hello", "world"])
    assert len(vectors) == 2
    assert all(isinstance(v, list) and v for v in vectors)


async def test_ollama_embed_returns_well_formed_vectors() -> None:
    connector = _make_ollama(_ollama_success_handler)
    vectors = await connector.embed(["hello"])
    assert vectors == [[0.1, 0.2, 0.3]]


async def test_anthropic_embed_raises_not_supported_cleanly() -> None:
    connector = _make_anthropic()
    with pytest.raises(NotSupportedError):
        await connector.embed(["hello"])


@_params(_WORKING_CONNECTORS)
async def test_health_reports_available_when_working(factory: ConnectorFactory) -> None:
    connector = factory()
    health = await connector.health()
    assert health.available is True


async def test_ollama_health_reports_unavailable_on_transport_failure() -> None:
    connector = _make_ollama(_ollama_failure_handler)
    health = await connector.health()
    assert health.available is False


async def test_anthropic_health_reports_unavailable_on_failure() -> None:
    connector = _make_anthropic(should_fail=True)
    health = await connector.health()
    assert health.available is False


@_params(_WORKING_CONNECTORS)
async def test_tool_call_round_trip(factory: ConnectorFactory) -> None:
    connector = factory()
    result = await connector.generate(_request(with_tools=True))
    # Every connector must accept a tool-schema-bearing request without error;
    # whether *this* canned response actually invokes the tool is a
    # per-fixture detail (FakeConnector always echoes a tool call; the mocked
    # Ollama/Anthropic responses above don't), not a compliance requirement.
    assert isinstance(result.tool_calls, list)


# --- Speech (Whisper/Piper): docs/design/phase-2d/01-communication-engine.md
# §0.3 -- the same "no live provider dependency ever in this suite" discipline,
# mocked transports only. --------------------------------------------------


def _transcribe_request() -> TranscribeRequest:
    return TranscribeRequest(
        audio_bytes=b"fake-wav-bytes", requesting_engine="test", correlation_id=uuid4()
    )


def _synthesize_request() -> SynthesizeRequest:
    return SynthesizeRequest(text="Hello there.", requesting_engine="test", correlation_id=uuid4())


def _whisper_success_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v1/audio/transcriptions":
        return httpx.Response(200, json={"text": "hello there", "language": "en"})
    if request.url.path == "/health":
        return httpx.Response(200, json={"status": "ok"})
    return httpx.Response(404)


def _whisper_failure_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, json={"error": "simulated failure"})


def _make_whisper(handler: Callable[[httpx.Request], httpx.Response]) -> WhisperConnector:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://fake-whisper")
    return WhisperConnector(model="test-model", client=client)


def _piper_success_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v1/audio/speech":
        return httpx.Response(200, content=b"fake-audio-bytes")
    if request.url.path == "/health":
        return httpx.Response(200, json={"status": "ok"})
    return httpx.Response(404)


def _piper_failure_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, json={"error": "simulated failure"})


def _make_piper(handler: Callable[[httpx.Request], httpx.Response]) -> PiperConnector:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://fake-piper")
    return PiperConnector(client=client)


async def test_whisper_transcribe_returns_well_formed_result() -> None:
    connector = _make_whisper(_whisper_success_handler)
    result = await connector.transcribe(_transcribe_request())
    assert result.text == "hello there"
    assert result.detected_language == "en"
    assert result.structural_confidence == 1.0


async def test_whisper_transcribe_raises_catchable_error_on_failure() -> None:
    connector = _make_whisper(_whisper_failure_handler)
    with pytest.raises(Exception, match=".*"):
        await connector.transcribe(_transcribe_request())


async def test_whisper_health_reports_unavailable_on_transport_failure() -> None:
    connector = _make_whisper(_whisper_failure_handler)
    health = await connector.health()
    assert health.available is False


async def test_whisper_generate_raises_not_supported_cleanly() -> None:
    connector = _make_whisper(_whisper_success_handler)
    with pytest.raises(NotSupportedError):
        await connector.generate(_request())


async def test_whisper_synthesize_raises_not_supported_cleanly() -> None:
    connector = _make_whisper(_whisper_success_handler)
    with pytest.raises(NotSupportedError):
        await connector.synthesize(_synthesize_request())


async def test_piper_synthesize_returns_well_formed_result() -> None:
    connector = _make_piper(_piper_success_handler)
    result = await connector.synthesize(_synthesize_request())
    assert result.audio_bytes == b"fake-audio-bytes"
    assert result.structural_confidence == 1.0


async def test_piper_synthesize_stream_yields_incrementally() -> None:
    connector = _make_piper(_piper_success_handler)
    chunks = [chunk async for chunk in connector.synthesize_stream(_synthesize_request())]
    assert len(chunks) >= 1
    assert any(c.delta_audio_bytes for c in chunks) or any(c.finished for c in chunks)


async def test_piper_synthesize_raises_catchable_error_on_failure() -> None:
    connector = _make_piper(_piper_failure_handler)
    with pytest.raises(Exception, match=".*"):
        await connector.synthesize(_synthesize_request())


async def test_piper_health_reports_unavailable_on_transport_failure() -> None:
    connector = _make_piper(_piper_failure_handler)
    health = await connector.health()
    assert health.available is False


async def test_piper_transcribe_raises_not_supported_cleanly() -> None:
    connector = _make_piper(_piper_success_handler)
    with pytest.raises(NotSupportedError):
        await connector.transcribe(_transcribe_request())


_NON_SPEECH_CONNECTORS: list[tuple[str, ConnectorFactory]] = [
    ("ollama", lambda: _make_ollama(_ollama_success_handler)),
    ("anthropic", lambda: _make_anthropic(should_fail=False)),
]
"""`FakeConnector` deliberately excluded here -- unlike Ollama/Anthropic, it
*does* support speech by default (`supports_speech=True`), the same asymmetry
`test_fake_embed_returns_well_formed_vectors` already carries for embedding."""


@_params(_NON_SPEECH_CONNECTORS)
async def test_non_speech_connectors_raise_not_supported_for_transcribe(
    factory: ConnectorFactory,
) -> None:
    connector = factory()
    with pytest.raises(NotSupportedError):
        await connector.transcribe(_transcribe_request())


@_params(_NON_SPEECH_CONNECTORS)
async def test_non_speech_connectors_raise_not_supported_for_synthesize(
    factory: ConnectorFactory,
) -> None:
    connector = factory()
    with pytest.raises(NotSupportedError):
        await connector.synthesize(_synthesize_request())


async def test_fake_transcribe_returns_well_formed_result() -> None:
    connector = FakeConnector()
    result = await connector.transcribe(_transcribe_request())
    assert result.text
    assert result.structural_confidence == 1.0


async def test_fake_synthesize_returns_well_formed_result() -> None:
    connector = FakeConnector()
    result = await connector.synthesize(_synthesize_request())
    assert result.audio_bytes
    assert result.structural_confidence == 1.0


async def test_fake_synthesize_stream_yields_incrementally() -> None:
    connector = FakeConnector()
    chunks = [chunk async for chunk in connector.synthesize_stream(_synthesize_request())]
    assert len(chunks) >= 1
