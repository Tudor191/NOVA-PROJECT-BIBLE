"""In-memory `RegistryRepository` fake -- mirrors `capability-engine`'s
own `tests/fakes/repository.py` convention: lets `create_app()` be
exercised in `test_health.py` without a real Postgres connection, and
lets `domain/pipeline.py` unit tests exercise the full install pipeline
without SQLAlchemy at all. Natural key: `(category, version)` -- the
approved Fork 3E-2 ORM shape (see `domain/pipeline.py`'s module
docstring and `docs/design/phase-3/15-3e-supervisor-reconciliation.md`
§A)."""

from __future__ import annotations

from uuid import UUID

from nova_agent_os_registry.domain.models import AgentPackage
from nova_agent_os_registry.domain.ports import AgentPackageAlreadyExistsError

__all__ = ["FakeRegistryRepository"]


class FakeRegistryRepository:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], AgentPackage] = {}

    async def find_by_category_version(
        self, category: str, version: str
    ) -> AgentPackage | None:
        return self.rows.get((category, version))

    async def find_latest_by_category(self, category: str) -> AgentPackage | None:
        matches = [row for row in self.rows.values() if row.category == category]
        if not matches:
            return None
        return max(matches, key=lambda row: row.installed_at)

    async def list_by_category(self, category: str) -> list[AgentPackage]:
        return [row for row in self.rows.values() if row.category == category]

    async def insert(self, package: AgentPackage) -> AgentPackage:
        key = (package.category, package.version)
        if key in self.rows:
            raise AgentPackageAlreadyExistsError(f"agent_package {key} already exists")
        self.rows[key] = package
        return package

    async def update_health_status(self, package_id: UUID, *, health_status: str) -> None:
        for key, row in self.rows.items():
            if row.id == package_id:
                self.rows[key] = row.model_copy(update={"health_status": health_status})
                return
