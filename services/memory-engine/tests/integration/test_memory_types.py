"""`domain/short_term.py`, `domain/working.py`, `domain/sensory.py`, and the thin
per-type wrappers (`semantic.py`, `procedural.py`, `episodic.py`, `project.py`,
`preference.py`) -- docs/design/phase-1/01-memory-engine.md §2.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from nova_memory_engine.domain import (
    episodic,
    preference,
    procedural,
    project,
    semantic,
    sensory,
    short_term,
    working,
)
from nova_memory_engine.domain.models import MemoryType

from tests.fakes.memory_repository import FakeMemoryRepository
from tests.fakes.working_memory_store import FakeWorkingMemoryStore


async def test_short_term_remember_sets_expiry_from_ttl() -> None:
    repo = FakeMemoryRepository()
    user_id = uuid4()

    record = await short_term.remember(
        repo,
        user_id=user_id,
        content="recently opened file.py",
        category="recent_file",
        correlation_id=uuid4(),
        ttl=timedelta(hours=1),
    )

    assert record.expires_at > datetime.now(UTC)
    assert record.expires_at <= datetime.now(UTC) + timedelta(hours=1, minutes=1)


async def test_short_term_recall_recent_scoped_to_user() -> None:
    repo = FakeMemoryRepository()
    owner = uuid4()
    await short_term.remember(
        repo, user_id=owner, content="mine", category="recent_conversation", correlation_id=uuid4()
    )
    await short_term.remember(
        repo,
        user_id=uuid4(),
        content="not mine",
        category="recent_conversation",
        correlation_id=uuid4(),
    )

    recent = await short_term.recall_recent(repo, user_id=owner)

    assert [r.content for r in recent] == ["mine"]


async def test_working_memory_remember_and_recall() -> None:
    store = FakeWorkingMemoryStore()
    user_id = uuid4()

    await working.remember(
        store, user_id=user_id, session_id="s1", key="current_file", value="a.py"
    )
    await working.remember(
        store, user_id=user_id, session_id="s1", key="cursor_line", value="42"
    )

    recalled = await working.recall_all(store, user_id=user_id, session_id="s1")

    assert recalled == {"current_file": "a.py", "cursor_line": "42"}


async def test_working_memory_clear_removes_session() -> None:
    store = FakeWorkingMemoryStore()
    user_id = uuid4()
    await working.remember(store, user_id=user_id, session_id="s1", key="k", value="v")

    await working.clear(store, user_id=user_id, session_id="s1")

    assert await working.recall_all(store, user_id=user_id, session_id="s1") == {}


def test_sensory_worth_retaining_respects_explicit_verdict() -> None:
    candidate = sensory.SensoryCandidate(
        content="hi", source="perception", user_id=uuid4(), explicit_worth_retaining=True
    )
    assert sensory.worth_retaining(candidate) is True


def test_sensory_worth_retaining_falls_back_to_length_heuristic() -> None:
    short = sensory.SensoryCandidate(content="hi", source="perception", user_id=uuid4())
    long_enough = sensory.SensoryCandidate(
        content="the user opened a new terminal window", source="perception", user_id=uuid4()
    )
    assert sensory.worth_retaining(short) is False
    assert sensory.worth_retaining(long_enough) is True


async def test_semantic_remember_shapes_type_data() -> None:
    repo = FakeMemoryRepository()
    record = await semantic.remember(
        repo,
        user_id=uuid4(),
        content="Rust has no garbage collector",
        concept="Rust",
        related_concepts=["memory safety"],
        correlation_id=uuid4(),
    )
    assert record.memory_type == MemoryType.SEMANTIC
    assert record.type_data["concept"] == "Rust"


async def test_procedural_remember_shapes_type_data() -> None:
    repo = FakeMemoryRepository()
    record = await procedural.remember(
        repo,
        user_id=uuid4(),
        content="how to deploy",
        steps=["build", "push", "deploy"],
        correlation_id=uuid4(),
    )
    assert record.memory_type == MemoryType.PROCEDURAL
    assert record.type_data["steps"] == ["build", "push", "deploy"]


async def test_episodic_remember_shapes_type_data() -> None:
    repo = FakeMemoryRepository()
    record = await episodic.remember(
        repo,
        user_id=uuid4(),
        content="deployment failed then recovered",
        outcome="recovered after rollback",
        correlation_id=uuid4(),
    )
    assert record.memory_type == MemoryType.EPISODIC
    assert record.type_data["outcome"] == "recovered after rollback"


async def test_preference_remember_shapes_type_data() -> None:
    repo = FakeMemoryRepository()
    record = await preference.remember(
        repo,
        user_id=uuid4(),
        content="user likes dark mode",
        key="theme",
        value="dark",
        correlation_id=uuid4(),
    )
    assert record.memory_type == MemoryType.PREFERENCE
    assert record.type_data["key"] == "theme"
    assert record.type_data["value"] == "dark"


async def test_project_remember_requires_project_id_and_recall_scopes_to_it() -> None:
    repo = FakeMemoryRepository()
    user_id = uuid4()
    project_id = uuid4()
    await project.remember(
        repo, user_id=user_id, project_id=project_id, content="project note", correlation_id=uuid4()
    )
    await semantic.remember(
        repo, user_id=user_id, content="unrelated note", concept="x", correlation_id=uuid4()
    )

    scoped = await project.recall_for_project(repo, user_id=user_id, project_id=project_id)

    assert [r.content for r in scoped] == ["project note"]
