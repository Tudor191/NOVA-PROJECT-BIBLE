"""**D3 over the real chain: a declared folder of a project NOVA holds makes
its observations known** (TDD 4F.8 §18 row 2; A-4F8-2 (a), (a1), (a2); E-2).

    a real memory.long_term.created, from a producer bound as memory-engine
      → real NATS → this engine's real lifespan subscription
      → real perception.known_project (PostgreSQL)
    a real file write → the real nova-companion process → real HTTP
      → the real workspace route → the operator's declared folder for it
      → is that project known? → real perception.outbox_event

**What is asserted**, each read with independent SQL:
- **the match** (E-2): a file under the declared folder of a known project is
  published with that `project_id`;
- **the inert binding**: a file under a declared folder whose project has never
  been seen on `memory.long_term.created` is published with `None`;
- **the miss** (E-2, N-13): a file under no declared folder is published with
  `None`;
- **the store**: the project is learned once, current state only, with the
  event that made it known.

**The producer is not imported from `memory-engine`** (TDD 4F §16.1 control 7).
It is a real NATS connection bound with that engine's name and its one
allow-listed subject, publishing the real registered payload.

`@pytest.mark.real_infra`: needs Docker for PostgreSQL and NATS, and a Rust
toolchain for the companion binary.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from nova_contracts import EventEnvelope
from nova_contracts.events.memory import LongTermMemoryCreatedPayload
from nova_eventbus_sdk.backends.nats import NatsEventBus
from nova_eventbus_sdk.boundary import BoundEventBus
from nova_perception_engine.config import Settings
from nova_perception_engine.domain.workspace import object_id_for_path
from nova_perception_engine.main import create_app
from nova_perception_engine.repository.postgres_perception_repository import (
    PostgresPerceptionRepository,
)
from nova_service_kit import create_engine, create_session_factory
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from testcontainers.postgres import PostgresContainer

from tests.fakes.ai_model_port import FakeAIModelOrchestrationPort
from tests.integration.companion_harness import (
    DEADLINE_SECONDS,
    RunningCompanion,
    RunningEngine,
    build_companion,
    serve,
    start_companion,
    stop_companion,
)

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
_PRIMARY_USER_ID = uuid4()
_ENCRYPTION_KEY = "3ktMjuHsQ9TNWhEiReuORzkawsz4KEYq2zDMZByQhHo="  # test-only Fernet key

MEMORY = "memory.long_term.created"
WORKSPACE = "perception.workspace.observed"
KNOWN = uuid4()
"""The project a real memory makes known, and an operator declares a folder for."""
NEVER_SEEN = uuid4()
"""A project an operator declares a folder for, which no memory ever names."""


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["PERCEPTION_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture(scope="session")
def companion_binary() -> Path:
    return build_companion()


@pytest.fixture
async def database(postgres_container: PostgresContainer) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(postgres_container.get_connection_url())
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM perception.outbox_event"))
        await connection.execute(text("DELETE FROM perception.known_project"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM perception.outbox_event"))
        await connection.execute(text("DELETE FROM perception.known_project"))
    await engine.dispose()


@pytest.fixture
def watch_root(tmp_path: Path) -> Path:
    root = (tmp_path / "workspace").resolve()
    for folder in ("atlas", "orion", "misc"):
        (root / folder).mkdir(parents=True)
    return root


@pytest.fixture
def app(
    database: AsyncEngine,
    watch_root: Path,
    nats_container,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
) -> FastAPI:
    """The real app on real NATS, so its lifespan subscription is the real one.
    The operator declares `atlas` for `KNOWN` and `orion` for `NEVER_SEEN`;
    `misc` is declared for nothing."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "nats")
    monkeypatch.setenv("NATS_URL", nats_container.nats_uri())
    return create_app(
        Settings(
            primary_user_id=_PRIMARY_USER_ID,
            template_encryption_key=_ENCRYPTION_KEY,
            project_folder_bindings={
                str(watch_root / "atlas"): KNOWN,
                str(watch_root / "orion"): NEVER_SEEN,
            },
        ),
        repository=PostgresPerceptionRepository(create_session_factory(database)),
        ai_model_port=FakeAIModelOrchestrationPort(),
    )


@pytest.fixture
async def engine(app: FastAPI, database: AsyncEngine) -> AsyncIterator[RunningEngine]:
    async for running in serve(app):
        async with database.begin() as connection:
            await connection.execute(text("DELETE FROM perception.outbox_event"))
        yield running


@pytest.fixture
def companion(
    companion_binary: Path, watch_root: Path, engine: RunningEngine
) -> Iterator[RunningCompanion]:
    running = start_companion(companion_binary, watch_root=watch_root, base_url=engine.base_url)
    try:
        yield running
    finally:
        stop_companion(running)


@pytest.fixture
async def memory_producer(nats_container) -> AsyncIterator[BoundEventBus]:  # type: ignore[no-untyped-def]
    """A real NATS connection bound as `memory-engine`, allowed exactly the one
    subject it publishes. Not imported from that engine (control 7)."""
    bus = BoundEventBus(
        NatsEventBus(servers=nats_container.nats_uri()),
        engine_name="memory-engine",
        publishable_subjects=frozenset({MEMORY}),
        subscribable_subjects=frozenset(),
    )
    await bus.connect()
    yield bus
    await bus.close()


async def _known_rows(database: AsyncEngine) -> list[dict]:  # type: ignore[type-arg]
    async with database.connect() as connection:
        result = await connection.execute(
            text("SELECT project_id, source_event_id FROM perception.known_project")
        )
        return [dict(row) for row in result.mappings().all()]


async def _project_of(database: AsyncEngine, path: Path, companion: RunningCompanion) -> object:
    """The `project_id` the committed outbox row for `path` carries, read with
    SQL once the row exists."""
    object_id = object_id_for_path(str(path))
    deadline = asyncio.get_running_loop().time() + DEADLINE_SECONDS
    while True:
        async with database.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT payload FROM perception.outbox_event "
                    "WHERE subject = :subject AND payload->>'object_id' = :object_id"
                ),
                {"subject": WORKSPACE, "object_id": object_id},
            )
            rows = [row[0] for row in result.all()]
        if rows:
            assert len(rows) == 1, rows
            return rows[0]["project_id"]
        assert asyncio.get_running_loop().time() < deadline, (
            f"no observation of {path.name} was committed:\n{companion.raw_output()}"
        )
        await asyncio.sleep(0.05)


async def _publish_memory(producer: BoundEventBus, *, project_id: UUID) -> EventEnvelope:
    payload = LongTermMemoryCreatedPayload(
        memory_id=uuid4(),
        user_id=_PRIMARY_USER_ID,
        project_id=project_id,
        memory_type="semantic",
        importance_score=0.5,
        privacy_level="internal",
        created_at=datetime.now(UTC),
    )
    envelope = EventEnvelope(
        subject=MEMORY,
        source_engine="memory-engine",
        correlation_id=uuid4(),
        payload=payload.model_dump(mode="json"),
    )
    await producer.publish(envelope)
    return envelope


async def test_a_declared_folder_of_a_known_project_correlates_and_nothing_else_does(
    companion: RunningCompanion,
    database: AsyncEngine,
    memory_producer: BoundEventBus,
    watch_root: Path,
) -> None:
    published = await _publish_memory(memory_producer, project_id=KNOWN)

    deadline = asyncio.get_running_loop().time() + DEADLINE_SECONDS
    while not await _known_rows(database):
        assert asyncio.get_running_loop().time() < deadline, "the memory was never learned"
        await asyncio.sleep(0.05)
    assert await _known_rows(database) == [
        {"project_id": KNOWN, "source_event_id": published.event_id}
    ]

    match = watch_root / "atlas" / "notes.md"
    inert = watch_root / "orion" / "notes.md"
    miss = watch_root / "misc" / "notes.md"
    for path in (match, inert, miss):
        path.write_text(path.parent.name)

    assert await _project_of(database, match, companion) == str(KNOWN)
    assert await _project_of(database, inert, companion) is None
    assert await _project_of(database, miss, companion) is None


async def test_a_repeated_memory_of_the_same_project_changes_nothing(
    engine: RunningEngine, database: AsyncEngine, memory_producer: BoundEventBus
) -> None:
    first = await _publish_memory(memory_producer, project_id=KNOWN)
    deadline = asyncio.get_running_loop().time() + DEADLINE_SECONDS
    while not await _known_rows(database):
        assert asyncio.get_running_loop().time() < deadline
        await asyncio.sleep(0.05)

    await _publish_memory(memory_producer, project_id=KNOWN)
    # A second, unrelated project proves the subscription is still consuming,
    # so the unchanged row above is a decision rather than a stall.
    await _publish_memory(memory_producer, project_id=NEVER_SEEN)
    while len(await _known_rows(database)) < 2:
        assert asyncio.get_running_loop().time() < deadline
        await asyncio.sleep(0.05)

    rows = {row["project_id"]: row["source_event_id"] for row in await _known_rows(database)}
    assert rows[KNOWN] == first.event_id
