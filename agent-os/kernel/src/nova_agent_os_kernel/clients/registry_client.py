"""`RegistryClient` -- `domain.ports.RegistryPort` implementation, calling
the two disclosed Registry RPCs (see `nova_contracts.events.agent_os`'s own
module docstring). Mirrors `reasoning-engine`'s own
`ModelOrchestrationClient` structure exactly.

**Neither method catches.** A `TimeoutError` from an unreachable Registry,
or a validation error from a malformed reply, propagates to the caller. That
is the existing convention for `find_healthy_package` -- the Scheduler
handles an unreachable Registry at its own call site, where it has the
context to decide (`domain/scheduler.py`'s `_plan_restart_or_decline`
docstring records the same reasoning for the Supervisor RPC) -- and 4C.2a
holds `list_packages` to it deliberately: decision **D-1** requires
`GET /v1/agents` to answer 503 for a degraded Registry and `200 []` for a
healthy empty one, and a client that turned a timeout into `[]` would make
that distinction unrepresentable at every layer above it.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_contracts import (
    AgentOsFindHealthyPackageReplyPayload,
    AgentOsFindHealthyPackageRequestPayload,
    AgentOsListPackagesReplyPayload,
    AgentOsListPackagesRequestPayload,
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

    async def list_packages(
        self, *, correlation_id: UUID | None = None
    ) -> list[AgentPackageSnapshot]:
        """Every installed Agent Package, in Registry's own deterministic
        order -- returned as received, never re-sorted here. The ordering
        guarantee belongs to one layer (`RegistryRepository.list_all`), and
        a second sort in the client would be a second place for it to
        drift."""
        cid = correlation_id or uuid4()
        envelope = await self._event_publisher.request(
            "agent_os.registry.list_packages.request",
            AgentOsListPackagesRequestPayload(
                requesting_engine=SOURCE_ENGINE, correlation_id=cid
            ),
            source_engine=SOURCE_ENGINE,
            correlation_id=cid,
            timeout_ms=self._timeout_ms,
        )
        parsed = AgentOsListPackagesReplyPayload.model_validate(envelope.payload)
        return parsed.packages
