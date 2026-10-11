"""Phase 4F.8 -- **AC-7 and AC-8 against the deployed stack** (TDD 4F.8 D5, D6;
§29.1 A-4F8-4, A-4F8-6, A-4F8-7; §29.4 the acceptance plan; §30, §31).

Three phases, each its own step in `pr-checks.yml`'s `e2e` job, run after 4F.P's
P8 proof against the same stack:

``ac8`` -- **AC-8** (D6; E-8 ... E-13, E-17)
    The same T1 category, from the **production trigger**, at Level 1 and then
    at Level 2. Between the two only the level changes, and the configuration
    is read back by SQL before each run (E-12). Level 1 proposes and executes
    nothing (E-8); Level 2 executes for real, and `action-engine`'s own row says
    `completed` (E-9). Then the identity row is removed, and stage 3 denies
    (E-17).

``ac7-latency`` -- **AC-7's detection and latency** (D5; E-1 ... E-4)
    At Level 0, so samples add no proposal and execute nothing (§29.4.3). The
    known project is made known through `memory-engine`'s own production route.
    Then **at least 10 samples**, each on a never-observed path in the known
    project's declared folder. Each is measured from the file's OS modification
    time to the first successful read of its World Model object through
    `world-model-engine`'s own REST, polled at 50 ms. **Every sample is
    reported. AC-7's latency passes only if every one is at most 5.0 s.** No
    sample is retried, re-run or discarded.

``ac7-revocation`` -- **AC-7's revocation** (D1, D2; E-5, E-6, E-18)
    After P-AC7-1 has made the genuine revocation (`chmod g-rx` on the
    workspace, by its owner) in the browser run, it checks:
    - the companion reported it, and `perception-engine` and
      `cognitive-state-engine` both hold `failed` (E-5);
    - a write the OS accepts produces nothing for 25 s (E-6);
    - only the companion lost access, and `capability-engine` did not (E-18).

**What this harness never does** (`tools/tests/test_e2e_acceptance.py` checks
its AST):
- it imports no engine;
- it publishes, requests or replies to nothing on the bus, and calls no
  `promote_thought` or `decide` (E-13, N-4);
- every SQL statement is a `SELECT`;
- it calls only the configuration and observation routes named in
  `ROUTES_USED`;
- it never references the dispatch schedule, retries a sample, or uses a fake
  clock (N-1, N-2, N-3).

Between a write and its observation it makes no request into the chain (E-4).

Usage (the e2e job sets every variable; the defaults are compose's host ports):

    uv run python tools/e2e_acceptance.py ac8 | ac7-latency | ac7-revocation

Exit status 0 only if every check passed. The evidence is printed as JSON.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID, uuid4, uuid5

import asyncpg
import httpx
from e2e_real_execution import (
    OUTCOME_FOR_STATUS,
    PRIMARY_USER,
    T1,
    TRIGGER_NAMESPACE,
    Config,
    Report,
    Run,
    Stores,
    Tap,
    check_executed,
    configure,
    invocation_count,
    put_identity_policy,
    real_run,
    wait_for,
    wait_ready,
)

ROUTES_USED = (
    "/internal/readiness",
    "/internal/metrics/",
    "/v1/autonomy/level",
    "/v1/autonomy/permissions",
    "/v1/autonomy/policies",
    "/v1/action/identity-confidence-policy",
    "/v1/memories",
    "/v1/world/objects/",
    "/v1/perception/sensors",
    "/v1/cognitive-state/sensors",
)
"""Every route this harness calls. Configuration goes through production routes;
everything else is a read. `/v1/memories` is `memory-engine`'s own production
write route, used once to make the known project known (A-4F8-2 (a)).
`/v1/autonomy/permissions` and `/v1/autonomy/policies` are reached through
P8's `configure`."""

LATENCY_BUDGET_SECONDS = 5.0
"""AC-7's ratified budget (TDD 4F §4.1, D-4F-1). Never lowered or widened."""

MINIMUM_SAMPLES = 10
"""A-4F8-6: at least ten independent samples."""

SAMPLE_DEADLINE_SECONDS = 30.0
"""A-4F8-6: a sample is observed for 30 s, so the true figure is always
reported. It is a deadline for reporting, not the criterion."""

POLL_SECONDS = 0.05
"""A-4F8-6: `world-model-engine`'s object read is polled at <= 100 ms. Polling
is observation: nothing is re-sent, re-written or re-run."""

WATCH_SECONDS = 25.0
"""E-6: how long a write after the revocation is watched for, and must produce
nothing. TDD 4F.8 §16 E-6's figure."""

MTIME_GRANULARITY_SECONDS = 0.010
"""The kernel stamps a file's mtime from a coarse clock, which can trail the
fine clock the harness reads by up to a scheduler tick. So the OS time may
precede the harness's `before` by a few milliseconds. This is the allowance
for that, and nothing more. It never shortens a sample: the interval starts at
the OS time, the earlier of the two. *(F-4F8-18: that is the file's creation
time.)*"""

_HASH_PREFIX = "ws"
"""`perception-engine`'s `object_id_for_path` prefix, restated, not imported,
and drift-guarded in `tools/tests/test_e2e_acceptance.py`."""

_RANDOM = random.SystemRandom()


def object_id_for_path(path: str) -> str:
    """`perception-engine`'s handle for a workspace path (TDD 4F §20.2), restated.

    The companion reports the path as it sees it, inside its container, so the
    argument is the `/workspace/...` path, not the runner's."""
    normalized = path.strip()
    digest = hashlib.sha256(PurePosixPath(normalized).as_posix().encode("utf-8")).hexdigest()
    return f"{_HASH_PREFIX}-{digest}"


@dataclass(frozen=True)
class AcceptanceConfig:
    base: Config
    run_id: str
    world_model_url: str
    memory_url: str
    known_project_id: UUID | None
    known_folder: str | None
    samples: int
    output_file: Path | None
    compose_files: tuple[str, ...]

    @classmethod
    def from_env(cls) -> AcceptanceConfig:
        env = os.environ.get
        project = env("NOVA_ACCEPTANCE_KNOWN_PROJECT_ID")
        output = env("GITHUB_OUTPUT")
        return cls(
            base=Config.from_env(),
            run_id=env("NOVA_ACCEPTANCE_RUN_ID") or uuid4().hex[:12],
            world_model_url=env("NOVA_E2E_WORLD_MODEL_URL", "http://localhost:8003"),
            memory_url=env("NOVA_E2E_MEMORY_URL", "http://localhost:8001"),
            known_project_id=UUID(project) if project else None,
            known_folder=env("NOVA_ACCEPTANCE_KNOWN_FOLDER"),
            samples=int(env("NOVA_ACCEPTANCE_AC7_SAMPLES", str(MINIMUM_SAMPLES))),
            output_file=Path(output) if output else None,
            # The base file only: `exec` and `logs` act on the running
            # containers, whose user the acceptance override already set.
            compose_files=("infra/docker/docker-compose.local.yml",),
        )

    def emit(self, **values: str) -> None:
        """Hand values to later steps as step outputs, and print them."""
        for key, value in values.items():
            print(f"output {key}={value}", flush=True)
        if self.output_file is not None:
            with self.output_file.open("a") as handle:
                for key, value in values.items():
                    handle.write(f"{key}={value}\n")


# --- independent SQL, SELECT only ----------------------------------------------------


class AcceptanceStores(Stores):
    """P8's reads, plus the ones AC-7 and AC-8 need. `SELECT` only."""

    def __init__(self, connection: asyncpg.Connection) -> None:
        super().__init__(connection)
        self._connection = connection

    async def level(self) -> list[dict[str, Any]]:
        rows = await self._connection.fetch(
            "SELECT user_id, level FROM autonomy.autonomy_level ORDER BY user_id"
        )
        return [dict(r) for r in rows]

    async def configuration(self) -> dict[str, Any]:
        """Everything AC-8's two runs must share, except the level (E-12)."""
        policies = await self._connection.fetch(
            "SELECT id, name, effect, match_category, match_min_risk, match_capability_class, "
            "enabled FROM autonomy.policy WHERE user_id = $1 ORDER BY id",
            PRIMARY_USER,
        )
        grants = await self._connection.fetch(
            "SELECT category, max_risk, requires_approval_above FROM autonomy.permission_grant "
            "WHERE user_id = $1 ORDER BY category",
            PRIMARY_USER,
        )
        return {
            "policies": [{k: str(v) for k, v in dict(r).items()} for r in policies],
            "grants": [dict(r) for r in grants],
            "identity_policy": [
                {"user_id": str(p["user_id"]), "thresholds": p["minimum_confidence_by_risk"]}
                for p in await self.identity_policy()
            ],
        }

    async def decision_rows(self, subject_id: UUID) -> list[dict[str, Any]]:
        rows = await self._connection.fetch(
            "SELECT id, action_id, suggestion_id, autonomy_level, risk, confidence, "
            "policy_checks, outcome, reason FROM autonomy.decision_log WHERE action_id = $1",
            subject_id,
        )
        return [
            {
                **dict(r),
                "policy_checks": json.loads(r["policy_checks"])
                if isinstance(r["policy_checks"], str)
                else r["policy_checks"],
            }
            for r in rows
        ]

    async def suggestion_rows(self, subject_id: UUID) -> list[dict[str, Any]]:
        rows = await self._connection.fetch(
            "SELECT id, category, risk, title, status FROM autonomy.suggestion WHERE id = $1",
            subject_id,
        )
        return [dict(r) for r in rows]

    async def outbox_for(self, object_id: str) -> list[dict[str, Any]]:
        rows = await self._connection.fetch(
            "SELECT id, payload, correlation_id, created_at, dispatched_at "
            "FROM perception.outbox_event WHERE subject = 'perception.workspace.observed' "
            "AND payload->>'object_id' = $1 ORDER BY created_at, id",
            object_id,
        )
        return [{**dict(r), "payload": _json(r["payload"])} for r in rows]

    async def world_history(self, object_id: str) -> list[dict[str, Any]]:
        rows = await self._connection.fetch(
            "SELECT object_id, new_state, user_id, correlation_id, changed_at "
            "FROM world_model.object_state_history WHERE object_id = $1 ORDER BY changed_at, id",
            object_id,
        )
        return [dict(r) for r in rows]

    async def known_project(self, project_id: UUID) -> list[dict[str, Any]]:
        rows = await self._connection.fetch(
            "SELECT project_id, first_observed_at, source_event_id "
            "FROM perception.known_project WHERE project_id = $1",
            project_id,
        )
        return [dict(r) for r in rows]

    async def health_reports(self, sensor_id: str) -> list[dict[str, Any]]:
        rows = await self._connection.fetch(
            "SELECT id, payload, dispatched_at, created_at FROM perception.outbox_event "
            "WHERE subject = 'perception.sensor.health_changed' "
            "AND payload->>'sensor_id' = $1 ORDER BY created_at, id",
            sensor_id,
        )
        return [{**dict(r), "payload": _json(r["payload"])} for r in rows]

    async def sensor_state(self, sensor_id: str) -> list[dict[str, Any]]:
        rows = await self._connection.fetch(
            "SELECT sensor_id, sensor_type, state, reported_at, last_event_id "
            "FROM cognitive_state.sensor_state WHERE sensor_id = $1",
            sensor_id,
        )
        return [dict(r) for r in rows]


def _for_action(subject_id: UUID) -> Any:
    """A tap filter for `action.execute` requests carrying `subject_id`."""
    return lambda seen: seen.payload.get("action_id") == str(subject_id)


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, UUID | datetime):
        return str(value)
    return value


async def set_level(http: httpx.AsyncClient, cfg: Config, level: int, report: Report) -> None:
    response = await http.put(f"{cfg.autonomy_url}/v1/autonomy/level", json={"level": level})
    report.check(
        f"PUT /v1/autonomy/level -> Level {level}", response.status_code == 200, response.text
    )


def assert_never_observed(
    label: str, object_id: str, outbox: list[dict[str, Any]], world: int, report: Report
) -> None:
    """FP-14 (§29.4.4): before the write, by SELECT and a read only."""
    report.check(
        f"[{label}] FP-14. never observed before: no outbox row, no World Model object",
        not outbox and world == 404,
        {"object_id": object_id, "outbox_rows": len(outbox), "world_status": world},
    )


async def world_status(http: httpx.AsyncClient, url: str, object_id: str) -> int:
    response = await http.get(f"{url}/v1/world/objects/{object_id}")
    return response.status_code


# --- AC-8 (D6) -------------------------------------------------------------------------


async def ac8(acfg: AcceptanceConfig) -> int:
    cfg, report, run_id = acfg.base, Report(), acfg.run_id
    evidence: dict[str, Any] = {"phase": "ac8", "run_id": run_id}
    tap = Tap()
    observer = await tap.start(cfg.nats_url)
    database = await asyncpg.connect(cfg.postgres_dsn)
    stores = AcceptanceStores(database)
    async with httpx.AsyncClient(timeout=15.0) as http:
        try:
            await wait_ready(http, cfg, report)
            # P8 left this configuration; it is re-applied through the same
            # production routes, idempotently, so AC-8 does not depend on P8.
            evidence["configuration"] = await configure(http, cfg, report)

            # --- Level 1 -------------------------------------------------------------
            await set_level(http, cfg, 1, report)
            before_1 = await stores.configuration()
            level_1 = await stores.level()
            run_1 = await _ac8_run("level1", acfg, http, stores, tap, report)

            # --- Level 2: only the level changes ---------------------------------------
            await set_level(http, cfg, 2, report)
            before_2 = await stores.configuration()
            level_2 = await stores.level()
            report.check(
                "E-12. between the two runs only the level changed: policies, grants and the "
                "identity row are identical by SQL",
                before_1 == before_2
                and [r["level"] for r in level_1] == [1]
                and [r["level"] for r in level_2] == [2],
                {"before_level1": before_1, "before_level2": before_2},
            )
            invocations_before = await invocation_count(http, cfg)
            run_2 = await _ac8_run("level2", acfg, http, stores, tap, report)
            evidence["level2_execution"] = check_executed(
                run_2,
                sandbox_root=cfg.sandbox_root,
                report=report,
                tap=tap,
                history=await stores.history(run_2.subject_id),
                capability=await stores.filesystem_capability() or {},
                invocations_delta=await invocation_count(http, cfg) - invocations_before,
                identity_policy=await stores.identity_policy(),
                decisions=await stores.decisions(run_2.subject_id),
                actions=await stores.actions(run_2.subject_id),
                thoughts=await stores.thoughts(run_2.label),
            )
            evidence["level1"] = await _check_level1(run_1, stores, tap, report)
            await _check_same_path(run_1, run_2, stores, report)

            # --- E-17: fail-closed at stage 3, without the identity row ------------------
            evidence["denied"] = await _ac8_denied(acfg, http, stores, tap, report)

            acfg.emit(
                ac8_level1_label=run_1.label,
                ac8_level1_subject_id=str(run_1.subject_id),
                ac8_level2_label=run_2.label,
                ac8_level2_subject_id=str(run_2.subject_id),
            )
        except TimeoutError as exc:
            report.check(f"the chain completed within the deadline: {exc}", False, str(exc))
        except Exception as exc:
            _unexpected(exc, report)
        finally:
            await observer.drain()
            await database.close()
    return _finish("AC-8", evidence, report)


async def _ac8_run(
    tag: str,
    acfg: AcceptanceConfig,
    http: httpx.AsyncClient,
    stores: AcceptanceStores,
    tap: Tap,
    report: Report,
) -> Run:
    """One AC-8 run from a never-observed path. `real_run` (P8's) writes the
    file and follows it to the recorded decision and its reply on the bus."""
    label = f"ac8-{acfg.run_id}-{tag}.txt"
    object_id = object_id_for_path(f"{acfg.base.sandbox_root}/{label}")
    assert_never_observed(
        tag,
        object_id,
        await stores.outbox_for(object_id),
        await world_status(http, acfg.world_model_url, object_id),
        report,
    )
    run = await real_run(
        tag,
        run_id=acfg.run_id,
        cfg=acfg.base,
        stores=stores,
        tap=tap,
        content=f"4F.8 acceptance probe {label}\n",
        prefix="ac8",
    )
    report.check(
        f"[{tag}] E-13. the decision's subject is uuid5 of the trigger cognitive-state-engine "
        "published",
        run.trigger.envelope.get("source_engine") == "cognitive-state-engine"
        and run.subject_id == uuid5(TRIGGER_NAMESPACE, str(run.trigger.envelope["event_id"])),
        run.trigger.envelope,
    )
    report.check(
        f"[{tag}] the observed object is this run's own path (attribution, §29.4.2)",
        run.observation["payload"].get("object_id") == object_id,
        {"expected": object_id, "observed": run.observation["payload"].get("object_id")},
    )
    return run


async def _check_level1(
    run: Run, stores: AcceptanceStores, tap: Tap, report: Report
) -> dict[str, Any]:
    decision = run.decision
    suggestions = await stores.suggestion_rows(run.subject_id)
    executes = tap.requests(
        "action.execute", lambda s: s.payload.get("action_id") == str(run.subject_id)
    )
    report.check(
        "[level1] E-8. Level 1 proposed: PROPOSE, with exactly one suggestion, still proposed",
        decision["outcome"] == "propose"
        and decision["autonomy_level"] == 1
        and decision["suggestion_id"] == run.subject_id
        and [s["status"] for s in suggestions] == ["proposed"],
        {"decision": _plain(decision), "suggestions": _plain(suggestions)},
    )
    report.check(
        "[level1] E-8. its title names the run's own file (the browser finds it by that)",
        len(suggestions) == 1 and run.label in suggestions[0]["title"],
        _plain(suggestions),
    )
    report.check(
        "[level1] E-8. nothing executed: no action.execute, no action row",
        not executes and not await stores.actions(run.subject_id),
        [s.envelope for s in executes],
    )
    return {
        "file": run.label,
        "subject_id": str(run.subject_id),
        "trigger": run.trigger.envelope,
        "decision_row": _plain(decision),
        "suggestion": _plain(suggestions),
    }


async def _check_same_path(
    run_1: Run, run_2: Run, stores: AcceptanceStores, report: Report
) -> None:
    """E-10 and E-11: the same category, through the same gates, at low risk twice.

    *(F-4F8-19.)* A missing row is a failed check, never an unpacking error:
    a Level-2 run that executes nothing must still report every check."""
    rows_1 = await stores.decision_rows(run_1.subject_id)
    rows_2 = await stores.decision_rows(run_2.subject_id)
    actions = await stores.actions(run_2.subject_id)
    report.check(
        "E-10. each run recorded exactly one decision, and the Level-2 run exactly one action",
        len(rows_1) == 1 and len(rows_2) == 1 and len(actions) == 1,
        {"level1_decisions": len(rows_1), "level2_decisions": len(rows_2), "actions": len(actions)},
    )
    row_1 = rows_1[0] if rows_1 else {}
    row_2 = rows_2[0] if rows_2 else {}
    action = actions[0] if actions else {}
    report.check(
        "E-10. the two decisions passed the same gates: identical policy_checks, risk and "
        "confidence; only the outcome and the level differ",
        bool(row_1)
        and bool(row_2)
        and row_1["policy_checks"] == row_2["policy_checks"]
        and row_1["risk"] == row_2["risk"]
        and row_1["confidence"] == row_2["confidence"]
        and (row_1["outcome"], row_1["autonomy_level"]) == ("propose", 1)
        and (row_2["outcome"], row_2["autonomy_level"]) == ("execute", 2),
        {"level1": _plain(row_1), "level2": _plain(row_2)},
    )
    triggers = [run_1.trigger.payload, run_2.trigger.payload]
    report.check(
        "E-10. both triggers carry the same category, action type and authored risk (T1)",
        all(
            t.get("category") == T1["category"]
            and t.get("action_type") == T1["action_type"]
            and t.get("risk") == T1["risk"]
            for t in triggers
        ),
        triggers,
    )
    report.check(
        "E-11. low risk twice: authored low, and action-engine classified it negligible",
        run_2.trigger.payload.get("risk") == "low" and action.get("risk") == "negligible",
        {"authored": run_2.trigger.payload.get("risk"), "action_engine": action.get("risk")},
    )
    report.check(
        "[level2] P-AC8-1's premise: the Level-2 run produced no suggestion",
        not await stores.suggestion_rows(run_2.subject_id),
        str(run_2.subject_id),
    )


async def _ac8_denied(
    acfg: AcceptanceConfig,
    http: httpx.AsyncClient,
    stores: AcceptanceStores,
    tap: Tap,
    report: Report,
) -> dict[str, Any]:
    cfg = acfg.base
    removed = await http.delete(f"{cfg.action_url}/v1/action/identity-confidence-policy")
    report.check(
        "E-17. DELETE /v1/action/identity-confidence-policy (the threshold returns to 1.0)",
        removed.status_code in (204, 404),
        removed.status_code,
    )
    try:
        before = await invocation_count(http, cfg)
        run = await _ac8_run("denied", acfg, http, stores, tap, report)
        delta = await invocation_count(http, cfg) - before
    finally:
        restored = await put_identity_policy(http, cfg)
        report.check(
            "E-17. the identity row is restored afterwards",
            restored.status_code == 200,
            restored.text,
        )
    action = (await stores.actions(run.subject_id) or [{}])[0]
    report.check(
        "E-17. without the row, the real action-engine denied at stage 3; PROPOSE, never "
        "EXECUTE; nothing invoked",
        action.get("status") == "denied"
        and run.decision["outcome"] == OUTCOME_FOR_STATUS["denied"] == "propose"
        and delta == 0.0,
        {"action": _plain(action), "decision": _plain(run.decision), "invocations": delta},
    )
    return {"file": run.label, "subject_id": str(run.subject_id)}


# --- AC-7: detection and latency (D5) -----------------------------------------------------


@dataclass
class Sample:
    index: int
    file: str
    object_id: str
    pause_before_s: float
    harness_before: float
    os_created: float
    os_written: float
    first_seen: float | None

    @property
    def elapsed(self) -> float | None:
        """From the file's creation, the earlier of its two OS times (F-4F8-18)."""
        return None if self.first_seen is None else self.first_seen - self.os_created


async def measure_sample(
    index: int,
    folder: Path,
    container_folder: str,
    run_id: str,
    world_model_url: str,
    http: httpx.AsyncClient,
) -> Sample:
    """One AC-7 sample: a write, then reads only, until the object exists.

    **No request into the chain is made here** (E-4): a file write, two
    `os.fstat`s, and `GET`s of `world-model-engine`'s object read. It is called
    once per sample, and its result is reported whatever it is (N-2).

    *(F-4F8-18, TDD 4F.8 §36.)* Creating the file and writing it are two
    syscalls, and each may stamp its own mtime. Observed here, the two differ
    when the clock moves between them, or when the file's times are queried
    between them. Such a query may be the companion's own stat on the create
    event, or this function's `fstat`. The companion may therefore report
    either. Both are recorded, and the interval starts at the creation, the
    earlier of the two. That never shortens a sample. `O_EXCL` also makes the
    OS refuse a path that already exists (FP-14)."""
    name = f"ac7-{run_id}-{index}.txt"
    object_id = object_id_for_path(f"{container_folder}/{name}")
    # A pause drawn from the OS's entropy, so a write's phase relative to any
    # periodic process is uniform. It reads no clock and no schedule (N-1).
    pause = _RANDOM.uniform(0.0, 2.0)
    await asyncio.sleep(pause)

    harness_before = time.time()
    fd = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        os_created = os.fstat(fd).st_mtime_ns / 1e9
        os.write(fd, f"4F.8 AC-7 sample {run_id} {index}\n".encode())
        os_written = os.fstat(fd).st_mtime_ns / 1e9
    finally:
        os.close(fd)

    first_seen: float | None = None
    deadline = time.monotonic() + SAMPLE_DEADLINE_SECONDS
    while time.monotonic() < deadline:
        response = await http.get(f"{world_model_url}/v1/world/objects/{object_id}")
        if response.status_code == 200:
            first_seen = time.time()
            break
        await asyncio.sleep(POLL_SECONDS)
    return Sample(index, name, object_id, pause, harness_before, os_created, os_written, first_seen)


async def ac7_latency(acfg: AcceptanceConfig) -> int:
    cfg, report, run_id = acfg.base, Report(), acfg.run_id
    evidence: dict[str, Any] = {"phase": "ac7-latency", "run_id": run_id}
    if acfg.known_project_id is None or not acfg.known_folder:
        raise SystemExit(
            "NOVA_ACCEPTANCE_KNOWN_PROJECT_ID and NOVA_ACCEPTANCE_KNOWN_FOLDER are required: "
            "the project folder the operator declared in NOVA_PROJECT_FOLDER_BINDINGS"
        )
    if acfg.samples < MINIMUM_SAMPLES:
        raise SystemExit(f"A-4F8-6 requires at least {MINIMUM_SAMPLES} samples")
    project_id, folder = acfg.known_project_id, cfg.workspace / acfg.known_folder
    container_folder = f"{cfg.sandbox_root}/{acfg.known_folder}"
    tap = Tap()
    observer = await tap.start(cfg.nats_url)
    database = await asyncpg.connect(cfg.postgres_dsn)
    stores = AcceptanceStores(database)
    async with httpx.AsyncClient(timeout=15.0) as http:
        try:
            await wait_ready(http, cfg, report)
            sensors = (
                await http.get(f"{cfg.cognitive_state_url}/v1/cognitive-state/sensors")
            ).json()
            report.check(
                "readiness (§29.4.1, K-1). cognitive-state-engine holds companion-filesystem as "
                "running, so it is subscribed",
                {"sensor_id": "companion-filesystem", "state": "running"}.items()
                <= {
                    k: v
                    for s in sensors.get("sensors", [])
                    if s.get("sensor_id") == "companion-filesystem"
                    for k, v in s.items()
                }.items(),
                sensors,
            )
            await set_level(http, cfg, 0, report)
            report.check(
                "§29.4.3. the samples run at Level 0",
                [r["level"] for r in await stores.level()] == [0],
            )
            report.check(
                "the declared project folder exists in the workspace", folder.is_dir(), str(folder)
            )

            # --- the known project, made known by memory-engine's own route -----------
            created = await http.post(
                f"{acfg.memory_url}/v1/memories",
                json={
                    "user_id": str(PRIMARY_USER),
                    "memory_type": "semantic",
                    "content": f"4F.8 acceptance: the known project of run {run_id}",
                    "project_id": str(project_id),
                },
            )
            report.check(
                "POST /v1/memories (memory-engine's production route) with the known project",
                created.status_code == 201,
                created.text,
            )

            async def _known() -> list[dict[str, Any]] | None:
                return await stores.known_project(project_id) or None

            known = await wait_for(
                _known, "the project learned from memory.long_term.created", cfg.deadline_seconds
            )
            report.check(
                "A-4F8-2. perception-engine learned the project from memory.long_term.created",
                len(known) == 1,
                _plain(known),
            )

            # --- E-2's miss: a path under no declared folder ---------------------------
            miss = f"ac7-{run_id}-miss.txt"
            miss_id = object_id_for_path(f"{cfg.sandbox_root}/{miss}")
            assert_never_observed(
                "miss",
                miss_id,
                await stores.outbox_for(miss_id),
                await world_status(http, acfg.world_model_url, miss_id),
                report,
            )
            (cfg.workspace / miss).write_text(f"4F.8 E-2 miss {run_id}\n")

            async def _miss_row() -> dict[str, Any] | None:
                rows = await stores.outbox_for(miss_id)
                return rows[0] if rows else None

            miss_row = await wait_for(_miss_row, "the miss's observation", cfg.deadline_seconds)
            report.check(
                "E-2 (miss, N-13). a path under no declared folder carries project_id None",
                miss_row["payload"].get("project_id") is None,
                miss_row["payload"],
            )

            # --- the samples --------------------------------------------------------------
            samples: list[Sample] = []
            for index in range(1, acfg.samples + 1):
                object_id = object_id_for_path(f"{container_folder}/ac7-{run_id}-{index}.txt")
                assert_never_observed(
                    f"sample {index}",
                    object_id,
                    await stores.outbox_for(object_id),
                    await world_status(http, acfg.world_model_url, object_id),
                    report,
                )
                sample = await measure_sample(
                    index, folder, container_folder, run_id, acfg.world_model_url, http
                )
                samples.append(sample)
                shown = (
                    "not observed within 30 s"
                    if sample.elapsed is None
                    else f"{sample.elapsed:.3f} s"
                )
                print(f"AC-7 sample {index}: {shown}  ({sample.file})", flush=True)

            # E-3 first, from the figures alone, so the verdict and every figure
            # are recorded even if a later attribution check cannot complete.
            elapsed = [s.elapsed for s in samples]
            measured = [e for e in elapsed if e is not None]
            met = (
                len(samples) >= MINIMUM_SAMPLES
                and len(measured) == len(samples)
                and all(e <= LATENCY_BUDGET_SECONDS for e in measured)
            )
            evidence["latency"] = {
                "samples": len(samples),
                "elapsed_seconds": elapsed,
                "max_seconds": max(measured) if measured else None,
                "budget_seconds": LATENCY_BUDGET_SECONDS,
                "every_sample_within_budget": met,
            }
            report.check(
                f"E-3. AC-7's latency: every one of {len(samples)} samples at or below "
                f"{LATENCY_BUDGET_SECONDS} s",
                met,
                evidence["latency"],
            )
            evidence["samples"] = await _check_samples(
                samples, project_id, stores, tap, cfg, report
            )
        except TimeoutError as exc:
            report.check(f"the chain completed within the deadline: {exc}", False, str(exc))
        except Exception as exc:
            _unexpected(exc, report)
        finally:
            await observer.drain()
            await database.close()
    return _finish("AC-7 latency", evidence, report)


async def _check_samples(
    samples: list[Sample],
    project_id: UUID,
    stores: AcceptanceStores,
    tap: Tap,
    cfg: Config,
    report: Report,
) -> list[dict[str, Any]]:
    """E-1, E-2 and §29.4.3's attribution, per sample, after all are measured."""
    table = []
    for sample in samples:
        rows = await stores.outbox_for(sample.object_id)
        history = await stores.world_history(sample.object_id)
        row = rows[0] if rows else {}
        payload = row.get("payload") or {}
        observed_at = payload.get("observed_at")
        reported = datetime.fromisoformat(observed_at).timestamp() if observed_at else None
        tag = f"sample {sample.index}"
        report.check(
            f"[{tag}] E-1. one observation, from the companion's sensor, of this path",
            len(rows) == 1 and payload.get("sensor_id") == "companion-filesystem",
            [_plain(r) for r in rows],
        )
        report.check(
            f"[{tag}] N-3. observed_at is one of the file's own OS times, and not before the write",
            reported is not None
            and min(abs(reported - sample.os_created), abs(reported - sample.os_written)) < 1e-5
            and sample.os_created >= sample.harness_before - MTIME_GRANULARITY_SECONDS,
            {
                "observed_at": observed_at,
                "os_created": sample.os_created,
                "os_written": sample.os_written,
                "harness_before": sample.harness_before,
            },
        )
        report.check(
            f"[{tag}] E-2 (match). the observation carries the known project's id",
            payload.get("project_id") == str(project_id),
            payload,
        )
        report.check(
            f"[{tag}] E-1. the World Model's transition carries that observation's "
            "correlation_id (provenance)",
            bool(history) and history[0]["correlation_id"] == row.get("correlation_id"),
            {
                "history": [_plain(h) for h in history],
                "outbox_correlation": str(row.get("correlation_id")),
            },
        )

        async def _decided(sample: Sample = sample) -> dict[str, Any] | None:
            thoughts = await stores.thoughts(sample.file)
            if not thoughts:
                return None
            triggers = tap.requests(
                "autonomy.decision.requested",
                lambda s: s.payload.get("thought_id") == str(thoughts[0]["thought_id"]),
            )
            if not triggers:
                return None
            subject_id = uuid5(TRIGGER_NAMESPACE, str(triggers[0].envelope["event_id"]))
            decisions = await stores.decision_rows(subject_id)
            return {"subject_id": subject_id, "decisions": decisions} if decisions else None

        decided = await wait_for(
            _decided, f"{sample.file}: its Level-0 decision", cfg.deadline_seconds
        )
        subject_id = decided["subject_id"]
        report.check(
            f"[{tag}] §29.4.3. Level 0 observed only: one observe_only row, no suggestion, no "
            "action.execute, no action row",
            [d["outcome"] for d in decided["decisions"]] == ["observe_only"]
            and not await stores.suggestion_rows(subject_id)
            and not tap.requests("action.execute", _for_action(subject_id))
            and not await stores.actions(subject_id),
            _plain(decided),
        )
        table.append(
            {
                "sample": sample.index,
                "file": sample.file,
                "object_id": sample.object_id,
                "pause_before_s": round(sample.pause_before_s, 3),
                "os_created": datetime.fromtimestamp(sample.os_created, UTC).isoformat(),
                "os_written": datetime.fromtimestamp(sample.os_written, UTC).isoformat(),
                "elapsed_s": None if sample.elapsed is None else round(sample.elapsed, 3),
                "subject_id": str(subject_id),
            }
        )
    return table


# --- AC-7: the revocation (D1, D2; E-5, E-6, E-18) ------------------------------------


def compose(acfg: AcceptanceConfig, *args: str) -> subprocess.CompletedProcess[str]:
    """A read-only inspection of the running containers (E-18), or their logs."""
    files = [part for f in acfg.compose_files for part in ("-f", f)]
    return subprocess.run(
        ["docker", "compose", *files, *args], capture_output=True, text=True, check=False
    )


def companion_log_messages(acfg: AcceptanceConfig) -> list[dict[str, Any]]:
    lines = compose(acfg, "logs", "--no-color", "--no-log-prefix", "nova-companion").stdout
    messages = []
    for line in lines.splitlines():
        try:
            parsed = json.loads(line[line.index("{") :]) if "{" in line else None
        except ValueError:
            continue
        if isinstance(parsed, dict):
            messages.append(parsed)
    return messages


async def ac7_revocation(acfg: AcceptanceConfig) -> int:
    cfg, report, run_id = acfg.base, Report(), acfg.run_id
    evidence: dict[str, Any] = {"phase": "ac7-revocation", "run_id": run_id}
    database = await asyncpg.connect(cfg.postgres_dsn)
    stores = AcceptanceStores(database)
    async with httpx.AsyncClient(timeout=15.0) as http:
        try:
            mode = cfg.workspace.stat().st_mode & 0o777
            report.check(
                "the revocation is in place: the workspace's group bits are withdrawn, the "
                "owner's are not",
                mode & 0o050 == 0 and mode & 0o700 == 0o700,
                oct(mode),
            )

            # --- E-5: reported, and failed everywhere it is held ---------------------
            messages = [m.get("message") for m in companion_log_messages(acfg)]
            report.check(
                "E-5. the companion detected the loss and the engine acknowledged it, once each",
                messages.count("permission_revoked") == 1
                and messages.count("revocation_reported") == 1,
                [m for m in messages if m in ("permission_revoked", "revocation_reported")],
            )
            listed = (await http.get(f"{cfg.perception_url}/v1/perception/sensors")).json()
            fs = [s for s in listed if s.get("sensor_id") == "companion-filesystem"]
            report.check(
                "E-5. perception-engine's filesystem sensor is failed",
                [s.get("state") for s in fs] == ["failed"],
                fs,
            )

            async def _published() -> list[dict[str, Any]] | None:
                failed = [
                    r
                    for r in await stores.health_reports("companion-filesystem")
                    if r["payload"].get("status") == "failed"
                ]
                return failed if failed and all(r["dispatched_at"] for r in failed) else None

            failed = await wait_for(
                _published, "the dispatched `failed` report", cfg.deadline_seconds
            )
            report.check(
                "E-5. exactly one `failed` report was published, through the outbox",
                len(failed) == 1,
                [_plain(r) for r in failed],
            )

            async def _held() -> list[dict[str, Any]] | None:
                rows = await stores.sensor_state("companion-filesystem")
                return rows if rows and rows[0]["state"] == "failed" else None

            held = await wait_for(
                _held, "cognitive_state.sensor_state = failed", cfg.deadline_seconds
            )
            report.check(
                "E-5. cognitive-state-engine holds failed, from that report",
                held[0]["last_event_id"] == failed[0]["id"],
                _plain(held),
            )

            # --- E-18: only the sensor lost access -----------------------------------
            companion_id = compose(acfg, "exec", "-T", "nova-companion", "id", "-u")
            companion_ls = compose(acfg, "exec", "-T", "nova-companion", "ls", cfg.sandbox_root)
            capability_ls = compose(acfg, "exec", "-T", "capability-engine", "ls", cfg.sandbox_root)
            report.check(
                "E-18. the companion runs as the override's uid, and is denied the workspace",
                companion_id.stdout.strip() == "1100"
                and companion_ls.returncode != 0
                and "Permission denied" in companion_ls.stderr,
                {"uid": companion_id.stdout.strip(), "ls": companion_ls.stderr.strip()},
            )
            report.check(
                "E-18. capability-engine can still list the workspace",
                capability_ls.returncode == 0,
                {"returncode": capability_ls.returncode, "stderr": capability_ls.stderr.strip()},
            )

            # --- E-6: the stream has stopped -----------------------------------------
            folder = cfg.workspace / (acfg.known_folder or "")
            name = f"ac7-{run_id}-after-revocation.txt"
            container = (
                f"{cfg.sandbox_root}/{acfg.known_folder}" if acfg.known_folder else cfg.sandbox_root
            )
            object_id = object_id_for_path(f"{container}/{name}")
            (folder / name).write_text(f"4F.8 E-6 {run_id}\n")
            report.check(
                "E-6 (N-7). a writer that still has permission wrote, and the OS accepted it",
                (folder / name).is_file(),
                str(folder / name),
            )
            deadline = time.monotonic() + WATCH_SECONDS
            leaked: list[dict[str, Any]] = []
            world = 404
            while time.monotonic() < deadline:
                leaked = await stores.outbox_for(object_id)
                world = await world_status(http, acfg.world_model_url, object_id)
                if leaked or world != 404:
                    break
                await asyncio.sleep(0.5)
            report.check(
                f"E-6. for {WATCH_SECONDS:.0f} s: no outbox row and no World Model object for it",
                not leaked and world == 404,
                {"outbox": [_plain(r) for r in leaked], "world_status": world},
            )
            report.check(
                "E-6. the companion submitted nothing for it",
                not any(
                    m.get("message") == "observation_submitted" and m.get("file") == name
                    for m in companion_log_messages(acfg)
                ),
                name,
            )
            evidence["revocation"] = {
                "workspace_mode": oct(mode),
                "failed_report": _plain(failed),
                "sensor_state": _plain(held),
                "e18": {
                    "companion_uid": companion_id.stdout.strip(),
                    "companion_ls": companion_ls.stderr.strip(),
                    "capability_ls_returncode": capability_ls.returncode,
                },
            }
        except TimeoutError as exc:
            report.check(f"the chain completed within the deadline: {exc}", False, str(exc))
        except Exception as exc:
            _unexpected(exc, report)
        finally:
            await database.close()
    return _finish("AC-7 revocation", evidence, report)


def _unexpected(exc: Exception, report: Report) -> None:
    """*(F-4F8-19.)* Any other error fails the phase as a check, with its
    traceback, so the evidence gathered so far is still printed. Nothing is
    retried, and the phase's exit status is still non-zero."""
    report.check(
        f"the phase ran to completion without an unexpected error: {type(exc).__name__}",
        False,
        traceback.format_exc(),
    )


def _finish(name: str, evidence: dict[str, Any], report: Report) -> int:
    evidence["checks"] = report.checks
    print("=== evidence ===")
    print(json.dumps(evidence, indent=2, default=str))
    if report.failed:
        print(f"=== {name}: {len(report.failed)} check(s) FAILED ===")
        for check in report.failed:
            print(f"  - {check}")
        return 1
    print(f"=== {name}: all {len(report.checks)} checks passed ===")
    return 0


PHASES = {"ac8": ac8, "ac7-latency": ac7_latency, "ac7-revocation": ac7_revocation}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in PHASES:
        raise SystemExit(f"usage: {sys.argv[0]} {' | '.join(PHASES)}")
    sys.exit(asyncio.run(PHASES[sys.argv[1]](AcceptanceConfig.from_env())))
