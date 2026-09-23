"""The initiative trigger's producer against **real NATS and real PostgreSQL**
-- Phase 4F.6, TDD 4F.6 §10 and §19 rows 1, 2, 10-12.

Everything on this engine's side is production code: the real
`PostgresCognitiveStateRepository` over the real migration chain, the real
`promote_thought`, the real `DecisionTriggerClient`, and a real `BoundEventBus`
bound with this engine's own `events/published.py` allow-list.

**`autonomy-engine` is a stand-in responder** on the real broker, recording
each envelope it receives. Its real consumer -- the production `serve()`, the
real `decide()` and real Postgres -- is proven in
`services/autonomy-engine/tests/integration/test_decision_trigger_real_infra.py`;
this engine may not import that one (control 7), so the two halves meet at the
one shared contract, `AutonomyDecisionRequestedPayload`, which the stand-in
validates through the registry exactly as the real consumer does.

Three things only a real broker decides, and each has a test:

* **a request with no subscriber is refused immediately** (`NoRespondersError`),
  which the client recognises by type name -- only a real broker proves the
  name still matches (L-18 is open; the SDK does not translate it);
* **the reply bound is a real bounded wait**, after which nothing is re-sent;
* **the allow-list is enforced by the real bus** -- `action.execute` included.

`@pytest.mark.real_infra`: requires Docker.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import pytest
from nova_cognitive_state_engine.clients.decision_trigger_client import DecisionTriggerClient
from nova_cognitive_state_engine.domain.models import ActiveThought, AttentionLayer
from nova_cognitive_state_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_cognitive_state_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_cognitive_state_engine.promotion_orchestration import promote_thought
from nova_cognitive_state_engine.repository.postgres_cognitive_state_repository import (
    PostgresCognitiveStateRepository,
)
from nova_contracts import EventEnvelope, validate_payload
from nova_contracts.events.autonomy import (
    AutonomyDecisionReplyPayload,
    AutonomyDecisionRequestedPayload,
)
from nova_eventbus_sdk import BoundEventBus, SubjectNotAllowedError
from nova_eventbus_sdk.backends.nats import NatsEventBus
from nova_testkit.postgres import run_alembic_upgrade
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

SUBJECT = "autonomy.decision.requested"
NAMESPACE = UUID("0c81f3b8-e30f-5f0a-9241-8985e4b83489")

PROPOSAL = {
    "category": "create",
    "risk": "high",
    "action_type": "terminal",
    "execution_target": "terminal",
    "verification_method": "exit_code",
    "title": "prune stale build artifacts",
    "detail": "older than thirty days",
}

Handler = Callable[[EventEnvelope], Awaitable[BaseModel]]


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["COGNITIVE_STATE_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
async def database(postgres_container: PostgresContainer) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(postgres_container.get_connection_url())
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM cognitive_state.active_thought"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM cognitive_state.active_thought"))
    await engine.dispose()


@pytest.fixture
def repository(database: AsyncEngine) -> PostgresCognitiveStateRepository:
    return PostgresCognitiveStateRepository(async_sessionmaker(database, expire_on_commit=False))


@pytest.fixture
async def bus(nats_container) -> AsyncIterator[BoundEventBus]:  # type: ignore[no-untyped-def]
    """This engine's real allow-listed bus, as `main.py` binds it."""
    backend = NatsEventBus(servers=nats_container.nats_uri())
    await backend.connect()
    yield BoundEventBus(
        backend,
        engine_name="cognitive-state-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )
    await backend.close()


@pytest.fixture
async def serve_autonomy(nats_container) -> AsyncIterator[Callable[[Handler], Awaitable[None]]]:  # type: ignore[no-untyped-def]
    """Starts a stand-in `autonomy-engine` responder with a given handler; every
    one started is closed at teardown, so no test inherits a subscriber."""
    backends: list[NatsEventBus] = []

    async def _start(handler: Handler) -> None:
        backend = NatsEventBus(servers=nats_container.nats_uri())
        await backend.connect()
        await backend.serve(SUBJECT, handler, source_engine="autonomy-engine-stub")
        backends.append(backend)
        await asyncio.sleep(0.1)  # let the SUB reach the server first

    yield _start
    for backend in backends:
        await backend.close()


@pytest.fixture
async def autonomy(serve_autonomy) -> list[EventEnvelope]:  # type: ignore[no-untyped-def]
    """A stand-in that validates each payload through the registry -- as the
    real consumer does -- and replies with a decision."""
    received: list[EventEnvelope] = []

    async def _handle(envelope: EventEnvelope) -> AutonomyDecisionReplyPayload:
        received.append(envelope)
        validate_payload(SUBJECT, envelope.payload)
        return AutonomyDecisionReplyPayload(
            degraded=False, outcome="propose", subject_id=uuid5(NAMESPACE, str(envelope.event_id))
        )

    await serve_autonomy(_handle)
    return received


def _thought(layer: AttentionLayer, *, proposal: dict | None = PROPOSAL) -> ActiveThought:
    moment = datetime.now(UTC)
    return ActiveThought(
        thought_id=uuid4(),
        user_id=uuid4(),
        description="Keep the build directory bounded.",
        priority=4,
        confidence=0.2,
        current_progress=0.0,
        attention_layer=layer,
        created_at=moment,
        updated_at=moment,
        proposed_action=proposal,  # type: ignore[arg-type]
    )


async def _layer(database: AsyncEngine, thought_id: UUID) -> str:
    async with database.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT attention_layer FROM cognitive_state.active_thought WHERE thought_id = :id"
            ),
            {"id": thought_id},
        )
        return str(result.scalar_one())


def _client(bus: BoundEventBus, timeout_seconds: float = 20.0) -> DecisionTriggerClient:
    return DecisionTriggerClient(bus, timeout_seconds=timeout_seconds)


# --- the one case that triggers ---------------------------------------------------


async def test_promotion_to_immediate_sends_one_real_request_carrying_the_proposal(
    bus: BoundEventBus,
    autonomy: list[EventEnvelope],
    repository: PostgresCognitiveStateRepository,
    database: AsyncEngine,
) -> None:
    thought = await repository.upsert_thought(_thought(AttentionLayer.ACTIVE))

    result = await promote_thought(thought.thought_id, repository=repository, trigger=_client(bus))

    assert await _layer(database, thought.thought_id) == "immediate"
    assert len(autonomy) == 1
    envelope = autonomy[0]
    assert envelope.subject == SUBJECT
    assert envelope.source_engine == "cognitive-state-engine"

    payload = validate_payload(SUBJECT, envelope.payload)
    assert isinstance(payload, AutonomyDecisionRequestedPayload)
    for field, value in PROPOSAL.items():
        assert envelope.payload[field] == value, field
    assert payload.thought_id == thought.thought_id
    assert payload.priority == thought.priority
    assert envelope.correlation_id == payload.correlation_id
    # §19 row 4: the producer names neither the decision nor the user.
    assert "subject_id" not in envelope.payload
    assert "user_id" not in envelope.payload

    assert result.trigger is not None
    assert result.trigger.status == "decided"
    assert result.trigger.subject_id == uuid5(NAMESPACE, str(envelope.event_id))


# --- the cases that do not ---------------------------------------------------------


async def test_a_thought_without_a_proposal_reaches_immediate_and_sends_nothing(
    bus: BoundEventBus,
    autonomy: list[EventEnvelope],
    repository: PostgresCognitiveStateRepository,
    database: AsyncEngine,
) -> None:
    thought = await repository.upsert_thought(_thought(AttentionLayer.ACTIVE, proposal=None))

    result = await promote_thought(thought.thought_id, repository=repository, trigger=_client(bus))

    assert await _layer(database, thought.thought_id) == "immediate"
    assert result.trigger is None
    assert autonomy == []


async def test_a_promotion_below_immediate_sends_nothing(
    bus: BoundEventBus,
    autonomy: list[EventEnvelope],
    repository: PostgresCognitiveStateRepository,
    database: AsyncEngine,
) -> None:
    thought = await repository.upsert_thought(_thought(AttentionLayer.PASSIVE))

    await promote_thought(thought.thought_id, repository=repository, trigger=_client(bus))

    assert await _layer(database, thought.thought_id) == "active"
    assert autonomy == []


async def test_promoting_an_immediate_thought_again_sends_nothing(
    bus: BoundEventBus,
    autonomy: list[EventEnvelope],
    repository: PostgresCognitiveStateRepository,
) -> None:
    thought = await repository.upsert_thought(_thought(AttentionLayer.ACTIVE))
    await promote_thought(thought.thought_id, repository=repository, trigger=_client(bus))
    again = await promote_thought(thought.thought_id, repository=repository, trigger=_client(bus))

    assert again.moved is False
    assert len(autonomy) == 1  # the first promotion's, and only that


# --- lost triggers, on a real broker ------------------------------------------------


async def test_a_real_broker_with_no_consumer_is_reported_unavailable(
    bus: BoundEventBus,
    repository: PostgresCognitiveStateRepository,
    database: AsyncEngine,
) -> None:
    """**The real `NoRespondersError`.** Nothing serves the subject, the broker
    answers at once, and the client reports `unavailable` -- proving its
    type-name match against the real class. The promotion itself stands."""
    thought = await repository.upsert_thought(_thought(AttentionLayer.ACTIVE))

    result = await promote_thought(thought.thought_id, repository=repository, trigger=_client(bus))

    assert result.trigger is not None
    assert result.trigger.status == "unavailable"
    assert await _layer(database, thought.thought_id) == "immediate"


async def test_a_silent_consumer_is_unconfirmed_after_a_real_bounded_wait_and_not_resent(
    bus: BoundEventBus,
    serve_autonomy,  # type: ignore[no-untyped-def]
    repository: PostgresCognitiveStateRepository,
) -> None:
    """The bound is shortened to keep the suite fast; the 20-second default is
    asserted in the unit tier. What this decides is that the wait is real and
    that nothing is re-sent after it."""
    received: list[UUID] = []

    async def _never_reply(envelope: EventEnvelope) -> AutonomyDecisionReplyPayload:
        received.append(envelope.event_id)
        await asyncio.sleep(30)
        raise AssertionError("unreachable: the producer must have given up first")

    await serve_autonomy(_never_reply)
    thought = await repository.upsert_thought(_thought(AttentionLayer.ACTIVE))

    result = await promote_thought(
        thought.thought_id, repository=repository, trigger=_client(bus, timeout_seconds=1.0)
    )
    await asyncio.sleep(0.5)  # a retry, if there were one, would have arrived by now

    assert result.trigger is not None
    assert result.trigger.status == "unconfirmed"
    assert len(received) == 1


async def test_a_degraded_reply_crosses_the_real_wire_as_degraded(
    bus: BoundEventBus,
    serve_autonomy,  # type: ignore[no-untyped-def]
    repository: PostgresCognitiveStateRepository,
) -> None:
    async def _degraded(envelope: EventEnvelope) -> AutonomyDecisionReplyPayload:
        return AutonomyDecisionReplyPayload(degraded=True, error="database unreachable")

    await serve_autonomy(_degraded)
    thought = await repository.upsert_thought(_thought(AttentionLayer.ACTIVE))

    result = await promote_thought(thought.thought_id, repository=repository, trigger=_client(bus))

    assert result.trigger is not None
    assert result.trigger.status == "degraded"
    assert result.trigger.subject_id is None
    assert result.trigger.error == "database unreachable"


# --- the allow-list, enforced by the real bus -------------------------------------


async def test_the_real_bus_refuses_action_execute_and_every_other_subject(
    bus: BoundEventBus,
) -> None:
    """**TDD 4F §6.2 / §16 control 11 at runtime.** This engine can request a
    decision; it cannot request an execution, or anything else."""
    payload = AutonomyDecisionReplyPayload(degraded=True)
    for forbidden in (
        "action.execute",
        "autonomy.decision.made",
        "cognitive_state.thought.promoted",
    ):
        with pytest.raises(SubjectNotAllowedError):
            await bus.request(
                forbidden, payload, source_engine="cognitive-state-engine", timeout_ms=200
            )


async def test_this_engine_cannot_consume_the_trigger_it_produces(bus: BoundEventBus) -> None:
    async def _handler(envelope: EventEnvelope) -> AutonomyDecisionReplyPayload:
        raise AssertionError("unreachable")

    with pytest.raises(SubjectNotAllowedError):
        await bus.serve(SUBJECT, _handler, source_engine="cognitive-state-engine")
