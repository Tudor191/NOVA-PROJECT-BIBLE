"""`FakePersonalityRepository` -- an in-memory `domain.ports.
PersonalityRepository`, mirroring `PostgresPersonalityRepository`'s own
behavior (design doc Sec9) closely enough that swapping one for the other in
a test changes nothing observable. Seeded with a Doc-23-shaped identity by
default so most tests don't need to construct one by hand; pass
`core_identity=None` to exercise design doc Sec8's no-Core-Identity failure
mode.
"""

from __future__ import annotations

from uuid import UUID

from nova_personality_engine.domain.models import CoreIdentity, MemoryProfile, ValidationResult

_DEFAULT_IDENTITY = CoreIdentity(
    traits=["calm", "professional", "honest"],
    values=["Trust Before Intelligence", "Truth over appearance"],
    forbidden_behaviors=["manipulation", "pretending_certainty_when_uncertain"],
    version_note="test fixture",
)


class FakePersonalityRepository:
    def __init__(
        self,
        *,
        core_identity: CoreIdentity | None = _DEFAULT_IDENTITY,
        memory_profile: MemoryProfile | None = None,
    ) -> None:
        self.core_identity = core_identity
        self.memory_profile = memory_profile or MemoryProfile()
        self.audit_records: list[tuple[UUID, ValidationResult, str | None]] = []

    async def get_core_identity(self) -> CoreIdentity | None:
        return self.core_identity

    async def get_memory_profile(self) -> MemoryProfile:
        return self.memory_profile

    async def update_memory_profile(self, profile: MemoryProfile) -> MemoryProfile:
        self.memory_profile = profile
        return profile

    async def record_validation_audit(
        self,
        *,
        session_id: UUID,
        result: ValidationResult,
        selected_style: str | None,
    ) -> None:
        self.audit_records.append((session_id, result, selected_style))
