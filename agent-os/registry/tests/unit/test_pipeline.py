"""Unit tests for `domain/pipeline.py`'s real 8-step install pipeline --
every stage exercised against a real fixture Agent Package written to
disk (`tmp_path`), using `FakeRegistryRepository`/`FakeCommunicationPort`
so no real Postgres or Event Bus is required. Mirrors
`capability-engine`'s own `tests/unit/test_pipeline.py` convention,
adapted for filesystem discovery (`DiscoveredPackage`, not an in-memory
bundled manifest) and the natural-key `(id, version)` resolution this
component's own `domain/pipeline.py` module docstring discloses.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from nova_agent_os_registry.domain.discovery import DiscoveredPackage
from nova_agent_os_registry.domain.models import AgentPackage
from nova_agent_os_registry.domain.pipeline import (
    InstallationError,
    InstallationStage,
    install_agent_package,
)
from nova_agent_os_registry.domain.ports import AgentPackageAlreadyExistsError

from tests.fakes.communication_port import FakeCommunicationPort
from tests.fakes.repository import FakeRegistryRepository

_CONFORMING_HANDLER = '''
from __future__ import annotations

from nova_agent_sdk import (
    AgentContext,
    AgentHandler,
    AgentHealth,
    AgentManifest,
    AgentMessage,
    AgentMetrics,
    AgentResult,
    ValidationOutcome,
)
from nova_contracts import ResourceUsage


class Handler(AgentHandler):
    def __init__(self) -> None:
        self.loaded = False

    async def on_load(self, manifest: AgentManifest) -> None:
        self.loaded = True

    async def on_unload(self) -> None:
        self.loaded = False

    async def on_assign(self, task, context) -> None:
        pass

    async def execute(self) -> AgentResult:
        raise NotImplementedError

    async def on_pause(self) -> None:
        pass

    async def on_resume(self) -> None:
        pass

    async def self_validate(self, result) -> ValidationOutcome:
        raise NotImplementedError

    async def health_check(self) -> AgentHealth:
        return AgentHealth(
            status="healthy",
            latency_ms=1.0,
            error_rate=0.0,
            resource_usage=ResourceUsage(cpu_percent=1.0, memory_mb=32.0),
        )

    async def on_message(self, message: AgentMessage) -> AgentMessage | None:
        return None

    def metrics_snapshot(self) -> AgentMetrics:
        return AgentMetrics(
            tasks_completed=0,
            tasks_failed=0,
            average_duration_ms=0.0,
            average_confidence=0.0,
            resource_efficiency=1.0,
        )
'''

_FAILING_ON_LOAD_HANDLER = _CONFORMING_HANDLER.replace(
    "        self.loaded = True\n",
    "        raise RuntimeError('on_load blew up')\n",
)

_NON_CONFORMING_HANDLER = '''
class Handler:
    """Does not implement AgentHandler at all."""
'''

_BROKEN_IMPORT_HANDLER = "this is not valid python syntax :::\n"

_NO_HANDLER_CLASS = '''
class NotCalledHandler:
    """Imports cleanly but never defines a top-level `Handler`."""
'''


def _write_agent_package(
    tmp_path: Path,
    *,
    package_id: str = "toy-agent",
    version: str = "0.1.0",
    category: str = "qa",
    required_permissions: list[str] | None = None,
    supported_execution_backends: list[str] | None = None,
    min_kernel_version: str = "0.1.0",
    handler_source: str = _CONFORMING_HANDLER,
) -> DiscoveredPackage:
    directory = tmp_path / package_id
    (directory / "src").mkdir(parents=True)
    manifest = {
        "id": package_id,
        "version": version,
        "category": category,
        "display_name": package_id.replace("-", " ").title(),
        "required_capabilities": [],
        "required_permissions": required_permissions or [],
        "supported_execution_backends": supported_execution_backends or ["inprocess"],
        "resource_profile": {"cpu": "standard", "memory": "standard", "gpu": "none"},
        "health_check": {"interval_seconds": 30},
        "compatibility": {"min_kernel_version": min_kernel_version},
    }
    manifest_path = directory / "agent.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest))
    handler_path = directory / "src" / "handler.py"
    handler_path.write_text(handler_source)
    return DiscoveredPackage(
        directory=directory, manifest_path=manifest_path, handler_path=handler_path
    )


async def _install(package: DiscoveredPackage, **overrides: object) -> AgentPackage:
    kwargs: dict[str, object] = {
        "repository": FakeRegistryRepository(),
        "communication_port": None,
        "primary_user_id": None,
        "kernel_version": "0.1.0",
    }
    kwargs.update(overrides)
    return await install_agent_package(package, **kwargs)  # type: ignore[arg-type]


async def test_full_pipeline_succeeds_and_promotes_health_to_healthy(tmp_path: Path) -> None:
    package = _write_agent_package(tmp_path)
    repository = FakeRegistryRepository()

    stages_seen: list[tuple[InstallationStage, str]] = []

    async def on_stage(stage: InstallationStage, outcome: str) -> None:
        stages_seen.append((stage, outcome))

    installed = await install_agent_package(
        package,
        repository=repository,
        communication_port=None,
        primary_user_id=None,
        kernel_version="0.1.0",
        on_stage=on_stage,
    )

    assert installed.id == "toy-agent"
    assert installed.version == "0.1.0"
    assert installed.category == "qa"
    assert installed.health_status == "healthy"
    assert installed.checksum

    persisted = await repository.find_by_id_version("toy-agent", "0.1.0")
    assert persisted is not None
    assert persisted.health_status == "healthy"

    assert [stage for stage, _ in stages_seen] == [
        InstallationStage.FETCH,
        InstallationStage.INTEGRITY_VERIFICATION,
        InstallationStage.MANIFEST_VALIDATION,
        InstallationStage.DEPENDENCY_RESOLUTION,
        InstallationStage.PERMISSION_REVIEW,
        InstallationStage.SANDBOX_TEST,
        InstallationStage.REGISTRATION,
        InstallationStage.ON_LOAD,
    ]


async def test_fetch_stage_fails_on_missing_files(tmp_path: Path) -> None:
    directory = tmp_path / "ghost-agent"
    directory.mkdir()
    package = DiscoveredPackage(
        directory=directory,
        manifest_path=directory / "agent.yaml",
        handler_path=directory / "src" / "handler.py",
    )

    with pytest.raises(InstallationError) as exc_info:
        await _install(package)
    assert exc_info.value.stage is InstallationStage.FETCH


async def test_integrity_verification_fails_on_an_empty_manifest(tmp_path: Path) -> None:
    package = _write_agent_package(tmp_path)
    package.manifest_path.write_text("")

    with pytest.raises(InstallationError) as exc_info:
        await _install(package)
    assert exc_info.value.stage is InstallationStage.INTEGRITY_VERIFICATION


async def test_manifest_validation_fails_on_malformed_yaml(tmp_path: Path) -> None:
    package = _write_agent_package(tmp_path)
    package.manifest_path.write_text("id: [this is not: valid: yaml")

    with pytest.raises(InstallationError) as exc_info:
        await _install(package)
    assert exc_info.value.stage is InstallationStage.MANIFEST_VALIDATION


async def test_manifest_validation_fails_on_missing_required_field(tmp_path: Path) -> None:
    package = _write_agent_package(tmp_path)
    manifest = yaml.safe_load(package.manifest_path.read_text())
    del manifest["compatibility"]
    package.manifest_path.write_text(yaml.safe_dump(manifest))

    with pytest.raises(InstallationError) as exc_info:
        await _install(package)
    assert exc_info.value.stage is InstallationStage.MANIFEST_VALIDATION


async def test_idempotent_reinstall_returns_the_existing_row_unchanged(tmp_path: Path) -> None:
    package = _write_agent_package(tmp_path)
    repository = FakeRegistryRepository()
    existing = AgentPackage(
        id="toy-agent",
        category="qa",
        version="0.1.0",
        manifest_json={"id": "toy-agent"},
        installed_at=datetime.now(UTC),
        health_status="healthy",
        checksum="pre-existing-checksum",
    )
    repository.rows[("toy-agent", "0.1.0")] = existing

    result = await install_agent_package(
        package,
        repository=repository,
        communication_port=None,
        primary_user_id=None,
        kernel_version="0.1.0",
    )

    assert result == existing
    assert result.checksum == "pre-existing-checksum"


async def test_dependency_resolution_fails_when_no_phase3_backend_is_declared(
    tmp_path: Path,
) -> None:
    package = _write_agent_package(tmp_path, supported_execution_backends=["subprocess"])

    with pytest.raises(InstallationError) as exc_info:
        await _install(package)
    assert exc_info.value.stage is InstallationStage.DEPENDENCY_RESOLUTION


async def test_dependency_resolution_fails_when_kernel_is_too_old(tmp_path: Path) -> None:
    package = _write_agent_package(tmp_path, min_kernel_version="99.0.0")

    with pytest.raises(InstallationError) as exc_info:
        await _install(package, kernel_version="0.1.0")
    assert exc_info.value.stage is InstallationStage.DEPENDENCY_RESOLUTION


async def test_permission_review_first_install_with_no_permissions_is_a_no_op(
    tmp_path: Path,
) -> None:
    package = _write_agent_package(tmp_path)
    communication_port = FakeCommunicationPort(session_id=uuid4())

    await _install(
        package,
        communication_port=communication_port,
        primary_user_id=uuid4(),
    )

    assert communication_port.delivered_content == []


async def test_permission_review_delivers_new_permissions_on_first_install(
    tmp_path: Path,
) -> None:
    package = _write_agent_package(
        tmp_path, required_permissions=["filesystem:write:project-scope"]
    )
    communication_port = FakeCommunicationPort(session_id=uuid4())

    await _install(
        package,
        communication_port=communication_port,
        primary_user_id=uuid4(),
    )

    assert len(communication_port.delivered_content) == 1
    assert "filesystem:write:project-scope" in communication_port.delivered_content[0]


async def test_permission_review_diffs_against_the_previous_version(tmp_path: Path) -> None:
    package_v1 = _write_agent_package(
        tmp_path / "v1", version="0.1.0", required_permissions=["terminal:execute"]
    )
    repository = FakeRegistryRepository()
    await install_agent_package(
        package_v1,
        repository=repository,
        communication_port=None,
        primary_user_id=None,
        kernel_version="0.1.0",
    )

    package_v2 = _write_agent_package(
        tmp_path / "v2",
        version="0.2.0",
        required_permissions=["terminal:execute", "http:outbound:api.example.com"],
    )
    communication_port = FakeCommunicationPort(session_id=uuid4())
    await install_agent_package(
        package_v2,
        repository=repository,
        communication_port=communication_port,
        primary_user_id=uuid4(),
        kernel_version="0.1.0",
    )

    assert len(communication_port.delivered_content) == 1
    content = communication_port.delivered_content[0]
    assert "http:outbound:api.example.com" in content
    assert "terminal:execute" not in content


async def test_permission_review_skips_when_no_primary_user_configured(tmp_path: Path) -> None:
    package = _write_agent_package(tmp_path, required_permissions=["terminal:execute"])

    installed = await _install(package, communication_port=None, primary_user_id=None)

    assert installed.health_status == "healthy"


async def test_permission_review_skips_when_no_session_is_connected(tmp_path: Path) -> None:
    package = _write_agent_package(tmp_path, required_permissions=["terminal:execute"])
    communication_port = FakeCommunicationPort(session_id=None)

    installed = await _install(
        package, communication_port=communication_port, primary_user_id=uuid4()
    )

    assert installed.health_status == "healthy"
    assert communication_port.delivered_content == []


async def test_permission_review_survives_a_communication_engine_timeout(tmp_path: Path) -> None:
    package = _write_agent_package(tmp_path, required_permissions=["terminal:execute"])
    communication_port = FakeCommunicationPort(session_id=uuid4(), raise_timeout=True)

    installed = await _install(
        package, communication_port=communication_port, primary_user_id=uuid4()
    )

    assert installed.health_status == "healthy"


async def test_sandbox_test_fails_when_handler_py_defines_no_handler_class(
    tmp_path: Path,
) -> None:
    package = _write_agent_package(tmp_path, handler_source=_NO_HANDLER_CLASS)

    with pytest.raises(InstallationError) as exc_info:
        await _install(package)
    assert exc_info.value.stage is InstallationStage.SANDBOX_TEST


async def test_sandbox_test_fails_on_broken_handler_syntax(tmp_path: Path) -> None:
    package = _write_agent_package(tmp_path, handler_source=_BROKEN_IMPORT_HANDLER)

    with pytest.raises(InstallationError) as exc_info:
        await _install(package)
    assert exc_info.value.stage is InstallationStage.SANDBOX_TEST


async def test_sandbox_test_fails_when_handler_does_not_satisfy_the_protocol(
    tmp_path: Path,
) -> None:
    package = _write_agent_package(tmp_path, handler_source=_NON_CONFORMING_HANDLER)

    with pytest.raises(InstallationError) as exc_info:
        await _install(package)
    assert exc_info.value.stage is InstallationStage.SANDBOX_TEST


async def test_registration_race_returns_the_already_inserted_row(tmp_path: Path) -> None:
    package = _write_agent_package(tmp_path)

    class _RaceRepository(FakeRegistryRepository):
        async def insert(self, agent_package: AgentPackage) -> AgentPackage:
            raced = agent_package.model_copy(update={"checksum": "raced-in-first"})
            self.rows[(agent_package.id, agent_package.version)] = raced
            raise AgentPackageAlreadyExistsError("raced")

    result = await _install(package, repository=_RaceRepository())

    assert result.checksum == "raced-in-first"


async def test_on_load_failure_does_not_roll_back_registration(tmp_path: Path) -> None:
    package = _write_agent_package(tmp_path, handler_source=_FAILING_ON_LOAD_HANDLER)
    repository = FakeRegistryRepository()

    installed = await install_agent_package(
        package,
        repository=repository,
        communication_port=None,
        primary_user_id=None,
        kernel_version="0.1.0",
    )

    assert installed.health_status == "unknown"
    persisted = await repository.find_by_id_version("toy-agent", "0.1.0")
    assert persisted is not None
    assert persisted.health_status == "unknown"
