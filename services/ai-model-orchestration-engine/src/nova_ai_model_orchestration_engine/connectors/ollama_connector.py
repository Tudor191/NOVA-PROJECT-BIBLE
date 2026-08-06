"""The default, zero-budget connector (Bible Part 7 "Initial Zero Budget
Strategy"; ADR-020's one legal home for provider coupling). `generate`/`stream`
talk to Ollama's `/api/chat` endpoint directly via `httpx` (lazily imported, same
pattern as `nova_embeddings_sdk.backends.ollama` -- importing this module never
requires an Ollama server to be reachable); `embed` reuses
`nova-embeddings-sdk`'s `OllamaEmbeddingProvider` rather than duplicating an
Ollama HTTP client for the same server (design doc §5, §10).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from nova_embeddings_sdk.backends.ollama import OllamaEmbeddingProvider

from nova_ai_model_orchestration_engine.domain.models import (
    ConnectorHealth,
    GenerateChunk,
    GenerateRequest,
    GenerateResult,
    SynthesizeRequest,
    SynthesizeResult,
    ToolCall,
    TranscribeRequest,
    TranscribeResult,
)
from nova_ai_model_orchestration_engine.domain.ports import NotSupportedError
from nova_ai_model_orchestration_engine.domain.tool_schema import parse_tool_arguments

if TYPE_CHECKING:
    import httpx

__all__ = ["OllamaConnector"]


def _messages_from_context(request: GenerateRequest) -> list[dict[str, str]]:
    """Ollama's chat API wants role-based messages; `ContextComponent`s carry no
    role of their own (design doc §0 -- they're formatting input, not a
    conversation). Convention: a component sourced `"user_request"` becomes the
    `user` turn; everything else concatenates into one `system` message, in
    caller-supplied order."""
    system_parts = [c.text for c in request.context if c.source != "user_request"]
    user_parts = [c.text for c in request.context if c.source == "user_request"]
    messages: list[dict[str, str]] = []
    if system_parts:
        messages.append({"role": "system", "content": "\n\n".join(system_parts)})
    messages.append({"role": "user", "content": "\n\n".join(user_parts) or "..."})
    return messages


def _tools_payload(request: GenerateRequest) -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters_json_schema,
            },
        }
        for t in request.tools
    ]


class OllamaConnector:
    connector_type = "ollama"

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        model: str,
        timeout_s: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """`client` is an injection point for tests (ADR-023's compliance suite
        supplies one built on `httpx.MockTransport`, never a live server) --
        production code always leaves it `None` and lets `_ensure_client` build
        a real one lazily."""
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._client = client
        self._embedding_provider = OllamaEmbeddingProvider(base_url=base_url, model=model)

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout_s)
        return self._client

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        client = self._ensure_client()
        payload: dict[str, object] = {
            "model": self._model,
            "messages": _messages_from_context(request),
            "stream": False,
        }
        if request.tools:
            payload["tools"] = _tools_payload(request)
        response = await client.post("/api/chat", json=payload)
        response.raise_for_status()
        body = response.json()
        message = body.get("message", {})
        tool_calls = [
            ToolCall(
                id=f"call_{i}",
                tool_name=call["function"]["name"],
                arguments=parse_tool_arguments(call["function"].get("arguments", {})),
            )
            for i, call in enumerate(message.get("tool_calls", []))
        ]
        return GenerateResult(
            text=message.get("content", ""),
            tool_calls=tool_calls,
            input_tokens=body.get("prompt_eval_count", 0),
            output_tokens=body.get("eval_count", 0),
            finish_reason="tool_calls" if tool_calls else "stop",
            structural_confidence=1.0 if body.get("done", True) else 0.5,
        )

    async def stream(self, request: GenerateRequest) -> AsyncIterator[GenerateChunk]:
        client = self._ensure_client()
        payload: dict[str, object] = {
            "model": self._model,
            "messages": _messages_from_context(request),
            "stream": True,
        }
        async with client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                import json

                chunk = json.loads(line)
                message = chunk.get("message", {})
                if chunk.get("done"):
                    yield GenerateChunk(finished=True, finish_reason="stop")
                    return
                yield GenerateChunk(delta_text=message.get("content", ""))

    async def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = await self._embedding_provider.embed_batch(texts)
        return [e.vector for e in embeddings]

    async def transcribe(self, request: TranscribeRequest) -> TranscribeResult:
        # Ollama serves text-generation models, not speech (design doc §0.3) --
        # raising cleanly here, the same explicit-not-silent pattern `embed()`
        # follows for Anthropic.
        raise NotSupportedError(self.connector_type, "speech_to_text")

    async def synthesize(self, request: SynthesizeRequest) -> SynthesizeResult:
        raise NotSupportedError(self.connector_type, "text_to_speech")

    def synthesize_stream(self, request: SynthesizeRequest) -> Any:
        # Not a generator (never yields) -- raises immediately on call, the
        # simplest honest shape for "this connector cannot do this at all,"
        # distinct from a real streaming connector that could fail mid-stream.
        raise NotSupportedError(self.connector_type, "text_to_speech")

    async def health(self) -> ConnectorHealth:
        client = self._ensure_client()
        try:
            import time

            start = time.perf_counter()
            response = await client.get("/api/tags")
            response.raise_for_status()
            latency_ms = (time.perf_counter() - start) * 1000
            return ConnectorHealth(available=True, latency_ms=latency_ms, error_rate=0.0)
        except Exception as exc:  # noqa: BLE001 -- health checks must never raise
            return ConnectorHealth(available=False, detail=str(exc))
