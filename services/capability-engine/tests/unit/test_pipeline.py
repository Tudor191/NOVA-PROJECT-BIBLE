"""`domain/pipeline.py`'s `install_capability` -- the real 8-stage
Installation Pipeline (TDD 3C §2.3), fake-repository-backed per this
project's own two-tier testing convention (ADR-033): pipeline *orchestration*
is exercised here; real adapter I/O is exercised separately in
`test_filesystem_adapter.py`/`test_terminal_adapter.py`/`test_git_adapter.py`/
`test_http_adapter.py`."""

from __future__ import annotations

from uuid import uuid4

import pytest
from nova_capability_engine.domain.models import CapabilityManifest
from nova_capability_engine.domain.pipeline import (
    InstallationError,
    InstallationStage,
    install_capability,
)

from tests.fakes.adapters import RecordingAdapter, UnenforcedAdapter
from tests.fakes.communication_port import FakeCommunicationPort
from tests.fakes.repository import FakeCapabilityRepository

_MANIFEST_SCHEMA: dict = {"type": "object"}


def _manifest(**overrides: object) -> CapabilityManifest:
    defaults: dict[str, object] = {
        "name": "test-capability",
        "description": "a test capability",
        "category": "test",
        "version": "1.0.0",
        "required_permissions": ["filesystem:read"],
        "required_resources": ["/workspace"],
        "input_schema": _MANIFEST_SCHEMA,
        "output_schema": _MANIFEST_SCHEMA,
        "execution_adapter": "recording",
    }
    defaults.update(overrides)
    return CapabilityManifest(**defaults)  # type: ignore[arg-type]


async def test_a_successful_install_registers_the_capability_as_healthy() -> None:
    repository = FakeCapabilityRepository()
    adapters = {"recording": RecordingAdapter()}

    capability = await install_capability(
        _manifest(),
        repository=repository,
        adapters=adapters,
        communication_port=None,
        primary_user_id=None,
    )

    assert capability.name == "test-capability"
    assert capability.health_status == "healthy"
    assert repository.capabilities[capability.id] == capability


async def test_a_successful_install_records_every_stage_as_success_in_order() -> None:
    repository = FakeCapabilityRepository()
    adapters = {"recording": RecordingAdapter()}

    await install_capability(
        _manifest(),
        repository=repository,
        adapters=adapters,
        communication_port=None,
        primary_user_id=None,
    )

    stages = [e["stage"] for e in repository.installation_events]
    assert stages == [s.value for s in InstallationStage]
    assert all(e["outcome"] in ("success", "skipped") for e in repository.installation_events)


async def test_on_stage_callback_is_invoked_once_per_stage() -> None:
    repository = FakeCapabilityRepository()
    adapters = {"recording": RecordingAdapter()}
    observed: list[tuple[InstallationStage, str]] = []

    async def on_stage(stage: InstallationStage, outcome: str) -> None:
        observed.append((stage, outcome))

    await install_capability(
        _manifest(),
        repository=repository,
        adapters=adapters,
        communication_port=None,
        primary_user_id=None,
        on_stage=on_stage,
    )

    assert len(observed) == len(list(InstallationStage))
    assert observed[0][0] == InstallationStage.DOWNLOAD
    assert observed[-1][0] == InstallationStage.ACTIVATION


async def test_reinstalling_the_same_name_and_version_returns_the_existing_row() -> None:
    repository = FakeCapabilityRepository()
    adapters = {"recording": RecordingAdapter()}

    first = await install_capability(
        _manifest(),
        repository=repository,
        adapters=adapters,
        communication_port=None,
        primary_user_id=None,
    )
    second = await install_capability(
        _manifest(),
        repository=repository,
        adapters=adapters,
        communication_port=None,
        primary_user_id=None,
    )

    assert first.id == second.id
    assert len(repository.capabilities) == 1
    # No stage events recorded for the idempotent no-op path -- it returns
    # before stage 1, per the pipeline's own documented framing.
    assert len(repository.installation_events) == len(list(InstallationStage))


async def test_a_concurrent_install_race_is_treated_as_the_same_idempotent_no_op() -> None:
    """Fork 3C-4: a `CapabilityAlreadyExistsError` raised by `insert()` (a
    concurrent installer winning an already-passed pre-check) is treated
    identically to the pre-check idempotent path, never a hard failure."""

    class _RaceyRepository(FakeCapabilityRepository):
        """Its first `find_by_name_version` call (the pipeline's own
        pre-check) returns `None`, as if this installer's pre-check ran
        before a concurrent winner committed. Its `insert()` then raises,
        exactly as a real `UNIQUE (name, version)` violation would. Every
        `find_by_name_version` call after that -- including the pipeline's
        own Fork 3C-4 recovery lookup -- sees the winner that is pre-seeded
        into `capabilities`."""

        def __init__(self) -> None:
            super().__init__()
            self._precheck_done = False

        async def find_by_name_version(self, *, name: str, version: str):  # type: ignore[override]
            if not self._precheck_done:
                self._precheck_done = True
                return None
            return await super().find_by_name_version(name=name, version=version)

        async def insert(self, capability: object) -> object:  # type: ignore[override]
            from nova_capability_engine.domain.ports import CapabilityAlreadyExistsError

            raise CapabilityAlreadyExistsError("simulated concurrent-install race")

    seed_repository = FakeCapabilityRepository()
    adapters = {"recording": RecordingAdapter()}
    manifest = _manifest()
    winner = await install_capability(
        manifest,
        repository=seed_repository,
        adapters=adapters,
        communication_port=None,
        primary_user_id=None,
    )

    racey_repository = _RaceyRepository()
    racey_repository.capabilities[winner.id] = winner

    result = await install_capability(
        manifest,
        repository=racey_repository,
        adapters=adapters,
        communication_port=None,
        primary_user_id=None,
    )

    assert result.id == winner.id
    assert len(racey_repository.capabilities) == 1


async def test_a_missing_dependency_halts_at_dependency_resolution() -> None:
    repository = FakeCapabilityRepository()
    adapters = {"recording": RecordingAdapter()}

    with pytest.raises(InstallationError) as exc_info:
        await install_capability(
            _manifest(dependencies=["nonexistent-capability"]),
            repository=repository,
            adapters=adapters,
            communication_port=None,
            primary_user_id=None,
        )

    assert exc_info.value.stage == InstallationStage.DEPENDENCY_RESOLUTION
    assert repository.capabilities == {}


async def test_a_circular_dependency_halts_at_dependency_resolution() -> None:
    repository = FakeCapabilityRepository()
    adapters = {"recording": RecordingAdapter()}

    # Install "a" depending on nothing, then "b" depending on "a" -- both
    # succeed. Then attempt to reinstall "a" as version 2.0.0 depending on
    # "b", which (transitively, via "a" -> "b" -> "a") would be circular.
    await install_capability(
        _manifest(name="a", version="1.0.0"),
        repository=repository,
        adapters=adapters,
        communication_port=None,
        primary_user_id=None,
    )
    await install_capability(
        _manifest(name="b", version="1.0.0", dependencies=["a"]),
        repository=repository,
        adapters=adapters,
        communication_port=None,
        primary_user_id=None,
    )

    with pytest.raises(InstallationError) as exc_info:
        await install_capability(
            _manifest(name="a", version="2.0.0", dependencies=["b"]),
            repository=repository,
            adapters=adapters,
            communication_port=None,
            primary_user_id=None,
        )
    assert exc_info.value.stage == InstallationStage.DEPENDENCY_RESOLUTION


async def test_no_registered_adapter_for_the_execution_adapter_halts_at_sandbox_testing() -> None:
    repository = FakeCapabilityRepository()

    with pytest.raises(InstallationError) as exc_info:
        await install_capability(
            _manifest(execution_adapter="nonexistent-adapter"),
            repository=repository,
            adapters={},
            communication_port=None,
            primary_user_id=None,
        )

    assert exc_info.value.stage == InstallationStage.SANDBOX_TESTING
    assert repository.capabilities == {}


async def test_an_adapter_that_fails_to_enforce_its_own_sandbox_never_reaches_registration() -> (
    None
):
    """TDD 3C's acceptance criterion 2: if the adversarial self-test probe
    is *not* blocked, that proves scope enforcement is broken -- the
    capability must never reach Registration/Activation."""
    repository = FakeCapabilityRepository()
    adapters = {"filesystem": UnenforcedAdapter()}

    with pytest.raises(InstallationError) as exc_info:
        await install_capability(
            _manifest(execution_adapter="filesystem", required_resources=["/workspace"]),
            repository=repository,
            adapters=adapters,
            communication_port=None,
            primary_user_id=None,
        )

    assert exc_info.value.stage == InstallationStage.SANDBOX_TESTING
    assert repository.capabilities == {}
    stages = [e["stage"] for e in repository.installation_events]
    assert InstallationStage.REGISTRATION.value not in stages


async def test_permission_review_is_skipped_and_recorded_when_no_primary_user_is_configured() -> (
    None
):
    repository = FakeCapabilityRepository()
    adapters = {"recording": RecordingAdapter()}

    await install_capability(
        _manifest(),
        repository=repository,
        adapters=adapters,
        communication_port=FakeCommunicationPort(session_id=uuid4()),
        primary_user_id=None,
    )

    review_events = [
        e for e in repository.installation_events if e["stage"] == "permission_review"
    ]
    assert review_events == [
        {
            "capability_id": None,
            "name": "test-capability",
            "version": "1.0.0",
            "stage": "permission_review",
            "outcome": "skipped",
            "detail": "no primary_user_id configured",
        }
    ]


async def test_permission_review_delivers_a_disclosure_when_a_session_is_connected() -> None:
    repository = FakeCapabilityRepository()
    adapters = {"recording": RecordingAdapter()}
    communication_port = FakeCommunicationPort(session_id=uuid4())

    await install_capability(
        _manifest(),
        repository=repository,
        adapters=adapters,
        communication_port=communication_port,
        primary_user_id=uuid4(),
    )

    assert len(communication_port.delivered_content) == 1
    assert "test-capability" in communication_port.delivered_content[0]


async def test_permission_review_is_skipped_and_recorded_when_no_session_is_connected() -> None:
    repository = FakeCapabilityRepository()
    adapters = {"recording": RecordingAdapter()}
    communication_port = FakeCommunicationPort(session_id=None)

    await install_capability(
        _manifest(),
        repository=repository,
        adapters=adapters,
        communication_port=communication_port,
        primary_user_id=uuid4(),
    )

    review_events = [
        e for e in repository.installation_events if e["stage"] == "permission_review"
    ]
    assert review_events[0]["outcome"] == "skipped"
    assert review_events[0]["detail"] == "no connected session"


async def test_permission_review_timeout_is_recorded_and_never_halts_the_pipeline() -> None:
    repository = FakeCapabilityRepository()
    adapters = {"recording": RecordingAdapter()}
    communication_port = FakeCommunicationPort(session_id=uuid4(), raise_timeout=True)

    capability = await install_capability(
        _manifest(),
        repository=repository,
        adapters=adapters,
        communication_port=communication_port,
        primary_user_id=uuid4(),
    )

    assert capability.health_status == "healthy"
    review_events = [
        e for e in repository.installation_events if e["stage"] == "permission_review"
    ]
    assert review_events[0]["outcome"] == "timeout"
