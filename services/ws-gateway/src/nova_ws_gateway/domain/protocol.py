"""The public WebSocket protocol, and the topic allow-list behind it.

Two properties this module exists to hold:

**The browser can only name a topic from a fixed list.** `PUBLIC_TOPICS` is
an allow-list, not a pattern language: a client cannot subscribe to `>` , to
`*`, or to an internal RPC subject, because those strings are not in the
set. Doc 09 §6 makes `ws-gateway` the only component permitted to bridge bus
subjects to a browser, and an arbitrary-subscription endpoint would hand that
privilege straight back to the client.

**Bus internals stay off the wire.** A frame carries the topic, the payload,
and doc 11 §4's `meta` -- nothing else. `causation_id` is internal event
chaining and `source_engine` is internal topology; neither is anything a
panel should couple to, and Part 4's "departments never communicate directly
with the user" is easier to keep true if the wire format cannot express them.

The frame reuses doc 11 §4's `{data, meta, error}` envelope deliberately, so
the web client's data layer sees one convention across both transports
rather than two.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from nova_contracts import EventEnvelope
from pydantic import BaseModel, Field, ValidationError

#: Every topic a browser may name in 4A. Extended per milestone; see
#: `events/subscribed.py` for the matching bus-side declaration.
#:
#: Every entry is a subject some engine's own `events/published.py` actually
#: declares, asserted by `test_every_public_topic_is_actually_published`.
#: The first draft of this list did not hold that property: it named
#: `communication.intent.delivered`, `perception.identity.present` and
#: `personality.style.selected`, and **none of the three existed**. Only the
#: first was made real (4A added it to communication-engine, because without
#: it the Conversation panel had no source for NOVA's replies at all); the
#: published identity subject is `perception.identity.observed`; and
#: personality-engine broadcasts nothing -- `personality.style.select` is a
#: request/reply RPC whose reply goes to one caller and is not subscribable.
#:
#: A dead topic is not harmless here: the client subscribes successfully and
#: then waits forever. The original prefix-only test passed against all
#: three, which is why the guard is now a publication check.
PUBLIC_TOPICS: frozenset[str] = frozenset(
    {
        # Conversation panel -- both halves of the exchange.
        "communication.turn.received",
        "communication.intent.delivered",
        "communication.session.created",
        "communication.session.state_changed",
        "communication.session.completed",
        # Presence/identity indicator.
        "perception.identity.observed",
        "perception.presence.observed",
        # System Pulse (doc 04 §4).
        "nova.heartbeat",
        # --- Phase 4B observability panels --------------------------------
        # Every entry below was checked against the publishing engine's own
        # `events/published.py` before being added, because this list's
        # failure mode is silent: a client subscribes to a dead topic
        # successfully and then waits forever.
        #
        # Planning panel -- planning-engine.
        "planning.task_graph.created",
        # Reasoning Trace panel -- reasoning-engine.
        "reasoning.process.completed",
        "reasoning.process.failed",
        "reasoning.human_override.applied",
        # Approvals panel -- action-engine.
        "action.approval.requested",
        "action.approval.decided",
        # Health panel -- nova-core and ai-model-orchestration-engine.
        "nova.module.status_changed",
        "ai_model.model.health_changed",
        "perception.sensor.health_changed",
        #
        # The Capabilities panel has no entry on purpose: capability-engine
        # publishes no domain events at all, only outbound RPC requests. It
        # is REST-only, and inventing a subject to make the panel symmetric
        # would put a dead topic back on this list.
    }
)


class FrameMeta(BaseModel):
    """Doc 11 §4's `meta`, carried unchanged onto the WebSocket."""

    correlation_id: str
    generated_at: datetime
    confidence: float | None = None


class FrameError(BaseModel):
    code: str
    message: str


class EventFrame(BaseModel):
    type: Literal["event"] = "event"
    topic: str
    data: dict[str, Any]
    meta: FrameMeta
    error: None = None


class ControlFrame(BaseModel):
    """Acknowledgements and errors. Never carries engine data."""

    type: Literal["ready", "subscribed", "unsubscribed", "error"]
    topics: list[str] = Field(default_factory=list)
    error: FrameError | None = None


class ClientMessage(BaseModel):
    action: Literal["subscribe", "unsubscribe"]
    topics: list[str] = Field(min_length=1, max_length=64)


class MalformedClientMessage(ValueError):
    """The client sent something that is not a valid protocol message."""


def parse_client_message(raw: str) -> ClientMessage:
    try:
        return ClientMessage.model_validate_json(raw)
    except ValidationError as exc:
        raise MalformedClientMessage(str(exc)) from exc


def partition_topics(topics: list[str]) -> tuple[list[str], list[str]]:
    """Split a requested set into (allowed, rejected), order-preserving."""
    allowed: list[str] = []
    rejected: list[str] = []
    for topic in topics:
        (allowed if topic in PUBLIC_TOPICS else rejected).append(topic)
    return allowed, rejected


def to_event_frame(envelope: EventEnvelope) -> EventFrame:
    """Project a bus envelope onto the public frame.

    `correlation_id` and `occurred_at` come from the source event rather than
    being regenerated here -- a frame that minted its own would break the
    trace back through the event chain that produced it, which is exactly
    what doc 11 §4 surfaces `correlation_id` to preserve.

    `confidence` is copied only when the source event carries one. It is
    never defaulted or inferred.
    """
    return EventFrame(
        topic=envelope.subject,
        data=dict(envelope.payload),
        meta=FrameMeta(
            correlation_id=str(envelope.correlation_id),
            generated_at=envelope.occurred_at,
            confidence=envelope.confidence,
        ),
    )


def error_frame(code: str, message: str) -> ControlFrame:
    return ControlFrame(type="error", error=FrameError(code=code, message=message))


def ready_frame(topics: list[str]) -> ControlFrame:
    return ControlFrame(type="ready", topics=sorted(topics))


def now() -> datetime:
    return datetime.now(UTC)
