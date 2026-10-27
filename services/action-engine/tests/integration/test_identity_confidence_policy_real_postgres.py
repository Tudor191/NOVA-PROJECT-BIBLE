"""**CF-9's write surface, end to end against real PostgreSQL** — Phase 4F.4.

This is the evidence that decides the slice. Everything that matters about a
write surface for an authorization threshold is only decidable against the real
store and the real gate:

```
real HTTP request  →  api/identity_confidence_policy.py
  →  real PostgresActionRepository  →  real action.identity_confidence_policy
  →  real execute_action() stage 3  →  admitted or denied
```

**Nothing here inserts the ORM row directly.** ADR-032 names exactly that — *"the
sole write anywhere is a `real_infra` test inserting the ORM row directly"* — as
the reason decision point 2 counts as unimplemented. Evidence for the fix must
therefore go through the production surface, or it proves the same nothing.

**Stage 3 is the real `execute_action`**, not a re-implementation of the
threshold comparison. `IdentityPort` is faked because it is an Event-Bus RPC to
`world-model-engine` and is not the subject of any claim here; the policy row,
the repository, the table and the gate are all real.

**Why not the shared `postgres_session_factory` fixture.** It binds every session
to one connection inside a transaction it rolls back, so writes never commit and
are invisible to another connection. Both properties are wrong when the claim is
that a written policy is *persisted* and later *read back by the gate*. This
composes the production `create_engine`/`create_session_factory` instead and
cleans up by deleting rows.

`@pytest.mark.real_infra`: requires Docker. **Not executed in the environment
this file was written in** — no Docker daemon is reachable there.
"""

from __future__ import annotations

import asyncio
import os
import socket
import time
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
import uvicorn
from nova_action_engine.config import Settings
from nova_action_engine.domain.pipeline import execute_action
from nova_action_engine.main import create_app
from nova_action_engine.repository.postgres_action_repository import PostgresActionRepository
from nova_contracts import ActionExecuteRequestPayload
from nova_service_kit import create_engine, create_session_factory
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from testcontainers.postgres import PostgresContainer

from tests.fakes.capability_port import FakeCapabilityPort
from tests.fakes.communication_port import FakeCommunicationPort
from tests.fakes.event_publisher import FakeEventPublisher
from tests.fakes.identity_port import FakeIdentityPort

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"

ROUTE = "/v1/action/identity-confidence-policy"

#: The deployment's single trusted identity. Every row written through the
#: surface must carry this and nothing else.
PRIMARY_USER_ID = UUID("00000000-0000-0000-0000-0000000004f4")

#: `classify_risk` returns LOW for any operation outside its named sets, so this
#: is a genuinely LOW-risk action rather than one forced into the tier.
LOW_RISK_OPERATION = "sync"

#: Below the 0.75 single-signal ceiling, so it is a confidence a real identity
#: signal could actually produce.
REAL_CONFIDENCE = 0.70


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["ACTION_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
async def database(postgres_container: PostgresContainer) -> AsyncIterator[AsyncEngine]:
    """A real, committing engine. Each test starts from an empty policy table so
    "absent policy" is a fact about this test rather than about ordering."""
    engine = create_engine(postgres_container.get_connection_url())
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM action.identity_confidence_policy"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM action.identity_confidence_policy"))
    await engine.dispose()


@pytest.fixture
def repository(database: AsyncEngine) -> PostgresActionRepository:
    return PostgresActionRepository(create_session_factory(database))


@pytest.fixture
async def client(
    repository: PostgresActionRepository, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    """A real HTTP client against a **real uvicorn server in this test's own
    event loop**.

    Not `TestClient`: it drives the app through an `anyio` portal on a separate
    thread with its own event loop, and the SQLAlchemy/asyncpg connections this
    test creates belong to *this* loop. Crossing them raises
    `got Future attached to a different loop` — which is exactly how the first
    CI run of this file failed. Serving in-loop removes the thread boundary
    entirely, and costs nothing: the request still crosses a real TCP socket to
    a real uvicorn server running the real app.
    """
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(
        Settings(primary_user_id=PRIMARY_USER_ID),
        repository=repository,
        capability_port=FakeCapabilityPort(),
        communication_port=FakeCommunicationPort(),
        identity_port=FakeIdentityPort(),
    )
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())

    deadline = time.monotonic() + 30.0
    while not server.started:
        if task.done():  # surface a startup failure rather than timing out on it
            await task
        if time.monotonic() > deadline:
            raise RuntimeError("uvicorn did not start within the deadline")
        await asyncio.sleep(0.02)

    bound: socket.socket = server.servers[0].sockets[0]
    base_url = f"http://127.0.0.1:{bound.getsockname()[1]}"
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as running:
            yield running
    finally:
        server.should_exit = True
        await task


async def _rows(database: AsyncEngine) -> list[dict]:
    """Read the real table with real SQL on its own connection.

    Deliberately not `find_identity_confidence_policy`: the claim is about what
    is *in the database*, and asking the object that wrote it would let a
    repository-level bug agree with itself.
    """
    async with database.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT user_id, minimum_confidence_by_risk "
                "FROM action.identity_confidence_policy"
            )
        )
        return [dict(row) for row in result.mappings().all()]


async def _run_low_risk_action(
    repository: PostgresActionRepository, *, confidence: float | None
) -> str:
    """Drive the **real** pipeline and return the resulting status.

    `confidence` scripts the identity RPC; everything downstream of it — the
    policy lookup, the threshold selection and the comparison — is production
    code reading the real row.
    """
    identity_port = FakeIdentityPort()
    if confidence is not None:
        identity_port.confidence_by_user[PRIMARY_USER_ID] = confidence

    result = await execute_action(
        ActionExecuteRequestPayload(
            action_id=uuid4(),
            action_type="filesystem",
            priority="normal",
            source="tdd-4f4-test",
            requested_by=PRIMARY_USER_ID,
            execution_target="filesystem",
            parameters={"operation": LOW_RISK_OPERATION},
            # Required by the contract; omitted in the first draft, which is
            # what the first CI run caught.
            verification_method="none",
            requesting_engine="tdd-4f4-test",
            correlation_id=uuid4(),
        ),
        repository=repository,
        capability_port=FakeCapabilityPort(),
        communication_port=FakeCommunicationPort(),
        identity_port=identity_port,
        event_publisher=FakeEventPublisher(),
        approval_timeout_seconds=5.0,
    )
    return result.status


# --- W-1: the production surface really persists ----------------------------


async def test_w1_a_policy_written_through_the_api_is_persisted_and_read_back(
    client: httpx.AsyncClient, repository: PostgresActionRepository, database: AsyncEngine
) -> None:
    """**CF-9 closure condition 1.** Created through a production surface, and
    read back by the same method stage 3 uses, in real Postgres."""
    written = await client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.5}})
    assert written.status_code == 200, written.text

    rows = await _rows(database)
    assert len(rows) == 1
    assert rows[0]["user_id"] == PRIMARY_USER_ID
    assert rows[0]["minimum_confidence_by_risk"] == {"low": 0.5}

    policy = await repository.find_identity_confidence_policy(PRIMARY_USER_ID)
    assert policy is not None
    assert policy.minimum_confidence_by_risk == {"low": 0.5}


async def test_the_upsert_replaces_rather_than_duplicating_or_merging(
    client: httpx.AsyncClient, database: AsyncEngine
) -> None:
    """One row per user is a PRIMARY KEY fact, and removing a tier must stay
    expressible — both are only decidable against the real table."""
    await client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.5, "moderate": 0.6}})
    await client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.4}})

    rows = await _rows(database)
    assert len(rows) == 1, f"the upsert created a second row: {rows}"
    assert rows[0]["minimum_confidence_by_risk"] == {"low": 0.4}


# --- W-2 / W-3: the gate itself ---------------------------------------------


async def test_w3_absent_policy_denies_a_low_risk_action(
    repository: PostgresActionRepository, database: AsyncEngine
) -> None:
    """**The fail-closed negative control, and the reason CF-9 exists.**

    With no row, stage 3's threshold is 1.0 at every tier, and a real
    single-signal confidence cannot reach it. Asserted *before* any admission
    test, so a later pass cannot be mistaken for the gate never having worked.
    """
    assert await _rows(database) == []

    assert await _run_low_risk_action(repository, confidence=REAL_CONFIDENCE) == "denied"


async def test_w2_a_policy_written_through_the_api_admits_the_same_action(
    client: httpx.AsyncClient, repository: PostgresActionRepository
) -> None:
    """**The slice's exit criterion: "Stage 3 can pass for LOW risk."**

    The only thing that changed between this test and the one above is a row
    written through the production HTTP surface.
    """
    await client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.5}})

    assert await _run_low_risk_action(repository, confidence=REAL_CONFIDENCE) != "denied"


async def test_a_threshold_above_the_real_confidence_still_denies(
    client: httpx.AsyncClient, repository: PostgresActionRepository
) -> None:
    """Writing a policy is not the same as weakening the gate: a threshold the
    signal cannot meet still denies."""
    await client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.75}})

    assert await _run_low_risk_action(repository, confidence=0.5) == "denied"


async def test_a_tier_omitted_from_the_map_stays_fail_closed(
    client: httpx.AsyncClient, repository: PostgresActionRepository
) -> None:
    """**§16.5's central property.** Strictness is expressed by omission: a
    policy that configures only `moderate` leaves `low` at 1.0."""
    await client.put(ROUTE, json={"minimum_confidence_by_risk": {"moderate": 0.5}})

    assert await _run_low_risk_action(repository, confidence=REAL_CONFIDENCE) == "denied"


async def test_an_empty_stored_map_is_not_an_absent_row_and_stays_fail_closed(
    client: httpx.AsyncClient, repository: PostgresActionRepository, database: AsyncEngine
) -> None:
    """**TDD 4F.4 §10.1 negative test 6**, and the degenerate end of §16.5.

    Two different security states share one observable behaviour, and this
    separates them. An **absent row** and a **stored empty map** both leave
    stage 3 at the fail-closed 1.0 for every tier -- but only one of them is a
    configuration an operator performed on purpose. The row is asserted to
    *exist* (real SQL, and `find_identity_confidence_policy` returning a policy
    rather than `None`, which is the exact distinction stage 3's
    `policy is not None` sees) and the LOW-risk action is asserted to be denied
    anyway.

    That is what makes "maximum strictness everywhere" expressible as a written
    row instead of only as the absence of one: an empty map configures nothing,
    so `risk.value in policy.minimum_confidence_by_risk` is false at LOW and the
    threshold stays 1.0 -- above the 0.75 a real single signal can reach.

    LOW is the tier TDD 4F §18's exit criterion names; every other tier reaches
    1.0 through the same lookup on the same empty mapping.
    """
    written = await client.put(ROUTE, json={"minimum_confidence_by_risk": {}})
    assert written.status_code == 200, written.text

    rows = await _rows(database)
    assert len(rows) == 1, f"an empty map must still store a row, got {rows}"
    assert rows[0]["user_id"] == PRIMARY_USER_ID
    assert rows[0]["minimum_confidence_by_risk"] == {}

    policy = await repository.find_identity_confidence_policy(PRIMARY_USER_ID)
    assert policy is not None, "an empty map must not read back as an absent policy"
    assert policy.minimum_confidence_by_risk == {}

    assert await _run_low_risk_action(repository, confidence=REAL_CONFIDENCE) == "denied"


async def test_an_absent_identity_signal_still_denies_even_with_a_policy(
    client: httpx.AsyncClient, repository: PostgresActionRepository
) -> None:
    """TDD 3D §10's other fail-closed path, re-asserted because this slice is
    the first thing that could have disturbed it: no confidence means 0.0."""
    await client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.5}})

    assert await _run_low_risk_action(repository, confidence=None) == "denied"


# --- W-8: DELETE restores fail-closed ---------------------------------------


async def test_w8_delete_restores_fail_closed_behaviour(
    client: httpx.AsyncClient, repository: PostgresActionRepository, database: AsyncEngine
) -> None:
    """**The most important test in this file.**

    Admission, then deletion, then denial of the identical action — proving
    DELETE removes the policy rather than leaving a permissive remnant.
    """
    await client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.5}})
    assert await _run_low_risk_action(repository, confidence=REAL_CONFIDENCE) != "denied"

    assert (await client.delete(ROUTE)).status_code == 204
    assert await _rows(database) == []

    assert await _run_low_risk_action(repository, confidence=REAL_CONFIDENCE) == "denied"


# --- the identity boundary, against the real table ---------------------------


async def test_a_client_supplied_user_id_never_reaches_the_real_row(
    client: httpx.AsyncClient, database: AsyncEngine
) -> None:
    hostile = uuid4()
    response = await client.put(
        ROUTE,
        json={"minimum_confidence_by_risk": {"low": 0.5}, "user_id": str(hostile)},
    )

    assert response.status_code == 200
    rows = await _rows(database)
    assert [row["user_id"] for row in rows] == [PRIMARY_USER_ID]
    assert hostile not in [row["user_id"] for row in rows]


async def test_rejected_input_leaves_the_real_table_untouched(
    client: httpx.AsyncClient, database: AsyncEngine
) -> None:
    """Invalid input must not mutate state — proven against the table, not
    against a fake's dictionary."""
    await client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.5}})

    too_high = await client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.9}})
    unknown_tier = await client.put(ROUTE, json={"minimum_confidence_by_risk": {"nope": 0.5}})
    assert too_high.status_code == 422
    assert unknown_tier.status_code == 422

    rows = await _rows(database)
    assert rows[0]["minimum_confidence_by_risk"] == {"low": 0.5}
