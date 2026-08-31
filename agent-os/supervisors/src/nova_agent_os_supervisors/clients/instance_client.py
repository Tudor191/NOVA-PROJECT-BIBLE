"""`InstanceMailboxClient` -- `domain.ports.AgentInstancePort`
implementation, calling `agent_os.instance.<id>.inbox` (doc 12 §10). See
`domain/ports.py`'s own module docstring: this speaks the real wire
protocol, but nothing in this project currently subscribes on that subject
family (`agent-os/kernel`'s own `SUBSCRIBABLE_SUBJECTS` is empty as of
this milestone -- no Scheduler, no `inprocess` execution backend yet), so
every call this client makes will time out against a real Event Bus until
Kernel's own dispatch/backend exist. Not exercised by any test beyond its
own subject-formatting/payload-translation logic; the domain layer
(`domain/peer_review.py`, `domain/restart.py`) is fully tested against
`FakeAgentInstancePort` instead.
"""

from __future__ import annotations

from nova_contracts import AgentMessage

from nova_agent_os_supervisors.domain.ports import EventPublisher

__all__ = ["InstanceMailboxClient"]

SOURCE_ENGINE = "supervisors"


class InstanceMailboxClient:
    def __init__(self, event_publisher: EventPublisher) -> None:
        self._event_publisher = event_publisher

    async def deliver(
        self, message: AgentMessage, *, timeout_ms: int = 30000
    ) -> AgentMessage | None:
        subject = f"agent_os.instance.{message.to_instance_id}.inbox"
        reply = await self._event_publisher.request(
            subject,
            message,
            source_engine=SOURCE_ENGINE,
            correlation_id=message.correlation_id,
            timeout_ms=timeout_ms,
        )
        if reply.payload is None:
            return None
        return AgentMessage.model_validate(reply.payload)
