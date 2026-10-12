"""**D1 + D2 over the real chain: a real OS permission revocation stops the
perception stream, and says so** (TDD 4F.8 §18 rows 2 and 3; §29.5 item 2).

    real chmod → real nova-companion process (D1) → real HTTP → real uvicorn
      → real create_app → the one revocation route → real FilesystemSensor
      → running → failed (D2) → real PostgresPerceptionRepository
      → real perception.outbox_event → real dispatcher → real NatsEventBus

Then a further write, by a writer that still has permission, produces nothing.

**What is asserted, each read independently of the code under test:**
- the sensor reached `failed`, and its permission reads as withdrawn;
- exactly **one** `perception.sensor.health_changed` row with `status: failed`
  is committed, read with independent SQL;
- it reaches a real NATS subscriber through the real dispatcher;
- a later write that the OS **accepted** produces no workspace row (E-6, N-7);
- the companion logged the revocation and the engine's acknowledgement, and
  named no path.

**These tests must run as a non-root user.** Root bypasses permission checks,
so a `chmod` would deny root nothing. The revocation step asserts that the OS
really denies access, and fails loudly if it does not. CI runs them as the
runner's own unprivileged user.

`@pytest.mark.real_infra`: needs Docker for PostgreSQL and NATS, and a Rust
toolchain for the companion binary.
"""

from __future__ import annotations

import asyncio
import os
import stat
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from nova_contracts import EventEnvelope
from nova_eventbus_sdk.backends.nats import NatsEventBus
from nova_perception_engine.config import Settings
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

HEALTH = "perception.sensor.health_changed"
WORKSPACE = "perception.workspace.observed"


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["PERCEPTION_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture(scope="session")
def companion_binary() -> Path:
    return build_companion()


@pytest.fixture
async def database(postgres_container: PostgresContainer) -> AsyncIterator[AsyncEngine]:
    """A real, committing engine; each test starts from an empty outbox."""
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
def app(repository: PostgresPerceptionRepository, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    return create_app(
        Settings(primary_user_id=_PRIMARY_USER_ID, template_encryption_key=_ENCRYPTION_KEY),
        repository=repository,
        ai_model_port=FakeAIModelOrchestrationPort(),
    )


@pytest.fixture
async def engine(app: FastAPI, database: AsyncEngine) -> AsyncIterator[RunningEngine]:
    async for running in serve(app):
        # Startup's six lifecycle rows (4F.7) are removed so the counts below
        # are this test's own.
        async with database.begin() as connection:
            await connection.execute(text("DELETE FROM perception.outbox_event"))
        yield running


@pytest.fixture
def watch_root(tmp_path: Path) -> Iterator[Path]:
    root = tmp_path / "workspace"
    root.mkdir()
    yield root
    root.chmod(0o755)  # so pytest can remove it, however the test ended


@pytest.fixture
def companion(
    companion_binary: Path, watch_root: Path, engine: RunningEngine
) -> Iterator[RunningCompanion]:
    running = start_companion(companion_binary, watch_root=watch_root, base_url=engine.base_url)
    try:
        yield running
    finally:
        stop_companion(running)


async def _rows(database: AsyncEngine, subject: str) -> list[dict]:  # type: ignore[type-arg]
    """Independent SQL on its own connection, never the repository."""
    async with database.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT id, payload, correlation_id FROM perception.outbox_event "
                "WHERE subject = :subject ORDER BY created_at"
            ),
            {"subject": subject},
        )
        return [dict(row) for row in result.mappings().all()]


def _revoke(root: Path) -> None:
    """Mode 0o300: the owner, which is this test, keeps write and search, so it
    can still create files. It loses read, and so does the companion, which runs
    as the same user here."""
    root.chmod(0o300)
    try:
        os.listdir(root)
    except PermissionError:
        return
    pytest.fail(
        "the OS still grants read after chmod 300. These tests must run as a non-root "
        "user: root bypasses permission checks, so nothing here would be tested"
    )


def _logged(companion: RunningCompanion, message: str) -> list[dict]:  # type: ignore[type-arg]
    return [line for line in companion.logs() if line.get("message") == message]


async def _post_observation(engine: RunningEngine, path: Path) -> dict:  # type: ignore[type-arg]
    """One workspace observation over real HTTP to the real engine, shaped as
    the companion's. It reports what the gate decided."""
    # `trust_env=False`: a loopback call to the engine must not be routed
    # through, or configured by, whatever proxy the environment declares.
    async with httpx.AsyncClient(base_url=engine.base_url, trust_env=False) as client:
        response = await client.post(
            "/v1/perception/workspace-observations",
            params={"source": "filesystem"},
            json={"path": str(path), "observed_at": datetime.now(UTC).isoformat()},
        )
    assert response.status_code == 202, response.text
    body = response.json()
    return {"published": body["published"], "reason": body["reason"]}


async def test_a_real_revocation_fails_the_sensor_publishes_failed_once_and_stops_the_stream(
    app: FastAPI,
    engine: RunningEngine,
    companion: RunningCompanion,
    database: AsyncEngine,
    repository: PostgresPerceptionRepository,
    watch_root: Path,
    nats_event_bus: NatsEventBus,
) -> None:
    sensor = app.state.sensors_by_source["filesystem"]

    # Live first, so "nothing after" means the gate, not a dead process.
    (watch_root / "before.md").write_text("before")
    deadline = asyncio.get_running_loop().time() + DEADLINE_SECONDS
    while not await _rows(database, WORKSPACE):
        assert asyncio.get_running_loop().time() < deadline, companion.raw_output()
        await asyncio.sleep(0.05)

    _revoke(watch_root)

    assert await wait_until(lambda: sensor.state() == "failed"), (
        f"the sensor never failed. Companion output:\n{companion.raw_output()}"
    )
    assert sensor.permission_status().granted is False

    # Exactly one committed `failed`, read with SQL, not asked of the repository.
    failed = await _rows(database, HEALTH)
    assert [row["payload"]["status"] for row in failed] == ["failed"]
    assert failed[0]["payload"]["sensor_id"] == "companion-filesystem"

    # A write the OS accepts, by a writer that still has permission (N-7).
    after = watch_root / "after.md"
    after.write_text("after")
    assert stat.S_ISREG(after.stat().st_mode), "the post-revocation write did not land"
    workspace_rows = len(await _rows(database, WORKSPACE))
    await asyncio.sleep(SETTLE_SECONDS)
    assert len(await _rows(database, WORKSPACE)) == workspace_rows, (
        "a workspace observation was persisted after the revocation"
    )
    assert len(await _rows(database, HEALTH)) == 1, "a second `failed` was published"

    # The engine's own gate, not only the companion's silence (F-4F8-15): an
    # observation that does reach the real route after the revocation is
    # dropped there, and commits nothing.
    gated = await _post_observation(engine, after)
    assert gated == {"published": False, "reason": "sensor_not_running"}, gated
    assert len(await _rows(database, WORKSPACE)) == workspace_rows

    # The real dispatcher delivers the one `failed` over real NATS.
    received: list[EventEnvelope] = []

    async def on_health(envelope: EventEnvelope) -> None:
        received.append(envelope)

    subscription = await nats_event_bus.subscribe(HEALTH, on_health)
    try:
        await dispatch_ready_events(repository, nats_event_bus)
        envelope = await wait_until(lambda: received[0] if received else None)
        assert envelope is not None, "`failed` never arrived over NATS"
        assert envelope.payload["status"] == "failed"
        assert envelope.event_id == failed[0]["id"]
    finally:
        await subscription.unsubscribe()

    # The companion said what happened, once, and named no path. (Its startup
    # line names the root by design; the revocation lines must not.)
    revoked = _logged(companion, "permission_revoked")
    assert len(revoked) == 1
    reported = _logged(companion, "revocation_reported")
    assert reported and reported[0]["state"] == "failed" and reported[0]["transitioned"] is True
    assert str(watch_root) not in str(revoked + reported)
    assert not any(
        line.get("file") == "after.md" for line in _logged(companion, "observation_submitted")
    )
