"""ADR-023's compliance discipline, applied to this engine's four upstream
ports (docs/design/phase-2c/00-executive-cognition-engine.md §24): for each
port, a fake implementation and a mock-transport-backed real-client
implementation (via `FakeEventPublisher`, no real network/event-bus
dependency) must both satisfy the identical test functions. A genuine
behavioral difference (`GoalsPort`'s Phase 2C placeholder always returning
`[]`) is asserted explicitly, not silently skipped.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

import pytest
from nova_contracts import (
    ContextReplyPayload,
    MemoryRetrieveReplyPayload,
    MemorySearchResultPayload,
    MemoryType,
)
from nova_executive_cognition_engine.clients.goals_client import GoalsClient
from nova_executive_cognition_engine.clients.memory_client import MemoryClient
from nova_executive_cognition_engine.clients.personal_context_client import PersonalContextClient
from nova_executive_cognition_engine.clients.world_model_client import WorldModelClient
from nova_executive_cognition_engine.domain.models import (
    MemoryReference,
    PersonalContext,
    WorldModelSnapshot,
)
from nova_executive_cognition_engine.domain.ports import (
    GoalsPort,
    MemoryPort,
    PersonalContextPort,
    WorldModelPort,
)

from tests.fakes.event_publisher import FakeEventPublisher
from tests.fakes.ports import (
    FakeGoalsPort,
    FakeMemoryPort,
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
    # §5.5: a `None`/timeout result is not an error at the port level.
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
# §5.7: Phase 2C's honest placeholder -- both implementations return `[]`
# unconditionally (Planning Engine doesn't exist yet), asserted explicitly
# as the one legitimate behavioral identity this port has right now.

_GOALS_PORTS: list[tuple[str, Callable[[], GoalsPort]]] = [
    ("fake", lambda: FakeGoalsPort()),
    ("real", lambda: GoalsClient()),
]


@_params(_GOALS_PORTS)
async def test_goals_port_placeholder_returns_empty(factory: Callable[[], GoalsPort]) -> None:
    port = factory()
    assert await port.current_goals(user_id=uuid4()) == []
