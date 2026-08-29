"""Decision D5's binding proof: `coding-agent`'s real `execute()` produces a
**real git commit** in a real repository, through the real Action Engine and
the real `GitAdapter`.

Nothing in the chain below the Handler is mocked. `action-engine` and
`capability-engine` are both stood up with their own `create_app()` on one
shared in-memory Event Bus, `action-engine` builds its own real
`CapabilityClient` over that bus, `capability-engine` builds its own real
`FilesystemAdapter`/`GitAdapter`/`TerminalAdapter`, and those spawn real
`git` subprocesses. The Handler reaches them through `agent-os/kernel`'s own
production `ActionClient` -- the same object `InprocessExecutionBackend`
injects -- rather than a test stand-in, so the request path is the real one.

Two boundaries are stood in for, neither of them the git path:

- **`ActionRepository`** -- `action-engine`'s own `FakeActionRepository`,
  loaded from that package's test fakes rather than re-implemented here.
  Postgres persistence is that engine's own `real_infra` concern and is
  orthogonal to whether a commit happens.
- **`IdentityPort`** -- ADR-032's identity-confidence signal, which in
  production comes from `perception-engine`. Absent it, the gate fails closed
  (confidence 0.0 against a 1.0 threshold) and no action would execute at
  all. That is the correct production behaviour and is already proven by
  `action-engine`'s own tests; here it is satisfied so the git path is
  reachable.

**Verification is done by asking git, not by reading the handler's own
report.** Every assertion about the commit shells out to `git log`/`git
show`/`git status` in the repository afterwards, so a handler that returned
`status="success"` without committing anything fails these tests.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest
from nova_agent_os_kernel.clients.action_client import ActionClient
from nova_agent_sdk import AgentContext, AgentManifest
from nova_capability_engine.config import Settings as CapabilitySettings
from nova_capability_engine.main import create_app as create_capability_app
from nova_contracts import (
    ActionExecuteRequestPayload,
    ActionPriority,
    PermissionSet,
    TaskNodeSnapshot,
    WorldModelSnapshot,
)
from nova_eventbus_sdk import BoundEventBus
from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus

_REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from handler import Handler, commit_message_for, output_path_for  # noqa: E402

# The subprocess environment `TerminalAdapter` gives every git invocation:
# one `PATH`, nothing else -- notably no `HOME`.
_GIT_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin"}
_AUTHOR_NAME = "NOVA Coding Agent"
_AUTHOR_EMAIL = "coding-agent@nova.invalid"


def _load_module(name: str, relative_path: str) -> ModuleType:
    """Loads another package's own test fake by path. Reusing
    `action-engine`'s `FakeActionRepository` keeps this test honest about
    that engine's real repository semantics (including its
    `ActionAlreadyExistsError` translation) instead of re-implementing them
    approximately here."""
    spec = importlib.util.spec_from_file_location(name, _REPO_ROOT / relative_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FakeActionRepository = _load_module(
    "_ae_fake_repository", "services/action-engine/tests/fakes/repository.py"
).FakeActionRepository
FakeCapabilityRepository = _load_module(
    "_ce_fake_repository", "services/capability-engine/tests/fakes/repository.py"
).FakeCapabilityRepository


class _TrustedIdentityPort:
    """ADR-032's signal, satisfied. Returns full confidence for any user so
    the identity gate admits the action; everything downstream of the gate is
    real."""

    async def get_confidence(self, *, user_id: object) -> float:
        return 1.0


def _git(repo: Path, *args: str) -> str:
    """Verification helper -- runs git directly, outside the system under
    test, so what it reports is the repository's real state."""
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=_GIT_ENV,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _init_repo(tmp_path: Path, *, configure_identity: bool = True) -> Path:
    """A real, empty git repository. D5: `user.name`/`user.email` are set
    **locally**, in the repository itself -- never globally, and never
    through an environment variable the adapter would have to carry."""
    repo = tmp_path / "target-repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, env=_GIT_ENV, check=True)
    if configure_identity:
        subprocess.run(
            ["git", "config", "user.name", _AUTHOR_NAME], cwd=repo, env=_GIT_ENV, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", _AUTHOR_EMAIL], cwd=repo, env=_GIT_ENV, check=True
        )
    return repo


def _task() -> TaskNodeSnapshot:
    return TaskNodeSnapshot(
        id=uuid4(),
        objective="Add a health-check endpoint",
        depends_on=[],
        assigned_agent_category="coding",
        effort_hours=2.0,
        confidence=0.7,
        risk="moderate",
        status="ready",
    )


def _context(task: TaskNodeSnapshot) -> AgentContext:
    return AgentContext(
        task=task,
        world_model_slice=WorldModelSnapshot(user_id=uuid4(), degraded=True),
        relevant_memory=[],
        relevant_knowledge=[],
        granted_permissions=PermissionSet(granted=[]),
        granted_capabilities=[],
        correlation_id=uuid4(),
    )


def _manifest() -> AgentManifest:
    return AgentManifest.model_validate(
        {
            "id": "coding-agent",
            "version": "0.1.0",
            "category": "coding",
            "display_name": "Coding Agent",
            "required_capabilities": ["git", "filesystem", "terminal"],
            "required_permissions": ["filesystem:write:project-scope", "terminal:execute"],
            "supported_execution_backends": ["inprocess"],
            "resource_profile": {"cpu": "standard", "memory": "standard", "gpu": "none"},
            "health_check": {"interval_seconds": 30},
            "compatibility": {"min_kernel_version": "0.1.0"},
            "peer_reviewer_category": "architect",
        }
    )


class _RealStack:
    """The two engines and the bus, brought up together and torn down
    together."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.bus = InMemoryEventBus()
        self.capability_app = None
        self.action_app = None
        self.action_repository = FakeActionRepository()

    async def __aenter__(self) -> _RealStack:
        from nova_action_engine.config import Settings as ActionSettings
        from nova_action_engine.main import create_app as create_action_app

        self.capability_app = create_capability_app(
            CapabilitySettings(sandbox_filesystem_root=str(self.repo)),
            repository=FakeCapabilityRepository(),
        )
        self.action_app = create_action_app(
            ActionSettings(),
            repository=self.action_repository,
            identity_port=_TrustedIdentityPort(),
        )
        self._capability_ctx = self.capability_app.router.lifespan_context(self.capability_app)
        self._action_ctx = self.action_app.router.lifespan_context(self.action_app)
        await self._capability_ctx.__aenter__()
        await self._action_ctx.__aenter__()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._action_ctx.__aexit__(None, None, None)
        await self._capability_ctx.__aexit__(None, None, None)

    def action_client(self) -> ActionClient:
        """`agent-os/kernel`'s own production `ActionPort` implementation,
        over the same bus both engines are on."""
        caller_bus = BoundEventBus(
            self.bus,
            engine_name="kernel",
            publishable_subjects=frozenset({"action.execute"}),
            subscribable_subjects=frozenset(),
        )
        return ActionClient(caller_bus)


@pytest.fixture
def shared_bus(monkeypatch: pytest.MonkeyPatch) -> InMemoryEventBus:
    """One broker instance for both engines -- `create_app` in each calls
    `get_event_bus()`, so both are patched to the same object."""
    bus = InMemoryEventBus()
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    monkeypatch.setattr("nova_capability_engine.main.get_event_bus", lambda: bus)
    monkeypatch.setattr("nova_action_engine.main.get_event_bus", lambda: bus)
    return bus


async def _run_agent(stack: _RealStack, task: TaskNodeSnapshot, context: AgentContext):  # type: ignore[no-untyped-def]
    handler = Handler(agent_instance_id=uuid4(), action_port=stack.action_client())
    await handler.on_load(_manifest())
    await handler.on_assign(task, context)
    return await handler.execute()


async def test_coding_agent_produces_a_real_verifiable_commit(
    tmp_path: Path, shared_bus: InMemoryEventBus
) -> None:
    """D5 end to end. Every assertion after the agent runs comes from git."""
    repo = _init_repo(tmp_path)
    task = _task()
    context = _context(task)

    stack = _RealStack(repo)
    stack.bus = shared_bus
    async with stack:
        result = await _run_agent(stack, task, context)

    assert result.status == "success", result.output
    assert result.self_validation_passed is True

    # --- The commit exists, and it is the only one.
    assert _git(repo, "rev-list", "--count", "HEAD") == "1"
    commit_sha = _git(repo, "rev-parse", "HEAD")
    assert len(commit_sha) == 40

    # --- Its metadata is the one the agent asked for, read back from git.
    assert _git(repo, "log", "-1", "--format=%s") == commit_message_for(task)
    assert _git(repo, "log", "-1", "--format=%an") == _AUTHOR_NAME
    assert _git(repo, "log", "-1", "--format=%ae") == _AUTHOR_EMAIL

    # --- It contains exactly the file the agent wrote, and nothing else.
    relative_path = output_path_for(task)
    assert _git(repo, "show", "--name-only", "--format=", "HEAD").splitlines() == [relative_path]

    # --- The committed *blob* carries the real content -- read out of git's
    # object store, not off the working tree, so a staged-but-uncommitted
    # file could not satisfy this.
    committed_blob = _git(repo, "show", f"HEAD:{relative_path}")
    assert str(task.objective) in committed_blob
    assert "Scripted change committed by coding-agent." in committed_blob

    # --- Nothing is left uncommitted: the working tree is clean, which a
    # write-without-commit or an add-without-commit would both fail.
    assert _git(repo, "status", "--porcelain") == ""

    # --- The file really is on disk where D7 says the target root is.
    assert (repo / relative_path).read_text() == committed_blob + "\n"


async def test_three_real_actions_are_persisted_for_the_one_task(
    tmp_path: Path, shared_bus: InMemoryEventBus
) -> None:
    """The write/add/commit chain reached `action-engine` as three separate,
    completed Actions -- proven from that engine's own repository rather than
    from the agent's self-report."""
    repo = _init_repo(tmp_path)
    task = _task()

    stack = _RealStack(repo)
    stack.bus = shared_bus
    async with stack:
        result = await _run_agent(stack, task, _context(task))

    assert result.status == "success", result.output
    actions = list(stack.action_repository.actions.values())
    assert len(actions) == 3
    assert [a.status for a in actions] == ["completed", "completed", "completed"]
    assert {a.source for a in actions} == {"coding-agent"}
    assert [a.execution_target for a in actions] == ["filesystem", "git", "git"]
    # `ActionType`'s own rule: git is `terminal` plus an adapter selection.
    assert [a.action_type for a in actions] == ["filesystem", "terminal", "terminal"]


async def test_git_commits_without_HOME_in_the_subprocess_environment(
    tmp_path: Path, shared_bus: InMemoryEventBus
) -> None:
    """The Slice 3 watch item, settled against real git rather than assumed.

    `TerminalAdapter` exports exactly one variable (`PATH`) and inherits
    nothing, so every git invocation above ran with **no `HOME`**. The
    successful commit in the test above is itself the evidence; this test
    states the premise explicitly so a future change that starts relying on
    an inherited `HOME` fails here rather than mysteriously in an E2E run.

    Consequence recorded deliberately: no `HOME` is added to the terminal
    environment, and no new setting is introduced for one."""
    repo = _init_repo(tmp_path)
    task = _task()

    stack = _RealStack(repo)
    stack.bus = shared_bus
    async with stack:
        # The environment the adapter actually gives a subprocess, read from
        # inside one, through the same real capability path.
        env_probe = await stack.action_client().execute(_terminal_probe())
        result = await _run_agent(stack, task, _context(task))

    assert env_probe.status == "completed", env_probe.error
    assert env_probe.result is not None
    observed_env = env_probe.result["stdout"]
    assert "HOME" not in observed_env
    assert "PATH" in observed_env

    # ...and with that environment, the commit still happened.
    assert result.status == "success", result.output
    assert _git(repo, "rev-list", "--count", "HEAD") == "1"


def _terminal_probe() -> ActionExecuteRequestPayload:
    """A `terminal` action that reports the environment it was given, sent
    through the same real Action Engine and adapter the git steps use."""
    return ActionExecuteRequestPayload(
        action_id=uuid4(),
        action_type="terminal",
        priority=ActionPriority.NORMAL,
        source="test-probe",
        requested_by=uuid4(),
        execution_target="terminal",
        parameters={
            "operation": "execute",
            "executable": "python3",
            "args": ["-c", "import os; print(sorted(os.environ))"],
        },
        verification_method="environment inspection",
        requesting_engine="test-probe",
        correlation_id=uuid4(),
    )


async def test_a_repository_without_a_configured_identity_leaves_no_commit(
    tmp_path: Path, shared_bus: InMemoryEventBus
) -> None:
    """D5 requires the *fixture* to configure `user.name`/`user.email`
    locally. When it does not, real git refuses to commit -- and the agent
    must report that as a failure with nothing committed, rather than a
    successful change.

    This is the failure the exit-code check exists for: `action-engine`
    reports `status="completed"` for all three actions, because each
    invocation succeeded; only `exit_code` distinguishes them."""
    repo = _init_repo(tmp_path, configure_identity=False)
    task = _task()

    stack = _RealStack(repo)
    stack.bus = shared_bus
    async with stack:
        result = await _run_agent(stack, task, _context(task))

    assert result.status == "failure"
    assert result.output["failed_step"] == "commit"
    assert result.self_validation_passed is False

    # git itself confirms nothing was committed.
    assert subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, env=_GIT_ENV, capture_output=True
    ).returncode != 0
    # ...but the write and the staging really did happen, so the failure is
    # located at the commit and not earlier.
    assert (repo / output_path_for(task)).exists()
    assert _git(repo, "diff", "--cached", "--name-only") == output_path_for(task)
