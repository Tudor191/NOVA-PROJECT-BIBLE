"""`PostgresCapabilityRepository` -- implements `domain.ports.CapabilityRepository`
against SQLAlchemy async, per the schema in
docs/design/phase-3/06-tdd-3c-capability-engine.md §6.

`insert()` translates a `(name, version)` `UniqueConstraint` violation
(`sqlalchemy.exc.IntegrityError`) into `CapabilityAlreadyExistsError`
(Fork 3C-4's concurrent-installation-race safety net, §4) -- the first
engine in this project to need this specific translation, since it is the
first engine with an application-visible natural-key uniqueness
constraint `domain/` code must react to, not merely a schema-level
invariant nothing ever violates in practice.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from nova_contracts import Capability
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nova_capability_engine.domain.ports import CapabilityAlreadyExistsError
from nova_capability_engine.repository.models import CapabilityInstallationEventORM, CapabilityORM

__all__ = ["PostgresCapabilityRepository"]


def _to_domain(row: CapabilityORM) -> Capability:
    return Capability(
        id=row.id,
        name=row.name,
        description=row.description,
        category=row.category,
        version=row.version,
        dependencies=list(row.dependencies),
        required_permissions=list(row.required_permissions),
        required_resources=list(row.required_resources),
        input_schema=dict(row.input_schema),
        output_schema=dict(row.output_schema),
        execution_adapter=row.execution_adapter,
        health_status=row.health_status,
        installed_at=row.installed_at,
    )


class PostgresCapabilityRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def find_by_name_version(self, *, name: str, version: str) -> Capability | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(CapabilityORM).where(
                    CapabilityORM.name == name, CapabilityORM.version == version
                )
            )
            return _to_domain(row) if row is not None else None

    async def find_by_id(self, capability_id: UUID) -> Capability | None:
        async with self._session_factory() as session:
            row = await session.get(CapabilityORM, capability_id)
            return _to_domain(row) if row is not None else None

    async def list_all(self) -> list[Capability]:
        async with self._session_factory() as session:
            rows = await session.scalars(select(CapabilityORM))
            return [_to_domain(row) for row in rows]

    async def insert(self, capability: Capability) -> Capability:
        now = datetime.now(UTC)
        row = CapabilityORM(
            id=capability.id,
            name=capability.name,
            description=capability.description,
            category=capability.category,
            version=capability.version,
            dependencies=list(capability.dependencies),
            required_permissions=list(capability.required_permissions),
            required_resources=list(capability.required_resources),
            input_schema=dict(capability.input_schema),
            output_schema=dict(capability.output_schema),
            execution_adapter=capability.execution_adapter,
            health_status=capability.health_status,
            installed_at=capability.installed_at,
            # Sandbox Testing and Permission Review (domain/pipeline.py's
            # stages 4/5) have both already completed by the time this is
            # called -- see repository/models.py's own docstring.
            permissions_reviewed_at=now,
            sandbox_test_passed_at=now,
        )
        async with self._session_factory() as session:
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise CapabilityAlreadyExistsError(
                    f"capability {capability.name!r} version {capability.version!r} "
                    "already exists"
                ) from exc
        return capability

    async def delete(self, capability_id: UUID) -> bool:
        async with self._session_factory() as session:
            row = await session.get(CapabilityORM, capability_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

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
        async with self._session_factory() as session:
            session.add(
                CapabilityInstallationEventORM(
                    capability_id=capability_id,
                    name=name,
                    version=version,
                    stage=stage,
                    outcome=outcome,
                    detail=detail,
                )
            )
            await session.commit()
