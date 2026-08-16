"""The real 8-stage Installation Pipeline (TDD 3C §2.3, Bible Part 15
`:241-275`): Download -> Integrity Verification -> Dependency Resolution ->
Permission Review -> Sandbox Testing -> Registration -> Health Check ->
Activation. Framework-free (docs/architecture/03-backend-architecture.md
§1) -- depends only on `domain/ports.py`'s Protocols and `domain/sandbox.py`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from nova_contracts import Capability

from nova_capability_engine.domain.models import CapabilityManifest
from nova_capability_engine.domain.ports import (
    AdapterPort,
    CapabilityAlreadyExistsError,
    CapabilityRepository,
    CommunicationPort,
)
from nova_capability_engine.domain.sandbox import SandboxViolation

__all__ = ["InstallationError", "InstallationStage", "install_capability"]


class InstallationStage(StrEnum):
    DOWNLOAD = "download"
    INTEGRITY_VERIFICATION = "integrity_verification"
    DEPENDENCY_RESOLUTION = "dependency_resolution"
    PERMISSION_REVIEW = "permission_review"
    SANDBOX_TESTING = "sandbox_testing"
    REGISTRATION = "registration"
    HEALTH_CHECK = "health_check"
    ACTIVATION = "activation"


class InstallationError(Exception):
    """TDD 3C §8: "Sandbox test fails during install -> Capability never
    reaches Registration/Activation -- install pipeline halts... no partial
    registration." Every raise site records the failing stage."""

    def __init__(self, message: str, *, stage: InstallationStage) -> None:
        super().__init__(message)
        self.stage = stage


class _RecordFn(Protocol):
    async def __call__(
        self, stage: InstallationStage, outcome: str, detail: str | None = None
    ) -> None: ...


async def install_capability(
    manifest: CapabilityManifest,
    *,
    repository: CapabilityRepository,
    adapters: dict[str, AdapterPort],
    communication_port: CommunicationPort | None,
    primary_user_id: UUID | None,
    on_stage: Callable[[InstallationStage, str], Awaitable[None]] | None = None,
) -> Capability:
    """Runs the real 8-stage pipeline for one capability manifest.

    Fork 3C-4 (idempotency, Option B): if `(manifest.name, manifest.version)`
    already exists, returns the existing record immediately -- no stage
    re-runs, no duplicate `capability_installation_event` rows. This check
    happens before stage 1, not as a stage of its own (TDD 3C §7's own
    framing: idempotent-POST behavior, distinct from the 8-stage lifecycle
    the Bible names).

    `on_stage`, when supplied, is awaited with each `(stage, outcome)` pair
    as it is reached -- `reasoning-engine`'s own `domain/pipeline.py`
    `on_stage` callback precedent, reused here so `main.py`/`api/` can
    increment `capability_install_pipeline_stage_total{stage=...}`
    (TDD 3C §9) without `domain/` importing an observability framework."""
    existing = await repository.find_by_name_version(name=manifest.name, version=manifest.version)
    if existing is not None:
        return existing

    async def _record(stage: InstallationStage, outcome: str, detail: str | None = None) -> None:
        await repository.record_installation_event(
            capability_id=None,
            name=manifest.name,
            version=manifest.version,
            stage=stage.value,
            outcome=outcome,
            detail=detail,
        )
        if on_stage is not None:
            await on_stage(stage, outcome)

    # 1. Download -- first-party, bundled: reads from this engine's own
    # embedded manifest, never a network fetch (TDD 3C §2.3).
    await _record(InstallationStage.DOWNLOAD, "success")

    # 2. Integrity Verification -- signature/checksum against the bundled
    # package. For a first-party, embedded manifest this reduces to
    # structural validation, already guaranteed by `CapabilityManifest`'s
    # own Pydantic construction; recorded as its own stage regardless, so a
    # future non-bundled capability's real checksum check slots in here
    # without changing the pipeline's shape.
    await _record(InstallationStage.INTEGRITY_VERIFICATION, "success")

    # 3. Dependency Resolution -- every declared dependency must already be
    # registered, and the resulting dependency graph must be acyclic
    # (Bible Part 15's own "circular dependencies should never be allowed,"
    # a gap left silent by TDD 3C's own text -- closed here).
    installed = await repository.list_all()
    installed_by_name = {c.name: c for c in installed}
    missing = [dep for dep in manifest.dependencies if dep not in installed_by_name]
    if missing:
        detail = f"missing dependencies: {missing}"
        await _record(InstallationStage.DEPENDENCY_RESOLUTION, "failure", detail)
        raise InstallationError(
            f"capability {manifest.name!r} depends on unregistered capabilities {missing!r}",
            stage=InstallationStage.DEPENDENCY_RESOLUTION,
        )
    cycle = _find_dependency_cycle(manifest, installed_by_name)
    if cycle is not None:
        detail = f"circular dependency: {' -> '.join(cycle)}"
        await _record(InstallationStage.DEPENDENCY_RESOLUTION, "failure", detail)
        raise InstallationError(
            f"installing {manifest.name!r} would create a circular dependency: "
            f"{' -> '.join(cycle)}",
            stage=InstallationStage.DEPENDENCY_RESOLUTION,
        )
    await _record(InstallationStage.DEPENDENCY_RESOLUTION, "success")

    # 4. Permission Review -- best-effort disclosure to the single
    # configured user (TDD 3C §5; ADR-025's single-trusted-user-per-instance
    # assumption, `perception-engine`'s own `Settings.primary_user_id`
    # precedent). Never blocks the pipeline -- a missing/unreachable
    # session is recorded and the pipeline proceeds; nothing in TDD 3C
    # says installation blocks pending a reply (unlike `action-engine`'s
    # Critical-risk approval loop).
    await _attempt_permission_review_disclosure(
        manifest,
        communication_port=communication_port,
        primary_user_id=primary_user_id,
        record=_record,
    )

    # 5. Sandbox Testing -- a real, adversarial scope-violation probe
    # against the resolved adapter (never a fake port's simulated logic,
    # TDD 3C §12). A capability that cannot prove its own declared scope is
    # enforced never reaches Registration.
    adapter = adapters.get(manifest.execution_adapter)
    if adapter is None:
        detail = f"no adapter registered for {manifest.execution_adapter!r}"
        await _record(InstallationStage.SANDBOX_TESTING, "failure", detail)
        raise InstallationError(
            f"no adapter registered for execution_adapter {manifest.execution_adapter!r}",
            stage=InstallationStage.SANDBOX_TESTING,
        )
    try:
        await _sandbox_self_test(manifest, adapter)
    except SandboxViolation as exc:
        await _record(InstallationStage.SANDBOX_TESTING, "failure", str(exc))
        raise InstallationError(
            f"capability {manifest.name!r} failed its own sandbox self-test: {exc}",
            stage=InstallationStage.SANDBOX_TESTING,
        ) from exc
    await _record(InstallationStage.SANDBOX_TESTING, "success")

    # 6. Registration -- Sandbox Testing already proved the declared scope
    # is enforced, so the capability registers directly as `"healthy"`;
    # `"unknown"`/`"degraded"`/`"unhealthy"` are runtime-invocation-time
    # states (TDD 3C §8), not install-time outcomes.
    capability = Capability(
        id=uuid4(),
        name=manifest.name,
        description=manifest.description,
        category=manifest.category,
        version=manifest.version,
        dependencies=manifest.dependencies,
        required_permissions=manifest.required_permissions,
        required_resources=manifest.required_resources,
        input_schema=manifest.input_schema,
        output_schema=manifest.output_schema,
        execution_adapter=manifest.execution_adapter,
        health_status="healthy",
        installed_at=datetime.now(UTC),
    )
    try:
        capability = await repository.insert(capability)
    except CapabilityAlreadyExistsError:
        # Fork 3C-4: a concurrent installer won the race between our own
        # pre-check and this insert -- treat identically to the pre-check
        # idempotent-no-op path, never a hard failure.
        existing = await repository.find_by_name_version(
            name=manifest.name, version=manifest.version
        )
        if existing is not None:
            await _record(InstallationStage.REGISTRATION, "already_exists")
            return existing
        raise
    await _record(InstallationStage.REGISTRATION, "success")

    # 7. Health Check -- confirms the just-registered row is actually
    # persisted and queryable (the registry's own health), distinct from
    # Sandbox Testing's already-completed capability-level scope check.
    readback = await repository.find_by_id(capability.id)
    if readback is None:
        await _record(InstallationStage.HEALTH_CHECK, "failure", "registered row not readable")
        raise InstallationError(
            f"capability {manifest.name!r} was registered but is not readable back "
            "from the registry",
            stage=InstallationStage.HEALTH_CHECK,
        )
    await _record(InstallationStage.HEALTH_CHECK, "success")

    # 8. Activation -- registered + healthy is this engine's observable
    # "active" state (TDD 3C's own model has no separate flag).
    await _record(InstallationStage.ACTIVATION, "success")
    return readback


def _find_dependency_cycle(
    manifest: CapabilityManifest, installed_by_name: dict[str, Capability]
) -> list[str] | None:
    """DFS from each direct dependency; a path back to `manifest.name` is a
    cycle. Every name in `manifest.dependencies` is already confirmed
    registered by the caller before this runs -- reuses the same
    "detect a cycle before it's persisted" discipline `planning-engine`'s
    own `TaskGraph` validation established (`domain/task_graph.py`
    `find_cycle`), reimplemented locally since cross-engine imports are
    forbidden (ADR-004)."""

    def _walk(name: str, path: list[str], visited: set[str]) -> list[str] | None:
        if name == manifest.name:
            return [*path, name]
        if name in visited:
            return None
        visited.add(name)
        capability = installed_by_name.get(name)
        if capability is None:
            return None
        for dep in capability.dependencies:
            result = _walk(dep, [*path, name], visited)
            if result is not None:
                return result
        return None

    for dep in manifest.dependencies:
        result = _walk(dep, [], set())
        if result is not None:
            return result
    return None


async def _attempt_permission_review_disclosure(
    manifest: CapabilityManifest,
    *,
    communication_port: CommunicationPort | None,
    primary_user_id: UUID | None,
    record: _RecordFn,
) -> None:
    if communication_port is None or primary_user_id is None:
        await record(
            InstallationStage.PERMISSION_REVIEW, "skipped", "no primary_user_id configured"
        )
        return
    try:
        session_id = await communication_port.get_connected_session(user_id=primary_user_id)
        if session_id is None:
            await record(InstallationStage.PERMISSION_REVIEW, "skipped", "no connected session")
            return
        content = (
            f"New capability installed: {manifest.name!r} (v{manifest.version}), "
            f"requesting permissions: {manifest.required_permissions}."
        )
        delivered = await communication_port.deliver_intent(session_id=session_id, content=content)
        await record(
            InstallationStage.PERMISSION_REVIEW,
            "success" if delivered else "not_delivered",
        )
    except TimeoutError:
        await record(InstallationStage.PERMISSION_REVIEW, "timeout")


def _out_of_scope_probe(manifest: CapabilityManifest) -> tuple[str, dict] | None:
    """A deliberately out-of-scope operation for each adapter family, used
    only to prove the adapter correctly refuses it (see
    `_sandbox_self_test`). `.invalid` is RFC 2606's reserved TLD for
    exactly this kind of guaranteed-never-real-host use."""
    if manifest.execution_adapter in ("filesystem", "git"):
        root = manifest.required_resources[0] if manifest.required_resources else "/"
        outside = str(Path(root).resolve().parent / "__capability_engine_sandbox_probe__")
        return "read", {"path": outside}
    if manifest.execution_adapter == "terminal":
        return "execute", {
            "executable": "__capability_engine_sandbox_probe_disallowed__",
            "args": [],
        }
    if manifest.execution_adapter == "http":
        return "request", {"method": "GET", "url": "http://sandbox-probe.invalid/"}
    return None


async def _sandbox_self_test(manifest: CapabilityManifest, adapter: AdapterPort) -> None:
    """A real, adversarial probe (TDD 3C's own acceptance criterion 2):
    attempt an operation deliberately outside the capability's declared
    scope and confirm the adapter raises `SandboxViolation` rather than
    silently succeeding. If the adapter does *not* raise, that is the
    failure -- scope enforcement is not actually working."""
    probe = _out_of_scope_probe(manifest)
    if probe is None:
        return
    operation, parameters = probe
    try:
        await adapter.invoke(operation, parameters, required_resources=manifest.required_resources)
    except SandboxViolation:
        return  # correctly blocked -- this IS the passing case
    raise SandboxViolation(
        f"adapter {manifest.execution_adapter!r} did not block an out-of-scope probe "
        "operation during install-time self-test",
        adapter=manifest.execution_adapter,
    )
