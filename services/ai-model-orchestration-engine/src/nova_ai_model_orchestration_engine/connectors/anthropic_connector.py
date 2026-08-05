"""The connector that proves the `ModelConnector` abstraction holds against a
real cloud provider (design doc §1) -- the second, deliberately different
connector implementation (different wire format, different tool-calling
convention, no public embedding endpoint) that the ADR-023 compliance suite runs
against alongside `OllamaConnector` and `FakeConnector`. `anthropic` (the
official SDK) is imported only here, per ADR-020.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from nova_ai_model_orchestration_engine.domain.models import (
    ConnectorHealth,
    GenerateChunk,
    GenerateRequest,
    GenerateResult,
    ToolCall,
)
from nova_ai_model_orchestration_engine.domain.ports import NotSupportedError

if TYPE_CHECKING:
    import anthropic

__all__ = ["AnthropicConnector"]


def _system_and_messages(request: GenerateRequest) -> tuple[str, list[dict[str, str]]]:
    """Anthropic's Messages API takes `system` as a top-level parameter, not a
    message with `role: "system"` -- the one genuinely provider-specific shape
    difference from Ollama's chat format, handled entirely inside this
    connector (ADR-023: no such difference leaks to callers)."""
    system_parts = [c.text for c in request.context if c.source != "user_request"]
    user_parts = [c.text for c in request.context if c.source == "user_request"]
    system = "\n\n".join(system_parts)
    messages = [{"role": "user", "content": "\n\n".join(user_parts) or "..."}]
    return system, messages


def _tools_payload(request: GenerateRequest) -> list[dict[str, object]]:
    return [
        {"name": t.name, "description": t.description, "input_schema": t.parameters_json_schema}
        for t in request.tools
    ]


class AnthropicConnector:
    connector_type = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_s: float = 60.0,
        client: anthropic.AsyncAnthropic | None = None,
    ) -> None:
        """`client` is an injection point for tests (ADR-023's compliance suite
        supplies a minimal fake satisfying only the `.messages.create`/`.stream`
        surface this connector actually calls) -- production code always leaves
        it `None` and lets `_ensure_client` build a real one lazily."""
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s
        self._client = client

    def _ensure_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=self._api_key, timeout=self._timeout_s)
        return self._client

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        client = self._ensure_client()
        system, messages = _system_and_messages(request)
        kwargs: dict[str, object] = {
            "model": self._model,
            "max_tokens": request.max_output_tokens or 4096,
            "system": system,
            "messages": messages,
        }
        if request.tools:
            kwargs["tools"] = _tools_payload(request)
        # anthropic's `.create()` overloads are keyed on a `stream` literal we
        # deliberately never pass via **kwargs -- mypy can't resolve the
        # overload from a loosely-typed dict; the call is correct at runtime
        # (verified by the ADR-023 compliance suite against a mocked client).
        response = await client.messages.create(**kwargs)  # type: ignore[call-overload]

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, tool_name=block.name, arguments=dict(block.input))
                )

        if tool_calls:
            finish_reason = "tool_calls"
        elif response.stop_reason == "max_tokens":
            finish_reason = "length"
        else:
            finish_reason = "stop"
        return GenerateResult(
            text="".join(text_parts),
            tool_calls=tool_calls,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            finish_reason=finish_reason,
            structural_confidence=1.0,
        )

    async def stream(self, request: GenerateRequest) -> AsyncIterator[GenerateChunk]:
        client = self._ensure_client()
        system, messages = _system_and_messages(request)
        async with client.messages.stream(
            model=self._model,
            max_tokens=request.max_output_tokens or 4096,
            system=system,
            messages=messages,  # type: ignore[arg-type]
        ) as stream:
            async for text in stream.text_stream:
                yield GenerateChunk(delta_text=text)
            yield GenerateChunk(finished=True, finish_reason="stop")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Anthropic has no public embedding endpoint (design doc §5) -- raising
        # here, rather than silently returning an empty/fake result, is exactly
        # what the ADR-023 compliance suite verifies every connector does for an
        # unsupported modality.
        raise NotSupportedError(self.connector_type, "embedding")

    async def health(self) -> ConnectorHealth:
        client = self._ensure_client()
        try:
            import time

            start = time.perf_counter()
            await client.messages.create(
                model=self._model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            latency_ms = (time.perf_counter() - start) * 1000
            return ConnectorHealth(available=True, latency_ms=latency_ms, error_rate=0.0)
        except Exception as exc:  # noqa: BLE001 -- health checks must never raise
            return ConnectorHealth(available=False, detail=str(exc))
