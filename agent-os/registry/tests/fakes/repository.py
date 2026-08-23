"""In-memory `RegistryRepository` fake -- mirrors `capability-engine`'s
own `tests/fakes/repository.py` convention: lets `create_app()` be
exercised in `test_health.py` without a real Postgres connection, and
lets `domain/pipeline.py` unit tests exercise the full install pipeline
without SQLAlchemy at all. Natural key: `(id, version)` (see
`domain/pipeline.py`'s module docstring)."""

from __future__ import annotations

from nova_agent_os_registry.domain.models import AgentPackage
from nova_agent_os_registry.domain.ports import AgentPackageAlreadyExistsError

__all__ = ["FakeRegistryRepository"]


class FakeRegistryRepository:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], AgentPackage] = {}

    async def find_by_id_version(self, package_id: str, version: str) -> AgentPackage | None:
        return self.rows.get((package_id, version))

    async def find_latest_by_id(self, package_id: str) -> AgentPackage | None:
        matches = [row for row in self.rows.values() if row.id == package_id]
        if not matches:
            return None
        return max(matches, key=lambda row: row.installed_at)

    async def list_by_category(self, category: str) -> list[AgentPackage]:
        return [row for row in self.rows.values() if row.category == category]

    async def insert(self, package: AgentPackage) -> AgentPackage:
        key = (package.id, package.version)
        if key in self.rows:
            raise AgentPackageAlreadyExistsError(
                f"agent_package {key} already exists"
            )
        self.rows[key] = package
        return package

    async def update_health_status(
        self, package_id: str, version: str, *, health_status: str
    ) -> None:
        row = self.rows.get((package_id, version))
        if row is None:
            return
        self.rows[(package_id, version)] = row.model_copy(update={"health_status": health_status})
