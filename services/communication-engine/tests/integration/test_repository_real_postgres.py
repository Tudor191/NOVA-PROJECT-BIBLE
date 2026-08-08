"""Real-Postgres verification of `PostgresCommunicationRepository` -- closes
task #93's communication-engine leg (docs/design/nova-testkit/
technical-implementation-plan.md §4, §6: highest-priority of the three named
engines, by lowest total coverage concentrated in exactly this layer). Real
schema (via this engine's own Alembic migration `0001_initial_schema.py`),
real INSERT/SELECT/UPDATE round trips, a real foreign-key constraint the fake
repository (`tests/fakes/repository.py`) cannot represent at all, and real
`onupdate` timestamp behavior -- not "the container started."

Deliberately narrow: exercises the repository/infrastructure boundary only,
per direct instruction not to rewrite this engine's existing (fake-backed)
unit/integration tests merely to increase coverage -- those already cover
the domain/API logic this file does not re-test.

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run test`
invocation (ADR-033) -- requires Docker. **Not executed in the environment
this file was written in** (no reachable Docker daemon there); see
`nova_testkit.postgres`'s module docstring for exactly what was and wasn't
verifiable here.
"""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from nova_communication_engine.domain.models import (
    ChannelType,
    ConversationSession,
    ConversationState,
    ConversationTurn,
    Notification,
    NotificationPriority,
    TurnDirection,
)
from nova_communication_engine.domain.ports import OutboxEvent
from nova_communication_engine.repository.postgres_communication_repository import (
    PostgresCommunicationRepository,
)
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    """Runs this engine's real Alembic migration once per session against
    `postgres_container`, before any test below runs."""
    os.environ["COMMUNICATION_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
def repository(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> PostgresCommunicationRepository:
    return PostgresCommunicationRepository(postgres_session_factory)


async def test_create_and_get_session_round_trips_through_real_postgres(
    repository: PostgresCommunicationRepository,
) -> None:
    session = ConversationSession(user_id=uuid4(), channel=ChannelType.VOICE, device_id=uuid4())

    created = await repository.create_session(session)
    fetched = await repository.get_session(created.session_id)

    assert fetched is not None
    assert fetched.session_id == created.session_id
    assert fetched.channel == ChannelType.VOICE
    assert fetched.state == ConversationState.IDLE


async def test_update_session_state_persists_and_advances_updated_at(
    repository: PostgresCommunicationRepository,
) -> None:
    session = await repository.create_session(
        ConversationSession(user_id=uuid4(), channel=ChannelType.TEXT, device_id=uuid4())
    )

    updated = await repository.update_session_state(
        session.session_id, state=ConversationState.LISTENING.value
    )

    assert updated.state == ConversationState.LISTENING
    assert updated.updated_at >= session.updated_at


async def test_append_turn_persists_and_is_returned_by_get_session(
    repository: PostgresCommunicationRepository,
) -> None:
    session = await repository.create_session(
        ConversationSession(user_id=uuid4(), channel=ChannelType.TEXT, device_id=uuid4())
    )

    await repository.append_turn(
        ConversationTurn(
            session_id=session.session_id,
            direction=TurnDirection.INBOUND,
            content="hello",
            channel=ChannelType.TEXT,
        )
    )
    fetched = await repository.get_session(session.session_id)

    assert fetched is not None
    assert len(fetched.turns) == 1
    assert fetched.turns[0].content == "hello"


async def test_append_turn_enforces_the_real_foreign_key_to_session(
    repository: PostgresCommunicationRepository,
) -> None:
    """A behavior the fake repository cannot represent at all: a turn
    referencing a `session_id` that was never created is rejected by the real
    schema's foreign key, not silently accepted."""
    with pytest.raises(IntegrityError):
        await repository.append_turn(
            ConversationTurn(
                session_id=uuid4(),
                direction=TurnDirection.INBOUND,
                content="orphaned",
                channel=ChannelType.TEXT,
            )
        )


async def test_create_notification_persists(repository: PostgresCommunicationRepository) -> None:
    created = await repository.create_notification(
        Notification(user_id=uuid4(), content="hello", priority=NotificationPriority.HIGH)
    )

    assert created.notification_id is not None
    assert created.priority == NotificationPriority.HIGH


async def test_outbox_enqueue_list_and_mark_dispatched_round_trip(
    repository: PostgresCommunicationRepository,
) -> None:
    outbox_id = await repository.enqueue_outbox(
        OutboxEvent(
            subject="communication.session.created", payload={"x": 1}, correlation_id=uuid4()
        )
    )

    ready = await repository.list_dispatch_ready()
    assert any(row.id == outbox_id for row in ready)

    await repository.mark_dispatched(outbox_id)

    ready_after = await repository.list_dispatch_ready()
    assert not any(row.id == outbox_id for row in ready_after)
