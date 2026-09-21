"""Autonomy Level 2 against **real PostgreSQL and a real NATS bus** — Phase
4F.5, TDD 4F.5 §12.

Four claims are only decidable here, and a fake would prove that the fake
agrees with itself:

1. **The `action.execute` RPC really is request/reply over a real broker** —
   `BoundEventBus.request()` against a real responder on a real connection,
   with the reply parsed back through the real contract.
2. **The 15-second bound is a real bounded wait** — a deliberately silent
   responder, a real elapsed timeout, and `DecisionOutcome.TIMEOUT` rather than
   a hang or a generic failure.
3. **`EXECUTE` and `TIMEOUT` persist** in the real `autonomy.decision_log`
   through the real repository and the real migration chain, read back with
   **independent SQL on its own connection** so a repository bug cannot agree
   with itself.
4. **The allow-list is enforced by the real bus**, not merely declared — a
   subject outside `PUBLISHABLE_SUBJECTS` is refused at the boundary.

**Why not the shared `postgres_session_factory` fixture.** It binds every
session to one connection inside a transaction it rolls back, so writes never
commit and are invisible to another connection. Both properties are wrong when
the claim is that a decision is *persisted*. This composes the production
`create_engine`/`create_session_factory` instead and cleans up by deleting rows
— the same reasoning 4F.3 and 4F.4 both recorded.

`@pytest.mark.real_infra`: requires Docker.
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
from nova_autonomy_engine.clients.action_dispatch import ActionDispatchClient
from nova_autonomy_engine.config import Settings
from nova_autonomy_engine.domain.decision import DecisionRequest, decide
from nova_autonomy_engine.domain.models import (
    AutonomyLevel,
    DecisionOutcome,
    PermissionCategory,
    PermissionGrant,
    Policy,
    PolicyEffect,
    PolicyMatch,
    RiskLevel,
    TrustInputStatus,
)
from nova_autonomy_engine.domain.ports import ActionDispatchTimeout
from nova_autonomy_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_autonomy_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_autonomy_engine.main import create_app
from nova_autonomy_engine.repository.postgres_autonomy_repository import (
    PostgresAutonomyRepository,
)
from nova_contracts import ActionResultPayload
from nova_eventbus_sdk import BoundEventBus, SubjectNotAllowedError
from nova_eventbus_sdk.backends.nats import NatsEventBus
from nova_service_kit import create_engine, create_session_factory
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from testcontainers.postgres import PostgresContainer

from tests.fakes.trust_source import StubTrustSource

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

USER = UUID("00000000-0000-0000-0000-0000000004f5")

#: Below the `low` ceiling, so an `AUTO_EXECUTE` policy is not inert.
LOW = RiskLevel.LOW


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["AUTONOMY_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
async def database(postgres_container: PostgresContainer) -> AsyncIterator[AsyncEngine]:
    """A real, **committing** engine. Each test starts from an empty decision
    log so "one row" is a fact about this test rather than about ordering."""
    engine = create_engine(postgres_container.get_connection_url())
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM autonomy.decision_log"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM autonomy.decision_log"))
    await engine.dispose()


@pytest.fixture
def repository(database: AsyncEngine) -> PostgresAutonomyRepository:
    return PostgresAutonomyRepository(create_session_factory(database))


@pytest.fixture
async def bus(nats_container) -> AsyncIterator[BoundEventBus]:  # type: ignore[no-untyped-def]
    """The **real** allow-listed bus this engine binds in `main.py`, over a
    real NATS connection — not the in-memory backend."""
    backend = NatsEventBus(servers=nats_container.nats_uri())
    await backend.connect()
    bound = BoundEventBus(
        backend,
        engine_name="autonomy-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )
    yield bound
    await backend.close()


@pytest.fixture
async def responder(nats_container) -> AsyncIterator[list[UUID]]:  # type: ignore[no-untyped-def]
    """A real `action.execute` responder standing in for `action-engine`.

    **It is not a mock of the thing under test.** `action-engine`'s own
    consumer is proven by its own suite and is not modified by this slice;
    what this fixture makes real is the *transport* — a genuine request/reply
    round trip over a genuine broker, which is the claim §12 requires.
    """
    served: list[UUID] = []
    backend = NatsEventBus(servers=nats_container.nats_uri())
    await backend.connect()

    async def _handle(envelope):  # type: ignore[no-untyped-def]
        action_id = UUID(str(envelope.payload["action_id"]))
        served.append(action_id)
        return ActionResultPayload(action_id=action_id, status="completed")

    await backend.serve("action.execute", _handle, source_engine="action-engine-stub")
    await asyncio.sleep(0.1)  # let the subscription register before the request
    yield served
    await backend.close()


def _request(**overrides: object) -> DecisionRequest:
    fields: dict[str, object] = {
        "action_type": "filesystem",
        "execution_target": "filesystem",
        "verification_method": "none",
    }
    fields.update(overrides)
    return DecisionRequest(
        user_id=USER,
        category=PermissionCategory.CREATE,
        risk=LOW,
        title="4F.5 real-infrastructure dispatch",
        **fields,  # type: ignore[arg-type]
    )


def _auto_execute() -> Policy:
    return Policy(
        user_id=USER,
        name="auto-execute low-risk creates",
        effect=PolicyEffect.AUTO_EXECUTE,
        match=PolicyMatch(category=PermissionCategory.CREATE),
    )


def _open_grant() -> PermissionGrant:
    return PermissionGrant(
        user_id=USER, category=PermissionCategory.CREATE, max_risk=RiskLevel.CRITICAL
    )


async def _rows(database: AsyncEngine) -> list[dict]:
    """Read the real table with real SQL on its own connection.

    Deliberately not `list_decision_log`: the claim is about what is *in the
    database*, and asking the object that wrote it would let a repository-level
    bug agree with itself.
    """
    async with database.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT subject_id, autonomy_level, outcome, reason, policy_checks "
                "FROM autonomy.decision_log ORDER BY created_at"
            )
        )
        return [dict(row) for row in result.mappings().all()]


# --- X-1: Level 2 is selectable, through the production route ---------------


@pytest.fixture
async def http(database: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    """A real HTTP client against a **real uvicorn server in this test's own
    event loop**, backed by the real Postgres repository.

    Not `TestClient`: it drives the app through an `anyio` portal on a separate
    thread with its own event loop, and the asyncpg connections this test
    creates belong to *this* loop — crossing them raises "got Future attached
    to a different loop". Serving in-loop removes the thread boundary, and the
    request still crosses a real TCP socket to a real server.
    """
    app = create_app(
        Settings(primary_user_id=USER),
        repository=PostgresAutonomyRepository(create_session_factory(database)),
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
    try:
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{bound.getsockname()[1]}", timeout=10.0
        ) as client:
            yield client
    finally:
        server.should_exit = True
        await task


async def test_x1_level_two_is_selectable_through_the_production_route(
    http: httpx.AsyncClient, database: AsyncEngine
) -> None:
    """**X-1.** `PUT /v1/autonomy/level {"level": 2}` returns **200** and
    persists in real Postgres, read back through the production `GET`.

    The 4D refusal is gone, and the row is real — a fake repository could not
    decide that the `SMALLINT` column accepts it or that the round trip
    survives a commit.
    """
    async with database.begin() as connection:
        await connection.execute(text("DELETE FROM autonomy.autonomy_level_setting"))

    written = await http.put("/v1/autonomy/level", json={"level": 2})
    assert written.status_code == 200, written.text
    assert written.json()["level"] == 2

    read_back = await http.get("/v1/autonomy/level")
    assert read_back.json()["level"] == 2
    assert read_back.json()["configured"] is True

    # Verified independently of the repository that wrote it.
    async with database.connect() as connection:
        result = await connection.execute(
            text("SELECT level FROM autonomy.autonomy_level_setting WHERE user_id = :u"),
            {"u": USER},
        )
        assert result.scalar_one() == int(AutonomyLevel.ASSISTED)


@pytest.mark.parametrize("level", [3, 4, 5])
async def test_x2_levels_three_to_five_are_still_refused_through_the_route(
    http: httpx.AsyncClient, level: int
) -> None:
    """**X-2** against real Postgres: the refusal survives, and nothing is
    stored for a level with no defined semantics."""
    response = await http.put("/v1/autonomy/level", json={"level": level})

    assert response.status_code == 422
    assert "no defined semantics" in response.json()["detail"]


# --- the real RPC ------------------------------------------------------------


async def test_a_level_two_decision_dispatches_over_real_nats_and_persists_execute(
    bus: BoundEventBus,
    responder: list[UUID],
    repository: PostgresAutonomyRepository,
    database: AsyncEngine,
) -> None:
    """**X-3 and X-11 against real infrastructure.**

    Real `decide()` → real `BoundEventBus.request()` → real NATS → real
    responder → real reply → real `autonomy.decision_log` row, verified by
    independent SQL.
    """
    dispatcher = ActionDispatchClient(bus, timeout_seconds=15.0)

    result = await decide(
        _request(),
        level=AutonomyLevel.ASSISTED,
        policies=[_auto_execute()],
        grants=[_open_grant()],
        trust_source=StubTrustSource(status=TrustInputStatus.UNAVAILABLE),
        dispatcher=dispatcher,
    )

    assert result.outcome is DecisionOutcome.EXECUTE
    # The RPC really crossed the broker, exactly once.
    assert responder == [result.log_entry.subject_id]

    await repository.append_decision_log(result.log_entry)

    rows = await _rows(database)
    assert len(rows) == 1
    assert rows[0]["subject_id"] == result.log_entry.subject_id
    assert rows[0]["outcome"] == DecisionOutcome.EXECUTE.value
    assert rows[0]["autonomy_level"] == int(AutonomyLevel.ASSISTED)

    # X-11's third clause: **the permitting policy checks** are in the row, so
    # the log explains *why* the action was allowed to execute rather than only
    # that it was. A dispatch whose justification is not recorded would be an
    # audit gap, and the decision log is this slice's whole audit trail.
    recorded = rows[0]["policy_checks"]
    assert len(recorded) == 1
    assert recorded[0]["effect"] == PolicyEffect.AUTO_EXECUTE.value
    assert recorded[0]["matched"] is True


async def test_trust_unavailable_did_not_block_that_dispatch(
    bus: BoundEventBus, responder: list[UUID]
) -> None:
    """**§22.7 against real infrastructure.** CF-10's `UNAVAILABLE` state is
    what the production adapter returns, and the dispatch above happened with
    it — while `score` stayed `None` and no threshold was consulted."""
    result = await decide(
        _request(),
        level=AutonomyLevel.ASSISTED,
        policies=[_auto_execute()],
        grants=[_open_grant()],
        trust_source=StubTrustSource(status=TrustInputStatus.UNAVAILABLE),
        dispatcher=ActionDispatchClient(bus, timeout_seconds=15.0),
    )

    assert result.outcome is DecisionOutcome.EXECUTE
    assert result.trust is not None
    assert result.trust.score is None
    assert result.trust.input_status is TrustInputStatus.UNAVAILABLE
    assert len(responder) == 1


# --- the fail-closed controls, against real infrastructure -------------------


async def test_absent_policy_dispatches_nothing_over_the_real_bus(
    bus: BoundEventBus, responder: list[UUID]
) -> None:
    """**The fail-closed control, and it is mandatory.** An empty policy set
    over a live broker with a live responder still dispatches nothing."""
    result = await decide(
        _request(),
        level=AutonomyLevel.ASSISTED,
        policies=[],
        grants=[_open_grant()],
        trust_source=StubTrustSource(status=TrustInputStatus.UNAVAILABLE),
        dispatcher=ActionDispatchClient(bus, timeout_seconds=15.0),
    )

    assert result.outcome is DecisionOutcome.PROPOSE
    assert responder == []


async def test_a_missing_execution_field_dispatches_nothing_over_the_real_bus(
    bus: BoundEventBus, responder: list[UUID]
) -> None:
    """**X-14.** No guessed action reaches the broker."""
    result = await decide(
        _request(execution_target=None),
        level=AutonomyLevel.ASSISTED,
        policies=[_auto_execute()],
        grants=[_open_grant()],
        trust_source=StubTrustSource(status=TrustInputStatus.UNAVAILABLE),
        dispatcher=ActionDispatchClient(bus, timeout_seconds=15.0),
    )

    assert result.outcome is DecisionOutcome.PROPOSE
    assert responder == []


# --- the real bounded timeout ------------------------------------------------


async def test_a_silent_responder_produces_a_persisted_timeout_and_no_retry(
    nats_container,  # type: ignore[no-untyped-def]
    bus: BoundEventBus,
    repository: PostgresAutonomyRepository,
    database: AsyncEngine,
) -> None:
    """**X-13 against a real bounded wait.**

    A responder that accepts the request and never replies. The wait is real,
    the elapsed timeout is real, and the outcome is `TIMEOUT` — distinct from a
    denial and from a failure — persisted in the real decision log.

    The bound is shortened to keep the suite fast; **15.0 is the production
    default and is asserted separately** in
    `tests/unit/test_action_dispatch_client.py`, which also proves the seconds
    → milliseconds conversion. What this test decides is that the wait is
    genuinely bounded and that nothing is retried.
    """
    silent = NatsEventBus(servers=nats_container.nats_uri())
    await silent.connect()
    requests: list[UUID] = []

    async def _never_reply(envelope):  # type: ignore[no-untyped-def]
        requests.append(UUID(str(envelope.payload["action_id"])))
        await asyncio.sleep(30)
        raise AssertionError("unreachable: the client must have given up first")

    await silent.serve("action.execute", _never_reply, source_engine="silent-stub")
    await asyncio.sleep(0.1)

    try:
        result = await decide(
            _request(),
            level=AutonomyLevel.ASSISTED,
            policies=[_auto_execute()],
            grants=[_open_grant()],
            trust_source=StubTrustSource(status=TrustInputStatus.UNAVAILABLE),
            dispatcher=ActionDispatchClient(bus, timeout_seconds=1.0),
        )

        assert result.outcome is DecisionOutcome.TIMEOUT
        assert result.outcome is not DecisionOutcome.DENY
        # Exactly one request reached the broker: no retry, no second dispatch.
        assert len(requests) == 1

        await repository.append_decision_log(result.log_entry)
        rows = await _rows(database)
        assert len(rows) == 1
        assert rows[0]["outcome"] == DecisionOutcome.TIMEOUT.value
        assert "no reply" in rows[0]["reason"]
    finally:
        await silent.close()


async def test_the_dispatch_client_raises_the_typed_timeout(
    nats_container,  # type: ignore[no-untyped-def]
    bus: BoundEventBus,
) -> None:
    """The adapter translates the transport's `TimeoutError` into
    `ActionDispatchTimeout`, so a caller never matches on a builtin."""
    from nova_contracts import ActionExecuteRequestPayload

    payload = ActionExecuteRequestPayload(
        action_id=uuid4(),
        action_type="filesystem",
        priority="normal",
        source="autonomy-engine",
        requested_by=USER,
        execution_target="filesystem",
        verification_method="none",
        requesting_engine="autonomy-engine",
        correlation_id=uuid4(),
    )
    # Nothing is serving on this connection, so the wait simply elapses.
    with pytest.raises(ActionDispatchTimeout, match="no reply"):
        await ActionDispatchClient(bus, timeout_seconds=1.0).dispatch(payload)


# --- the allow-list, enforced by the real bus --------------------------------


async def test_the_real_bus_refuses_any_subject_but_action_execute(
    bus: BoundEventBus,
) -> None:
    """**TDD 4F §16 control 6 at runtime**, not merely in a frozenset literal.

    4D's control 8 asserted the engine never called the bus at all; 4F.5
    retires that and replaces it with this — one subject, and the boundary
    refuses everything else."""
    from nova_contracts import ActionResultPayload as _AnyPayload

    for forbidden in ("autonomy.decision.made", "action.result", "perception.workspace.observed"):
        with pytest.raises(SubjectNotAllowedError):
            await bus.request(
                forbidden,
                _AnyPayload(action_id=uuid4(), status="completed"),
                source_engine="autonomy-engine",
                timeout_ms=200,
            )


async def test_this_engine_still_subscribes_to_nothing(bus: BoundEventBus) -> None:
    """`SUBSCRIBABLE_SUBJECTS` is empty, so there is still no autonomy subject
    that could leak anywhere."""

    async def _handler(envelope):  # type: ignore[no-untyped-def]
        raise AssertionError("unreachable")

    with pytest.raises(SubjectNotAllowedError):
        await bus.subscribe("action.execute", _handler)
