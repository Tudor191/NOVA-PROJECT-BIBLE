"""`clients/` -- upstream port adapters, exercised against `FakeEventPublisher`
(no real Event Bus). Covers the `_summarize` truncation in `MemoryClient`,
graceful timeout degradation, `PersonalContextClient`'s projection of
`WorldModelSnapshot`, and `GoalsClient`'s honest empty-list placeholder.
"""

from __future__ import annotations

from uuid import uuid4

from nova_contracts import (
    ContextReplyPayload,
    MemoryRetrieveReplyPayload,
    MemorySearchResultPayload,
    MemoryType,
)
from nova_executive_cognition_engine.clients.goals_client import GoalsClient
from nova_executive_cognition_engine.clients.memory_client import MemoryClient, _summarize
from nova_executive_cognition_engine.clients.personal_context_client import PersonalContextClient
from nova_executive_cognition_engine.clients.world_model_client import WorldModelClient

from tests.fakes.event_publisher import FakeEventPublisher
from tests.fakes.ports import FakeWorldModelPort


async def test_memory_client_translates_reply() -> None:
    publisher = FakeEventPublisher()
    memory_id = uuid4()
    publisher.register(
        "memory.retrieve.request",
        lambda _req: MemoryRetrieveReplyPayload(
            results=[
                MemorySearchResultPayload(
                    memory_id=memory_id,
                    memory_type=MemoryType.EPISODIC,
                    content="short memory",
                    score=0.9,
                    importance_score=0.5,
                    confidence=0.8,
                )
            ]
        ),
    )
    client = MemoryClient(publisher)
    results = await client.retrieve(user_id=uuid4(), query="anything")
    assert results[0].memory_id == memory_id
    assert results[0].summary == "short memory"
    assert results[0].confidence == 0.8


async def test_memory_client_degrades_to_empty_on_timeout() -> None:
    client = MemoryClient(FakeEventPublisher())  # nothing registered -> TimeoutError
    results = await client.retrieve(user_id=uuid4(), query="anything")
    assert results == []


def test_summarize_never_exceeds_the_max_length() -> None:
    long_content = "x" * 1000
    summary = _summarize(long_content)
    assert len(summary) <= 280
    assert summary.endswith("…")


def test_summarize_leaves_short_content_unchanged() -> None:
    assert _summarize("short") == "short"


async def test_world_model_client_translates_reply() -> None:
    publisher = FakeEventPublisher()
    user_id = uuid4()
    publisher.register(
        "world_model.context.request",
        lambda _req: ContextReplyPayload(user_id=user_id, objective="ship it"),
    )
    client = WorldModelClient(publisher)
    snapshot = await client.get_context(user_id=user_id)
    assert snapshot is not None
    assert snapshot.objective == "ship it"


async def test_world_model_client_returns_none_on_timeout() -> None:
    client = WorldModelClient(FakeEventPublisher())
    assert await client.get_context(user_id=uuid4()) is None


async def test_personal_context_client_projects_world_model_snapshot() -> None:
    from nova_executive_cognition_engine.domain.models import WorldModelSnapshot

    user_id = uuid4()
    world_model = FakeWorldModelPort(WorldModelSnapshot(user_id=user_id, objective="ship it"))
    client = PersonalContextClient(world_model)
    context = await client.get_personal_context(user_id=user_id)
    assert context is not None
    assert context.objective == "ship it"


async def test_personal_context_client_returns_none_when_world_model_has_no_snapshot() -> None:
    client = PersonalContextClient(FakeWorldModelPort(None))
    assert await client.get_personal_context(user_id=uuid4()) is None


async def test_goals_client_is_an_honest_placeholder_returning_empty() -> None:
    client = GoalsClient()
    assert await client.current_goals(user_id=uuid4()) == []
