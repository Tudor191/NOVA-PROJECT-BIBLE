# TDD 4F — `nova-companion`, the perception extension,
## `services/cognitive-state-engine`, and Autonomy Level 2

**Status: DESIGN PREPARATION — NOT RATIFIED.**
**§0.1 records five findings. §19 lists the decisions that must be answered
before implementation starts. Three of them are blocking.**

**Written against** `phase-4` at `c04b58e0d6be4f4236b8fe8c5a7dcf79bf7d56f4`
(the Phase 4E closure commit), on the preparation branch `phase-4f-tdd`.
**No `phase-4f` branch exists and none is created by this document.**

**Protocol:** [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md),
sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`,
1131 lines, read from `origin/main` and verified byte-identical on `phase-4`.

**Satisfies:** AC-7, AC-8. **Depends on:** 4E (merged as `59bbeee`).

---

## 0. Objective

Phase 4F is the milestone Phase 4's own scope calls *"the one that carries all
of Phase 4's platform risk, and it comes last by design (D-1)"*. It gives NOVA
**senses it does not have** (`nova-companion`), **an inner life it has never
had** (`cognitive-state-engine`), and **the first autonomy level at which it
acts without being asked** (Level 2).

Everything below is derived against the repository rather than from the
roadmap's prose. Where the two disagree, §0.1 says so.

### 0.1 Findings from deriving this TDD against the repository

Five findings. **Three are blocking** and are restated as decisions D-4F-1,
D-4F-2 and D-4F-3 in §19.

#### 0.1.1 AC-7's one-second budget is unreachable through the transactional outbox — **BLOCKING**

AC-7 clause 1: *"Opening a known project in the IDE is detected and reflected in
the World Model **within one second** with no user action."*

Every `perception-engine` publisher returns an `OutboxEvent`
(`events/publishers.py` — seven call sites, no exceptions), and
`nova_service_kit.outbox.dispatch_ready_events` is the only caller of
`bus.publish()` for engine domain events. That dispatcher runs on a **fixed
10-second cron**:

```python
# services/perception-engine/src/nova_perception_engine/workers/__init__.py:85-88
cron_jobs = [
    # Short, fixed poll -- outbox latency should be seconds, not minutes.
    service_cron(_SERVICE_NAME, arq_run_outbox_dispatch, second={0, 10, 20, 30, 40, 50}),
]
```

**Worst-case perception→bus latency is therefore ~10 s, and mean ~5 s, before
`world-model-engine` has even received the event.** A one-second end-to-end
budget is not achievable by tuning; it is excluded by the architecture.

This was invisible until now because no prior acceptance criterion put a latency
bound on an outbox-published subject. It is **not** a defect in the outbox — the
outbox is what makes a write and its event atomic (Phase 1's transactional outbox
pattern), and Phase 4E's stack-completeness guard now enforces that every
outbox-publishing engine on a browser-observable path actually runs its worker.

**Three options, none of which this TDD chooses.** See D-4F-1 (§19.1).

#### 0.1.2 AC-8 is blocked by CF-9, at every risk level — **BLOCKING**

AC-8: *"The same action category that is blocked at Level 1 auto-executes at
Level 2 for a **low-risk** case, purely by policy — no code path differs."*

A Level-2 auto-execution must reach `action-engine`. Its pipeline stage 3 is
ADR-032's identity-confidence gate, and **it is not Critical-only**:

```python
# services/action-engine/src/nova_action_engine/domain/pipeline.py:181-189
confidence = await identity_port.get_confidence(user_id=action.requested_by)
policy = await repository.find_identity_confidence_policy(action.requested_by)
threshold = 1.0  # absent-policy fails closed: require maximum confidence (TDD 3D §10)
if policy is not None and risk.value in policy.minimum_confidence_by_risk:
    threshold = policy.minimum_confidence_by_risk[risk.value]
effective_confidence = confidence if confidence is not None else 0.0
if effective_confidence < threshold:
    ...  # denied
```

With **no policy row the threshold is 1.0 for every risk level including LOW**,
and `perception-engine`'s `SINGLE_SIGNAL_CONFIDENCE_CEILING = 0.75` means a real
single-signal identity cannot reach it. Nothing in the repository can create a
policy row — that is exactly **CF-9**, open since 4B, routed to 4D, and declined
there by ratified decision **D-4D-2**.

**So AC-8's low-risk auto-execution is denied at stage 3 today, and no amount of
Level-2 work in `autonomy-engine` changes that.** This is a genuine, factual
dependency of 4F on CF-9 — not an implication, and not a licence to close CF-9
silently. See D-4F-2 (§19.2).

#### 0.1.3 AC-8 has no trigger — CF-11 — **BLOCKING**

`autonomy-engine`'s decision pipeline has **no production caller**. Phase 4D's
Gate Review re-verified at source: **0** call sites of `insert_suggestion`, **0**
of `decide()`, no handler, worker or scheduler, and **0 of 11** published
operations create one. Both of its Event Bus allow-lists are **empty frozensets
carrying scaffold TODOs**, and `test_control_8_this_engine_never_calls_the_bus_at_all`
asserts the engine makes no bus call of any kind.

That is **CF-11**: *"no component produces a suggestion."* AC-8 needs a real
trigger for a real action, so 4F must build the initiative surface CF-11
describes as missing. **Which component owns it is not settled by any
authoritative document.** `cognitive-state-engine` is the natural candidate —
Bible Part 6's Active Thoughts are literally ongoing reasoning processes with
priority and progress — but the master scope's 4F entry does not say so, and
inventing that ownership is exactly what this TDD must not do. See D-4F-3
(§19.3).

#### 0.1.4 The Sensor Abstraction Layer's type literals exclude every 4F sensor — non-blocking

`domain/sensor.py` is explicitly built for this moment — its own docstring says a
future `nova-companion` sensor *"is a matter of implementing an already-correct
Protocol, never a redesign"* — and the `Sensor` Protocol needs **no change**.

But two closed literals do:

```python
class SensorConfig(BaseModel):
    sensor_type: Literal["voice", "camera"]      # ← no companion sensor fits

class PermissionStatus(BaseModel):
    source: Literal["microphone", "camera"]      # ← no OS permission fits
```

4F's sensors are desktop/window-focus, clipboard, filesystem and process/system
health. **Both literals must widen.** This is additive and internal —
`domain/sensor.py` is `perception-engine`'s own domain module, not
`nova-contracts`, and neither type is serialized into any registered payload
(verified: no `register_payload` class references either). It is recorded here
rather than treated as incidental because it is a change to a **2D-B shipped
type**, and §14 pins the widened set so it cannot drift further unnoticed.

#### 0.1.5 AC-7 clause 2 has no browser-reachable data source — non-blocking, but it forces a choice

AC-7 clause 2: *"revoking a sensor's OS permission immediately and **visibly**
stops that perception stream **in the UI**."*

The UI can learn this in exactly two ways, and **neither exists today**:

| Path | Status | Cost |
|---|---|---|
| Event Bus → `ws-gateway` | `perception.sensor.health_changed` is **registered but not public** — `PUBLIC_TOPICS` holds 18 strings and it is not among them | A new `PUBLIC_TOPICS` entry |
| REST → `api-gateway` | `GET /v1/perception/sensors` **already exists** (`api/sensors.py:26`), but **`/v1/perception` is not in the gateway route table** — the eight fronted prefixes are `/v1/communication`, `/v1/plans`, `/v1/reasoning`, `/v1/capabilities`, `/v1/action`, `/v1/agents`, `/v1/autonomy`, `/v1/digital-twin` | A new D-6 prefix |

**The REST option is cheaper but carries Phase 4E's finding §0.1.7 in a sharper
form.** A D-6 prefix fronts the *whole* subtree, and `/v1/perception` includes:

- `POST /v1/perception/consent` and **`DELETE /v1/perception/consent/{source}?user_id=…`**
- `POST /v1/perception/identities` (biometric enrollment) and `DELETE /v1/perception/identities/{identity_id}`

all taking a **caller-supplied `user_id`**. Fronting the prefix would make
**consent revocation and biometric identity enrollment externally reachable** —
a materially more serious surface than 4E's profile writes. See D-4F-4 (§19.4).
**This TDD does not choose**, and §0.1.5 is the reason §18's SLOC estimate
carries a range rather than a number.

---

## 1. Scope

| # | Deliverable | Where |
|---|---|---|
| 1 | **`nova-companion`** — a Rust process providing desktop/window-focus, clipboard, filesystem and process/system-health sensors, plus terminal and window-control actuators | new top-level `companion/` |
| 2 | **Sensor Abstraction Layer registration** — every companion sensor behind the existing `Sensor` Protocol, with the two literals of §0.1.4 widened | `perception-engine` |
| 3 | **Perception extension** — normalization, context enrichment, multi-modal fusion | `perception-engine` |
| 4 | **`services/cognitive-state-engine`** — Active Thoughts, Focus System, Attention Layers (Bible Part 6) | new engine |
| 5 | **Autonomy Level 2** — defined → selectable → policy-permitted → triggered → executing, as five separable steps (§11) | `autonomy-engine` |
| 6 | **The `cognitive-state/` panel** — the eleventh and last Phase 4 panel (master scope §6) | `apps/web-client` |

### 1.1 What 4F deliberately does **not** build

- **The desktop shell.** `apps/desktop-client` (Tauri) is Phase 5. `nova-companion`
  is a **headless sensor/actuator process**, not a UI.
- **Voice UI presentation** — Phase 5. The voice channel already exists from 2D-A/2D-B.
- **The five deferred panels** — Phase 5.
- **OIDC/PKCE, `nova-auth`, RBAC, multi-user** — Phase 7; ADR-025 governs.
- **Mobile, third-party API access, marketplace.**
- **Autonomy Levels 3–5.** Named in the vocabulary, no defined semantics. 4F
  enables **2 and only 2**.
- **Closing CF-4, CF-5, CF-6, CF-8.** Untouched.
- **Any Phase 5 work of any kind.**

---

## 2. Non-goals, stated as properties a reviewer can check

1. No new engine-to-engine HTTP. The only `httpx` client that crosses a service
   boundary in the repository is `api-gateway`'s `clients/upstream.py`, and that
   is the gateway doing its job. **4F adds none** (ADR-004).
2. `api-gateway` remains the **sole** external REST boundary.
3. `ws-gateway` remains the **sole** browser realtime bridge, and the only path
   from a browser to bus activity (AC-2, already proven).
4. Existing envelope conventions unchanged.
5. Existing authentication boundaries unchanged (D-3's session model).
6. **No fabricated sensor data.** AC-7 is measured against a real OS signal from
   a real companion process, or it is not measured (§15, §17).
7. **No fake clock and no time simulation** anywhere in 4F — the same rule
   ratified for 4E §20.1, restated because AC-7 is a *latency* criterion and the
   temptation is structurally identical.
8. No duplicated state ownership (§10).

---

## 3. Dependencies and inherited state — verified at `c04b58e`

### 3.1 Hard dependencies, all present

| Dependency | Evidence at `c04b58e` |
|---|---|
| Sensor Abstraction Layer | `perception-engine/domain/sensor.py` — full 12-method `Sensor` Protocol, 8-transition lifecycle state machine |
| World Model ingestion of perception | `world-model-engine/events/subscribed.py` subscribes **`perception.*.observed`** — a wildcard, so a new `perception.<x>.observed` subject needs **no subscription change** |
| World Model object lifecycle | `world_model.object.created` / `.updated` / `.deleted`, `world_model.context.changed`, `world_model.attention.shifted` — all registered |
| Action execution entry point | `action-engine` subscribes to exactly one subject: **`action.execute`**, registered as `ActionExecuteRequestPayload`, **with no production publisher today** |
| Autonomy level machinery | `autonomy-engine/domain/levels.py` — `DEFINED_LEVELS` already contains Level 2; `SELECTABLE_LEVELS` does not |
| Approval-vs-execute signal | `GateReport.requires_approval`, already carried, documented as *"recorded for the log now so that when 4F enables Level 2 the signal is already being carried rather than needing to be retrofitted"* |
| Digital Twin domains | 4E's nine Part 16 domains, merged as `59bbeee` |

### 3.2 Authoritative decisions 4F is bound by

- **D-1** — Level 2 enablement and `nova-companion` are 4F's, and 4F comes last.
- **D-3** — the Phase-4 session model; 4F does not change it.
- **D-6** — `api-gateway` forwards 1:1, no path rewriting.
- **D-4D-1** — no Event Bus contract without a genuine producer/consumer need.
  **4F's `action.execute` publication is exactly such a need** (§12).
- **D-4D-2** — CF-9 stays open, `action-engine` keeps sole ownership of
  `IdentityConfidencePolicy`. **§0.1.2 puts this in direct tension with AC-8**
  and D-4F-2 is where it is resolved.
- **ADR-004, ADR-024, ADR-025, ADR-030, ADR-032, ADR-033.**

### 3.3 Carry-forwards that touch 4F

| ID | 4F's relationship | Closed by 4F? |
|---|---|---|
| **CF-9** | **AC-8 cannot pass without it** (§0.1.2) | **Only if D-4F-2 ratifies it.** Not by implication |
| **CF-10** | No `TrustMetric` read surface. `autonomy-engine`'s trust input still reports unavailable and fails closed. **4F does not need it**: AC-8 turns on *policy*, not on a trust score | **No** |
| **CF-11** | **AC-8 needs a trigger** (§0.1.3) | **Only if D-4F-3 ratifies an owner.** Not by implication |
| CF-4, CF-5, CF-6, CF-8 | Untouched | **No** |
| 4E's three findings | `nova_testkit` image drift, the D-6 prefix exposure, the stranded-outbox guard's missing `memory` schema. **The third becomes more load-bearing in 4F** if D-4F-1 keeps the outbox on the AC-7 path | **No** |

---

## 4. AC-7 and AC-8 — explicit mapping

### 4.1 AC-7, clause by clause

> *"Opening a known project in the IDE is detected and reflected in the World
> Model within one second with no user action, and revoking a sensor's OS
> permission immediately and visibly stops that perception stream in the UI."*

| Clause | Discharged by | Blocked on |
|---|---|---|
| *"Opening a known project in the IDE is detected"* | `nova-companion`'s window-focus sensor, behind the Sensor Abstraction Layer (§6) | — |
| *"…is a **known** project"* | Correlation to a `project_id` the system already holds. **The only project identity in the system is `MemoryRecord.project_id`** (established by 4E §5.2) | — |
| *"reflected in the World Model"* | `world-model-engine`'s existing `perception.*.observed` wildcard subscription → a world object | — |
| *"**within one second**"* | — | **D-4F-1.** Unreachable through a 10 s outbox cron (§0.1.1) |
| *"with no user action"* | An autonomous sensor loop, not a REST call | — |
| *"revoking a sensor's OS permission"* | A **real** OS permission revocation observed by the companion; `Sensor.permission_status()` already exists | — |
| *"immediately and visibly stops that perception stream"* | Lifecycle transition `running → stopped` (or `→ failed`), plus `perception.sensor.health_changed` | — |
| *"**in the UI**"* | — | **D-4F-4.** No browser-reachable source today (§0.1.5) |

### 4.2 AC-8, clause by clause

> *"The same action category that is blocked at Level 1 auto-executes at Level 2
> for a low-risk case, purely by policy — no code path differs."*

| Clause | Discharged by | Blocked on |
|---|---|---|
| *"the same action category"* | One `ActionType`, one `DecisionRequest` shape, exercised twice | — |
| *"blocked at Level 1"* | Already true and already tested: `permits_execution()` is `False`, `GateReport.requires_approval` defaults `True` | — |
| *"auto-executes at Level 2"* | `autonomy-engine` publishes **`action.execute`** (§12) | **D-4F-2** (CF-9 denies it at stage 3) and **D-4F-3** (no trigger) |
| *"for a low-risk case"* | `RiskLevel.LOW`; `risk_at_most` already exists | — |
| *"purely by policy"* | The policy-derived `requires_approval` flag is the **only** input that differs | — |
| *"**no code path differs**"* | §11.6's single-dispatch rule, enforced by a test that the Level-1 and Level-2 runs execute the **same** call sequence | — |

**AC-7 and AC-8 are both provider-free.** Neither needs a model provider, so
neither inherits AC-3's or AC-4's deferrals.

---

## 5. `nova-companion` — process and ownership boundary

### 5.1 What it is

A **headless Rust process** on the user's machine. It is the only 4F component
that touches the operating system, and it owns **nothing** in the domain sense:
it observes, normalizes into the Sensor Abstraction Layer's vocabulary, and hands
off. Every fact it produces is owned downstream.

### 5.2 The boundary, stated as prohibitions

1. **It never talks to a browser.** No local HTTP server the web client could
   call, no WebSocket the browser could open. AC-2's property — `ws-gateway` is
   the only path from a browser to bus activity — must remain provable.
2. **It never publishes to the Event Bus directly.** It is a *sensor host*, not
   an engine; `perception-engine` owns the publication.
3. **It never writes to any database.**
4. **It never calls another engine's HTTP API.**
5. **Its actuators execute nothing on their own initiative** — they are invoked
   through `action-engine`'s existing lifecycle or not at all (§5.4).

### 5.3 How it reaches `perception-engine` — **OPEN, D-4F-5**

The repository has **no precedent** for a non-Python process feeding an engine.
Candidates: a local transport the engine owns, or an engine-owned REST intake
endpoint on `perception-engine`'s existing `/v1/perception` surface. Each has a
different blast radius against §2's properties and against D-4F-4's prefix
question. **This TDD does not choose.**

### 5.4 Actuators

Terminal and window control are **actuators, not autonomous capabilities**. They
are reachable only as `action-engine` action types, so every existing stage —
risk estimation, the identity-confidence gate, approval, the append-only action
log — applies unchanged. **4F adds no path that bypasses the Action Principle
lifecycle.**

---

## 6. Sensor Abstraction Layer integration

Each companion sensor registers as a `Sensor` implementation. **The Protocol is
unchanged**; §0.1.4's two literals widen to admit the new `sensor_type` values
and OS permission `source` values.

The lifecycle state machine is already exactly what AC-7 clause 2 needs:

```
uninitialized → initialized → running → { paused, stopped, failed }
                                paused → { running, stopped }
                                failed → initialized
```

A revoked OS permission drives `running → stopped` (deliberate revocation) or
`running → fail` (revoked underneath a live stream). **`next_state` rejects every
undefined pair**, so a sensor cannot reach a state the diagram does not permit.

---

## 7. Sensor input normalization

Raw OS signals are noisy, high-frequency and platform-shaped. Normalization is
`perception-engine`'s, not the companion's, so the rules are testable in Python
against the existing suite: debounce and coalesce, map platform-specific
identifiers to a stable vocabulary, drop signals whose sensor is not `running`,
and **attach no identity the sensor did not observe**.

**Explicitly not normalization:** inventing a `project_id`. Correlating a window
title to a known project is *enrichment* (§8), and it can fail.

---

## 8. Perception enrichment

Enrichment attaches context the raw signal lacks — most importantly AC-7's
*"known project"*. The only project identity in the system is
`MemoryRecord.project_id`, and `perception-engine` must not read
`memory-engine`'s database (ADR-004; 4E §0.1.5 settled the identical question
for `digital-twin-engine`, and the answer was the Event Bus).

**When correlation fails the observation is still published, without a
`project_id`.** An unrecognized project is an honest unknown, not an error, and
never a guess — the same discipline 4E's `DomainReasonCode` enforces.

---

## 9. Multi-modal fusion

The roadmap's *"meeting begins"* scenario: calendar, voice, presence and window
focus agreeing. `perception-engine` already has `domain/correlation_buffer.py`
and `domain/identity_fusion.py`; 4F extends the same shape rather than adding a
parallel one.

**Fusion never raises confidence above what its inputs support**, and
`SINGLE_SIGNAL_CONFIDENCE_CEILING = 0.75` stays as it is — a fused *identity*
claim is the one thing 4F must not quietly strengthen, because ADR-032's gate
reads exactly that number (§0.1.2).

---

## 10. Ownership — who owns what, and who must not

| Fact | Owner | 4F's relationship |
|---|---|---|
| Raw OS signal | `nova-companion` | Produces, owns nothing |
| Sensor lifecycle & permission status | `perception-engine` | Extends |
| Normalized observation | `perception-engine` | Extends |
| World objects, context, prediction | `world-model-engine` | **Consumer only.** 4F adds no world-model write path other than its existing subscription |
| Memories, `project_id` | `memory-engine` | **Read-only, via events** |
| Part 16 domains | `digital-twin-engine` | **Untouched by 4F** |
| Autonomy level, policy, permission grants, decision log | `autonomy-engine` | Extends |
| Action lifecycle, risk, approval, identity-confidence policy | `action-engine` | **Consumer.** 4F publishes `action.execute`; it does **not** re-implement any stage |
| **Active Thoughts, Focus, Attention Layers** | **`cognitive-state-engine`** | **New, sole owner** |

**Two ownership rules 4F must not break.** (a) Cognitive state is *explicitly
distinct* from Phase 2D-C's session-scoped conversation memory — different
lifetime, different owner. (b) ADR-030's *"Personality stores, Digital Twin
learns"* is unchanged: cognitive state is a **third** thing and neither engine's
data moves.

---

## 11. Autonomy Level 2 — five distinct states

**This section is the one the Gate Review should read hardest.** Level 2 is not
one switch. It is five, and 4D built the first and pre-wired the others.

| # | State | Where it lives | Status at `c04b58e` | What 4F changes |
|---|---|---|---|---|
| **1** | **Defined** | `DEFINED_LEVELS` | **Already true.** Level 2 is in the set; Bible Part 14's semantics are recorded | Nothing |
| **2** | **Technically enabled (selectable)** | `SELECTABLE_LEVELS`, `require_selectable()` | **False.** Raises `LevelNotSelectableError` → 422, *"enabled in milestone 4F (decision D-1)"* | Adds Level 2 to `SELECTABLE_LEVELS` |
| **3** | **Permitted by the Policy Engine** | `evaluate_policies()` → `requires_approval` | Machinery exists; **there is no `allow` effect and none is added** | Policy rows may set `requires_approval=False` for a low-risk category |
| **4** | **Receiving a real trigger** | **Nothing.** CF-11 | **0 callers of `decide()`** | **D-4F-3 — unowned** |
| **5** | **Executing an action** | **Nothing.** `permits_execution()` returns `False` unconditionally; `_forbid_execution()` raises if it ever returns `True` without a real path | No execution path exists | Publishes `action.execute` (§12) — **and D-4F-2 must clear CF-9 or it is denied at stage 3** |

### 11.1 Why the distinction is load-bearing

4D wrote the guard that makes conflating them impossible:

```python
# domain/decision.py:119-131
def _forbid_execution(level: AutonomyLevel) -> None:
    if permits_execution(level):
        raise AssertionError(
            f"... Enabling Level 2 is milestone 4F "
            f"(decision D-1) and requires an execution path, not a flag."
        )
```

**"An execution path, not a flag."** A 4F implementation that flips
`permits_execution` without §12's publication turns every decision into an
`AssertionError`. That is the intended outcome and the control must survive 4F
in a form that still fails on a flag-only change (§14 control 3).

### 11.2 State 2 — selectable

One-line change, plus the 422's reason text, plus the panel. `require_selectable`
returning the level rather than a bool *"so a caller cannot forget to act on a
`False`"* stays as it is.

### 11.3 State 3 — permitted by policy

**No `allow` effect is introduced.** `PolicyEvaluation` has *"no field meaning
'allowed'"* by design (`domain/policy.py`), and there is no `allow` member of
`PolicyEffect`, and 4F keeps that: a policy can lower `requires_approval`
for a bounded, low-risk category; it can never assert that something is
permitted. Denial remains the only effect a policy can produce.

### 11.4 State 4 — the trigger

**Unowned. D-4F-3.** §0.1.3.

### 11.5 State 5 — execution

§12.

### 11.6 The single-dispatch rule — how *"no code path differs"* is made true

One dispatch point reads `GateReport.requires_approval`:

- `True` → persist a suggestion; the existing approval surface applies.
- `False` → publish `action.execute`.

**Everything upstream is byte-identical between the two runs**: same request
shape, same gate order, same trust read, same log entry. The Level-1 and Level-2
runs differ in exactly one boolean, computed by policy. §14 control 4 asserts the
two runs produce the same call sequence up to that point.

### 11.7 Fail-closed, restated for Level 2

- A failing policy engine **denies** — already true, and 4F does not soften it.
- An absent policy means `requires_approval` stays `True` — approval, not
  execution.
- An unavailable trust input stays unavailable (CF-10) and **never** becomes 0.0
  or a default number.
- Level 2 applies to **LOW risk only**. Any higher risk requires approval
  regardless of level, and §14 control 5 asserts it.

---

## 12. Event Bus subjects

### 12.1 New subjects genuinely required: **most likely zero**

| Need | Existing subject | New? |
|---|---|---|
| Companion observation → World Model | a `perception.*.observed` subject, already wildcard-subscribed | **No** |
| Sensor permission/health change | `perception.sensor.health_changed` (registered) | **No** |
| Level-2 execution | **`action.execute`** (registered, `ActionExecuteRequestPayload`, **no production publisher today**) | **No** |
| Cognitive-state changes | — | **Only if a genuine consumer exists.** D-4F-6 |

**The `action.execute` finding is the important one.** 4F becomes its **first
real production publisher**, which is precisely the D-4D-1 shape 4E also used:
*a new producer on an existing contract, not a new contract.*

### 12.2 `autonomy-engine`'s allow-lists must change — disclosed, not silent

Both are currently **empty frozensets with scaffold TODOs**, and 4D's control 8
asserts *the engine never calls the bus at all*. 4F adds `"action.execute"` to
`PUBLISHABLE_SUBJECTS`, which **necessarily** retires that control in its present
form. This is a deliberate, D-1-authorized change, and §14 control 6 replaces it
with the tighter property: **`action.execute` is the only subject this engine may
publish, and it publishes nothing else.**

### 12.3 What 4F must not do

No `autonomy.*` subject. No `TrustMetric` subject or RPC (CF-10 stays open). No
new `memory.*` or `digital_twin.*` subject. No wildcard widening.

---

## 13. `PUBLIC_TOPICS`, REST, and realtime

### 13.1 `PUBLIC_TOPICS` — **unchanged unless D-4F-4 says otherwise**

18 exact strings today. The **only** candidate is
`perception.sensor.health_changed`, and **only** if D-4F-4 chooses the bus route
for AC-7 clause 2 over the REST route. §0.1.5 is the trade-off; §14 control 2
pins whichever answer is ratified.

### 13.2 REST

- **`cognitive-state-engine`**: a read surface for the panel, identity resolved
  **server-side** from `primary_user_id` — 4E's discipline, adopted from the
  start, so 4F never creates a caller-supplied-`user_id` route.
- **`/v1/perception` at the gateway**: **D-4F-4.** §0.1.5's consent and biometric
  exposure is the whole question.
- **`autonomy-engine`**: the existing `/v1/autonomy/*` surface gains no new
  route for Level 2 — selecting a level is an existing operation whose 422 stops
  being returned for `2`.

### 13.3 Realtime

`ws-gateway` stays the only browser bridge; no engine gains a browser-facing
socket; the companion has none (§5.2).

---

## 14. Negative and security controls

Each demonstrated by removing the property and observing a **named** test fail —
4D's and 4E's standard, not a declaration.

| # | Control |
|---|---|
| 1 | **No new Event Bus subject is registered by 4F** — subject count equal at base and head, unless D-4F-6 ratifies one |
| 2 | **`PUBLIC_TOPICS` is byte-identical at its 18 strings**, unless D-4F-4 ratifies exactly one addition — in which case 19 exact strings, pinned |
| 3 | **Level 2 cannot execute by flag alone** — `permits_execution` returning `True` with the §12 publication removed must still fail |
| 4 | **No code path differs** — the Level-1 and Level-2 runs produce the same call sequence up to the single dispatch point |
| 5 | **Level 2 never auto-executes above LOW risk**, at any policy setting |
| 6 | **`autonomy-engine` publishes `action.execute` and nothing else**; its subscribe allow-list stays empty unless D-4F-3 requires otherwise |
| 7 | **No cross-engine import and no engine-to-engine HTTP** — import-linter plus an AST check; zero HTTP clients in the new engine |
| 8 | **The companion opens no browser-reachable port** and no direct NATS connection |
| 9 | **CF-10 is not resolved by 4F** — 4E's five sub-properties re-asserted verbatim |
| 10 | **No fake clock, no time simulation, no fabricated sensor reading** anywhere in 4F |
| 11 | **Cognitive state never writes another engine's store** — the only repository it writes is its own |

---

## 15. Test strategy

**Unit** — normalization, enrichment, fusion, attention-layer transitions, focus
selection, the five Level-2 states as five separate assertions.

**Integration** — the decision pipeline at Level 1 and Level 2 over the same
request; sensor lifecycle under permission revocation.

**Real Postgres (`real_infra`, ADR-033)** — `cognitive-state-engine`'s
persistence; a new `real-infra-checks.yml` matrix row.

**Contract** — the eleven controls of §14.

**Rust** — the companion's own suite; **new to this repository**, and `pr-checks.yml`
has no Rust job today (D-4F-7).

**Browser E2E** — §17.

---

## 16. Real-infrastructure requirements

Docker is unreachable in the implementation environment, so — exactly as in 4D
and 4E — **every real-infrastructure and browser result will be CI's and must be
labelled as such**. No local claim substitutes.

**AC-7 is the hard case.** It needs a real OS signal and a real permission
revocation. A CI container has no desktop session. **How AC-7 is executed in CI
without fabricating a sensor reading is D-4F-8, and it is not answerable from the
repository as it stands.**

---

## 17. Browser E2E requirements

| Spec | Asserts |
|---|---|
| AC-7 latency | A real project-open reaches the World Model within **1 s**, measured as a number, not matched as a string — 4E's discipline |
| AC-7 revocation | Revoking the OS permission visibly stops the stream in the panel |
| AC-8 | The same action category: approval-required at Level 1, auto-executed at Level 2, **both rendered** |

Every spec runs through `api-gateway` and `ws-gateway` only.

---

## 18. Persistence, migration, rollback, SLOC

**Persistence.** A new `cognitive_state` schema owned solely by the new engine;
additive tables only; **zero existing tables altered**. Whether companion sensor
registrations persist is D-4F-5's consequence.

**Migration/rollback.** Every table additive, so rollback is dropping a schema
nothing else references. **The one genuinely irreversible step is behavioural:**
once Level 2 is selectable and a policy lowers `requires_approval`, NOVA can act
unattended. Rollback is setting the level back to 1 — and §11.7's fail-closed
defaults mean the *absence* of configuration is always the safe state.

**SLOC.** Base at `c04b58e`: **35,733 / 41,074 / 44,706** (`cloc` v2.06,
`--skip-uniqueness --quiet`, pristine `git archive`). 4F is the largest milestone
— a new engine, a new Rust process, a panel and three engine extensions.
**The 50,000 gate has 5,294 of headroom on the widest scope and this milestone
may cross it.** SAD 15 §10's milestone check must be run *during* 4F, not only at
its Gate Review, and crossing it triggers a Project Health Review.

---

## 19. Decisions required before implementation

**Three blocking, five non-blocking. This TDD must not be implemented until at
least D-4F-1, D-4F-2 and D-4F-3 are answered.**

### 19.1 D-4F-1 — AC-7's one-second budget — **BLOCKING**

A 10 s outbox cron cannot serve a 1 s criterion (§0.1.1). Options:

| | Option | Cost |
|---|---|---|
| **A** | **Shorten the cron** for `perception-engine` | Cheapest; still polling, so a 1 s *guarantee* is not established, only made likely. Raises DB load |
| **B** | **A latency-critical direct-publish path** for this one subject, bypassing the outbox | Meets the budget. **Gives up atomicity for that subject** and creates a second publish path the 4E stack guard does not model |
| **C** | **Push-triggered dispatch** — the write signals the dispatcher instead of waiting for the tick | Keeps atomicity *and* meets the budget. The largest change, and it touches `nova-service-kit`, i.e. **every** engine |
| **D** | **Renegotiate the criterion** | AC-7 is a ratified acceptance criterion; only the user can change it |

**Recommendation: C, or D.** B trades away the guarantee Phase 1 established and
Phase 4E's guard now enforces, for one subject — that is the option most likely
to be regretted.

### 19.2 D-4F-2 — CF-9 and AC-8 — **BLOCKING**

AC-8's low-risk auto-execution is **denied at `action-engine` stage 3** with no
identity-confidence policy row, because the absent-policy threshold is 1.0 at
*every* risk level (§0.1.2). Either 4F builds CF-9's missing policy-creation
surface — reversing D-4D-2's routing — or **AC-8 cannot be met**. No third option
exists that does not weaken a fail-closed security gate, and weakening it is not
proposed.

**This TDD does not close CF-9. It reports that AC-8 depends on it.**

### 19.3 D-4F-3 — who triggers an autonomous decision — **BLOCKING**

CF-11: nothing calls `decide()` (§0.1.3). AC-8 needs a real trigger.
`cognitive-state-engine` is the natural owner — Bible Part 6's Active Thoughts
are ongoing reasoning processes with priority, progress and dependencies — but
**no authoritative document assigns it**, and assigning it would give the new
engine the power to initiate action on its first day.

### 19.4 D-4F-4 — how AC-7 clause 2 reaches the UI

A new `PUBLIC_TOPICS` entry, or a `/v1/perception` D-6 prefix that also exposes
**consent revocation and biometric enrollment** (§0.1.5). **Recommendation: the
single `PUBLIC_TOPICS` entry**, as the narrower and more honest surface — one
read-only subject rather than an entire subtree including writes.

### 19.5 D-4F-5 — the companion→engine transport

No precedent exists for a non-Python process feeding an engine (§5.3).

### 19.6 D-4F-6 — does any cognitive-state subject have a genuine consumer?

If the panel reads over REST and nothing else consumes cognitive state, **D-4D-1
says publish nothing**. A subject exists to be consumed, not to be complete.

### 19.7 D-4F-7 — Rust in CI

No Rust toolchain, no `cargo` job, no `build-and-scan` entry for a non-Python
artifact. Whether the companion ships as a container at all is part of this.

### 19.8 D-4F-8 — how AC-7 is executed in CI without fabricating a sensor

§16. A CI container has no desktop session, and §2 rule 6 forbids fabricating the
reading. **This is the single largest unresolved risk in Phase 4F**, and it is a
question about the acceptance criterion's executability, not about the design.

---

## 20. Documentation, Gate Review and closure requirements

**Documentation** — this TDD kept current; a `phase-4f.md` health record
(23 fields); the master timeline row; the roadmap 4F row; the master scope's 4F
closure note; the `cognitive-state-engine` README; corrections additive per
protocol §0.3.4.

**Gate Review** — `docs/roadmap/architecture-reviews/phase-4f-*-gate-review.md`,
following 4D's and 4E's shape, and additionally required to cover: the **five
Level-2 states individually**, AC-7's latency **as a measured number**, the
CF-9/CF-10/CF-11 disposition each stated separately, and the SLOC gate (§18).

**Closure** — protocol §3.2's eleven GO conditions and all ten
`definition-of-done.md` items; merged into `phase-4` by a **normal two-parent
merge**; `phase-4f` preserved; `main` untouched at `7e273e6`.

**Phase 4F is the last Phase 4 milestone.** Its closure is immediately followed
by Phase 4's own Gate Review and the single `phase-4 → main` promotion — so 4F's
closure must leave **every** Phase 4 carry-forward explicitly dispositioned,
including the `README.md` Phase 4 status line that 4C, 4D and 4E each carried
forward.

---

## 21. Compatibility with the Bible

| Source | 4F's relationship |
|---|---|
| **Part 6** — Cognitive State Engine | Active Thoughts (7 fields), the Focus System (6 inputs), five Attention Layers, implemented as named |
| **Part 11** — Perception Engine | The Sensor Abstraction Layer is used as designed, not redesigned |
| **Part 14** — Autonomy Engine | Level 2 is *"Low risk actions execute automatically"*, enabled exactly and only at LOW risk |
| **Part 12** — Action Engine | Every 4F actuator goes through the unchanged Action Principle lifecycle |
| **Part 16** — Digital Twin | Untouched by 4F |

---

## 22. Status

**NOT RATIFIED. Not implementable as written.** Three blocking decisions
(§19.1–19.3) and five further open questions must be answered first. No
`phase-4f` branch exists; no implementation scaffolding has been generated; no
implementation file has been modified.
