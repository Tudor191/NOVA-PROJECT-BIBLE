from uuid import uuid4

import pytest
from nova_contracts import EventEnvelope
from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus
from nova_eventbus_sdk.boundary import BoundEventBus, SubjectNotAllowedError


async def _bound_bus(*, publishable: frozenset[str], subscribable: frozenset[str]) -> BoundEventBus:
    inner = InMemoryEventBus()
    await inner.connect()
    return BoundEventBus(
        inner,
        engine_name="memory-engine",
        publishable_subjects=publishable,
        subscribable_subjects=subscribable,
    )


async def test_publish_outside_allow_list_is_rejected() -> None:
    bus = await _bound_bus(publishable=frozenset({"memory.*.created"}), subscribable=frozenset())
    with pytest.raises(SubjectNotAllowedError):
        await bus.publish(
            EventEnvelope(
                subject="action.execute", source_engine="memory-engine", correlation_id=uuid4()
            )
        )


async def test_publish_within_allow_list_succeeds() -> None:
    bus = await _bound_bus(publishable=frozenset({"memory.*.created"}), subscribable=frozenset())
    await bus.publish(
        EventEnvelope(
            subject="memory.episodic.created", source_engine="memory-engine", correlation_id=uuid4()
        )
    )  # should not raise


async def test_subscribe_outside_allow_list_is_rejected() -> None:
    bus = await _bound_bus(publishable=frozenset(), subscribable=frozenset({"world_model.*"}))

    async def handler(envelope: EventEnvelope) -> None:
        pass

    with pytest.raises(SubjectNotAllowedError):
        await bus.subscribe("knowledge.node.created", handler)


async def test_subscribe_within_allow_list_succeeds() -> None:
    bus = await _bound_bus(publishable=frozenset(), subscribable=frozenset({"world_model.*"}))

    async def handler(envelope: EventEnvelope) -> None:
        pass

    await bus.subscribe("world_model.object.created", handler)  # should not raise
