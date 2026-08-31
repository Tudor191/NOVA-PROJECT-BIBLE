# action-engine

Bible Part 12's Action Engine (`docs/design/phase-3/07-tdd-3d-action-engine.md`)
-- the twelve-stage Action Principle lifecycle, the approval loop for
Critical-risk actions, the ADR-032 identity-confidence gate, and the
`CapabilityPort` consumer that invokes `capability-engine`'s adapters on
an agent instance's behalf. Never receives adapter code itself -- every
execution is a `capability.invoke.request` RPC (ADR-004, Fork 3C-1/3D-1).

## Architecture

**Approved decision, execution_target semantics (§5.1,
`docs/design/phase-3/13-3d-action-engine-research.md`):** `Action.execution_target`
holds the target `Capability`'s stable `name` (e.g. `"git"`), resolved via
`capability.resolve.request`'s additive `name` field -- never a
Postgres-generated `capability_id`, which this engine has no way to know
in advance.

**Approved decision, validation stage ownership (§5.2):** stage 2
("Validate") is structural only -- `parameters['operation']` presence.
Deep parameter validation against the resolved `Capability.input_schema`
is deferred to stage 5 ("Prepare Resources"), after resolution.

**Approved decision, `action.execute` idempotency (§5.3):** natural-key
idempotency on `Action.id` (`= ActionExecuteRequestPayload.action_id`),
mirroring `capability-engine`'s own Fork 3C-4 `UNIQUE (name, version)`
precedent. A repeat request for an already-terminal `action_id` returns
the stored result unmodified -- never re-executes, never re-fires the
approval loop.

**Fork 3C-3 (Option B, resolved by Phase 3C):** this engine owns rollback
entirely -- a read-before-write pattern against `capability-engine`'s
existing, unmodified `capability.invoke.request` RPC. Only `"restore_file"`
has a concrete, automated mechanism; `"undo_configuration"`/
`"restart_service"`/`"manual"` are disclosed as requiring
operator/agent-level handling beyond this pipeline's automated reach.

**Fork E2 (Phase-3-owned approval namespace):** `action.approval.requested`/
`action.approval.decided` are this engine's own events -- never
`autonomy.approval.requested`/`autonomy.decision.made`, which stay
reserved, undefined, for `autonomy-engine` to claim in Phase 4.

## The Action Principle lifecycle

Twelve stages (`domain/pipeline.py`): Receive Request -> Validate -> Check
Permissions -> Estimate Risk -> Prepare Resources -> Execute -> Monitor
Progress -> Detect Errors -> Recover If Necessary -> Verify Result ->
Report Outcome -> Store Experience. Every stage transition is recorded in
`action_execution_history` (append-only), and Critical-risk actions block
in the approval loop before Prepare Resources ever runs.

**Known, disclosed implementation-time resolutions (not forks, no
competing architecture proposed anywhere in this project's documents --
see `domain/pipeline.py`'s module docstring):** risk is classified once,
internally, before stage 3's ADR-032 gate runs (which needs it), while the
stage-transition audit trail still records `CHECK_PERMISSIONS` before
`ESTIMATE_RISK`, matching Bible's literal stage order for what is
observable. `capability.invoke.request`'s `operation` field is read from
`Action.parameters['operation']` by convention. Risk classification itself
(`domain/risk.py`) is a small, deterministic, disclosed default -- no
document in this project specifies the exact `(action_type, operation) ->
RiskLevel` mapping.

## The approval loop

Critical-risk actions publish `action.approval.requested`, best-effort
notify the requester via `CommunicationPort.deliver_intent` (skipped if no
connected session), and block on `POST /v1/action/approvals/{id}/decide`
(the stopgap decision endpoint -- `api-gateway` does not exist yet) or the
configured `approval_timeout_seconds`. A timeout **denies**, never
auto-approves -- this project's standing fail-closed discipline.
`action.approval.decided` is published on every resolution path
(explicit decision or timeout).

## The ADR-032 identity-confidence gate

Stage 3 ("Check Permissions") reads `IdentityPort.get_confidence()`
(`world_model.context.request` -> `present_identities`) for
`Action.requested_by`, and compares it against a per-user, per-risk-tier
`IdentityConfidencePolicy` threshold. An absent policy or a timed-out/
absent confidence signal fails closed -- treated as zero confidence
against a maximum-confidence-required default, never silently bypassing
the gate. `action-engine` never performs identity recognition itself
(ADR-032 point 3) -- this only reads `perception-engine`'s (via World
Model's) already-scored signal.

## Owned events

| Direction | Subject | Payload |
|---|---|---|
| Served (RPC) | `action.execute` | Runs the full Action Principle lifecycle; no real caller until Phase 3E's Kernel Scheduler. |
| Requests (outbound, RPC) | `capability.resolve.request`, `capability.invoke.request` | `CapabilityPort` (Fork 3C-1/3D-1). |
| Requests (outbound, RPC) | `communication.session.lookup_by_user.request`, `communication.intent.deliver.request` | The approval loop's best-effort human-notification step. |
| Requests (outbound, RPC) | `world_model.context.request` | `IdentityPort` (ADR-032). |
| Published (fire-and-forget) | `action.approval.requested`, `action.approval.decided` | The Phase-3-owned approval-loop events (Fork E2). |

See `events/published.py` / `events/subscribed.py` for the enforced
allow-lists.

## Owned APIs

- `POST /v1/action/approvals/{action_id}/decide` -- the stopgap approval
  decision endpoint.
- `GET /internal/health`
- `GET /internal/readiness`
- `GET /internal/metrics`

Exposed directly (no `api-gateway` yet -- same stopgap precedent as every
other Phase 3 engine).

## Testing

```bash
uv run --package action-engine pytest -m "not real_infra" services/action-engine/tests
```

Real-infrastructure tests (`tests/real_infra/`) are marked `real_infra`
and require Docker (`testcontainers`) -- run explicitly with
`-m real_infra`.
