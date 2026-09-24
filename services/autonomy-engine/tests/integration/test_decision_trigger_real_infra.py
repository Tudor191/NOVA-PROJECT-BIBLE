"""The initiative trigger's consumer against **real NATS and real PostgreSQL**
-- Phase 4F.6, TDD 4F.6 §10 (*"`real_infra` -- load-bearing"*) and §19.

**No test in this file calls `decide()`.** TDD 4F.6 §10: *"The decisive
evidence: a real-infra test in which no test code calls `decide()` directly.
Anything weaker re-proves 4F.5."* Every decision here is made by the
**production** wiring: `create_app`'s lifespan binds the real allow-listed bus,
registers the real `serve()` on `autonomy.decision.requested`, and the real
handler calls the real `decide()` with the production trust adapter and the
production `ActionDispatchClient`. The test only sends a trigger and reads the
database.

**The producer here is a real `BoundEventBus` bound exactly as
`cognitive-state-engine` binds its own** -- engine name and allow-list -- over
a real NATS connection. It is not imported from that engine: control 10 forbids
one engine's code depending on another's, and that applies to its tests too.
The producer's own side (`promote_thought` over a real broker) is proven in
`services/cognitive-state-engine/tests/integration/test_decision_trigger_real_nats.py`;
the two halves meet at the one shared contract, `AutonomyDecisionRequestedPayload`.

**`action-engine` is a stand-in responder**, as in 4F.5's real-infra tier: its
consumer and its terminal-replay guard are proven by its own suite
(`tests/unit/test_pipeline.py::test_idempotent_replay_of_a_terminal_action_returns_stored_result`,
`tests/integration/test_repository_real_postgres.py::test_inserting_a_duplicate_action_id_raises_action_already_exists`)
and `action-engine` is not modified by this slice. What this file proves is
what reaches that guard: the `action_id` a redelivery carries.

**Rows are read back with independent SQL on their own connection**, never
through the repository that wrote them.

`@pytest.mark.real_infra`: requires Docker.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import nats
import pytest
from nova_autonomy_engine.config import Settings
from nova_autonomy_engine.domain.models import (
    AutonomyLevel,
    DecisionOutcome,
    PermissionCategory,
    PermissionGrant,
    Policy,
    PolicyEffect,
    PolicyMatch,
    RiskLevel,
)
from nova_autonomy_engine.main import create_app
from nova_autonomy_engine.repository.postgres_autonomy_repository import (
    PostgresAutonomyRepository,
)
from nova_contracts import ActionResultPayload, EventEnvelope
from nova_contracts.events.autonomy import (
    AutonomyDecisionReplyPayload,
    AutonomyDecisionRequestedPayload,
)
from nova_eventbus_sdk import BoundEventBus
from nova_eventbus_sdk.backends.nats import NatsEventBus
from nova_service_kit import create_engine, create_session_factory
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

SUBJECT = "autonomy.decision.requested"
NAMESPACE = UUID("0c81f3b8-e30f-5f0a-9241-8985e4b83489")
"""TDD 4F.6 §5.2's pinned literal, restated rather than imported so this file
checks the production module against the TDD, not against itself."""

USER = UUID("00000000-0000-0000-0000-0000000004f6")

_TABLES = ("decision_log", "suggestion", "policy", "permission_grant", "autonomy_level")
"""Child first: `decision_log.suggestion_id` is `ON DELETE RESTRICT`."""


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["AUTONOMY_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


async def _truncate(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        for table in _TABLES:
            await connection.execute(text(f"DELETE FROM autonomy.{table}"))


@pytest.fixture
async def database(postgres_container: PostgresContainer) -> AsyncIterator[AsyncEngine]:
    """A real, **committing** engine -- the shared rollback fixture would hide
    every write from the independent read-back (4F.5's recorded reasoning)."""
    engine = create_engine(postgres_container.get_connection_url())
    await _truncate(engine)
    yield engine
    await _truncate(engine)
    await engine.dispose()


@pytest.fixture
def repository(database: AsyncEngine) -> PostgresAutonomyRepository:
    return PostgresAutonomyRepository(create_session_factory(database))


@pytest.fixture
def nats_uri(nats_container, monkeypatch: pytest.MonkeyPatch) -> str:  # type: ignore[no-untyped-def]
    """Points `create_app`'s `get_event_bus()` at the real broker. Overrides the
    suite-wide autouse `EVENT_BUS_BACKEND=in_memory`, because the claim here is
    that the **production** bus binding serves the trigger."""
    uri: str = nats_container.nats_uri()
    monkeypatch.setenv("EVENT_BUS_BACKEND", "nats")
    monkeypatch.setenv("NATS_URL", uri)
    return uri


@asynccontextmanager
async def _serving(repository: PostgresAutonomyRepository) -> AsyncIterator[None]:
    """The production app, lifespan and all. Trust source and dispatcher are
    **not** injected: the production `UnavailableConversationalTrustSource`
    and `ActionDispatchClient` are what run."""
    app = create_app(Settings(primary_user_id=USER), repository=repository)
    async with app.router.lifespan_context(app):
        await asyncio.sleep(0.1)  # let the SUB reach the server before the first request
        yield


@pytest.fixture
async def consumer(nats_uri: str, repository: PostgresAutonomyRepository) -> AsyncIterator[None]:
    async with _serving(repository):
        yield


@pytest.fixture
async def producer(nats_uri: str) -> AsyncIterator[BoundEventBus]:
    """A real bus bound as `cognitive-state-engine` binds its own: one
    publishable subject, nothing subscribable."""
    backend = NatsEventBus(servers=nats_uri)
    await backend.connect()
    yield BoundEventBus(
        backend,
        engine_name="cognitive-state-engine",
        publishable_subjects=frozenset({SUBJECT}),
        subscribable_subjects=frozenset(),
    )
    await backend.close()


@pytest.fixture
async def action_engine(nats_uri: str) -> AsyncIterator[list[UUID]]:
    """A real `action.execute` responder standing in for `action-engine`. It
    records every `action_id` it is handed -- the value `action-engine`'s
    terminal-replay guard keys on."""
    received: list[UUID] = []
    backend = NatsEventBus(servers=nats_uri)
    await backend.connect()

    async def _handle(envelope):  # type: ignore[no-untyped-def]
        action_id = UUID(str(envelope.payload["action_id"]))
        received.append(action_id)
        return ActionResultPayload(action_id=action_id, status="completed")

    await backend.serve("action.execute", _handle, source_engine="action-engine-stub")
    await asyncio.sleep(0.1)
    yield received
    await backend.close()


def _payload(**overrides: object) -> AutonomyDecisionRequestedPayload:
    fields: dict = {
        "thought_id": uuid4(),
        "category": PermissionCategory.CREATE,
        "risk": RiskLevel.LOW,
        "action_type": "filesystem",
        "execution_target": "filesystem",
        "verification_method": "none",
        "title": "rotate the scratch directory",
        "detail": "keep the last seven",
        "priority": 3,
        "requesting_engine": "cognitive-state-engine",
        "correlation_id": uuid4(),
    }
    fields.update(overrides)
    return AutonomyDecisionRequestedPayload(**fields)


async def _trigger(
    producer: BoundEventBus, payload: AutonomyDecisionRequestedPayload | None = None
) -> tuple[UUID, AutonomyDecisionReplyPayload]:
    """One real request. Returns the request's `event_id` -- the reply's
    `causation_id`, which the SDK's `serve()` sets -- and the parsed reply."""
    payload = payload or _payload()
    reply = await producer.request(
        SUBJECT,
        payload,
        source_engine="cognitive-state-engine",
        correlation_id=payload.correlation_id,
        timeout_ms=20_000,
    )
    assert reply.causation_id is not None
    return reply.causation_id, AutonomyDecisionReplyPayload.model_validate(reply.payload)


async def _raw(uri: str, envelope: EventEnvelope) -> AutonomyDecisionReplyPayload:
    """Send a **pre-built** envelope, byte for byte. The SDK mints a fresh
    `event_id` per call, so a redelivery -- the same envelope twice -- and a
    payload the contract would refuse to build can only be sent this way."""
    connection = await nats.connect(uri)
    try:
        message = await connection.request(SUBJECT, envelope.model_dump_json().encode(), timeout=20)
    finally:
        await connection.close()
    return AutonomyDecisionReplyPayload.model_validate(
        EventEnvelope.model_validate_json(message.data).payload
    )


def _envelope(payload: dict) -> EventEnvelope:
    return EventEnvelope(
        subject=SUBJECT,
        source_engine="cognitive-state-engine",
        correlation_id=uuid4(),
        payload=payload,
    )


async def _configure(
    repository: PostgresAutonomyRepository,
    level: AutonomyLevel | None,
    *,
    auto_execute: bool = False,
    deny: bool = False,
) -> None:
    """Server-side state, written through the production repository -- the
    trigger itself can carry none of it."""
    if level is not None:
        await repository.set_level(USER, level)
    if auto_execute:
        await repository.create_policy(
            Policy(
                user_id=USER,
                name="auto-execute low-risk creates",
                effect=PolicyEffect.AUTO_EXECUTE,
                match=PolicyMatch(category=PermissionCategory.CREATE),
            )
        )
    if deny:
        await repository.create_policy(
            Policy(
                user_id=USER,
                name="never create",
                effect=PolicyEffect.DENY,
                match=PolicyMatch(category=PermissionCategory.CREATE),
            )
        )
    await repository.upsert_permission_grants(
        USER,
        [
            PermissionGrant(
                user_id=USER, category=PermissionCategory.CREATE, max_risk=RiskLevel.CRITICAL
            )
        ],
    )


async def _log(database: AsyncEngine) -> list[dict]:
    async with database.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT action_id, suggestion_id, autonomy_level, outcome, reason "
                "FROM autonomy.decision_log ORDER BY created_at, id"
            )
        )
        return [dict(row) for row in result.mappings().all()]


async def _suggestions(database: AsyncEngine) -> list[dict]:
    async with database.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT id, user_id, category, risk, title, detail, status "
                "FROM autonomy.suggestion ORDER BY created_at, id"
            )
        )
        return [dict(row) for row in result.mappings().all()]


# --- the served trigger, end to end ---------------------------------------------


async def test_a_real_trigger_is_decided_by_the_production_served_handler(
    consumer: None,
    producer: BoundEventBus,
    repository: PostgresAutonomyRepository,
    database: AsyncEngine,
    action_engine: list[UUID],
) -> None:
    """Level 1: the real handler proposes, and the proposal and its log row
    are in real Postgres under the **consumer-derived** identity."""
    await _configure(repository, AutonomyLevel.SUGGESTIVE)

    event_id, reply = await _trigger(producer, _payload(title="prune the cache"))
    subject_id = uuid5(NAMESPACE, str(event_id))

    assert reply.degraded is False
    assert reply.outcome == DecisionOutcome.PROPOSE.value
    assert reply.subject_id == subject_id

    suggestions = await _suggestions(database)
    assert len(suggestions) == 1
    assert suggestions[0]["id"] == subject_id
    assert suggestions[0]["user_id"] == USER  # primary_user_id, never the producer's
    assert suggestions[0]["category"] == "create"
    assert suggestions[0]["risk"] == "low"
    assert suggestions[0]["title"] == "prune the cache"
    assert suggestions[0]["status"] == "proposed"

    log = await _log(database)
    assert len(log) == 1
    assert log[0]["action_id"] == subject_id
    assert log[0]["suggestion_id"] == subject_id
    assert log[0]["outcome"] == DecisionOutcome.PROPOSE.value
    assert log[0]["autonomy_level"] == int(AutonomyLevel.SUGGESTIVE)

    assert action_engine == []  # Level 1 never reaches `action.execute`


async def test_level_two_executes_once_through_the_real_dispatch_path(
    consumer: None,
    producer: BoundEventBus,
    repository: PostgresAutonomyRepository,
    database: AsyncEngine,
    action_engine: list[UUID],
) -> None:
    """The one path to execution: Level 2, an `AUTO_EXECUTE` policy, LOW risk,
    an open grant, every execution field. The dispatched `action_id` **is** the
    derived `subject_id`."""
    await _configure(repository, AutonomyLevel.ASSISTED, auto_execute=True)

    event_id, reply = await _trigger(producer)
    subject_id = uuid5(NAMESPACE, str(event_id))

    assert reply.outcome == DecisionOutcome.EXECUTE.value
    assert action_engine == [subject_id]
    log = await _log(database)
    assert [(row["action_id"], row["outcome"]) for row in log] == [
        (subject_id, DecisionOutcome.EXECUTE.value)
    ]
    assert await _suggestions(database) == []


async def test_an_unconfigured_instance_only_observes(
    consumer: None,
    producer: BoundEventBus,
    repository: PostgresAutonomyRepository,
    database: AsyncEngine,
    action_engine: list[UUID],
) -> None:
    """No level row: Level 0 -- observe, record, never propose or execute. An
    `AUTO_EXECUTE` policy and an open grant are configured so the level is the
    only thing standing between this trigger and a dispatch. (Without a grant
    the permission gate denies first, at every level -- TDD 4D §4.3.)"""
    await _configure(repository, None, auto_execute=True)
    _, reply = await _trigger(producer)
    assert reply.outcome == DecisionOutcome.OBSERVE_ONLY.value
    assert [row["outcome"] for row in await _log(database)] == [DecisionOutcome.OBSERVE_ONLY.value]
    assert await _suggestions(database) == []
    assert action_engine == []


async def test_a_policy_denial_denies_and_dispatches_nothing(
    consumer: None,
    producer: BoundEventBus,
    repository: PostgresAutonomyRepository,
    database: AsyncEngine,
    action_engine: list[UUID],
) -> None:
    await _configure(repository, AutonomyLevel.ASSISTED, auto_execute=True, deny=True)
    _, reply = await _trigger(producer)
    assert reply.outcome == DecisionOutcome.DENY.value
    assert [row["outcome"] for row in await _log(database)] == [DecisionOutcome.DENY.value]
    assert action_engine == []


@pytest.mark.parametrize("risk", [RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL])
async def test_above_low_never_auto_executes(
    risk: RiskLevel,
    consumer: None,
    producer: BoundEventBus,
    repository: PostgresAutonomyRepository,
    action_engine: list[UUID],
) -> None:
    await _configure(repository, AutonomyLevel.ASSISTED, auto_execute=True)
    _, reply = await _trigger(producer, _payload(risk=risk))
    assert reply.outcome != DecisionOutcome.EXECUTE.value
    assert action_engine == []


async def test_no_action_engine_degrades_to_a_proposal_that_executes_nothing(
    consumer: None,
    producer: BoundEventBus,
    repository: PostgresAutonomyRepository,
    database: AsyncEngine,
) -> None:
    """4F.5's `ActionDispatchUnavailable` degradation, reached through the
    trigger: a qualifying Level-2 decision with **no** `action.execute`
    subscriber on the real broker becomes a proposal, and says why."""
    await _configure(repository, AutonomyLevel.ASSISTED, auto_execute=True)
    event_id, reply = await _trigger(producer)

    assert reply.outcome == DecisionOutcome.PROPOSE.value
    log = await _log(database)
    assert len(log) == 1
    assert log[0]["action_id"] == uuid5(NAMESPACE, str(event_id))
    assert "no subscriber" in log[0]["reason"]
    assert "not executed" in log[0]["reason"]


# --- identity: Layer 1 only --------------------------------------------------------


async def test_a_redelivered_trigger_reaches_action_engine_under_the_same_action_id(
    consumer: None,
    nats_uri: str,
    repository: PostgresAutonomyRepository,
    database: AsyncEngine,
    action_engine: list[UUID],
) -> None:
    """**A-4F6-3 Layer 1, §5.4 question 5.** The same envelope twice derives
    the same `subject_id`, so `action-engine` is handed the same `action_id`
    both times -- the key its terminal-replay guard replays on, so nothing
    executes twice. The log records **every attempt** (append-only)."""
    await _configure(repository, AutonomyLevel.ASSISTED, auto_execute=True)
    envelope = _envelope(_payload().model_dump(mode="json"))
    subject_id = uuid5(NAMESPACE, str(envelope.event_id))

    first = await _raw(nats_uri, envelope)
    second = await _raw(nats_uri, envelope)

    assert first.subject_id == second.subject_id == subject_id
    assert action_engine == [subject_id, subject_id]
    assert [row["action_id"] for row in await _log(database)] == [subject_id, subject_id]


async def test_a_redelivered_proposal_is_not_recorded_twice(
    consumer: None,
    nats_uri: str,
    repository: PostgresAutonomyRepository,
    database: AsyncEngine,
) -> None:
    """The same redelivery at Level 1. The suggestion table's **existing**
    primary key refuses a second row under the same derived id; the second
    attempt's transaction rolls back whole, so neither a second suggestion nor
    a second log row exists, and the reply says it was not recorded. No
    constraint, migration or second mechanism was added for this."""
    await _configure(repository, AutonomyLevel.SUGGESTIVE)
    envelope = _envelope(_payload().model_dump(mode="json"))
    subject_id = uuid5(NAMESPACE, str(envelope.event_id))

    first = await _raw(nats_uri, envelope)
    second = await _raw(nats_uri, envelope)

    assert (first.degraded, first.outcome) == (False, DecisionOutcome.PROPOSE.value)
    assert (second.degraded, second.outcome) == (True, DecisionOutcome.PROPOSE.value)
    assert second.subject_id == subject_id
    assert [row["id"] for row in await _suggestions(database)] == [subject_id]
    assert [row["action_id"] for row in await _log(database)] == [subject_id]


async def test_two_event_ids_with_identical_payloads_are_two_decisions(
    consumer: None,
    producer: BoundEventBus,
    repository: PostgresAutonomyRepository,
    database: AsyncEngine,
    action_engine: list[UUID],
) -> None:
    """**No Layer 2** (§19 row 8): distinct `event_id`s are distinct transport
    identities, whatever the payload says."""
    await _configure(repository, AutonomyLevel.ASSISTED, auto_execute=True)
    payload = _payload()
    first_event, first = await _trigger(producer, payload)
    second_event, second = await _trigger(producer, payload)

    assert first_event != second_event
    assert first.subject_id != second.subject_id
    assert len(action_engine) == 2
    assert len(await _log(database)) == 2


# --- rejection: the producer cannot name identity or user --------------------------


@pytest.mark.parametrize("field", ["subject_id", "user_id"])
async def test_a_producer_supplied_identity_field_is_rejected_on_the_real_bus(
    field: str,
    consumer: None,
    nats_uri: str,
    repository: PostgresAutonomyRepository,
    database: AsyncEngine,
    action_engine: list[UUID],
) -> None:
    """Sent raw, because the contract will not even let the SDK build it."""
    await _configure(repository, AutonomyLevel.ASSISTED, auto_execute=True)
    payload = _payload().model_dump(mode="json") | {field: str(uuid4())}

    reply = await _raw(nats_uri, _envelope(payload))

    assert reply.rejected is True
    assert reply.outcome is None
    assert await _log(database) == []
    assert await _suggestions(database) == []
    assert action_engine == []


# --- Design A, and "no execution without delivery" ------------------------------


async def test_an_unreachable_database_is_a_degraded_reply_and_nothing_executes(
    nats_uri: str,
    producer: BoundEventBus,
    database: AsyncEngine,
    action_engine: list[UUID],
) -> None:
    """**A-4F6-5 Design A with a real failure**: the served handler's first
    server-side read hits a database that is not there. The reply is
    structured and degraded, `subject_id` is `None` -- nothing was decided --
    and `action.execute` is never requested."""
    unreachable = create_engine("postgresql+asyncpg://nova:nova@127.0.0.1:1/absent")
    try:
        async with _serving(PostgresAutonomyRepository(create_session_factory(unreachable))):
            _, reply = await _trigger(producer)
    finally:
        await unreachable.dispose()

    assert reply.degraded is True
    assert reply.outcome is None
    assert reply.subject_id is None
    assert action_engine == []
    assert await _log(database) == []


async def test_an_undelivered_trigger_decides_nothing_and_executes_nothing(
    producer: BoundEventBus,
    repository: PostgresAutonomyRepository,
    database: AsyncEngine,
    action_engine: list[UUID],
) -> None:
    """**§19 row 12.** With no consumer serving, the real broker refuses the
    request at the producer -- and on this side nothing was decided, recorded
    or dispatched, even with every Level-2 gate configured open."""
    await _configure(repository, AutonomyLevel.ASSISTED, auto_execute=True)

    with pytest.raises(Exception) as caught:  # noqa: PT011 -- asserted by name below
        await _trigger(producer)

    assert type(caught.value).__name__ == "NoRespondersError"
    assert await _log(database) == []
    assert await _suggestions(database) == []
    assert action_engine == []
