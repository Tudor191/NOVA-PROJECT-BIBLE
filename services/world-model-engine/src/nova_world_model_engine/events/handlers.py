"""Event Bus subscription handlers -- docs/design/phase-1/03-world-model-engine.md
§13.

Per docs/design/phase-1/04-cross-engine-integration.md, Perception, Planning,
and Agent OS don't exist yet in Phase 1 -- these handlers are contracts this
engine is ready to serve, exercised today by a synthetic/test-published event,
not a live upstream producer (mirroring Memory/Knowledge Engine's own
`events/handlers.py`, same rationale).

`make_perception_observed_handler` and `make_action_result_handler` implement
real effects (an object state transition via `object_graph.observe_object`),
not placeholders -- §3's "Object write path" sequence diagram is concrete
enough to implement against even without a finalized upstream payload schema.
`make_mode_changed_handler` and `make_agent_os_task_handler` are honest
no-ops: §13's "shifts Attention Model weighting" gives one worked example
(Part 6: "if gaming begins, performance monitoring becomes dominant") but no
general formula, and inventing one would be exactly the speculative behavior
this project's standing instructions rule out.
"""

from __future__ import annotations

from uuid import UUID

from nova_contracts import EventEnvelope
from nova_observability import get_logger

from nova_world_model_engine.domain import object_graph, state_management, temporal
from nova_world_model_engine.domain.models import ObjectState, WorldObject
from nova_world_model_engine.domain.ports import WorldHistoryRepository

logger = get_logger("world-model-engine.events.handlers")


def _text_from(payload: dict, *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _uuid_from(payload: dict, key: str) -> UUID | None:
    value = payload.get(key)
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


async def _current_state(history_repo: WorldHistoryRepository, object_id: str) -> ObjectState:
    recent = await temporal.object_history(history_repo, object_id, limit=1)
    return recent[0].new_state if recent else ObjectState.UNKNOWN


def make_perception_observed_handler(history_repo: WorldHistoryRepository):  # type: ignore[no-untyped-def]
    """"Object write path" (§3): a perception observation about an entity
    (window, file, project, ...) either creates it (first observation) or
    moves it `Idle -> Active` (a new observation on an already-known object).
    Deliberately does not attempt multi-modal *fusion* (Active Context
    updates) here -- that needs correlation-window batching across multiple
    concurrent signals, a genuinely different mechanism from a single-event
    handler (see `domain/fusion.py`'s module docstring)."""

    async def handle(envelope: EventEnvelope) -> None:
        object_id = _text_from(envelope.payload, "object_id", "entity_id")
        label = _text_from(envelope.payload, "label", "object_label") or "Unknown"
        user_id = _uuid_from(envelope.payload, "user_id")
        if object_id is None or user_id is None:
            logger.warning(
                "perception.*.observed missing object_id/user_id, skipping",
                extra={"subject": envelope.subject},
            )
            return

        current = await _current_state(history_repo, object_id)
        next_state = (
            state_management.next_state_on_first_observation(current)
            if current is ObjectState.UNKNOWN
            else state_management.next_state_on_new_observation(current)
        )
        if next_state is None:
            return  # no defined transition (e.g. already ACTIVE) -- not an error

        obj = WorldObject(object_id=object_id, label=label, user_id=user_id, state=next_state)
        previous = None if current is ObjectState.UNKNOWN else current
        await object_graph.observe_object(
            history_repo, obj=obj, previous_state=previous, correlation_id=envelope.correlation_id
        )

    return handle


def make_action_result_handler(history_repo: WorldHistoryRepository):  # type: ignore[no-untyped-def]
    """"object state updates from completed actions" (§13) -- only acts when
    the object is currently `EXECUTING` (§6's diagram has no other state this
    event is meaningful for)."""

    async def handle(envelope: EventEnvelope) -> None:
        object_id = _text_from(envelope.payload, "object_id", "entity_id")
        label = _text_from(envelope.payload, "label", "object_label") or "Task"
        user_id = _uuid_from(envelope.payload, "user_id")
        outcome = _text_from(envelope.payload, "outcome")
        if object_id is None or user_id is None or outcome not in ("success", "error", "blocked"):
            logger.warning(
                "action.result missing object_id/user_id/valid outcome, skipping",
                extra={"subject": envelope.subject},
            )
            return

        current = await _current_state(history_repo, object_id)
        next_state = state_management.next_state_on_execution_result(
            current, outcome=outcome  # type: ignore[arg-type]
        )
        if next_state is None:
            return

        obj = WorldObject(object_id=object_id, label=label, user_id=user_id, state=next_state)
        await object_graph.observe_object(
            history_repo,
            obj=obj,
            previous_state=current,
            correlation_id=envelope.correlation_id,
        )

    return handle


def make_mode_changed_handler():  # type: ignore[no-untyped-def]
    """"shifts Attention Model weighting" (§13, Part 6). No general weighting
    formula is specified beyond one worked example -- this is an honest
    placeholder, not a guessed implementation (see module docstring)."""

    async def handle(envelope: EventEnvelope) -> None:
        logger.info(
            "nova.mode.changed received, Attention weighting shift not yet implemented",
            extra={"subject": envelope.subject},
        )

    return handle


def make_agent_os_task_handler():  # type: ignore[no-untyped-def]
    """§13: "Phase 3+, no-op subscription registered now.\""""

    async def handle(envelope: EventEnvelope) -> None:
        logger.info(
            "agent_os.task.* received, no-op in Phase 1", extra={"subject": envelope.subject}
        )

    return handle
