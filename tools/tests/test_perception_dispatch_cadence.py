"""`perception-engine` dispatches its outbox every second, serially, from
exactly one worker -- and no other engine's schedule moved.

D-4F-1 was reopened on 2026-10-11 for one item only: `perception-engine`'s
outbox dispatch interval, so that AC-7's unchanged 5-second budget can be met
(TDD 4F.8 §30). The exception is safe only in a narrow shape, and every part of
that shape is pinned here:

* **every second** -- the cadence the exception exists for;
* **`max_jobs = 1`** -- arq enqueues each tick under its own job id whether or
  not the previous run has finished, and `list_dispatch_ready` claims no row,
  so two runs alive at once can publish one row twice. A per-second cron
  without this setting overlapped itself in TDD 4F.8 §30.2's probe;
* **one worker process** -- `max_jobs` bounds one process, not a deployment.
  Two replicas overlapped even with `max_jobs = 1` (§30.2). Making several
  replicas safe would need row claiming in `nova_service_kit`'s shared outbox,
  which is outside the exception and not built. So compose defines exactly
  one `perception-engine-worker`, and nothing scales it;
* **every other engine unchanged** -- the exception is this engine's alone.

The runtime half -- a real arq worker, real Redis, PostgreSQL and NATS, no
overlap and no duplicate -- is
`services/perception-engine/tests/integration/test_outbox_dispatch_cadence_real_infra.py`.

Parsed with `ast` and `yaml`, never imported, for the reason
`test_worker_queue_isolation.py` gives: importing a `workers/__init__.py`
constructs that engine's `Settings()` at module scope.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES = REPO_ROOT / "services"
COMPOSE_DIR = REPO_ROOT / "infra" / "docker"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

PERCEPTION_WORKER = SERVICES / "perception-engine/src/nova_perception_engine/workers/__init__.py"
PERCEPTION_DOCKERFILE = SERVICES / "perception-engine" / "Dockerfile"
PERCEPTION_WORKER_TARGET = "nova_perception_engine.workers.WorkerSettings"
PERCEPTION_WORKER_SERVICE = "perception-engine-worker"

#: arq's own scheduling keywords. Any of them besides `second` would narrow
#: the per-second schedule to a subset of minutes, hours or days.
_SCHEDULE_KEYWORDS = {"month", "day", "weekday", "hour", "minute", "second", "microsecond"}

#: Every other engine's `WorkerSettings` at `phase-4` = `1ccce7a`, the commit
#: the 4F.8 branch was cut from: each cron job's coroutine and its schedule
#: keywords, verbatim. None of them sets `max_jobs` or any other tuning field.
#: Changing a row here is changing another engine's schedule -- outside the
#: D-4F-1 exception, and a decision of its own.
_EVERY_TEN_SECONDS = (("second", "{0, 10, 20, 30, 40, 50}"),)
OTHER_ENGINE_SCHEDULES: dict[str, list[tuple[str, tuple[tuple[str, str], ...]]]] = {
    "ai-model-orchestration-engine": [
        ("arq_run_outbox_dispatch", _EVERY_TEN_SECONDS),
        (
            "arq_run_health_checks",
            (("second", "set(range(0, 60, _SETTINGS.health_check_interval_seconds))"),),
        ),
        (
            "arq_run_benchmarks",
            (
                ("hour", "set(range(0, 24, _SETTINGS.benchmark_interval_hours))"),
                ("minute", "0"),
            ),
        ),
    ],
    "communication-engine": [("arq_run_outbox_dispatch", _EVERY_TEN_SECONDS)],
    "digital-twin-engine": [("arq_run_outbox_dispatch", _EVERY_TEN_SECONDS)],
    "executive-cognition-engine": [("arq_run_outbox_dispatch", _EVERY_TEN_SECONDS)],
    "knowledge-engine": [
        ("arq_run_outbox_dispatch", _EVERY_TEN_SECONDS),
        ("arq_run_embedding_pass", (("second", "{5, 35}"),)),
        (
            "arq_run_maintenance",
            (
                ("hour", "set(range(0, 24, _SETTINGS.maintenance_interval_hours))"),
                ("minute", "0"),
            ),
        ),
    ],
    "memory-engine": [
        ("arq_run_outbox_dispatch", _EVERY_TEN_SECONDS),
        ("arq_run_embedding_pass", (("second", "{5, 35}"),)),
        (
            "arq_run_consolidation",
            (
                ("hour", "set(range(0, 24, _SETTINGS.consolidation_interval_hours))"),
                ("minute", "0"),
            ),
        ),
        (
            "arq_run_short_term_expiry",
            (
                (
                    "minute",
                    "set(range(0, 60, _SETTINGS.short_term_expiry_check_interval_minutes))",
                ),
            ),
        ),
    ],
    "planning-engine": [("arq_run_outbox_dispatch", _EVERY_TEN_SECONDS)],
    "reasoning-engine": [("arq_run_outbox_dispatch", _EVERY_TEN_SECONDS)],
    "world-model-engine": [
        ("arq_run_outbox_dispatch", _EVERY_TEN_SECONDS),
        (
            "arq_run_scheduled_snapshots",
            (("hour", "set(range(0, 24, _SETTINGS.snapshot_interval_hours))"), ("minute", "0")),
        ),
        (
            "arq_run_predictions",
            (("hour", "set(range(0, 24, _SETTINGS.snapshot_interval_hours))"), ("minute", "5")),
        ),
    ],
}

#: `WorkerSettings` fields every worker sets for its identity and wiring, not
#: its scheduling or concurrency.
_WIRING_FIELDS = {
    "queue_name",
    "functions",
    "cron_jobs",
    "on_startup",
    "on_shutdown",
    "redis_settings",
}


def _worker_settings(path: Path) -> ast.ClassDef:
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "WorkerSettings":
            return node
    raise AssertionError(f"{path.relative_to(REPO_ROOT)} declares no WorkerSettings")


def _fields(cls: ast.ClassDef) -> dict[str, ast.expr]:
    fields: dict[str, ast.expr] = {}
    for node in cls.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    fields[target.id] = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.value is not None
        ):
            fields[node.target.id] = node.value
    return fields


def _cron_calls(cls: ast.ClassDef) -> list[ast.Call]:
    cron_jobs = _fields(cls).get("cron_jobs")
    assert isinstance(cron_jobs, ast.List), "cron_jobs is not a list literal; fix this parser"
    calls = [element for element in cron_jobs.elts if isinstance(element, ast.Call)]
    assert len(calls) == len(cron_jobs.elts), "cron_jobs holds a non-call entry; fix this parser"
    return calls


def _schedule(call: ast.Call) -> tuple[str, tuple[tuple[str, str], ...]]:
    coroutine = call.args[1]
    assert isinstance(coroutine, ast.Name), "unparsed cron coroutine; fix this parser"
    return coroutine.id, tuple((kw.arg or "**", ast.unparse(kw.value)) for kw in call.keywords)


def _other_worker_modules() -> dict[str, Path]:
    modules = {
        path.relative_to(SERVICES).parts[0]: path
        for path in sorted(SERVICES.glob("*/src/nova_*/workers/__init__.py"))
    }
    modules.pop("perception-engine")
    return modules


def _compose_files() -> list[Path]:
    files = sorted(COMPOSE_DIR.glob("docker-compose*.yml"))
    assert any(f.name == "docker-compose.local.yml" for f in files), "no base compose file found"
    return files


def _runs_perception_worker(service: dict) -> bool:  # type: ignore[type-arg]
    command = service.get("command") or []
    text = " ".join(command) if isinstance(command, list) else str(command)
    return PERCEPTION_WORKER_TARGET in text


# --- perception-engine: every second, serially -------------------------------


def test_perception_dispatches_its_outbox_every_second() -> None:
    calls = _cron_calls(_worker_settings(PERCEPTION_WORKER))
    assert [_schedule(call)[0] for call in calls] == ["arq_run_outbox_dispatch"], (
        "perception-engine's worker runs exactly one cron job, its outbox dispatch"
    )
    (call,) = calls
    keywords = {kw.arg: kw.value for kw in call.keywords}
    assert set(keywords) & _SCHEDULE_KEYWORDS == {"second"}, (
        "the dispatch is scheduled by `second=` alone; any other arq schedule keyword "
        f"narrows it. Found: {sorted(keywords)}"
    )
    second = eval(  # noqa: S307 -- a compiled AST expression, builtins removed
        compile(ast.Expression(keywords["second"]), str(PERCEPTION_WORKER), "eval"),
        {"__builtins__": {}},
        {"set": set, "range": range, "frozenset": frozenset},
    )
    assert set(second) == set(range(60)), (
        f"perception-engine's outbox must dispatch on every second of the minute "
        f"(D-4F-1's exception, TDD 4F.8 §30); it is scheduled on {sorted(second)}"
    )


def test_perception_dispatch_is_serial() -> None:
    max_jobs = _fields(_worker_settings(PERCEPTION_WORKER)).get("max_jobs")
    assert isinstance(max_jobs, ast.Constant) and max_jobs.value == 1, (
        "perception-engine's WorkerSettings must set `max_jobs = 1`. Without it arq "
        "starts the next one-second tick while a slow run is still publishing, and "
        "both runs can publish the same unclaimed outbox row (TDD 4F.8 §30.2)."
    )


# --- one worker process, structurally ----------------------------------------


def test_compose_defines_exactly_one_perception_worker() -> None:
    owners = [
        (path.name, name)
        for path in _compose_files()
        for name, service in (yaml.safe_load(path.read_text()).get("services") or {}).items()
        if _runs_perception_worker(service)
    ]
    assert {name for _, name in owners} == {PERCEPTION_WORKER_SERVICE}, (
        f"only `{PERCEPTION_WORKER_SERVICE}` may run {PERCEPTION_WORKER_TARGET}; "
        f"found {owners}. A second service running it is a second replica, and the "
        "shared outbox claims no row (TDD 4F.8 §30.2)."
    )
    base = yaml.safe_load((COMPOSE_DIR / "docker-compose.local.yml").read_text())["services"]
    assert _runs_perception_worker(base[PERCEPTION_WORKER_SERVICE])


@pytest.mark.parametrize("path", _compose_files(), ids=lambda p: p.name)
def test_no_compose_file_replicates_the_perception_worker(path: Path) -> None:
    services = yaml.safe_load(path.read_text()).get("services") or {}
    service = services.get(PERCEPTION_WORKER_SERVICE) or {}
    assert "scale" not in service, f"{path.name} scales {PERCEPTION_WORKER_SERVICE}"
    replicas = (service.get("deploy") or {}).get("replicas")
    assert replicas in (None, 1), (
        f"{path.name} gives {PERCEPTION_WORKER_SERVICE} {replicas} replicas"
    )


def test_no_workflow_scales_a_compose_service() -> None:
    offenders = [
        f"{path.name}:{number}"
        for path in sorted(WORKFLOWS.glob("*.yml"))
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if "--scale" in line
    ]
    assert not offenders, (
        f"`docker compose --scale` appears at {offenders}; scaling "
        f"{PERCEPTION_WORKER_SERVICE} beyond one replica is outside D-4F-1's exception"
    )


def test_the_perception_api_process_runs_no_worker() -> None:
    """The API container's own command is uvicorn, so the worker service above is
    the only process anywhere that runs this engine's `WorkerSettings`."""
    lines = PERCEPTION_DOCKERFILE.read_text().splitlines()
    cmd = [line for line in lines if line.startswith("CMD")]
    assert len(cmd) == 1 and "uvicorn" in cmd[0] and "arq" not in cmd[0], cmd
    base = yaml.safe_load((COMPOSE_DIR / "docker-compose.local.yml").read_text())["services"]
    assert "command" not in base["perception-engine"], (
        "perception-engine's API service overrides its image command; check it does not "
        "start a second dispatcher"
    )


# --- every other engine: unchanged --------------------------------------------


def test_the_snapshot_covers_every_other_worker() -> None:
    assert set(_other_worker_modules()) == set(OTHER_ENGINE_SCHEDULES), (
        "a worker was added or removed; add its schedule to OTHER_ENGINE_SCHEDULES "
        "deliberately rather than leave it unpinned"
    )


@pytest.mark.parametrize("engine", sorted(OTHER_ENGINE_SCHEDULES))
def test_other_engines_schedules_are_unchanged(engine: str) -> None:
    settings = _worker_settings(_other_worker_modules()[engine])
    assert [_schedule(call) for call in _cron_calls(settings)] == OTHER_ENGINE_SCHEDULES[engine], (
        f"{engine}'s cron schedule changed. D-4F-1's exception covers perception-engine's "
        "dispatch interval only (TDD 4F.8 §30.1)."
    )
    tuning = set(_fields(settings)) - _WIRING_FIELDS
    assert not tuning, (
        f"{engine}'s WorkerSettings now sets {sorted(tuning)}; at 1ccce7a it set none"
    )
