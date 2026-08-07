"""Fake implementations of this engine's three upstream ports
(`domain.ports.PersonalityPort`, `ModelOrchestrationPort`, `WorldModelPort`)
-- deterministic, in-memory, configurable per test."""

from __future__ import annotations

from uuid import UUID

from nova_communication_engine.domain.ports import (
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
    ) -> None:
        self.outcome = outcome or ValidationOutcome(passed=True)
        self.raise_timeout = raise_timeout
        self.validate_calls: list[str] = []

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
        return StyleSelection(
            style="professional", verbosity="moderate", technical_depth="moderate"
        )


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
