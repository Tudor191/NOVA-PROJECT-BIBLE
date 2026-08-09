"""`PostgresPersonalityRepository` -- implements
`domain.ports.PersonalityRepository` against SQLAlchemy async, per the schema
in docs/design/phase-2d/02-personality-engine.md Sec9.

No transactional outbox (unlike every prior engine's repository) -- this
engine publishes nothing this phase (design doc Sec10); every write here is
its own short transaction.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nova_personality_engine.domain.models import CoreIdentity, MemoryProfile, ValidationResult
from nova_personality_engine.repository.models import (
    CoreIdentityORM,
    MemoryProfileORM,
    ValidationAuditORM,
)

__all__ = ["PostgresPersonalityRepository"]


def _identity_to_domain(row: CoreIdentityORM) -> CoreIdentity:
    return CoreIdentity(
        schema_version=row.schema_version,
        traits=list(row.traits),
        values=list(row.values),
        forbidden_behaviors=list(row.forbidden_behaviors),
        version_note=row.version_note,
    )


def _profile_to_domain(row: MemoryProfileORM) -> MemoryProfile:
    return MemoryProfile(
        verbosity=row.verbosity,
        technical_depth=row.technical_depth,
        terminology_preference=row.terminology_preference,
        source=row.source,
        updated_at=row.updated_at,
    )


class PostgresPersonalityRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_core_identity(self) -> CoreIdentity | None:
        async with self._session_factory() as session:
            row = await session.get(CoreIdentityORM, 1)
            return _identity_to_domain(row) if row is not None else None

    async def get_memory_profile(self) -> MemoryProfile:
        async with self._session_factory() as session:
            row = await session.get(MemoryProfileORM, 1)
            if row is None:
                # Sec6: config-defined default, never a null/crash -- a
                # config-integrity bug to alert on (missing seed row), not a
                # runtime decision point. Falling back to the domain
                # model's own defaults here is that alert-worthy fallback.
                return MemoryProfile()
            return _profile_to_domain(row)

    async def update_memory_profile(self, profile: MemoryProfile) -> MemoryProfile:
        async with self._session_factory() as session, session.begin():
            row = await session.get(MemoryProfileORM, 1)
            if row is None:
                row = MemoryProfileORM(id=1)
                session.add(row)
            row.verbosity = profile.verbosity
            row.technical_depth = profile.technical_depth
            row.terminology_preference = profile.terminology_preference
            row.source = profile.source
            await session.flush()
            await session.refresh(row)
            return _profile_to_domain(row)

    async def record_validation_audit(
        self,
        *,
        session_id: UUID,
        result: ValidationResult,
        selected_style: str | None,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                ValidationAuditORM(
                    session_id=session_id,
                    passed=result.passed,
                    violations=[v.model_dump(mode="json") for v in result.violations] or None,
                    selected_style=selected_style,
                )
            )
