"""`RegistryClient` -- `domain.ports.RegistryPort` implementation, calling
the disclosed `agent_os.registry.find_healthy_package.request` RPC (see
`nova_contracts.events.agent_os`'s own module docstring). Mirrors
`reasoning-engine`'s own `ModelOrchestrationClient` structure exactly.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_contracts import (
    AgentOsFindHealthyPackageReplyPayload,
    AgentOsFindHealthyPackageRequestPayload,
    AgentPackageSnapshot,
)

from nova_agent_os_kernel.domain.ports import EventPublisher

__all__ = ["RegistryClient"]

SOURCE_ENGINE = "kernel"
DEFAULT_TIMEOUT_MS = 2000


class RegistryClient:
    def __init__(
        self, event_publisher: EventPublisher, *, timeout_ms: int = DEFAULT_TIMEOUT_MS
    ) -> None:
        self._event_publisher = event_publisher
        self._timeout_ms = timeout_ms

    async def find_healthy_package(
        self, *, category: str, correlation_id: UUID | None = None
    ) -> AgentPackageSnapshot | None:
        cid = correlation_id or uuid4()
        envelope = await self._event_publisher.request(
            "agent_os.registry.find_healthy_package.request",
            AgentOsFindHealthyPackageRequestPayload(
                category=category, requesting_engine=SOURCE_ENGINE, correlation_id=cid
            ),
            source_engine=SOURCE_ENGINE,
            correlation_id=cid,
            timeout_ms=self._timeout_ms,
        )
        parsed = AgentOsFindHealthyPackageReplyPayload.model_validate(envelope.payload)
        return parsed.package
