from uuid import uuid4

import pytest
from nova_contracts import (
    ContextReplyPayload,
    GenerateReplyPayload,
    GenerateRequestPayload,
    GoalSnapshot,
    KnowledgeLayer,
    KnowledgeRetrieveReplyPayload,
    KnowledgeSearchResultPayload,
    KnowledgeTraverseReplyPayload,
    MemoryRetrieveReplyPayload,
    MemorySearchResultPayload,
    MemoryType,
    PlanningGoalsCurrentReplyPayload,
    PlanningGoalsCurrentRequestPayload,
)
from nova_reasoning_engine.clients.goals_client import GoalsClient
from nova_reasoning_engine.clients.knowledge_client import KnowledgeClient
from nova_reasoning_engine.clients.memory_client import MemoryClient
from nova_reasoning_engine.clients.model_orchestration_client import ModelOrchestrationClient
from nova_reasoning_engine.clients.personal_context_client import PersonalContextClient
from nova_reasoning_engine.clients.world_model_client import WorldModelClient
from nova_reasoning_engine.domain.models import WorldModelSnapshot

from tests.fakes.event_publisher import FakeEventPublisher
from tests.fakes.ports import FakeWorldModelPort


async def test_memory_client_translates_reply_and_truncates_never_over_content() -> None:
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


async def test_knowledge_client_retrieve_translates_layer_enum_to_string() -> None:
    publisher = FakeEventPublisher()
    publisher.register(
        "knowledge.retrieve.request",
        lambda _req: KnowledgeRetrieveReplyPayload(
            results=[
                KnowledgeSearchResultPayload(
                    node_id="n1",
                    label="Concept",
                    name="gravity",
                    score=0.9,
                    confidence=0.7,
                    layer=KnowledgeLayer.VERIFIED,
                )
            ]
        ),
    )
    client = KnowledgeClient(publisher)
    results = await client.retrieve(query="gravity")
    assert results[0].node_id == "n1"
    assert results[0].layer == "verified"


async def test_knowledge_client_traverse_uses_honest_placeholder_confidence() -> None:
    publisher = FakeEventPublisher()
    publisher.register(
        "knowledge.traverse.request",
        lambda _req: KnowledgeTraverseReplyPayload(connected_node_ids=["n1", "n2"]),
    )
    client = KnowledgeClient(publisher)
    results = await client.traverse(seed_node_id="n0")
    assert [r.node_id for r in results] == ["n1", "n2"]
    assert all(r.confidence == 0.5 for r in results)


async def test_world_model_client_translates_degraded_flag() -> None:
    publisher = FakeEventPublisher()
    user_id = uuid4()
    publisher.register(
        "world_model.context.request",
        lambda _req: ContextReplyPayload(user_id=user_id, objective="ship it", degraded=True),
    )
    client = WorldModelClient(publisher)
    snapshot = await client.get_context(user_id=user_id)
    assert snapshot is not None
    assert snapshot.objective == "ship it"
    assert snapshot.degraded is True


async def test_world_model_client_returns_none_on_timeout() -> None:
    client = WorldModelClient(FakeEventPublisher())
    assert await client.get_context(user_id=uuid4()) is None


async def test_personal_context_client_projects_world_model_snapshot() -> None:
    user_id = uuid4()
    world_model_port = FakeWorldModelPort(
        WorldModelSnapshot(user_id=user_id, objective="ship it", device="laptop", task="coding")
    )
    client = PersonalContextClient(world_model_port)
    context = await client.get_personal_context(user_id=user_id)
    assert context is not None
    assert context.objective == "ship it"
    assert context.device == "laptop"


async def test_personal_context_client_returns_none_when_world_model_has_nothing() -> None:
    client = PersonalContextClient(FakeWorldModelPort(None))
    assert await client.get_personal_context(user_id=uuid4()) is None


async def test_goals_client_translates_reply_into_domain_goals() -> None:
    publisher = FakeEventPublisher()
    goal_id = uuid4()

    def handler(req: PlanningGoalsCurrentRequestPayload) -> PlanningGoalsCurrentReplyPayload:
        assert req.requesting_engine == "reasoning-engine"
        return PlanningGoalsCurrentReplyPayload(
            goals=[
                GoalSnapshot(
                    id=goal_id, description="Ship rate limiting", priority=0.8,
                    goal_tier="established",
                )
            ]
        )

    publisher.register("planning.goals.current.request", handler)
    client = GoalsClient(publisher)
    goals = await client.current_goals(user_id=uuid4())
    assert len(goals) == 1
    assert goals[0].id == goal_id
    assert goals[0].description == "Ship rate limiting"
    assert goals[0].priority == 0.8


async def test_goals_client_degrades_to_empty_list_on_timeout() -> None:
    client = GoalsClient(FakeEventPublisher())  # nothing registered -> TimeoutError
    assert await client.current_goals(user_id=uuid4()) == []


async def test_model_orchestration_client_round_trips_generate() -> None:
    publisher = FakeEventPublisher()
    model_id = uuid4()

    def handler(req: GenerateRequestPayload) -> GenerateReplyPayload:
        assert req.requesting_engine == "reasoning-engine"
        return GenerateReplyPayload(
            text="hello",
            input_tokens=1,
            output_tokens=1,
            finish_reason="stop",
            structural_confidence=1.0,
            model_id=model_id,
            provider="anthropic",
        )

    publisher.register("ai_model.generate.request", handler)
    client = ModelOrchestrationClient(publisher)
    reply = await client.generate(
        GenerateRequestPayload(
            context=[], requesting_engine="reasoning-engine", correlation_id=uuid4()
        )
    )
    assert reply.model_id == model_id
    assert reply.text == "hello"


async def test_model_orchestration_client_propagates_timeout() -> None:
    client = ModelOrchestrationClient(FakeEventPublisher())
    with pytest.raises(TimeoutError):
        await client.generate(
            GenerateRequestPayload(
                context=[], requesting_engine="reasoning-engine", correlation_id=uuid4()
            )
        )
