"""Phase 4F.P, P8 -- **real end-to-end execution** across the composed stack.

TDD 4F.P A-4FP-12 (ratified), §15's V-items in §28.4 C-14's composed tier.
This driver proves the whole production path against **real engines**, with a
**real input**, and **no stand-in anywhere in the chain**:

    a real file write in the shared workspace
      -> nova-companion (real, Rust)        -> perception-engine intake (real)
      -> perception.workspace.observed      (perception-engine's own outbox worker)
      -> cognitive-state-engine             (ingestion, T1 authoring, CAS promotion)
      -> autonomy.decision.requested        (the production trigger)
      -> autonomy-engine                    (Level 2, AUTO_EXECUTE, the real gates)
      -> action.execute                     (the one producer: autonomy-engine)
      -> action-engine                      (its 12-stage pipeline)
      -> capability.invoke.request          -> capability-engine (the filesystem adapter)
      -> the real `list` of the real sandbox root
      -> action-engine's reply -> P7's mapping -> autonomy.decision_log

**What this driver does, and nothing else.**

* **Writes real files** into the bind-mounted workspace (`NOVA_WORKSPACE_DIR`),
  each with a fresh, unique name, so every run is a new observed object and
  P5/P6 are neither weakened nor bypassed.
* **Configures only through production routes**: autonomy Level 2, one
  `AUTO_EXECUTE` policy for `read`, a `read` grant up to `low`, and A-4FP-11's
  disclosed test configuration -- `minimum_confidence_by_risk = {"negligible":
  0.0}` through `PUT /v1/action/identity-confidence-policy`. Each is the
  engine's own REST route, the same one `api-gateway` forwards.
* **Observes the Event Bus passively.** It subscribes to the subjects on the
  path, and to `_INBOX.>` to see each RPC's reply, and **never publishes,
  requests or replies**. A plain NATS subscription receives a copy of each
  message; it changes no delivery. The SDK's `serve()` stamps every reply's
  `causation_id` with its request's `event_id`, which is how a reply is paired
  with its request here.
* **Reads every engine's store by independent SQL** on its own connection --
  `SELECT` only.

**What it never does** (V-9; `tools/tests/test_e2e_real_execution.py` checks
this file's AST): it imports no engine, calls no `promote_thought` or `decide`,
publishes nothing, inserts or updates no row, and calls no `action-engine` or
`capability-engine` route that could execute anything.

**What it does not claim.** It is not AC-8: no Level-1 comparison, no browser,
no latency measurement (TDD 4F.P §20). It closes no carry-forward finding.

**Runs, in order** (each a fresh file):

1. **A -- the primary proof** (V-1 ... V-5): the T1 action executes for real,
   and `EXECUTE` is recorded because, and only because, `action-engine`
   reported `completed`.
2. **V-7 (a1)** -- a second real modification of A's file, after the debounce
   window: a new observation of the same object, and still one thought, one
   trigger, one `action.execute` and one action row.
3. **C -- the ordered marker** for (2), and a second complete real execution.
4. **B -- V-6 (a)**: with A-4FP-11's policy row removed, stage 3 denies; the
   decision is `PROPOSE` with a suggestion, never `EXECUTE`. The row is
   restored afterwards.

Usage (the e2e job sets every variable; the defaults are compose's host ports):

    NOVA_WORKSPACE_DIR=/path/to/workspace uv run python tools/e2e_real_execution.py

Exit status 0 only if every check passed. The evidence is printed as JSON.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4, uuid5

import asyncpg
import httpx
import nats

TRIGGER_NAMESPACE = UUID("0c81f3b8-e30f-5f0a-9241-8985e4b83489")
"""TDD 4F.6 §5.2's pinned literal: `autonomy-engine` derives a decision's
`subject_id` as `uuid5(TRIGGER_NAMESPACE, str(envelope.event_id))`. Restated,
not imported, so this driver checks the deployed engine against the TDD."""

INGESTION_NAMESPACE = UUID("77980e9a-8808-5af9-8e41-2442669868a1")
"""TDD 4F.P A-4FP-9: `cognitive-state-engine` derives an ingested thought's
identity as `uuid5(INGESTION_NAMESPACE, object_id)` -- the observed object, not
the event. Restated, not imported, for the same reason."""

PRIMARY_USER = UUID("00000000-0000-0000-0000-000000000001")
"""ADR-025's one user: the default `primary_user_id` of cognitive-state-,
autonomy- and action-engine, which compose sets on perception-engine too
(A-4FP-12, §28.4 C-12)."""

OUTCOME_FOR_STATUS = {
    "completed": "execute",
    "denied": "propose",
    "failed": "execution_failed",
    "rolled_back": "execution_failed",
    "pending": "execution_failed",
    "approval_required": "execution_failed",
    "approved": "execution_failed",
    "executing": "execution_failed",
}
"""A-4FP-7's ratified table, restated: the recorded outcome is checked as a
function of the status `action-engine` itself persisted, never hard-coded."""

T1 = {
    "category": "read",
    "risk": "low",
    "action_type": "filesystem",
    "execution_target": "filesystem",
    "operation": "list",
    "parameters": {},
    "verification_method": "adapter_success",
}
"""A-4FP-3's one ratified authoring entry, value for value."""

TWELVE_STAGES = (
    "receive_request",
    "validate",
    "check_permissions",
    "estimate_risk",
    "prepare_resources",
    "execute",
    "monitor_progress",
    "detect_errors",
    "recover_if_necessary",
    "verify_result",
    "report_outcome",
    "store_experience",
)
"""`action-engine`'s twelve stages, as `action.action_execution_history`
names them."""

TAPPED_SUBJECTS = (
    "perception.workspace.observed",
    "autonomy.decision.requested",
    "action.execute",
    "capability.resolve.request",
    "capability.invoke.request",
    "world_model.context.request",
    "_INBOX.>",
)
"""Every subject on the path, plus the replies. Subscribed to, never published."""

TERMINAL = ("completed", "failed", "denied", "rolled_back")


@dataclass(frozen=True)
class Config:
    workspace: Path
    sandbox_root: str
    postgres_dsn: str
    nats_url: str
    perception_url: str
    cognitive_state_url: str
    autonomy_url: str
    action_url: str
    capability_url: str
    deadline_seconds: float

    @classmethod
    def from_env(cls) -> Config:
        workspace = os.environ.get("NOVA_WORKSPACE_DIR")
        if not workspace:
            raise SystemExit(
                "NOVA_WORKSPACE_DIR is required: the host directory compose bind-mounts "
                "as /workspace for nova-companion and capability-engine"
            )
        env = os.environ.get
        return cls(
            workspace=Path(workspace),
            # The workspace as capability-engine and the companion see it: the
            # compose bind mount's target, `/workspace`.
            sandbox_root=env("NOVA_E2E_SANDBOX_ROOT", "/workspace"),
            postgres_dsn=env(
                "NOVA_E2E_POSTGRES_DSN", "postgresql://nova:nova_dev_password@localhost:5432/nova"
            ),
            nats_url=env("NATS_URL", "nats://localhost:4222"),
            perception_url=env("NOVA_E2E_PERCEPTION_URL", "http://localhost:8009"),
            cognitive_state_url=env("NOVA_E2E_COGNITIVE_STATE_URL", "http://localhost:8020"),
            autonomy_url=env("NOVA_E2E_AUTONOMY_URL", "http://localhost:8019"),
            action_url=env("NOVA_E2E_ACTION_URL", "http://localhost:8012"),
            capability_url=env("NOVA_E2E_CAPABILITY_URL", "http://localhost:8011"),
            deadline_seconds=float(env("NOVA_E2E_DEADLINE_SECONDS", "90")),
        )


# --- the passive bus observer ------------------------------------------------------


@dataclass
class Seen:
    subject: str
    envelope: dict[str, Any]
    at: float

    @property
    def payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = self.envelope.get("payload") or {}
        return payload


@dataclass
class Tap:
    """Subscribes and records. **Never publishes.**"""

    seen: list[Seen] = field(default_factory=list)

    async def start(self, url: str) -> Any:
        connection = await nats.connect(url, name="4fp-p8-observer")

        async def _record(message: Any) -> None:
            try:
                envelope = json.loads(message.data)
            except ValueError:
                return
            if isinstance(envelope, dict):
                self.seen.append(Seen(message.subject, envelope, time.monotonic()))

        for subject in TAPPED_SUBJECTS:
            await connection.subscribe(subject, cb=_record)
        await connection.flush()
        return connection

    def requests(self, subject: str, where: Callable[[Seen], bool] | None = None) -> list[Seen]:
        return [s for s in self.seen if s.subject == subject and (where is None or where(s))]

    def replies_to(self, request: Seen) -> list[Seen]:
        """Every reply on the bus to `request`. A responder that is not the one
        engine serving the subject -- even one claiming that engine's name --
        adds a second reply, so the checks below require exactly one."""
        event_id = request.envelope.get("event_id")
        return [
            seen
            for seen in self.seen
            if seen.subject.startswith("_INBOX.") and seen.envelope.get("causation_id") == event_id
        ]

    def reply_to(self, request: Seen) -> Seen | None:
        replies = self.replies_to(request)
        return replies[0] if replies else None


# --- checks ---------------------------------------------------------------------


@dataclass
class Report:
    checks: list[dict[str, Any]] = field(default_factory=list)

    def check(self, name: str, ok: bool, evidence: Any = None) -> bool:
        self.checks.append({"check": name, "ok": bool(ok), "evidence": evidence})
        print(f"{'PASS' if ok else 'FAIL'}  {name}", flush=True)
        if not ok:
            print(f"      evidence: {json.dumps(evidence, default=str)[:1500]}", flush=True)
        return bool(ok)

    @property
    def failed(self) -> list[str]:
        return [c["check"] for c in self.checks if not c["ok"]]


async def wait_for[T](probe: Callable[[], Awaitable[T | None]], what: str, deadline_s: float) -> T:
    """Poll until `probe` returns a value. Bounds a wait; it does not pace one."""
    deadline = time.monotonic() + deadline_s
    while True:
        value = await probe()
        if value is not None:
            return value
        if time.monotonic() >= deadline:
            raise TimeoutError(f"timed out after {deadline_s}s waiting for {what}")
        await asyncio.sleep(0.25)


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


# --- independent SQL, SELECT only --------------------------------------------------


class Stores:
    def __init__(self, connection: asyncpg.Connection) -> None:
        self._db = connection

    async def observations(self, label: str) -> list[dict[str, Any]]:
        rows = await self._db.fetch(
            "SELECT id, payload, created_at, dispatched_at FROM perception.outbox_event "
            "WHERE subject = 'perception.workspace.observed' AND payload->>'label' = $1 "
            "ORDER BY created_at, id",
            label,
        )
        return [{**dict(r), "payload": _json(r["payload"])} for r in rows]

    async def thoughts(self, label: str) -> list[dict[str, Any]]:
        rows = await self._db.fetch(
            "SELECT thought_id, user_id, description, attention_layer, proposed_action, "
            "created_at, updated_at FROM cognitive_state.active_thought WHERE description = $1",
            f"Activity observed in {label}",
        )
        return [{**dict(r), "proposed_action": _json(r["proposed_action"])} for r in rows]

    async def decisions(self, subject_id: UUID) -> list[dict[str, Any]]:
        rows = await self._db.fetch(
            "SELECT id, action_id, suggestion_id, autonomy_level, outcome, reason, "
            "xmin::text::bigint AS xid FROM autonomy.decision_log WHERE action_id = $1",
            subject_id,
        )
        return [dict(r) for r in rows]

    async def suggestions(self, subject_id: UUID) -> list[dict[str, Any]]:
        rows = await self._db.fetch(
            "SELECT id, user_id, category, risk, title, status FROM autonomy.suggestion "
            "WHERE id = $1",
            subject_id,
        )
        return [dict(r) for r in rows]

    async def actions(self, action_id: UUID) -> list[dict[str, Any]]:
        rows = await self._db.fetch(
            "SELECT id, action_type, source, requested_by, execution_target, parameters, "
            "risk, status, verification_method, result, error, xmin::text::bigint AS xid "
            "FROM action.action WHERE id = $1",
            action_id,
        )
        return [
            {**dict(r), "parameters": _json(r["parameters"]), "result": _json(r["result"])}
            for r in rows
        ]

    async def history(self, action_id: UUID) -> list[dict[str, Any]]:
        rows = await self._db.fetch(
            "SELECT stage, outcome, detail, xmin::text::bigint AS xid "
            "FROM action.action_execution_history WHERE action_id = $1 ORDER BY created_at, id",
            action_id,
        )
        return [dict(r) for r in rows]

    async def identity_policy(self) -> list[dict[str, Any]]:
        rows = await self._db.fetch(
            "SELECT user_id, minimum_confidence_by_risk FROM action.identity_confidence_policy"
        )
        return [
            {**dict(r), "minimum_confidence_by_risk": _json(r["minimum_confidence_by_risk"])}
            for r in rows
        ]

    async def filesystem_capability(self) -> dict[str, Any] | None:
        row = await self._db.fetchrow(
            "SELECT id, name, execution_adapter, health_status, required_resources "
            "FROM capability.capability WHERE name = 'filesystem'"
        )
        return (
            None
            if row is None
            else {**dict(row), "required_resources": _json(row["required_resources"])}
        )


# --- production routes -------------------------------------------------------------


async def wait_ready(http: httpx.AsyncClient, cfg: Config, report: Report) -> None:
    for name, base in (
        ("perception-engine", cfg.perception_url),
        ("cognitive-state-engine", cfg.cognitive_state_url),
        ("autonomy-engine", cfg.autonomy_url),
        ("action-engine", cfg.action_url),
        ("capability-engine", cfg.capability_url),
    ):

        async def _ready(base: str = base) -> bool | None:
            try:
                response = await http.get(f"{base}/internal/readiness")
            except httpx.HTTPError:
                return None
            return True if response.status_code == 200 else None

        await wait_for(_ready, f"{name} readiness", cfg.deadline_seconds)
    report.check("every engine on the path answers readiness", True)


async def configure(http: httpx.AsyncClient, cfg: Config, report: Report) -> dict[str, Any]:
    """Level 2, one AUTO_EXECUTE policy for `read`, a `read` grant to `low`,
    and A-4FP-11's identity threshold -- **through production routes only**.
    Idempotent, so repeated runs against one stack configure one state."""
    level = await http.put(f"{cfg.autonomy_url}/v1/autonomy/level", json={"level": 2})
    report.check("PUT /v1/autonomy/level -> Level 2", level.status_code == 200, level.text)

    grants = await http.put(
        f"{cfg.autonomy_url}/v1/autonomy/permissions",
        json={
            "grants": [
                {
                    "category": "read",
                    "max_risk": "low",
                    "requires_approval_above": None,
                    "granted": True,
                }
            ]
        },
    )
    report.check(
        "PUT /v1/autonomy/permissions -> read up to low", grants.status_code == 200, grants.text
    )

    policies = (await http.get(f"{cfg.autonomy_url}/v1/autonomy/policies")).json()
    existing = [
        p
        for p in policies
        if p["effect"] == "auto_execute" and p["match_category"] == "read" and p["enabled"]
    ]
    if not existing:
        created = await http.post(
            f"{cfg.autonomy_url}/v1/autonomy/policies",
            json={
                "name": "4F.P P8: auto-execute low-risk reads",
                "effect": "auto_execute",
                "match_category": "read",
            },
        )
        report.check(
            "POST /v1/autonomy/policies -> AUTO_EXECUTE for read",
            created.status_code == 201,
            created.text,
        )
    else:
        report.check("an AUTO_EXECUTE policy for read exists", True, existing[0]["id"])

    policy = await put_identity_policy(http, cfg)
    report.check(
        "PUT /v1/action/identity-confidence-policy -> {negligible: 0.0} "
        "(A-4FP-11, disclosed test configuration)",
        policy.status_code == 200 and policy.json()["user_id"] == str(PRIMARY_USER),
        policy.text,
    )
    return {"level": level.json(), "identity_policy": policy.json()}


async def put_identity_policy(http: httpx.AsyncClient, cfg: Config) -> httpx.Response:
    return await http.put(
        f"{cfg.action_url}/v1/action/identity-confidence-policy",
        json={"minimum_confidence_by_risk": {"negligible": 0.0}},
    )


async def invocation_count(http: httpx.AsyncClient, cfg: Config) -> float:
    """`capability-engine`'s own `capability_invocation_total` for a successful
    `filesystem` invocation, read from its own `/internal/metrics`."""
    response = await http.get(f"{cfg.capability_url}/internal/metrics/", follow_redirects=True)
    response.raise_for_status()
    total = 0.0
    for line in response.text.splitlines():
        if not line.startswith("capability_invocation_total{"):
            continue
        labels, _, value = line.rpartition(" ")
        if 'adapter="filesystem"' in labels and 'outcome="success"' in labels:
            total += float(value)
    return total


# --- one real run --------------------------------------------------------------------


@dataclass
class Run:
    label: str
    path: Path
    observation: dict[str, Any]
    thought: dict[str, Any]
    trigger: Seen
    subject_id: UUID
    decision: dict[str, Any]
    action: dict[str, Any] | None


async def real_run(
    tag: str,
    *,
    run_id: str,
    cfg: Config,
    stores: Stores,
    tap: Tap,
    content: str | None = None,
) -> Run:
    """Writes one fresh file and follows it through every store."""
    label = f"p8-{run_id}-{tag}.txt"
    path = cfg.workspace / label
    path.write_text(content or f"4F.P P8 real-execution probe {run_id} {tag}\n")

    async def _observed() -> dict[str, Any] | None:
        rows = [r for r in await stores.observations(label) if r["dispatched_at"] is not None]
        return rows[0] if rows else None

    observation = await wait_for(
        _observed, f"{label}: a dispatched perception observation", cfg.deadline_seconds
    )

    async def _promoted() -> dict[str, Any] | None:
        rows = [r for r in await stores.thoughts(label) if r["attention_layer"] == "immediate"]
        return rows[0] if rows else None

    thought = await wait_for(_promoted, f"{label}: a promoted Active Thought", cfg.deadline_seconds)

    async def _triggered() -> Seen | None:
        found = tap.requests(
            "autonomy.decision.requested",
            lambda s: s.payload.get("thought_id") == str(thought["thought_id"]),
        )
        return found[0] if found else None

    trigger = await wait_for(_triggered, f"{label}: the trigger on the bus", cfg.deadline_seconds)
    subject_id = uuid5(TRIGGER_NAMESPACE, str(trigger.envelope["event_id"]))

    async def _decided() -> dict[str, Any] | None:
        rows = await stores.decisions(subject_id)
        return rows[0] if rows else None

    decision = await wait_for(_decided, f"{label}: the recorded decision", cfg.deadline_seconds)

    async def _replied() -> Seen | None:
        return tap.reply_to(trigger)

    await wait_for(_replied, f"{label}: the decision reply on the bus", cfg.deadline_seconds)
    actions = await stores.actions(subject_id)
    return Run(
        label,
        path,
        observation,
        thought,
        trigger,
        subject_id,
        decision,
        actions[0] if actions else None,
    )


def check_executed(
    run: Run,
    *,
    sandbox_root: str,
    report: Report,
    tap: Tap,
    history: list[dict[str, Any]],
    capability: dict[str, Any],
    invocations_delta: float,
    identity_policy: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    thoughts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Every check for one fully executed run, and the evidence it rests on."""
    tag = run.label
    obs_payload = run.observation["payload"]
    observed = tap.requests(
        "perception.workspace.observed",
        lambda s: s.envelope.get("event_id") == str(run.observation["id"]),
    )
    report.check(
        f"[{tag}] 1. the real observation reached the bus from perception-engine's outbox",
        len(observed) == 1 and observed[0].envelope.get("source_engine") == "perception-engine",
        [s.envelope for s in observed],
    )
    report.check(
        f"[{tag}] 1. the observation is the primary user's, and carries no path",
        obs_payload.get("user_id") == str(PRIMARY_USER)
        and sandbox_root not in json.dumps(obs_payload),
        obs_payload,
    )

    report.check(
        f"[{tag}] 2. the thought's identity is the observed object's (A-4FP-9)",
        run.thought["thought_id"] == uuid5(INGESTION_NAMESPACE, obs_payload["object_id"]),
        {"thought_id": str(run.thought["thought_id"]), "object_id": obs_payload["object_id"]},
    )
    proposal = run.thought["proposed_action"]
    report.check(
        f"[{tag}] 2. exactly one Active Thought for the observed object, the primary user's",
        len(thoughts) == 1 and run.thought["user_id"] == PRIMARY_USER,
        [{k: str(v) for k, v in t.items() if k != "proposed_action"} for t in thoughts],
    )
    report.check(
        f"[{tag}] 3. its ProposedAction is T1: list + {{}}",
        all(proposal.get(k) == v for k, v in T1.items()),
        proposal,
    )
    report.check(
        f"[{tag}] 4. promoted to immediate (the production CAS path)",
        run.thought["attention_layer"] == "immediate",
        run.thought["attention_layer"],
    )

    triggers = tap.requests(
        "autonomy.decision.requested",
        lambda s: s.payload.get("thought_id") == str(run.thought["thought_id"]),
    )
    trigger = run.trigger
    report.check(
        f"[{tag}] 5. exactly one autonomy.decision.requested, from cognitive-state-engine, "
        "carrying T1's pair",
        len(triggers) == 1
        and trigger.envelope.get("source_engine") == "cognitive-state-engine"
        and trigger.payload.get("operation") == "list"
        and trigger.payload.get("parameters") == {},
        trigger.envelope,
    )
    decided = tap.reply_to(trigger)
    report.check(
        f"[{tag}] 5. exactly one reply to the trigger: one autonomy-engine decided it",
        len(tap.replies_to(trigger)) == 1,
        [s.envelope for s in tap.replies_to(trigger)],
    )
    report.check(
        f"[{tag}] 5. autonomy-engine decided it, under the identity it derives from the trigger",
        decided is not None
        and decided.envelope.get("source_engine") == "autonomy-engine"
        and decided.payload.get("subject_id") == str(run.subject_id),
        decided.envelope if decided else None,
    )

    executes = tap.requests(
        "action.execute", lambda s: s.payload.get("action_id") == str(run.subject_id)
    )
    report.check(
        f"[{tag}] 7/14/15. exactly one action.execute for the decision -- no retry, no duplicate",
        len(executes) == 1,
        [s.envelope for s in executes],
    )
    execute = executes[0] if executes else None
    report.check(
        f"[{tag}] 7. published by autonomy-engine, the one producer, for the primary user",
        execute is not None
        and execute.envelope.get("source_engine") == "autonomy-engine"
        and execute.payload.get("requested_by") == str(PRIMARY_USER),
        execute.envelope if execute else None,
    )
    report.check(
        f'[{tag}] 8. action.execute carries exactly {{"operation": "list"}} (P4)',
        execute is not None and execute.payload.get("parameters") == {"operation": "list"},
        execute.payload if execute else None,
    )

    reply = tap.reply_to(execute) if execute else None
    report.check(
        f"[{tag}] 9. exactly one reply to action.execute: one engine answered it",
        execute is not None and len(tap.replies_to(execute)) == 1,
        [s.envelope for s in tap.replies_to(execute)] if execute else None,
    )
    report.check(
        f"[{tag}] 9/11. the real action-engine replied completed, with the listing",
        reply is not None
        and reply.envelope.get("source_engine") == "action-engine"
        and reply.payload.get("status") == "completed"
        and run.label in (reply.payload.get("result") or {}).get("entries", []),
        reply.envelope if reply else None,
    )

    action = run.action or {}
    report.check(
        f"[{tag}] 9. exactly one action row, keyed by the decision's subject_id",
        len(actions) == 1 and action.get("id") == run.subject_id,
        [str(a.get("id")) for a in actions],
    )
    report.check(
        f"[{tag}] V-1/V-2. action-engine stored the authored operation and parameters",
        action.get("parameters")
        == {"operation": proposal.get("operation"), **(proposal.get("parameters") or {})}
        and action.get("action_type") == proposal.get("action_type")
        and action.get("execution_target") == proposal.get("execution_target"),
        {k: action.get(k) for k in ("parameters", "action_type", "execution_target")},
    )
    stages = [(h["stage"], h["outcome"]) for h in history]
    report.check(
        f"[{tag}] 12. the 12-stage pipeline ran (V-3: validate and check_permissions succeeded)",
        set(TWELVE_STAGES) <= {s for s, _ in stages}
        and ("validate", "success") in stages
        and ("check_permissions", "success") in stages
        and ("execute", "started") in stages,
        stages,
    )
    report.check(
        f"[{tag}] 11. V-4: action-engine's own row is completed, with the listing",
        action.get("status") == "completed"
        and run.label in (action.get("result") or {}).get("entries", []),
        {k: action.get(k) for k in ("status", "result", "error", "risk")},
    )

    invokes = tap.requests(
        "capability.invoke.request",
        lambda s: execute is not None and reply is not None and execute.at <= s.at <= reply.at,
    )
    invoke = invokes[0] if len(invokes) == 1 else None
    invoke_reply = tap.reply_to(invoke) if invoke else None
    report.check(
        f"[{tag}] 10. exactly one reply to the capability invocation: one engine answered it",
        invoke is not None and len(tap.replies_to(invoke)) == 1,
        [s.envelope for s in tap.replies_to(invoke)] if invoke else None,
    )
    report.check(
        f"[{tag}] 10. action-engine invoked capability-engine's filesystem capability once, "
        "operation list",
        invoke is not None
        and invoke.envelope.get("source_engine") == "action-engine"
        and invoke.payload.get("capability_id") == str(capability["id"])
        and invoke.payload.get("operation") == "list"
        and invoke.payload.get("parameters") == {"operation": "list"},
        [s.envelope for s in invokes],
    )
    report.check(
        f"[{tag}] 10/T2. the real capability-engine executed it: success, and its listing is "
        "action-engine's stored result",
        invoke_reply is not None
        and invoke_reply.envelope.get("source_engine") == "capability-engine"
        and invoke_reply.payload.get("outcome") == "success"
        and invoke_reply.payload.get("result") == action.get("result"),
        invoke_reply.envelope if invoke_reply else None,
    )
    report.check(
        f"[{tag}] 10/T2. the listing is of the shared workspace: it names this run's own file",
        capability.get("required_resources") == [sandbox_root]
        and run.label
        in ((invoke_reply.payload.get("result") or {}).get("entries", []) if invoke_reply else []),
        {"required_resources": capability.get("required_resources")},
    )
    report.check(
        f"[{tag}] 10/T2. capability-engine's own invocation counter rose by exactly one",
        invocations_delta == 1.0,
        invocations_delta,
    )

    decision = run.decision
    expected = OUTCOME_FOR_STATUS.get(str(action.get("status")))
    report.check(
        f"[{tag}] 12/16. exactly one decision row: the outcome P7 maps from "
        "action-engine's own status",
        len(decisions) == 1 and decision["outcome"] == expected == "execute",
        {
            "status": action.get("status"),
            "expected": expected,
            "decisions": [{k: str(v) for k, v in d.items()} for d in decisions],
        },
    )
    report.check(
        f"[{tag}] 12. the decision's reason names action-engine's report",
        "action-engine reported completed" in (decision.get("reason") or "")
        and decision.get("autonomy_level") == 2
        and decision.get("suggestion_id") is None,
        {k: str(v) for k, v in decision.items()},
    )
    history_xids = [h["xid"] for h in history]
    report.check(
        f"[{tag}] 13. EXECUTE was written after action-engine's terminal writes "
        "(transaction order)",
        bool(history_xids)
        and decision["xid"] > action.get("xid", 0)
        and decision["xid"] > max(history_xids),
        {
            "decision_xid": decision["xid"],
            "action_xid": action.get("xid"),
            "history_max_xid": max(history_xids) if history_xids else None,
        },
    )
    report.check(
        f"[{tag}] C-12. one user: the identity policy stage 3 read is keyed by requested_by",
        [str(p["user_id"]) for p in identity_policy]
        == [str(action.get("requested_by"))]
        == [str(PRIMARY_USER)],
        [str(p["user_id"]) for p in identity_policy],
    )

    return {
        "file": run.label,
        "observation": {"event_id": str(run.observation["id"]), "payload": obs_payload},
        "thought": {"thought_id": str(run.thought["thought_id"]), "proposed_action": proposal},
        "trigger": {"event_id": trigger.envelope.get("event_id"), "payload": trigger.payload},
        "subject_id": str(run.subject_id),
        "action_execute": execute.envelope if execute else None,
        "action_engine_reply": reply.envelope if reply else None,
        "capability_invoke": invoke.envelope if invoke else None,
        "capability_reply": invoke_reply.envelope if invoke_reply else None,
        "capability_invocations_delta": invocations_delta,
        "action_row": {k: str(v) if isinstance(v, UUID) else v for k, v in action.items()},
        "stages": stages,
        "decision_row": {k: str(v) if isinstance(v, UUID) else v for k, v in decision.items()},
    }


async def execute_and_check(
    tag: str,
    *,
    run_id: str,
    cfg: Config,
    http: httpx.AsyncClient,
    stores: Stores,
    tap: Tap,
    report: Report,
) -> dict[str, Any]:
    before = await invocation_count(http, cfg)
    run = await real_run(tag, run_id=run_id, cfg=cfg, stores=stores, tap=tap)
    capability = await stores.filesystem_capability()
    assert capability is not None, "capability-engine never installed the filesystem capability"
    return check_executed(
        run,
        sandbox_root=cfg.sandbox_root,
        report=report,
        tap=tap,
        history=await stores.history(run.subject_id),
        capability=capability,
        invocations_delta=await invocation_count(http, cfg) - before,
        identity_policy=await stores.identity_policy(),
        decisions=await stores.decisions(run.subject_id),
        actions=await stores.actions(run.subject_id),
        thoughts=await stores.thoughts(run.label),
    )


# --- the whole proof -------------------------------------------------------------------


async def prove(cfg: Config) -> int:
    report = Report()
    run_id = uuid4().hex[:12]
    evidence: dict[str, Any] = {"run_id": run_id, "workspace": str(cfg.workspace)}
    tap = Tap()
    observer = await tap.start(cfg.nats_url)
    database = await asyncpg.connect(cfg.postgres_dsn)
    stores = Stores(database)
    async with httpx.AsyncClient(timeout=15.0) as http:
        try:
            await wait_ready(http, cfg, report)
            capability = await wait_for(
                stores.filesystem_capability,
                "the installed filesystem capability",
                cfg.deadline_seconds,
            )
            report.check(
                "capability-engine's filesystem capability is installed, healthy, rooted at the "
                "shared workspace",
                capability["health_status"] == "healthy"
                and capability["required_resources"] == [cfg.sandbox_root],
                {k: str(v) for k, v in capability.items()},
            )
            evidence["configuration"] = await configure(http, cfg, report)

            # --- A: the primary proof -------------------------------------------------
            print("--- run A: the complete real execution (Tests 1-5; V-1 ... V-5) ---", flush=True)
            evidence["run_a"] = await execute_and_check(
                "a", run_id=run_id, cfg=cfg, http=http, stores=stores, tap=tap, report=report
            )

            # --- V-7 (a1): the same object, observed again ---------------------------
            print("--- V-7 (a1): a second real modification of A's file ---", flush=True)
            label_a = evidence["run_a"]["file"]
            subject_a = UUID(evidence["run_a"]["subject_id"])
            thought_a = evidence["run_a"]["thought"]["thought_id"]
            with (cfg.workspace / label_a).open("a") as handle:
                handle.write("modified again, after the debounce window\n")

            async def _second_observation() -> list[dict[str, Any]] | None:
                rows = [
                    r for r in await stores.observations(label_a) if r["dispatched_at"] is not None
                ]
                return rows if len(rows) >= 2 else None

            observations_a = await wait_for(
                _second_observation, "A's second dispatched observation", cfg.deadline_seconds
            )
            report.check(
                "V-7 (a1). the modification is a new observation (new event_id) of the same object",
                len({str(r["id"]) for r in observations_a}) == len(observations_a)
                and len({r["payload"]["object_id"] for r in observations_a}) == 1,
                [
                    {"event_id": str(r["id"]), "object_id": r["payload"]["object_id"]}
                    for r in observations_a
                ],
            )

            # --- C: the ordered marker, and a second real execution -------------------
            print(
                "--- run C: the ordered marker for V-7 (a1), and a second real execution ---",
                flush=True,
            )
            evidence["run_c"] = await execute_and_check(
                "c", run_id=run_id, cfg=cfg, http=http, stores=stores, tap=tap, report=report
            )
            report.check(
                "V-7 (a1). after the marker: still one thought, one trigger, one action.execute, "
                "one decision row and one action row for A",
                len(await stores.thoughts(label_a)) == 1
                and len(
                    tap.requests(
                        "autonomy.decision.requested",
                        lambda s: s.payload.get("thought_id") == thought_a,
                    )
                )
                == 1
                and len(
                    tap.requests(
                        "action.execute", lambda s: s.payload.get("action_id") == str(subject_a)
                    )
                )
                == 1
                and len(await stores.decisions(subject_a)) == 1
                and len(await stores.actions(subject_a)) == 1,
                {"thought_id": thought_a, "subject_id": str(subject_a)},
            )

            # --- B: V-6 (a), a real denial --------------------------------------------
            print("--- run B: V-6 (a), stage 3 denies without A-4FP-11's row ---", flush=True)
            removed = await http.delete(f"{cfg.action_url}/v1/action/identity-confidence-policy")
            report.check(
                "V-6 (a). DELETE /v1/action/identity-confidence-policy "
                "(the threshold returns to 1.0)",
                removed.status_code in (204, 404),
                removed.status_code,
            )
            try:
                before = await invocation_count(http, cfg)
                run_b = await real_run("b", run_id=run_id, cfg=cfg, stores=stores, tap=tap)
                delta_b = await invocation_count(http, cfg) - before
            finally:
                restored = await put_identity_policy(http, cfg)
                report.check(
                    "V-6 (a). the A-4FP-11 row is restored afterwards",
                    restored.status_code == 200,
                    restored.text,
                )
            action_b = run_b.action or {}
            executes_b = tap.requests(
                "action.execute", lambda s: s.payload.get("action_id") == str(run_b.subject_id)
            )
            reply_b = tap.reply_to(executes_b[0]) if executes_b else None
            report.check(
                "V-6 (a). the real action-engine denied it at stage 3, and replied denied",
                action_b.get("status") == "denied"
                and reply_b is not None
                and reply_b.envelope.get("source_engine") == "action-engine"
                and reply_b.payload.get("status") == "denied",
                {
                    "action": {k: str(v) for k, v in action_b.items()},
                    "reply": reply_b.envelope if reply_b else None,
                },
            )
            report.check(
                "V-6 (a). P7 recorded PROPOSE with a suggestion -- never EXECUTE",
                run_b.decision["outcome"]
                == OUTCOME_FOR_STATUS[str(action_b.get("status"))]
                == "propose"
                and "action-engine denied the action" in (run_b.decision.get("reason") or "")
                and len(await stores.suggestions(run_b.subject_id)) == 1,
                {k: str(v) for k, v in run_b.decision.items()},
            )
            report.check(
                "V-6 (a). nothing executed: no capability invocation for the denied action",
                delta_b == 0.0,
                delta_b,
            )
            evidence["run_b"] = {
                "file": run_b.label,
                "subject_id": str(run_b.subject_id),
                "action_engine_reply": reply_b.envelope if reply_b else None,
                "decision_row": {k: str(v) for k, v in run_b.decision.items()},
            }
        except TimeoutError as exc:
            report.check(f"the chain completed within the deadline: {exc}", False, str(exc))
        finally:
            await observer.drain()
            await database.close()

    evidence["checks"] = report.checks
    print("=== evidence ===")
    print(json.dumps(evidence, indent=2, default=str))
    if report.failed:
        print(f"=== P8: {len(report.failed)} check(s) FAILED ===")
        for name in report.failed:
            print(f"  - {name}")
        return 1
    print(f"=== P8: all {len(report.checks)} checks passed ===")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(prove(Config.from_env())))
