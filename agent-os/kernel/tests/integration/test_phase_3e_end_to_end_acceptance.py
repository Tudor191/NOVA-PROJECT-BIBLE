"""**TDD 3E §13's scripted end-to-end objective, and §14 acceptance
criterion #1, proven on the real path.**

§13: "a real, scripted end-to-end objective ('add a health-check endpoint
to a sample repo') flows through Reasoning -> Planning -> NAOS (Kernel ->
Engineering Supervisor -> agent instances, including a peer-review round)
-> Action Engine -> a real git commit in a throwaway repo."

§14 #1: "...executes via at least two agent instances working in parallel
where dependencies allow, includes at least one real peer-review round
(`architect-agent` reviewing `coding-agent`'s output), and produces a
verifiable result (a passing test suite in the target repo)."

**The trigger is the real Reasoning Engine's own HTTP API**, not a
hand-constructed `planning.task_graph.created`. `POST /v1/reasoning/reason`
is the only thing this test publishes; every subsequent event on the bus is
produced by production code.

## The real path, hop by hop

    POST /v1/reasoning/reason            real reasoning-engine app
      -> reasoning `outbox_event` row    real domain/pipeline.py
      -> dispatch_ready_events()         real reasoning outbox dispatcher
      -> reasoning.process.completed     real BoundEventBus publish
      -> real planning-engine subscriber -> real domain/decomposition.py
      -> planning `outbox_event` row     real PlanningRepository.insert
      -> dispatch_ready_events()         real planning outbox dispatcher
      -> planning.task_graph.created     real BoundEventBus publish
      -> real Kernel subscriber          -> real domain/scheduler.py
      -> agent_os.registry...request     real RegistryClient RPC
      -> real agent-os/registry app      real 8-stage install pipeline
      -> real InprocessExecutionBackend  real agents/*/src/handler.py
      -> action.execute                  real kernel ActionClient RPC
      -> real action-engine app          real domain/pipeline.py
      -> capability.invoke.request       real CapabilityClient RPC
      -> real capability-engine app      real Filesystem/Terminal/GitAdapter
      -> real `git` / `pytest` subprocesses in the throwaway repository
      -> agent_os.supervisor.peer_review.request  real SupervisorClient RPC
      -> real agent-os/supervisors app   real peer-review classification
      -> agent_os.task.completed         real Kernel publish
      -> real planning-engine subscriber -> real TaskNode advancement
      -> (loop) the promoted `qa` node dispatches the same way

Seven real `create_app()`s share one `InMemoryEventBus`.

## What is stood in for, and why (none of it on the git path)

- **Every Postgres repository** -- each engine's own in-memory test fake.
  Postgres is `real_infra` (ADR-033, Docker), unavailable in the default
  suite. `_DispatchableReasoningRepository` additionally implements the
  two outbox-dispatch methods `FakeReasoningRepository` leaves as stubs,
  mirroring `FakePlanningRepository`'s own already-working implementation
  of them.
- **The Arq *scheduler*, not the dispatch loop.** Both engines publish
  through a transactional outbox drained by a separate Arq worker process
  (`workers/outbox_worker.py`). Arq needs Redis, also `real_infra`. This
  test therefore calls each engine's own **real production**
  `dispatch_ready_events` directly (see `_Stack.drain_outboxes`) -- the
  same function `arq_run_outbox_dispatch(ctx)` calls, doing the same
  `EventEnvelope` construction, publish, and `mark_dispatched`. Only the
  timer around it is the test's.
- **Both model boundaries** (ADR-020) -- `reasoning-engine`'s and
  `planning-engine`'s `ModelOrchestrationPort`, and the Kernel execution
  backend's `ModelGatewayPort`. No real provider call is legal here.
- **`action-engine`'s `IdentityPort`** -- ADR-032's signal, produced by
  `perception-engine` in production. Absent, the gate fails closed and
  nothing executes; satisfied, everything downstream is real. Identical to
  `agents/coding-agent/tests/integration/test_real_git_commit.py`.
- **`agent-os/registry`'s `CommunicationPort`** -- the install pipeline's
  best-effort Permission Review disclosure, which targets
  `communication-engine`; not part of this chain.

## Where the parallelism is observed

`_RendezvousActionRepository` is the `action-engine` repository fake with
one addition: the **first** `action.execute` from each of `coding-agent`
and `documentation-agent` blocks on a two-party `asyncio.Barrier` inside
`insert()`. An agent only reaches `insert()` from inside its own real
`execute()`, so the barrier can only release when two different real agent
instances are simultaneously mid-execution. Later actions from an
already-arrived source pass straight through, so `coding-agent`'s
`add`/`commit` steps are never gated.

Verified by negative control: with `dispatch_ready_nodes`' `asyncio.gather`
replaced by a sequential loop, the barrier's second party never arrives,
the wait times out, and `concurrent_peak` is 1 -- the assertion in
`test_two_independent_agent_instances_execute_genuinely_in_parallel` is the
one that fails. (The other six tests still pass under that patch, because
the Kernel's own bounded single retry re-runs each timed-out instance
successfully -- a real property, disclosed here so the scope of this
barrier's evidence is not overstated: it proves overlap, not liveness.)

## Cross-package imports, disclosed

This module imports six other engines' top-level packages and loads four
of their test fakes by path. That is a **test-only** dependency on the
`uv sync --all-packages` workspace environment CI already provisions; it
does not add a runtime dependency to `kernel`'s own `pyproject.toml`, and
ADR-004's import boundary (`uv run lint-imports`) governs
`nova_agent_os_kernel` itself, not this file. The precedent is
`agents/coding-agent/tests/integration/test_real_git_commit.py`, which
already stands up two engines' `create_app()`s the same way.
"""

from __future__ import annotations

import asyncio
import importlib.util
import subprocess
import sysconfig
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import UUID, uuid4

import pytest
from nova_action_engine.config import Settings as ActionSettings
from nova_action_engine.main import create_app as create_action_app
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
from nova_contracts import (
    AgentOsTaskCompletedPayload,
    EventEnvelope,
    GenerateReplyPayload,
    GenerateRequestPayload,
    ToolCallPayload,
)
from nova_eventbus_sdk import BoundEventBus
from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus
from nova_planning_engine.config import Settings as PlanningSettings
from nova_planning_engine.main import create_app as create_planning_app
from nova_planning_engine.repository.outbox_dispatcher import (
    dispatch_ready_events as dispatch_planning_outbox,
)
from nova_reasoning_engine.config import Settings as ReasoningSettings
from nova_reasoning_engine.domain.models import KnowledgeReference
from nova_reasoning_engine.domain.ports import OutboxRow as ReasoningOutboxRow
from nova_reasoning_engine.main import create_app as create_reasoning_app
from nova_reasoning_engine.repository.outbox_dispatcher import (
    dispatch_ready_events as dispatch_reasoning_outbox,
)

from tests.fakes.repository import FakeKernelRepository

_REPO_ROOT = Path(__file__).resolve().parents[4]
_AGENTS_ROOT = _REPO_ROOT / "agents"

_OBJECTIVE = "Add a health-check endpoint to a sample repo"

# `TerminalAdapter`'s own subprocess environment: one `PATH`, nothing else.
# The verification helpers below use the same one so what they observe is
# what the system under test could observe.
_GIT_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin"}
_AUTHOR_NAME = "NOVA Coding Agent"
_AUTHOR_EMAIL = "coding-agent@nova.invalid"

# `qa-agent` runs a fixed `pytest -q`. `pytest` lives in this workspace's
# virtualenv rather than on the conventional POSIX path, which is exactly
# the deployment-scoped case `Settings.sandbox_terminal_path`'s own
# docstring describes. Derived from the running interpreter so it is never
# machine-specific.
# `sysconfig`, not `Path(sys.executable).resolve()`: the venv's own
# `bin/python3` is a symlink out of the venv, so resolving it lands in the
# interpreter's install prefix, where no console scripts live.
_SCRIPTS_DIR = sysconfig.get_path("scripts")
_TERMINAL_PATH = f"{_SCRIPTS_DIR}:{_GIT_ENV['PATH']}"


def _load_module(name: str, relative_path: str) -> ModuleType:
    """Loads another package's own test fake by path -- reusing each
    engine's real fake keeps this test honest about that engine's own
    repository semantics instead of re-implementing them approximately."""
    spec = importlib.util.spec_from_file_location(name, _REPO_ROOT / relative_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_reasoning_fakes = _load_module("_re_fake_ports", "services/reasoning-engine/tests/fakes/ports.py")
FakeReasoningRepository = _load_module(
    "_re_fake_repository", "services/reasoning-engine/tests/fakes/repository.py"
).FakeReasoningRepository
FakePlanningRepository = _load_module(
    "_pe_fake_repository", "services/planning-engine/tests/fakes/repository.py"
).FakePlanningRepository
FakeActionRepository = _load_module(
    "_ae_fake_repository", "services/action-engine/tests/fakes/repository.py"
).FakeActionRepository
FakeCapabilityRepository = _load_module(
    "_ce_fake_repository", "services/capability-engine/tests/fakes/repository.py"
).FakeCapabilityRepository
FakeRegistryRepository = _load_module(
    "_rg_fake_repository", "agent-os/registry/tests/fakes/repository.py"
).FakeRegistryRepository
FakeRegistryCommunicationPort = _load_module(
    "_rg_fake_communication", "agent-os/registry/tests/fakes/communication_port.py"
).FakeCommunicationPort


# --------------------------------------------------------------------------
# The throwaway target repository
# --------------------------------------------------------------------------

_HEALTH_MODULE = '''"""The sample project the scripted objective targets."""


def health_status() -> dict[str, str]:
    return {"status": "ok"}
'''

_HEALTH_TEST = '''"""The sample repository's own pre-existing test."""

from health import health_status


def test_health_status_reports_ok() -> None:
    assert health_status() == {"status": "ok"}
'''

# The half of the target repository's suite that only passes once the agent
# instances have really done their work -- this is what makes "a passing
# test suite in the target repo" (TDD 3E §14 #1) a verification of the run
# rather than a tautology. `qa-agent` runs it via a real `pytest`
# subprocess, after `coding-agent` and `documentation-agent` have finished.
_AGENT_OUTPUT_TEST = '''"""Verifies, from inside the target repository, that the agent instances
really changed it -- run by `qa-agent`'s own `pytest -q`."""

import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parent


def test_the_coding_agent_output_is_committed_to_git() -> None:
    written = sorted((_REPO / "coding-agent-output").glob("*.md"))
    assert written, "coding-agent wrote no output file"
    # `ls-tree HEAD`, not `ls-files`: the latter reads the index, so a file
    # that was staged but never committed would still satisfy it.
    committed = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD", "coding-agent-output"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert committed, "coding-agent's output exists but was never committed"


def test_the_documentation_agent_output_landed_on_disk() -> None:
    assert sorted((_REPO / "documentation-agent-output").glob("*.md"))
'''


def _git(repo: Path, *args: str) -> str:
    """Runs git directly, outside the system under test, so what it reports
    is the repository's real state."""
    completed = subprocess.run(
        ["git", *args], cwd=repo, env=_GIT_ENV, capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


def _init_target_repo(tmp_path: Path) -> Path:
    """A real git repository holding a small sample project and its own
    test suite. D5: `user.name`/`user.email` are set **locally**, in the
    repository itself -- never globally, and never through an environment
    variable the adapter would have to carry."""
    repo = tmp_path / "sample-repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, env=_GIT_ENV, check=True)
    subprocess.run(["git", "config", "user.name", _AUTHOR_NAME], cwd=repo, env=_GIT_ENV, check=True)
    subprocess.run(
        ["git", "config", "user.email", _AUTHOR_EMAIL], cwd=repo, env=_GIT_ENV, check=True
    )
    (repo / "health.py").write_text(_HEALTH_MODULE)
    (repo / "test_health.py").write_text(_HEALTH_TEST)
    (repo / "test_agent_output.py").write_text(_AGENT_OUTPUT_TEST)
    subprocess.run(["git", "add", "-A"], cwd=repo, env=_GIT_ENV, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "Initial sample project"],
        cwd=repo,
        env=_GIT_ENV,
        check=True,
    )
    return repo


# --------------------------------------------------------------------------
# Stand-ins (see this module's docstring for why each one is legitimate)
# --------------------------------------------------------------------------


class _DispatchableReasoningRepository(FakeReasoningRepository):  # type: ignore[misc, valid-type]
    """`FakeReasoningRepository` plus a working outbox, so the **real**
    `dispatch_ready_events` has rows to publish.

    That fake records `OutboxEvent`s but leaves `list_dispatch_ready`
    returning `[]` and `mark_dispatched` a no-op, because no reasoning test
    had ever needed to drive the dispatcher. This subclass supplies exactly
    the behaviour `FakePlanningRepository` already implements for the same
    two methods: mint a row id, hand rows back oldest-first, drop a row once
    it is dispatched."""

    def __init__(self) -> None:
        super().__init__()
        self._rows: dict[UUID, ReasoningOutboxRow] = {}
        self._promoted = 0
        self.dispatched: list[UUID] = []

    def _promote_new_events(self) -> None:
        while self._promoted < len(self.outbox):
            event = self.outbox[self._promoted]
            self._promoted += 1
            row_id = uuid4()
            self._rows[row_id] = ReasoningOutboxRow(
                id=row_id,
                subject=event.subject,
                payload=event.payload,
                correlation_id=event.correlation_id,
                causation_id=event.causation_id,
                created_at=datetime.now(UTC),
            )

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[ReasoningOutboxRow]:
        self._promote_new_events()
        return sorted(self._rows.values(), key=lambda row: row.created_at)[:limit]

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        self._rows.pop(outbox_id, None)
        self.dispatched.append(outbox_id)


class _RendezvousActionRepository(FakeActionRepository):  # type: ignore[misc, valid-type]
    """`action-engine`'s own repository fake, plus the parallelism proof.

    The first `Action` inserted for each named `source` blocks on a
    two-party barrier; every later one passes through untouched. An agent
    reaches `insert()` only from inside its own real `execute()`, so the
    barrier releases only if two different real agent instances are
    genuinely in flight at the same moment.

    Nothing about the action pipeline is altered: this is stage 2's normal
    persistence call, awaited slightly longer."""

    def __init__(self, *, sources: frozenset[str], timeout: float = 20.0) -> None:
        super().__init__()
        self._sources = sources
        self._barrier = asyncio.Barrier(len(sources))
        self._arrived: set[str] = set()
        self._timeout = timeout
        self._in_flight = 0
        self.concurrent_peak = 0

    async def insert(self, action: Any) -> Any:
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


_GROUNDING = KnowledgeReference(
    node_id="node-health-endpoint",
    name="Expose a /health endpoint returning {'status': 'ok'}",
    layer="verified",
    confidence=0.9,
)
"""The one retrieved `KnowledgeReference` the objective is grounded in.

Reactive mode (`domain/pipeline.py::_resolve_reactive`) answers from
whatever context was actually retrieved, and scores an ungrounded answer
`confidence_score=0.1` -- below `planning-engine`'s own
`decomposition_confidence_threshold` of 0.6, so an ungrounded objective is
correctly never decomposed. Supplying real grounding is what makes this
run decomposable; the threshold itself is left at its default, unmodified.
Its `name` becomes the `chosen_description` `decompose()` receives."""


class _TrustedIdentityPort:
    """ADR-032's identity-confidence signal, satisfied so the gate admits
    the actions; everything downstream of the gate is real."""

    async def get_confidence(self, *, user_id: object) -> float:
        return 1.0


class _PlanningModelPort:
    """`planning-engine`'s `ModelOrchestrationPort` (ADR-020's boundary),
    answering the real `propose_task_graph` tool schema with the diamond
    TDD 3E §14 #1 needs: two independent nodes plus one that depends on
    both."""

    def __init__(self) -> None:
        self.requests: list[GenerateRequestPayload] = []

    async def generate(self, request: GenerateRequestPayload) -> GenerateReplyPayload:
        self.requests.append(request)
        return GenerateReplyPayload(
            text="",
            input_tokens=10,
            output_tokens=10,
            finish_reason="tool_calls",
            structural_confidence=0.9,
            model_id=uuid4(),
            provider="fake",
            tool_calls=[
                ToolCallPayload(
                    id="call-1",
                    tool_name="propose_task_graph",
                    arguments={
                        "tasks": [
                            {
                                "local_id": "endpoint",
                                "objective": "Add the /health endpoint",
                                "depends_on": [],
                                "assigned_agent_category": "coding",
                                "effort_hours": 2.0,
                                "confidence": 0.8,
                                "risk": "moderate",
                            },
                            {
                                "local_id": "docs",
                                "objective": "Document the /health endpoint",
                                "depends_on": [],
                                "assigned_agent_category": "documentation",
                                "effort_hours": 1.0,
                                "confidence": 0.9,
                                "risk": "low",
                            },
                            {
                                "local_id": "qa",
                                "objective": "Run the sample repository's test suite",
                                "depends_on": ["endpoint", "docs"],
                                "assigned_agent_category": "qa",
                                "effort_hours": 1.0,
                                "confidence": 0.9,
                                "risk": "low",
                            },
                        ]
                    },
                )
            ],
        )


class _AgentModelGateway:
    """The Kernel execution backend's `ModelGatewayPort` (ADR-020's
    boundary again) -- only `documentation-agent` calls it."""

    def __init__(self) -> None:
        self.requests: list[GenerateRequestPayload] = []

    async def generate(self, request: GenerateRequestPayload) -> GenerateReplyPayload:
        self.requests.append(request)
        return GenerateReplyPayload(
            text='# /health\n\nReturns `{"status": "ok"}`.',
            input_tokens=20,
            output_tokens=12,
            finish_reason="stop",
            structural_confidence=0.9,
            model_id=uuid4(),
            provider="fake",
        )


# --------------------------------------------------------------------------
# The stack
# --------------------------------------------------------------------------


class _Stack:
    """All seven engines on one bus, brought up and torn down together."""

    def __init__(self, repo: Path, user_id: UUID, bus: InMemoryEventBus) -> None:
        self.repo = repo
        self.user_id = user_id
        self.bus = bus

        self.reasoning_repository = _DispatchableReasoningRepository()
        self.planning_repository = FakePlanningRepository()
        self.action_repository = _RendezvousActionRepository(
            sources=frozenset({"coding-agent", "documentation-agent"})
        )
        self.registry_repository = FakeRegistryRepository()
        self.kernel_repository = FakeKernelRepository()

        self.planning_model = _PlanningModelPort()
        self.agent_model_gateway = _AgentModelGateway()
        self.completions: list[AgentOsTaskCompletedPayload] = []

        self._contexts: list[Any] = []

    def _build_apps(self) -> None:
        self.reasoning_app = create_reasoning_app(
            ReasoningSettings(),
            memory_port=_reasoning_fakes.FakeMemoryPort(),
            knowledge_port=_reasoning_fakes.FakeKnowledgePort([_GROUNDING]),
            world_model_port=_reasoning_fakes.FakeWorldModelPort(),
            personal_context_port=_reasoning_fakes.FakePersonalContextPort(),
            goals_port=_reasoning_fakes.FakeGoalsPort(),
            model_orchestration_port=_reasoning_fakes.FakeModelOrchestrationPort(),
            repository=self.reasoning_repository,
        )
        self.planning_app = create_planning_app(
            PlanningSettings(),
            repository=self.planning_repository,
            model_orchestration_port=self.planning_model,
        )
        self.capability_app = create_capability_app(
            CapabilitySettings(
                sandbox_filesystem_root=str(self.repo),
                sandbox_terminal_path=_TERMINAL_PATH,
            ),
            repository=FakeCapabilityRepository(),
        )
        self.action_app = create_action_app(
            ActionSettings(),
            repository=self.action_repository,
            identity_port=_TrustedIdentityPort(),
        )
        self.registry_app = create_registry_app(
            RegistrySettings(agents_root=str(_AGENTS_ROOT), primary_user_id=self.user_id),
            repository=self.registry_repository,
            communication_port=FakeRegistryCommunicationPort(session_id=None),
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
            repository=self.kernel_repository,
            execution_backend=InprocessExecutionBackend(
                agents_root=_AGENTS_ROOT,
                model_gateway=self.agent_model_gateway,
                action_port=ActionClient(kernel_action_bus),
            ),
        )

    async def __aenter__(self) -> _Stack:
        self._build_apps()
        # Capability/Action/Registry/Supervisor first: the Kernel's own
        # dispatch is driven by an event, so nothing races, but every RPC
        # server a dispatch needs must already be serving.
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

    async def drain_outboxes(self, *, max_rounds: int = 12) -> int:
        """Runs both engines' **real** outbox dispatchers until neither has
        a row left -- what the two Arq workers do continuously in
        production. Each published event is fully processed inside its own
        `publish()` (the in-memory bus delivers inline), so a round that
        dispatches nothing means the whole cascade has settled."""
        total = 0
        for _ in range(max_rounds):
            dispatched = await dispatch_reasoning_outbox(
                self.reasoning_repository, self.reasoning_app.state.bus
            )
            dispatched += await dispatch_planning_outbox(
                self.planning_repository, self.planning_app.state.bus
            )
            if dispatched == 0:
                return total
            total += dispatched
        raise AssertionError("outbox dispatch did not settle -- the cascade is looping")


@pytest.fixture
def shared_bus(monkeypatch: pytest.MonkeyPatch) -> InMemoryEventBus:
    """One broker for all seven engines.

    Six `create_app()`s call `get_event_bus()` through their own module-level
    import; `reasoning-engine` reaches it via `bind_event_bus`, so the SDK's
    own `boundary` module is patched too."""
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


async def _run_objective(stack: _Stack) -> None:
    """Drives the one and only input: the real Reasoning Engine's HTTP API."""
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


@pytest.fixture
async def completed_run(tmp_path: Path, shared_bus: InMemoryEventBus):  # type: ignore[no-untyped-def]
    """One complete end-to-end run, in its own throwaway repository.

    Deliberately function-scoped: each test below gets a fresh `tmp_path`,
    a fresh bus and a fresh set of engines, so no test can pass on state
    another one left behind. Every test then inspects a different facet of
    its own real run."""
    repo = _init_target_repo(tmp_path)
    stack = _Stack(repo, uuid4(), shared_bus)
    async with stack:
        await _run_objective(stack)
        yield stack


# --------------------------------------------------------------------------
# TDD 3E §13 -- the objective flows the whole way
# --------------------------------------------------------------------------


async def test_the_objective_flows_from_reasoning_to_a_real_git_commit(
    completed_run: _Stack,
) -> None:
    """§13, end to end. The only thing published by this test is the
    reasoning request; the commit below is what came out the other side."""
    stack = completed_run
    repo = stack.repo

    # --- Reasoning really ran and really enqueued its own event.
    assert stack.reasoning_repository.dispatched, "no reasoning outbox row was dispatched"
    assert [e.subject for e in stack.reasoning_repository.outbox] == ["reasoning.process.completed"]

    # --- Planning really decomposed it, through the real tool schema.
    assert len(stack.planning_model.requests) == 1
    graphs = list(stack.planning_repository.graphs.values())
    assert len(graphs) == 1
    assert graphs[0].root_objective == _OBJECTIVE
    assert {node.assigned_agent_category for node in graphs[0].nodes} == {
        "coding",
        "documentation",
        "qa",
    }

    # --- All three nodes reached a terminal, successful state.
    assert [node.status for node in graphs[0].nodes] == ["completed"] * 3

    # --- A real commit exists on top of the fixture's own initial commit.
    assert _git(repo, "rev-list", "--count", "HEAD") == "2"
    assert _git(repo, "log", "-1", "--format=%s").startswith("coding-agent: ")
    assert _git(repo, "log", "-1", "--format=%an") == _AUTHOR_NAME
    assert _git(repo, "log", "-1", "--format=%ae") == _AUTHOR_EMAIL


async def test_the_commit_is_verifiable_from_the_repositorys_own_git_history(
    completed_run: _Stack,
) -> None:
    """Requirement 6 -- every claim here is read back out of git, never off
    the agent's own report."""
    repo = completed_run.repo

    committed = _git(repo, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert len(committed) == 1
    relative_path = committed[0]
    assert relative_path.startswith("coding-agent-output/")
    assert relative_path.endswith(".md")

    # Read out of git's object store, so a staged-but-uncommitted file could
    # not satisfy it.
    blob = _git(repo, "show", f"HEAD:{relative_path}")
    assert "Scripted change committed by coding-agent." in blob
    assert (repo / relative_path).read_text() == blob + "\n"

    # The commit is genuinely a child of the fixture's own initial commit --
    # not a re-initialised or orphaned history.
    assert _git(repo, "log", "--format=%s", "--reverse").splitlines()[0] == (
        "Initial sample project"
    )
    assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""


async def test_the_target_repositorys_own_test_suite_ran_and_passed(
    completed_run: _Stack,
) -> None:
    """§14 #1's "a verifiable result (a passing test suite in the target
    repo)" -- and requirement 5.

    `qa-agent` runs a real `pytest -q` subprocess whose working directory is
    the target repository (D8's `TerminalAdapter.default_cwd`). The suite it
    runs includes assertions that only hold because the other two agents
    really changed the repository, so a green exit code here is evidence
    about this run, not about the fixture."""
    stack = completed_run
    qa = _completion_for(stack, "qa-agent")

    assert qa.outcome == "success", qa.result
    assert qa.result is not None
    output = qa.result["output"]
    assert output["exit_code"] == 0, output
    assert "3 passed" in output["stdout"], output["stdout"]

    # The suite really is the target repository's own, and it really was run
    # from inside it: the fixture only ever *wrote* these modules, so the
    # bytecode cache beside them could only have been produced by a Python
    # process that imported them in place.
    assert (stack.repo / "test_agent_output.py").exists()
    cached = {path.name.split(".")[0] for path in (stack.repo / "__pycache__").glob("*.pyc")}
    assert {"health", "test_health", "test_agent_output"} <= cached


# --------------------------------------------------------------------------
# TDD 3E §14 criterion #1 -- parallelism and peer review
# --------------------------------------------------------------------------


async def test_two_independent_agent_instances_execute_genuinely_in_parallel(
    completed_run: _Stack,
) -> None:
    """Requirement 4. `coding-agent` and `documentation-agent` were both
    inside their own real `execute()` at the same moment -- the barrier in
    `_RendezvousActionRepository` cannot release otherwise, and a sequential
    dispatch loop would have timed out inside the run."""
    stack = completed_run
    assert stack.action_repository.concurrent_peak == 2

    # ...and the two of them really are the graph's independent pair, with
    # the dependent node dispatched only afterwards.
    graph = next(iter(stack.planning_repository.graphs.values()))
    by_category = {node.assigned_agent_category: node for node in graph.nodes}
    assert by_category["qa"].depends_on == [
        by_category["coding"].id,
        by_category["documentation"].id,
    ]


async def test_a_real_peer_review_round_ran_against_the_coding_agents_output(
    completed_run: _Stack,
) -> None:
    """§14 #1's peer-review clause: a real `architect-agent` instance
    reviewed a real `coding-agent` result, and the real Engineering
    Supervisor -- not the Kernel -- classified the verdict."""
    coding = _completion_for(completed_run, "coding-agent")

    assert coding.result is not None
    assert coding.result["peer_validation"] == "approved"
    assert coding.outcome == "success"

    # Only `coding-agent` declares a reviewer, so no other node carries a
    # verdict -- the review round is targeted, not blanket.
    others = [c for c in completed_run.completions if c is not coding]
    assert all(c.result is None or "peer_validation" not in c.result for c in others)


# --------------------------------------------------------------------------
# Requirement 7 -- the semantics the earlier slices established still hold
# --------------------------------------------------------------------------


async def test_every_agent_instance_reached_a_terminal_row_with_its_pinned_package(
    completed_run: _Stack,
) -> None:
    """Lifecycle and version-pinning. Three dispatched nodes, three
    `agent_instance` rows, each pinned to the `agent_package` row the real
    Registry installed for its category, none left `"running"`."""
    stack = completed_run

    assert len(stack.completions) == 3
    assert await stack.kernel_repository.list_by_status("running") == []

    installed = {row.category: row for row in stack.registry_repository.rows.values()}
    assert {"coding", "documentation", "qa", "research", "architect"} <= set(installed)

    for completion in stack.completions:
        row = await stack.kernel_repository.find_by_id(completion.agent_instance_id)
        assert row is not None
        assert row.status == "completed"
        assert row.health_status == "healthy"
        assert row.assigned_task_node_id == completion.task_node_id
        assert row.agent_package_id == installed[row.category].id
        assert installed[row.category].version == "0.1.0"


async def test_action_provenance_and_identity_survive_the_full_path(
    completed_run: _Stack,
) -> None:
    """D6 and TDD 3D's provenance split: `Action.source` names the agent,
    `Action.requested_by` names the real user the identity gate resolves a
    policy for -- never the ephemeral instance id."""
    stack = completed_run
    actions = list(stack.action_repository.actions.values())

    # write + add + commit (coding) + write (documentation) + pytest (qa).
    assert len(actions) == 5
    assert all(action.status == "completed" for action in actions)
    assert {action.source for action in actions} == {
        "coding-agent",
        "documentation-agent",
        "qa-agent",
    }
    assert {action.requested_by for action in actions} == {stack.user_id}

    instance_ids = {completion.agent_instance_id for completion in stack.completions}
    assert not (instance_ids & {action.requested_by for action in actions})

    # `ActionType`'s own rule survives: git is `terminal` plus an adapter
    # selection, never a third `action_type` value.
    git_actions = [action for action in actions if action.execution_target == "git"]
    assert len(git_actions) == 2
    assert {action.action_type for action in git_actions} == {"terminal"}


def _completion_for(stack: _Stack, source: str) -> AgentOsTaskCompletedPayload:
    """Finds the `agent_os.task.completed` payload for the node the named
    agent handled, via that node's own category."""
    category = source.removesuffix("-agent")
    graph = next(iter(stack.planning_repository.graphs.values()))
    node_id = next(node.id for node in graph.nodes if node.assigned_agent_category == category)
    return next(c for c in stack.completions if c.task_node_id == node_id)
