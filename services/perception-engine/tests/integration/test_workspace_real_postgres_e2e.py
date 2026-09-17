"""**S-3 and S-4 over the whole real chain** (findings F-4 and F-5).

`test_companion_intake_real_http.py` proves the chain as far as this engine's
intake; this file carries the same chain through **real PostgreSQL** and out
over a **real NATS** connection:

    real write → real notify watcher → real nova-companion process
      → real HTTP → real uvicorn → real create_app → real orchestration
      → real PostgresPerceptionRepository → real Postgres
      → real outbox dispatcher → real NatsEventBus → real subscriber

Finding F-4 was that the real-Postgres tier existed but never covered *this*
path: `test_repository_real_postgres.py` calls the repository directly, which
proves the repository and nothing upstream of it. Nothing in this file calls the
repository to produce a row — the only way a row appears is a file being
written on disk.

**Why not the shared `postgres_session_factory` fixture.** That one binds every
session to a single connection inside an outer transaction it rolls back, which
makes writes invisible to any other connection and never actually commits. Both
properties are wrong here: the claim is that the observation is *persisted*, and
the verification queries must see it from outside the writer's own session. So
this composes the production `create_engine`/`create_session_factory` against the
container and cleans up by deleting rows, the way a real deployment would behave.

`@pytest.mark.real_infra`: needs Docker for Postgres and NATS, and a Rust
toolchain for the companion binary. **Not executed in the environment this file
was written in** — no Docker daemon is reachable there (`docker info` fails).
The companion → HTTP → engine half of this chain *was* executed there, through
the same harness module, in `test_companion_intake_real_http.py`.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
from nova_contracts import EventEnvelope
from nova_eventbus_sdk.backends.nats import NatsEventBus
from nova_perception_engine.config import Settings
from nova_perception_engine.domain.workspace import object_id_for_path
from nova_perception_engine.main import create_app
from nova_perception_engine.repository.outbox_dispatcher import dispatch_ready_events
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
    SETTLE_SECONDS,
    RunningCompanion,
    RunningEngine,
    build_companion,
    serve,
    start_companion,
    stop_companion,
    wait_until,
)

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"

_PRIMARY_USER_ID = uuid4()
_ENCRYPTION_KEY = "3ktMjuHsQ9TNWhEiReuORzkawsz4KEYq2zDMZByQhHo="  # test-only Fernet key

PROJECT_DIR = "analytical-engine"
NESTED_DIR = "design"
FILE_NAME = "notes.md"
#: Every directory name on the watched path. The assertion that none of these
#: survives into Postgres is the whole of S-4's persisted leg.
SEGMENTS = ("home", "ada", "projects", PROJECT_DIR, NESTED_DIR)


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    """This engine's own Alembic migration, once, against the container --
    the established pattern from `test_repository_real_postgres.py`."""
    os.environ["PERCEPTION_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture(scope="session")
def companion_binary() -> Path:
    return build_companion()


@pytest.fixture
async def database(postgres_container: PostgresContainer) -> AsyncIterator[AsyncEngine]:
    """A real, committing engine -- the production helper, not a rollback
    fixture. Each test starts from an empty outbox so "exactly one row" is a
    statement about this test's own write and nothing else."""
    engine = create_engine(postgres_container.get_connection_url())
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM perception.outbox_event"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM perception.outbox_event"))
    await engine.dispose()


@pytest.fixture
def repository(database: AsyncEngine) -> PostgresPerceptionRepository:
    return PostgresPerceptionRepository(create_session_factory(database))


@pytest.fixture
async def engine(
    repository: PostgresPerceptionRepository, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[RunningEngine]:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(
        Settings(primary_user_id=_PRIMARY_USER_ID, template_encryption_key=_ENCRYPTION_KEY),
        repository=repository,
        ai_model_port=FakeAIModelOrchestrationPort(),
    )
    async for running in serve(app):
        yield running


@pytest.fixture
def watch_root(tmp_path: Path) -> Path:
    root = tmp_path / "home" / "ada" / "projects"
    (root / PROJECT_DIR / NESTED_DIR).mkdir(parents=True)
    return root


@pytest.fixture
def companion(
    companion_binary: Path, watch_root: Path, engine: RunningEngine
) -> AsyncIterator[RunningCompanion]:
    running = start_companion(companion_binary, watch_root=watch_root, base_url=engine.base_url)
    try:
        yield running
    finally:
        stop_companion(running)


async def _outbox_rows(database: AsyncEngine) -> list[dict]:
    """Read the real table with real SQL, on a connection of its own.

    Deliberately not `repository.list_dispatch_ready`: the claim is about what
    is *in the database*, and asking the same object that wrote it would let a
    repository-level bug agree with itself.
    """
    async with database.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT id, subject, payload, correlation_id, dispatched_at "
                "FROM perception.outbox_event ORDER BY created_at"
            )
        )
        return [dict(row) for row in result.mappings().all()]


async def _wait_for_rows(
    database: AsyncEngine, companion: RunningCompanion, *, settle: bool = True
) -> list[dict]:
    """Wait for the first row, then keep watching long enough to catch a second.

    The settle is what makes "exactly one" meaningful: asserting the count the
    instant the first row lands would pass even if a duplicate were a moment
    behind it.
    """
    deadline = asyncio.get_running_loop().time() + DEADLINE_SECONDS
    rows: list[dict] = []
    while asyncio.get_running_loop().time() < deadline:
        rows = await _outbox_rows(database)
        if rows:
            break
        await asyncio.sleep(0.05)

    assert rows, f"no observation was persisted. Companion output:\n{companion.raw_output()}"
    if settle:
        await asyncio.sleep(SETTLE_SECONDS)
        rows = await _outbox_rows(database)
    return rows


async def test_s3_one_real_file_write_persists_exactly_one_outbox_row(
    companion: RunningCompanion, database: AsyncEngine, watch_root: Path
) -> None:
    """**S-3.** One write on a real disk, one committed row in real Postgres.

    The write emits a genuine burst — a create and one or more content
    modifications, each a real OS event — so this is simultaneously the
    exactly-once claim and the debounce claim. Neither is arranged: the burst is
    whatever the kernel produced.
    """
    (watch_root / PROJECT_DIR / NESTED_DIR / FILE_NAME).write_text("real content")

    rows = await _wait_for_rows(database, companion)

    assert len(rows) == 1, f"expected one row, got {len(rows)}: {rows}"
    assert rows[0]["subject"] == "perception.workspace.observed"
    assert rows[0]["dispatched_at"] is None  # not yet dispatched; that is the worker's job


async def test_s3_a_second_real_edit_after_the_window_persists_a_second_row(
    companion: RunningCompanion, database: AsyncEngine, watch_root: Path
) -> None:
    """The negative control for the test above: debounce must collapse a burst
    without collapsing two genuinely separate edits, or "exactly one" would be
    indistinguishable from "at most one, ever"."""
    target = watch_root / PROJECT_DIR / FILE_NAME
    target.write_text("first edit")
    await _wait_for_rows(database, companion)

    target.write_text("second edit, after the debounce window")

    deadline = asyncio.get_running_loop().time() + DEADLINE_SECONDS
    rows: list[dict] = []
    while asyncio.get_running_loop().time() < deadline:
        rows = await _outbox_rows(database)
        if len(rows) >= 2:
            break
        await asyncio.sleep(0.05)

    assert len(rows) == 2, f"a separate edit did not persist its own row: {rows}"
    assert {row["subject"] for row in rows} == {"perception.workspace.observed"}


async def test_s4_no_path_segment_is_present_in_the_persisted_row(
    companion: RunningCompanion, database: AsyncEngine, watch_root: Path
) -> None:
    """**S-4's persisted leg, read back out of real Postgres.**

    Asserted over the whole serialized row rather than one column: a leak into
    any field would be equally bad, and `payload` is JSONB, so a stray field
    would be stored perfectly happily.
    """
    target = watch_root / PROJECT_DIR / NESTED_DIR / FILE_NAME
    target.write_text("real content")
    resolved = str(target.resolve())

    rows = await _wait_for_rows(database, companion)
    serialized = str(rows[0])

    assert resolved not in serialized
    for segment in SEGMENTS:
        assert segment not in serialized, f"path segment {segment!r} reached the database"

    # And the handle really is this engine's own hash of the real path, so the
    # absence above is a transformation rather than an omission.
    assert rows[0]["payload"]["object_id"] == object_id_for_path(resolved)
    assert rows[0]["payload"]["label"] == FILE_NAME


async def test_s4_the_published_event_carries_no_path_either(
    companion: RunningCompanion,
    database: AsyncEngine,
    repository: PostgresPerceptionRepository,
    watch_root: Path,
    nats_event_bus: NatsEventBus,
) -> None:
    """**S-4's publication leg, over a real NATS connection.**

    The real dispatcher reads the real row out of real Postgres and publishes it
    through the same `NatsEventBus` class every engine's `main.py` uses. What a
    downstream consumer would actually receive is therefore what is asserted
    here, rather than what the payload looked like before it was written.
    """
    received: list[EventEnvelope] = []

    async def handler(envelope: EventEnvelope) -> None:
        received.append(envelope)

    subscription = await nats_event_bus.subscribe("perception.workspace.observed", handler)
    try:
        target = watch_root / PROJECT_DIR / NESTED_DIR / FILE_NAME
        target.write_text("real content")
        resolved = str(target.resolve())

        await _wait_for_rows(database, companion)
        dispatched = await dispatch_ready_events(repository, nats_event_bus)
        assert dispatched == 1

        envelope = await wait_until(lambda: received[0] if received else None)
        assert envelope is not None, "the published event never arrived over NATS"

        serialized = str(envelope.payload)
        assert resolved not in serialized
        for segment in SEGMENTS:
            assert segment not in serialized, f"path segment {segment!r} was published"
        assert envelope.payload["object_id"] == object_id_for_path(resolved)
    finally:
        await subscription.unsubscribe()


async def test_the_row_is_marked_dispatched_so_it_publishes_once(
    companion: RunningCompanion,
    database: AsyncEngine,
    repository: PostgresPerceptionRepository,
    watch_root: Path,
    nats_event_bus: NatsEventBus,
) -> None:
    """Exactly-once *delivery*, as far as this slice owns it: the dispatcher
    marks the real row dispatched, so a second pass republishes nothing."""
    (watch_root / PROJECT_DIR / FILE_NAME).write_text("real content")
    await _wait_for_rows(database, companion)

    assert await dispatch_ready_events(repository, nats_event_bus) == 1
    assert await dispatch_ready_events(repository, nats_event_bus) == 0

    rows = await _outbox_rows(database)
    assert len(rows) == 1
    assert rows[0]["dispatched_at"] is not None
