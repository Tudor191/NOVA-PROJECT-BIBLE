"""Known projects: the operator's folder bindings, and the project identities
this engine learns from `memory.long_term.created` -- Phase 4F.8, A-4F8-2 (a)
and (a1) (TDD 4F.8 §29.1).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from nova_contracts import EventEnvelope
from nova_perception_engine.config import Settings
from nova_perception_engine.events.handlers import make_known_project_handler
from nova_perception_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from pydantic import ValidationError

from tests.fakes.repository import FakePerceptionRepository

USER_ID = uuid4()
SUBJECT = "memory.long_term.created"


def _memory(*, project_id: UUID | None, user_id: UUID = USER_ID) -> EventEnvelope:
    payload = {
        "memory_id": str(uuid4()),
        "user_id": str(user_id),
        "memory_type": "semantic",
        "importance_score": 0.5,
        "privacy_level": "internal",
    }
    if project_id is not None:
        payload["project_id"] = str(project_id)
    return EventEnvelope(
        subject=SUBJECT, source_engine="memory-engine", correlation_id=uuid4(), payload=payload
    )


# --- the subscription ----------------------------------------------------------


def test_the_one_new_subscription_is_the_existing_memory_subject() -> None:
    assert SUBJECT in SUBSCRIBABLE_SUBJECTS
    assert {
        "communication.session.created",
        "communication.session.completed",
        SUBJECT,
    } == SUBSCRIBABLE_SUBJECTS


async def test_a_memory_with_a_project_makes_that_project_known_once() -> None:
    repository = FakePerceptionRepository()
    handle = make_known_project_handler(repository, primary_user_id=USER_ID)
    project_id = uuid4()
    first = _memory(project_id=project_id)

    await handle(first)
    await handle(_memory(project_id=project_id))

    assert await repository.is_project_known(project_id)
    # Current state only: the first sighting stays, a repeat writes nothing.
    assert repository.known_projects == {project_id: (first.occurred_at, first.event_id)}


async def test_a_memory_without_a_project_makes_nothing_known() -> None:
    repository = FakePerceptionRepository()
    await make_known_project_handler(repository, primary_user_id=USER_ID)(
        _memory(project_id=None)
    )
    assert repository.known_projects == {}


async def test_another_users_memory_makes_nothing_known() -> None:
    repository = FakePerceptionRepository()
    project_id = uuid4()
    await make_known_project_handler(repository, primary_user_id=USER_ID)(
        _memory(project_id=project_id, user_id=uuid4())
    )
    assert not await repository.is_project_known(project_id)


async def test_with_no_configured_user_nothing_is_learned() -> None:
    """The same explicit degrade the workspace route applies: never a guessed
    identity."""
    repository = FakePerceptionRepository()
    project_id = uuid4()
    await make_known_project_handler(repository, primary_user_id=None)(
        _memory(project_id=project_id)
    )
    assert not await repository.is_project_known(project_id)


# --- the operator's declaration -----------------------------------------------


def test_no_folder_is_bound_by_default() -> None:
    assert Settings().project_folder_bindings == {}


def test_bindings_are_read_from_json_and_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    project_id = uuid4()
    monkeypatch.setenv(
        "PERCEPTION_ENGINE_PROJECT_FOLDER_BINDINGS", f'{{"/workspace/atlas/": "{project_id}"}}'
    )
    assert Settings().project_folder_bindings == {"/workspace/atlas": project_id}


@pytest.mark.parametrize("folder", ["workspace/atlas", "./atlas", "/", ""])
def test_a_relative_or_root_folder_is_refused(folder: str) -> None:
    with pytest.raises(ValidationError):
        Settings(project_folder_bindings={folder: uuid4()})


async def test_the_first_sighting_is_dated_by_the_event_not_by_a_clock() -> None:
    """The handler records the envelope's own time, so a project first seen in
    an event published at 09:00 is recorded at 09:00, whenever it is handled."""
    repository = FakePerceptionRepository()
    project_id = uuid4()
    moment = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
    envelope = _memory(project_id=project_id).model_copy(update={"occurred_at": moment})

    await make_known_project_handler(repository, primary_user_id=USER_ID)(envelope)

    assert repository.known_projects[project_id] == (moment, envelope.event_id)
