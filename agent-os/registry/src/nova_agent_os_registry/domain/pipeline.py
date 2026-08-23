"""The real 8-step Agent Package Installation Pipeline (TDD 3E §5, doc 12
§6's flowchart: Discover -> **Fetch -> Integrity verification -> Manifest
validation -> Dependency & capability resolution -> Permission review ->
Sandbox test run -> Register -> on_load invoked (-> Idle)** -- the eight
steps counted for one package; "Discover" is the enumeration loop that
calls `install_agent_package()` once per `discover_agent_packages()`
result, "Idle"/"Available for scheduling" is the terminal state
description, neither is a pipeline step of its own, consistent with TDD
3E's own "8-step" naming and the user's own Milestone 3 instruction).

Framework-free (docs/architecture/03-backend-architecture.md §1) beyond
plain file I/O (`pathlib`), `hashlib`, and `yaml.safe_load` -- no FastAPI,
SQLAlchemy, or `nova_eventbus_sdk` import. Structurally modeled on
`capability-engine`'s own `domain/pipeline.py::install_capability` (TDD 3E
§5's own text: "agent-os/registry is structurally the Capability Registry
... applied to agents") -- same `InstallationStage`/`InstallationError`/
`on_stage` callback shape, adapted for genuinely filesystem-discovered
packages (unlike capability-engine's bundled, already-in-memory manifests):
idempotency can only be pre-checked *after* Fetch + Manifest Validation
have actually parsed `agent.yaml`, not before Fetch, since there is
nothing to key on before that.

**Natural-key resolution, disclosed.** TDD 3E §5's own text reads:
"the Registry's persistence keys on `(category, version)`, not `category`
alone" -- but doc 12 §6's own worked example versions `coding-agent@1.2.0`/
`coding-agent@1.3.0` (the package's own `id`, not its taxonomy `category`),
and TDD 3E §5's very same sentence states the purpose is multi-version
coexistence "per agent" (per package identity). Keying uniqueness on
`category` alone (or `(category, version)`) would incorrectly forbid two
*different* packages sharing one category (e.g. two distinct `"coding"`-
category agents) from ever coexisting -- the opposite of what
category-based Kernel Scheduler dispatch (doc 12 §7: "query Registry for
healthy candidates in the required category") requires categories to
allow. Resolved here as `(id, version)`, matching doc 12's own worked
example and mirroring `capability-engine`'s own `(name, version)`/Fork
3C-4 precedent exactly (`name`/`id` playing the identical role). Flagged
prominently for the Phase 3E Gate Review and for explicit confirmation.

**Update, Phase 3E Supervisor milestone reconciliation pass
(`docs/design/phase-3/15-3e-supervisor-reconciliation.md` §A).** This is
*not* merely a wording discrepancy, as first disclosed above -- tracing it
through TDD 3E §4's own Fork 3E-2 resolution note shows the *already-
approved* concrete ORM (`14-3e-agent-os-research.md` §4) uses a UUID
surrogate `id` and a `UniqueConstraint("category", "version")`, matching
TDD 3E §5's literal wording exactly, and Kernel's own already-built
`agent_instance.agent_package_id` column (Milestone 2) is typed `UUID` to
match it -- a real, disclosed schema mismatch against *this* module's own
`(id: str, version: str)` composite-key choice. Genuinely stopped, not
resolved; see that document for the full evidence chain and the options
left for the user's decision. Not changed here on this pass's own
authority.

**Sandbox Test Run, disclosed.** Fork E3's "lighter OS-level scoping"
(TDD 3C §3) constrains what capability *adapters* may touch (filesystem/
terminal/http path- and host-allow-lists) -- it has no analogue for
arbitrary in-process Python code, which is what an Agent Package's
`handler.py` is (doc 12 §8: `inprocess` is Phase 3's only execution
backend, an asyncio task in the Kernel's own process). No behavioral
execution sandboxing mechanism exists anywhere in this project for that
case. This stage therefore validates *structural* conformance only --
the module imports cleanly and the resulting `Handler` satisfies
`AgentHandler` (`nova_agent_sdk`'s `@runtime_checkable` Protocol) -- a
real, meaningful gate before Registration, not a no-op, but explicitly not
full behavioral isolation. Disclosed, not silently implied to be more than
it is (mirrors `nova_capability_engine.domain.sandbox`'s own disclosed-
limitation discipline).

**Confirmed, Phase 3E Supervisor milestone reconciliation pass
(`docs/design/phase-3/15-3e-supervisor-reconciliation.md` §B).** Structural
conformance only is the intended, correct scope for Phase 3 -- doc 12 §8's
own execution-backend table shows the Sandbox Test Run's real purpose
(gating `inprocess`/`subprocess` -> `container` trust promotion) is inert
while `inprocess` is the only implemented backend, and
`14-3e-agent-os-research.md` §8a independently confirms this project's
actual enforcement boundary is `capability-engine`'s own OS-level
sandboxing, exercised downstream at `action.execute()` time, never the
Registry's own install-time gate. No implementation change follows from
this confirmation.
"""

from __future__ import annotations

import hashlib
import importlib.util
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from uuid import UUID

import yaml
from nova_agent_sdk import AgentHandler, AgentManifest
from pydantic import ValidationError

from nova_agent_os_registry.domain.discovery import DiscoveredPackage
from nova_agent_os_registry.domain.models import AgentPackage
from nova_agent_os_registry.domain.ports import (
    AgentPackageAlreadyExistsError,
    CommunicationPort,
    RegistryRepository,
)

__all__ = ["InstallationError", "InstallationStage", "install_agent_package"]


class InstallationStage(StrEnum):
    FETCH = "fetch"
    INTEGRITY_VERIFICATION = "integrity_verification"
    MANIFEST_VALIDATION = "manifest_validation"
    DEPENDENCY_RESOLUTION = "dependency_resolution"
    PERMISSION_REVIEW = "permission_review"
    SANDBOX_TEST = "sandbox_test"
    REGISTRATION = "registration"
    ON_LOAD = "on_load"


class InstallationError(Exception):
    """Every raise site records the failing stage -- mirrors
    `capability-engine`'s own `InstallationError`, TDD 3C §8's "install
    pipeline halts... no partial registration" discipline, extended here:
    an `ON_LOAD` failure is the one stage that does *not* raise (see
    `install_agent_package`'s own docstring), since doc 12 §6's flowchart
    already committed Registration by the time `on_load` runs."""

    def __init__(self, message: str, *, stage: InstallationStage) -> None:
        super().__init__(message)
        self.stage = stage


class _RecordFn(Protocol):
    async def __call__(
        self, stage: InstallationStage, outcome: str, detail: str | None = None
    ) -> None: ...


def _version_tuple(version: str) -> tuple[int, ...]:
    """Dotted-integer comparison, e.g. `"1.0.0"` -> `(1, 0, 0)` --
    deliberately not a full semver parser (no pre-release/build-metadata
    handling): every version this project has ever assigned an engine or
    component is a plain `MAJOR.MINOR.PATCH` string, and doc 12/TDD 3E
    name no richer version grammar."""
    return tuple(int(part) for part in version.split("."))


class _KernelVersionTooOldError(Exception):
    pass


def _check_kernel_compatibility(manifest: AgentManifest, *, kernel_version: str) -> None:
    required = _version_tuple(manifest.compatibility.min_kernel_version)
    actual = _version_tuple(kernel_version)
    if actual < required:
        raise _KernelVersionTooOldError(
            f"package requires kernel >= {manifest.compatibility.min_kernel_version}, "
            f"running kernel is {kernel_version}"
        )


def _load_handler_class(handler_path: Path) -> type:
    """Dynamically imports `src/handler.py` and returns its `Handler`
    class -- used by both Sandbox Test (structural conformance only) and
    On Load (an actual instantiated call)."""
    spec = importlib.util.spec_from_file_location("_agent_package_handler", handler_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load a module spec from {handler_path!r}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    handler_class = getattr(module, "Handler", None)
    if handler_class is None:
        raise ImportError(f"{handler_path!r} does not define a top-level 'Handler' class")
    return handler_class


async def install_agent_package(
    package: DiscoveredPackage,
    *,
    repository: RegistryRepository,
    communication_port: CommunicationPort | None,
    primary_user_id: UUID | None,
    kernel_version: str,
    on_stage: Callable[[InstallationStage, str], Awaitable[None]] | None = None,
) -> AgentPackage:
    """Runs the real 8-step pipeline for one discovered Agent Package.

    Idempotency (mirroring Fork 3C-4, adapted for filesystem discovery --
    see this module's own docstring): checked *after* Fetch + Manifest
    Validation, the earliest point `(manifest.id, manifest.version)` is
    known. If a row already exists, returns it immediately -- no stage
    re-runs beyond the two needed to learn the key.
    """

    async def _record(stage: InstallationStage, outcome: str, detail: str | None = None) -> None:
        if on_stage is not None:
            await on_stage(stage, outcome)
        _ = detail  # available to callers that want it; not persisted by this domain fn

    # 1. Fetch -- read the manifest and handler source off disk. Phase 3's
    # sole discovery mode is the local filesystem (doc 12 §15); no network
    # fetch exists yet.
    try:
        manifest_bytes = package.manifest_path.read_bytes()
        handler_bytes = package.handler_path.read_bytes()
    except OSError as exc:
        await _record(InstallationStage.FETCH, "failure", str(exc))
        raise InstallationError(
            f"could not read package files under {package.directory}: {exc}",
            stage=InstallationStage.FETCH,
        ) from exc
    await _record(InstallationStage.FETCH, "success")

    # 2. Integrity Verification -- a real SHA-256 digest over both files,
    # stored on the registered row. No cryptographic *signature*
    # verification: no signing/PKI infrastructure exists anywhere in this
    # project (disclosed, matching TDD 3E §5's own "no nova-auth" gap
    # treatment) -- a future signed package slots its check into this same
    # stage without changing the pipeline's shape.
    if not manifest_bytes or not handler_bytes:
        await _record(InstallationStage.INTEGRITY_VERIFICATION, "failure", "empty file")
        raise InstallationError(
            f"package under {package.directory} has an empty agent.yaml or handler.py",
            stage=InstallationStage.INTEGRITY_VERIFICATION,
        )
    checksum = hashlib.sha256(manifest_bytes + handler_bytes).hexdigest()
    await _record(InstallationStage.INTEGRITY_VERIFICATION, "success")

    # 3. Manifest Validation -- parse agent.yaml and validate against
    # AgentManifest (nova_agent_sdk).
    try:
        raw_manifest = yaml.safe_load(manifest_bytes)
        manifest = AgentManifest.model_validate(raw_manifest)
    except (yaml.YAMLError, ValidationError) as exc:
        await _record(InstallationStage.MANIFEST_VALIDATION, "failure", str(exc))
        raise InstallationError(
            f"agent.yaml under {package.directory} failed manifest validation: {exc}",
            stage=InstallationStage.MANIFEST_VALIDATION,
        ) from exc
    await _record(InstallationStage.MANIFEST_VALIDATION, "success")

    existing = await repository.find_by_id_version(manifest.id, manifest.version)
    if existing is not None:
        return existing

    # 4. Dependency & Capability Resolution -- structural only
    # (`required_capabilities` existence against capability-engine is not
    # live-checked, the same declared-intent-only treatment Fork 3C-2
    # already gives the Kernel Scheduler, TDD 3E §4). Two real, meaningful
    # checks that require no live RPC: (a) at least one declared backend
    # is actually enabled in Phase 3 (`inprocess`), since the Kernel can
    # never dispatch a package declaring only unimplemented backends; (b)
    # `compatibility.min_kernel_version` is satisfiable against the
    # running Kernel's own version.
    if "inprocess" not in manifest.supported_execution_backends:
        detail = (
            f"declared backends {manifest.supported_execution_backends} include none "
            "Phase 3 implements ('inprocess')"
        )
        await _record(InstallationStage.DEPENDENCY_RESOLUTION, "failure", detail)
        raise InstallationError(
            f"agent {manifest.id!r} declares no Phase-3-enabled execution backend: {detail}",
            stage=InstallationStage.DEPENDENCY_RESOLUTION,
        )
    try:
        _check_kernel_compatibility(manifest, kernel_version=kernel_version)
    except _KernelVersionTooOldError as exc:
        await _record(InstallationStage.DEPENDENCY_RESOLUTION, "failure", str(exc))
        raise InstallationError(
            f"agent {manifest.id!r} is incompatible with the running kernel: {exc}",
            stage=InstallationStage.DEPENDENCY_RESOLUTION,
        ) from exc
    await _record(InstallationStage.DEPENDENCY_RESOLUTION, "success")

    # 5. Permission Review -- local diff-and-display (TDD 3E §5's
    # resolved note): diff against the previously-installed version's own
    # declared permissions (or the empty list, first install), surfaced
    # to the user via the same best-effort, non-blocking
    # CommunicationPort delivery `capability-engine`'s own Permission
    # Review stage already established (TDD 3C §10) -- never blocks the
    # pipeline, never a nova-auth.authorize() call.
    previous = await repository.find_latest_by_id(manifest.id)
    previous_permissions: set[str] = (
        set(previous.manifest_json.get("required_permissions", []))
        if previous is not None
        else set()
    )
    new_permissions = sorted(set(manifest.required_permissions) - previous_permissions)
    await _attempt_permission_review_disclosure(
        manifest,
        new_permissions=new_permissions,
        communication_port=communication_port,
        primary_user_id=primary_user_id,
        record=_record,
    )

    # 6. Sandbox Test Run -- structural conformance only (see module
    # docstring): dynamic import succeeds and the Handler class satisfies
    # AgentHandler.
    try:
        handler_class = _load_handler_class(package.handler_path)
    except Exception as exc:  # noqa: BLE001 -- any import-time failure is this stage's outcome
        await _record(InstallationStage.SANDBOX_TEST, "failure", str(exc))
        raise InstallationError(
            f"agent {manifest.id!r}'s handler.py failed to import: {exc}",
            stage=InstallationStage.SANDBOX_TEST,
        ) from exc
    if not issubclass(handler_class, AgentHandler):
        detail = f"{handler_class!r} does not structurally satisfy AgentHandler"
        await _record(InstallationStage.SANDBOX_TEST, "failure", detail)
        raise InstallationError(
            f"agent {manifest.id!r}'s Handler class does not satisfy the AgentHandler Protocol",
            stage=InstallationStage.SANDBOX_TEST,
        )
    await _record(InstallationStage.SANDBOX_TEST, "success")

    # 7. Registration
    agent_package = AgentPackage(
        id=manifest.id,
        category=manifest.category,
        version=manifest.version,
        manifest_json=manifest.model_dump(mode="json"),
        installed_at=datetime.now(UTC),
        health_status="unknown",
        checksum=checksum,
        supervisor_notified_new_permissions=new_permissions,
    )
    try:
        agent_package = await repository.insert(agent_package)
    except AgentPackageAlreadyExistsError:
        # A concurrent installer won the race between our own pre-check
        # and this insert -- treat identically to the pre-check
        # idempotent-no-op path (Fork 3C-4's precedent), never a hard
        # failure.
        raced = await repository.find_by_id_version(manifest.id, manifest.version)
        if raced is not None:
            await _record(InstallationStage.REGISTRATION, "already_exists")
            return raced
        raise
    await _record(InstallationStage.REGISTRATION, "success")

    # 8. on_load invoked -> Idle. Registration has already committed by
    # this point (doc 12 §6's own flowchart ordering: Register precedes
    # on_load) -- an on_load failure does not roll back the just-created
    # row, it simply leaves health_status at "unknown" rather than
    # promoting it to "healthy", a real, disclosed, non-silent state.
    try:
        handler_instance = handler_class()
        await handler_instance.on_load(manifest)
    except Exception as exc:  # noqa: BLE001 -- recorded, not re-raised (see docstring)
        await _record(InstallationStage.ON_LOAD, "failure", str(exc))
        return agent_package
    await repository.update_health_status(manifest.id, manifest.version, health_status="healthy")
    agent_package = agent_package.model_copy(update={"health_status": "healthy"})
    await _record(InstallationStage.ON_LOAD, "success")
    return agent_package


async def _attempt_permission_review_disclosure(
    manifest: AgentManifest,
    *,
    new_permissions: list[str],
    communication_port: CommunicationPort | None,
    primary_user_id: UUID | None,
    record: _RecordFn,
) -> None:
    if not new_permissions:
        await record(InstallationStage.PERMISSION_REVIEW, "no_new_permissions")
        return
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
            f"Agent package installed: {manifest.id!r} (v{manifest.version}), "
            f"requesting new permissions: {new_permissions}."
        )
        delivered = await communication_port.deliver_intent(session_id=session_id, content=content)
        await record(
            InstallationStage.PERMISSION_REVIEW,
            "success" if delivered else "not_delivered",
        )
    except TimeoutError:
        await record(InstallationStage.PERMISSION_REVIEW, "timeout")
