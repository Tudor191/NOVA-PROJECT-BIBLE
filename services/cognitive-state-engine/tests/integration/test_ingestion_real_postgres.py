"""Thought ingestion and the compare-and-set against **real PostgreSQL and real
NATS** -- Phase 4F.P, A-4FP-1, A-4FP-2, A-4FP-8 and A-4FP-9 (TDD 4F.P §30.2,
§13, §15.1's per-engine `real_infra` row).

What only real infrastructure can prove, and where:

* **Insert-if-absent is one statement.** The first insert returns the row; a
  repeat -- with another label, project and clock reading -- returns nothing
  and leaves the row's **tuple version** (`xmin`) unchanged, so it was not
  rewritten, not merely rewritten with equal values. Concurrent inserts of one
  identity on independent connections create exactly one row.
* **The CAS has exactly one winner** (A-4FP-8). Concurrent compare-and-sets on
  independent connections: one row back, the rest nothing.
* **V-7 (b) -- two concurrent promotions trigger once.** Every caller is forced
  to read `ACTIVE` before any of them writes (a barrier between the read and
  the write), so the race is certain rather than hoped for. **The negative
  control runs the same interleaving with the unconditional `move_layer`** (TDD
  4F.P NP-7) and triggers every time -- which is what proves the interleaving
  is real.
* **The whole step, raced.** Concurrent ingestions of one observed object:
  one thought, one promotion, one trigger request.
* **The production path over a real bus.** An observation published by a bus
  **bound as `perception-engine`** (4F.7 P-15's precedent) reaches the
  production `create_app` subscription, becomes one row in real Postgres (read
  by independent SQL) and one real `autonomy.decision.requested` request. A
  re-published envelope, a later observation of the same file and a foreign
  user's observation add nothing, asserted with an ordered marker.

**Fresh paths everywhere.** Every test derives its object ids from paths no
other test uses, so no test can pass on another's row.

**`autonomy-engine` is a stand-in responder** in the bus test, as in 4F.6's
`test_decision_trigger_real_nats.py`: this tier proves the producer's half, up
to a real request on the real broker. It is labelled RS-8 test infrastructure
and counts toward no V-item's composed-stack evidence (TDD 4F.P §28.4 C-14).

*(Phase 4F.P, P4 -- A-4FP-6, 2026-09-30:* the request now also carries the
persisted proposal's `operation` and `parameters`. The last test below reads
the row by independent SQL and compares its authored pair to the raw envelope
the real broker delivered. *The stand-in responder above is still only the
receiving end of the producer's half; `autonomy-engine`'s half of P4 is proven
in that engine's own real-infra tier.)*

`@pytest.mark.real_infra`: requires Docker (or equivalent real services).
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import socket
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePath
from uuid import UUID, uuid4, uuid5

import httpx
import pytest
import uvicorn
from nova_cognitive_state_engine.config import Settings
from nova_cognitive_state_engine.domain.authoring import T1
from nova_cognitive_state_engine.domain.ingestion import (
    thought_for_workspace_observation,
    thought_id_for,
)
from nova_cognitive_state_engine.domain.models import ActiveThought, AttentionLayer
from nova_cognitive_state_engine.domain.ports import TriggerDelivery
from nova_cognitive_state_engine.ingestion_orchestration import ingest_workspace_observation
from nova_cognitive_state_engine.main import create_app
from nova_cognitive_state_engine.promotion_orchestration import promote_thought
from nova_cognitive_state_engine.repository.postgres_cognitive_state_repository import (
    PostgresCognitiveStateRepository,
)
from nova_contracts import EventEnvelope, validate_payload
from nova_contracts.events.autonomy import (
    AutonomyDecisionReplyPayload,
    AutonomyDecisionRequestedPayload,
)
from nova_contracts.events.perception import PerceptionWorkspaceObservedPayload
from nova_eventbus_sdk import BoundEventBus
from nova_eventbus_sdk.backends.nats import NatsEventBus
from nova_testkit.postgres import run_alembic_upgrade
from nova_testkit.waiting import wait_until
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
PRIMARY = Settings().primary_user_id
NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
RACERS = 12
OBSERVED = "perception.workspace.observed"
REQUESTED = "autonomy.decision.requested"


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["COGNITIVE_STATE_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
async def database(postgres_container: PostgresContainer) -> AsyncIterator[AsyncEngine]:
    """Enough pooled connections that every racer holds its own -- the races
    below are between independent connections, never within one."""
    engine = create_async_engine(
        postgres_container.get_connection_url(), pool_size=RACERS + 4, max_overflow=0
    )
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM cognitive_state.active_thought"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM cognitive_state.active_thought"))
    await engine.dispose()


@pytest.fixture
def repository(database: AsyncEngine) -> PostgresCognitiveStateRepository:
    return PostgresCognitiveStateRepository(async_sessionmaker(database, expire_on_commit=False))


class RecordingTrigger:
    def __init__(self) -> None:
        self.requests: list[AutonomyDecisionRequestedPayload] = []

    async def request_decision(
        self, payload: AutonomyDecisionRequestedPayload, *, correlation_id: UUID
    ) -> TriggerDelivery:
        self.requests.append(payload)
        return TriggerDelivery(status="decided", outcome="propose")


def _fresh_path() -> str:
    return f"/workspace/{uuid4()}/notes.md"


def _object_id(path: str) -> str:
    """`perception-engine`'s derivation, restated (control 7)."""
    return "ws-" + hashlib.sha256(PurePath(path.strip()).as_posix().encode()).hexdigest()


def _observation(path: str, **overrides: object) -> PerceptionWorkspaceObservedPayload:
    fields: dict = {
        "object_id": _object_id(path),
        "label": PurePath(path).name,
        "user_id": PRIMARY,
        "object_type": "project",
        "project_id": None,
        "sensor_id": "companion-filesystem",
        "observed_at": NOW,
    }
    fields.update(overrides)
    return PerceptionWorkspaceObservedPayload(**fields)


def _thought(path: str, *, label: str = "notes.md", now: datetime = NOW) -> ActiveThought:
    return thought_for_workspace_observation(
        object_id=_object_id(path), label=label, project_id=None, user_id=PRIMARY, now=now
    )


async def _row(database: AsyncEngine, thought_id: UUID) -> dict | None:  # type: ignore[type-arg]
    """Independent SQL on its own connection, with the tuple version."""
    async with database.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT *, xmin::text AS version FROM cognitive_state.active_thought "
                "WHERE thought_id = :id"
            ),
            {"id": thought_id},
        )
        row = result.one_or_none()
        return dict(row._mapping) if row is not None else None


async def _count(database: AsyncEngine) -> int:
    async with database.connect() as connection:
        result = await connection.execute(
            text("SELECT count(*) FROM cognitive_state.active_thought")
        )
        return int(result.scalar_one())


# --- insert-if-absent (A-4FP-1) ---------------------------------------------------------


async def test_the_first_insert_creates_the_row_and_a_repeat_writes_nothing(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    path = _fresh_path()
    created = await repository.insert_thought_if_absent(_thought(path, label="a.md"))
    assert created is not None
    before = await _row(database, created.thought_id)

    repeat = await repository.insert_thought_if_absent(
        _thought(path, label="b.md", now=NOW + timedelta(hours=1))
    )

    assert repeat is None
    after = await _row(database, created.thought_id)
    assert after == before  # every column, and the tuple version: not rewritten
    assert after is not None and after["description"] == "Activity observed in a.md"


async def test_the_inserted_row_holds_every_ratified_field(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    path = _fresh_path()
    created = await repository.insert_thought_if_absent(_thought(path, label="nova"))
    assert created is not None
    row = await _row(database, created.thought_id)
    assert row is not None

    assert row["thought_id"] == thought_id_for(_object_id(path))
    assert row["user_id"] == PRIMARY
    assert row["description"] == "Activity observed in nova"
    assert (row["priority"], row["confidence"], row["current_progress"]) == (1, 1.0, 0.0)
    assert row["dependencies"] == row["related_memories"] == row["related_projects"] == []
    assert row["estimated_completion"] is None
    assert row["attention_layer"] == "active"
    assert row["created_at"] == row["updated_at"] == NOW
    assert row["proposed_action"] == T1.author(label="nova").model_dump(mode="json")
    assert row["proposed_action"]["operation"] == "list"
    assert row["proposed_action"]["parameters"] == {}


async def test_concurrent_inserts_of_one_identity_create_exactly_one_row(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    path = _fresh_path()
    results = await asyncio.gather(
        *(
            repository.insert_thought_if_absent(_thought(path, now=NOW + timedelta(seconds=n)))
            for n in range(RACERS)
        )
    )
    assert sum(result is not None for result in results) == 1
    assert await _count(database) == 1


# --- the compare-and-set (A-4FP-8) --------------------------------------------------------


async def test_the_compare_and_set_moves_only_from_the_expected_layer(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    created = await repository.insert_thought_if_absent(_thought(_fresh_path()))
    assert created is not None
    later = NOW + timedelta(minutes=5)

    wrong = await repository.compare_and_set_layer(
        created.thought_id,
        expected=AttentionLayer.PASSIVE,
        target=AttentionLayer.ACTIVE,
        updated_at=later,
    )
    assert wrong is None
    row = await _row(database, created.thought_id)
    assert row is not None and (row["attention_layer"], row["updated_at"]) == ("active", NOW)

    moved = await repository.compare_and_set_layer(
        created.thought_id,
        expected=AttentionLayer.ACTIVE,
        target=AttentionLayer.IMMEDIATE,
        updated_at=later,
    )
    assert moved is not None
    assert moved.attention_layer is AttentionLayer.IMMEDIATE
    assert moved.updated_at == later
    row = await _row(database, created.thought_id)
    assert row is not None and (row["attention_layer"], row["updated_at"]) == ("immediate", later)
    assert row["created_at"] == NOW

    again = await repository.compare_and_set_layer(
        created.thought_id,
        expected=AttentionLayer.ACTIVE,
        target=AttentionLayer.IMMEDIATE,
        updated_at=later + timedelta(minutes=1),
    )
    assert again is None


async def test_a_compare_and_set_on_a_missing_thought_returns_nothing(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    missing = await repository.compare_and_set_layer(
        uuid4(), expected=AttentionLayer.ACTIVE, target=AttentionLayer.IMMEDIATE, updated_at=NOW
    )
    assert missing is None
    assert await _count(database) == 0


async def test_concurrent_compare_and_sets_have_exactly_one_winner(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    created = await repository.insert_thought_if_absent(_thought(_fresh_path()))
    assert created is not None
    instants = [NOW + timedelta(seconds=n + 1) for n in range(RACERS)]

    results = await asyncio.gather(
        *(
            repository.compare_and_set_layer(
                created.thought_id,
                expected=AttentionLayer.ACTIVE,
                target=AttentionLayer.IMMEDIATE,
                updated_at=instant,
            )
            for instant in instants
        )
    )

    winners = [result for result in results if result is not None]
    assert len(winners) == 1
    row = await _row(database, created.thought_id)
    assert row is not None
    assert row["attention_layer"] == "immediate"
    assert row["updated_at"] == winners[0].updated_at


# --- V-7 (b): concurrent promotions, with the race forced ---------------------------------


class BarrierRepository(PostgresCognitiveStateRepository):
    """Every caller's read completes before any caller's write: the barrier
    sits between `promote_thought`'s `get_thought` and its transition."""

    def __init__(self, session_factory: async_sessionmaker, parties: int) -> None:
        super().__init__(session_factory)
        self._barrier = asyncio.Barrier(parties)

    async def get_thought(self, thought_id: UUID) -> ActiveThought:
        thought = await super().get_thought(thought_id)
        await self._barrier.wait()
        return thought


class UnconditionalRepository(BarrierRepository):
    """**TDD 4F.P NP-7**: the CAS replaced by `move_layer`. Used only by the
    negative control."""

    async def compare_and_set_layer(
        self,
        thought_id: UUID,
        *,
        expected: AttentionLayer,
        target: AttentionLayer,
        updated_at: datetime,
    ) -> ActiveThought | None:
        return await self.move_layer(thought_id, target)


async def _race_promotions(repository: BarrierRepository, thought_id: UUID) -> RecordingTrigger:
    trigger = RecordingTrigger()
    await asyncio.gather(
        *(
            promote_thought(thought_id, repository=repository, trigger=trigger)
            for _ in range(RACERS)
        )
    )
    return trigger


async def test_v7b_concurrent_promotions_of_one_thought_trigger_exactly_once(
    database: AsyncEngine,
) -> None:
    factory = async_sessionmaker(database, expire_on_commit=False)
    repository = BarrierRepository(factory, RACERS)
    created = await repository.insert_thought_if_absent(_thought(_fresh_path()))
    assert created is not None

    trigger = await _race_promotions(repository, created.thought_id)

    assert len(trigger.requests) == 1
    assert trigger.requests[0].thought_id == created.thought_id
    row = await _row(database, created.thought_id)
    assert row is not None and row["attention_layer"] == "immediate"


async def test_v7b_negative_control_an_unconditional_move_triggers_every_racer(
    database: AsyncEngine,
) -> None:
    """NP-7 fails the property: with the same forced interleaving, the
    unconditional move lets every caller that read `ACTIVE` fire. This is what
    proves the test above races for real."""
    factory = async_sessionmaker(database, expire_on_commit=False)
    repository = UnconditionalRepository(factory, RACERS)
    created = await repository.insert_thought_if_absent(_thought(_fresh_path()))
    assert created is not None

    trigger = await _race_promotions(repository, created.thought_id)

    assert len(trigger.requests) == RACERS


# --- the whole ingestion step, raced ------------------------------------------------------


async def test_concurrent_ingestions_of_one_object_create_one_thought_and_one_trigger(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    path, trigger = _fresh_path(), RecordingTrigger()

    results = await asyncio.gather(
        *(
            ingest_workspace_observation(
                _observation(path),
                repository=repository,
                trigger=trigger,
                user_id=PRIMARY,
                now=NOW + timedelta(seconds=n),
            )
            for n in range(RACERS)
        )
    )

    assert sorted(result.outcome for result in results) == ["created"] + ["duplicate"] * (
        RACERS - 1
    )
    assert len(trigger.requests) == 1
    assert await _count(database) == 1
    row = await _row(database, thought_id_for(_object_id(path)))
    assert row is not None and row["attention_layer"] == "immediate"


async def test_a_repeat_after_promotion_neither_resets_nor_repromotes(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    """TDD 4F.P NP-8 and NP-9: an upsert would reset the promoted thought to
    `ACTIVE`, and promoting on every observation would trigger again."""
    path, trigger = _fresh_path(), RecordingTrigger()
    first = await ingest_workspace_observation(
        _observation(path), repository=repository, trigger=trigger, user_id=PRIMARY, now=NOW
    )
    assert first.outcome == "created"
    before = await _row(database, first.thought_id)  # type: ignore[arg-type]

    repeat = await ingest_workspace_observation(
        _observation(path, label="renamed.md", project_id=uuid4(), sensor_id="second-sensor"),
        repository=repository,
        trigger=trigger,
        user_id=PRIMARY,
        now=NOW + timedelta(hours=1),
    )

    assert repeat.outcome == "duplicate"
    assert await _row(database, first.thought_id) == before  # type: ignore[arg-type]
    assert before is not None and before["attention_layer"] == "immediate"
    assert len(trigger.requests) == 1


# --- the production path over a real bus --------------------------------------------------


@pytest.fixture
async def producer(nats_container) -> AsyncIterator[BoundEventBus]:  # type: ignore[no-untyped-def]
    """A real NATS connection bound with `perception-engine`'s engine name and
    one subject its own allow-list holds. Not imported from that engine."""
    backend = NatsEventBus(servers=nats_container.nats_uri())
    bus = BoundEventBus(
        backend,
        engine_name="perception-engine",
        publishable_subjects=frozenset({OBSERVED}),
        subscribable_subjects=frozenset(),
    )
    await bus.connect()
    yield bus
    await bus.close()


@pytest.fixture
async def autonomy(nats_container) -> AsyncIterator[list[EventEnvelope]]:  # type: ignore[no-untyped-def]
    """Stand-in `autonomy-engine` responder (RS-8 test infrastructure):
    validates each request through the registry and replies `propose`."""
    received: list[EventEnvelope] = []

    async def _handle(envelope: EventEnvelope) -> AutonomyDecisionReplyPayload:
        received.append(envelope)
        validate_payload(REQUESTED, envelope.payload)
        return AutonomyDecisionReplyPayload(
            degraded=False, outcome="propose", subject_id=uuid5(uuid4(), str(envelope.event_id))
        )

    backend = NatsEventBus(servers=nats_container.nats_uri())
    await backend.connect()
    await backend.serve(REQUESTED, _handle, source_engine="autonomy-engine-stub")
    await asyncio.sleep(0.1)  # let the SUB reach the server first
    yield received
    await backend.close()


@asynccontextmanager
async def _running_engine(
    postgres_container: PostgresContainer,
    nats_container,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[None]:
    """The **production** app and lifespan, served by a real uvicorn in this
    test's event loop (4F.7 P-15's precedent)."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "nats")
    monkeypatch.setenv("NATS_URL", nats_container.nats_uri())
    app = create_app(Settings(postgres_dsn=postgres_container.get_connection_url()))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    task = asyncio.create_task(server.serve())
    deadline = time.monotonic() + 30.0
    while not server.started:
        if task.done():
            await task
        if time.monotonic() > deadline:
            raise RuntimeError("uvicorn did not start within the deadline")
        await asyncio.sleep(0.02)
    bound: socket.socket = server.servers[0].sockets[0]
    try:
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{bound.getsockname()[1]}", timeout=10.0
        ) as client:
            assert (await client.get("/internal/readiness")).status_code == 200
            yield
    finally:
        server.should_exit = True
        await task


def _envelope(payload: PerceptionWorkspaceObservedPayload) -> EventEnvelope:
    return EventEnvelope(
        subject=OBSERVED,
        source_engine="perception-engine",
        correlation_id=uuid4(),
        payload=payload.model_dump(mode="json"),
    )


async def _layer_is(database: AsyncEngine, thought_id: UUID, layer: str) -> bool:
    row = await _row(database, thought_id)
    return row is not None and row["attention_layer"] == layer


async def test_an_observation_over_the_real_bus_becomes_one_thought_and_one_real_request(
    producer: BoundEventBus,
    autonomy: list[EventEnvelope],
    database: AsyncEngine,
    postgres_container: PostgresContainer,
    nats_container,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, marker = _fresh_path(), _fresh_path()
    thought_id = thought_id_for(_object_id(path))
    marker_id = thought_id_for(_object_id(marker))

    async with _running_engine(postgres_container, nats_container, monkeypatch):
        first = _envelope(_observation(path))
        await producer.publish(first)
        await wait_until(lambda: _layer_is(database, thought_id, "immediate"), timeout_s=15.0)
        before = await _row(database, thought_id)

        # An outbox re-publish (same `event_id`), a later observation of the same
        # file (new `event_id`), and a foreign user's observation of a new file ...
        await producer.publish(first)
        await producer.publish(_envelope(_observation(path, label="renamed.md")))
        foreign = _fresh_path()
        await producer.publish(_envelope(_observation(foreign, user_id=uuid4())))
        # ... then an ordered marker. One subscription, processed in order and
        # inline (SD-6): once the marker is promoted, all three were handled.
        await producer.publish(_envelope(_observation(marker)))
        await wait_until(lambda: _layer_is(database, marker_id, "immediate"), timeout_s=15.0)

    assert await _row(database, thought_id) == before
    assert await _row(database, thought_id_for(_object_id(foreign))) is None
    assert await _count(database) == 2

    requested = [validate_payload(REQUESTED, envelope.payload) for envelope in autonomy]
    assert [payload.thought_id for payload in requested] == [thought_id, marker_id]  # type: ignore[union-attr]
    assert all(envelope.source_engine == "cognitive-state-engine" for envelope in autonomy)
    assert requested[0].title == "Review the workspace after activity in notes.md"  # type: ignore[union-attr]


async def test_a_persisted_t1_proposal_crosses_the_real_bus_with_its_authored_execution_fields(
    producer: BoundEventBus,
    autonomy: list[EventEnvelope],
    database: AsyncEngine,
    postgres_container: PostgresContainer,
    nats_container,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**Phase 4F.P, P4 (A-4FP-6), required test A.** The production app
    persists T1's proposal, and the one request it sends carries that row's
    `operation` and `parameters` unchanged: `"list"` and an explicit `{}` --
    neither dropped, defaulted nor turned into `None`."""
    path = _fresh_path()
    thought_id = thought_id_for(_object_id(path))

    async with _running_engine(postgres_container, nats_container, monkeypatch):
        await producer.publish(_envelope(_observation(path)))
        await wait_until(lambda: _layer_is(database, thought_id, "immediate"), timeout_s=15.0)
        await wait_until(lambda: len(autonomy) >= 1, timeout_s=15.0)

    row = await _row(database, thought_id)
    assert row is not None
    persisted = row["proposed_action"]
    assert (persisted["operation"], persisted["parameters"]) == ("list", {})

    assert len(autonomy) == 1
    wire = autonomy[0].payload
    assert wire["operation"] == persisted["operation"]
    assert wire["parameters"] == persisted["parameters"]
    assert isinstance(wire["parameters"], dict)
    for field in ("category", "risk", "action_type", "execution_target", "verification_method"):
        assert wire[field] == persisted[field], field
    received = validate_payload(REQUESTED, wire)
    assert isinstance(received, AutonomyDecisionRequestedPayload)
    assert (received.operation, received.parameters) == ("list", {})
