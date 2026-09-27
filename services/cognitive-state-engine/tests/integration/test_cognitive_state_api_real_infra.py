"""`/v1/cognitive-state/*` against **real PostgreSQL over a real socket** -- Phase
4F.7, TDD 4F.7 §16 P-2, P-3, P-4, P-6 and P-8.

Every claim is made on the **production** `create_app` -- its own
`nova-service-kit` engine and repository, its own lifespan -- served by a real
uvicorn in this test's own event loop (the `action-engine` 4F.4 precedent), and
asserted on the body a real HTTP client receives.

**Test data is test infrastructure (RS-8).** The thoughts below are written by
the real repository's `upsert_thought` **in this test only**, to prove that a
real row serializes. They are not evidence that NOVA creates thoughts: nothing
in 4F.7's served path can write one (P-14), and production holds none until 4F.P
(§15 K-4).

`@pytest.mark.real_infra`: requires Docker (or equivalent real services).
"""

from __future__ import annotations

import asyncio
import os
import socket
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
import uvicorn
from nova_cognitive_state_engine.config import Settings
from nova_cognitive_state_engine.domain.focus import select_focus
from nova_cognitive_state_engine.domain.models import (
    ActiveThought,
    AttentionLayer,
    ProposedAction,
)
from nova_cognitive_state_engine.main import create_app
from nova_cognitive_state_engine.repository.postgres_cognitive_state_repository import (
    PostgresCognitiveStateRepository,
)
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

PRIMARY = UUID("00000000-0000-0000-0000-00000000f007")
SECOND = UUID("00000000-0000-0000-0000-0000000000aa")
MOMENT = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)

PROPOSAL = ProposedAction.model_validate(
    {
        "category": "modify",
        "risk": "low",
        "action_type": "filesystem",
        "execution_target": "filesystem",
        "verification_method": "checksum",
        "title": "rotate the scratch directory",
        "detail": "keep the last seven",
    }
)


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["COGNITIVE_STATE_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
async def database(postgres_container: PostgresContainer) -> AsyncIterator[AsyncEngine]:
    """A **committing** engine, so the served app's own connections see the rows
    -- the shared rollback fixture's writes are invisible to a second connection
    (4F.3/4F.4/4F.5's recorded reasoning)."""
    engine = create_async_engine(postgres_container.get_connection_url())
    await _clear(engine)
    yield engine
    await _clear(engine)
    await engine.dispose()


async def _clear(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM cognitive_state.active_thought"))
        await connection.execute(text("DELETE FROM cognitive_state.sensor_state"))


@pytest.fixture
def repository(database: AsyncEngine) -> PostgresCognitiveStateRepository:
    return PostgresCognitiveStateRepository(async_sessionmaker(database, expire_on_commit=False))


@asynccontextmanager
async def _served(
    postgres_container: PostgresContainer,
    nats_container,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
    *,
    focus_capacity: int = 7,
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "nats")
    monkeypatch.setenv("NATS_URL", nats_container.nats_uri())
    app = create_app(
        Settings(
            postgres_dsn=postgres_container.get_connection_url(),
            primary_user_id=PRIMARY,
            focus_capacity=focus_capacity,
        )
    )
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
            yield client
    finally:
        server.should_exit = True
        await task


def _thought(
    *,
    user_id: UUID = PRIMARY,
    layer: AttentionLayer = AttentionLayer.ACTIVE,
    priority: int = 3,
    updated: datetime = MOMENT,
    **overrides: object,
) -> ActiveThought:
    values: dict[str, object] = {
        "thought_id": uuid4(),
        "user_id": user_id,
        "description": "Investigate recurring build failures",
        "priority": priority,
        "confidence": 0.7,
        "current_progress": 0.25 if layer is not AttentionLayer.ARCHIVED else 0.0,
        "attention_layer": layer,
        "created_at": MOMENT,
        "updated_at": updated,
    }
    values.update(overrides)
    return ActiveThought(**values)  # type: ignore[arg-type]


def _served_thought(thought: ActiveThought) -> dict:  # type: ignore[type-arg]
    """What §7.1 says a thought serializes as -- written out, not derived from the
    response model, so a model that drops or renames a field fails."""
    return {
        "thought_id": str(thought.thought_id),
        "description": thought.description,
        "priority": thought.priority,
        "confidence": thought.confidence,
        "dependencies": [str(value) for value in thought.dependencies],
        "estimated_completion": (
            thought.estimated_completion.isoformat().replace("+00:00", "Z")
            if thought.estimated_completion is not None
            else None
        ),
        "related_memories": [str(value) for value in thought.related_memories],
        "related_projects": [str(value) for value in thought.related_projects],
        "current_progress": thought.current_progress,
        "attention_layer": thought.attention_layer.value,
        "created_at": thought.created_at.isoformat().replace("+00:00", "Z"),
        "updated_at": thought.updated_at.isoformat().replace("+00:00", "Z"),
        "proposed_action": (
            thought.proposed_action.model_dump(mode="json")
            if thought.proposed_action is not None
            else None
        ),
    }


# --- P-3: an empty store returns empty --------------------------------------------------


async def test_p3_an_empty_store_serves_empty_bodies(
    database: AsyncEngine,
    postgres_container: PostgresContainer,
    nats_container,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with _served(postgres_container, nats_container, monkeypatch, focus_capacity=4) as client:
        thoughts = await client.get("/v1/cognitive-state/thoughts")
        focus = await client.get("/v1/cognitive-state/focus")
        sensors = await client.get("/v1/cognitive-state/sensors")

    assert (thoughts.status_code, focus.status_code, sensors.status_code) == (200, 200, 200)
    assert thoughts.json() == {"thoughts": []}
    assert focus.json() == {"capacity": 4, "entries": []}
    assert sensors.json() == {"sensors": []}


# --- P-2: identity is server-side --------------------------------------------------------


async def test_p2_only_the_primary_users_thoughts_are_served(
    repository: PostgresCognitiveStateRepository,
    postgres_container: PostgresContainer,
    nats_container,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mine = await repository.upsert_thought(_thought(priority=2))
    theirs = await repository.upsert_thought(_thought(user_id=SECOND, priority=9))

    async with _served(postgres_container, nats_container, monkeypatch) as client:
        for query in ("", f"?user_id={SECOND}"):
            listed = (await client.get(f"/v1/cognitive-state/thoughts{query}")).json()
            focused = (await client.get(f"/v1/cognitive-state/focus{query}")).json()
            assert [t["thought_id"] for t in listed["thoughts"]] == [str(mine.thought_id)]
            assert [e["thought"]["thought_id"] for e in focused["entries"]] == [
                str(mine.thought_id)
            ]
            assert str(theirs.thought_id) not in str(listed) + str(focused)

        openapi = (await client.get("/openapi.json")).json()
    for path in ("/v1/cognitive-state/thoughts", "/v1/cognitive-state/focus"):
        assert openapi["paths"][path]["get"].get("parameters", []) == []


# --- P-4 and P-8: every Part 6 field; a proposal, and its absence ---------------------------


async def test_p4_p8_real_rows_serialize_field_for_field(
    repository: PostgresCognitiveStateRepository,
    database: AsyncEngine,
    postgres_container: PostgresContainer,
    nats_container,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two rows: one with a proposal, all three relation lists and an estimated
    completion; one with neither, whose `estimated_completion` and
    `proposed_action` are SQL `NULL` -- read back by independent SQL first -- and
    are served as `null`."""
    full = await repository.upsert_thought(
        _thought(
            dependencies=(uuid4(), uuid4()),
            related_memories=(uuid4(),),
            related_projects=(uuid4(),),
            estimated_completion=MOMENT + timedelta(days=5),
            proposed_action=PROPOSAL,
            updated=MOMENT + timedelta(minutes=1),
        )
    )
    bare = await repository.upsert_thought(_thought(layer=AttentionLayer.DORMANT))

    async with database.connect() as connection:
        nulls = (
            await connection.execute(
                text(
                    "SELECT proposed_action IS NULL, estimated_completion IS NULL "
                    "FROM cognitive_state.active_thought WHERE thought_id = :id"
                ),
                {"id": bare.thought_id},
            )
        ).one()
    assert tuple(nulls) == (True, True)

    async with _served(postgres_container, nats_container, monkeypatch) as client:
        response = await client.get("/v1/cognitive-state/thoughts")

    assert response.status_code == 200
    # `list_thoughts`' order: newest-updated first.
    assert response.json() == {"thoughts": [_served_thought(full), _served_thought(bare)]}
    served_full, served_bare = response.json()["thoughts"]
    assert served_full["proposed_action"] == PROPOSAL.model_dump(mode="json")
    assert served_bare["proposed_action"] is None
    assert served_bare["estimated_completion"] is None
    assert served_bare["attention_layer"] == "dormant"


# --- P-6: focus is `select_focus` over the same real rows -----------------------------------


async def test_p6_focus_is_select_focus_over_the_same_rows(
    repository: PostgresCognitiveStateRepository,
    postgres_container: PostgresContainer,
    nats_container,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capacity 3 against four focusable thoughts, so the cap must exclude one;
    three high-priority thoughts in non-focusable layers, so eligibility must
    exclude them; and a priority tie, so the order must be the deterministic
    `thought_id` tiebreak rather than whatever the store returned."""
    tie_a = _thought(priority=6, thought_id=UUID("00000000-0000-0000-0000-00000000000a"))
    tie_b = _thought(
        priority=6,
        layer=AttentionLayer.IMMEDIATE,
        thought_id=UUID("00000000-0000-0000-0000-00000000000b"),
    )
    top = _thought(priority=8)
    capped = _thought(priority=1)
    ineligible = [
        _thought(priority=50, layer=AttentionLayer.PASSIVE),
        _thought(priority=60, layer=AttentionLayer.DORMANT),
        _thought(priority=70, layer=AttentionLayer.ARCHIVED),
    ]
    for thought in [capped, tie_b, top, tie_a, *ineligible]:
        await repository.upsert_thought(thought)

    expected = select_focus(
        await repository.list_thoughts(user_id=PRIMARY), capacity=3, inputs=None
    )

    async with _served(postgres_container, nats_container, monkeypatch, focus_capacity=3) as client:
        body = (await client.get("/v1/cognitive-state/focus")).json()

    assert body["capacity"] == 3
    assert [e["thought"]["thought_id"] for e in body["entries"]] == [
        str(top.thought_id),
        str(tie_a.thought_id),
        str(tie_b.thought_id),
    ]
    assert body["entries"] == [
        {
            "thought": _served_thought(entry.thought),
            "score": entry.score,
            "signals_used": [signal.value for signal in entry.signals_used],
        }
        for entry in expected
    ]
    assert all(entry["signals_used"] == [] for entry in body["entries"])
