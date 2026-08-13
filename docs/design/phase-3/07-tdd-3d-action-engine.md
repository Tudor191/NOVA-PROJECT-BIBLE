# TDD 3D — `action-engine`

**Status: design only, awaiting approval. No production code authorized.**

---

## 0. Scope and dependencies

**Scope.** Action Object Model, validation/risk pipeline, terminal +
filesystem + git adapters (pending Fork 3C-1/3D-1), rollback for
reversible actions, Action Queue, and the Phase-3-owned approval loop
(Fork E2's resolution) — per `ENGINEERING_ROADMAP.md:515` and Bible Part
12.

**Dependencies.** `capability-engine` (`3C`) — per the roadmap's own
stated reason, *"depends on capabilities existing to execute against"*
(`ENGINEERING_ROADMAP.md:528`), sharpened by Fork 3C-1/3D-1 (§2).
**Does not depend on `agent-os`** — `action-engine` serves `action.execute`
now; its real caller (an agent instance via a Supervisor) does not exist
until `3E` (§5, same "real code, no real caller yet" idiom already used
throughout this project).

---

## 1. Existing capability vs. what's being built

Nothing exists — confirmed by directory listing and repo-wide grep (no
`Action*` type in `nova-contracts` beyond `action.result` referenced only
in doc 10's prose, never defined as a payload class). Entirely new
engine. `autonomy-engine`, `autonomy.approval.*`, and `nova-auth` are all
confirmed absent (§7) — this TDD's approval loop is necessarily
self-contained, per Fork E2's already-approved resolution.

---

## 2. Fork 3C-1/3D-1 resolution required before implementation

This TDD's own adapter design depends on TDD 3C's Fork 3C-1 being
resolved first. **Recommendation (shared with TDD 3C): `action-engine`
defines its own `CapabilityPort`** (own Protocol in
`domain/ports.py`, own client, mirroring the `GoalsPort`/`DigitalTwinPort`
convention) and invokes `capability-engine`'s already-registered git/
filesystem/terminal capabilities rather than reimplementing adapter
logic — `action-engine`'s own contribution is the risk/approval/
rollback/audit wrapper, not a second "how to run git."

**A concrete coordination consequence, disclosed here rather than
invented silently:** `action-engine`'s Rollback Strategy (§4) requires
some destructive filesystem/terminal operations to be reversible (Bible's
*"execution without recovery is unacceptable,"* `part-12-action-engine.md:287`).
If Fork 3C-1 resolves to Option A (shared adapters), `capability-engine`'s
filesystem adapter must support a pre-operation snapshot/backup primitive
for destructive calls — a requirement on TDD 3C's own adapter design that
TDD 3C's document (§3) does not currently specify, since it was written
before this dependency was traced. **This must be reconciled between the
two TDDs before either begins implementation** — flagged explicitly, not
silently assumed resolved.

---

## 3. Domain model

### 3.1 Action Object Model — Bible Part 12, mapped with two disclosed proposals

`part-12-action-engine.md:127-169` names 18 fields. Sixteen map directly
to well-understood types; two reference concepts the Bible names only by
example, requiring a proposed shape (same disclosure discipline as TDD
3B's `Estimate`/TDD 3C's `CapabilityHandle`):

```python
class Action(BaseModel):
    id: UUID
    action_type: Literal["terminal", "filesystem"]   # git layered atop these two, §3.2
    priority: ActionPriority                          # Bible's own 6-tier scale, §3.3
    source: str                                        # e.g. "agent:coding-agent"
    requested_by: UUID                                 # agent instance or user
    execution_target: str
    depends_on: list[UUID] = []
    parameters: dict
    expected_result: str | None = None
    risk: RiskLevel                                    # reused from TDD 3B, Bible Part 14
    timeout_seconds: int
    retry_policy: RetryPolicy                           # proposed, below
    rollback_strategy: RollbackStrategy                  # proposed, below
    required_permissions: list[str]
    status: Literal["pending","approval_required","approved","denied",
                     "executing","completed","failed","rolled_back"]
    verification_method: str
    confidence: float | None = None
```

**Proposed `RetryPolicy`** (Bible names the field, not a schema):
```python
class RetryPolicy(BaseModel):
    max_retries: int = 0
    backoff_seconds: float = 1.0
```
**Proposed `RollbackStrategy`** (Bible gives six examples,
`part-12-action-engine.md:275-285`, no enum):
```python
class RollbackStrategy(BaseModel):
    kind: Literal["restore_file", "undo_configuration", "restart_service", "manual"]
    detail: str | None = None
```
Both **flagged for explicit approval** — proposed, not extracted.

### 3.2 Action Types — Phase 3 scope, exact Bible attribution

Bible names 13 Action Types (`part-12-action-engine.md:95-125`), Phase 3
implements exactly **two**: Filesystem Actions, Terminal Actions. **"Git"
is not a Bible-named Action Type** — it is a roadmap-level adapter
layered on top of Terminal/Filesystem Actions (confirmed discrepancy,
`00-research-and-scope.md:143-144`); `action_type` above is therefore a
two-value `Literal`, with git operations represented as `action_type="terminal"`
or `"filesystem"` plus an adapter selection, not a third type value.

### 3.3 `ActionPriority` — Bible Part 12, distinct from `RiskLevel`

`part-12-action-engine.md:473-489`: *"Emergency. Critical. High. Normal.
Low. Background."* Note this is a **scheduling** priority scale, not the
risk-tier scale (`RiskLevel`, reused from Bible Part 14) — the two are
independent axes on the same `Action` (a Background-priority action can
still be Critical-risk, and vice versa). Kept distinct per Bible's own
separate section headers.

---

## 4. The approval loop (Fork E2's resolution, made concrete)

**Trigger.** During the "Check Permissions" / "Estimate Risk" stages of
the Action Principle lifecycle (§6), an `Action` classified `risk="critical"`
(or matching a Bible §"SAFETY LAYERS" example — delete files, format
storage, credential modification, etc., `part-12-action-engine.md:453-471`)
transitions to `status="approval_required"` rather than proceeding
directly to `Execute`.

**Mechanism — new, `action`-owned namespace, never `autonomy.approval.*`:**

1. `action-engine` persists a `PendingApproval` record (`action_id`,
   `risk`, `requested_at`, `decided_at: datetime | None`,
   `decision: Literal["approved","denied"] | None`).
2. Publishes `action.approval.requested` (new payload, defined and owned
   here — **not** `autonomy.approval.requested`, which stays reserved,
   undefined, for `autonomy-engine` to claim in Phase 4, per Fork E2).
3. Calls the existing, unmodified `communication.intent.deliver.request`
   gate (ADR-005-compliant — `action-engine` never publishes
   `communication.intent.*` directly) via its own `CommunicationPort`/
   `CommunicationClient`, mirroring `digital-twin-engine`'s exact Fork D
   precedent structurally (own Protocol in `domain/ports.py`, own client
   in `clients/`).
4. The decision is collected via a stopgap direct REST endpoint,
   `POST /v1/action/approvals/{id}/decide` (body: `{approved: bool, reason: str | None}`)
   — served directly by `action-engine`'s own FastAPI app, since
   `api-gateway` does not exist yet (`03-gateway-web-prerequisite.md`).
   Named deliberately to mirror doc 11's reserved
   `/v1/autonomy/approvals/{id}/decide` naming convention, under
   `action-engine`'s own namespace instead.
5. On decision: publishes `action.approval.decided`, updates the
   `PendingApproval` record, and either proceeds to `Execute`
   (`approved`) or transitions the `Action` to `status="denied"`,
   reported to the caller via `action.result` with an outcome that
   distinguishes **user denial** from **execution failure** — these are
   not the same event to a calling agent instance.

**Timeout policy.** Reuses doc 10 §3's exact stated policy for the
analogous (Phase 4) autonomy approval check: *"No timeout bypass — action
blocks until a decision or explicit user timeout policy fires."* Default,
per this project's standing fail-closed discipline (the same discipline
`digital-twin-engine`'s `ProactiveBoundaryPolicy` already established for
an absent policy): **a timeout denies, never auto-approves.** Exact
timeout duration is a configuration value (`pydantic-settings`), not
hardcoded.

**What Phase 4's `autonomy-engine` adds later (explicitly out of this
TDD's scope, additive per doc 13 §7's two-engine model):** a *second*,
independent re-check consuming `autonomy.approval.requested`/
`.decision.made` on its own reserved namespace — this TDD's mechanism is
not replaced when `autonomy-engine` ships, only supplemented.

---

## 5. `action.execute` — served now, no real caller until `3E`

Per doc 10 row 7: *"an agent instance (via its Supervisor) → `action.execute`"*
→ `action-engine` validates permissions/risk, executes, replies
`action.result`. `action-engine` defines and serves this RPC now; tested
via the established "second `BoundEventBus` as external caller" pattern
(Phase 2D-D precedent) since no real `agent-os` Supervisor exists to call
it until `3E`.

---

## 6. Action Principle lifecycle — implementation mapping

`part-12-action-engine.md:43-93`'s twelve stages, mapped to concrete
pipeline steps (mirrors `reasoning-engine`'s own "Bible lifecycle,
implemented literally" precedent):

1. **Receive Request** — `action.execute` consumed (§5).
2. **Validate** — schema/parameter validation against `input_schema`.
3. **Check Permissions** — ADR-032 identity-confidence gate (§7).
4. **Estimate Risk** — `RiskLevel` classification (Bible Part 14 scale,
   reused).
5. **Prepare Resources** — resolve the target `Capability` via
   `CapabilityPort` (§2), confirm it is `health_status="healthy"`.
6. **Execute** — invoke the capability's adapter; blocked pending §4's
   approval loop if `risk="critical"`.
7. **Monitor Progress** — timeout enforcement (`timeout_seconds`).
8. **Detect Errors** — adapter-reported failure or timeout.
9. **Recover if Necessary** — `RollbackStrategy` invocation (§3.1, §2's
   coordination note).
10. **Verify Result** — `verification_method` check.
11. **Report Outcome** — `action.result` published.
12. **Store Experience** — persisted to Action History (§9).

---

## 7. ADR-032 compliance — identity-confidence as authorization signal

**Binding, cited explicitly per ADR-032's own requirement**
(`ADR-032-identity-confidence-is-also-an-authorization-signal.md:132-136`:
*"Phase 3 (Action Engine/NAOS)... design work must cite this ADR
explicitly when defining their own execution-gating logic."*).

- `action-engine` defines its own `IdentityPort` (own Protocol, own
  client — consuming `world-model-engine`'s existing `present_identities`
  field on `ActiveContext`, populated by `perception-engine` since Phase
  2D-B, via the already-existing `world_model.context.request` RPC — no
  new upstream RPC invented).
- Per ADR-032 point 2: a **configurable threshold per risk tier**, never
  one global hardcoded value — proposed shape:
  ```python
  class IdentityConfidencePolicy(BaseModel):
      user_id: UUID
      minimum_confidence_by_risk: dict[RiskLevel, float]
  ```
  Absent policy → fails closed (treats every risk tier as requiring
  maximum confidence), same idiom `ProactiveBoundaryPolicy` established.
- Per ADR-032 point 3: `action-engine` never performs identity
  recognition itself — it only consumes `perception-engine`'s (via World
  Model's) already-scored signal.

**Flagged for approval:** `IdentityConfidencePolicy`'s shape is proposed,
not extracted — same disclosure discipline as every other new type in
this TDD package.

---

## 8. Persistence

New `action` Postgres schema: `action` (the `Action` model, §3.1),
`pending_approval` (§4), `action_execution_history` (append-only, per
Bible's "Store Experience" stage, §6.12 — mirrors `ConversationDecisionTraceORM`'s
append-only precedent), `identity_confidence_policy` (§7).

---

## 9. Observability

- `action_execute_total{action_type=..., outcome=...}` (counter).
- `action_approval_requested_total{risk=...}`,
  `action_approval_decided_total{decision=...}` (counters).
- `action_approval_timeout_total` (counter — the fail-closed path, §4).
- `action_rollback_invoked_total{kind=...}` (counter).
- `action_identity_confidence_denied_total{risk=...}` (counter — ADR-032
  gate rejections, §7).
- Standard health/readiness/metrics via `nova-service-kit`.

---

## 10. Failure and degraded behavior

| Condition | Behavior |
|---|---|
| `CapabilityPort` reports the target capability unhealthy | Action fails at "Prepare Resources" (§6.5), never attempts execution against a known-unhealthy adapter. |
| Approval timeout fires | Denied (§4) — never auto-approved. |
| `IdentityPort` (World Model) timeout | Fails closed — treated as zero confidence for the gate (§7), consistent with this project's degraded-mode discipline (never silently bypass a security gate on a dependency timeout). |
| Execution fails mid-way | Rollback Strategy invoked (§6.9); if rollback itself fails, `status="failed"` with the rollback failure recorded distinctly from the original execution failure — never conflated into one opaque error. |
| Postgres unavailable | Standard loud-failure mode, consistent with every other engine's persistence-layer handling. |

---

## 11. Security boundaries

This TDD is, alongside TDD 3C, one of the two security-boundary-defining
TDDs in this package. ADR-032 (§7) and doc 13 §7's two-engine
defense-in-depth model (this TDD implements the `action-engine` half now;
`autonomy-engine`'s re-check half is Phase 4, additive) are both directly
binding. `required_permissions` follows the same locally-enforced,
`nova-auth`-absent reasoning already established in TDD 3C §10.

---

## 12. Required workspace/contract changes

- New `services/action-engine` (standard `-engine` scaffold).
- `nova_contracts.events.action` (new file): `Action`, `RetryPolicy`,
  `RollbackStrategy` (entities), `ActionExecuteRequestPayload`/
  `ActionResultPayload` (doc 10 row 7), `ActionApprovalRequestedPayload`/
  `ActionApprovalDecidedPayload` (§4, new Phase-3-owned namespace).
  **Explicitly not defined:** `autonomy.approval.requested`/
  `.decision.made` (reserved for Phase 4).
- Root `pyproject.toml`/import-linter contracts gain
  `nova_action_engine`.
- `infra/docker/docker-compose.local.yml`, `build-and-scan.yml` — new
  entries.

---

## 13. Testing strategy

**Unit (fake-backed):** risk classification for scripted parameter sets;
approval-loop state machine (requested → approved/denied/timeout);
ADR-032 gate unit tests (confidence above/below threshold, per risk
tier, absent-policy fail-closed case); rollback-invocation unit tests per
`RollbackStrategy.kind`.

**Contract:** all new payload round-trips, including confirming
`ActionApprovalRequestedPayload`'s subject is `action.approval.requested`,
never `autonomy.approval.requested` (a direct assertion, not just an
absence check — this is a security-relevant naming boundary worth a
dedicated test).

**Integration:** `action.execute` served correctly via the "second bus"
pattern (§5); full approval-loop round trip against a fake
`CommunicationPort` (mirroring `digital-twin-engine`'s
`FakeCommunicationPort` precedent exactly) proving the
`communication.intent.deliver.request` call happens and the stopgap
REST decide-endpoint correctly resolves a pending approval.

**Real-infrastructure:** real end-to-end approval round trip (real
Postgres for `pending_approval`, real `communication-engine` call) —
mirrors the Phase 2D-D Fork D real-wire-round-trip test pattern exactly.
Real sandbox-escape-adjacent test: a scripted Critical-risk filesystem
delete blocked pending approval, never executing before a decision
lands, verified against real timing (not a fake clock).

---

## 14. Acceptance criteria

1. A deliberately risky action (Bible's own example: deleting a file) is
   blocked pending approval and proceeds only after approval — the exact
   roadmap acceptance criterion (`ENGINEERING_ROADMAP.md:544`), now with
   a concrete, tested mechanism.
2. An approval timeout denies, never auto-approves.
3. `action.approval.*` subjects are never confused with
   `autonomy.approval.*` — the namespace boundary is a tested, not just
   documented, property.
4. ADR-032's identity-confidence gate correctly blocks a low-confidence-
   identity execution attempt for at least one Critical-risk action, with
   the policy's per-risk-tier configurability exercised (not just a
   single global threshold).
5. A forced mid-execution failure triggers the configured
   `RollbackStrategy` and restores prior state (roadmap's own rollback
   test, `ENGINEERING_ROADMAP.md:539`).
6. Fork 3C-1/3D-1's coordination consequence (§2) is reconciled with TDD
   3C before either implementation begins.

---

## 15. Non-goals / explicitly deferred

- `autonomy-engine`'s own re-check (Phase 4, additive per doc 13 §7).
- Any Action Type beyond Terminal/Filesystem (§3.2) — Desktop, Browser,
  Cloud, API, Database, AI, Voice, Communication, IoT, Mobile, Robot
  Actions are all future-phase work.
- `nova-auth`'s real RBAC/OIDC backing for `required_permissions` (Phase
  7, per `01-tdd-preparation-and-fork-resolutions.md` §9).
- `api-gateway` fronting the stopgap `/v1/action/approvals/{id}/decide`
  endpoint — additive once `3-P.1` ships (`03-gateway-web-prerequisite.md`).
