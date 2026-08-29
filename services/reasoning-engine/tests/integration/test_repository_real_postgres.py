"""Real-Postgres verification of `PostgresReasoningRepository` and of the
Reactive-mode persistence sequence that drives it -- real schema (via this
engine's own Alembic chain, `0001_initial_schema.py`), real INSERT/SELECT
round trips, and the real foreign keys the `reasoning` schema declares.
Mirrors `agent-os/kernel`'s own `test_repository_real_postgres.py`
convention.

**Why this file exists.** Until it did, every reasoning-engine test ran
against `FakeReasoningRepository`, which has no foreign keys, and this
engine was absent from `real-infra-checks.yml`'s matrix. Defect D-1 --
Reactive mode calling `finalize()` without ever persisting the `Alternative`
that `Decision.selected_alternative_id` references -- therefore survived
from Phase 2B until the Phase 3E real-Postgres acceptance E2E hit it. These
tests pin the fixed behaviour, and two of them assert the *failure* the old
behaviour produced, so a regression cannot pass silently.

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run
test` invocation (ADR-033) -- requires Docker (or an externally provided
PostgreSQL).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from nova_reasoning_engine.domain import pipeline
from nova_reasoning_engine.domain.models import (
    Alternative,
    KnowledgeReference,
    ReasoningMode,
    ReasoningRequest,
)
from nova_reasoning_engine.repository.postgres_reasoning_repository import (
    PostgresReasoningRepository,
)
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

from tests.fakes.ports import (
    FakeGoalsPort,
    FakeKnowledgePort,
    FakeMemoryPort,
    FakeModelOrchestrationPort,
    FakePersonalContextPort,
    FakeWorldModelPort,
)

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["REASONING_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
def repository(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> PostgresReasoningRepository:
    return PostgresReasoningRepository(postgres_session_factory)


def _reactive_request() -> ReasoningRequest:
    return ReasoningRequest(
        objective_text="what is the capital of France?",
        user_id=uuid4(),
        requesting_engine="test",
        reasoning_mode_hint=ReasoningMode.REACTIVE,
    )


def _ports(repository: PostgresReasoningRepository, **overrides: Any) -> dict[str, Any]:
    """The same port set `tests/unit/test_pipeline.py` uses, with the real
    repository swapped in for the fake -- so what differs between the two
    files is exactly the persistence layer and nothing else."""
    defaults: dict[str, Any] = {
        "memory_port": FakeMemoryPort(),
        "knowledge_port": FakeKnowledgePort(
            [KnowledgeReference(node_id="n1", name="Paris", layer="verified", confidence=0.9)]
        ),
        "world_model_port": FakeWorldModelPort(),
        "personal_context_port": FakePersonalContextPort(),
        "goals_port": FakeGoalsPort(),
        "model_port": FakeModelOrchestrationPort(),
        "repository": repository,
    }
    defaults.update(overrides)
    return defaults


# --------------------------------------------------------------------------
# D-1: the Reactive path, end to end, against the real schema
# --------------------------------------------------------------------------


async def test_reactive_mode_completes_against_real_postgres(
    repository: PostgresReasoningRepository,
) -> None:
    """The regression test for D-1. Before the fix this raised
    `IntegrityError: decision_selected_alternative_id_fkey`."""
    decision, trace, chosen = await pipeline.run(_reactive_request(), **_ports(repository))

    assert trace.outcome == "decided"
    assert chosen is not None
    assert decision.selected_alternative_id is not None


async def test_reactive_modes_decision_and_trace_round_trip_from_postgres(
    repository: PostgresReasoningRepository,
) -> None:
    decision, trace, _chosen = await pipeline.run(_reactive_request(), **_ports(repository))

    fetched_decision = await repository.get_decision(decision.id)
    assert fetched_decision is not None
    assert fetched_decision.selected_alternative_id == decision.selected_alternative_id
    assert fetched_decision.confidence_score == decision.confidence_score

    by_process = await repository.get_decision_for_process(decision.reasoning_process_id)
    assert by_process is not None
    assert by_process.id == decision.id

    fetched_trace = await repository.get_trace(trace.id)
    assert fetched_trace is not None
    assert fetched_trace.reasoning_process_id == decision.reasoning_process_id


async def test_reactive_mode_persists_a_terminal_process_row(
    repository: PostgresReasoningRepository,
) -> None:
    decision, _trace, _chosen = await pipeline.run(_reactive_request(), **_ports(repository))

    process = await repository.get_process(decision.reasoning_process_id)
    assert process is not None
    assert process.status == "decided"
    assert process.completed_at is not None


async def test_reactive_mode_enqueues_a_dispatchable_outbox_row(
    repository: PostgresReasoningRepository,
) -> None:
    """`finalize()` writes the `reasoning.process.completed` outbox row in the
    same transaction as the Decision -- and it is really dispatchable, and
    really stops being dispatchable once marked."""
    request = _reactive_request()
    await pipeline.run(request, **_ports(repository))

    rows = await repository.list_dispatch_ready()
    matching = [row for row in rows if row.correlation_id == request.correlation_id]
    assert len(matching) == 1
    assert matching[0].subject == "reasoning.process.completed"

    await repository.mark_dispatched(matching[0].id)

    remaining = await repository.list_dispatch_ready()
    assert all(row.id != matching[0].id for row in remaining)


# --------------------------------------------------------------------------
# The foreign keys are real -- these two assert the failure D-1 produced, so
# reverting the fix cannot pass silently (protocol §9.2 negative control,
# expressed as permanent tests rather than a one-off manual check).
# --------------------------------------------------------------------------


class _SkipsRecordingAlternatives(PostgresReasoningRepository):
    """The pre-fix behaviour, reproduced exactly: everything real except that
    `record_alternatives` does nothing."""

    async def record_alternatives(self, alternatives: list[Alternative]) -> None:
        return None


async def test_finalizing_without_persisting_the_alternative_violates_the_foreign_key(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    broken = _SkipsRecordingAlternatives(postgres_session_factory)

    with pytest.raises(IntegrityError) as excinfo:
        await pipeline.run(_reactive_request(), **_ports(broken))

    assert "decision_selected_alternative_id_fkey" in str(excinfo.value)


async def test_an_alternative_pointing_at_a_non_hypothesis_violates_the_foreign_key(
    repository: PostgresReasoningRepository,
) -> None:
    """`alternative.hypothesis_id` is a NOT NULL foreign key to
    `reasoning.hypothesis(id)`. The pre-fix code put `process.id` there; this
    is what the real schema does with any id that is not a hypothesis."""
    decision, _trace, _chosen = await pipeline.run(_reactive_request(), **_ports(repository))
    process_id = decision.reasoning_process_id

    orphan = Alternative(
        reasoning_process_id=process_id,
        hypothesis_id=process_id,  # a process id, exactly the old bug
        description="not backed by any hypothesis row",
        constraint_status="eligible",
    )

    with pytest.raises(IntegrityError) as excinfo:
        await repository.record_alternatives([orphan])

    assert "alternative_hypothesis_id_fkey" in str(excinfo.value)
