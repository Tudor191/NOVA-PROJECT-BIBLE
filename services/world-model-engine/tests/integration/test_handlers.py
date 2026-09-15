"""`events/handlers.py` -- exercises the real "Object write path" (§3) against
`FakeWorldHistoryRepository`, driven by synthetic events (no live Perception
Engine exists yet, per docs/design/phase-1/04-cross-engine-integration.md).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from nova_contracts import EventEnvelope
from nova_world_model_engine.events.handlers import (
    make_action_result_handler,
    make_perception_dispatch_handler,
    make_perception_observed_handler,
)

from tests.fakes.context_repository import FakeContextRepository
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


# --- perception-engine dispatch (docs/design/phase-2d/03-perception-engine.md
# §0.6, §13.2) -- the single handler behind the `perception.*.observed`
# wildcard, routing presence/identity to Active Context and everything else
# to the pre-existing object-graph path. -------------------------------------


async def test_dispatch_routes_identity_observed_to_present_identities() -> None:
    context_repo = FakeContextRepository()
    history_repo = FakeWorldHistoryRepository()
    handler = make_perception_dispatch_handler(context_repo, history_repo)
    user_id = uuid4()
    identity_id = uuid4()

    await handler(
        _envelope(
            "perception.identity.observed",
            {
                "user_id": str(user_id),
                "identity_id": str(identity_id),
                "confidence": 0.9,
                "modality_summary": "voice+face",
            },
        )
    )

    context = await context_repo.get_context(user_id)
    assert context is not None
    assert len(context.present_identities) == 1
    assert context.present_identities[0].identity_id == identity_id
    assert history_repo.history == []  # never touches the object-graph path


async def test_dispatch_routes_presence_lost_to_clear_present_identities() -> None:
    context_repo = FakeContextRepository()
    history_repo = FakeWorldHistoryRepository()
    handler = make_perception_dispatch_handler(context_repo, history_repo)
    user_id = uuid4()

    await handler(
        _envelope(
            "perception.identity.observed",
            {
                "user_id": str(user_id),
                "identity_id": str(uuid4()),
                "confidence": 0.9,
                "modality_summary": "voice",
            },
        )
    )
    await handler(
        _envelope("perception.presence.observed", {"user_id": str(user_id), "present": False})
    )

    context = await context_repo.get_context(user_id)
    assert context is not None
    assert context.present_identities == []


async def test_dispatch_ignores_bare_presence_detected_signal() -> None:
    context_repo = FakeContextRepository()
    history_repo = FakeWorldHistoryRepository()
    handler = make_perception_dispatch_handler(context_repo, history_repo)
    user_id = uuid4()

    await handler(
        _envelope("perception.presence.observed", {"user_id": str(user_id), "present": True})
    )

    assert await context_repo.get_context(user_id) is None


async def test_dispatch_routes_object_shaped_events_to_object_graph_path() -> None:
    context_repo = FakeContextRepository()
    history_repo = FakeWorldHistoryRepository()
    handler = make_perception_dispatch_handler(context_repo, history_repo)
    user_id = uuid4()

    await handler(
        _envelope(
            "perception.window.observed",
            {"object_id": "window:1", "label": "Window", "user_id": str(user_id)},
        )
    )

    history = await history_repo.list_object_history("window:1")
    assert len(history) == 1
    assert await context_repo.get_context(user_id) is None


# --- Phase 4F.2: perception.workspace.observed, with zero changes here ----
#
# These are **test-only additions**. No production file in this engine changed
# for 4F.2: the subject matches the `perception.*.observed` wildcard this
# engine has subscribed to since Phase 1, the dispatcher's `else` branch
# already routes it to the object handler, and that handler already reads the
# three fields the payload supplies. These tests exist to prove that claim
# rather than assert it -- if a later edit breaks the fit, it fails here.
#
# The payload is built from the registered `nova-contracts` model, not a
# hand-written dict, so a contract change cannot drift away from what this
# engine is tested against. `perception-engine` is deliberately not imported:
# the contract is the shared dependency, not the producer.


def _workspace_payload(**overrides) -> dict:
    from nova_contracts import PerceptionWorkspaceObservedPayload

    fields = {
        "object_id": "ws-" + "b" * 64,
        "label": "notes.md",
        "user_id": uuid4(),
        "object_type": "project",
        "sensor_id": "companion-filesystem",
        "observed_at": datetime.now(UTC),
    }
    fields.update(overrides)
    return PerceptionWorkspaceObservedPayload(**fields).model_dump(mode="json")


async def test_4f2_workspace_observed_reaches_the_object_path_through_the_dispatcher() -> None:
    """The routing claim, end to end through the real dispatcher: a one-segment
    `perception.workspace.observed` falls through the `else` branch to the
    object handler, exactly as §20.2 says it does."""
    context_repo = FakeContextRepository()
    history_repo = FakeWorldHistoryRepository()
    handler = make_perception_dispatch_handler(context_repo, history_repo)
    payload = _workspace_payload()

    await handler(_envelope("perception.workspace.observed", payload))

    history = await history_repo.list_object_history(payload["object_id"])
    assert len(history) == 1
    assert history[0].new_state.value == "active"
    assert history[0].previous_state is None


async def test_4f2_a_second_workspace_observation_moves_idle_to_active() -> None:
    """The `Idle -> Active` transition on a re-observation, which only works
    because `object_id` is a *stable* hash of the same path."""
    from nova_world_model_engine.domain.models import ObjectState, ObjectStateHistoryEntry

    context_repo = FakeContextRepository()
    history_repo = FakeWorldHistoryRepository()
    handler = make_perception_dispatch_handler(context_repo, history_repo)
    payload = _workspace_payload()

    await handler(_envelope("perception.workspace.observed", payload))
    await history_repo.append_object_history(
        ObjectStateHistoryEntry(
            object_id=payload["object_id"],
            object_label=payload["label"],
            user_id=UUID(payload["user_id"]),
            previous_state=ObjectState.ACTIVE,
            new_state=ObjectState.IDLE,
        )
    )
    await handler(_envelope("perception.workspace.observed", payload))

    # `list_object_history` returns newest first.
    newest = (await history_repo.list_object_history(payload["object_id"]))[0]
    assert newest.new_state is ObjectState.ACTIVE
    assert newest.previous_state is ObjectState.IDLE


async def test_4f2_the_extra_ratified_fields_are_ignored_without_error() -> None:
    """`sensor_id`, `observed_at`, `object_type` and `project_id` mean nothing
    to this engine. The handler reads its payload by key, so they are ignored
    -- but "ignored" has to be demonstrated, not assumed, because the
    alternative failure mode is a skipped event and a log line."""
    context_repo = FakeContextRepository()
    history_repo = FakeWorldHistoryRepository()
    handler = make_perception_dispatch_handler(context_repo, history_repo)
    payload = _workspace_payload(project_id=uuid4())

    assert {"sensor_id", "observed_at", "object_type", "project_id"} <= set(payload)
    await handler(_envelope("perception.workspace.observed", payload))
    assert len(await history_repo.list_object_history(payload["object_id"])) == 1


async def test_4f2_a_workspace_event_does_not_touch_present_identities() -> None:
    """The dispatcher must not route an object-shaped event into the identity
    path. Presence and identity remain the only two subjects that do."""
    context_repo = FakeContextRepository()
    history_repo = FakeWorldHistoryRepository()
    handler = make_perception_dispatch_handler(context_repo, history_repo)

    await handler(_envelope("perception.workspace.observed", _workspace_payload()))

    assert context_repo.contexts == {}
