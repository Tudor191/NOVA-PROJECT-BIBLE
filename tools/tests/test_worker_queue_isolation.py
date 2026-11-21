"""Every engine worker owns its own arq queue and its own cron job names.

The invariant: *each engine's arq worker is the sole enqueuer and sole consumer
of its own scheduled jobs.* Nothing in arq provides it, and losing it is silent
in both directions -- a stolen job that the thief cannot run is logged once at
WARNING and never re-enqueued, and an enqueue swallowed by a colliding job id
is not logged at all.

It was lost for as long as the repository existed, and invisible for as long as
the local stack ran a single arq worker. The Phase 4B E2E stack runs four, and
`communication-engine`'s outbox was then dispatched on roughly one tick in
four: run #77's diagnostics show 0 of 14 outbox rows dispatched, with the
worker healthy and its cron having fired exactly once. Phase 4B Gate Review
G-8 has the full account.

This file is the guard that keeps it from being lost again. It is a sibling of
`test_e2e_stack_completeness.py` for the same reason that one exists: the
failure mode is only observable under Docker, Docker is the expensive CI-only
path, and a defect that needs the expensive path to notice will be reintroduced
by the next engine someone scaffolds.

Parsed with `ast`, never imported: importing a `workers/__init__.py` constructs
that engine's `Settings()` at module scope, which needs a Postgres DSN and a
Redis URL this test has no business requiring.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES = REPO_ROOT / "services"

#: The helpers `nova_service_kit.worker` exposes. Named here rather than
#: matched loosely so a worker that hand-rolls an equivalent string -- and so
#: drifts the moment the derivation changes -- fails this test.
QUEUE_HELPER = "worker_queue_name"
CRON_HELPER = "service_cron"
SERVICE_CONST = "_SERVICE_NAME"


def _worker_modules() -> list[Path]:
    modules = sorted(SERVICES.glob("*/src/nova_*/workers/__init__.py"))
    assert modules, "found no engine workers at all; fix this parser, do not delete it"
    return modules


def _module_id(path: Path) -> str:
    """`communication-engine`, from the path -- for readable parametrised ids."""
    return path.relative_to(SERVICES).parts[0]


WORKER_MODULES = _worker_modules()
WORKER_IDS = [_module_id(path) for path in WORKER_MODULES]


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(), filename=str(path))


def _service_name(tree: ast.Module) -> str | None:
    """The `_SERVICE_NAME = "..."` constant at module scope."""
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == SERVICE_CONST for t in node.targets)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    return None


def _worker_settings(tree: ast.Module) -> ast.ClassDef | None:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "WorkerSettings":
            return node
    return None


def _assigned(cls: ast.ClassDef, name: str) -> ast.expr | None:
    for node in cls.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return node.value
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
        ):
            return node.value
    return None


def _cron_calls(cls: ast.ClassDef) -> list[ast.Call]:
    cron_jobs = _assigned(cls, "cron_jobs")
    if not isinstance(cron_jobs, ast.List):
        return []
    return [element for element in cron_jobs.elts if isinstance(element, ast.Call)]


def _coroutine_name(call: ast.Call) -> str:
    """The scheduled coroutine, whichever argument position it sits in.

    `service_cron(_SERVICE_NAME, arq_run_outbox_dispatch, ...)` puts it second;
    a bare `cron(arq_run_outbox_dispatch, ...)` puts it first.
    """
    for argument in call.args:
        if isinstance(argument, ast.Name) and argument.id != SERVICE_CONST:
            return argument.id
    return "<unparsed>"


# --- per worker -------------------------------------------------------------


@pytest.mark.parametrize("path", WORKER_MODULES, ids=WORKER_IDS)
def test_worker_declares_its_own_service_identity(path: Path) -> None:
    assert _service_name(_tree(path)) is not None, (
        f"{path.relative_to(REPO_ROOT)} has no module-level {SERVICE_CONST}. "
        "Every worker names the engine it belongs to once, and derives its arq "
        "queue and cron job names from it."
    )


@pytest.mark.parametrize("path", WORKER_MODULES, ids=WORKER_IDS)
def test_worker_owns_an_explicit_queue(path: Path) -> None:
    settings = _worker_settings(_tree(path))
    assert settings is not None, f"{path.relative_to(REPO_ROOT)} declares no WorkerSettings"

    queue = _assigned(settings, "queue_name")
    assert queue is not None, (
        f"{_module_id(path)}'s WorkerSettings sets no `queue_name`, so arq puts it on "
        "the global default `arq:queue` shared with every other engine's worker -- "
        "where whichever worker polls first claims the job, runs its own coroutine "
        "of that name, and discards jobs it has no function for."
    )
    assert (
        isinstance(queue, ast.Call)
        and isinstance(queue.func, ast.Name)
        and queue.func.id == QUEUE_HELPER
        and [a.id for a in queue.args if isinstance(a, ast.Name)] == [SERVICE_CONST]
    ), (
        f"{_module_id(path)}'s `queue_name` must read "
        f"`{QUEUE_HELPER}({SERVICE_CONST})`. A literal string would work today and "
        "drift the moment the derivation changes."
    )


@pytest.mark.parametrize("path", WORKER_MODULES, ids=WORKER_IDS)
def test_every_cron_job_carries_its_service(path: Path) -> None:
    settings = _worker_settings(_tree(path))
    assert settings is not None
    calls = _cron_calls(settings)
    assert calls, f"{_module_id(path)} schedules no cron jobs; this parser expected some"

    for call in calls:
        assert isinstance(call.func, ast.Name), f"{_module_id(path)}: unparsed cron entry"
        assert call.func.id == CRON_HELPER, (
            f"{_module_id(path)} schedules {_coroutine_name(call)} with "
            f"`{call.func.id}(...)`. A bare `cron(...)` names the job after the "
            "coroutine alone, and every engine's outbox entrypoint is called "
            "`arq_run_outbox_dispatch` -- so all of them derive one job id per tick "
            "and arq silently drops all but the first enqueue."
        )
        assert (
            call.args
            and isinstance(call.args[0], ast.Name)
            and call.args[0].id == SERVICE_CONST
        ), f"{_module_id(path)}: {CRON_HELPER} must take {SERVICE_CONST} first"


# --- across every worker ----------------------------------------------------


def test_no_two_workers_share_a_service_name() -> None:
    names = [_service_name(_tree(path)) for path in WORKER_MODULES]
    duplicates = [name for name, count in Counter(names).items() if count > 1]

    assert not duplicates, (
        f"two engines claim the same service identity: {duplicates}. Their queues "
        "and cron job names are derived from it, so they would share both."
    )


def test_no_two_workers_share_a_cron_job_identity() -> None:
    """The assertion that would have failed before this fix, and the reason the
    fix has two halves rather than one."""
    identities = [
        (service, _coroutine_name(call))
        for path in WORKER_MODULES
        for service in [_service_name(_tree(path))]
        for call in _cron_calls(_worker_settings(_tree(path)) or ast.ClassDef())
    ]
    duplicates = [key for key, count in Counter(identities).items() if count > 1]

    assert not duplicates, f"two workers derive the same arq cron job name: {duplicates}"


def test_the_collision_this_guards_is_real_not_hypothetical() -> None:
    """States the hazard positively.

    Ten engines schedule a coroutine called `arq_run_outbox_dispatch`, and
    `memory-engine`/`knowledge-engine` both schedule `arq_run_embedding_pass`.
    Without the service segment, arq derives one identity for each of those
    groups -- so if this assertion ever stops holding, the collision is gone
    for an unrelated reason and the guards above have quietly become vacuous.
    """
    coroutines = [
        _coroutine_name(call)
        for path in WORKER_MODULES
        for call in _cron_calls(_worker_settings(_tree(path)) or ast.ClassDef())
    ]
    colliding = {name for name, count in Counter(coroutines).items() if count > 1}

    assert "arq_run_outbox_dispatch" in colliding, (
        "no two engines share an outbox-dispatch coroutine name any more; if that is "
        "deliberate, this test has served its purpose and the reasoning above needs "
        "rewriting rather than the assertion deleting"
    )
