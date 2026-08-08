"""Closes the previously-unwired communication-engine <-> reasoning-engine
conversation loop (docs/design/phase-2d/05-conversation-intelligence-closure.md
Sec5, Priority 3, Fork #1 -- user-approved synchronous RPC design):

    communication.turn.received
    -> communication-engine (this module)
    -> reasoning-engine (`reasoning.reason.request`, synchronous RPC)
    -> reasoning result
    -> communication-engine (this module)
    -> intent gate (`events.handlers.deliver_content_to_session`)
    -> communication.intent.deliver.request's own delivery logic, reused
       in-process rather than re-issued as a redundant same-engine RPC
    -> response delivery

Lives outside `domain/` -- like `session_registry.py`, it needs `app.state`
(FastAPI) and the live `SessionRegistry`, which `domain/` may never import
(`domain/ports.py`'s own docstring). `handle_conversation_turn` is a plain,
directly-awaitable async function (so tests can call it synchronously and
assert its outcome); `schedule_conversation_turn` is the production entry
point, run as a detached `asyncio.Task` so a slow reasoning call never
blocks the WebSocket read loop or an HTTP request/response cycle -- exactly
the "acknowledgment now, answer delivered later over whatever channel
connection is live" behavior `api/sessions.py`'s own `send_message`
docstring already documented before this loop existed to fulfill it.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import FastAPI
from nova_observability import get_logger

from nova_communication_engine.domain.addressee_fusion import confidence_tier_label
from nova_communication_engine.domain.intent_gate import IntentDeliveryOutcome
from nova_communication_engine.events.handlers import deliver_content_to_session

__all__ = ["handle_conversation_turn", "schedule_conversation_turn"]

logger = get_logger("communication-engine.conversation_orchestration")

_background_tasks: set[asyncio.Task[None]] = set()
"""A strong reference to every in-flight `schedule_conversation_turn` task
until it completes. `asyncio`'s own docs warn the event loop holds only a
weak reference to a task -- without this, a task can be garbage-collected
mid-flight, silently dropping a turn's reasoning call before it finishes.
Each task removes itself on completion via `add_done_callback`."""

FALLBACK_CONTENT = (
    "I'm having trouble thinking that through right now -- could you try again in a moment?"
)
"""A short, honest fallback (Doc 22 Principle 3: never block/silently drop
delivery on a downstream failure) -- routed through the same intent gate
and `personality.validate_response` check as any other content, not a
mechanical transport notice, because how NOVA describes its own failure to
think is itself a personality-consistency concern (the five permanent
directives' "Personality Consistency"), unlike `api/websocket.py`'s
transcribe-failure notice, which bypasses the gate because it is not
generated content at all."""


async def handle_conversation_turn(
    app: FastAPI, *, session_id: UUID, user_id: UUID, content: str, correlation_id: UUID
) -> IntentDeliveryOutcome | None:
    """Directly awaitable -- call this from tests. `schedule_conversation_turn`
    wraps it for production, non-blocking use.

    Reasoning failure/timeout, a non-`decided` outcome, and a `decided`
    outcome with no `chosen_description` (a malformed/empty reply) all
    collapse to the same honest fallback path -- there is no case where this
    function fabricates content reasoning-engine did not actually produce.

    Returns `None` only when the session no longer exists by the time
    reasoning returns (e.g. it was closed while this ran in the
    background) -- there is nothing left to deliver to."""
    state = app.state
    try:
        result = await state.reasoning_port.reason(
            objective_text=content, user_id=user_id, correlation_id=correlation_id
        )
    except TimeoutError:
        result = None

    if result is not None and result.outcome == "decided" and result.content:
        response_content = result.content
        # Doc 22 Principle 7: reasoning conclusions and identity confidence
        # share the same four-tier Confidence Expression vocabulary --
        # `confidence_tier_label` already implements it for addressee
        # fusion; reused verbatim here rather than re-deriving the same
        # thresholds a second time.
        confidence_tier = confidence_tier_label(result.confidence_score or 0.0)
    else:
        response_content = FALLBACK_CONTENT
        confidence_tier = "unknown"

    session = await state.repository.get_session(session_id)
    if session is None:
        logger.warning(
            "conversation_turn_session_gone_before_delivery", extra={"session_id": str(session_id)}
        )
        return None

    return await deliver_content_to_session(
        app,
        session=session,
        content=response_content,
        confidence_tier=confidence_tier,
        correlation_id=correlation_id,
    )


def schedule_conversation_turn(
    app: FastAPI, *, session_id: UUID, user_id: UUID, content: str, correlation_id: UUID
) -> None:
    """Fire-and-forget entry point for the real API call sites
    (`api/websocket.py`, `api/sessions.py`) -- never awaited by the request/
    connection loop that calls it, so a slow reasoning call cannot stall
    inbound message processing (barge-in, `TRIGGER_STOP`, further audio
    chunks). Catches every exception at this outermost boundary and logs it:
    a detached `asyncio.Task`'s exception is otherwise silently discarded,
    which would turn a real bug into an invisible one."""

    async def _run() -> None:
        try:
            await handle_conversation_turn(
                app,
                session_id=session_id,
                user_id=user_id,
                content=content,
                correlation_id=correlation_id,
            )
        except Exception:
            logger.exception(
                "conversation_turn_orchestration_failed", extra={"session_id": str(session_id)}
            )

    task = asyncio.create_task(_run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
