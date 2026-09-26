# TDD 4F — `nova-companion`, the perception extension,
## `services/cognitive-state-engine`, and Autonomy Level 2

**Status: RATIFIED 2026-09-15 (§19), clarified by a second ratification the same
day (§20). Not yet implemented.**
**Eight decisions D-4F-1 … D-4F-8 are answered and both formerly-open questions
are now closed: AC-7's measurement rule (§20.1) and the perception subject
contract (§20.2). No architectural ambiguity remains.**

> **Added 2026-09-26, additively.** The status above is preserved as written.
> A **third ratification (§24)** settles RS-1 … RS-11 for 4F.7 and adds the
> slice **4F.P** before 4F.8 (§18). **Slices 4F.1–4F.6 are merged.**

**Written against** `phase-4` at `c04b58e0d6be4f4236b8fe8c5a7dcf79bf7d56f4`
(the Phase 4E closure commit), on the preparation branch `phase-4f-tdd`.
**No `phase-4f` branch exists and none is created by this document.**

**Protocol:** [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md),
sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`,
1131 lines, read from `origin/main`, byte-identical on `phase-4`.

**Satisfies:** AC-7 (revised, §4.1), AC-8 (unchanged). **Depends on:** 4E
(merged as `59bbeee`), **CF-9** (§5) and **CF-11** (§6).

---

## 0. Objective

Phase 4F gives NOVA **senses** (`nova-companion`), **an inner life**
(`cognitive-state-engine`), and **the first autonomy level at which it acts
without being asked** (Level 2). Master scope §5: *"This milestone carries all
of Phase 4's platform risk, and it comes last by design (D-1)."*

Everything here is derived against the repository. Where the roadmap's prose and
the code disagreed, §1 says which won.

---

## 1. What the design pass found, and what was ratified

Eight findings, each now closed by a ratified decision. **Three were blocking.**

| # | Finding | Ratified outcome |
|---|---|---|
| **1.1** | AC-7's 1-second budget is unreachable: every perception publisher returns an `OutboxEvent` and dispatch is a **fixed 10 s cron**, so worst case is ~10 s | **D-4F-1 — AC-7 re-scoped to 5 s.** The outbox architecture is unchanged: no push-dispatch, no shortened cron, no direct-publish bypass |
| **1.2** | AC-8 is denied at `action-engine` stage 3: the identity-confidence gate is **not Critical-only** and defaults to threshold **1.0 at every risk level** | **D-4F-2 — CF-9 is an explicit 4F dependency.** The write surface belongs to `action-engine`, which already owns the model and table |
| **1.3** | AC-8 has no trigger — **0 production callers** of `decide()` or `insert_suggestion`, and no create-suggestion route | **D-4F-3 — `cognitive-state-engine` owns the initiative trigger**, under §6.2's prohibitions |
| **1.4** | AC-7 is not executable in CI as window-focus sensing: the runner has no desktop session, no `DISPLAY`, no Xvfb, no IDE | **D-4F-8 — the CI acceptance modality is the filesystem sensor.** IDE/window-focus sensing is **explicitly outside** the CI acceptance path |
| **1.5** | `SensorConfig.sensor_type` and `PermissionStatus.source` are closed literals excluding every 4F sensor | Widen additively (§7.2). Internal to `perception-engine`; **no registered payload references either type** |
| **1.6** | AC-7 clause 2 has no browser-reachable source | **D-4F-4 — internal bus path only.** `PUBLIC_TOPICS` unchanged; **no `/v1/perception` gateway prefix**; the panel reads normalized state over REST |
| **1.7** | No precedent for a non-Python process feeding an engine | **D-4F-5 — the transport already exists** (§8). `POST /v1/perception/observations` was built in 2D-C for exactly this caller |
| **1.8** | `companion/` sits outside every measured SLOC scope | **Scope extended to include `companion/`** (§17) |

### 1.1 The two corrections this pass made to its own earlier draft

**(a) "Direct publish gives up atomicity" was too broad.** The outbox serves two
distinct purposes here: **atomicity coupling** (`record_identity_observation(observation,
outbox_event=…)` writes a domain row and its event in one `db_session.begin()`)
and **durable queueing** (`enqueue_outbox(event)` alone — which is how
`observation_orchestration.py:155` publishes `addressee_signal.candidate`, with
no coupled domain row). For a queue-only subject the cost of a bypass is
durability and replay, not atomicity. **The distinction is recorded because it is
the reason a bypass could look cheap.** D-4F-1 declines it regardless.

**(b) Push-triggered dispatch is not safe as a naive "enqueue on write."**
`list_dispatch_ready` takes **no row lock** — `with_for_update`/`SKIP LOCKED`
appear **0 times** in the repository — and consumer-side `event_id` dedup is not
systematic (only `digital-twin-engine` derives idempotent keys from it). A second
trigger would put concurrent dispatchers over unlocked rows across **13** engines.
That is the disproportionate repository-wide risk D-4F-1 excludes.

---

## 2. Scope

| # | Deliverable | Location | Owner |
|---|---|---|---|
| 1 | **`nova-companion`** — Rust sensor/actuator daemon | `companion/nova-companion/` ([doc 02](../../architecture/02-repository-and-folder-structure.md)'s repository tree: *"companion/ — Rust OS-level perception/action daemon"*) | new |
| 2 | Sensor Abstraction Layer registration + literal widening | `perception-engine` | existing |
| 3 | Perception normalization, enrichment, multi-modal fusion | `perception-engine` | existing |
| 4 | **`services/cognitive-state-engine`** — Active Thoughts, Focus, Attention | new engine | new |
| 5 | **Autonomy Level 2** — five separable states (§6) | `autonomy-engine` | existing |
| 6 | **CF-9's policy write surface** | `action-engine` | existing |
| 7 | The `cognitive-state/` panel — Phase 4's eleventh and last | `apps/web-client` | existing |

### 2.1 Non-goals

Desktop shell (Phase 5) · voice UI presentation (Phase 5) · the five deferred
panels (Phase 5) · OIDC/PKCE, `nova-auth`, RBAC, multi-user (Phase 7; ADR-025) ·
mobile, third-party API, marketplace · Autonomy Levels 3–5 · closing CF-4, CF-5,
CF-6, CF-8, CF-10 · **any Phase 5 work of any kind.**

### 2.2 Properties a reviewer can check

1. **No engine-to-engine HTTP.** The only boundary-crossing `httpx` client is
   `api-gateway`'s `clients/upstream.py`. 4F adds none (ADR-004).
2. `api-gateway` remains the **sole** external REST boundary; **no new prefix**.
3. `ws-gateway` remains the **sole** browser realtime bridge; `PUBLIC_TOPICS`
   **unchanged at 18 strings**.
4. **No raw sensor event reaches the browser**, ever.
5. **No fabricated sensor data, no fake clock, no time simulation** (§16).
6. No duplicated state ownership (§10).

> **Added 2026-09-26 (4F.7 ratification, RS-5), additively.** Property 2 reads
> *"`api-gateway` remains the **sole** external REST boundary; **no new
> prefix**."* Its second clause contradicts §12, which adds
> `/v1/cognitive-state` (D-6, forwarded 1:1), and §18's 4F.7 row. **§12 is
> authoritative.** Property 2 is to be read as follows:
>
> - `api-gateway` remains the **sole** external REST boundary.
> - 4F adds exactly **one** new external prefix, `/v1/cognitive-state`.
> - That prefix is forwarded **1:1** (D-6).
> - **No `/v1/perception` prefix** is added (D-4F-4).
> - **No other new prefix** is added by 4F.7.
>
> The original sentence is preserved above and has not been edited. Full
> record: §24, RS-5.

---

## 3. Dependencies — verified at `c04b58e`

| Dependency | Evidence |
|---|---|
| Sensor Abstraction Layer | `perception-engine/domain/sensor.py` — 12-method `Sensor` Protocol, 8-transition lifecycle. Its docstring names `nova-companion` as the future implementor |
| **Companion intake transport** | **`POST /v1/perception/observations` already exists** (2D-C Priority 1). Its docstring: *"No caller of this endpoint exists anywhere in this repository yet — no gateway or **companion-client** service exists"* |
| World Model object ingestion | `world-model-engine` subscribes **`perception.*.observed`** (wildcard). `make_perception_dispatch_handler` routes unknown subjects to `make_perception_observed_handler`, whose docstring says the object-shaped path is *"**reserved for Phase 4's desktop-sensor extension**"* |
| Action execution entry point | `action-engine` subscribes to exactly **`action.execute`**; registered as `ActionExecuteRequestPayload`; **no production publisher today** |
| Level 2 machinery | `DEFINED_LEVELS` already contains Level 2; `SELECTABLE_LEVELS` does not; `GateReport.requires_approval` already carried *"so that when 4F enables Level 2 the signal is already being carried"* |
| Autonomy policy write surface | `POST/PATCH/DELETE /v1/autonomy/policies` exist |
| **`IdentityConfidencePolicy` write surface** | **Does not exist — CF-9** |

**Bound by:** D-1, D-3, D-6, D-4D-1, D-4D-2 (§5.4), ADR-004, ADR-024, ADR-025,
ADR-030, ADR-032, ADR-033, ADR-034.

---

## 4. Acceptance criteria

### 4.1 AC-7 — REVISED, ratified 2026-09-15

> **AC-7 (4F).** *"A known project becoming active on the user's machine is
> detected by a `nova-companion` sensor, without user action, and is reflected in
> the World Model **within five seconds**; and revoking that sensor's OS-level
> permission stops the perception stream, **visibly**, in the Digital Twin /
> Cognitive State panel."*

***Superseded original, preserved per protocol §0.3.4:*** *"Opening a known
project in the IDE is detected and reflected in the World Model within one second
with no user action, and revoking a sensor's OS permission immediately and
visibly stops that perception stream in the UI."*

**Three changes, each with a reason.** *1 s → 5 s*: a 10 s outbox cron cannot
serve 1 s, and the three ways to make it could each cost more than the criterion
is worth (§1.1b). *"in the IDE" → "becoming active on the user's machine"*:
modality-neutral, so a genuine filesystem observation satisfies it — window focus
cannot be produced honestly in CI (§16). *"the UI" → a named panel*: testable.

| Clause | Discharged by |
|---|---|
| *"a known project becoming active"* | Filesystem sensor observes a real event in a real project directory |
| *"known"* | Correlated to a `project_id`; the only project identity in the system is `MemoryRecord.project_id` (4E §5.2), read **via events**, never by cross-engine DB access |
| *"detected by a `nova-companion` sensor"* | A real companion process, registered behind the Sensor Abstraction Layer |
| *"without user action"* | An autonomous sensor loop; no REST call by a human |
| *"reflected in the World Model"* | `perception.<name>.observed` → existing wildcard → existing object handler → `WorldObject` |
| *"within five seconds"* | Measured elapsed wall-clock, asserted as a number |
| *"revoking that sensor's OS-level permission"* | A genuine `chmod` on the watched directory |
| *"stops the perception stream"* | Lifecycle `running → failed` (revoked under a live stream) or `→ stopped` |
| *"visibly … in the panel"* | The panel renders sensor state from the engine's REST read surface |

> **Added 2026-09-26 (4F.7 ratification, RS-3a and RS-3b), additively.** The
> table above is unchanged. What it now means for the slices:
>
> - **4F.7 discharges only the last row**, *"visibly … in the panel"*. The panel
>   renders whatever normalized sensor state the read surface reports, and
>   nothing else.
> - **The mechanism behind the two rows above it does not exist in the
>   repository.** Those rows are *"revoking that sensor's OS-level permission"*
>   and *"stops the perception stream"*. At `4e19ed1`, **no code path moves the
>   filesystem sensor to `failed`**:
>   - its `report_error` records and logs but does not transition
>     (`perception-engine/sensors/filesystem_sensor.py`);
>   - its `permission_status` is always `granted`;
>   - `nova-companion` reports no status to `perception-engine`;
>   - no test anywhere exercises `chmod`.
> - **Revocation detection stays OPEN (RS-3b).** Its owner must be ratified
>   before the 4F.8 TDD. 4F.7 does not implement it and does not claim it.
>
> Full record: §24.

### 4.2 AC-8 — UNCHANGED

> *"The same action category that is blocked at Level 1 auto-executes at Level 2
> for a low-risk case, purely by policy — no code path differs."*

**Not weakened, and deliberately not re-scoped to avoid CF-9 or CF-11.** Both are
taken as explicit dependencies instead (§5, §6).

**The complete intended path:**

```
cognitive-state trigger (Active Thought crosses its threshold)
   → DecisionRequest                        [cognitive-state-engine produces only this]
   → autonomy-engine decide()               [control plane]
   → Policy Engine      (deny-only; may lower requires_approval)
   → Permission Matrix  (deny-only)
   → Trust Engine       (CF-10: unavailable, fails closed)
   → single dispatch point reads requires_approval
        ├── True  → suggestion + existing approval surface        (Level 1)
        └── False → publish action.execute                        (Level 2)
   → action-engine       [execution / approval boundary owner]
        stage 3: ADR-032 identity-confidence gate  ← CF-9 REQUIRED
        → executed
```

| Clause | Discharged by | Dependency |
|---|---|---|
| *"the same action category"* | One `ActionType`, one `DecisionRequest` shape, run twice | — |
| *"blocked at Level 1"* | Already true and tested | — |
| *"auto-executes at Level 2"* | `autonomy-engine` publishes `action.execute` | **CF-9**, **CF-11** |
| *"for a low-risk case"* | `RiskLevel.LOW`; `risk_at_most` exists | — |
| *"purely by policy"* | The policy-derived `requires_approval` is the only differing input | — |
| *"no code path differs"* | §6.6's single-dispatch rule, test-enforced | — |

**Both criteria are provider-free** and inherit no deferral.

---

## 5. CF-9 — why AC-8 requires it, and what 4F builds

### 5.1 Why it is required

`action-engine` pipeline stage 3:

```python
# services/action-engine/src/nova_action_engine/domain/pipeline.py:181-189
confidence = await identity_port.get_confidence(user_id=action.requested_by)
policy = await repository.find_identity_confidence_policy(action.requested_by)
threshold = 1.0  # absent-policy fails closed: require maximum confidence
if policy is not None and risk.value in policy.minimum_confidence_by_risk:
    threshold = policy.minimum_confidence_by_risk[risk.value]
effective_confidence = confidence if confidence is not None else 0.0
if effective_confidence < threshold:
    ...  # denied
```

**The gate is not Critical-only.** With no policy row the threshold is **1.0 at
every risk level including LOW**, and `perception-engine`'s
`SINGLE_SIGNAL_CONFIDENCE_CEILING = 0.75` caps a real single-signal identity
below it. **AC-8's low-risk auto-execution is therefore denied at stage 3** until
a policy row can exist. Nothing in the repository can create one. That is CF-9.

The asymmetry is specific: `autonomy-engine` **has** a policy write surface
(`POST/PATCH/DELETE /v1/autonomy/policies`); `action-engine`'s
`IdentityConfidencePolicy` has **none**.

### 5.2 The minimum surface 4F requires

A write path to the table `action-engine` already owns, and nothing more:

| | |
|---|---|
| **Owner** | **`action-engine`** — unchanged. It owns `IdentityConfidencePolicy` (`domain/models.py:46`) and the table `action.identity_confidence_policy` |
| **Surface** | Create/read/update a policy for a user: minimum confidence per risk level. Fronted by `api-gateway`'s **existing** `/v1/action` prefix — **no new prefix** |
| **Identity** | Resolved **server-side** from `primary_user_id` (ADR-025, 4E's discipline). No caller-supplied `user_id` |
| **Persistence** | The existing table. **No new table, no second store, no duplicate model** |
| **Evaluation semantics** | **Byte-identical.** Stage 3's code is not modified by 4F |
| **Fail-closed** | **Unchanged.** Absent policy still means threshold 1.0 at every risk level |

### 5.3 What must be verified before CF-9 is ever closed

**4F implementing the capability does not close CF-9**, and no 4F document may
record it as closed. Closure requires a separate, explicit verification that
ADR-032 decision point 2 is satisfied in full:

1. A policy row can be created through a production surface — **and** read back
   by stage 3 in real Postgres.
2. The threshold is **per privileged capability or per capability class**, never
   a single hardcoded system-wide value (ADR-032's actual words).
3. Absent policy still fails closed at 1.0, proven by a negative control.
4. `perception-engine`'s `SINGLE_SIGNAL_CONFIDENCE_CEILING` is unchanged.
5. The Phase 4B Gate Review §0.3, Phase 4C's health record and master scope §4's
   register are each updated, with the closing evidence cited.

**Until all five hold, CF-9 stays OPEN** — including throughout 4F.

### 5.4 Relationship to D-4D-2

D-4D-2 ratified that CF-9 stays open and that `action-engine` keeps sole
ownership of `IdentityConfidencePolicy`. **4F contradicts neither.** Ownership
does not move; 4F adds the missing write path *in the owning engine*. What
changes is only that 4F, unlike 4D, has an acceptance criterion that cannot pass
without it.

---

## 6. Autonomy Level 2 — five distinct states

| # | State | Where | At `c04b58e` | 4F |
|---|---|---|---|---|
| **1** | **Defined** | `DEFINED_LEVELS` | **True already** | Nothing |
| **2** | **Selectable** | `SELECTABLE_LEVELS`, `require_selectable()` | **False** — raises `LevelNotSelectableError` → 422 | Add Level 2 to the set |
| **3** | **Policy-permitted** | `evaluate_policies()` → `requires_approval` | Machinery exists; **no `allow` effect and none added** | A policy may lower `requires_approval` for a bounded LOW-risk category |
| **4** | **Triggered** | **Nothing — CF-11** | **0 callers** of `decide()` | `cognitive-state-engine` (§6.2) |
| **5** | **Executing** | **Nothing** | `permits_execution()` is `False`; `_forbid_execution()` raises | Publish `action.execute` (§11.1) |

**A Level 2 flag alone must never create execution.** 4D's guard states it:
*"Enabling Level 2 is milestone 4F (decision D-1) and **requires an execution
path, not a flag**."* §16 control 3 requires that a flag-only change still fails.

### 6.1 CF-11 — the trigger, and why it is a dependency

Verified independently at `c04b58e`: **0** production callers of `decide()`, **0**
of `insert_suggestion`, and the 11-operation autonomy REST surface has **no
create-suggestion route** — `POST /suggestions/{id}/decide` decides an *existing*
one. **AC-8 cannot run without a trigger**, so CF-11 is a 4F dependency.

**4F implementing a producer does not close CF-11 by implication.** Closure
requires that the producer be *production-reachable* and demonstrated end to end;
until that is verified and recorded, **CF-11 stays OPEN**.

> **Added 2026-09-26 (4F.7 ratification, RS-6a, RS-6b and RS-1c), additively.**
>
> - **State 4, *Triggered*, remains a system-level property** evidenced by
>   records. There is no per-thought "triggered" state, enum, column or
>   persisted outcome.
> - **The status of state 4 at `4e19ed1`.** 4F.6 built the mechanism, and its
>   consumer runs in production. **The production end-to-end *Triggered* state
>   is not yet evidenced**, because two things are missing:
>   - `cognitive-state-engine` is not deployed;
>   - nothing in production promotes an Active Thought.
> - **What makes it evidenceable.** The production promotion driver, thought
>   ingestion and `ProposedAction` authorship now belong to a new slice,
>   **4F.P**, which comes before 4F.8 (§18).
> - **CF-11 stays OPEN.**
>
> Full record: §24.

### 6.2 `cognitive-state-engine` as trigger owner — the ratified boundary

| **MAY produce** | **MUST NOT** |
|---|---|
| A `DecisionRequest` | Publish `action.execute` |
| An action type | Call any `action-engine` execution endpoint |
| Subject / context | Invoke any actuator |
| A rationale | Bypass `autonomy-engine` |
| The cognitive-state evidence behind the request | Bypass the Policy Engine |
| | Bypass the Permission Matrix |
| | Bypass the Trust Engine |
| | Bypass `action-engine`'s approval/execution boundary |

**`autonomy-engine` remains the decision/control-plane owner.**
**`action-engine` remains the execution/approval boundary owner.**

§16 controls 6 and 11 enforce every prohibition by property, not by convention.

### 6.3 Where each gate applies

Policy Engine and Permission Matrix run **in `autonomy-engine`**, in the fixed
order `evaluate_gates()` already establishes, deny-only. The Trust Engine runs
after them and stays **unavailable** per CF-10 — it never becomes `0.0` or a
default number. `action-engine`'s own stages — risk estimation, the ADR-032
identity gate, approval, the append-only log — are unchanged and always run.

### 6.4 Where user approval remains required

Every risk **above LOW**, at any level. Every denied gate. Every case where
policy leaves `requires_approval = True`. **Absent policy means approval**, never
execution.

### 6.5 What Level 2 actually permits

LOW risk only · policy-permitted only · through `action-engine`'s unchanged
lifecycle only · never as a consequence of the level alone.

### 6.6 The single-dispatch rule — how *"no code path differs"* is true

One dispatch point reads `GateReport.requires_approval`. `True` → suggestion.
`False` → publish `action.execute`. **Everything upstream is identical between
the two runs** — same request shape, same gate order, same trust read, same log
entry. §16 control 4 asserts the two runs produce the same call sequence up to
that point.

---

## 7. `nova-companion` — component specification

| | |
|---|---|
| **Owner** | New. `companion/nova-companion/` ([doc 02](../../architecture/02-repository-and-folder-structure.md)'s repository tree: *"companion/ — Rust OS-level perception/action daemon"*), a Cargo workspace |
| **Produces** | Normalized sensor observations, submitted to `perception-engine` |
| **Consumes** | OS signals only |
| **Persistence** | **None.** It owns no store and writes no database |
| **API surface** | **None exposed.** It is a client, never a server |
| **Event Bus** | **None.** It never connects to NATS |
| **Security boundary** | Internal network only; no browser-reachable port; no actuator fires on its own initiative (§7.3) |
| **Failure behavior** | A failed sensor transitions `running → failed` and reports through the existing `SensorErrorReport`; the engine keeps serving |
| **Test strategy** | Cargo unit tests; the real binary drives the AC-7 E2E (§16) |

### 7.1 Sensors and actuators

Sensors: desktop/window-focus, clipboard, filesystem, process/system health.
**Only the filesystem sensor is on the CI acceptance path** (§16).
Actuators: terminal and window control — reachable **only** as `action-engine`
action types (§7.3).

### 7.2 Sensor Abstraction Layer integration

The `Sensor` Protocol is **unchanged**. Two closed literals widen additively:

```python
class SensorConfig(BaseModel):
    sensor_type: Literal["voice", "camera"]      # widens to admit companion types
class PermissionStatus(BaseModel):
    source: Literal["microphone", "camera"]      # widens to admit OS permissions
```

Internal to `perception-engine`; **no registered payload references either
type** (verified: 0 occurrences in `nova-contracts`). §16 control 8 pins the
widened set.

The existing lifecycle is exactly what AC-7 clause 2 needs:
`uninitialized → initialized → running → {paused, stopped, failed}`;
`paused → {running, stopped}`; `failed → initialized`. **`next_state` rejects
every undefined pair.**

### 7.3 Actuators go through the Action Principle lifecycle

Terminal and window control are **action types**, not autonomous capabilities.
Every existing stage applies unchanged. **4F adds no path that bypasses
`action-engine`.**

---

## 8. D-4F-5 — the transport already exists

**`POST /v1/perception/observations` was built in Phase 2D-C Priority 1 for
exactly this caller.** Its own docstring:

> *"No caller of this endpoint exists anywhere in this repository yet — no
> gateway or **companion-client** service exists (`apps/` is empty). This mirrors
> `communication-engine`'s own WebSocket endpoint precedent exactly: a real REST
> surface that simply waits for a not-yet-built caller, rather than a fabricated
> capture integration."*

**4F invents no transport. It becomes the first caller of an endpoint built for
it.** Properties, each checked:

| Requirement | Held by |
|---|---|
| Authentication/security boundary | `/v1/perception` is **not** fronted by `api-gateway` (verified: eight prefixes, none of them `/v1/perception`). The endpoint is reachable only on the internal Docker network — the same posture as every other engine, with authentication at the gateway per D-3 |
| Process isolation | A separate OS process speaking HTTP to an engine. **Not engine-to-engine** — the companion is not an engine, so ADR-004 is not engaged |
| Sensor abstraction preserved | The route calls `handle_observation_window`, which drives the registered `Sensor` and the real pipeline |
| No browser access | No gateway prefix is added, so no browser can reach it |
| No new engine-to-engine HTTP | None added |

### 8.1 The one shape question — scoped, not open-ended

The existing route takes an `application/octet-stream` **capture window** (audio
buffer or face crop) and runs addressee-signal detection. A filesystem event is
**structured**, not a byte window. 4F therefore adds a **second intake route on
the same internal surface** for structured observations, reusing the same sensor
lookup and the same publication path.

**This stays inside `perception-engine`'s own ownership**, adds no gateway prefix
and no new transport. Recorded here so the Gate Review checks it as a deliberate
addition rather than discovering it.

---

## 9. Perception normalization, enrichment and fusion

**Normalization** (`perception-engine`): debounce and coalesce high-frequency OS
signals; map platform identifiers to a stable vocabulary; **drop any signal whose
sensor is not `running`** — this is what makes AC-7's revocation clause true at
the pipeline level; attach no identity the sensor did not observe.

**Enrichment**: attach AC-7's *"known project"*. The only project identity is
`MemoryRecord.project_id`, and `perception-engine` **must not read
`memory-engine`'s database** (ADR-004; 4E §0.1.5 settled the identical question
for `digital-twin-engine` — the answer was the Event Bus). **When correlation
fails the observation is published without a `project_id`** — an honest unknown,
never a guess.

**Fusion**: extends the existing `domain/correlation_buffer.py` and
`domain/identity_fusion.py` rather than adding a parallel mechanism. **Fusion
never raises confidence above what its inputs support, and
`SINGLE_SIGNAL_CONFIDENCE_CEILING = 0.75` is unchanged** — ADR-032's gate reads
exactly that number (§5.1), so quietly strengthening a fused identity claim would
weaken a security gate by the back door.

---

## 10. Ownership matrix

| Fact | Owner | 4F |
|---|---|---|
| Raw OS signal | `nova-companion` | Produces; owns nothing |
| Sensor lifecycle, permission status | `perception-engine` | Extends |
| Normalized observation | `perception-engine` | Extends |
| World objects, context, prediction | `world-model-engine` | **Consumer only — zero changes** (§11.1) |
| Memories, `project_id` | `memory-engine` | **Read-only, via events** |
| Part 16 domains | `digital-twin-engine` | **Untouched** |
| Autonomy level, policy, permission grants, decision log | `autonomy-engine` | Extends |
| Action lifecycle, risk, approval, **`IdentityConfidencePolicy`** | **`action-engine`** | **Consumer + CF-9's write path in the owning engine.** No stage re-implemented |
| **Active Thoughts, Focus, Attention Layers** | **`cognitive-state-engine`** | **New, sole owner** |

**Two rules 4F must not break.** Cognitive state is *explicitly distinct* from
Phase 2D-C's session-scoped conversation memory — different lifetime, different
owner. ADR-030's *"Personality stores, Digital Twin learns"* is unchanged:
cognitive state is a **third** thing and neither engine's data moves.

---

## 11. Event Bus

### 11.1 One new subject, and it is genuinely required

| | |
|---|---|
| **Subject** | **`perception.workspace.observed`** — object-shaped, one segment, so it lands under the existing wildcard. Payload `PerceptionWorkspaceObservedPayload`; the full schema is §20.2 |
| **Producer** | `perception-engine`, from a `nova-companion` sensor |
| **Consumer** | `world-model-engine` — **already subscribed** via the `perception.*.observed` wildcard |
| **Why existing subjects are insufficient** | `make_perception_observed_handler` requires `object_id`/`entity_id`, `label`, `user_id`. **No existing perception payload carries any of them** — presence, identity and attention payloads are identity-shaped |
| **`PUBLIC_TOPICS`** | **No change** |
| **`ws-gateway`** | **No change** |
| **Browser access** | **None** |
| **`api-gateway`** | **No new prefix** |

**`world-model-engine` needs zero changes.** Its dispatch handler's own docstring
reserves this path: *"`perception-engine` (Phase 2D-B) never publishes an
object-shaped `perception.*.observed` payload (**that path is reserved for Phase
4's desktop-sensor extension**)."* A new subject lands under the wildcard, falls
through the `else` branch to the object handler, and creates a `WorldObject`. The
handler is also naturally idempotent — a repeat observation on an already-`ACTIVE`
object hits an undefined transition and returns.

### 11.2 `action.execute` — an existing contract gains its first producer

`action.execute` is registered (`ActionExecuteRequestPayload`), subscribed by
`action-engine`, and has **no production publisher**. 4F makes `autonomy-engine`
its first — the same *new-producer-on-an-existing-contract* shape 4E used, and
exactly D-4D-1's *"a genuine producer/consumer need."*

This requires adding `"action.execute"` to `autonomy-engine`'s currently-empty
`PUBLISHABLE_SUBJECTS`, which **necessarily retires 4D's control 8**
(*"this engine never calls the bus at all"*) in its present form. **Disclosed,
not silent**, and §16 control 6 replaces it with the tighter property: *this
engine may publish `action.execute` and nothing else.*

### 11.3 D-4F-6 — no cognitive-state subject

**`PUBLIC_TOPICS` is the sole browser realtime allow-list** — there is no
alternative approved realtime mechanism, verified in `ws-gateway`. So a realtime
cognitive-state panel would require a new public subject.

**It does not get one.** The panel reads **normalized cognitive state over
REST** (§12). A subject exists to be consumed, not to be complete (D-4D-1), and
no non-UI consumer of cognitive state exists. **No cognitive-state Event Bus
subject is added.**

### 11.4 What 4F must not do

No `autonomy.*` subject. No `TrustMetric` subject or RPC (CF-10 stays open). No
new `memory.*` or `digital_twin.*` subject. No wildcard widening. **No
`perception.*` entry in `PUBLIC_TOPICS`.**

### 11.5 D-4F-9 — one internal `autonomy.*` subject, for the 4F.6 trigger. **RATIFIED 2026-09-22.**

§11.4 reads *"No `autonomy.* ` subject."* §13 records that
`cognitive-state-engine` *"publishes nothing."* §12 records that
*"`autonomy-engine` gains no new route."* **All three stand as written, and
none is deleted.** This section adds a bounded exception to the first two.

**Why the exception is needed.** §13's own *Produces* row requires
`cognitive-state-engine` to deliver **`DecisionRequest`s into
`autonomy-engine`** (§6.2), and 4F.6's preparation established that the three
statements above leave **no mechanism** by which it can: the engine has both
allow-lists empty, only a health route and no outbound client;
`autonomy-engine` has no intake route and an empty `SUBSCRIBABLE_SUBJECTS`;
the registry contains no subject that fits; and **no Python engine in this
repository calls another over HTTP** — engine-to-engine is the Event Bus,
exclusively. The constraints were jointly unsatisfiable.

**What §11.4's prohibition was protecting.** It sits beside §11.3, whose
subject is **browser-reachable and consumer-less** subjects: *"a subject
exists to be consumed, not to be complete"*, and *"`PUBLIC_TOPICS` is the sole
browser realtime allow-list."* The prohibition guards the **public surface**
and against subjects **nobody consumes**. **It was not written against an
internal, server-side subject with exactly one consumer** — the same document
permitted `action.execute` in §11.2 on precisely that basis.

**The exception, and its bounds.** **One** subject,
**`autonomy.decision.requested`**, is approved **for 4F.6 specifically**:

- **Internal only.** **Never** added to `PUBLIC_TOPICS`, which stays at
  **18**. Never browser-reachable. Not a public API. No gateway prefix.
- **Exactly one server-side consumer**, `autonomy-engine`.
- Registry **119 → 120**.
- **This is not a general relaxation.** §11.4 otherwise stands: no
  `TrustMetric` subject or RPC (**CF-10 stays open**), no new `memory.*` or
  `digital_twin.*` subject, no wildcard widening, no `perception.*` in
  `PUBLIC_TOPICS`.

**The two statements this amends, and their replacements.** Each retirement is
**disclosed and replaced by a tighter, test-enforced property** — the
precedent §11.2 set when `action.execute` retired 4D's control 8:

| Amended | Original wording | Replacement property |
|---|---|---|
| §13, Event Bus row | *"publishes nothing (§11.3)"* | *"publishes `autonomy.decision.requested` and **nothing else**"* |
| §11.4, first clause | *"No `autonomy.* ` subject."* | *"**Exactly one** `autonomy.* ` subject exists; it is internal, server-side, single-consumer, and **not** in `PUBLIC_TOPICS`"* |

**§12 is not amended.** *"`autonomy-engine` gains no new route"* remains true
and is now **strengthened** by this decision: the trigger arrives over the
bus, so no route is added. Its original sentence stands unqualified.

**§13's *Produces* row is unchanged** — it already said
`cognitive-state-engine` produces `DecisionRequest`s into `autonomy-engine`.
This amendment supplies the mechanism that sentence always presupposed.

*(Preserved per protocol principle 4: the original clauses of §11.4 and §13
are quoted above verbatim and are not edited in place. This section is the
dated note that explains what changed and why.)*

> **Provenance of §11.5 — appended 2026-09-26 (4F.7 ratification, RS-10),
> additively.**
>
> - **Source.** The text above is TDD 4F.6 §14's ratified D-4F-9 amendment,
>   copied **verbatim**. The only change is the removal of its blockquote
>   markers ([`10-tdd-4f6-initiative-trigger.md`](10-tdd-4f6-initiative-trigger.md),
>   lines 845–901 at `4e19ed1`).
> - **Why it is appended now.** TDD 4F.6 §14 says the text was *"to be appended
>   additively to TDD 4F"*. That append was **not performed** when 4F.6 merged
>   (PR #37, `4e19ed1`).
> - **What was not edited.** §11.4 and §13 are unchanged, exactly as D-4F-9
>   itself requires.
> - **What D-4F-9 does not amend.** §16.1 control 11 still reads *"publishes
>   nothing"*. 4F.6 retargeted that control **in code**, as
>   `test_control_11_this_engine_publishes_the_trigger_and_nothing_else` (4F.6
>   completion record §3.3), but D-4F-9's own table does not name control 11.
>   That residual is recorded, not resolved, in §24.

---

## 12. REST, realtime, and the browser

**`cognitive-state-engine`** exposes a read surface for the panel, fronted by a
**new `/v1/cognitive-state` `api-gateway` prefix** (D-6, forwarded 1:1).
**Identity resolved server-side** from `primary_user_id` — 4E's discipline
adopted from the start, so 4F never creates a caller-supplied-`user_id` route.
**It exposes only normalized state intended for the UI — never raw sensor
events.**

**`action-engine`** gains CF-9's policy surface under its **existing**
`/v1/action` prefix.

**`perception-engine`** gains **no** gateway prefix. AC-7 clause 2's panel
rendering is served from the Cognitive State read surface, which carries sensor
status as normalized state.

**`autonomy-engine`** gains no new route: selecting Level 2 is an existing
operation whose 422 stops being returned for `2`.

**Realtime:** `ws-gateway` unchanged; `PUBLIC_TOPICS` unchanged at 18; no engine
gains a browser-facing socket; the companion has none.

> **Added 2026-09-26 (4F.7 ratification, RS-3a and RS-4a–RS-4d),
> additively.** Nothing above is edited.
>
> **How sensor status reaches this read surface (RS-3a).**
>
> - `perception-engine` publishes the **existing** subject
>   `perception.sensor.health_changed` on its existing sensor lifecycle
>   transitions.
> - `cognitive-state-engine` subscribes to it as an **internal input**. Its
>   subscribe allow-list changes from empty to exactly that one subject.
> - `cognitive-state-engine` serves the **normalized** sensor state under
>   `/v1/cognitive-state`.
> - **No new subject is added, and `PUBLIC_TOPICS` stays byte-identical.**
>
> **An accepted consequence, recorded rather than hidden.**
> `perception.sensor.health_changed` has been in `PUBLIC_TOPICS` since 4B. Once
> `perception-engine` publishes it, `ws-gateway` also delivers it to subscribed
> browsers, and the Events panel records every frame. RS-3a accepts this as an
> architectural consequence.
>
> **The read surface (RS-4a–RS-4c).**
>
> - `GET`-only, with identity resolved server-side from `primary_user_id`.
> - It carries Active Thoughts with every Part 6 field, the attention layer,
>   Focus entries with `score` and `signals_used`, and normalized sensor
>   state.
> - `proposed_action` is rendered **as a proposal only**.
> - **No autonomy decision data** is included.
>
> **Deployment (RS-4d)** is part of 4F.7.
>
> The exact contract is TDD 4F.7
> ([`11-tdd-4f7-cognitive-state-panel.md`](11-tdd-4f7-cognitive-state-panel.md)).
> Full record: §24.

---

## 13. `cognitive-state-engine` — component specification

| | |
|---|---|
| **Owner** | New engine, scaffolded by `tools/scaffold-engine.py` |
| **Produces** | Cognitive state (Active Thoughts, Focus, Attention Layers) and **`DecisionRequest`s** into `autonomy-engine` (§6.2) |
| **Consumes** | Perception observations and World Model context, **via the Event Bus only** |
| **Persistence** | A new `cognitive_state` schema; additive tables only; **zero existing tables altered** |
| **API** | Read-only panel surface + a Level-2-relevant read; server-side identity |
| **Event Bus** | Subscribes to existing subjects; **publishes nothing** (§11.3) |
| **Security boundary** | §6.2's eight prohibitions, each test-enforced |
| **Failure behavior** | §15 |
| **Test strategy** | Unit (thought lifecycle, focus selection, attention transitions), integration, `real_infra` (new matrix row), contract (§16) |

Bible Part 6, implemented as named: **Active Thoughts** with priority,
confidence, dependencies, estimated completion, related memories, related
projects and current progress; the **Focus System** ranking by user activity,
task importance, deadlines, system health, current risks, agent workload and
learning opportunities; **five Attention Layers** — Immediate, Active, Passive,
Dormant, Archived — with thoughts moving between them.

> **Added 2026-09-26 (4F.7 ratification, RS-1a, RS-1b, RS-4c and RS-2),
> additively.** The table above is not edited. For its **API** row and for who
> moves thoughts between layers:
>
> - **RS-4c.** *"A Level-2-relevant read"* means the thought's **persisted
>   `proposed_action`**. It is rendered as a proposal, **never** as
>   triggered, decided, executing or executed. No new persistence is added for
>   it.
> - **RS-1b.** The *"Read-only panel surface"* is **strictly** read-only.
>   4F.7 does not:
>   - create Active Thoughts;
>   - author `ProposedAction`s;
>   - promote thoughts, or call `promotion_orchestration.promote_thought`;
>   - add any write route under `/v1/cognitive-state`.
> - **RS-1a.** Production promotion of an Active Thought between Attention
>   Layers is owned by **`cognitive-state-engine`**. No other engine performs
>   promotion decisions; other engines only supply inputs through existing
>   Event Bus subjects.
> - **RS-2.** Promotion, thought ingestion and `ProposedAction` authorship
>   belong to the new slice **4F.P** (§18). The *Consumes* row's *"Perception
>   observations and World Model context"* stays a statement of **where**
>   inputs may come from. **Which subjects, and how they map to a thought,
>   remain OPEN** for 4F.P's TDD. RS-3a's sensor-health subscription is a
>   Perception input to the **read surface**, not to thought creation.
>
> Full record: §24.

---

## 14. Relationship between perception, memory, Digital Twin and cognitive state

Perception observes; the World Model holds *what is*; Memory holds *what
happened*; the Digital Twin holds *what the user is like* (Part 16's eleven
domains, 4E); **cognitive state holds what NOVA is currently thinking about.**

**Cognitive state reads all three and owns none of them.** It writes only its own
schema. It never writes a Part 16 domain, never writes a memory, never writes a
world object. §16 control 11 asserts it.

---

## 15. Failure and degraded-state semantics

| Condition | Behaviour |
|---|---|
| Companion absent or crashed | Sensors report unavailable; the engine keeps serving; the panel shows the sensor stopped, not a fabricated reading |
| OS permission revoked | `running → failed`; **normalization drops further signals**; the panel shows it. **This is AC-7 clause 2** |
| Project correlation fails | Observation published **without** `project_id` (§9) |
| Trust input unavailable (CF-10) | Stays unavailable. **Never `0.0`, never a default** |
| Policy engine raises | **Deny** — already true; 4F does not soften it |
| No identity-confidence policy | **Threshold 1.0, denied.** Fail-closed, unchanged (§5.2) |
| No autonomy policy | `requires_approval` stays `True` → approval, never execution |
| Risk above LOW at Level 2 | Approval required regardless of level (§16 control 5) |
| Outbox dispatch delayed | AC-7 has a 5 s budget against a 10 s cron worst case — **§20.1 is the residual risk**, stated not hidden |

---

## 16. Test strategy, CI, and the AC-7 acceptance path

### 16.1 Negative and security controls

| # | Control |
|---|---|
| 1 | Exactly **one** new Event Bus subject; the registered-subject count moves by exactly one |
| 2 | **`PUBLIC_TOPICS` byte-identical at its 18 strings** |
| 3 | **Level 2 cannot execute by flag alone** — `permits_execution` returning `True` with §11.2's publication removed must still fail |
| 4 | **No code path differs** — Level-1 and Level-2 runs produce the same call sequence up to the single dispatch point |
| 5 | **Level 2 never auto-executes above LOW risk**, at any policy setting |
| 6 | **`autonomy-engine` publishes `action.execute` and nothing else** |
| 7 | **No cross-engine import, no engine-to-engine HTTP** — import-linter plus an AST check |
| 8 | **The widened sensor literals are exactly the ratified set** |
| 9 | **The companion opens no browser-reachable port and no NATS connection** |
| 10 | **CF-10 unresolved** — 4E's five sub-properties re-asserted verbatim |
| 11 | **`cognitive-state-engine` writes only its own repository**, publishes nothing, and violates none of §6.2's eight prohibitions |
| 12 | **No fake clock, no time simulation, no fabricated sensor reading, no injected Event Bus message and no mocked transport** anywhere in 4F |
| 13 | **`action-engine` stage 3 evaluation semantics are byte-identical**; absent policy still denies at 1.0 |
| 14 | **AC-7's E2E does not align to the dispatcher cron and does not retry** (§20.1) — the measured interval starts at the real filesystem event and a violation fails the test |
| 15 | **`perception.workspace.observed` is absent from `PUBLIC_TOPICS`**, is not exposed by `ws-gateway`, and a browser subscription to it is **rejected** (§20.2 requirement 11) |

### 16.2 AC-7's CI acceptance path — D-4F-8, ratified

**The modality is the filesystem sensor.** The runner is `ubuntu-latest` with no
`DISPLAY`, no Xvfb, no desktop session and no IDE. **IDE/window-focus sensing is
explicitly outside the Phase 4F CI acceptance path** and is not claimed as
verified by it.

**The acceptance path uses, end to end:** a **real `nova-companion` process** · a
**real filesystem observation** · a **real project-directory event** · the
**genuine perception pipeline** (`POST /v1/perception/observations` →
`handle_observation_window` → the registered `Sensor`) · the **genuine Event Bus
path** · the **genuine `world-model-engine` consumer** · **real persisted state**
· and **measured elapsed wall-clock time**.

**Explicitly forbidden, each a named control:** fake sensor readings · fake
clocks · `freezegun` · `time_machine` · monkeypatched `datetime` · direct Event
Bus injection · mocked perception publishers · artificial timestamps · any
bypass around `nova-companion` or `perception-engine`.

**Permission revocation uses a genuine filesystem permission change** (`chmod` on
the watched directory) and must demonstrate that the **real** perception stream
stops.

**The latency clause is measured honestly — §20.1 is binding here.** The E2E does
**not** align its measurement window to the 10-second dispatcher cron and does
**not** use a bounded retry. Elapsed time runs from the real filesystem event to
the observable World Model result, across the unchanged outbox and the unchanged
dispatcher. **If the real measured latency exceeds 5 seconds the test fails and
reports the figure** — the violation is exposed, not normalized, and AC-7 is not
weakened to accommodate it.

### 16.3 Tiers

Unit · integration · `real_infra` (ADR-033; a new `real-infra-checks.yml` row for
`cognitive-state-engine`) · contract (§16.1) · **Cargo** for the companion ·
browser E2E for AC-7 and AC-8.

Docker is unreachable in the implementation environment, so — as in 4D and 4E —
**every real-infrastructure and browser result is CI's and must be labelled as
such.**

### 16.4 D-4F-7 — Rust in CI, minimally

No Rust toolchain, `cargo` job or non-Python artifact exists in CI today.
**The minimal addition, using existing mechanisms:**

1. **`build-and-scan.yml`**: one matrix entry for the companion's Dockerfile. The
   matrix is already *"one entry per deployable Dockerfile"* with the path as a
   matrix field — generalized beyond `services/` by Phase 4C's D-5 — so this
   needs **no workflow restructuring**, and Trivy coverage follows automatically.
2. **`pr-checks.yml`**: one step running `cargo fmt --check`, `cargo clippy` and
   `cargo test` for the companion workspace, alongside the existing
   non-workspace steps (`tools/tests`, Agent Packages) that already establish the
   pattern.

**No global CI policy change.** Turborepo and `uv` are untouched; the companion is
neither a pnpm nor a uv workspace member.

---

## 17. SLOC — methodology change and headroom

**Ratified: the measured scope is extended to include `companion/`.** The metric
must not depend on whether code lands in a directory the historical scope
happens to exclude. The change is recorded in
[`project-health-master.md`](../../project-health/project-health-master.md) §2 as
a methodology entry when 4F's health record is written.

**Baseline at `c04b58e`**, `cloc` v2.06 `--skip-uniqueness --quiet` from pristine
`git archive`:

| Scope | Value |
|---|---|
| Comparable | **35,733** |
| Wider | **41,074** |
| Full (`+ apps/*/src`) | **44,706** |
| **4F scope (`+ companion/`)** | **44,706** — the directory does not exist yet |

**Headroom to 50,000: 5,294.**

| Component | Estimate |
|---|---|
| `cognitive-state-engine` (3 subsystems; `autonomy-engine` = 1,422 for reference) | 1,400–2,000 |
| Perception normalization + enrichment + fusion + sensors | 600–1,000 |
| Autonomy Level 2 + dispatch + publisher | 150–300 |
| CF-9 write surface | 100–200 |
| `cognitive-state/` panel | 300–400 |
| **`nova-companion` (Rust)** | **1,000–2,500** |
| AC-7 / AC-8 test infrastructure | **0 — tests are outside every scope** |
| **Projected total** | **47,256 – 49,106** |

**Likely under 50,000, but inside one milestone's margin of it.**

**If 4F crosses 50,000** — SAD 15 §10, treated as a **hard gate**: feature
development **pauses automatically**; 4F does not continue into later feature
work; the **Engineering Review Milestone** (12 items: architecture, dependency,
performance, security, refactoring, dead code, duplication, technical debt,
database, Event Bus, API consistency, documentation) is filed under
`docs/roadmap/architecture-reviews/` and **requires explicit approval before
feature development resumes**. It lands between 4F's closure and Phase 4's
promotion to `main`. **Code is never moved or reduced to game the metric.**

---

## 18. Milestone decomposition

Sequential, each slice independently verifiable. **4F is one milestone; these are
slices within it, not new milestones** — the Phase 4 set remains 4A–4F.

| Slice | Contents | Proves |
|---|---|---|
| **4F.1** | `cognitive-state-engine` domain + persistence + migration | Part 6's three subsystems; `real_infra` |
| **4F.2** | Perception extension: literal widening, structured intake (§8.1), normalization, enrichment, fusion, **and the `perception.workspace.observed` contract — not complete until all eleven of §20.2's requirements are documented and tested** | Observation reaches the World Model; the subject is provably internal |
| **4F.3** | `nova-companion`: Cargo workspace, filesystem sensor, intake client, Dockerfile, CI (§16.4) | A real OS signal enters the pipeline |
| **4F.4** | CF-9's write surface in `action-engine` | Stage 3 can pass for LOW risk, fail-closed unchanged |
| **4F.5** | Level 2: selectable, policy-permitted, single dispatch, `action.execute` publication | The five states, separately |
| **4F.6** | The trigger: `cognitive-state-engine` → `DecisionRequest` | CF-11's producer, under §6.2 |
| **4F.7** | `cognitive-state/` panel + `/v1/cognitive-state` prefix | AC-7 clause 2 visibly |
| **4F.8** | **The final implementation slice.** E2E: AC-7 (5 s, **honestly measured per §20.1** — no cron alignment, no bounded retry) and AC-8 (both levels). Performs the real acceptance verification | Both criteria in a browser, or the evidence that AC-7 cannot be met |

> **Amended 2026-09-26 (4F.7 ratification, RS-1c), additively.** The table
> above is preserved exactly as written.
>
> - **4F remains one milestone.** One implementation slice is added **before
>   4F.8**.
> - **4F.8 is still the final implementation slice**, so its row stays
>   accurate.
> - **The milestone now has nine slices.** Dated records that say *"eight
>   slices"* were accurate when written and are not edited (protocol principle
>   4).
>
> | Slice | Contents | Proves |
> |---|---|---|
> | 4F.1 – 4F.6 | Unchanged | Unchanged |
> | **4F.7** | The row above, read with RS-1b, RS-3a, RS-3b and RS-4a–RS-4d (§24). It covers: a **strictly read-only** `GET` surface under `/v1/cognitive-state`, carrying Active Thoughts, Attention Layers, Focus, normalized sensor state, and `proposed_action` as a proposal only; the `api-gateway` prefix; the `cognitive-state/` panel; deployment wiring; `perception-engine` publishing the existing `perception.sensor.health_changed` on existing lifecycle transitions; and `cognitive-state-engine` subscribing to it. **No write path of any kind** | Only §4.1's row *"visibly … in the panel"*: the panel renders the normalized sensor state actually reported. **Not** OS-level revocation (RS-3b, OPEN) |
> | **4F.P** *(new, 2026-09-26)* | **The production promotion slice.** It covers the production promotion driver in `cognitive-state-engine`, thought ingestion from existing Event Bus subjects, and `ProposedAction` authorship under an explicitly ratified rule. **Its TDD must explicitly ratify, before implementation:** the promotion policy; the thought-ingestion mapping; the `ProposedAction` authorship rule; the CAS transition semantics (RS-7); and A-4F6-3 Layer 2 logical deduplication | That the 4F.6 trigger gains a production caller (4F.6 finding F-6). **It closes nothing by itself.** CF-11 still needs 4F.8's end-to-end demonstration and 4F closure's recorded evidence (TDD 4F.6 §15.1) |
> | 4F.8 | Unchanged | Unchanged |
>
> **Two notes on the new slice:**
>
> - **"4F.P" is a label, not a number.** It keeps the identifier 4F.8, which
>   earlier TDDs and records cite, unchanged. RS-1c ratifies only *"before
>   4F.8"*, so its order relative to 4F.7 is not fixed here.
> - **4F.P is not started.** It has no TDD and no branch, and nothing in this
>   amendment implements it.
>
> **Not assigned to any slice by this amendment.** The owner of OS-level
> revocation detection (RS-3b) must be ratified before the 4F.8 TDD.

---

## 19. Ratified decisions — 2026-09-15

| ID | Decision | Status |
|---|---|---|
| **D-4F-1** | **Option D.** AC-7 re-scoped 1 s → 5 s, modality-neutral wording. **The transactional outbox architecture is unchanged** — no push-triggered dispatch, no shortened cron, no direct-publish bypass | **RATIFIED** |
| **D-4F-2** | **Option A.** CF-9 is an explicit 4F dependency; the write surface belongs to `action-engine`; no second store; fail-closed and evaluation semantics unchanged; **CF-9 not closed by implication** (§5.3) | **RATIFIED** |
| **D-4F-3** | `cognitive-state-engine` owns the initiative trigger, under §6.2's prohibitions. `autonomy-engine` remains control plane; `action-engine` remains execution/approval boundary | **RATIFIED** |
| **D-4F-4** | Internal perception bus path. One object-shaped `perception.<name>.observed`. **`PUBLIC_TOPICS` unchanged; no `/v1/perception` gateway prefix; no raw sensor stream to the browser** | **RATIFIED** |
| **D-4F-5** | The transport **already exists** — `POST /v1/perception/observations`, built in 2D-C for a companion client. One structured-intake route added on the same internal surface (§8.1) | **RATIFIED** |
| **D-4F-6** | **No cognitive-state Event Bus subject.** REST read surface only | **RATIFIED** |
| **D-4F-7** | Minimal Rust CI: one `build-and-scan` matrix entry, one `pr-checks` step. No global CI policy change | **RATIFIED** |
| **D-4F-8** | Filesystem sensing is the CI acceptance modality. **IDE/window-focus is explicitly outside the CI acceptance path** | **RATIFIED** |

---

## 20. Two clarifications ratified 2026-09-15 (second pass)

Both were carried as open questions in the first ratification. **Neither is open
any longer.**

### 20.1 AC-7 is an honest 5-second criterion — the measurement rule

**AC-7's wording stands exactly as §4.1 states it. The 5-second budget is not
negotiable and is not to be made reachable by test construction.**

The first ratification's §20.1 suggested the E2E could *"either align its
measurement window to the dispatch cycle or accept a bounded retry."*
**That suggestion is withdrawn.** Both techniques would make the test pass
without the system being faster, which is a way of hiding a latency violation
rather than measuring one.

**The E2E MUST measure real elapsed wall-clock time across the genuine chain:**

```
real filesystem event
  → nova-companion sensor
  → perception-engine
  → POST /v1/perception/observations        (the existing 2D-C transport, §8)
  → transactional outbox
  → the existing 10-second cron dispatcher   (unchanged)
  → Event Bus
  → world-model-engine
  → observable Digital Twin / Cognitive State state
```

**Forbidden, each a named control (§16.1 control 12 and control 14):**

- aligning the measurement window to the dispatcher's cron cycle;
- a bounded retry, a re-run, or any scheduling technique that avoids the
  worst-case dispatch latency;
- fabricated timestamps, fake clocks, `freezegun`, `time_machine`, monkeypatched
  `datetime`, or `sleep`-based compensation;
- injected Event Bus messages, mocked transport, or fabricated sensor events;
- changing the outbox architecture, shortening the cron, adding a direct-publish
  path or introducing push-triggered dispatch **in order to satisfy this
  criterion**.

**What happens if the measured latency exceeds 5 seconds.** The test **must fail
and must expose the real measured figure.** The violation is neither hidden nor
normalized, and the criterion is not weakened to accommodate it. If the current
architecture cannot honestly satisfy AC-7, that is reported as a **blocking Gate
Review finding** — the same disposition Phase 4E gave its own AC-6 blocker before
it was resolved by ratified decision, not a quiet re-scoping.

**The known risk, stated plainly.** The dispatcher's worst case is ~10 s and its
mean is ~5 s, so **a run beginning just after a tick is expected to exceed the
budget.** 4F.8 will therefore either demonstrate that the real chain meets 5 s, or
produce the evidence that it cannot. **Both outcomes are acceptable outputs of
4F.8; only a test that conceals the answer is not.**

### 20.2 The perception subject contract — ratified, and pinned by 4F.2

**Subject:** **`perception.workspace.observed`** — one segment, so it lands under
`world-model-engine`'s existing `perception.*.observed` wildcard and falls
through `make_perception_dispatch_handler`'s `else` branch to the object handler,
with **zero world-model changes**.

**Payload:** `PerceptionWorkspaceObservedPayload` in
`packages/nova-contracts/src/nova_contracts/events/perception.py`, registered with
`@register_payload("perception.workspace.observed")`, matching the existing
`Perception<X>ObservedPayload` convention.

| Field | Type | Required | Why |
|---|---|---|---|
| `object_id` | `str` | **Yes** | `make_perception_observed_handler` reads it via `_text_from(payload, "object_id", "entity_id")`, which requires a **non-empty** string. **A file-path hash** — `WorldObject`'s own docstring names *"a window handle, **a file path hash**, a project UUID"* as the sanctioned handle forms, so **the raw path never travels** |
| `label` | `str` | **Yes** | Read via `_text_from(payload, "label", "object_label")`; the handler defaults to `"Unknown"` when absent, and 4F does not rely on that default |
| `user_id` | `UUID` | **Yes** | Read via `_uuid_from(payload, "user_id")`; the handler skips the event without it |
| `object_type` | `Literal["project"]` | **Yes** | Distinguishes this from any future object-shaped observation; a closed literal so a new kind cannot appear unnoticed |
| `project_id` | `UUID \| None` | No, default `None` | §9's enrichment result. **`None` when correlation fails** — an honest unknown, never a guess |
| `sensor_id` | `str` | **Yes** | Provenance: which registered `Sensor` observed it |
| `observed_at` | `datetime` | **Yes** | The **real** OS event time, and the start of AC-7's measured interval. A genuine timestamp from a genuine event — §20.1 forbids fabricating it |

**Producer:** `perception-engine`, from a `nova-companion` filesystem sensor.
**Consumer:** `world-model-engine`, via the existing wildcard subscription.

**Why existing perception subjects are insufficient:** the object handler needs
`object_id`, `label` and `user_id`. Every existing perception payload —
presence, identity, attention, wake, addressee-signal, consent, sensor-health —
is **identity-shaped or sensor-shaped and carries none of the three**. Verified:
zero occurrences of `object_id`, `entity_id` or `object_label` in
`events/perception.py`.

**Why it is internal only:** it carries raw-ish sensor provenance
(`sensor_id`, `observed_at`, a path hash). The browser has no business seeing
sensor events; it sees **normalized state** through the Cognitive State REST
surface (§12). **It is not added to `PUBLIC_TOPICS`, `ws-gateway` does not expose
it, and no `/v1/perception` gateway route is added.**

**4F.2 is not complete until all eleven of these are documented and tested:**

| # | 4F.2 completion requirement |
|---|---|
| 1 | Exact subject name, as registered |
| 2 | Exact payload schema, field by field |
| 3 | Producer named and tested |
| 4 | Consumer named and tested |
| 5 | Why existing perception subjects are insufficient, evidenced |
| 6 | Why the subject is internal only |
| 7 | **Confirmation it is NOT in `PUBLIC_TOPICS`** — asserted, not stated |
| 8 | **Confirmation `ws-gateway` does not expose it** |
| 9 | **Confirmation raw sensor events are not browser-visible** |
| 10 | Contract/schema validation against the registry |
| 11 | **A negative test proving browser/public access is rejected** |

**No additional perception subject** is introduced without a demonstrated
producer/consumer need (D-4D-1). **No cognitive-state subject** (§11.3). **No
`/v1/perception` route.** **No `PUBLIC_TOPICS` change.**

---

## 21. Documentation, Gate Review and closure requirements

**Documentation** — this TDD kept current; `docs/project-health/phase-4f.md`
(23 fields); the master timeline row; **the §2 SLOC methodology entry** (§17);
the roadmap 4F row; the master scope's 4F closure note; the
`cognitive-state-engine` and `nova-companion` READMEs. Corrections additive per
protocol §0.3.4.

**Gate Review** — `docs/roadmap/architecture-reviews/phase-4f-*-gate-review.md`,
following 4D's and 4E's shape, and additionally required to cover:

1. The **five Level-2 states individually**, each with its own evidence.
2. **AC-7's latency as a measured number**, and an explicit statement that
   IDE/window-focus sensing was **not** the acceptance modality.
3. **CF-9, CF-10 and CF-11 each dispositioned separately** — CF-9 against §5.3's
   five-point checklist, CF-11 against §6.1, CF-10 unchanged and open.
4. The **SLOC gate** (§17), including whether 50,000 was crossed and, if so, the
   Engineering Review Milestone.
5. Confirmation that **`PUBLIC_TOPICS` is byte-identical** and exactly one
   Event Bus subject was added.
6. Confirmation that the companion reaches no browser and no NATS.

**Closure** — protocol §3.2's eleven GO conditions and all ten
`definition-of-done.md` items; merged into `phase-4` by a **normal two-parent
merge**; `phase-4f` preserved; `main` untouched at `7e273e6`.

**Phase 4F is the last Phase 4 milestone**, so its closure must leave **every**
Phase 4 carry-forward explicitly dispositioned — including the `README.md` Phase
4 status line that 4C, 4D and 4E each carried forward — before Phase 4's own Gate
Review and the single `phase-4 → main` promotion.

---

## 22. Consistency audit

Performed against the repository at `c04b58e`.

| Checked against | Result |
|---|---|
| **Completion protocol** | sha256 verified from `origin/main`; §21 maps to §3.2's eleven conditions and the ten DoD items; corrections additive per §0.3.4 |
| **Phase 4 master scope** | 4F's deliverables match §5's 4F entry; AC-7 revision recorded as a supersession (§4.1); the milestone set stays 4A–4F; §13's non-goals honoured (§2.1) |
| **Phase 4D closure** | D-1 respected (Level 2 is 4F's); D-4D-1 respected (no contract without a genuine need — §11.1, §11.2); **D-4D-2 not contradicted** (§5.4) |
| **Phase 4E closure** | Server-side identity, fail-closed allow-lists, additive contracts, measured-number assertions, and the new-producer-on-an-existing-contract shape all carried forward |
| **2D-B Sensor Abstraction Layer** | `Sensor` Protocol unchanged; lifecycle unchanged; only two literals widen (§7.2) |
| **`perception-engine`** | Intake route already exists (§8); outbox path unchanged; `SINGLE_SIGNAL_CONFIDENCE_CEILING` unchanged (§9) |
| **`world-model-engine`** | **Zero changes.** Wildcard subscription and object handler already reserve this path (§11.1) |
| **`memory-engine`** | Read-only via events; no schema change; no DB access across the boundary (§9) |
| **Digital Twin** | Untouched (§10) |
| **`autonomy-engine`** | Gate order, deny-only policy, `_forbid_execution` and the five states preserved (§6); control 8 retired **explicitly** and replaced (§11.2) |
| **`action-engine`** | Ownership unchanged; stage 3 semantics byte-identical; CF-9's surface added in the owning engine (§5.2) |
| **Event Bus contracts** | Exactly one new subject; `action.execute` reused; `PUBLIC_TOPICS` unchanged; no `autonomy.*`, no `TrustMetric`, no wildcard widening (§11.4) |

**No contradiction found.** The one deliberate reversal — 4D's control 8 — is
disclosed in §11.2 and replaced with a tighter property rather than dropped.

---

## 23. Status

**RATIFIED and implementable**, slice by slice per §18. **No architectural
ambiguity remains** — §20's two formerly-open questions are both closed by the
second ratification. No `phase-4f` branch exists; no implementation scaffolding
has been generated; no implementation file has been modified. **Implementation
does not begin until the user gives an explicit GO.**

> **Added 2026-09-26, additively.** The paragraph above is preserved as written.
> It was true at `c04b58e`; since then:
>
> - **Slices 4F.1–4F.6 are implemented and merged** into `phase-4`, whose head
>   is `4e19ed1`.
> - **A third ratification (§24) settles eleven decisions**, RS-1 … RS-11, for
>   4F.7 and for the milestone.
> - **It adds the slice 4F.P** before 4F.8 (§18).
> - **It appends D-4F-9 as §11.5.**
> - **4F.7's slice TDD is prepared** as
>   [`11-tdd-4f7-cognitive-state-panel.md`](11-tdd-4f7-cognitive-state-panel.md).
>
> **4F.7 implementation does not begin until the user gives an explicit GO.**

---

## 24. Ratified decisions — 2026-09-26 (third ratification: the 4F.7 packet)

### 24.0 Baseline, verified before anything was ratified

| Ref | Value |
|---|---|
| `origin/phase-4` | **`4e19ed19876f2c76dd6f6591b1aa9cc778dd2e89`** — the merge of PR #37 (4F.6) |
| Its first parent | `4f1602ac086c421fc1a6beb54b7effb10f3ef6d9` — PR #36's merge, the baseline TDD 4F.6 was prepared against |
| `origin/main` | **`7e273e62e942ecd5528ca807e65933d6bb675669`**, which is also `merge-base(origin/phase-4, origin/main)` |
| TDD 4F.6 and its completion record | Both reachable from `origin/phase-4` (`git merge-base --is-ancestor`; `git cat-file -e`) |
| Protocol | sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`, 1131 lines, read from `origin/main`, byte-identical on `phase-4` |

**The two recorded values are not in conflict.** `4f1602a` is `phase-4`
*before* PR #37, and `4e19ed1` is `phase-4` *after* it.

### 24.1 How to read this section

- **Every RS row below is RATIFIED**, in the wording the user approved.
- **No ratified decision was contradicted by repository evidence.**
- **Where a decision has a consequence another document did not anticipate,**
  the consequence is recorded under that decision. It is not silently
  absorbed.
- **Nothing here closes CF-9, CF-10 or CF-11.**

### 24.2 Promotion — ownership, 4F.7's scope and the new slice

**RS-1a — RATIFIED.** Production promotion of an Active Thought between
Attention Layers is owned by `cognitive-state-engine`. No other engine performs
promotion decisions. Other engines only supply inputs through existing Event
Bus subjects. *(Grounds: D-4F-3, §19; §10's ownership matrix.)*

**RS-1b — RATIFIED.** **4F.7 is strictly read-only.** It does not:

- create Active Thoughts;
- author `ProposedAction`s;
- promote thoughts;
- call `promotion_orchestration.promote_thought`;
- add a write route under `/v1/cognitive-state`.

Statements suggesting that the 4F.7 surface drives promotion are historical
contradictions. Each is resolved additively, with the original wording
preserved:

| Where the statement is | What happens to it |
|---|---|
| 4F.6 completion record §1.1 and §2.1, and finding F-6 in §8.1 | Dated additive notes in that record |
| `services/cognitive-state-engine/README.md`, *Status update — 4F.6* | A dated additive note |
| `promotion_orchestration.py`'s module docstring (l.29–35) and `main.py`'s lifespan comment (l.44–49) | **Not edited now**: they are production source, and this ratification step modifies none. Their additive clarification is an obligation of the 4F.7 implementation (TDD 4F.7 §17) |

**RS-1c — RATIFIED: Alternative C.**

- The production promotion driver, thought ingestion and `ProposedAction`
  authorship belong to a **new implementation slice inside milestone 4F, before
  4F.8**. It is **4F.P**, added to §18 by additive amendment.
- **4F remains one milestone.** 4F.P is **not implemented now**.
- **Its future TDD must explicitly ratify:**
  - the promotion policy;
  - the thought-ingestion mapping;
  - the `ProposedAction` authorship rule;
  - the CAS transition semantics;
  - Layer 2 logical deduplication.
- **Why D was rejected.** Alternative D was *"test/e2e-only until 4F.8"*. It
  would have left CF-11 unevidenceable within 4F. §4.2 states that AC-8 was
  *"deliberately not re-scoped to avoid … CF-11"*.

### 24.3 Thought ingestion and `ProposedAction` authorship

**RS-2a — RATIFIED (a recorded finding).** At `4e19ed1` the repository has **no
production producer that creates Active Thoughts** and **no existing producer
that authors a complete `ProposedAction`**. The evidence:

- `upsert_thought`, `list_thoughts`, `select_focus` and `promote_thought` have
  **no caller** in `cognitive-state-engine/src/` outside their own definitions.
- `SUBSCRIBABLE_SUBJECTS` is empty.
- **No registered payload carries all of `ProposedAction`'s required fields.**
  `category`, `action_type`, `execution_target` and `verification_method` are
  missing from every one of `world_model.context.changed`,
  `planning.task_graph.created`, `reasoning.process.completed` and
  `perception.workspace.observed`.

**4F.7 does not invent one.**

**RS-2b — RATIFIED.** The smallest future extension is:

- `cognitive-state-engine` subscribes to **existing** Event Bus subjects;
- it maps approved inputs into Active Thoughts;
- it authors complete `ProposedAction`s according to a **future, explicitly
  ratified** authoring rule.

**The exact source subjects, the field mapping and the authoring rule stay
OPEN** for 4F.P's TDD. No `ProposedAction` policy is invented here.

### 24.4 The sensor-state data path

**RS-3a — RATIFIED: Option B.** The decision:

- **No new subject.** 4F.7 uses the existing `perception.sensor.health_changed`
  (`PerceptionSensorHealthChangedPayload`).
- **Publisher.** `perception-engine` publishes it on existing sensor lifecycle
  transitions.
- **Consumer.** `cognitive-state-engine` subscribes to it as an internal input.
  Its subscribe allow-list changes from **empty** to **exactly this existing
  subject**.
- **Read surface.** `cognitive-state-engine` serves normalized sensor state
  through `/v1/cognitive-state`.
- **`PUBLIC_TOPICS` is not modified**, and stays byte-identical at 18.

**An accepted architectural consequence, recorded explicitly.** The subject is
**already public**: it has been in `ws-gateway`'s `PUBLIC_TOPICS` since 4B. So
publishing it also makes the event available to `ws-gateway` subscribers, and
the Events panel records every frame. This is accepted as a consequence of
RS-3a.

**Consequences recorded, not resolved here:**

| # | Consequence | Where it is handled |
|---|---|---|
| 1 | §2.2 property 4 (*"No raw sensor event reaches the browser"*) and D-4F-4 (*"no raw sensor stream to the browser"*) are read together with the accepted consequence above. A lifecycle-status report on an already-public topic is accepted by this ratification; **no sensor observation** becomes browser-visible | This row |
| 2 | Phase 2D-B's design (`docs/design/phase-2d/03-perception-engine.md` §12, §13.2) described the subject as published on *"repeated failures … for observability"*, with *"no engine consumer this phase"*. RS-3a broadens the publication condition to lifecycle transitions and adds an engine consumer. The 2D-B text is a dated design record and is not edited | This row |
| 3 | The payload's `status` field is plain `str` with **no fixed vocabulary** (`events/perception.py`). Which values `perception-engine` publishes is a **TDD 4F.7 decision** | TDD 4F.7 §20, A-4F7-2 |
| 4 | The Event Bus SDK's `subscribe()` is a core NATS subscription. A report dispatched while `cognitive-state-engine` is not subscribed is not delivered to it | TDD 4F.7 §15 and §18, as a known limitation |

> **Updated 2026-09-26 (TDD 4F.7 §28: A-4F7-1 and A-4F7-2 RATIFIED),
> additively.** The table above is preserved as written.
>
> **Consequence 3 is settled (A-4F7-2).** `perception-engine` publishes the
> **existing lifecycle vocabulary**, `SensorState` (`perception-engine`
> `domain/sensor.py` l.29):
>
> - The six values are `uninitialized`, `initialized`, `running`, `paused`,
>   `stopped` and `failed`, read after each transition.
> - `cognitive-state-engine` accepts exactly those six and **rejects anything
>   else without storing it**.
> - **No health-status vocabulary** is published or invented.
> - **The payload contract is unchanged** (`status: str`).
>
> **The store is fixed (A-4F7-1).** Normalized state lives in the durable
> current-state table `cognitive_state.sensor_state`, one record per sensor,
> with **no history and no audit semantics**.
>
> Nothing here changes RS-3a or its accepted consequence.

**Alternatives rejected:**

- **Option A** (the panel consumes the realtime topic) contradicts §4.1's last
  row and §12.
- **Option C** contradicts §4.1. Its variants were `perception.consent.changed`,
  which records app consent rather than OS permission; inferring failure from
  silence; and reading `perception-engine` over HTTP, which ADR-004 forbids.
- **Option D** (unrelated to 4F.7) contradicts §18.

**RS-3b — RATIFIED as OPEN.**

- **OS-level permission revocation detection stays OPEN.** 4F.7 does not
  implement `chmod` detection and does not modify `nova-companion` for this
  purpose.
- **4F.7 does not claim that OS permission revocation itself is demonstrated.**
  It only provides the read surface and visualizes whatever normalized sensor
  state is actually supplied.
- **The owner of revocation detection must be ratified before the 4F.8 TDD.**

### 24.5 The read surface

**RS-4a — RATIFIED.** The minimum `/v1/cognitive-state` read surface is
**`GET`-only**. Identity is resolved server-side from `primary_user_id`, and no
caller-supplied user id is accepted. The surface contains:

- Active Thoughts, with all Part 6 fields;
- the attention layer;
- Focus entries, with `score` and `signals_used`;
- normalized sensor state;
- `ProposedAction`, only under RS-4c.

**Empty production data must remain empty.** No synthetic thoughts, no fake
Focus activity, no fake sensor state.

**RS-4b — RATIFIED.**

- 4F.7 creates **no durable Thought-to-Decision link**.
- `cognitive-state-engine` does **not** read `autonomy-engine` data.
- **No autonomy decision data** is included in the cognitive-state read
  surface.

**RS-4c — RATIFIED: Alternative (i).**

- *"A Level-2-relevant read"* (§13) means the **persisted `proposed_action`**.
- It is rendered **as a proposal**. It is **never** rendered as triggered,
  decided, executing or executed.
- **No new persistence** is added for this purpose.
- **Alternative (ii)**, withdrawing the phrase, is rejected.

**RS-4d — RATIFIED.** 4F.7 includes deployment wiring for
`cognitive-state-engine` in two files:

- `infra/docker/docker-compose.local.yml`;
- `infra/docker/run-migrations.sh`.

This uses the assignment already established by the 4F.1 completion record
(§8: *"a compose service and `run-migrations.sh` entry (4F.7, with
deployment)"*).

### 24.6 The prefix

**RS-5 — RATIFIED.** The `/v1/cognitive-state` prefix contradiction is
resolved by an additive note under §2.2. The historical sentence is not
rewritten. The authoritative interpretation:

- `api-gateway` remains the **sole** external REST boundary.
- 4F adds exactly **one** new external prefix, `/v1/cognitive-state`, forwarded
  1:1.
- **No `/v1/perception` prefix** is added.
- **No other new prefix** is added by 4F.7.

### 24.7 *Triggered*

**RS-6a — RATIFIED: Option A.** *Triggered* remains a **system-level
property**. None of the following is created:

- a `Triggered` enum;
- a triggered database field;
- a per-thought triggered state;
- a persisted trigger outcome.

**Option B**, per-thought persisted state, is rejected.

**RS-6b — RATIFIED.** 4F.6's state 4 is to be interpreted as follows:

- **The consumer mechanism exists.**
- **The production end-to-end *Triggered* state is not yet evidenced** while
  `cognitive-state-engine` is not deployed and while no production component
  promotes an Active Thought.
- **CF-11 closure is not claimed.**

Additive notes carry this into TDD 4F.6 §2 and the 4F.6 completion record
§1.1.

### 24.8 Promotion transition semantics

**RS-7 — RATIFIED: Option E for 4F.7.**

- **4F.7 makes no change** to promotion transition semantics.
- **CAS protection is required before a production caller exists.**
  Promotion transition semantics need it at that point, using
  `autonomy-engine`'s `decide_suggestion` conditional-`UPDATE` pattern as
  precedent (`repository/postgres_autonomy_repository.py`). The future
  promotion slice ratifies the exact CAS behaviour. **CAS is not implemented
  now.**
- **None of the following is added:**
  - retry;
  - an outbox;
  - failed-trigger persistence;
  - TTL;
  - stale-trigger handling;
  - Layer 2 deduplication.

### 24.9 Stand-in producers

**RS-8 — RATIFIED: Option B.** All producer stand-ins are **test
infrastructure**, including `tools/e2e_seed_autonomy_suggestion.py`.

**A stand-in:**

- uses real repositories and gates;
- stays inside test infrastructure;
- does **not** count as a production producer;
- does **not** close CF-11;
- does **not** prove the Level 2 *Triggered* state.

**If AC-8 later uses a stand-in,** its evidence must state explicitly that the
CF-11 dependency (§4.2) remains unmet.

**Rejected:**

- **Option A** (a stand-in may close CF-11) contradicts §6.1's
  *"production-reachable"* and TDD 4F.6 §2's *"without a test harness"*.
- **Option C** (no stand-in, ever) is contradicted by precedent. The Phase 4D
  Gate Review accepted a disclosed stand-in as acceptance-test infrastructure
  (`phase-4d-autonomy-engine-gate-review.md`, lines 184–192 and 719–721).

### 24.10 SAD 15 §4 item 1

**RS-9 — RATIFIED: Option C.** The 4F.7 PR is granted an exception to SAD 15
§4 item 1.

**The exception covers:**

- `services/cognitive-state-engine/`;
- `services/api-gateway/`;
- `apps/web-client/`;
- `infra/docker/`;
- `services/perception-engine/`, because RS-3a requires it.

The tests and documentation associated with these surfaces are included.

**Conditions:**

- SAD 15 §4 items 2–5 remain mandatory.
- The Slice Completion Record must document the exception.
- **No change-scope linter is created.**

**Recorded, not an extension of the exception.** Some files that 4F.7 also
needs are **not an engine's `src/`**, so SAD 15 §4 item 1 does not govern
them:

- `.github/workflows/pr-checks.yml` — the e2e job's started-service list;
- the repository-root `uv.lock` — changed by a dependency declaration.

TDD 4F.7 §5 lists each one.

**Rejected:**

- **Option A** would repeat, undecided, the non-conformance the Phase 4B Gate
  Review recorded as an unmet DoD item for PR #24
  (`phase-4b-observability-panels-gate-review.md`, lines 1764–1770).
- **Option B** contradicts §18 (*"not new milestones"*).

### 24.11 Documentation

**RS-10 — RATIFIED.**

- The already-ratified D-4F-9 text from TDD 4F.6 §14 is appended as **§11.5**,
  additively.
- §11.4's historical wording is not rewritten.
- A provenance note sits at the end of §11.5.

**RS-11 — RATIFIED.** The documentation statements that 4F.7 drives
promotions are resolved by additive clarification:

- The historical wording is preserved.
- Ownership wording now names the future promotion slice, **4F.P**, as the owner
  of production promotion.
- **No production code is modified in this step.** See RS-1b's table.

### 24.12 OPEN — explicitly, and not closed by any wording here

- **Revocation and carry-forwards:** RS-3b (OS-level revocation detection);
  CF-9, CF-10 and CF-11.
- **4F.6's open and deferred semantics:**
  - TTL and stale-trigger semantics;
  - Layer 2 logical deduplication;
  - persistent lost-trigger auditability;
  - `observability.py` packaging;
  - the `correlation_id` logging convention.
- **Ledger rows:** L-14, L-17, L-18 and L-19.
- **`cognitive-state-engine` semantics:**
  - Focus-signal computation — every `FocusInputs` signal is still `None` in
    production;
  - Part 6 INTERRUPTIONS promotion semantics (`domain/attention.py` defers
    them).
- **Stale documentation:** the realtime-hydration row at
  `docs/architecture/04-frontend-architecture.md:81`, which contradicts D-4F-6.
- **4F.P's contents:** the promotion policy, the thought-ingestion mapping, the
  `ProposedAction` authorship rule and the CAS semantics (RS-1c, RS-2b).

### 24.13 Residuals recorded, not resolved

1. **§16.1 control 11** still reads *"publishes nothing"*. Two facts bear on
   it:
   - D-4F-9 (§11.5) amends §13 and §11.4 but does not name control 11;
   - 4F.6 retargeted the control's test in code.

   Deciding whether to amend the control's wording is left to 4F closure's
   category-12 sweep (ledger **L-9**).
2. **`docs/architecture/10-inter-engine-communication.md:81`** describes
   `world_model.context.changed` making `cognitive-state-engine` *"re-evaluate
   Focus"*. No such subscription exists, and whether 4F.P creates one is part
   of RS-2b's OPEN mapping.
3. **"Exactly one new subject" predates D-4F-9.** §16.1 control 1 (*"Exactly
   one new Event Bus subject"*) and §21 item 5 (*"exactly one Event Bus subject
   was added"*) were written before D-4F-9. Across 4F, two subjects are now
   registered:
   - `perception.workspace.observed`, by 4F.2;
   - `autonomy.decision.requested`, by 4F.6 (D-4F-9, registry 119 → 120).

   D-4F-9 does not amend either statement. **4F.7 adds no subject.** Settling
   the wording belongs to 4F closure's category-12 sweep (**L-9**) and the 4F
   Gate Review.
