"""Fake implementations of this engine's four upstream ports
(`domain.ports.PersonalityPort`, `ModelOrchestrationPort`, `WorldModelPort`,
`ReasoningPort`) -- deterministic, in-memory, configurable per test."""

from __future__ import annotations

import asyncio
from uuid import UUID

from nova_communication_engine.domain.ports import (
    ReasoningOutcomeResult,
    StyleSelection,
    ValidationOutcome,
    WorldModelSnapshot,
)


class FakePersonalityPort:
    def __init__(
        self,
        *,
        outcome: ValidationOutcome | None = None,
        raise_timeout: bool = False,
        style_selection: StyleSelection | None = None,
        raise_style_timeout: bool = False,
    ) -> None:
        self.outcome = outcome or ValidationOutcome(passed=True)
        self.raise_timeout = raise_timeout
        self.style_selection = style_selection or StyleSelection(
            style="professional", verbosity="moderate", technical_depth="moderate"
        )
        self.raise_style_timeout = raise_style_timeout
        self.validate_calls: list[str] = []
        self.select_style_calls: list[tuple[str | None, str | None]] = []

    async def validate_response(
        self,
        *,
        content: str,
        confidence_tier: str,
        session_id: UUID,
        correlation_id: UUID | None = None,
    ) -> ValidationOutcome:
        self.validate_calls.append(content)
        if self.raise_timeout:
            raise TimeoutError("personality.validate_response timed out")
        return self.outcome

    async def select_style(
        self,
        *,
        situation_hint: str | None,
        channel: str | None,
        correlation_id: UUID | None = None,
    ) -> StyleSelection:
        self.select_style_calls.append((situation_hint, channel))
        if self.raise_style_timeout:
            raise TimeoutError("personality.style.select timed out")
        return self.style_selection


class FakeModelOrchestrationPort:
    def __init__(
        self,
        *,
        transcript: str | None = "hello NOVA",
        audio_chunks: list[bytes | None] | None = None,
    ) -> None:
        self.transcript = transcript
        self._audio_chunks = audio_chunks
        self.synthesize_calls: list[str] = []

    async def transcribe(self, *, audio: bytes, correlation_id: UUID | None = None) -> str | None:
        return self.transcript

    async def synthesize(self, *, text: str, correlation_id: UUID | None = None) -> bytes | None:
        self.synthesize_calls.append(text)
        if self._audio_chunks is not None:
            if not self._audio_chunks:
                return None
            return self._audio_chunks.pop(0)
        return f"audio:{text}".encode()


class FakeWorldModelPort:
    def __init__(self, *, snapshot: WorldModelSnapshot | None = None) -> None:
        self.snapshot = snapshot

    async def get_context(
        self, *, user_id: UUID, scope: str | None = None, correlation_id: UUID | None = None
    ) -> WorldModelSnapshot | None:
        return self.snapshot


class FakeReasoningPort:
    """`hold` (unset by default) lets a test deterministically observe
    conversation-orchestration state *before* the background reasoning
    round trip completes -- `schedule_conversation_turn` (`conversation_
    orchestration.py`) runs as a detached `asyncio.Task`, so a test that
    wants to assert an in-flight state (e.g. still `thinking`) must control
    when this fake is allowed to return, rather than relying on how fast
    the event loop happens to schedule an un-gated fake's immediate
    return."""

    def __init__(
        self,
        *,
        result: ReasoningOutcomeResult | None = None,
        raise_timeout: bool = False,
        hold: asyncio.Event | None = None,
    ) -> None:
        self.result = result or ReasoningOutcomeResult(outcome="decided", content="Hello!")
        self.raise_timeout = raise_timeout
        self.hold = hold
        self.reason_calls: list[tuple[str, UUID, UUID | None]] = []

    async def reason(
        self, *, objective_text: str, user_id: UUID, correlation_id: UUID | None = None
    ) -> ReasoningOutcomeResult:
        self.reason_calls.append((objective_text, user_id, correlation_id))
        if self.hold is not None:
            await self.hold.wait()
        if self.raise_timeout:
            raise TimeoutError("reasoning.reason.request timed out")
        return self.result
