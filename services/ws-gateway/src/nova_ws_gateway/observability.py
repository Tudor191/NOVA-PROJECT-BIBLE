"""Observability instruments for `ws-gateway` (SAD 15 §9.1 item 10).

`create_metrics()` follows every other engine's `observability.py`
convention: it must only be called after `configure_observability()` has
run, and `domain/` never imports this module -- `api/stream.py` reads the
instruments off `app.state.metrics`.

**Every label is bounded.** A topic a client *names* is arbitrary text and is
never a label; a topic is labeled only once it is a member of
`PUBLIC_TOPICS` (eighteen subjects), and anything else is `"other"`.
`outcome` labels draw from the fixed sets below.
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_observability import get_meter
from opentelemetry.metrics import Counter, UpDownCounter

from nova_ws_gateway.domain.protocol import PUBLIC_TOPICS

__all__ = [
    "CONNECTION_OUTCOMES",
    "FRAME_OUTCOMES",
    "MESSAGE_OUTCOMES",
    "WsGatewayMetrics",
    "bounded_topic",
    "create_metrics",
]

#: `ws_gateway_connections_total`'s `outcome`.
CONNECTION_OUTCOMES: frozenset[str] = frozenset({"accepted", "unauthenticated"})

#: `ws_gateway_client_messages_total`'s `outcome`. A message naming both
#: allowed and refused topics counts once as `topic_not_allowed` and once
#: as its action, exactly as the client is answered twice.
MESSAGE_OUTCOMES: frozenset[str] = frozenset(
    {"subscribe", "unsubscribe", "malformed", "topic_not_allowed"}
)

#: `ws_gateway_frames_total`'s `outcome`.
FRAME_OUTCOMES: frozenset[str] = frozenset(
    {
        "queued",  # projected and queued for the client
        "dropped_slow_client",  # the client's queue was full
        "undeliverable",  # the envelope could not be projected or encoded
    }
)


def bounded_topic(subject: str) -> str:
    """`subject` when it is a public topic, else `"other"`."""
    return subject if subject in PUBLIC_TOPICS else "other"


@dataclass(frozen=True)
class WsGatewayMetrics:
    connections_total: Counter
    """Handshakes, labeled by `outcome` (`accepted` / `unauthenticated`)."""

    open_connections: UpDownCounter
    """Connections currently open."""

    client_messages_total: Counter
    """Client control messages, labeled by `outcome`."""

    frames_total: Counter
    """Bus events reaching a connection, labeled by `topic` and `outcome`.
    `dropped_slow_client` rising is the back-pressure signal."""

    bus_subscribe_refused_total: Counter
    """A public topic the bus-side allow-list refused, labeled by `topic` --
    a configuration bug in this service, never a client error."""


def create_metrics() -> WsGatewayMetrics:
    meter = get_meter("ws-gateway")
    return WsGatewayMetrics(
        connections_total=meter.create_counter(
            "ws_gateway_connections_total",
            description="WebSocket handshakes, labeled by outcome.",
        ),
        open_connections=meter.create_up_down_counter(
            "ws_gateway_open_connections",
            description="WebSocket connections currently open.",
        ),
        client_messages_total=meter.create_counter(
            "ws_gateway_client_messages_total",
            description="Client control messages, labeled by outcome.",
        ),
        frames_total=meter.create_counter(
            "ws_gateway_frames_total",
            description="Bus events reaching a connection, labeled by topic and outcome.",
        ),
        bus_subscribe_refused_total=meter.create_counter(
            "ws_gateway_bus_subscribe_refused_total",
            description="Public topics refused by the bus-side allow-list, labeled by topic.",
        ),
    )
