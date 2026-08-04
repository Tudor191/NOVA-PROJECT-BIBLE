"""`events/handlers.py` -- exercises the real "Object write path" (§3) against
`FakeWorldHistoryRepository`, driven by synthetic events (no live Perception
Engine exists yet, per docs/design/phase-1/04-cross-engine-integration.md).
"""

from uuid import uuid4

from nova_contracts import EventEnvelope
from nova_world_model_engine.events.handlers import (
    make_action_result_handler,
    make_perception_observed_handler,
)

from tests.fakes.history_repository import FakeWorldHistoryRepository


def _envelope(subject: str, payload: dict) -> EventEnvelope:
    return EventEnvelope(
        subject=subject, source_engine="test", correlation_id=uuid4(), payload=payload
    )


async def test_perception_observed_creates_new_object() -> None:
    history_repo = FakeWorldHistoryRepository()
    handler = make_perception_observed_handler(history_repo)
    user_id = uuid4()

    await handler(
        _envelope(
            "perception.window.observed",
            {"object_id": "window:1", "label": "Window", "user_id": str(user_id)},
        )
    )

    history = await history_repo.list_object_history("window:1")
    assert len(history) == 1
    assert history[0].new_state.value == "active"
    assert history[0].previous_state is None


async def test_perception_observed_idle_object_becomes_active() -> None:
    history_repo = FakeWorldHistoryRepository()
    handler = make_perception_observed_handler(history_repo)
    user_id = uuid4()

    await handler(
        _envelope(
            "perception.window.observed",
            {"object_id": "window:1", "label": "Window", "user_id": str(user_id)},
        )
    )
    # Second observation with the object still ACTIVE (no idle timeout applied) is a no-op.
    await handler(
        _envelope(
            "perception.window.observed",
            {"object_id": "window:1", "label": "Window", "user_id": str(user_id)},
        )
    )

    history = await history_repo.list_object_history("window:1")
    assert len(history) == 1  # second observation was a no-op (already ACTIVE)


async def test_perception_observed_missing_fields_is_skipped() -> None:
    history_repo = FakeWorldHistoryRepository()
    handler = make_perception_observed_handler(history_repo)

    await handler(_envelope("perception.window.observed", {}))

    assert history_repo.history == []


async def test_action_result_completes_executing_object() -> None:
    history_repo = FakeWorldHistoryRepository()
    user_id = uuid4()
    from nova_world_model_engine.domain import object_graph
    from nova_world_model_engine.domain.models import ObjectState, WorldObject

    obj = WorldObject(
        object_id="task:1", label="Task", user_id=user_id, state=ObjectState.EXECUTING
    )
    await object_graph.observe_object(
        history_repo, obj=obj, previous_state=ObjectState.ACTIVE, correlation_id=uuid4()
    )

    handler = make_action_result_handler(history_repo)
    await handler(
        _envelope(
            "action.result",
            {"object_id": "task:1", "label": "Task", "user_id": str(user_id), "outcome": "success"},
        )
    )

    history = await history_repo.list_object_history("task:1")
    assert history[0].new_state.value == "completed"


async def test_action_result_invalid_outcome_is_skipped() -> None:
    history_repo = FakeWorldHistoryRepository()
    handler = make_action_result_handler(history_repo)

    await handler(
        _envelope(
            "action.result",
            {"object_id": "task:1", "label": "Task", "user_id": str(uuid4()), "outcome": "bogus"},
        )
    )

    assert history_repo.history == []
