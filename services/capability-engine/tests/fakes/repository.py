"""`FakeCapabilityRepository` -- an in-memory `domain.ports.CapabilityRepository`,
mirroring `PostgresCapabilityRepository`'s own behavior closely enough that
swapping one for the other in a test changes nothing observable, including
the `(name, version)` uniqueness-violation -> `CapabilityAlreadyExistsError`
translation Fork 3C-4 depends on."""

from __future__ import annotations

from uuid import UUID

from nova_capability_engine.domain.ports import CapabilityAlreadyExistsError
from nova_contracts import Capability


class FakeCapabilityRepository:
    def __init__(self) -> None:
        self.capabilities: dict[UUID, Capability] = {}
        self.installation_events: list[dict] = []

    async def find_by_name_version(self, *, name: str, version: str) -> Capability | None:
        for capability in self.capabilities.values():
            if capability.name == name and capability.version == version:
                return capability
        return None

    async def find_by_id(self, capability_id: UUID) -> Capability | None:
        return self.capabilities.get(capability_id)

    async def find_by_name(self, name: str) -> Capability | None:
        matches = [c for c in self.capabilities.values() if c.name == name]
        if not matches:
            return None
        return max(matches, key=lambda c: c.installed_at)

    async def list_all(self) -> list[Capability]:
        return list(self.capabilities.values())

    async def insert(self, capability: Capability) -> Capability:
        existing = await self.find_by_name_version(name=capability.name, version=capability.version)
        if existing is not None:
            raise CapabilityAlreadyExistsError(
                f"capability {capability.name!r} version {capability.version!r} already exists"
            )
        self.capabilities[capability.id] = capability
        return capability

    async def delete(self, capability_id: UUID) -> bool:
        return self.capabilities.pop(capability_id, None) is not None

    async def record_installation_event(
        self,
        *,
        capability_id: UUID | None,
        name: str,
        version: str,
        stage: str,
        outcome: str,
        detail: str | None = None,
    ) -> None:
        self.installation_events.append(
            {
                "capability_id": capability_id,
                "name": name,
                "version": version,
                "stage": stage,
                "outcome": outcome,
                "detail": detail,
            }
        )
