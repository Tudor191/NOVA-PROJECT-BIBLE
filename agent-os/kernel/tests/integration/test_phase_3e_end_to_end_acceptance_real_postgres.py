"""**TDD 3E §13's acceptance test, on real PostgreSQL** -- the
`real_infra`-tier counterpart to
`test_phase_3e_end_to_end_acceptance.py`.

§13 files this objective under *Real-infrastructure*: "a real, scripted
end-to-end objective ('add a health-check endpoint to a sample repo') flows
through Reasoning -> Planning -> NAOS (Kernel -> Engineering Supervisor ->
agent instances, including a peer-review round) -> Action Engine -> a real
git commit in a throwaway repo." The default-tier variant proves that whole
chain with in-memory repositories; this one removes the last substitution on
the persistence side.

## What is different from the default-tier variant, and only that

Six engines' Alembic migration chains are applied to **one real PostgreSQL
database**, and then:

- **Five of the six engines build their own repository**, through their own
  unmodified `main.py` lifespan, from their own
  `<ENGINE>_POSTGRES_DSN` environment variable. Nothing is injected: the
  `PostgresReasoningRepository`, `PostgresPlanningRepository`,
  `PostgresCapabilityRepository`, `PostgresRegistryRepository` and
  `PostgresKernelRepository` this run uses are the ones production code
  constructs for itself.
- **`action-engine` is the one exception.** Its repository is injected, but
  the injected object *is* a real `PostgresActionRepository` -- a subclass
  that adds the parallelism rendezvous to `insert()` and then defers to
  `super().insert()`, so the production SQL still runs. See
  `_RendezvousPostgresActionRepository`.
- The two transactional outboxes are **real Postgres tables**, drained by
  the same real production `dispatch_ready_events` functions, whose
  `mark_dispatched` now really writes `dispatched_at`.
- After the run, every material claim is re-checked with **raw SQL over an
  independent connection** that shares nothing with the repositories under
  test (`_verify_rows`).

Everything else -- the objective, the target repository, the task graph, the
agents, the git and pytest subprocesses -- is imported unchanged from the
default-tier module, so the two variants cannot drift apart. That module is
imported, never modified.

## Why six schemas in one database is not a new architecture

Every engine's `alembic/env.py` already sets a **namespaced**
`version_table` (`alembic_version_reasoning`, `alembic_version_planning`,
`alembic_version_action`, `alembic_version_capability`,
`alembic_version_agent_os_kernel`, `alembic_version_agent_os_registry`) and
every `0001_initial_schema.py` already uses `CREATE SCHEMA IF NOT EXISTS`.
Both were deliberate: the engines were built to be able to share one
database. This test exercises that existing property; it adds no migration,
no schema, no contract and no production setting.

## Still not real, and disclosed

- **The Event Bus is still `InMemoryEventBus`.** This variant is
  Postgres-backed by design; a NATS-JetStream-backed variant would also have
  to replace the synchronous, inline delivery this test's drain loop depends
  on with real asynchronous delivery, which is a separate piece of work and
  is recorded as still owed.
- **The Arq *scheduler*** around the two real outbox dispatch functions
  (Redis), **both model boundaries** (ADR-020) and **`action-engine`'s
  `IdentityPort`** (perception-engine) are stood in for exactly as in the
  default-tier variant, for the same reasons.

## Where the database comes from

`e2e_postgres_url` prefers `NOVA_E2E_POSTGRES_DSN` when it is set, and
otherwise starts `nova-testkit`'s session-scoped `postgres_container`. CI
sets nothing, so CI gets the testcontainer; the override exists so the test
can also be pointed at an already-running PostgreSQL 16 when no Docker
daemon is available. It is a test-only knob -- no engine reads it.

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run
test` invocation (ADR-033).

## !! THIS TEST CURRENTLY FAILS, AND THAT IS THE FINDING !!

Executed against a real PostgreSQL 16.13 server on 2026-08-29, it fails --
not because of anything in this file, but because it is the first thing in
the repository ever to drive these engines' **real** repositories. It
uncovered two pre-existing production defects that no fake could expose:

1. **`reasoning-engine`, Reactive mode** (`domain/pipeline.py`). The branch
   builds an `Alternative`, points `Decision.selected_alternative_id` at it,
   and calls `finalize()` **without ever persisting the `Alternative`** --
   the Multi-step branch's own `record_alternatives()` call has no Reactive
   counterpart. Real Postgres rejects the `Decision` insert with
   `ForeignKeyViolationError: decision_selected_alternative_id_fkey`.
   Compounding it, the `Alternative` is built with
   `hypothesis_id=process.id` -- a *process* id in a column whose NOT NULL
   foreign key references `reasoning.hypothesis(id)` -- so simply persisting
   it is not sufficient either. Every Reactive `POST /v1/reasoning/reason`
   against a real database returns 500. `reasoning-engine` has no
   `test_repository_real_postgres.py` and is absent from
   `real-infra-checks.yml`'s matrix, which is why this survived since Phase
   2B.

2. **`action-engine`** (`repository/postgres_action_repository.py`).
   `insert()` passes `depends_on` (a `list[UUID]`) straight into a JSONB
   column: `TypeError: Object of type UUID is not JSON serializable`. Every
   `Action` carrying a dependency fails to persist -- which is exactly
   `coding-agent`'s `git add` and `git commit` steps (decision D5), so the
   Phase 3E acceptance commit cannot happen against a real database at all.
   The existing `action-engine` real-Postgres test only inserts Actions with
   an empty `depends_on`.

Both were reproduced in isolation, without any Phase 3E component involved.
With both fixed experimentally, this test **passes in full** (parallelism
peak 2, real commit, target suite green) -- so these two are the only
blockers, not the first two of many. The fixes are deliberately **not**
included here: each changes an engine outside Phase 3E, and the Reactive
one changes Phase 2B's approved persistence semantics. They are the
author's decision to make, not this test's.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from nova_action_engine.config import Settings as ActionSettings
from nova_action_engine.main import create_app as create_action_app
from nova_action_engine.repository.postgres_action_repository import PostgresActionRepository
from nova_agent_os_kernel.clients.action_client import ActionClient
from nova_agent_os_kernel.config import Settings as KernelSettings
from nova_agent_os_kernel.domain.execution_backend import InprocessExecutionBackend
from nova_agent_os_kernel.main import create_app as create_kernel_app
from nova_agent_os_registry.config import Settings as RegistrySettings
from nova_agent_os_registry.main import create_app as create_registry_app
from nova_agent_os_supervisors.config import Settings as SupervisorSettings
from nova_agent_os_supervisors.main import create_app as create_supervisor_app
from nova_capability_engine.config import Settings as CapabilitySettings
from nova_capability_engine.main import create_app as create_capability_app
from nova_contracts import Action, AgentOsTaskCompletedPayload, EventEnvelope
from nova_eventbus_sdk import BoundEventBus
from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus
from nova_planning_engine.config import Settings as PlanningSettings
from nova_planning_engine.main import create_app as create_planning_app
from nova_planning_engine.repository.outbox_dispatcher import (
    dispatch_ready_events as dispatch_planning_outbox,
)
from nova_reasoning_engine.config import Settings as ReasoningSettings
from nova_reasoning_engine.main import create_app as create_reasoning_app
from nova_reasoning_engine.repository.outbox_dispatcher import (
    dispatch_ready_events as dispatch_reasoning_outbox,
)
from nova_service_kit import create_engine, create_session_factory
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

# The default-tier variant is the single source of truth for the objective,
# the target repository, the task graph and every stand-in that is identical
# between the two. Importing it (rather than copying it) is what makes
# "the same real path" verifiable rather than aspirational.
from tests.integration.test_phase_3e_end_to_end_acceptance import (
    _AGENTS_ROOT,
    _AUTHOR_EMAIL,
    _AUTHOR_NAME,
    _GROUNDING,
    _OBJECTIVE,
    _REPO_ROOT,
    _TERMINAL_PATH,
    _AgentModelGateway,
    _git,
    _init_target_repo,
    _PlanningModelPort,
    _reasoning_fakes,
    _TrustedIdentityPort,
)

pytestmark = pytest.mark.real_infra

_EXTERNAL_DSN_ENV = "NOVA_E2E_POSTGRES_DSN"

_MIGRATIONS: tuple[tuple[str, Path], ...] = (
    ("REASONING_ENGINE_POSTGRES_DSN", _REPO_ROOT / "services/reasoning-engine/alembic.ini"),
    ("PLANNING_ENGINE_POSTGRES_DSN", _REPO_ROOT / "services/planning-engine/alembic.ini"),
    ("ACTION_ENGINE_POSTGRES_DSN", _REPO_ROOT / "services/action-engine/alembic.ini"),
    ("CAPABILITY_ENGINE_POSTGRES_DSN", _REPO_ROOT / "services/capability-engine/alembic.ini"),
    ("AGENT_OS_KERNEL_POSTGRES_DSN", _REPO_ROOT / "agent-os/kernel/alembic.ini"),
    ("AGENT_OS_REGISTRY_POSTGRES_DSN", _REPO_ROOT / "agent-os/registry/alembic.ini"),
)
"""Each engine's own `<ENGINE>_POSTGRES_DSN` variable paired with its own
`alembic.ini`. The variable names are not invented here -- each is the
engine's own `Settings.model_config` `env_prefix` plus `POSTGRES_DSN`."""


@pytest.fixture(scope="session")
def e2e_postgres_url(request: pytest.FixtureRequest) -> str:
    """The database this whole run uses.

    `postgres_container` is only requested when no external DSN is given, so
    a run against an already-provisioned PostgreSQL never needs a Docker
    daemon to be reachable at all."""
    external = os.environ.get(_EXTERNAL_DSN_ENV)
    if external:
        return external
    container = request.getfixturevalue("postgres_container")
    return str(container.get_connection_url())


@pytest.fixture(scope="session", autouse=True)
def _migrated_schemas(e2e_postgres_url: str) -> None:
    """Applies all six engines' real migration chains to the one database.

    Synchronous and session-scoped, matching every other real-Postgres test
    in this repository: `alembic upgrade` drives its own event loop, so it
    must not run inside an async test."""
    for env_var, ini_path in _MIGRATIONS:
        os.environ[env_var] = e2e_postgres_url
        run_alembic_upgrade(ini_path)


class _RendezvousPostgresActionRepository(PostgresActionRepository):
    """The **real** `PostgresActionRepository`, plus the parallelism proof.

    The first `Action` inserted for each named `source` blocks on a two-party
    barrier before the real INSERT runs; every later one goes straight
    through. An agent reaches `insert()` only from inside its own real
    `execute()`, so the barrier releases only when two different real agent
    instances are genuinely in flight at once.

    Every other method, and the INSERT itself, is inherited unchanged --
    `super().insert(action)` does the real work against real Postgres."""

    def __init__(
        self,
        session_factory: async_sessionmaker[Any],
        *,
        sources: frozenset[str],
        timeout: float = 30.0,
    ) -> None:
        super().__init__(session_factory)
        self._sources = sources
        self._barrier = asyncio.Barrier(len(sources))
        self._arrived: set[str] = set()
        self._timeout = timeout
        self._in_flight = 0
        self.concurrent_peak = 0

    async def insert(self, action: Action) -> Action:
        if action.source in self._sources and action.source not in self._arrived:
            self._arrived.add(action.source)
            self._in_flight += 1
            self.concurrent_peak = max(self.concurrent_peak, self._in_flight)
            try:
                async with asyncio.timeout(self._timeout):
                    await self._barrier.wait()
            finally:
                self._in_flight -= 1
        return await super().insert(action)


@pytest.fixture
def shared_bus(monkeypatch: pytest.MonkeyPatch) -> InMemoryEventBus:
    """One broker for all seven engines -- see the default-tier variant's own
    fixture for why `nova_eventbus_sdk.boundary` is patched alongside the six
    `main` modules."""
    bus = InMemoryEventBus()
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    for module in (
        "nova_eventbus_sdk.boundary",
        "nova_planning_engine.main",
        "nova_capability_engine.main",
        "nova_action_engine.main",
        "nova_agent_os_registry.main",
        "nova_agent_os_supervisors.main",
        "nova_agent_os_kernel.main",
    ):
        monkeypatch.setattr(f"{module}.get_event_bus", lambda bus=bus: bus)
    return bus


class _RealPostgresStack:
    """All seven engines on one bus, over one real PostgreSQL database."""

    def __init__(self, repo: Path, user_id: UUID, bus: InMemoryEventBus, dsn: str) -> None:
        self.repo = repo
        self.user_id = user_id
        self.bus = bus
        self.dsn = dsn

        self.planning_model = _PlanningModelPort()
        self.agent_model_gateway = _AgentModelGateway()
        self.completions: list[AgentOsTaskCompletedPayload] = []

        # `action-engine`'s repository is the one this test constructs, and
        # it is constructed exactly the way `main.py` constructs its own:
        # `create_engine(dsn)` then `create_session_factory(engine)`.
        self._action_engine = create_engine(dsn)
        self.action_repository = _RendezvousPostgresActionRepository(
            create_session_factory(self._action_engine),
            sources=frozenset({"coding-agent", "documentation-agent"}),
        )

        self._contexts: list[Any] = []

    def _build_apps(self) -> None:
        # Every `Settings()` below reads the `<ENGINE>_POSTGRES_DSN` that
        # `_migrated_schemas` exported, so each engine that is *not* handed a
        # repository builds its own real Postgres one in its own lifespan.
        self.reasoning_app = create_reasoning_app(
            ReasoningSettings(),
            memory_port=_reasoning_fakes.FakeMemoryPort(),
            knowledge_port=_reasoning_fakes.FakeKnowledgePort([_GROUNDING]),
            world_model_port=_reasoning_fakes.FakeWorldModelPort(),
            personal_context_port=_reasoning_fakes.FakePersonalContextPort(),
            goals_port=_reasoning_fakes.FakeGoalsPort(),
            model_orchestration_port=_reasoning_fakes.FakeModelOrchestrationPort(),
        )
        self.planning_app = create_planning_app(
            PlanningSettings(),
            model_orchestration_port=self.planning_model,
        )
        self.capability_app = create_capability_app(
            CapabilitySettings(
                sandbox_filesystem_root=str(self.repo),
                sandbox_terminal_path=_TERMINAL_PATH,
            ),
        )
        self.action_app = create_action_app(
            ActionSettings(),
            repository=self.action_repository,
            identity_port=_TrustedIdentityPort(),
        )
        self.registry_app = create_registry_app(
            RegistrySettings(agents_root=str(_AGENTS_ROOT), primary_user_id=self.user_id),
        )
        self.supervisor_app = create_supervisor_app(
            SupervisorSettings(primary_user_id=self.user_id)
        )

        kernel_action_bus = BoundEventBus(
            self.bus,
            engine_name="kernel",
            publishable_subjects=frozenset({"action.execute"}),
            subscribable_subjects=frozenset(),
        )
        self.kernel_app = create_kernel_app(
            KernelSettings(agents_root=str(_AGENTS_ROOT), primary_user_id=self.user_id),
            execution_backend=InprocessExecutionBackend(
                agents_root=_AGENTS_ROOT,
                model_gateway=self.agent_model_gateway,
                action_port=ActionClient(kernel_action_bus),
            ),
        )

    async def __aenter__(self) -> _RealPostgresStack:
        self._build_apps()
        for app in (
            self.capability_app,
            self.action_app,
            self.registry_app,
            self.supervisor_app,
            self.reasoning_app,
            self.planning_app,
            self.kernel_app,
        ):
            ctx = app.router.lifespan_context(app)
            await ctx.__aenter__()
            self._contexts.append(ctx)

        observer = BoundEventBus(
            self.bus,
            engine_name="test-observer",
            publishable_subjects=frozenset(),
            subscribable_subjects=frozenset({"agent_os.task.completed"}),
        )
        await observer.connect()

        async def _record(envelope: EventEnvelope) -> None:
            self.completions.append(AgentOsTaskCompletedPayload.model_validate(envelope.payload))

        await observer.subscribe("agent_os.task.completed", _record)
        return self

    async def __aexit__(self, *exc: object) -> None:
        for ctx in reversed(self._contexts):
            await ctx.__aexit__(None, None, None)
        await self._action_engine.dispose()

    async def drain_outboxes(self, *, max_rounds: int = 12) -> int:
        """Both engines' real production outbox dispatchers, run against real
        Postgres outbox tables until neither has an undispatched row left."""
        total = 0
        for _ in range(max_rounds):
            dispatched = await dispatch_reasoning_outbox(
                self.reasoning_app.state.repository, self.reasoning_app.state.bus
            )
            dispatched += await dispatch_planning_outbox(
                self.planning_app.state.repository, self.planning_app.state.bus
            )
            if dispatched == 0:
                return total
            total += dispatched
        raise AssertionError("outbox dispatch did not settle -- the cascade is looping")


async def _run_objective(stack: _RealPostgresStack) -> None:
    """The one and only input: the real Reasoning Engine's own HTTP API."""
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=stack.reasoning_app)
    async with AsyncClient(transport=transport, base_url="http://reasoning") as client:
        response = await client.post(
            "/v1/reasoning/reason",
            json={
                "objective_text": _OBJECTIVE,
                "user_id": str(stack.user_id),
                "requesting_engine": "test-harness",
                "reasoning_mode_hint": "reactive",
            },
        )
    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "decided"

    await stack.drain_outboxes()


async def _verify_rows(dsn: str, correlation_id: UUID, user_id: UUID) -> dict[str, Any]:
    """Reads the run's results back with raw SQL over a **separate**
    connection, so nothing here can be satisfied by an in-memory object the
    system under test still happens to hold."""
    engine = create_engine(dsn)
    try:
        async with engine.connect() as conn:
            actions = (
                await conn.execute(
                    text(
                        "SELECT source, action_type, execution_target, status, requested_by "
                        "FROM action.action ORDER BY created_at"
                    )
                )
            ).all()
            instances = (
                await conn.execute(
                    text(
                        "SELECT category, status, health_status, agent_package_id "
                        "FROM agent_os.agent_instance ORDER BY started_at"
                    )
                )
            ).all()
            packages = (
                await conn.execute(
                    text("SELECT category, version FROM agent_os.agent_package ORDER BY category")
                )
            ).all()
            nodes = (
                await conn.execute(
                    text(
                        "SELECT assigned_agent_category, status FROM planning.task_node "
                        "ORDER BY assigned_agent_category"
                    )
                )
            ).all()
            reasoning_outbox = (
                await conn.execute(
                    text(
                        "SELECT subject, dispatched_at IS NOT NULL FROM reasoning.outbox_event "
                        "WHERE correlation_id = :cid"
                    ),
                    {"cid": str(correlation_id)},
                )
            ).all()
            planning_outbox = (
                await conn.execute(
                    text("SELECT subject, dispatched_at IS NOT NULL FROM planning.outbox_event")
                )
            ).all()
            graphs = (
                await conn.execute(text("SELECT root_objective FROM planning.task_graph"))
            ).all()
    finally:
        await engine.dispose()

    return {
        "actions": [tuple(row) for row in actions],
        "instances": [tuple(row) for row in instances],
        "packages": [tuple(row) for row in packages],
        "nodes": [tuple(row) for row in nodes],
        "reasoning_outbox": [tuple(row) for row in reasoning_outbox],
        "planning_outbox": [tuple(row) for row in planning_outbox],
        "graphs": [tuple(row) for row in graphs],
        "user_id": user_id,
    }


async def test_the_acceptance_objective_completes_on_real_postgres(
    tmp_path: Path, shared_bus: InMemoryEventBus, e2e_postgres_url: str
) -> None:
    """TDD 3E §13 and §14 criterion #1, with real persistence underneath.

    One test rather than several: a full run writes to a shared database, so
    splitting the assertions across tests would either re-run the whole chain
    per test or leak state between them. The assertion blocks below mirror,
    one for one, the seven tests of the default-tier variant."""
    repo = _init_target_repo(tmp_path)
    user_id = uuid4()

    stack = _RealPostgresStack(repo, user_id, shared_bus, e2e_postgres_url)
    async with stack:
        await _run_objective(stack)

        # The repositories really are the production Postgres ones, built by
        # each engine's own lifespan -- not fakes that happen to satisfy the
        # same Protocol.
        assert type(stack.reasoning_app.state.repository).__name__ == (
            "PostgresReasoningRepository"
        )
        assert type(stack.planning_app.state.repository).__name__ == "PostgresPlanningRepository"
        assert type(stack.capability_app.state.repository).__name__ == (
            "PostgresCapabilityRepository"
        )
        assert type(stack.registry_app.state.repository).__name__ == "PostgresRegistryRepository"
        assert type(stack.kernel_app.state.repository).__name__ == "PostgresKernelRepository"
        assert isinstance(stack.action_repository, PostgresActionRepository)

        correlation_id = stack.completions[0].correlation_id
        peak = stack.action_repository.concurrent_peak

    # --- §14 #1, parallelism: two real agent instances were inside their own
    # real `execute()` at the same moment.
    assert peak == 2

    # --- §14 #1, peer review: one real round, classified by the real
    # Engineering Supervisor, and only for the package that declares a
    # reviewer.
    by_category = {c.task_node_id: c for c in stack.completions}
    assert len(by_category) == 3
    reviewed = [c for c in stack.completions if c.result and "peer_validation" in c.result]
    assert len(reviewed) == 1
    assert reviewed[0].result is not None
    assert reviewed[0].result["peer_validation"] == "approved"
    assert all(c.outcome == "success" for c in stack.completions)

    # --- §13, the real git commit, read from the repository's own history.
    assert _git(repo, "rev-list", "--count", "HEAD") == "2"
    assert _git(repo, "log", "-1", "--format=%s").startswith("coding-agent: ")
    assert _git(repo, "log", "-1", "--format=%an") == _AUTHOR_NAME
    assert _git(repo, "log", "-1", "--format=%ae") == _AUTHOR_EMAIL
    committed = _git(repo, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert len(committed) == 1
    assert committed[0].startswith("coding-agent-output/")
    blob = _git(repo, "show", f"HEAD:{committed[0]}")
    assert "Scripted change committed by coding-agent." in blob
    assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""

    # --- §14 #1, a passing test suite in the target repo, run by `qa-agent`
    # through a real `pytest` subprocess with the repository as its cwd.
    qa = next(
        c
        for c in stack.completions
        if c.result
        and isinstance(c.result.get("output"), dict)
        and "exit_code" in c.result["output"]
    )
    assert qa.result is not None
    assert qa.result["output"]["exit_code"] == 0, qa.result["output"]
    assert "3 passed" in qa.result["output"]["stdout"]

    # --- Everything above, re-read from PostgreSQL over its own connection.
    rows = await _verify_rows(e2e_postgres_url, correlation_id, user_id)

    assert rows["graphs"] == [(_OBJECTIVE,)]
    assert sorted(rows["nodes"]) == [
        ("coding", "completed"),
        ("documentation", "completed"),
        ("qa", "completed"),
    ]

    # write + add + commit (coding) + write (documentation) + pytest (qa).
    assert len(rows["actions"]) == 5
    assert {row[0] for row in rows["actions"]} == {
        "coding-agent",
        "documentation-agent",
        "qa-agent",
    }
    assert {row[3] for row in rows["actions"]} == {"completed"}
    assert {row[4] for row in rows["actions"]} == {user_id}
    git_rows = [row for row in rows["actions"] if row[2] == "git"]
    assert len(git_rows) == 2
    assert {row[1] for row in git_rows} == {"terminal"}

    # Three `agent_instance` rows, all terminal, each pinned to the
    # `agent_package` row the real Registry installed for its category.
    installed = dict(rows["packages"])
    assert {"coding", "documentation", "qa", "research", "architect"} <= set(installed)
    assert set(installed.values()) == {"0.1.0"}
    assert len(rows["instances"]) == 3
    assert {row[1] for row in rows["instances"]} == {"completed"}
    assert {row[2] for row in rows["instances"]} == {"healthy"}
    assert sorted(row[0] for row in rows["instances"]) == ["coding", "documentation", "qa"]

    # Both real outboxes were written and then really marked dispatched.
    assert rows["reasoning_outbox"] == [("reasoning.process.completed", True)]
    assert rows["planning_outbox"]
    assert {row[0] for row in rows["planning_outbox"]} == {"planning.task_graph.created"}
    assert all(dispatched for _subject, dispatched in rows["planning_outbox"])
