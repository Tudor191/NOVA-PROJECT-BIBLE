"""In-memory fakes for the six upstream ports (`domain/ports.py`, §7) --
configurable, deterministic, no real network/model call, the same
`FakeConnector`-shaped determinism precedent Phase 2A established."""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_contracts import GenerateReplyPayload, GenerateRequestPayload
from nova_reasoning_engine.domain.models import (
    Goal,
    KnowledgeReference,
    MemoryReference,
    PersonalContext,
    WorldModelSnapshot,
)


class FakeMemoryPort:
    def __init__(self, results: list[MemoryReference] | None = None) -> None:
        self.results = results if results is not None else []
        self.calls: list[tuple[UUID, str]] = []

    async def retrieve(
        self,
        *,
        user_id: UUID,
        query: str,
        limit: int = 10,
        correlation_id: UUID | None = None,
    ) -> list[MemoryReference]:
        self.calls.append((user_id, query))
        return self.results[:limit]


class FakeKnowledgePort:
    def __init__(self, results: list[KnowledgeReference] | None = None) -> None:
        self.results = results if results is not None else []
        self.retrieve_calls: list[str] = []
        self.traverse_calls: list[str] = []

    async def retrieve(
        self, *, query: str, limit: int = 10, correlation_id: UUID | None = None
    ) -> list[KnowledgeReference]:
        self.retrieve_calls.append(query)
        return self.results[:limit]

    async def traverse(
        self, *, seed_node_id: str, depth: int = 2, correlation_id: UUID | None = None
    ) -> list[KnowledgeReference]:
        self.traverse_calls.append(seed_node_id)
        return self.results


class FakeWorldModelPort:
    def __init__(self, snapshot: WorldModelSnapshot | None = None) -> None:
        self.snapshot = snapshot
        self.calls: list[UUID] = []

    async def get_context(
        self, *, user_id: UUID, scope: str | None = None, correlation_id: UUID | None = None
    ) -> WorldModelSnapshot | None:
        self.calls.append(user_id)
        return self.snapshot


class FakePersonalContextPort:
    def __init__(self, context: PersonalContext | None = None) -> None:
        self.context = context

    async def get_personal_context(
        self, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> PersonalContext | None:
        return self.context


class FakeGoalsPort:
    def __init__(self, goals: list[Goal] | None = None) -> None:
        self.goals = goals if goals is not None else []

    async def current_goals(
        self, *, user_id: UUID, scope: str | None = None, correlation_id: UUID | None = None
    ) -> list[Goal]:
        return self.goals


class FakeModelOrchestrationPort:
    """Returns a caller-configured `GenerateReplyPayload` (or a default
    three-hypothesis response) -- never calls a real model (§24)."""

    def __init__(self, reply: GenerateReplyPayload | None = None) -> None:
        self.reply = reply
        self.requests: list[GenerateRequestPayload] = []

    async def generate(self, request: GenerateRequestPayload) -> GenerateReplyPayload:
        self.requests.append(request)
        if self.reply is not None:
            return self.reply
        return GenerateReplyPayload(
            text=(
                "1. The first candidate explanation.\n"
                "2. The second candidate explanation.\n"
                "3. The third candidate explanation."
            ),
            input_tokens=10,
            output_tokens=10,
            finish_reason="stop",
            structural_confidence=0.9,
            model_id=uuid4(),
            provider="fake",
        )
