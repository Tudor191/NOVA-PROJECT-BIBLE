"""Event Bus subscription handlers -- docs/design/phase-1/03-world-model-engine.md
§13.

Per docs/design/phase-1/04-cross-engine-integration.md, Planning and Agent OS
don't exist yet -- `make_mode_changed_handler`/`make_agent_os_task_handler`
remain honest no-ops, contracts this engine is ready to serve, exercised today
by a synthetic/test-published event, not a live upstream producer (§13's
"shifts Attention Model weighting" gives one worked example but no general
formula, and inventing one would be exactly the speculative behavior this
project's standing instructions rule out).

`perception-engine` (Phase 2D-B) is this engine's first *real* Perception
producer -- `make_perception_dispatch_handler` is the single handler
registered against the `perception.*.observed` wildcard subscription
(`main.py`), routing each event by its exact subject rather than assuming
every match is object-shaped:

- `perception.presence.observed` / `perception.identity.observed` ->
  `ActiveContext.present_identities` (docs/design/phase-2d/
  03-perception-engine.md §0.6) -- `make_perception_presence_observed_handler`/
  `make_perception_identity_observed_handler`, both real effects via
  `domain/context.py`'s `clear_present_identities`/`upsert_present_identity`.
- anything else (object-shaped: window, file, project handles -- Phase 4's
  `nova-companion` desktop sensors) -> `make_perception_observed_handler`'s
  original object-graph path, unchanged since Phase 1.

Both are wired against a single wildcard subscription, not two competing
subscriptions to overlapping subjects -- NATS would otherwise deliver the same
message to two independent handlers, double-processing it.
"""

from __future__ import annotations

from uuid import UUID

from nova_contracts import EventEnvelope
from nova_observability import get_logger

from nova_world_model_engine.domain import context, object_graph, state_management, temporal
from nova_world_model_engine.domain.models import ObjectState, PresentIdentitySignal, WorldObject
from nova_world_model_engine.domain.ports import ContextRepository, WorldHistoryRepository

logger = get_logger("world-model-engine.events.handlers")

_PRESENCE_SUBJECTS = frozenset({"perception.presence.observed", "perception.identity.observed"})


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


def _float_from(payload: dict, key: str, *, default: float = 0.0) -> float:
    value = payload.get(key)
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


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


def make_perception_presence_observed_handler(  # type: ignore[no-untyped-def]
    context_repo: ContextRepository, history_repo: WorldHistoryRepository
):
    """`perception.presence.observed` (docs/design/phase-2d/
    03-perception-engine.md §13.2) -> `ActiveContext.present_identities` (§0.6).
    Only acts on `present=False` (presence lost): clears the roster, since
    World Model represents current reality only (ADR-017) and a stale
    "still present" entry after presence is lost would be exactly that kind
    of fabricated state. `present=True` alone carries no identity opinion --
    `perception.identity.observed` (below) is what actually populates the
    roster, so a bare presence-detected event is a deliberate no-op here."""

    async def handle(envelope: EventEnvelope) -> None:
        user_id = _uuid_from(envelope.payload, "user_id")
        present = envelope.payload.get("present")
        if user_id is None or not isinstance(present, bool):
            logger.warning(
                "perception.presence.observed missing user_id/present, skipping",
                extra={"subject": envelope.subject},
            )
            return
        if present:
            return  # no identity opinion carried by a bare presence signal
        await context.clear_present_identities(
            context_repo, history_repo, user_id=user_id, correlation_id=envelope.correlation_id
        )

    return handle


def make_perception_identity_observed_handler(  # type: ignore[no-untyped-def]
    context_repo: ContextRepository, history_repo: WorldHistoryRepository
):
    """`perception.identity.observed` (docs/design/phase-2d/
    03-perception-engine.md §13.2) -> `ActiveContext.present_identities`
    (§0.6). A direct pass-through of `perception-engine`'s own fused/smoothed
    identity signal (§8 of that document) -- this engine neither re-scores nor
    re-interprets the confidence value, per ADR-017's boundary against
    becoming a second identity-fusion engine."""

    async def handle(envelope: EventEnvelope) -> None:
        user_id = _uuid_from(envelope.payload, "user_id")
        confidence = envelope.payload.get("confidence")
        modality_summary = _text_from(envelope.payload, "modality_summary") or "unknown"
        if user_id is None or confidence is None:
            logger.warning(
                "perception.identity.observed missing user_id/confidence, skipping",
                extra={"subject": envelope.subject},
            )
            return
        identity_id = _uuid_from(envelope.payload, "identity_id")
        signal = PresentIdentitySignal(
            identity_id=identity_id,
            confidence=_float_from(envelope.payload, "confidence"),
            modality_summary=modality_summary,
        )
        await context.upsert_present_identity(
            context_repo,
            history_repo,
            user_id=user_id,
            identity=signal,
            correlation_id=envelope.correlation_id,
        )

    return handle


def make_perception_dispatch_handler(  # type: ignore[no-untyped-def]
    context_repo: ContextRepository, history_repo: WorldHistoryRepository
):
    """The single handler registered against the `perception.*.observed`
    wildcard subscription (`main.py`) -- routes by exact subject rather than
    assuming every match is object-shaped, per this module's own docstring.
    `perception-engine` (Phase 2D-B) never publishes an object-shaped
    `perception.*.observed` payload (that path is reserved for Phase 4's
    desktop-sensor extension), but this dispatcher makes the split explicit
    and mechanical rather than relying on that convention holding by
    convention alone."""

    presence_handler = make_perception_presence_observed_handler(context_repo, history_repo)
    identity_handler = make_perception_identity_observed_handler(context_repo, history_repo)
    object_handler = make_perception_observed_handler(history_repo)

    async def handle(envelope: EventEnvelope) -> None:
        if envelope.subject == "perception.presence.observed":
            await presence_handler(envelope)
        elif envelope.subject == "perception.identity.observed":
            await identity_handler(envelope)
        else:
            await object_handler(envelope)

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
