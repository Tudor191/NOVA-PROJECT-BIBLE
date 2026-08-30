"""Every subject Supervisors is permitted to publish/request against.

`reasoning.reason.request` is live and real (`reasoning-engine`'s own,
already-shipped RPC). `agent_os.instance.*.inbox` is the real wire shape
of doc 12 §10's Agent Mailbox, declared as a glob (`nova_eventbus_sdk.
BoundEventBus`'s existing fnmatch-based allow-list support, the same
convention `agent-os/kernel`'s own `events/subscribed.py` docstring
already documents for the receiving side) -- but has no live receiver yet;
see `domain/ports.py`'s own disclosure."""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "reasoning.reason.request",
        "agent_os.instance.*.inbox",
    }
)
