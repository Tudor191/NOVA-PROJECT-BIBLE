"""`PostgresRegistryRepository` -- implements
`domain.ports.RegistryRepository` against SQLAlchemy async, per the schema
in docs/design/phase-3/08-tdd-3e-agent-os.md §5.

`insert()` translates an `(id, version)` primary-key violation
(`sqlalchemy.exc.IntegrityError`) into `AgentPackageAlreadyExistsError` --
the natural-key idempotency guard convention every other Phase 3
repository already establishes.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nova_agent_os_registry.domain.models import AgentPackage
from nova_agent_os_registry.domain.ports import AgentPackageAlreadyExistsError
from nova_agent_os_registry.repository.models import AgentPackageORM

__all__ = ["PostgresRegistryRepository"]


def _to_domain(row: AgentPackageORM) -> AgentPackage:
    return AgentPackage(
        id=row.id,
        category=row.category,
        version=row.version,
        manifest_json=dict(row.manifest_json),
        installed_at=row.installed_at,
        health_status=row.health_status,
        checksum=row.checksum,
        supervisor_notified_new_permissions=list(row.supervisor_notified_new_permissions),
    )


class PostgresRegistryRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def find_by_id_version(self, package_id: str, version: str) -> AgentPackage | None:
        async with self._session_factory() as session:
            row = await session.get(AgentPackageORM, (package_id, version))
            return _to_domain(row) if row is not None else None

    async def find_latest_by_id(self, package_id: str) -> AgentPackage | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(AgentPackageORM)
                .where(AgentPackageORM.id == package_id)
                .order_by(AgentPackageORM.installed_at.desc())
                .limit(1)
            )
            row = result.scalars().first()
            return _to_domain(row) if row is not None else None

    async def list_by_category(self, category: str) -> list[AgentPackage]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(AgentPackageORM).where(AgentPackageORM.category == category)
            )
            return [_to_domain(row) for row in result.scalars().all()]

    async def insert(self, package: AgentPackage) -> AgentPackage:
        row = AgentPackageORM(
            id=package.id,
            category=package.category,
            version=package.version,
            manifest_json=package.manifest_json,
            installed_at=package.installed_at,
            health_status=package.health_status,
            checksum=package.checksum,
            supervisor_notified_new_permissions=package.supervisor_notified_new_permissions,
        )
        async with self._session_factory() as session:
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise AgentPackageAlreadyExistsError(
                    f"agent_package ({package.id}, {package.version}) already exists"
                ) from exc
        return package

    async def update_health_status(
        self, package_id: str, version: str, *, health_status: str
    ) -> None:
        async with self._session_factory() as session:
            row = await session.get(AgentPackageORM, (package_id, version))
            if row is None:
                return
            row.health_status = health_status
            await session.commit()
