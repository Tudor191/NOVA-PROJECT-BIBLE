"""Real-Postgres verification of `PostgresActionRepository` -- real schema
(via this engine's own Alembic migration chain, `0001_initial_schema.py`),
real INSERT/SELECT/UPDATE round trips across all four tables (`action`,
`pending_approval`, `action_execution_history`,
`identity_confidence_policy`), including the `Action.id` primary-key
uniqueness -> `ActionAlreadyExistsError` translation the natural-key
idempotency guard (§5.3) depends on. Mirrors `capability-engine`'s own
`test_repository_real_postgres.py` convention.

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run
test` invocation (ADR-033) -- requires Docker. **Not executed in the
environment this file was written in** (no reachable Docker daemon there);
see `nova_testkit.postgres`'s module docstring for exactly what was and
wasn't verifiable here.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from nova_action_engine.domain.models import IdentityConfidencePolicy, PendingApproval
from nova_action_engine.domain.ports import ActionAlreadyExistsError
from nova_action_engine.repository.postgres_action_repository import PostgresActionRepository
from nova_contracts import Action, RetryPolicy, RollbackStrategy
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["ACTION_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
def repository(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> PostgresActionRepository:
    return PostgresActionRepository(postgres_session_factory)


def _action(**overrides: object) -> Action:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "action_type": "filesystem",
        "priority": "normal",
        "source": "test-suite",
        "requested_by": uuid4(),
        "execution_target": "filesystem",
        "risk": "negligible",
        "timeout_seconds": 30,
        "retry_policy": RetryPolicy(),
        "status": "pending",
        "verification_method": "adapter_confirmation",
    }
    defaults.update(overrides)
    return Action(**defaults)  # type: ignore[arg-type]


async def test_insert_then_find_by_id_round_trips(
    repository: PostgresActionRepository,
) -> None:
    action = _action()
    assert await repository.find_by_id(action.id) is None

    inserted = await repository.insert(action)
    assert inserted == action

    fetched = await repository.find_by_id(action.id)
    assert fetched == action


async def test_insert_round_trips_a_rollback_strategy(
    repository: PostgresActionRepository,
) -> None:
    action = _action(rollback_strategy=RollbackStrategy(kind="restore_file", detail="snapshot"))
    await repository.insert(action)

    fetched = await repository.find_by_id(action.id)
    assert fetched is not None
    assert fetched.rollback_strategy == action.rollback_strategy


async def test_inserting_a_duplicate_action_id_raises_action_already_exists(
    repository: PostgresActionRepository,
) -> None:
    action = _action()
    await repository.insert(action)

    duplicate = _action(id=action.id)
    with pytest.raises(ActionAlreadyExistsError):
        await repository.insert(duplicate)


async def test_update_status_and_record_result_persist(
    repository: PostgresActionRepository,
) -> None:
    action = _action()
    await repository.insert(action)

    await repository.update_status(action.id, status="completed", confidence=0.95)
    await repository.record_result(action.id, result={"content": "hi"}, error=None)

    fetched = await repository.find_by_id(action.id)
    assert fetched is not None
    assert fetched.status == "completed"
    assert fetched.confidence == 0.95
    assert await repository.get_result(action.id) == ({"content": "hi"}, None)


async def test_get_result_returns_none_before_any_result_is_recorded(
    repository: PostgresActionRepository,
) -> None:
    action = _action()
    await repository.insert(action)
    assert await repository.get_result(action.id) is None


async def test_pending_approval_insert_find_and_decide_round_trips(
    repository: PostgresActionRepository,
) -> None:
    # `pending_approval.action_id` carries a foreign key to `action.id`
    # (0001_initial_schema.py) -- production code only ever calls
    # `insert_pending_approval` after `insert(action)` has already run
    # (`domain/pipeline.py::_run_approval_loop`), so the parent row must
    # exist here too.
    action = _action()
    await repository.insert(action)
    action_id = action.id
    now = datetime.now(UTC)
    await repository.insert_pending_approval(
        PendingApproval(action_id=action_id, risk="critical", requested_at=now)
    )

    fetched = await repository.find_pending_approval(action_id)
    assert fetched is not None
    assert fetched.decision is None

    await repository.decide_pending_approval(action_id, decision="approved", decided_at=now)

    decided = await repository.find_pending_approval(action_id)
    assert decided is not None
    assert decided.decision == "approved"


async def test_record_execution_history_persists(
    repository: PostgresActionRepository,
) -> None:
    action_id = uuid4()
    await repository.record_execution_history(
        action_id=action_id, stage="receive_request", outcome="success"
    )
    # No read port is exposed for execution history (TDD 3D's own model has
    # no such API) -- this proves the insert itself does not raise, the
    # append-only log's own functional requirement (mirrors
    # `capability-engine`'s `record_installation_event` precedent).


async def test_identity_confidence_policy_round_trips(
    repository: PostgresActionRepository,
) -> None:
    user_id = uuid4()
    assert await repository.find_identity_confidence_policy(user_id) is None

    policy_row = IdentityConfidencePolicy(
        user_id=user_id, minimum_confidence_by_risk={"critical": 0.9, "high": 0.6}
    )
    # No insert port exists on the read-only Protocol -- seed directly via
    # a raw session to prove the read side of the mapping.
    from nova_action_engine.repository.models import IdentityConfidencePolicyORM

    async with repository._session_factory() as session:  # noqa: SLF001
        session.add(
            IdentityConfidencePolicyORM(
                user_id=policy_row.user_id,
                minimum_confidence_by_risk=policy_row.minimum_confidence_by_risk,
            )
        )
        await session.commit()

    fetched = await repository.find_identity_confidence_policy(user_id)
    assert fetched == policy_row


# --------------------------------------------------------------------------
# `depends_on` <-> JSONB (defect D-2, found by the Phase 3E real-Postgres
# acceptance E2E). `Action.depends_on` is a `list[UUID]`; the column is
# JSONB, whose encoder has no `UUID` serializer, so every Action carrying a
# dependency used to fail to insert with "Object of type UUID is not JSON
# serializable" -- which is exactly `coding-agent`'s `git add`/`git commit`
# steps (decision D5). The tests above only ever used the default empty
# `depends_on`, which is why this went unnoticed.
# --------------------------------------------------------------------------


async def test_insert_round_trips_an_empty_depends_on(
    repository: PostgresActionRepository,
) -> None:
    action = _action(depends_on=[])
    await repository.insert(action)

    fetched = await repository.find_by_id(action.id)
    assert fetched is not None
    assert fetched.depends_on == []


async def test_insert_round_trips_a_single_dependency(
    repository: PostgresActionRepository,
) -> None:
    dependency = uuid4()
    action = _action(depends_on=[dependency])
    await repository.insert(action)

    fetched = await repository.find_by_id(action.id)
    assert fetched is not None
    assert fetched.depends_on == [dependency]
    # Parsed back as real `UUID`s, not the strings the column stores.
    assert all(isinstance(value, UUID) for value in fetched.depends_on)


async def test_insert_round_trips_multiple_dependencies_in_order(
    repository: PostgresActionRepository,
) -> None:
    """`coding-agent`'s own chain is write -> add -> commit, so order is not
    incidental: a caller reading `depends_on` back must see what it wrote."""
    dependencies = [uuid4(), uuid4(), uuid4()]
    action = _action(depends_on=dependencies)
    await repository.insert(action)

    fetched = await repository.find_by_id(action.id)
    assert fetched is not None
    assert fetched.depends_on == dependencies


async def test_a_dependent_action_survives_a_full_write_read_lifecycle(
    repository: PostgresActionRepository,
) -> None:
    """The whole `action-engine` pipeline shape for a dependent Action:
    insert, gate, execute, record -- every step against real Postgres, with
    `depends_on` intact at the end."""
    dependencies = [uuid4(), uuid4()]
    action = _action(
        action_type="terminal",
        execution_target="git",
        depends_on=dependencies,
        parameters={"operation": "commit", "args": ["-m", "coding-agent: objective"]},
    )
    await repository.insert(action)

    await repository.update_status(action.id, status="executing", confidence=1.0)
    await repository.record_result(action.id, result={"exit_code": 0}, error=None)

    fetched = await repository.find_by_id(action.id)
    assert fetched is not None
    assert fetched.depends_on == dependencies
    assert fetched.status == "executing"
    assert fetched.confidence == 1.0
    assert fetched.execution_target == "git"
    assert fetched.parameters["operation"] == "commit"

    result, error = await repository.get_result(action.id)  # type: ignore[misc]
    assert result == {"exit_code": 0}
    assert error is None
