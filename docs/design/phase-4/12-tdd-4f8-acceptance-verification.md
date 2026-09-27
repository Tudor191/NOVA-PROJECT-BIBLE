# TDD 4F.8 — The acceptance slice
## AC-7 and AC-8 end to end, and the evidence Phase 4F's closure needs

**Status: PREPARED 2026-09-27. NOT RATIFIED. NOT implementation-ready.**

- **What this is.** The implementation contract for 4F.8, *"the final
  implementation slice"* (TDD 4F §18, as amended by §24). It reconciles AC-7 and
  AC-8 against the repository as merged, and it names every decision still owed.
- **Blocking before implementation.** Eight decisions, **A-4F8-1 … A-4F8-8**
  (§7), must be ratified first. One of them, A-4F8-1, is RS-3b's revocation
  owner, which TDD 4F §24.4 says *"must be ratified before the 4F.8 TDD"*. So
  this document can be *prepared* now, but it cannot be *ratified* until
  A-4F8-1 is.
- **Ordering, already ratified.** **4F.P comes before 4F.8** (RS-1c). 4F.P has
  no TDD and no branch. This document **does not absorb 4F.P**: §11 lists what
  4F.8 needs from 4F.P as interface requirements only, and each one stays
  4F.P's to decide.
- **Not blocking 4F.8's implementation:** A-4F8-9 (unassigned 4F deliverables;
  it blocks 4F's GO, not this slice) and A-4F8-10 (deployment; recommended
  default).
- **No implementation exists.** This document was prepared on the
  documentation branch `phase-4f8-tdd`. No implementation branch exists, and no
  production file, test, migration, Dockerfile, workflow, contract or package
  was modified to prepare it.
- **CF-9, CF-10 and CF-11 stay OPEN.** Nothing here closes any of them.

| | |
|---|---|
| **Date** | 2026-09-27 |
| **Prepared against** | `phase-4` = **`9d2d63613fabf98c85dcdfa7c5a90fba4233baff`**, the merge of PR #38 (4F.7): parents `4e19ed1` and `d4502a9`. `main` = **`7e273e62e942ecd5528ca807e65933d6bb675669`**. Every repository fact below was read at this tree |
| **Protocol** | [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md), sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`, 1131 lines, read from `origin/main` |
| **Subordinate to** | [TDD 4F](06-tdd-4f-companion-and-cognitive-state.md), especially §4, §6, §9, §11, §12, §15, §16, §18 as amended, §20, §21 and §24. Also TDDs [4F.3](07-tdd-4f3-nova-companion.md), [4F.4](08-tdd-4f4-identity-confidence-policy.md), [4F.5](09-tdd-4f5-autonomy-level-2.md) §22, [4F.6](10-tdd-4f6-initiative-trigger.md) §15 and §19, and [4F.7](11-tdd-4f7-cognitive-state-panel.md) §15, §19 and §28. **Where this document and TDD 4F disagree, TDD 4F governs**, and the disagreement belongs in §7, not in an implementation |
| **Acceptance criteria** | [`00-master-scope.md`](00-master-scope.md) §1.1 **AC-7** (revised 2026-09-15) and **AC-8**. They are authoritative for Phase 4 (roadmap Phase 4 entry, status note) |
| **Bible** | [Part 14](../../bible/part-14-autonomy-engine.md) l.101–107 (*"Level 2 · Assisted. Low risk actions execute automatically. Important actions require confirmation."*); [Part 11](../../bible/part-11-perception-engine.md) l.569 (*"Every perception source requires explicit permissions."*); [Part 12](../../bible/part-12-action-engine.md) (the Action Principle lifecycle) |

---

## 0. How to read this document

- **§1–§3** fix the slice's scope, its non-goals and the verified baseline.
- **§4** reconciles the fifteen subjects the preparation instruction names,
  one by one, against source.
- **§5** records the findings this preparation made. Several of them are why
  the slice is not yet implementable.
- **§6** classifies every open or deferred item into exactly one of five
  classes.
- **§7** holds the ratification candidates. **Nothing in §7 is decided.** Each
  carries a recommendation, and a recommendation is not a decision.
- **§8–§22** are the contract: ownership, subjects, API, persistence, data
  flow, the Level 2 lifecycle, the trigger-to-execution flow, verification,
  negative controls, real infrastructure, Playwright, and closure.
- **Wherever a section depends on a §7 candidate**, it says which one, and it
  says what holds under the recommended option. **If the user ratifies a
  different option, that section is amended additively before implementation.**

---

## 1. Purpose and exact scope

TDD 4F §18's 4F.8 row, verbatim:

> **4F.8** | **The final implementation slice.** E2E: AC-7 (5 s, **honestly
> measured per §20.1** — no cron alignment, no bounded retry) and AC-8 (both
> levels). Performs the real acceptance verification | Both criteria in a
> browser, or the evidence that AC-7 cannot be met

**4F.8 is the acceptance slice.** It does the following:

- it makes AC-7 and AC-8 demonstrable against the real, deployed system;
- it measures them honestly;
- it produces the evidence 4F closure's Gate Review (L-1) and the Phase 4 Gate
  Review need.

It builds only what that demonstration genuinely lacks. Each piece of it
depends on a ratified decision (§7).

### 1.1 The proposed 4F.8 scope

Conditional on ratification. The table states the recommended option in each
case.

| # | Deliverable | Needed for | Depends on |
|---|---|---|---|
| **D1** | **Revocation detection in `nova-companion`.** The companion detects that the OS permission on its configured directory was withdrawn, and reports it | AC-7 *"revoking … permission stops the perception stream"* | **A-4F8-1** |
| **D2** | **A `failed` path for the filesystem sensor in `perception-engine`.** A reported revocation moves the sensor `running → failed` through the existing `report_error` path, and publishes it through 4F.7's existing `perception.sensor.health_changed` path. The existing `running` gate (`workspace_orchestration.py` l.94) then drops every further observation | AC-7 clause 2 | **A-4F8-1** |
| **D3** | **Known-project correlation in `perception-engine`.** The correlation table that has been empty since 4F.2 (`main.py` l.169; ledger **L-13**) gains a ratified population source | AC-7 *"a known project"* | **A-4F8-2** |
| **D4** | **Deployment for the acceptance stack.** `perception-engine`, `perception-engine-worker` and a real `nova-companion` process join the e2e stack, and `perception-engine`'s `primary_user_id` is configured | AC-7 end to end | **A-4F8-10** |
| **D5** | **The AC-7 acceptance harness** (test infrastructure): the honest latency measurement and the revocation demonstration | AC-7 | **A-4F8-6**, A-4F8-1, A-4F8-2 |
| **D6** | **The AC-8 acceptance harness** (test infrastructure): the same category at Level 1 and Level 2, triggered in production | AC-8 | **A-4F8-3**, **A-4F8-4**, **A-4F8-5**, **A-4F8-7**, and **4F.P merged** |
| **D7** | **Playwright specs** for each criterion's browser-visible clause | AC-7 clause 2; AC-8's Level-1 proposal | A-4F8-7 |
| **D8** | **Structural controls** that make §20.1's prohibitions enforceable against the harness itself (§17) | AC-7's honesty | — |
| **D9** | **Documentation and the 4F.8 Slice Completion Record.** It is a slice record, not a Gate Review; the Gate Review is L-1 | Protocol §0.1 | — |

**Not 4F.8's**, even though AC-8 needs them:

- **4F.P's outputs:** the promotion driver, thought ingestion, `ProposedAction`
  authorship, CAS on the promotion transition, and Layer 2 deduplication (RS-1c).
- **The `action.execute` executability extension (A-4F8-3).** The
  recommendation assigns it to **4F.P's TDD**, because it is part of what a
  *complete* `ProposedAction` must carry.

### 1.2 The slice's exit criterion

**AC-7 and AC-8 each demonstrated against the deployed system, with the
evidence recorded.** For AC-7, the alternative is equally acceptable: **the
measured evidence that AC-7 cannot be met** (TDD 4F §20.1: *"Both outcomes are
acceptable outputs of 4F.8; only a test that conceals the answer is not."*).

---

## 2. Non-goals

| Excluded | Why |
|---|---|
| **Any 4F.P work**: thought ingestion, the promotion policy, `ProposedAction` authorship, CAS, Layer 2 deduplication, a production caller of `promote_thought` | RS-1c; TDD 4F §18 as amended. §11 states what 4F.8 needs *from* 4F.P, and decides none of it |
| Changing the transactional outbox, shortening the 10 s cron, a direct-publish bypass or push-triggered dispatch **in order to satisfy AC-7** | D-4F-1; TDD 4F §20.1 |
| Aligning the measurement to the cron, retrying or re-running a failed measurement, fake clocks, fabricated timestamps, injected bus messages, mocked transport, fabricated sensor events | TDD 4F §16.1 controls 12 and 14; §20.1 |
| A new Event Bus subject; any `PUBLIC_TOPICS` change | TDD 4F §11.4, §16.1 control 2; RS-3a |
| A `/v1/perception` or `/v1/world` gateway prefix; any new gateway prefix | D-4F-4; RS-5; master scope §6 (`world-model/` is a Phase 5 panel) |
| A `TrustMetric` subject, RPC or route; closing CF-10 | TDD 4F §11.4; TDD 4F.6 §19 row 17 |
| A new autonomy REST route | TDD 4F §12; TDD 4F.6 §19 row 18. Subject to A-4F8-7 |
| Any change to `action-engine`'s stages, stage 3's evaluation, the approval loop or the fail-closed default | TDD 4F §5.2, §7.3; TDD 4F.4 W-6; TDD 4F.5 §18 |
| A production identity-confidence default or seed | D-4F4-4 |
| A consent subsystem for the filesystem source (L-14) | D-4F3-3. AC-7 concerns **OS-level permission**, not app consent (RS-3a's Option C analysis) |
| Desktop/window-focus, clipboard and process/system-health sensors; terminal and window-control actuators; multi-modal fusion; the "meeting begins" scenario | Not an AC-7/AC-8 dependency. Their unassigned status is A-4F8-9 |
| Autonomy Levels 3–5 | TDD 4F §2.1 |
| A policy-authoring UI for `AUTO_EXECUTE` (L-17) | TDD 4F.5 §18: *"Not in 4F at all"* |
| The 4F Gate Review, the Project Health record and the roadmap/README closure edits | L-1 … L-4, L-6; 4F closure, after 4F.8 |
| Closing CF-9, CF-10 or CF-11 | TDD 4F §5.3, §6.1; TDD 4F.6 §15 |

---

## 3. Baseline — verified at `9d2d636`

| Fact | Value | Evidence |
|---|---|---|
| `origin/phase-4` | `9d2d63613fabf98c85dcdfa7c5a90fba4233baff` | `git rev-parse`; merge of PR #38, parents `4e19ed1`, `d4502a9` |
| `origin/main` | `7e273e62e942ecd5528ca807e65933d6bb675669` | `git rev-parse`; untouched since Phase 4 began |
| Slices merged | 4F.1 … 4F.7 | Master scope §5; the seven completion records |
| **Registered Event Bus subjects** | **120** | `len(_REGISTRY)` after importing every `nova_contracts.events` module. The only `autonomy.*` subject is `autonomy.decision.requested` |
| **`PUBLIC_TOPICS`** | **18** strings, three of them `perception.*`: `identity.observed`, `presence.observed`, `sensor.health_changed` | AST parse of `ws-gateway/domain/protocol.py` |
| **`api-gateway` prefixes** | **Nine**: `/v1/communication`, `/v1/plans`, `/v1/reasoning`, `/v1/capabilities`, `/v1/action`, `/v1/agents`, `/v1/autonomy`, `/v1/digital-twin`, `/v1/cognitive-state`. **No `/v1/perception`, no `/v1/world`, no `/v1/memories`** | `api-gateway/domain/routing.py` l.104–214 |
| **The e2e stack** | Starts neither `perception-engine`, `perception-engine-worker` nor `nova-companion` | `pr-checks.yml` l.253–266 |
| `nova-companion` compose service | **None**. Its image is built and Trivy-scanned in `build-and-scan.yml` (4F.3) | `docker-compose.local.yml`: 0 matches |
| `perception-engine`'s `primary_user_id` | Defaults to **`None`** and is **not set in compose**, so every workspace observation is refused with `primary_user_id_not_configured` | `config.py` l.55; `workspace_orchestration.py` l.103–107; compose l.621 |
| Perception outbox dispatch | Arq cron at seconds **{0, 10, 20, 30, 40, 50}**, a fixed 10 s tick | `perception-engine/workers/__init__.py` l.87 |
| **SLOC, 4F scope** | **47,433**. Comparable 37,413; Wider 42,754; Full 46,787; companion less tests 646. **Headroom to 50,000: 2,567** | `cloc` v2.06 `--skip-uniqueness --quiet` over a pristine `git archive` of `9d2d636`, the 4E methodology. It reproduces the 4F.7 record §7.4 exactly |
| Docker in this environment | Not available | Every real-infrastructure and browser result is CI's (TDD 4F §16.3) |

---

## 4. Reconciliation — the fifteen subjects, against source

Each subject records what exists, what AC-7 or AC-8 needs from it, and what is
missing. The findings in §5 are referenced by number.

### 4.1 AC-7 (revised, ratified 2026-09-15)

> *"A known project becoming active on the user's machine is detected by a
> `nova-companion` sensor, without user action, and is reflected in the World
> Model **within five seconds**; and revoking that sensor's OS-level permission
> stops the perception stream, **visibly**, in the Digital Twin / Cognitive
> State panel."*

| Clause (TDD 4F §4.1) | State at `9d2d636` | What 4F.8 needs |
|---|---|---|
| *"a known project becoming active"* | A real file event in a watched directory is observed (4F.3 S-1) | — |
| *"known"* | **Not satisfiable.** `known_projects` is `{}` with no population path, and it is keyed per file hash. No event anywhere links a `project_id` to a location (F-4F8-5) | **A-4F8-2** → D3 |
| *"detected by a `nova-companion` sensor"* | Real: the companion's `notify` watcher (4F.3) | D4: the companion in the acceptance stack |
| *"without user action"* | The companion loop is autonomous (`main.rs` l.94–134) | The harness makes no request in the chain |
| *"reflected in the World Model"* | Real: `perception.workspace.observed` → the existing wildcard → `make_perception_observed_handler` → `WorldObject` (4F.2). The object is **per file**, and **`project_id` is not stored** (F-4F8-6) | Observed by the harness through `world-model-engine`'s own REST (**A-4F8-6**). There is no browser surface for it |
| *"within five seconds"* | Never measured. Dispatch waits for a fixed 10 s tick | **A-4F8-6** → D5 |
| *"revoking that sensor's OS-level permission"* | **No mechanism.** The companion observes only create and modify-data events (`sensors/lib.rs` l.72–78), and reports nothing else (F-4F8-7) | **A-4F8-1** → D1 |
| *"stops the perception stream"* | The pipeline gate exists: a non-`running` sensor's observations are dropped (`workspace_orchestration.py` l.94–101). **But nothing can move the filesystem sensor out of `running`** | **A-4F8-1** → D2 |
| *"visibly … in the panel"* | **Built by 4F.7.** The panel renders `cognitive_state.sensor_state`, fed by `perception.sensor.health_changed` | A real revocation to render (D1, D2) |

**Status: NOT MET, and not yet demonstrable.** Four clauses need a decision
first.

### 4.2 AC-8 (unchanged)

> *"The same action category that is blocked at Level 1 auto-executes at Level 2
> for a low-risk case, purely by policy — no code path differs."*

| Clause (TDD 4F §4.2) | State at `9d2d636` | What 4F.8 needs |
|---|---|---|
| *"the same action category"* | One `DecisionRequest` shape serves both levels (4F.5 X-8) | Two runs through the same production trigger |
| *"blocked at Level 1"* | Real: `PROPOSE` plus a suggestion (4D; 4F.5 X-4) | Demonstrated from the production trigger |
| *"auto-executes at Level 2"* | **Dispatch exists** (4F.5), **but no real dispatch can execute.** `autonomy-engine` sends `parameters={}` (`decision.py` l.211), and `action-engine` fails any request without `parameters["operation"]` at stage 2 (`pipeline.py` l.128–135). **This was never exercised**, because 4F.5's and 4F.6's real-infrastructure tiers drove a stand-in responder (F-4F8-1) | **A-4F8-3** |
| (same clause) — the trigger | 4F.6 built the consumer. **The producer has no production caller**: F-6, owned by **4F.P** | **4F.P**; **A-4F8-4** |
| (same clause) — stage 3 | 4F.4's write surface exists. **With no identity signal in CI, stage 3 reads confidence 0.0** (F-4F8-4) | **A-4F8-5** |
| *"for a low-risk case"* | Risk is classified **twice**: autonomy uses the authored risk, and `action-engine` re-derives its own from `(action_type, operation)` (F-4F8-3) | A constraint inside **A-4F8-3** |
| *"purely by policy"* | `requires_approval` is lowered only by an in-bounds `AUTO_EXECUTE` (D-4F5-1) | Between the two runs, only the autonomy level differs |
| *"no code path differs"* | The single-dispatch rule, test-enforced at the unit tier (4F.5 X-8, §16 control 4) | Re-asserted end to end (§16, E-10) |

**Status: NOT MET, and not yet demonstrable.** It needs 4F.P merged and four
decisions.

### 4.3 The existing Level 2 implementation (4F.5)

States 2, 3 and 5 are **built and CI-verified** (4F.5 record §12.7, 40/40 at
`f0ee8ae`):

- `SELECTABLE_LEVELS` includes `ASSISTED`;
- `PolicyEffect.AUTO_EXECUTE` is inert above `low` and fail-closed by absence;
- the single dispatch point sends one bounded **15 s** `action.execute`
  request/reply, with no retry;
- a no-responder dispatch degrades to a proposal through
  `ActionDispatchUnavailable`;
- the Trust contract of §22.7 holds.

**4F.8 changes none of it.** Two facts matter here:

- the payload builder sends `parameters={}` (F-4F8-1);
- `EXECUTE` is recorded for any reply status (F-4F8-2).

### 4.4 The *Triggered* state (4F.6)

- **The consumer exists and runs in production.**
  `decision_orchestration.handle_decision_request` is the only production
  `decide()` call site. It is served by `autonomy-engine`'s lifespan on the
  internal subject `autonomy.decision.requested`.
- **The producer has no production caller.** `promote_thought` is called by
  nothing in production (4F.7 P-14 asserts this).
- **So the production end-to-end *Triggered* state is not evidenced** (RS-6b).
  TDD 4F.6 §2 defines it as *"a production component, reachable in a deployed
  system without a test harness"*.
- **4F.P supplies that component.** 4F.8 then demonstrates it (CF-11 claim 3).
- ***Triggered* remains a system-level property** (RS-6a). 4F.8 adds no
  per-thought state.

### 4.5 The read-only cognitive-state infrastructure (4F.7)

- It serves exactly three `GET`s under `/v1/cognitive-state`: `thoughts`,
  `focus` and `sensors`. Identity is server-side, and every body is strict.
- It is deployed in compose and in the e2e stack.
- The panel fetches on mount and on Refresh, with no polling (A-4F7-3 (a)).
- **4F.8 uses the `sensors` read and the panel to show AC-7's revocation. It
  adds nothing to the surface.** No write route and no decision data, per
  RS-1b and RS-4b.

### 4.6 The perception sensor lifecycle integration (4F.7)

- `perception-engine` publishes `perception.sensor.health_changed`, carrying
  `SensorState` values read after each real transition. The call sites are
  startup, consent revocation, an observation-window failure and shutdown
  (`sensor_lifecycle.py`).
- `cognitive-state-engine` stores the current state per sensor, with an
  idempotent, order-safe upsert.
- **The filesystem sensor can reach `initialized`, `running` and `stopped`,
  but never `failed`.** Its `report_error` records without transitioning
  (`filesystem_sensor.py` l.154–162), and its `permission_status` is always
  `granted` (l.135–149).
- **D2 adds the `failed` transition**, subject to A-4F8-1. It reuses
  `sensor_lifecycle.report_sensor_error` exactly as camera and voice already do.
- **K-1 still applies.** A report dispatched while `cognitive-state-engine` is
  unsubscribed is lost. The harness therefore revokes only after that engine is
  ready and subscribed, which is sequencing, not fabrication (§16, E-6).

### 4.7 Digital Twin and Memory data (4E and earlier)

- **Memory** carries `project_id` on `memory.short_term.created` and
  `memory.long_term.created`. **No memory payload carries a location, a path or
  a root hash.**
- **Digital Twin** derives its Project Model from `MemoryRecord.project_id`,
  *"the only project identity anywhere in this repository"*
  (`digital-twin-engine/domain/models.py` l.365–373). It has **no filesystem
  root** either.
- **Consequence:** NOVA knows which projects exist, but not **where** any of
  them is. That gap is L-13 and F-4F8-5, and **A-4F8-2** decides how a location
  becomes known.
- **Neither engine is modified by the recommendation.** Both remain read only
  through the Event Bus (ADR-004; TDD 4F §9).
- **Neither is a data source for autonomy** (TDD 4F.5 §2.3). That stays true.

### 4.8 The Trust Engine and Policy Engine boundaries

- **The Policy Engine and the Permission Matrix** run in `autonomy-engine`,
  deny-only, in the fixed order `evaluate_gates()` sets. Only an in-bounds
  `AUTO_EXECUTE` lowers `requires_approval` (D-4F5-1).
- **The Trust Engine** stays `UNAVAILABLE`, which is non-blocking and **never
  a pass** (§22.7). There is no threshold, no default score and no coercion.
  **CF-10 stays OPEN.**
- **4F.8 changes neither.** Its AC-8 configuration is set through the
  **existing** routes:
  - `PUT /v1/autonomy/level`;
  - `POST /v1/autonomy/policies`, since L-17 means the panel cannot author
    `AUTO_EXECUTE`;
  - `PUT /v1/autonomy/permissions`.

### 4.9 The `action-engine` dispatch boundary

- `action-engine` serves `action.execute` as a request/reply RPC and runs the
  Action Principle lifecycle unchanged. Its stages, as they bear on AC-8:
  - **stage 2** requires `parameters["operation"]` (`pipeline.py` l.128–135);
  - **risk** is `classify_risk(action_type, operation)` (l.138; `risk.py`
    l.26–41);
  - **stage 3** is the ADR-032 identity gate, against confidence from
    `world_model.context.request` (l.180–202; `identity_client.py` l.34–52);
  - **approval** applies to **CRITICAL** risk only (l.214);
  - **stage 5** resolves the capability **by `execution_target` name** (l.234);
  - **stage 6** invokes it through `capability-engine` (l.296).
- The four built-in capabilities are bootstrap-installed at startup
  (`capability-engine/main.py` l.191): `filesystem` (`read`, `write`, `list`),
  `terminal` (`execute`), `git` and `http`.
- **4F.8 modifies none of this** (TDD 4F §7.3).

### 4.10 The `action.execute` contract and its execution semantics

- **The contract:** `ActionExecuteRequestPayload` (`events/action.py`
  l.152–181), whose `parameters` is a free `dict` (l.172).
- **Its only producer:** `autonomy-engine`'s `_execution_payload`
  (`decision.py` l.180–215). It fills `action_id = subject_id`,
  `requested_by = primary_user_id`, `priority="normal"` and
  `parameters={}`.
- **Its only production consumer:** `action-engine`.
- **The two do not compose into a successful execution**, for three reasons:
  - no `operation` is ever supplied (F-4F8-1);
  - `EXECUTE` is logged whatever `action-engine` replies (F-4F8-2);
  - the risk the policy saw and the risk `action-engine` enforces can differ
    (F-4F8-3).
- **A-4F8-3 decides how an executable request is formed.** 4F.8 then asserts
  `action-engine`'s terminal status (`completed`), not only autonomy's outcome.

### 4.11 The `autonomy.decision.requested` trigger architecture

- **The subject:** internal, request/reply, exactly one consumer, not in
  `PUBLIC_TOPICS`; registry 119 → 120 (D-4F-9, §11.5).
- **The payload:** `AutonomyDecisionRequestedPayload` (`events/autonomy.py`
  l.83–128). It is `extra="forbid"`, and it carries `category`, `risk`,
  `action_type`, `execution_target`, `verification_method`, `title`,
  `detail`, `priority`, `thought_id`, `requesting_engine` and
  `correlation_id`, **but no `operation` and no `parameters`**.
- **Identity:** `subject_id = uuid5(ns, event_id)`, derived by the consumer.
- **Not implemented:** no TTL and no Layer 2 deduplication (both still OPEN or
  DEFERRED).
- **The producer's reply wait:** 20 s, unratified (4F.6 F-2).
- **4F.8 uses the path as built.** Any payload extension is A-4F8-3's, and the
  recommendation places it with 4F.P.

### 4.12 The deferred 4F.P items

Owned by 4F.P and **not absorbed here** (RS-1c, RS-2b, RS-7):

- the promotion policy;
- the thought-ingestion mapping;
- the `ProposedAction` authorship rule;
- the CAS transition semantics;
- A-4F6-3 Layer 2 logical deduplication;
- a production caller of `promote_thought` (F-6).

**AC-8's authoritative evidence depends on all of them** (A-4F8-4). §11 lists
the properties 4F.8 needs 4F.P's result to have.

### 4.13 CF-9, CF-10 and CF-11

| | Status | What 4F.8 contributes | Where it settles |
|---|---|---|---|
| **CF-9** | **OPEN.** Conditions 1, 3 and 4 were evidenced by 4F.4. Condition 2 is answered by D-4F4-1 and awaits citation. **Condition 5 is unmet** | The first **deployed-stack use** of the policy surface on AC-8's path (A-4F8-5). **No closure evidence beyond that** | **4F closure (L-1):** conditions 2 and 5. §5.3's five-point checklist applies unchanged |
| **CF-10** | **OPEN.** Structurally blocked: a Trust read surface is forbidden by §11.4 | **None.** `UNAVAILABLE` stays non-blocking and never a pass (§22.7) | **Beyond Phase 4.** It must be dispositioned in Phase 4's closure, not closed |
| **CF-11** | **OPEN.** Claims 1–2 were evidenced by 4F.6 | **Claim 3** (end-to-end, in a running system) — **only with the production trigger** (A-4F8-4) | Claim 3: 4F.8, after 4F.P. **Claim 4** (recorded closure evidence): **4F closure** |

### 4.14 The open ledger rows L-14 and L-16 … L-22

Classified individually in §6. **None is required to implement 4F.8.** L-13
**is** required, which is why it has its own decision (A-4F8-2).

### 4.15 Additional unresolved dependencies genuinely required by AC-7 or AC-8

| Dependency | Required by | Handled by |
|---|---|---|
| L-13, known-project correlation | AC-7 *"known"* | A-4F8-2 |
| An executable `action.execute` | AC-8 *"auto-executes"* | A-4F8-3 |
| An identity-confidence configuration that the real stage 3 passes in CI | AC-8 *"auto-executes"* | A-4F8-5 |
| `perception-engine`, its worker and the companion in the acceptance stack; `primary_user_id` | AC-7 | A-4F8-10 |
| A place where the World Model reflection and the Level-2 execution are observed | AC-7, AC-8 | A-4F8-6, A-4F8-7 |
| The single-component PR rule | The 4F.8 PR | A-4F8-8 |

---

## 5. Findings of this preparation

Each finding is verified at `9d2d636`. None is fixed here, since this step
changes no source.

| # | Finding | Evidence | Goes to |
|---|---|---|---|
| **F-4F8-1** | **No real Level-2 dispatch can execute.** `_execution_payload` sends `parameters={}`. `action-engine` returns `status="failed"`, *"parameters['operation'] is required"*, at stage 2, before risk, identity, capability or execution. 4F.5's and 4F.6's real-infrastructure tiers drove a **stand-in** `action-engine` responder (4F.6 record §6 item 8), so the two production engines have never been composed | `decision.py` l.211; `pipeline.py` l.128–135 | **A-4F8-3** (blocking) |
| **F-4F8-2** | **`DecisionOutcome.EXECUTE` is recorded for any reply**, including `failed` and `denied`. The reply status appears only in the reason text, *"action-engine reported {status}"* | `decision.py` l.426–447 | Evidence rule (§16 E-9). A Gate Review note; **no 4F.5 change proposed** |
| **F-4F8-3** | **Risk is classified twice.** The policy gate uses the authored `risk`. `action-engine` re-derives its own from `(action_type, operation)`, and **that** tier selects the stage-3 threshold and the approval loop. With the built-in operations, `read`/`list` are `negligible`, `write` is `moderate`, `terminal`/`execute` is `high`, and `delete`/`remove`/`format` are `critical` | `risk.py` l.26–41; `pipeline.py` l.138, l.183–184, l.214 | Constraint in **A-4F8-3** |
| **F-4F8-4** | **Stage 3 has no identity source in CI.** Confidence is read from `world_model.context.request`'s `present_identities`, which needs a camera or voice signal. The runner has neither, and fabricating one is forbidden. So confidence is `None`, which becomes 0.0 | `identity_client.py` l.34–52; `pipeline.py` l.185–187 | **A-4F8-5** (blocking) |
| **F-4F8-5** | **`known_projects` has no population path.** It is `{}` at startup and keyed by the **per-file** hash. No subject carries a location for a project. L-13 was ledgered *"4F closure or later"*, **but AC-7's "known" depends on it** | `perception-engine/main.py` l.169; `domain/workspace.py` l.83–95; `events/memory.py` | **A-4F8-2** (blocking) |
| **F-4F8-6** | **The World Model object is per file and holds no `project_id`.** The handler reads `object_id`, `label` and `user_id` only, and ignores `project_id`. The published payload says `object_type: "project"` while its `object_id` hashes a file path | `world-model-engine/events/handlers.py` l.79–108; 4F.2's contract | **Disclosed.** The recommendation keeps TDD 4F §11.1's *"`world-model-engine` needs zero changes"* and evidences *"known"* on the published observation (A-4F8-2) |
| **F-4F8-7** | **No revocation path exists anywhere.** The companion drops metadata events and reports only observations. The filesystem sensor cannot reach `failed`. Its `permission_status` is always `granted`. The consent API's `Source` excludes `filesystem`. **Expected but unverified:** Linux checks read permission when a watch is added, not per event, so an existing watch is expected to keep delivering after a `chmod`. The OS alone should therefore not be relied on to stop the stream, and D1's real-filesystem test must establish the actual behaviour | `sensors/lib.rs` l.72–78; `main.rs` l.94–134; `filesystem_sensor.py` l.135–162 | **A-4F8-1** (blocking) |
| **F-4F8-8** | **The acceptance stack cannot run AC-7.** The e2e job starts no `perception-engine`, no worker and no companion. `perception-engine`'s `primary_user_id` is unset in compose, so it would publish nothing | `pr-checks.yml` l.253–266; `config.py` l.55 | **A-4F8-10** |
| **F-4F8-9** | **No browser-reachable surface shows either criterion's core fact.** There is no `/v1/world` prefix. `autonomy-engine` exposes no decision-log route. `action-engine` exposes no action read route. `action-engine` publishes only approval events, and a LOW-risk action never reaches the approval loop | `routing.py` l.104–214; `api/autonomy.py` l.231–413; `action-engine/events/published.py` | **A-4F8-6**, **A-4F8-7** |
| **F-4F8-10** | **Three groups of 4F milestone deliverables have no owning slice.** They are the desktop/window-focus, clipboard and process/system-health sensors; the terminal and window-control actuators; and multi-modal fusion (L-11, *"the meeting begins scenario"*). TDD 4F.3 marked the sensors *"Later"* and the actuators *"4F.5 at the earliest"*; no later slice took them | Master scope §5 (4F); TDD 4F §2, §7.1, §9; TDD 4F.3 §1 | **A-4F8-9** (blocks 4F GO, not 4F.8) |
| **F-4F8-11** | **Stale status statements in scope documents.** Master scope §17's 4F.7 row still reads *"Implementation has not begun"*, and §5 carries no note that 4F.7 merged. The roadmap's 4F row still reads *"2 of 8 slices merged"* | `00-master-scope.md` l.1108, l.526–541; `ENGINEERING_ROADMAP.md` l.587 | The two master-scope statements are **corrected additively in this change** (§21.3). The roadmap stays with **L-4/L-22** at 4F closure |
| **F-4F8-12** | **Both acceptance-carrying workflows are non-blocking by design**: the Playwright job (*"staged, non-blocking"*) and `real-infra-checks.yml` | `pr-checks.yml`; protocol §10.1 | The Gate Review must cite their conclusions **explicitly** at the exact SHA (§19) |

---

## 6. Classification of every open or deferred item

The five classes:

| Class | Meaning |
|---|---|
| **R** | **Required for 4F.8** |
| **N** | **Not required for 4F.8, and remains deferred** |
| **B** | **Required to close Phase 4, but belongs to another already-defined boundary** |
| **D** | **Documentation or verification only** |
| **U** | **Still unresolved, and requiring ratification before implementation** |

**Protocol §0.2 still governs every ledger row, whatever its class.** A
Sub-Phase may not be declared complete while any row is unsettled. So each row
below must be **settled at 4F closure**: done, or deferred by recorded approval.

| Item | Source | Class | Owner / settles at | Why |
|---|---|---|---|---|
| **RS-3b** — OS-level revocation detection | TDD 4F §24.4 | **U** → **R** once ratified | **A-4F8-1**; then 4F.8 (D1, D2) | AC-7 clause 2. RS-3b requires it before the 4F.8 TDD |
| **L-13** — `known_projects` population | 4F.2 record §11.2 | **U** → **R** | **A-4F8-2**; then 4F.8 (D3) | AC-7 *"known"* (F-4F8-5) |
| `action.execute` executability | F-4F8-1 | **U** | **A-4F8-3**; recommended owner **4F.P's TDD** | AC-8 *"auto-executes"* |
| The AC-8 trigger source | RS-8, RS-1c | **U** | **A-4F8-4** | Whether AC-8 may be MET by a stand-in |
| The stage-3 configuration in the acceptance stack | F-4F8-4 | **U** | **A-4F8-5** | A security semantic in the acceptance evidence |
| The AC-7 measurement protocol | TDD 4F §20.1 | **U** | **A-4F8-6** | Sample count, pass rule and observation point are unspecified |
| The AC-8 execution evidence surface | F-4F8-9; TDD 4F §18 | **U** | **A-4F8-7** | *"Both criteria in a browser"* against surfaces that do not exist |
| SAD 15 §4 item 1 for the 4F.8 PR | RS-9 precedent | **U** | **A-4F8-8** | The PR spans several components |
| Unassigned 4F deliverables: other sensors, actuators, fusion (incl. **L-11**) | F-4F8-10 | **U** (does not block 4F.8's implementation) | **A-4F8-9**; 4F closure | Protocol §0.3.6: never narrow scope unilaterally |
| Acceptance-stack deployment | F-4F8-8 | **R** | **A-4F8-10** (default); 4F.8 (D4) | AC-7 |
| **4F.P** — promotion driver; ingestion mapping; authorship rule; CAS (RS-7); Layer 2 deduplication (A-4F6-3); F-6 | RS-1c | **B** | **4F.P** (TDD, ratification, implementation, merge) | AC-8's authoritative evidence needs it; **not absorbed** (§11) |
| **CF-9** | Master scope §4 | **B** | **4F closure**: conditions 2 (citation) and 5 (documents) | Not closed by 4F.8 (TDD 4F §5.3) |
| **CF-10** | Master scope §5 (4D) | **N** | Beyond Phase 4; **dispositioned** in Phase 4's closure | TDD 4F §2.1, §11.4 |
| **CF-11** claim 3 | TDD 4F.6 §15.1 | **R** | 4F.8, **after 4F.P** | The end-to-end trigger-to-action demonstration |
| **CF-11** claim 4 | TDD 4F.6 §15.1 | **B** | 4F closure (L-1) | Recorded closure evidence |
| **L-1** — 4F Gate Review | 4F.2 record | **B** | 4F closure, after 4F.8 | Protocol §0.1: a slice defers category 3 |
| **L-2**, **L-3** — `phase-4f.md` and the master health row | 4F.2 record | **B** | 4F closure | Category 4 |
| **L-4** — the roadmap's 4F row | 4F.2 record | **D** | 4F closure | Category 5; also F-4F8-11 |
| **L-5** — master scope §17 SLOC table, §2 methodology, F-2 | 4F.2/4F.3 records | **D** | 4F closure | Category 5/12 |
| **L-6** — `README.md` (*"a new engine now exists"*) | 4F.2 record | **D** | 4F closure | Category 7 |
| **L-8** — `ws-gateway/README.md` | 4F.2 record | **D** | 4F closure | Category 7 |
| **L-9** — cross-file sweep, incl. the control 11 and *"exactly one new subject"* wording (TDD 4F §24.13) | 4F.2 record; §24.13 | **D** | 4F closure | Category 12 |
| **L-10** — `docs/` staleness sweep, incl. doc 11 l.57–59 | 4F.2/4F.4 records | **D** | 4F closure | Category 6 |
| **L-14** — filesystem consent (Doc 22 Principle 8) | 4F.3 | **N** | Settled at 4F closure, or deferred by approval | AC-7 concerns OS permission, not app consent (RS-3a Option C) |
| **L-15** — policy mutations unaudited | 4F.4 | **N** | `action-engine`, later | Not on AC-8's path |
| **L-16** — `action-engine` README Owned APIs | 4F.4 | **D** | 4F closure | Category 7 |
| **L-17** — web-client cannot author `AUTO_EXECUTE` | 4F.5 | **N** | A later policy-authoring UI scope | The harness authors through the existing REST route, disclosed (§16) |
| **L-18** — the SDK does not translate `NoRespondersError` | 4F.5 | **N** | `nova-eventbus-sdk` maintenance | Both clients on AC-8's path already defend locally |
| **L-19** — `autonomy-engine` README scaffold | 4F.6 | **D** | 4F closure | Category 7 |
| **L-20** — doc 20 and the `sensor_state` derived copy | 4F.7 | **D** | 4F closure (with L-9) | Category 12 |
| **L-21** — TDD 4E §5.1 and the 2D-B *"repeated failures"* framing | 4F.7 | **D** | 4F closure (L-9) | Category 12 |
| **L-22** — 4F.7 health, roadmap and README status | 4F.7 | **D** | 4F closure | Categories 4, 5 and 7. The master-scope half is corrected additively here (§21.3) |
| 4F.6 **TTL** and **stale-trigger semantics** | 4F.6 §16 | **N** | OPEN; dispositioned at 4F closure | Every gate still runs on a stale trigger |
| 4F.6 **persistent lost-trigger auditability** | 4F.6 §16 | **N** | A later slice | Design A is fully specified without it |
| 4F.6 **`observability.py` packaging**; **F-4F7-7** Prometheus targets | 4F.6 §16; 4F.7 §8.1 | **N** | OPEN; 4F closure disposition | Packaging, not acceptance |
| 4F.6 **`correlation_id` logging convention**; **F-7** | 4F.6 §16 | **D** | Gate Review decision | A convention |
| 4F.6 **F-1** (reply registration, 120 vs 121), **F-2** (the 20 s reply wait), **F-3**, **F-5** | 4F.6 §8.1 | **D** | Gate Review ratification | Each is recommended there |
| 4F.6 **F-4** — a redelivered `propose` replies `degraded` | 4F.6 §8.1 | **N** | A later ratified change | Safe as built |
| **F-4F7-1** — control 11's schema check is vacuous | 4F.7 | **D** | Its own ratified change (A-4F7-6 (a)) | A verification control |
| **F-4F7-4** — `digitalTwin.ts` is not strict | 4F.7 | **N** | 4E's owner | Not on either criterion's path |
| **F-4F7-5**, **F-4F7-6** | 4F.7 | **D** | 4F closure (L-9/L-10) | Documentation |
| **K-1** — at-most-once sensor reports | TDD 4F.7 §15 | **D** | Harness sequencing (§16 E-6) | Not fixed. The harness revokes only after the consumer is subscribed |
| **K-5** — Focus signals are always empty | TDD 4F.7 §15 | **N** | OPEN | Not an AC-7/AC-8 dependency |
| Part 6 INTERRUPTIONS promotion semantics | TDD 4F §24.12 | **N** | 4F.P or later | Not an AC-7/AC-8 dependency |
| `04-frontend-architecture.md:81` realtime-hydration row | TDD 4F §24.12 | **D** | 4F closure (L-10) | Documentation |
| **D-4F-1**'s residual risk: AC-7's latency | TDD 4F §20.1 | **R** | 4F.8 measures it (A-4F8-6) | The measurement *is* 4F.8 |
| **AC-3**'s and **AC-4**'s deferred clauses | Master scope §1.1 | **B** | Phase 4 Gate Review | Deferred by approval; never represented as met |
| 4A with no Gate Review or health record; 4B's open conditions C-1, C-2, C-6, C-7; 4C's C-3; 4E's three OPEN findings | Roadmap Phase 4 table; master scope §5 | **B** | Phase 4 closure | Master scope §16's close-out sequence |

---

## 7. Ratification candidates

**Eight block implementation: A-4F8-1 … A-4F8-8.**

- **A-4F8-9** blocks 4F's GO, not 4F.8's implementation.
- **A-4F8-10** has a recommended default.

A candidate is **blocking** when implementing without it would mean inventing a
security, identity, persistence, acceptance or externally visible semantic
(TDD 4F.6 §17's definition). **Nothing in this section is decided.**

### A-4F8-1 — Who detects OS-level permission revocation, and how does it reach the sensor lifecycle? **BLOCKING**

- **Question.** For the filesystem source, which component detects that the
  OS-level permission on the watched directory was withdrawn? How does that
  detection reach `perception-engine`'s sensor lifecycle, and what state
  results?
- **Why it is owed now.** RS-3b: *"The owner of revocation detection must be
  ratified before the 4F.8 TDD."* F-4F8-7 shows that no part of the mechanism
  exists.

| Option | Consequence |
|---|---|
| **(a) The companion detects; `perception-engine` owns the transition.** The companion checks its own access to the watch root when the root's metadata changes, and before each submission. On loss, it stops submitting and reports the revocation over `perception-engine`'s **existing internal surface**, through one additional internal route (TDD 4F §8.1's precedent: *"a second intake route on the same internal surface"*). `perception-engine` moves the filesystem sensor `running → failed` via `report_error`, as camera and voice already do. 4F.7's `sensor_lifecycle` publishes `failed`. The existing `running` gate drops every later observation | Real OS detection, in the only process that holds the permission. The lifecycle stays `perception-engine`'s (TDD 4F §10). **No new subject, no `PUBLIC_TOPICS` change, no gateway prefix and no consent subsystem.** Cost: Rust detection, one internal route, a `failed` transition in `FilesystemSensor`, and real-filesystem tests |
| (b) The companion exits on revocation, and `perception-engine` infers failure from the silence | **Rejected by RS-3a's analysis:** *"inferring failure from silence"* contradicts TDD 4F §4.1 |
| (c) `perception-engine` probes the directory itself | `FilesystemSensor` *"performs no detection"* (D-4F3-1). It would also need the host directory mounted into `perception-engine`, a new coupling |
| (d) Model revocation as consent revocation through `api/consent.py` | **Rejected by RS-3a's analysis:** consent records **app** consent, not OS permission, and `Source` excludes `filesystem` |
| (e) Leave it OPEN | AC-7 clause 2 is **NOT MET**, and that is a **blocking Gate Review finding** |

**Recommendation: (a).** Two sub-questions must be ratified with it:

- **(a1) The shape of the report.** Recommended: a **separate internal route**
  on `perception-engine`, not fronted by `api-gateway`. The frozen
  `POST /v1/perception/workspace-observations` contract is **unchanged** (TDD
  4F.3 §7).
- **(a2) Recovery.** Recommended: **no automatic recovery in 4F.8.**
  `failed → initialized` exists in the lifecycle, but re-granting permission
  takes effect only when the companion and engine restart. This is disclosed
  as a known limitation.

**Recommended wording (implementation-neutral):**

> *"OS-level permission revocation for the filesystem source is detected by
> `nova-companion`, the only process that holds that permission, and reported
> to `perception-engine` over its existing internal surface. `perception-engine`
> remains the sole owner of the sensor lifecycle. It moves the filesystem sensor
> to `failed` through the existing error path, publishes that transition through
> the existing `perception.sensor.health_changed` path, and drops every further
> observation because the sensor is not `running`. No new Event Bus subject, no
> `PUBLIC_TOPICS` change, no gateway prefix, no consent mechanism, and no
> inference from silence."*

- **Affected components:** `nova-companion` (Rust); `perception-engine`
  (`FilesystemSensor`, one internal route, a `sensor_lifecycle` call site).
  `cognitive-state-engine` and the panel are **unchanged**.
- **Affected criteria:** AC-7 — *"revoking … OS-level permission"*, *"stops
  the perception stream"*, *"visibly … in the panel"*.
- **Implementation must wait: yes.**

### A-4F8-2 — What makes a project "known", and how is the correlation populated? **BLOCKING**

- **Question.** How does `perception-engine` learn which filesystem location
  belongs to which project identity, without reading another engine's database?
  And where does AC-7's *"known"* show?
- **The ratified constraints:**
  - TDD 4F §4.1: *"Correlated to a `project_id`; the only project identity in
    the system is `MemoryRecord.project_id`, read **via events**, never by
    cross-engine DB access."*
  - §9: a failed correlation publishes `project_id = None`.
  - §11.1: `world-model-engine` needs zero changes.

| Option | Consequence |
|---|---|
| **(a) Operator-declared root bindings, activated by project identities learned over the Event Bus.** An operator-declared configuration binds a watched root to a project identity (D-4F3-3's precedent: the watched directory is already operator-declared). `perception-engine` learns which project identities exist from an **existing** memory subject that carries `project_id`, `memory.long_term.created`. A binding is **active only once its project identity has been seen**, and is otherwise inert. Correlation matches the file's **ancestor root** inside `perception-engine`'s trust boundary, where the path is transiently available (D-4F3-2). A match attaches `project_id` to `perception.workspace.observed`, and a miss attaches `None` | Satisfies *"read via events"* for the identity. The location is operator-declared, disclosed and never guessed. `world-model-engine` is unchanged: *"known"* is evidenced on the published observation, and F-4F8-6 is disclosed. **Adds one subscription** to `perception-engine` (an existing subject; no registry or `PUBLIC_TOPICS` change) |
| (b) Operator-declared bindings only, with no event check | Simpler. **It contradicts §4.1's "read via events"** and would need that row amended |
| (c) A new memory-side fact carrying a root or root hash | A contract change with **no producer**: nothing in the repository knows a project's location |
| (d) Leave L-13 OPEN | Every AC-7 observation publishes `project_id = None`. AC-7's *"known"* is **NOT MET** |

**Recommendation: (a).** Two sub-questions must be ratified with it:

- **(a1) Where learned identities live.** In memory, lost on restart, with a
  seed after startup in CI; **or** an additive `perception` table. Recommended:
  **an additive table**, following A-4F7-1's current-state precedent, because a
  restart must not silently make every project unknown.
- **(a2) World Model representation.** Recommended: **unchanged.** The object
  stays per file (4F.2's ratified contract). *"Reflected in the World Model"*
  is evidenced by the `WorldObject`, and *"known"* by the observation's
  `project_id`. TDD 4F §4.1's clause table already assigns the two clauses that
  way.

**Recommended wording:**

> *"An observation is of a known project when `perception-engine` correlates
> its location, inside its own trust boundary, to a project identity NOVA
> already holds, learned over the Event Bus and never by reading another
> engine's store. The binding from location to project is explicit and
> declared, never inferred. A failed correlation publishes `project_id = None`.
> `world-model-engine` is unchanged."*

- **Affected components:** `perception-engine` (configuration, one
  subscription, `resolve_project_id`'s input, optionally a table);
  `infra/docker` (configuration). `memory-engine`, `digital-twin-engine` and
  `world-model-engine` are **unchanged**.
- **Affected criteria:** AC-7 *"known"*.
- **Implementation must wait: yes.**

### A-4F8-3 — How does a Level-2 dispatch become executable, and which action is AC-8's low-risk case? **BLOCKING**

- **Question.** Where do `action.execute`'s `operation` and adapter parameters
  come from? And what makes an action "the low-risk case" when risk is
  classified twice?
- **The facts:** F-4F8-1 and F-4F8-3.
  - **`action-engine` cannot run a request that has no `operation`.**
  - **Neither the trigger payload (`extra="forbid"`) nor `DecisionRequest`
    carries one.**
  - D-4F5-2 forbids defaults and guessing.

| Option | Consequence |
|---|---|
| **(a) An authored, additive extension.** `ProposedAction` gains an `operation` and a bounded adapter-parameter object. These are authored by the same rule as its other fields and are all-or-nothing. `AutonomyDecisionRequestedPayload`, `DecisionRequest` and `_execution_payload` carry them through. They are **required at the dispatch branch only**, so absence yields a suggestion, exactly as D-4F5-2 treats the other three fields | Honest execution with no guessing. An **additive contract change**: codegen regenerates, the registry is unchanged, and `schema_version` handling is per ADR-024. It **amends** A-4F6-2a's field set and 4F.5's payload builder, both disclosed. Its natural owner is **4F.P's TDD**, which ratifies the authorship rule |
| (b) Derive `operation` from existing fields | **Guessing**, forbidden by D-4F5-2 |
| (c) Default a missing `operation` in `action-engine` | Changes Phase 3D's stage 2. TDD 4F §7.3 says *"every existing stage applies unchanged"* |
| (d) Count a stage-2 `failed` reply as "executed" | AC-8's *"auto-executes"* would be claimed on an action that never ran. **Rejected** |

**Recommendation: (a), owned by 4F.P's TDD**, which must ratify the extension
together with the authorship rule. 4F.8 **consumes** it.

**The low-risk constraint.** AC-8's action must satisfy all four of these:

1. its **authored** risk is `low` — the tier the policy gate and `AUTO_EXECUTE`
   read, which TDD 4F §4.2 names as *"`RiskLevel.LOW`"*;
2. `action-engine`'s own classification of `(action_type, operation)` is **at
   or below `low`**, so it neither enters the approval loop nor escalates the
   identity threshold;
3. it is executable by a **bootstrap-installed built-in capability** named by
   its `execution_target`;
4. its effect is **observable** by the harness without fabrication.

The concrete action is chosen **by 4F.P's authorship rule, not by 4F.8.**

**Recommended wording:**

> *"A Level-2 dispatch carries everything `action-engine` needs to execute,
> authored by `cognitive-state-engine` under its ratified authorship rule and
> never derived, defaulted or guessed downstream. Where any of it is absent the
> decision is a suggestion. AC-8's low-risk case is low risk both as authored
> and as `action-engine` classifies it."*

- **Affected components:** `nova-contracts` (`events/autonomy.py`, generated
  TypeScript); `cognitive-state-engine` (`ProposedAction`, and the trigger
  payload through 4F.P); `autonomy-engine` (`DecisionRequest`,
  `_execution_payload`, `decision_orchestration`). **`action-engine` is
  unchanged.**
- **Affected criteria:** AC-8 *"auto-executes"*, *"for a low-risk case"*.
- **Implementation must wait: yes.** 4F.P must also ratify it before its own
  implementation.

### A-4F8-4 — Does AC-8's acceptance evidence require the production trigger? **BLOCKING**

- **Question.** May AC-8 be recorded **MET** with the trigger supplied by an
  RS-8 stand-in? Or does it require 4F.P's production trigger, which makes
  4F.8's AC-8 work wait for 4F.P's merge?
- **The ratified facts:**
  - RS-1c ordered 4F.P **before** 4F.8, rejecting Alternative D because it
    *"would have left CF-11 unevidenceable within 4F"*.
  - RS-8 permits stand-ins as test infrastructure and requires the evidence to
    state that the CF-11 dependency is unmet.
  - TDD 4F §4.2 lists CF-11 as a dependency of *"auto-executes at Level 2"*.
  - TDD 4F.6 §15.1 assigns CF-11 claim 3 to 4F.8.

| Option | Consequence |
|---|---|
| **(a) Production trigger only.** AC-8's authoritative runs originate in 4F.P's production promotion driver, fed by a real input. No test code calls `promote_thought` or `decide()`, or publishes `autonomy.decision.requested`. A stand-in may appear **only** as supplementary evidence, labelled as such. **4F.8's AC-8 work starts after 4F.P is merged** | AC-8 and CF-11 claim 3 are evidenced together, as RS-1c intended |
| (b) A stand-in may make AC-8 MET, with CF-11 claim 3 recorded as unmet | AC-8 could be closed before 4F.P, but TDD 4F §4.2's dependency would be recorded as MET while unmet. That undoes RS-1c's rationale |
| (c) Split: AC-7 now, and AC-8 in a second 4F.8 PR after 4F.P | Possible **under (a)**. It is a sequencing choice, not an evidence rule |

**Recommendation: (a).** Whether to use (c)'s split is left to the user;
**recommended: one 4F.8 slice after 4F.P**, which keeps one acceptance run.

**Recommended wording:**

> *"AC-8's acceptance evidence is produced by the production initiative path,
> from a real input to execution, with no test code standing in for any
> production component. A stand-in trigger is supplementary evidence only, is
> labelled as such, and never makes AC-8 met."*

- **Affected components:** the harness; the sequencing of 4F.8 behind 4F.P.
- **Affected criteria:** AC-8; CF-11 claim 3.
- **Implementation must wait: yes**, for this decision and for 4F.P.

### A-4F8-5 — What identity-confidence configuration does the AC-8 run use? **BLOCKING**

- **Question.** Stage 3 reads identity confidence that the CI runner cannot
  honestly produce (F-4F8-4). What configuration may the acceptance stack
  carry?
- **The constraints:**
  - `SINGLE_SIGNAL_CONFIDENCE_CEILING` is unchanged.
  - 4F.4's writable range is `[0.0, 0.75]`
    (`api/identity_confidence_policy.py` l.38, l.77).
  - D-4F4-4: no production default, no seed.
  - Fabricating a sensor reading is forbidden (control 12).

| Option | Consequence |
|---|---|
| **(a) Disclosed test configuration through the production surface.** The harness writes `minimum_confidence_by_risk = {<tier>: 0.0}` through the production `PUT /v1/action/identity-confidence-policy`, fronted by `api-gateway`. It covers **only** the tier `action-engine` assigns to AC-8's action. A negative control proves that without it stage 3 denies at 1.0 | Stage 3's code and fail-closed default are untouched. The configuration is **visible and scoped**. It is not closure evidence for CF-9 condition 2 beyond D-4F4-1's citation |
| (b) A real identity signal | Impossible in CI without a fabricated reading |
| (c) Accept the stage-3 denial | AC-8 is **NOT MET** |

**Recommendation: (a).**

**Recommended wording:**

> *"The acceptance stack sets an identity-confidence threshold of 0.0 for
> exactly the risk tier of AC-8's action, through the production policy
> surface, as disclosed test configuration. Stage 3's evaluation and the absent-
> policy default of 1.0 are unchanged, and a negative control shows the gate
> denying without it."*

- **Affected components:** the harness only. **No production file changes.**
- **Affected criteria:** AC-8 *"auto-executes"*.
- **Implementation must wait: yes**, because it is a security-relevant
  configuration in acceptance evidence.

### A-4F8-6 — How is AC-7 measured? **BLOCKING**

- **Question.** §20.1 fixes what is forbidden. It does not fix three things:
  **where** the World Model result is observed, **how many** measurements
  are taken, and **what passes**.
- **The facts:**
  - `/v1/world` has no gateway prefix, and adding one would breach RS-5 and
    master scope §6.
  - `world-model-engine` answers `GET /v1/world/objects/{object_id}` on its
    own port (compose l.354, `8003`).
  - The companion's `observed_at` is the file's own modification time, from the
    OS.
  - Dispatch waits for a fixed 10 s tick.

| Sub-question | Options | Recommended |
|---|---|---|
| **Observation point** | (a) the harness reads `world-model-engine`'s own REST on the internal network; (b) a new `/v1/world` prefix (**rejected**: RS-5, master scope §6); (c) independent SQL on `world_model`'s tables | **(a)**, with (c) as a cross-check |
| **Start of the interval** | (a) the file's OS modification time (`observed_at`); (b) the harness's clock before the write | **(a)**, asserted to be not earlier than (b). Both come from the host's one real-time clock |
| **End of the interval** | The harness's clock at the first successful read of the object, polling at **≤ 100 ms**. Polling is **observation, not retry**: nothing is re-sent, re-written or re-run | As stated. The resolution is disclosed |
| **Sample count and pass rule** | (i) one measurement; (ii) **N ≥ 10 independent events**, written at times uncorrelated with the cron, each measured and all reported; (iii) a median or percentile | **(ii), passing only if every sample is ≤ 5.0 s.** (iii) weakens the criterion; (i) lets one lucky sample conceal the answer |
| **Observation deadline** | Beyond 5 s, so the true figure is always reported | **30 s** per sample. A sample over 5 s **fails the test and prints the figure** |

**The expected outcome, stated plainly.** Worst-case dispatch latency is ~10 s
and the mean ~5 s (§20.1). Under (ii), **most runs are expected to fail** and
to report figures above 5 s. **That is the blocking Gate Review finding §20.1
anticipates**, and it is an acceptable output of 4F.8. **It must not be
engineered around.** Resolving it would reopen D-4F-1, and **that is the
user's decision at the Gate Review, not 4F.8's.**

**Recommended wording:**

> *"AC-7's latency is measured over at least ten independent real filesystem
> events, from each event's OS time to the first observation of its World Model
> object through `world-model-engine`'s own read surface, across the unchanged
> outbox and dispatcher. Every figure is reported. The criterion is met only if
> every figure is at most five seconds, and otherwise the test fails and
> exposes the figures."*

- **Affected components:** the harness; the e2e job.
- **Affected criteria:** AC-7 *"within five seconds"*, *"reflected in the
  World Model"*.
- **Implementation must wait: yes.**

### A-4F8-7 — Where is AC-8's execution evidenced, and what does "both criteria in a browser" mean? **BLOCKING**

- **Question.** TDD 4F §18's 4F.8 row reads *"Both criteria in a browser"*, but
  no browser-reachable surface shows either the World Model reflection or a
  Level-2 execution (F-4F8-9).
- **What AC-8's own text requires:** it has **no** browser clause. AC-7's
  browser clause is the panel.

| Option | Consequence |
|---|---|
| **(a) No new surface.** In the browser: the **Level-1** run's proposal appears in the Autonomy panel, requires approval, and executes nothing. The **Level-2** run produces **no** proposal. The level selector shows 2. AC-7's revocation shows as `failed` in the Cognitive State panel. Outside the browser: the **execution** is evidenced by independent SQL on `autonomy.decision_log` (`EXECUTE`) and `action.action` (`completed`), plus the capability's real effect; the World Model reflection per A-4F8-6. §18's phrase is **clarified additively** to *"each criterion's browser-visible clause in a browser; the rest by real-infrastructure evidence"* | No new route, subject or prefix. Consistent with TDD 4F §12, TDD 4F.6 §19 row 18, RS-4b and D-4F-6 |
| (b) A read-only `GET /v1/autonomy/decisions` | A browser-visible execution. **It contradicts TDD 4F §12** (*"`autonomy-engine` gains no new route"*) and TDD 4F.6 §19 row 18, and needs an amendment and a panel change |
| (c) A read-only action lookup under `/v1/action` | Needs a new `action-engine` route and a panel change. It is not demanded by any AC |
| (d) A public completion subject | **Forbidden** (§11.4; `PUBLIC_TOPICS`) |

**Recommendation: (a).**

**Recommended wording:**

> *"Each acceptance criterion's browser-visible clause is demonstrated in a real
> browser. Everything else is demonstrated by real-infrastructure evidence read
> independently of the code under test. No route, subject or prefix is added to
> make a fact browser-visible."*

- **Affected components:** Playwright specs; the harness; an additive
  clarification to TDD 4F §18 at ratification.
- **Affected criteria:** AC-7, AC-8.
- **Implementation must wait: yes.**

### A-4F8-8 — SAD 15 §4 item 1 for the 4F.8 PR **BLOCKING (process)**

- **Question.** The 4F.8 PR would touch several components:
  - `companion/`;
  - `services/perception-engine/`;
  - `infra/docker/`;
  - `tools/`, for test harnesses and stack-completeness tests;
  - `apps/web-client/tests/`;
  - `.github/workflows/pr-checks.yml`, for the e2e job.

  Is it granted RS-9's kind of exception?

| Option | Consequence |
|---|---|
| **(a) An exception scoped to exactly the surfaces 4F.8's ratified deliverables need**, recorded in the Slice Completion Record, with SAD 15 §4 items 2–5 mandatory | RS-9's precedent |
| (b) One PR per component | Contradicts TDD 4F §18 (*"not new milestones"*). The acceptance run spans components by nature |
| (c) No decision | Repeats the non-conformance the Phase 4B Gate Review recorded |

**Recommendation: (a)**, to be scoped after A-4F8-1 … A-4F8-7 fix the
surfaces.

- **Affected components:** the PR.
- **Affected criteria:** none directly.
- **Implementation must wait: yes.**

### A-4F8-9 — The unassigned 4F deliverables. **Blocks 4F's GO, not 4F.8's implementation**

- **Question.** The desktop/window-focus, clipboard and process/system-health
  sensors, the terminal and window-control actuators, and multi-modal fusion
  (L-11 and *"the meeting begins scenario"*) are named in master scope §5 and
  TDD 4F §2, §7.1 and §9. **No slice owns them** (F-4F8-10). What is their
  disposition?

| Option | Consequence |
|---|---|
| **(a) Deferred by explicit approval** at 4F closure, to a named later phase, with each recorded. **Not absorbed into 4F.8** | Protocol §0.3.6 and §2.1 are satisfied by an approval, not by silence |
| (b) New 4F slices before 4F closure | Real scope. The SLOC headroom is 2,567 before 4F.P and 4F.8 |
| (c) Absorbed into 4F.8 | **Rejected.** They are not acceptance dependencies, and absorption would be silent scope growth |

**Recommendation: (a).**

- **Affected components:** none in 4F.8.
- **Affected criteria:** none of AC-7/AC-8. It affects **4F's own scope and
  GO**.
- **Implementation must wait: no.** 4F closure must.

### A-4F8-10 — The acceptance-stack deployment. **Recommended default; not blocking**

| Sub-question | Recommended default | Alternative |
|---|---|---|
| How the companion runs | **(a) A `nova-companion` compose service** from its already-built, Trivy-scanned image, running as its image's non-root user and watching a **bind-mounted** host directory that the harness writes to and changes permissions on | (b) A harness-spawned binary on the runner, as the real-infrastructure tier already does |
| `perception-engine` and its worker in the e2e job | **Added** | — |
| `perception-engine`'s `primary_user_id` in compose | **Set to the same primary user every other engine defaults to** (ADR-025) | Leave it unset, and then AC-7 publishes nothing |
| `tools/tests` stack-completeness | Extended to require the new services and workers | — |

These are deployment wiring, not semantics. **Setting `primary_user_id` is
identity configuration**, so the user may elevate this item to blocking.

---

## 8. Component ownership

| Component | Owns | 4F.8's change (under the recommendations) |
|---|---|---|
| `nova-companion` | The raw OS signal; **revocation detection** (A-4F8-1) | D1. It still has no listening port, no NATS and no store (TDD 4F §7) |
| `perception-engine` | The sensor lifecycle and permission status; normalization; **known-project correlation** | D2, D3. It remains the only owner of `SensorState` |
| `world-model-engine` | World objects | **None** (TDD 4F §11.1). The harness reads it |
| `memory-engine` | `project_id` | **None.** It is read via its existing event |
| `digital-twin-engine` | Part 16 domains | **None** |
| `cognitive-state-engine` | Active Thoughts, Focus, Attention; the `sensor_state` copy; the trigger producer | **None from 4F.8.** 4F.P owns its promotion work |
| `autonomy-engine` | Level, policy, grants, the decision log, dispatch | **None from 4F.8.** A-4F8-3's extension is 4F.P's, recommended |
| `action-engine` | The action lifecycle, risk, approval, `IdentityConfidencePolicy` | **None** |
| `capability-engine` | The built-in capabilities | **None** |
| `api-gateway`, `ws-gateway` | The browser boundaries | **None** |
| `apps/web-client` | The panels | **Tests only** (D7) |
| `infra/docker`, `pr-checks.yml`, `tools/` | Deployment, CI and harnesses | D4, D5, D6 (A-4F8-8) |

---

## 9. Event subjects on the AC-7 and AC-8 paths

**4F.8 proposes no new subject.** The registry stays at **120** and
`PUBLIC_TOPICS` at **18**. If 4F.P, or the Gate Review's decision on 4F.6
F-1, changes either count, that is recorded by the change that makes it.

| Subject | Visibility | Producer → consumer | On which path |
|---|---|---|---|
| `perception.workspace.observed` | **Internal** (not in `PUBLIC_TOPICS`) | `perception-engine` → `world-model-engine` (wildcard) | AC-7 detection |
| `perception.sensor.health_changed` | **Public** (in `PUBLIC_TOPICS` since 4B; RS-3a's accepted consequence) | `perception-engine` → `cognitive-state-engine`, `ws-gateway` | AC-7 revocation, visible |
| `memory.long_term.created` | **Internal** | `memory-engine` → `digital-twin-engine`, and **`perception-engine` under A-4F8-2 (a)** | AC-7 *"known"* |
| `autonomy.decision.requested` | **Internal**, request/reply | `cognitive-state-engine` → `autonomy-engine` | AC-8 trigger |
| `action.execute` | **Internal**, request/reply | `autonomy-engine` → `action-engine` | AC-8 execution |
| `world_model.context.request` | **Internal**, request/reply | `action-engine` → `world-model-engine` | AC-8 stage 3 |
| `capability.resolve.request`, `capability.invoke.request` | **Internal**, request/reply | `action-engine` → `capability-engine` | AC-8 stages 5–6 |
| `action.approval.requested`, `.decided` | **Public** | `action-engine` | **Not** on AC-8's LOW path. Present only if an action is `critical` |
| 4F.P's input subjects | **4F.P's decision** | — | AC-8's trigger input |

---

## 10. API surface

**No gateway prefix and no browser-reachable route is added.** Subject to
A-4F8-1 (a1), exactly **one internal `perception-engine` route** is added. It
is reachable only on the internal network, is never forwarded by
`api-gateway`, and carries the companion's revocation report.

**Routes the acceptance harness uses, all existing:**

| Route | Through | Purpose |
|---|---|---|
| `PUT /v1/autonomy/level` | `api-gateway` | Level 1, then Level 2 |
| `POST /v1/autonomy/policies` | `api-gateway` | The `AUTO_EXECUTE` policy (L-17: not through the panel) |
| `PUT /v1/autonomy/permissions` | `api-gateway` | The category's grant |
| `PUT /v1/action/identity-confidence-policy` | `api-gateway` | A-4F8-5 |
| `GET /v1/autonomy/suggestions` | `api-gateway` (the panel) | The Level-1 proposal |
| `GET /v1/cognitive-state/sensors` | `api-gateway` (the panel) | The revocation, visible |
| `GET /v1/world/objects/{object_id}` | **`world-model-engine` directly, on the internal network. Not the browser** | AC-7's measurement (A-4F8-6) |

---

## 11. What 4F.8 requires from 4F.P — interface requirements only

**None of these is decided here.** Each is a property 4F.8's AC-8 evidence
needs 4F.P's ratified result to have. **4F.P's TDD decides how, or whether.**
If it cannot provide one of them, that is reported back as a blocking finding
for this document.

1. **A production-reachable promotion.** A deployed component promotes an Active
   Thought carrying a complete `ProposedAction` to `IMMEDIATE`, in response to a
   real input, with no test harness in the chain.
2. **A reproducible input in CI.** The input can be produced in the acceptance
   stack without fabrication. For example, a real filesystem observation of a
   known project, **if** 4F.P's ingestion mapping maps it. That is 4F.P's
   choice.
3. **An executable proposal.** The authored `ProposedAction` satisfies A-4F8-3's
   four-part low-risk constraint.
4. **Two runs of the same category.** The same category can be triggered at
   Level 1 and at Level 2 within one acceptance run. **4F.P's Layer 2
   deduplication and CAS semantics must not make the second trigger
   impossible**, and if they suppress it, the acceptance design must say so.
5. **No coupling to autonomy data.** RS-4b holds: `cognitive-state-engine` does
   not read decision data.

**This TDD is re-verified after 4F.P's TDD is ratified**, and amended
additively where 4F.P's decisions fix a detail left open here (§22, step 3).

---

## 12. Persistence changes

- **Proposed by 4F.8: none, except under A-4F8-2 (a1).** That option adds one
  **additive** `perception` table for learned project identities: current state
  only, no history and no audit.
- **No existing table is altered.**
- **Altered by nothing in 4F.8:** `cognitive_state.*`, `autonomy.*` and
  `action.*`.
- **Configured, not written, by the harness:** the identity-confidence row
  (A-4F8-5), through the production route.

---

## 13. Data flow

### 13.1 AC-7 — detection and latency

```mermaid
sequenceDiagram
    participant H as acceptance harness
    participant FS as host filesystem (bind-mounted)
    participant C as nova-companion (container)
    participant PE as perception-engine
    participant OB as perception outbox + worker (10 s cron)
    participant N as Event Bus
    participant WM as world-model-engine

    H->>FS: write a file under a known project root
    FS-->>C: inotify event (real OS time = mtime)
    C->>PE: POST /v1/perception/workspace-observations (internal)
    PE->>PE: sensor running? primary_user_id? correlate root → project_id (A-4F8-2)
    PE->>OB: enqueue perception.workspace.observed
    OB->>N: publish at the next 10 s tick (unchanged)
    N-->>WM: wildcard subscription
    WM->>WM: WorldObject created / advanced
    loop poll ≤ 100 ms, deadline 30 s
        H->>WM: GET /v1/world/objects/{object_id}
    end
    H->>H: elapsed = first seen − mtime; report; fail if > 5.0 s (A-4F8-6)
```

### 13.2 AC-7 — revocation, visible

```mermaid
sequenceDiagram
    participant H as acceptance harness
    participant FS as host filesystem
    participant C as nova-companion
    participant PE as perception-engine
    participant OB as outbox + worker
    participant CS as cognitive-state-engine
    participant UI as Cognitive State panel (browser)

    H->>FS: withdraw the companion's OS permission on the watched root
    C->>C: detects loss of access (A-4F8-1)
    C->>PE: internal revocation report
    PE->>PE: FilesystemSensor running → failed (report_error)
    PE->>OB: enqueue perception.sensor.health_changed{status: failed}
    OB-->>CS: dispatched; sensor_state upserted
    UI->>CS: Refresh → GET /v1/cognitive-state/sensors (via api-gateway)
    CS-->>UI: companion-filesystem: failed, last reported …
    H->>FS: a further write, by a writer that still has permission
    H->>H: assert no new observation published, no World Model change (E-6)
```

### 13.3 AC-8 — trigger → decision → execution

```mermaid
sequenceDiagram
    participant IN as real input (4F.P's ingestion)
    participant CS as cognitive-state-engine (4F.P's promotion)
    participant AE as autonomy-engine
    participant AX as action-engine
    participant WM as world-model-engine
    participant CE as capability-engine

    IN->>CS: existing subject
    CS->>CS: thought promoted to IMMEDIATE with a complete ProposedAction
    CS->>AE: autonomy.decision.requested (request/reply)
    AE->>AE: level, policies, grants (server-side); Policy → Permission → Trust (UNAVAILABLE)
    alt Level 1 (or requires_approval)
        AE->>AE: PROPOSE + suggestion (visible in the Autonomy panel)
    else Level 2, AUTO_EXECUTE, LOW, all seven preconditions
        AE->>AX: action.execute (15 s, one request, no retry)
        AX->>AX: validate (operation), classify risk (≤ low)
        AX->>WM: world_model.context.request (identity; none in CI → 0.0)
        AX->>AX: stage 3 vs the configured tier threshold (A-4F8-5)
        AX->>CE: capability.resolve / capability.invoke
        CE-->>AX: success
        AX-->>AE: ActionResultPayload{status: completed}
        AE->>AE: EXECUTE logged
    end
    AE-->>CS: AutonomyDecisionReplyPayload
```

---

## 14. The Autonomy Level 2 lifecycle — what 4F.8 must evidence per state

TDD 4F §21 item 1 requires the Gate Review to cover **the five states
individually**.

| # | State | Built by | Production evidence 4F.8 must produce |
|---|---|---|---|
| 1 | **Defined** | 4D | `DEFINED_LEVELS` contains 2 (cited; unchanged) |
| 2 | **Selectable** | 4F.5 | `PUT /v1/autonomy/level {"level": 2}` returns 200 **through `api-gateway`** in the acceptance stack, and the level persists |
| 3 | **Policy-permitted** | 4F.5 | An `AUTO_EXECUTE` policy, LOW-bounded, created through the production route. The Level-2 decision's `policy_checks` name it |
| 4 | **Triggered** | 4F.6 + **4F.P** | `decide()` runs because **4F.P's production promotion** sent `autonomy.decision.requested`. No test code sits in that chain (A-4F8-4) |
| 5 | **Executing** | 4F.5 | Exactly one `action.execute`, and `action-engine`'s **terminal status `completed`**, read by independent SQL (F-4F8-2), with the capability's real effect |

**Separability.** Each state is also shown failing on its own:

| Removed | Result |
|---|---|
| Level 1 instead of 2 | A suggestion |
| No policy | A suggestion |
| Moderate risk | A suggestion |
| Not triggered | No decision at all |
| No `operation` | A suggestion under A-4F8-3 (a) |

---

## 15. The trigger → decision → execution flow, step by step

| # | Step | Owner | Gate or rule | Evidence | On failure |
|---|---|---|---|---|---|
| 1 | Real input arrives | 4F.P's source | 4F.P's ingestion mapping | 4F.P's own records | No thought |
| 2 | Thought promoted to `IMMEDIATE` with a complete `ProposedAction` | `cognitive-state-engine` | 4F.P's policy and CAS; A-4F6-2a | Independent SQL on `active_thought` | No trigger (A-4F6-2a: *"missing never triggers"*) |
| 3 | `autonomy.decision.requested` sent | `cognitive-state-engine` | One request, 20 s reply wait, no retry (4F.6) | The consumer's `subject_id = uuid5(event_id)` | `unconfirmed` or `unavailable`; nothing executes (§19 row 12) |
| 4 | `DecisionRequest` built server-side | `autonomy-engine` | `primary_user_id`; `extra="forbid"` | 4F.6 row 7 | Rejected or degraded reply; `decide()` not invoked |
| 5 | Policy → Permission | `autonomy-engine` | Deny-only; `DENY` wins; `AUTO_EXECUTE` ≤ LOW | `policy_checks` | `DENY` |
| 6 | Trust | `autonomy-engine` | `UNAVAILABLE`, non-blocking, never a pass | `TrustScore.score is None` | — |
| 7 | Single dispatch point | `autonomy-engine` | `requires_approval`; the seven §22.4 preconditions | Decision log | `PROPOSE` |
| 8 | `action.execute` | `autonomy-engine` → `action-engine` | 15 s, one request, no retry | One row per `action_id` | `TIMEOUT`, or `PROPOSE` if unavailable |
| 9 | Stage 2 | `action-engine` | `operation` present (A-4F8-3) | `action_execution_history` | `failed`. **4F.8 must not reach this** |
| 10 | Risk | `action-engine` | `classify_risk` ≤ LOW (A-4F8-3) | `action.risk` | Approval loop if `critical` |
| 11 | Stage 3 | `action-engine` | ADR-032, threshold per tier (A-4F8-5) | `action.confidence`; history | `denied` |
| 12 | Stages 5–6 | `action-engine` → `capability-engine` | Built-in capability, healthy, sandboxed | History; the effect | `failed` |
| 13 | Reply recorded | `autonomy-engine` | `EXECUTE`, reason carries the status (F-4F8-2) | Decision log **and** `action.action.status = completed` | — |

---

## 16. Verification requirements — defined before implementation

Each item names the proof. The E-numbers are 4F.8's own. **Every E-item is
subject to its §7 decision**, and is amended if a different option is
ratified.

| # | Claim | Proof required |
|---|---|---|
| **E-1** | A real companion process watches a real, explicitly configured project directory, and a real write becomes a `WorldObject` | The acceptance stack (D4). The harness writes a file. `world-model-engine` holds the object with `object_id == object_id_for_path(path)`. **Provenance:** the World Model's recorded transition carries the `correlation_id` of the perception outbox row that produced it. `world-model-engine` records `envelope.correlation_id` (`events/handlers.py` l.111), and the outbox row persists it (`nova_service_kit/outbox.py` l.102). Both sides are read by independent SQL, which rules out an injected message |
| **E-2** | *"Known"*: the observation carries the known project's `project_id`; outside every known root it carries `None` | Independent SQL on the perception outbox payload, one of each (A-4F8-2) |
| **E-3** | *"Within five seconds"*, measured honestly | A-4F8-6: N ≥ 10 samples, every figure reported, a pass only if all are ≤ 5.0 s. **The test prints the figures either way** |
| **E-4** | *"Without user action"* | Structural: between the write and the observation, the harness makes no request into the chain. It only writes and reads |
| **E-5** | Revocation reaches `failed`, visibly | After a genuine permission withdrawal: `perception-engine`'s filesystem sensor is `failed`; `cognitive_state.sensor_state` holds `failed`; the panel shows `failed` after Refresh (P-AC7-1) |
| **E-6** | *"Stops the perception stream"* | After `failed` is visible: a further write **by a writer that still has OS permission**, **asserted to have succeeded at the OS level**, produces **no** outbox row and **no** World Model change within **≥ 2 dispatch cycles (25 s)**. The revocation happens only after `cognitive-state-engine` is ready and subscribed (K-1) |
| **E-7** | The modality is disclosed | The record states that IDE/window-focus sensing was **not** the acceptance modality (D-4F-8; TDD 4F §21 item 2) |
| **E-8** | Blocked at Level 1 | Level 1: the production trigger yields `PROPOSE`; the suggestion is visible in the Autonomy panel; **no `action.execute`**; no `action.action` row for its `subject_id` |
| **E-9** | Auto-executes at Level 2 | Level 2, same category, action type and authored risk: `EXECUTE`; **exactly one** `action.action` row; **`status = completed`**; the capability's real effect observed. **`EXECUTE` alone is not accepted as evidence** (F-4F8-2) |
| **E-10** | No code path differs | The two decision-log rows carry identical `policy_checks`, and the Level-1 row differs only in `outcome` and `autonomy_level`. X-8's unit-tier call-sequence control stays green |
| **E-11** | Low risk, twice | The authored risk is `low`, and `action.action.risk` is at or below `low` (A-4F8-3) |
| **E-12** | Purely by policy | Between the two runs, **only the level changes**. Policies, grants and the identity-confidence row are identical, read back by independent SQL before each run |
| **E-13** | Production trigger | No test module imports or calls `promote_thought` or `decide()`, or publishes `autonomy.decision.requested`, on the authoritative path. That is structural (AST). The decision's `subject_id` is `uuid5(ns, event_id)` of an envelope produced by `cognitive-state-engine` (A-4F8-4) |
| **E-14** | CF-11 claim 3 | E-8, E-9 and E-13 together, recorded as claim 3's evidence. **Claim 4 is 4F closure's** |
| **E-15** | Boundaries unchanged | Registry 120, `PUBLIC_TOPICS` 18 byte-identical, nine prefixes, no `/v1/perception`, no `/v1/world`, `perception.workspace.observed` not subscribable by a browser (TDD 4F §16.1 control 15, re-run) |
| **E-16** | Earlier slices intact | 4F.1–4F.7's controls unchanged and green; stage 3 byte-identical (TDD 4F §16.1 control 13) |
| **E-17** | Fail-closed at stage 3 | Without A-4F8-5's row, the same Level-2 run is `denied` at stage 3 at threshold 1.0 |

### 16.1 Mapping AC-7 and AC-8 to deliverables

| Criterion clause | Deliverable | Evidence | Depends on |
|---|---|---|---|
| AC-7 *"a known project becoming active"* | D3, D4, D5 | E-1, E-2 | A-4F8-2, A-4F8-10 |
| AC-7 *"detected by a `nova-companion` sensor"* | D4 | E-1 | A-4F8-10 |
| AC-7 *"without user action"* | D5 | E-4 | — |
| AC-7 *"reflected in the World Model"* | D5 | E-1 | A-4F8-6 |
| AC-7 *"within five seconds"* | D5 | E-3 | A-4F8-6 |
| AC-7 *"revoking that sensor's OS-level permission"* | D1 | E-5 | A-4F8-1 |
| AC-7 *"stops the perception stream"* | D2 | E-6 | A-4F8-1 |
| AC-7 *"visibly … in the panel"* | 4F.7 (built) + D7 | E-5, P-AC7-1 | A-4F8-1 |
| AC-8 *"the same action category"* | D6 | E-10, E-12 | 4F.P; A-4F8-4 |
| AC-8 *"blocked at Level 1"* | D6, D7 | E-8, P-AC8-1 | 4F.P; A-4F8-4 |
| AC-8 *"auto-executes at Level 2"* | D6 | E-9, E-13, E-14, E-17 | 4F.P; A-4F8-3, A-4F8-4, A-4F8-5 |
| AC-8 *"for a low-risk case"* | D6 | E-11 | A-4F8-3 |
| AC-8 *"purely by policy"* | D6 | E-12 | — |
| AC-8 *"no code path differs"* | D6 | E-10 | — |

---

## 17. Negative controls

Protocol §9.2 applies. Each mutation must fail at least one named test. The
harness-level controls (N-1 … N-4) are **structural checks over the harness's
own source**, because a mutation to a test cannot be caught by that test.

| # | Mutation | Must fail |
|---|---|---|
| N-1 | Align a sample's write to the dispatcher's tick (read or reference the cron, or sleep to a boundary) | A structural scan of the harness (control 14) |
| N-2 | Retry, re-run or discard a failed sample | Structural scan; E-3's all-samples report |
| N-3 | Fabricate `observed_at`, or use a fake clock (`freezegun`, `time_machine`, patched `datetime`) | Control 12 scan |
| N-4 | Publish `perception.workspace.observed` or `autonomy.decision.requested` from test code | E-1's `correlation_id` provenance; E-13's AST check |
| N-5 | The companion detects revocation but `perception-engine` does not transition | E-5 |
| N-6 | Keep publishing after `failed` | E-6 |
| N-7 | Revoke the harness's writer too, so the stream "stops" because nothing can be written | E-6's asserted-successful write |
| N-8 | Infer `failed` from silence | A-4F8-1's structural control: `failed` is reached only through the report path |
| N-9 | Remove the `AUTO_EXECUTE` policy | E-9 → a suggestion |
| N-10 | Remove A-4F8-5's identity-confidence row | E-17 (denied) |
| N-11 | Author `moderate` risk | E-9 → a suggestion (TDD 4F §16.1 control 5) |
| N-12 | Accept an `EXECUTE` whose reply is `failed` as success | E-9's `completed` assertion |
| N-13 | A correlation miss attaches a guessed `project_id` | E-2's `None` case |
| N-14 | Add any subject to `PUBLIC_TOPICS`, or add a prefix | E-15 |
| N-15 | Level 2 by flag alone (`permits_execution` true, no wired path) | TDD 4F §16.1 control 3, unchanged |

**Flakiness.** Every real-infrastructure and browser test in 4F.8 involves
timing. Each is run **≥ 10 times** and reported. **AC-7's latency test is
exempt from "must be green ten times"**: its outcome is the measurement, and a
red result with figures is a valid, reported outcome (§20.1).

---

## 18. Real-infrastructure validation

| Tier | What | Real dependencies |
|---|---|---|
| **Cargo** (`companion/`) | D1: revocation detected against a **real** temporary directory whose permissions are **really** changed. Establishes F-4F8-7's actual inotify behaviour | The real filesystem and real `notify` |
| **`real_infra`** (`perception-engine`) | D2: a revocation report moves the real sensor to `failed`; one outbox row; a later observation dropped. D3: known-project correlation over a real `memory.long_term.created` from a bound producer (control 7's precedent) | Real Postgres, real NATS, the real dispatcher |
| **`real_infra`** (`perception-engine`, companion) | The existing real-binary crossing (4F.3) extended: a real companion process reports a real revocation | The real Rust binary |
| **The acceptance stack** (the `pr-checks` e2e job) | E-1 … E-17 against the deployed engines | The full compose stack |

- **Docker is unavailable in this environment.** Every result above is **CI's**
  and must be labelled as such (TDD 4F §16.3; protocol §10).
- **Both carrying workflows are non-blocking** (F-4F8-12). The record and the
  Gate Review cite their conclusions **at the exact SHA**.

---

## 19. Playwright coverage

| # | Spec | What it proves |
|---|---|---|
| **P-AC7-1** | The Cognitive State panel shows `companion-filesystem` as `running`, then, after the harness's genuine revocation and a Refresh, `failed` with *"last reported …"*. The content equals `GET /v1/cognitive-state/sensors` through the gateway | AC-7 clause 2, visibly |
| **P-AC8-1** | The Autonomy panel shows the **Level-1** run's proposal for AC-8's category as requiring approval. After the level is set to 2 and the **second** trigger fires, **no new proposal** appears | AC-8's browser-visible clause (A-4F8-7 (a)) |
| Existing | `golden-path`, `observability-panels`, `approval-lifecycle`, `capability-lifecycle`, `autonomy-suggestion` (its RS-8 stand-in unchanged), `digital-twin-reconstruction`, `cognitive-state-panel` | Unchanged and green |

**AC-7's latency is not measured in the browser** (A-4F8-6).

---

## 20. Final Phase 4 Gate Review evidence

### 20.1 What 4F.8 hands to 4F closure (L-1)

TDD 4F §21 requires six items, plus protocol §3.2:

1. **The five Level-2 states individually** (§14), each with its evidence.
2. **AC-7's latency as measured numbers**: every sample, with an explicit
   statement that IDE/window-focus was **not** the modality.
3. **CF-9, CF-10 and CF-11 dispositioned separately:**
   - CF-9 against §5.3's five points;
   - CF-11 against §6.1 and 4F.6 §15.1's four claims;
   - CF-10 unchanged and OPEN.
4. **The SLOC gate:** the measured 4F-scope figure, and whether 50,000 was
   crossed.
5. **`PUBLIC_TOPICS` byte-identical.** The wording *"exactly one Event Bus
   subject was added"* predates D-4F-9. Two were added across 4F (TDD 4F
   §24.13, item 3), and **L-9 settles that wording**.
6. **The companion reaches no browser and no NATS.**

**Plus:**

- CI conclusions at the exact SHA for all three workflows, including the two
  non-blocking ones;
- the negative-control and flakiness tables;
- the unverified-items list;
- **if AC-7 fails, the figures, framed as the blocking finding §20.1 requires.**

### 20.2 What the Phase 4 Gate Review then needs

It comes after 4F closure, and before the single `phase-4 → main` PR (master
scope §16).

- **AC-1 … AC-8, each with a status and evidence**:
  - AC-3's and AC-4's deferred clauses stay **Deferred by approval**, never met;
  - AC-7 and AC-8 carry 4F.8's evidence, or its failure.
- **Every carry-forward CF-1 … CF-11 dispositioned.** CF-10 is expected to be
  carried beyond Phase 4.
- **Each milestone's own gate state**, and its open conditions:
  - 4A: no Gate Review and no health record;
  - 4B: C-1, C-2, C-6, C-7;
  - 4C: C-3;
  - 4E: three OPEN findings.
- **D-1 … D-8 and R-1 … R-6** re-checked.
- **The `README.md` Phase 4 status line** that 4C, 4D and 4E each carried
  forward (TDD 4F §21).
- **A-4F8-9's approval**, or the slices it demands.
- **The verdict: GO, CONDITIONAL-GO or NO-GO.** An unmet AC-7 is a NO-GO
  unless the user approves its deferral (protocol §3.2).

---

## 21. Closure obligations

### 21.1 For the 4F.8 slice

- **A Slice Completion Record, not a Gate Review** (protocol §0.1). It
  carries:
  - categories 1, 2, 8, 9, 10, 11, 13 and 14 in full;
  - categories 3–7 and 12 as the ledger;
  - the A-4F8-8 exception;
  - every figure.
- **CI at the exact implementation SHA.** Zero skipped or cancelled, or each
  one explained.
- **Documentation:** the READMEs of every changed engine and of the companion,
  plus dated notes in docs 09, 10, 11 and 14 where the ratified options touch
  them.
- **No closure of CF-9, CF-10 or CF-11** in the slice record.

### 21.2 For 4F closure, after 4F.8

- **L-1 … L-22 settled**: done, or deferred by recorded approval.
- **The 4F Gate Review** and **`docs/project-health/phase-4f.md`** (23 fields)
  written.
- **The master health row, the roadmap row, the master scope's 4F closure
  note, `README.md`**, and the §2 SLOC methodology entry.
- **CF-9's closure checked** against §5.3. **CF-11 claim 4 recorded.**
- **A-4F8-9 settled.**
- **A normal two-parent merge**, `phase-4f` preserved, and `main` untouched.

### 21.3 Made by this preparation, additively

- **This document.**
- **`00-master-scope.md`:**
  - a dated slice-status note under §5's 4F entry;
  - a new §17 row for this TDD;
  - a dated note on §17's 4F.7 row recording its merge (F-4F8-11).

  No original wording is edited.

---

## 22. Implementation and closure sequence

**Nothing here starts without the user's explicit GO.**

1. **Ratify A-4F8-1 … A-4F8-8**, and confirm or change A-4F8-10. A-4F8-1
   satisfies RS-3b's precondition.
2. **4F.P: its TDD is written and ratified**, including A-4F8-3's extension if
   ratified as recommended. It is then implemented and merged (RS-1c).
3. **Re-verify this TDD against merged `phase-4`**, and amend it additively
   where 4F.P fixed a detail (§11).
4. **Cut the 4F.8 implementation branch** from the then-current `phase-4`
   head (master scope §16, rules 4 and 5). **Not created by this document.**
5. **D1, D2 then D3**, each with its Cargo or `real_infra` tier.
6. **D4**: the acceptance stack.
7. **D5**: the AC-7 harness, and its structural controls (D8).
8. **D6**: the AC-8 harness.
9. **D7**: the Playwright specs.
10. **Negative controls, flakiness runs, and the full protocol gate set.**
11. **The Slice Completion Record.**
12. **A PR only when asked.**
13. **4F closure (L-1)**, then **the Phase 4 Gate Review**, then **the single
    `phase-4 → main` PR** after GO.

---

## 23. SLOC budget

**Base: 47,433** (4F scope, at `9d2d636`). **Headroom to 50,000: 2,567.**

| Component | Estimate (not measured) |
|---|---|
| D1, companion revocation detection (Rust) | 60 – 150 |
| D2, `FilesystemSensor`'s `failed` path, one internal route, the call site | 60 – 120 |
| D3, known-project correlation (configuration, subscription, handler, optional table) | 60 – 180 |
| D4 – D8 (compose, harnesses, tests) | **0**. Outside every counted scope |
| **4F.8 total** | **180 – 450** |
| 4F.P, including A-4F8-3's extension if assigned there | **Unknown; 4F.P's TDD estimates it** |

**If 4F crosses 50,000, TDD 4F §17's hard gate applies unchanged.**

---

## 24. Risks

| Risk | Mitigation |
|---|---|
| **AC-7's latency fails against the 10 s cron.** This is expected (A-4F8-6) | Report the figures. Do not engineer around them. The decision on D-4F-1 belongs to the Gate Review |
| 4F.P cannot produce an input that is reproducible in CI | §11 item 2 makes it an explicit requirement. If unmet, it is a blocking finding back to this TDD |
| The first composition of the real `autonomy-engine` and `action-engine` surfaces defects beyond F-4F8-1 | The acceptance stack is where they surface. Each is reported, not absorbed (4F.5's §12 precedent) |
| Revocation behaves differently than F-4F8-7 expects | D1's real-filesystem test establishes it first |
| The acceptance workflows are non-blocking | §18: the conclusions are cited explicitly |
| The stage-3 configuration is misread as a production default | A-4F8-5: scoped to one tier, test configuration only, negative-controlled |
| The SLOC gate | §23 |

---

## 25. SAD 15 §9.0 — the 33 required contents

| # | Item | Where |
|---|---|---|
| 1 | Overall architecture | §1, §8, §13 |
| 2 | Core responsibilities | §1.1 |
| 3 | What does not belong here | §2, §11 |
| 4 | Internal execution flow | §13, §15 |
| 5 | Complete data flow | §13 |
| 6 | Domain model | Existing types; §7 (A-4F8-2, A-4F8-3) |
| 7 | State transitions | §4.6, §14; `running → failed` (A-4F8-1) |
| 8 | APIs | §10 |
| 9 | Event Bus RPCs | §9. **None added** |
| 10 | Published events | §9. **None new** |
| 11 | Consumed events | §9. One new consumer under A-4F8-2 (a) |
| 12 | Database schema | §12 |
| 13 | Repository layer | §12 (A-4F8-2 (a1) only) |
| 14 | Dependency boundaries | §8 |
| 15 | ADR compliance | ADR-004 (§4.7, A-4F8-2); ADR-025 (A-4F8-10); ADR-032 (A-4F8-5); ADR-033 (§18) |
| 16 | Bible compliance | Part 14 l.101–107 (§14); Part 11 l.569 (L-14, §6); Part 12 (§15) |
| 17 | Human Interaction Principles | No interaction behaviour is added. The panels show only real state |
| 18 | Personality Specification | **N/A** |
| 19 | Failure handling | §15; §13.2 |
| 20 | Recovery mechanisms | A-4F8-1 (a2): **none automatic**, disclosed |
| 21 | Observability | Existing conventions. `observability.py` packaging stays OPEN (§6) |
| 22 | Logging strategy | Existing loggers at each new decision point |
| 23 | Metrics | **None added** |
| 24 | Performance goals | AC-7's 5 s is the only ratified target (A-4F8-6) |
| 25 | Security considerations | A-4F8-1, A-4F8-2, A-4F8-5; §10 |
| 26 | Scalability | Single user (ADR-025) |
| 27 | Testing strategy | §16 – §19 |
| 28 | Future extension points | A-4F8-9; automatic recovery (A-4F8-1 (a2)) |
| 29 | Known limitations | F-4F8-2, F-4F8-6, K-1, (a2) |
| 30 | Technical debt | F-4F8-2; L-18 |
| 31 | Architectural risks | §24 |
| 32 | Tradeoffs | §7 |
| 33 | Explicit implementation order | §22 |

---

## 26. Consistency audit — this TDD against the master scope and every ratified decision

Performed against `9d2d636` **before commit**. A recommendation that would
**amend** a ratified decision is disclosed as an amendment, never presented as
consistent.

| Checked against | Result |
|---|---|
| **Master scope** §1.1 (AC-7, AC-8), §5 (4F), §6, §13, §15, §16 | AC-7 and AC-8 are not reworded. The milestone set stays 4A–4F. No panel is added (§6; `world-model/` stays Phase 5). No non-goal is touched. The branch rules are respected: no implementation branch; this document is on a documentation branch |
| **D-1 … D-8** | D-6: no prefix added and forwarding stays 1:1. D-3: no new authentication path. Consistent |
| **D-4D-1, D-4D-2** | D-4D-1: no subject without a need, and none added. D-4D-2: CF-9 stays open and ownership is unchanged. Consistent |
| **D-4F-1** | Outbox unchanged. AC-7 is measured honestly, and a failure is reported, not engineered around. Consistent |
| **D-4F-2, TDD 4F §5.3** | CF-9 is not closed. The write surface is used, not changed. Consistent |
| **D-4F-3, TDD 4F §6.2** | `cognitive-state-engine`'s prohibitions are untouched by 4F.8. Consistent |
| **D-4F-4, RS-5** | No `/v1/perception`, no `/v1/world`, no new prefix. Consistent |
| **D-4F-5, TDD 4F §8.1** | A-4F8-1 (a1) adds an internal route on the existing internal surface, the §8.1 precedent. **4F.2's route is unchanged.** Consistent |
| **D-4F-6** | No cognitive-state subject. Consistent |
| **D-4F-7** | No CI policy change. The companion image is already in the matrix. Consistent |
| **D-4F-8** | The filesystem is the modality; E-7 states it. Consistent |
| **D-4F-9, §11.5** | The trigger subject is used as built. Consistent |
| **§20.1, §20.2** | A-4F8-6 adds specifics §20.1 left open, and forbids everything §20.1 forbids. §20.2 is unchanged. Consistent |
| **TDD 4F §4.1's *"known"* row** | A-4F8-2 (a) satisfies *"read via events"*. Option (b) would **amend** it, and is not recommended |
| **TDD 4F §11.1** (world-model zero changes) | Kept. F-4F8-6 is disclosed instead |
| **TDD 4F §12** (no autonomy route) and **TDD 4F.6 §19 row 18** | Kept by A-4F8-7 (a). Options (b) and (c) would **amend** them, and are not recommended |
| **TDD 4F §18** (*"Both criteria in a browser"*) | **A-4F8-7 (a) requires an additive clarification** of this phrase at ratification. **Disclosed as an amendment** |
| **D-4F3-1 … D-4F3-4** | D-4F3-1: `FilesystemSensor` still performs no detection; the companion detects. D-4F3-2: the path stays inside `perception-engine`'s boundary. D-4F3-3: no consent subsystem; the watch root and bindings are operator-declared. D-4F3-4: the hardening guard is unchanged. Consistent |
| **TDD 4F.3 §7** (*"no new route"*) | That was 4F.3's own boundary. A-4F8-1 (a1) **adds one internal route in a later slice**. Disclosed |
| **D-4F4-1 … D-4F4-4** | D-4F4-4: **no production default and no seed**. A-4F8-5 is test configuration through the production surface, scoped and negative-controlled. **This reading requires ratification**, which is why A-4F8-5 is blocking |
| **D-4F5-1 … D-4F5-4, §22.7, §22.8** | Unchanged by 4F.8. **A-4F8-3 (a) amends 4F.5's payload builder** to carry authored fields, keeping D-4F5-2's *"absence yields a suggestion, never a guess"*. **Disclosed as an amendment**, recommended to 4F.P's TDD |
| **A-4F6-1 … A-4F6-7, TDD 4F.6 §19** | **A-4F8-3 (a) amends A-4F6-2a's field set and the trigger payload, additively.** Disclosed. Nothing else is touched: no TTL, no Layer 2 deduplication, no retry, no new outcome, no audit table |
| **RS-1 … RS-11** | RS-1b/RS-4b: nothing writes through `/v1/cognitive-state` and no decision data is read. RS-1c: 4F.P is first, and **nothing of 4F.P is absorbed** (§11). RS-3a: the revocation reuses the existing subject. **RS-3b: A-4F8-1 is its ratification candidate.** RS-6a: no triggered state. RS-7: no CAS here. RS-8: stand-ins are supplementary only (A-4F8-4). RS-9: A-4F8-8 follows it |
| **A-4F7-1, A-4F7-2** | The `sensor_state` table and vocabulary are unchanged. `failed` is a `SensorState` value already accepted |
| **Protocol** §0.3.4, §0.3.6, §13.3 | Every correction is additive. No scope is narrowed: A-4F8-9 surfaces it. Every ambiguity is stopped and reported (§7) |

**No unreported conflict remains.** Four recommendations would **amend**
ratified text, and each is disclosed above:

- A-4F8-1 (a1), against TDD 4F.3 §7's scope;
- A-4F8-3 (a), against A-4F6-2a and 4F.5's builder;
- A-4F8-7 (a), against §18's phrase;
- A-4F8-5 (a), a reading of D-4F4-4.

**None takes effect without ratification.**

---

## 27. Status

**PREPARED 2026-09-27. NOT RATIFIED. NOT implementation-ready.**

- **Blocking:** A-4F8-1 … A-4F8-8, and **4F.P's merge** (RS-1c).
- **A-4F8-9** must be settled before 4F's GO.
- **A-4F8-10** has recommended defaults.
- **CF-9, CF-10 and CF-11 stay OPEN.**
- **4F.P is not started and is not absorbed.**
- **4F.8 is not started.** No implementation branch exists. **No production
  file, test, migration, Dockerfile, workflow, contract or package was
  modified** to prepare this document.
