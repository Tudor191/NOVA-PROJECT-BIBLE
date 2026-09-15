"""`handle_workspace_event` -- TDD 4F §8.1's structured intake.

The branches that matter are the ones that publish **nothing**: a sensor that
is no longer running, and an unconfigured `primary_user_id`. Both are ratified
degrades, and both would be easy to regress into a silent publish.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from nova_perception_engine.domain.workspace import (
    WorkspaceObservationDebouncer,
    object_id_for_path,
)
from nova_perception_engine.workspace_orchestration import (
    WorkspaceObservationRequest,
    handle_workspace_event,
)

from tests.fakes.repository import FakePerceptionRepository
from tests.fakes.sensor import FakeSensor

PATH = "/home/ada/projects/analytical-engine/notes.md"
USER_ID = uuid4()


def _app(
    *,
    sensor_state: str = "running",
    primary_user_id: UUID | None = USER_ID,
    known_projects: dict | None = None,
    debounce_seconds: float = 1.0,
) -> tuple[SimpleNamespace, FakePerceptionRepository]:
    repository = FakePerceptionRepository()
    sensor = FakeSensor(state=sensor_state)  # type: ignore[arg-type]
    state = SimpleNamespace(
        sensors_by_source={"filesystem": sensor},
        settings=SimpleNamespace(primary_user_id=primary_user_id),
        repository=repository,
        known_projects=known_projects if known_projects is not None else {},
        workspace_debouncer=WorkspaceObservationDebouncer(
            window=timedelta(seconds=debounce_seconds)
        ),
    )
    return SimpleNamespace(state=state), repository



def _rows(repository: FakePerceptionRepository) -> list:
    """`FakePerceptionRepository.outbox` is a `dict[UUID, OutboxRow]` keyed by
    row id, matching the real table; these tests care about what was enqueued,
    not about the ids."""
    return list(repository.outbox.values())


def _request(*, at: datetime | None = None, path: str = PATH) -> WorkspaceObservationRequest:
    return WorkspaceObservationRequest(path=path, observed_at=at or datetime.now(UTC))


async def test_an_unknown_source_returns_none_for_the_caller_to_404() -> None:
    app, _ = _app()
    assert await handle_workspace_event(app, source="nope", request=_request()) is None


async def test_a_well_formed_observation_is_enqueued_on_the_outbox() -> None:
    """Not published directly: the transactional outbox is the only path,
    so replay and ordering keep the guarantees every other subject has."""
    app, repository = _app()
    outcome = await handle_workspace_event(app, source="filesystem", request=_request())

    assert outcome is not None and outcome.published is True
    assert len(_rows(repository)) == 1
    assert _rows(repository)[0].subject == "perception.workspace.observed"


async def test_the_enqueued_payload_carries_the_hash_and_never_the_path() -> None:
    app, repository = _app()
    await handle_workspace_event(app, source="filesystem", request=_request())

    payload = _rows(repository)[0].payload
    assert payload["object_id"] == object_id_for_path(PATH)
    assert PATH not in str(payload)
    for segment in ("home", "ada", "analytical-engine"):
        assert segment not in str(payload)
    assert payload["label"] == "notes.md"


async def test_a_sensor_that_is_not_running_publishes_nothing() -> None:
    """§9: *"drop any signal whose sensor is not `running`"* -- what makes
    AC-7's revocation clause true at the pipeline level, not only at the
    sensor. An in-flight observation must not slip through behind a pause."""
    for state in ("paused", "stopped", "failed", "initialized"):
        app, repository = _app(sensor_state=state)
        outcome = await handle_workspace_event(app, source="filesystem", request=_request())

        assert outcome is not None
        assert outcome.published is False
        assert outcome.reason == "sensor_not_running"
        assert _rows(repository) == []


async def test_an_unconfigured_primary_user_id_publishes_nothing() -> None:
    """The ratified degrade: never a guessed identity, never a fabricated
    user -- and never a published event carrying one."""
    app, repository = _app(primary_user_id=None)
    outcome = await handle_workspace_event(app, source="filesystem", request=_request())

    assert outcome is not None
    assert outcome.published is False
    assert outcome.reason == "primary_user_id_not_configured"
    assert _rows(repository) == []


async def test_the_user_id_comes_from_settings_not_from_the_request() -> None:
    """The identity boundary. The companion does not get a say."""
    app, repository = _app()
    await handle_workspace_event(app, source="filesystem", request=_request())
    assert _rows(repository)[0].payload["user_id"] == str(USER_ID)


def test_the_request_model_has_no_user_id_field_to_supply() -> None:
    """A client-supplied `user_id` is not rejected at runtime -- it is
    **unrepresentable**. Pydantic ignores the unknown key, and there is no
    field for it to land in, so there is no path by which one could ever
    override `primary_user_id`."""
    assert "user_id" not in WorkspaceObservationRequest.model_fields
    assert "object_id" not in WorkspaceObservationRequest.model_fields


async def test_a_client_supplied_user_id_cannot_override_the_configured_one() -> None:
    """The same property, exercised end to end with an attacker-shaped body."""
    app, repository = _app()
    hostile = uuid4()
    request = WorkspaceObservationRequest.model_validate(
        {"path": PATH, "observed_at": datetime.now(UTC).isoformat(), "user_id": str(hostile)}
    )
    await handle_workspace_event(app, source="filesystem", request=request)

    payload = _rows(repository)[0].payload
    assert payload["user_id"] == str(USER_ID)
    assert str(hostile) not in str(payload)


async def test_a_failed_project_correlation_publishes_without_a_project_id() -> None:
    app, repository = _app(known_projects={})
    await handle_workspace_event(app, source="filesystem", request=_request())
    assert _rows(repository)[0].payload["project_id"] is None


async def test_a_successful_project_correlation_is_attached() -> None:
    project_id = uuid4()
    app, repository = _app(known_projects={object_id_for_path(PATH): project_id})
    await handle_workspace_event(app, source="filesystem", request=_request())
    assert _rows(repository)[0].payload["project_id"] == str(project_id)


async def test_the_real_observed_at_is_preserved_not_replaced_by_now() -> None:
    """§20.1: the timestamp is the real OS event time and the start of AC-7's
    measured interval. Substituting the server's clock would look identical
    and make that interval wrong."""
    moment = datetime.now(UTC) - timedelta(minutes=17)
    app, repository = _app()
    await handle_workspace_event(app, source="filesystem", request=_request(at=moment))

    published = datetime.fromisoformat(_rows(repository)[0].payload["observed_at"])
    assert published == moment


async def test_a_burst_publishes_once() -> None:
    app, repository = _app()
    start = datetime.now(UTC)
    for offset in (0.0, 0.2, 0.5, 0.9):
        await handle_workspace_event(
            app, source="filesystem", request=_request(at=start + timedelta(seconds=offset))
        )

    assert len(_rows(repository)) == 1


async def test_a_debounced_observation_says_why_it_was_dropped() -> None:
    app, _ = _app()
    start = datetime.now(UTC)
    await handle_workspace_event(app, source="filesystem", request=_request(at=start))
    outcome = await handle_workspace_event(
        app, source="filesystem", request=_request(at=start + timedelta(seconds=0.1))
    )

    assert outcome is not None
    assert outcome.published is False
    assert outcome.reason == "debounced"


async def test_a_separate_edit_after_the_window_publishes_again() -> None:
    app, repository = _app()
    start = datetime.now(UTC)
    await handle_workspace_event(app, source="filesystem", request=_request(at=start))
    await handle_workspace_event(
        app, source="filesystem", request=_request(at=start + timedelta(seconds=2))
    )

    assert len(_rows(repository)) == 2


async def test_the_object_type_is_always_the_closed_literal() -> None:
    app, repository = _app()
    await handle_workspace_event(app, source="filesystem", request=_request())
    assert _rows(repository)[0].payload["object_type"] == "project"


@pytest.mark.parametrize("bad_path", ["", "   "])
async def test_an_empty_path_is_rejected_rather_than_hashed(bad_path: str) -> None:
    app, _ = _app()
    with pytest.raises(ValueError, match="must not be empty"):
        await handle_workspace_event(app, source="filesystem", request=_request(path=bad_path))
