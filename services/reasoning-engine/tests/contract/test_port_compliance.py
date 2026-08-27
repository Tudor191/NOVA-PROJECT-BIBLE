"""ADR-023's compliance discipline, applied to this engine's six upstream
ports (docs/design/phase-2b/00-reasoning-engine.md §24): for each port, a
fake implementation and a mock-transport-backed real-client implementation
(via `FakeEventPublisher`, no real network/event-bus/model dependency) must
both satisfy the identical test functions. A genuine behavioral difference
(e.g. `GoalsPort`'s Phase 2B placeholder always returning `[]`, §7.1) is
asserted explicitly, not silently skipped.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

import pytest
from nova_contracts import (
    ContextReplyPayload,
    GenerateReplyPayload,
    KnowledgeLayer,
    KnowledgeRetrieveReplyPayload,
    KnowledgeSearchResultPayload,
    KnowledgeTraverseReplyPayload,
    MemoryRetrieveReplyPayload,
    MemorySearchResultPayload,
    MemoryType,
)
from nova_reasoning_engine.clients.goals_client import GoalsClient
from nova_reasoning_engine.clients.knowledge_client import KnowledgeClient
from nova_reasoning_engine.clients.memory_client import MemoryClient
from nova_reasoning_engine.clients.model_orchestration_client import ModelOrchestrationClient
from nova_reasoning_engine.clients.personal_context_client import PersonalContextClient
from nova_reasoning_engine.clients.world_model_client import WorldModelClient
from nova_reasoning_engine.domain.models import (
    KnowledgeReference,
    MemoryReference,
    PersonalContext,
    WorldModelSnapshot,
)
from nova_reasoning_engine.domain.ports import (
    GoalsPort,
    KnowledgePort,
    MemoryPort,
    ModelOrchestrationPort,
    PersonalContextPort,
    WorldModelPort,
)

from tests.fakes.event_publisher import FakeEventPublisher
from tests.fakes.ports import (
    FakeGoalsPort,
    FakeKnowledgePort,
    FakeMemoryPort,
    FakeModelOrchestrationPort,
    FakePersonalContextPort,
    FakeWorldModelPort,
)


def _params(factories: list[tuple[str, Callable[[], object]]]) -> pytest.MarkDecorator:
    return pytest.mark.parametrize(
        "factory", [f[1] for f in factories], ids=[f[0] for f in factories]
    )


# --- MemoryPort --------------------------------------------------------------

_MEMORY_ID = uuid4()


def _make_real_memory_port() -> MemoryPort:
    publisher = FakeEventPublisher()
    publisher.register(
        "memory.retrieve.request",
        lambda _req: MemoryRetrieveReplyPayload(
            results=[
                MemorySearchResultPayload(
                    memory_id=_MEMORY_ID,
                    memory_type=MemoryType.EPISODIC,
                    content="a matching memory",
                    score=0.9,
                    importance_score=0.5,
                    confidence=0.8,
                )
            ]
        ),
    )
    return MemoryClient(publisher)


_FAKE_MEMORY = MemoryReference(memory_id=_MEMORY_ID, summary="a matching memory", confidence=0.8)
_MEMORY_PORTS: list[tuple[str, Callable[[], MemoryPort]]] = [
    ("fake", lambda: FakeMemoryPort([_FAKE_MEMORY])),
    ("real", _make_real_memory_port),
]


@_params(_MEMORY_PORTS)
async def test_memory_port_retrieve_returns_memory_references(
    factory: Callable[[], MemoryPort],
) -> None:
    port = factory()
    results = await port.retrieve(user_id=uuid4(), query="anything")
    assert len(results) == 1
    assert results[0].memory_id == _MEMORY_ID
    assert isinstance(results[0].summary, str) and results[0].summary


# --- KnowledgePort -------------------------------------------------------------


def _make_real_knowledge_port() -> KnowledgePort:
    publisher = FakeEventPublisher()
    publisher.register(
        "knowledge.retrieve.request",
        lambda _req: KnowledgeRetrieveReplyPayload(
            results=[
                KnowledgeSearchResultPayload(
                    node_id="n1", label="Concept", name="gravity", score=0.9,
                    confidence=0.7, layer=KnowledgeLayer.VERIFIED,
                )
            ]
        ),
    )
    publisher.register(
        "knowledge.traverse.request",
        lambda _req: KnowledgeTraverseReplyPayload(connected_node_ids=["n2"]),
    )
    return KnowledgeClient(publisher)


_FAKE_KNOWLEDGE = KnowledgeReference(node_id="n1", name="gravity", layer="verified", confidence=0.7)
_KNOWLEDGE_PORTS: list[tuple[str, Callable[[], KnowledgePort]]] = [
    ("fake", lambda: FakeKnowledgePort([_FAKE_KNOWLEDGE])),
    ("real", _make_real_knowledge_port),
]


@_params(_KNOWLEDGE_PORTS)
async def test_knowledge_port_retrieve_returns_knowledge_references(
    factory: Callable[[], KnowledgePort],
) -> None:
    port = factory()
    results = await port.retrieve(query="gravity")
    assert len(results) == 1
    assert results[0].node_id == "n1"
    assert isinstance(results[0].layer, str) and results[0].layer


@_params(_KNOWLEDGE_PORTS)
async def test_knowledge_port_traverse_returns_a_list(
    factory: Callable[[], KnowledgePort],
) -> None:
    port = factory()
    results = await port.traverse(seed_node_id="n0")
    assert isinstance(results, list)


# --- WorldModelPort ------------------------------------------------------------

_WORLD_MODEL_USER_ID = uuid4()


def _make_real_world_model_port() -> WorldModelPort:
    publisher = FakeEventPublisher()
    publisher.register(
        "world_model.context.request",
        lambda _req: ContextReplyPayload(user_id=_WORLD_MODEL_USER_ID, objective="ship it"),
    )
    return WorldModelClient(publisher)


_FAKE_WORLD_MODEL_SNAPSHOT = WorldModelSnapshot(user_id=_WORLD_MODEL_USER_ID, objective="ship it")
_WORLD_MODEL_PORTS: list[tuple[str, Callable[[], WorldModelPort]]] = [
    ("fake", lambda: FakeWorldModelPort(_FAKE_WORLD_MODEL_SNAPSHOT)),
    ("real", _make_real_world_model_port),
]


@_params(_WORLD_MODEL_PORTS)
async def test_world_model_port_get_context_returns_a_snapshot(
    factory: Callable[[], WorldModelPort],
) -> None:
    port = factory()
    snapshot = await port.get_context(user_id=_WORLD_MODEL_USER_ID)
    assert snapshot is not None
    assert snapshot.objective == "ship it"


async def test_world_model_port_get_context_returns_none_when_unreachable() -> None:
    # §7.2: a `None`/timeout result is not an error at the port level.
    fake_empty = FakeWorldModelPort(None)
    real_unreachable = WorldModelClient(FakeEventPublisher())  # nothing registered -> timeout
    assert await fake_empty.get_context(user_id=uuid4()) is None
    assert await real_unreachable.get_context(user_id=uuid4()) is None


# --- PersonalContextPort -------------------------------------------------------

_PERSONAL_CONTEXT_USER_ID = uuid4()

_PERSONAL_CONTEXT_PORTS: list[tuple[str, Callable[[], PersonalContextPort]]] = [
    (
        "fake",
        lambda: FakePersonalContextPort(
            PersonalContext(user_id=_PERSONAL_CONTEXT_USER_ID, objective="ship it")
        ),
    ),
    (
        "real",
        lambda: PersonalContextClient(
            FakeWorldModelPort(
                WorldModelSnapshot(user_id=_PERSONAL_CONTEXT_USER_ID, objective="ship it")
            )
        ),
    ),
]


@_params(_PERSONAL_CONTEXT_PORTS)
async def test_personal_context_port_returns_projected_context(
    factory: Callable[[], PersonalContextPort],
) -> None:
    port = factory()
    context = await port.get_personal_context(user_id=_PERSONAL_CONTEXT_USER_ID)
    assert context is not None
    assert context.objective == "ship it"


# --- GoalsPort -------------------------------------------------------------
#
# TDD 3E §8: `GoalsClient` now calls a real `planning.goals.current.request`
# RPC. `[]` is still a legitimate, shared behavior for both implementations
# in this one scenario -- `FakeGoalsPort()` defaults to no configured goals,
# and `GoalsClient` degrades to `[]` on a timeout (nothing registered on the
# `FakeEventPublisher`) -- but for different reasons, not because the port
# is a placeholder any more.

_GOALS_PORTS: list[tuple[str, Callable[[], GoalsPort]]] = [
    ("fake", lambda: FakeGoalsPort()),
    ("real", lambda: GoalsClient(FakeEventPublisher())),
]


@_params(_GOALS_PORTS)
async def test_goals_port_returns_empty_when_no_goals_are_available(
    factory: Callable[[], GoalsPort],
) -> None:
    port = factory()
    assert await port.current_goals(user_id=uuid4()) == []


# --- ModelOrchestrationPort ------------------------------------------------


def _make_real_model_orchestration_port() -> ModelOrchestrationPort:
    publisher = FakeEventPublisher()
    publisher.register(
        "ai_model.generate.request",
        lambda _req: GenerateReplyPayload(
            text="hello", input_tokens=1, output_tokens=1, finish_reason="stop",
            structural_confidence=1.0, model_id=uuid4(), provider="fake",
        ),
    )
    return ModelOrchestrationClient(publisher)


_MODEL_ORCHESTRATION_PORTS: list[tuple[str, Callable[[], ModelOrchestrationPort]]] = [
    ("fake", lambda: FakeModelOrchestrationPort()),
    ("real", _make_real_model_orchestration_port),
]


@_params(_MODEL_ORCHESTRATION_PORTS)
async def test_model_orchestration_port_generate_returns_well_formed_reply(
    factory: Callable[[], ModelOrchestrationPort],
) -> None:
    from nova_contracts import GenerateRequestPayload

    port = factory()
    reply = await port.generate(
        GenerateRequestPayload(context=[], requesting_engine="test", correlation_id=uuid4())
    )
    assert isinstance(reply.text, str) and reply.text
    assert reply.finish_reason in {"stop", "length", "tool_calls", "error"}
