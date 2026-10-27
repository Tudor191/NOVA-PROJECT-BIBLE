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

> **Re-verified 2026-10-11 against merged `phase-4` @ `1ccce7a`, additively
> (§28).** The status above is unchanged: **PREPARED. NOT RATIFIED. NOT
> implementation-ready.**
>
> - **4F.P now has a ratified TDD, and is implemented and merged** (RS-1c is
>   met). The bullet above saying *"4F.P has no TDD and no branch"* is
>   historical.
> - A-4F8-3 and A-4F8-5 are recorded as answered by 4F.P (§28.2). D4 and
>   A-4F8-10 were absorbed by A-4FP-12, with one residual (§28.3).
> - **Six candidates await the user:** A-4F8-1, -2, -4, -6, -7 and -8
>   (§28.11).
> - New findings F-4F8-13 … F-4F8-16 (§28.6). One of them, a shared-workspace
>   permission conflict on A-4F8-1 (a)'s demonstration, needs a decision
>   (§28.7).

> **RATIFIED 2026-10-11 (§29), additively.** The status lines above are
> preserved as written, and **§29 governs**.
>
> - **Ratified:** A-4F8-1, -2, -4, -6, -7 and -8, and §28.7 option (B).
>   A-4F8-3 and A-4F8-5 are answered by 4F.P, and A-4F8-10 is absorbed.
> - **Implementation waits only for the user's explicit GO** to cut the branch
>   (§22 step 4).
> - **One decision affects scope:** whether to reopen D-4F-1, so that AC-7 can
>   be met (§29.3).
> - **A-4F8-9** still blocks 4F's GO. **AC-7 and AC-8 are not met, and not
>   claimed.**

> **D-4F-1 reopened 2026-10-11 (§30), additively.** The user reopened D-4F-1
> **only for `perception-engine`'s outbox dispatch interval**, so that AC-7's
> existing 5.0 s budget can be met.
>
> - The approach is a one-second cron with `max_jobs = 1`. It is verified safe
>   under the supported single-replica deployment, and it is not yet
>   implemented.
> - **The user authorized cutting the implementation branch** from `phase-4` at
>   `1ccce7a`.
> - **AC-7 and AC-8 are not met, and not claimed.**

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

> **Amended 2026-10-11 (§30), additively.** The table is preserved as written.
> **Row 2 has one exception.** `perception-engine`'s outbox dispatch interval
> may be shortened, with a serial dispatcher (`max_jobs = 1`), so that AC-7's
> unchanged 5.0 s budget can be met.
>
> - Every other part of row 2 stands: the outbox, every other engine's cron, no
>   direct publish, and no push-triggered dispatch.
> - Rows 3 onwards are unchanged.

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

> **Re-verified 2026-10-11, additively.** The table above is the baseline at
> `9d2d636`, and is kept as written. **§28.1 is the baseline at `1ccce7a`.**
> `phase-4` is `1ccce7a`. The registry is still 120, `PUBLIC_TOPICS` still 18,
> and the prefixes still nine. The e2e stack now runs `perception-engine`, its
> worker and `nova-companion`, and `primary_user_id` is set. The 4F-scope SLOC
> is **47,817**, with headroom **2,183**.

---

## 4. Reconciliation — the fifteen subjects, against source

Each subject records what exists, what AC-7 or AC-8 needs from it, and what is
missing. The findings in §5 are referenced by number.

> **Re-verified 2026-10-11, additively.** §4.1–§4.15 describe `9d2d636`, and
> are kept as written. 4F.P changed what §4.2 ("auto-executes"), §4.4 (the
> producer), §4.10, §4.11 (the payload now carries `operation` and
> `parameters`) and §4.12 (4F.P's items, now built) record. **§28.4 and §28.5**
> state the merged facts. AC-7 and AC-8 remain **NOT MET** (§28.12).

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

> **Re-verified 2026-10-11, additively.** The findings above are kept as
> written, at `9d2d636`. **§28.5** re-checks F-4F8-1 (resolved for T1),
> F-4F8-2 (resolved; the `failed` mapping rests on F-4FP-1's two halves) and
> F-4F8-8 (partly resolved; AC-7 is still not demonstrable). **§28.6** adds
> F-4F8-13 … F-4F8-16.

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

> **Re-verified 2026-10-11, additively (§28).** Everything in this section is
> kept as written, and **nothing in it is decided by the re-verification.**
>
> - **Answered by 4F.P, and recorded as TDD 4F.P §30.9 directs:** A-4F8-3 and
>   A-4F8-5 (§28.2).
> - **Absorbed by A-4FP-12:** A-4F8-10 (§28.3).
> - **Awaiting the user:** A-4F8-1, -2, -4, -6, -7 and -8 (§28.11). A-4F8-1
>   comes with §28.7's shared-workspace choice, and A-4F8-8 is re-scoped in
>   §28.8.
> - **A-4F8-9** still blocks 4F's GO, not 4F.8's implementation.

> **RATIFIED 2026-10-11 (§29.1), additively.** The text above and the note
> above are preserved as written.
>
> - **Ratified:** A-4F8-1 (a) with (a1) and (a2); A-4F8-2 (a) with (a1) and
>   (a2); A-4F8-4 (a); A-4F8-6; A-4F8-7 (a); A-4F8-8 (a), restricted to
>   §28.8's surfaces; and §28.7 (B).
> - **Each candidate's *"Nothing … is decided"*, *"BLOCKING"* label and
>   unchosen options are now history.** **§29 governs.**

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

> **Re-verified 2026-10-11, additively. Still PROPOSED, and not ratified.**
> Under A-4FP-12, the watched directory is also `capability-engine`'s sandbox
> root. Both services run as uid 1000, so **a revocation of the watched root
> also revokes `capability-engine`** (F-4F8-13).
>
> - **§28.7 analyses this**, with a local demonstration, and offers options
>   (A) and (B) for decision alongside this candidate. (A) sequences the
>   revocation last; (B) gives the companion a distinct uid.
> - **Option (a)'s ownership is unaffected.** Its detection is supported:
>   `IN_ATTRIB` arrives on the root at a revocation, and `stat` then fails.
> - **Today's companion stops silently** after a revocation (F-4F8-15), which
>   is what (a) must replace with a report.

> **RATIFIED 2026-10-11 (§29.1): option (a), with (a1) and (a2).**
>
> - **The companion detects**, and reports over exactly one internal
>   `perception-engine` route.
> - **`perception-engine` owns `running → failed`.** There is no automatic
>   recovery.
> - **The acceptance stack uses §28.7 (B)**, verified at runtime with the real
>   binaries (§29.2).
> - **Detection and reporting are acceptance checks for D1** (§29.5), because
>   today's companion is silent (F-4F8-15).

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

> **RATIFIED 2026-10-11 (§29.1): option (a), with (a1) and (a2).**
>
> - Operator-declared folder bindings, activated by project IDs observed on
>   `memory.long_term.created`.
> - One additive `perception` table.
> - `world-model-engine` unchanged.

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

> **Re-verified 2026-10-11, additively. Answered by 4F.P (§28.2)**, and
> recorded as TDD 4F.P §30.9 directs. This is not a new decision.
>
> - Option (a) is built and merged: A-4FP-3 … A-4FP-6.
> - **AC-8's low-risk case is T1**: `filesystem`/`list`, authored `low` and
>   classified `negligible`. It meets all four parts of the constraint above.

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

> **RATIFIED 2026-10-11 (§29.1): option (a).** AC-8's evidence originates
> from the production trigger, in one 4F.8 slice. Option (c)'s split is not
> taken.

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

> **Re-verified 2026-10-11, additively. Answered by 4F.P's ratified
> A-4FP-11 (§28.2)**, and recorded as TDD 4F.P §30.9 directs.
>
> - The threshold of `0.0` covers **only `negligible`**, the tier
>   `action-engine` assigns to T1, through the production route.
> - Its negative control, a denial recorded as `propose` with zero capability
>   invocations, ran in CI at `2b0757d`.

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

> **RATIFIED 2026-10-11 (§29.1).**
>
> - **At least 10 independent samples**, each on a never-before-observed path,
>   every sample reported. **A pass only if every sample is ≤ 5.0 s.**
> - The observation point, start, end and deadline are as recommended above.
> - **§29.3** traces the chain. **With the unchanged 10-second cron, AC-7 is
>   expected to be NOT MET**, unless the user reopens D-4F-1.

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

> **RATIFIED 2026-10-11 (§29.1): option (a).** No new UI or route. The browser
> shows the browser-visible clauses, and SQL and internal REST show the rest.
> TDD 4F §18 is clarified additively, in this change.

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

> **Re-verified 2026-10-11, additively. Still PROPOSED, and not ratified.**
> It is re-scoped in §28.8. D4's deployment wiring left with A-4FP-12.
>
> - **Governed:** `companion/`, `services/perception-engine/` and
>   `infra/docker/`.
> - **Recorded, not governed** (A-4FP-13's precedent): `tools/`,
>   `pr-checks.yml` and `apps/web-client/tests/`.
> - SAD 15 §4 item 5 applies to the 4F.8 PR's description.

> **RATIFIED 2026-10-11 (§29.1): option (a), restricted to §28.8's surfaces.**
>
> - **Governed:** `companion/`, `services/perception-engine/` (including
>   A-4F8-2 (a1)'s migration) and `infra/docker/` (including §29.2's
>   acceptance-only override).
> - **Recorded, not governed:** `tools/`, `pr-checks.yml` and
>   `apps/web-client/tests/`.
> - **Any other surface needs a new decision.**

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

> **Re-verified 2026-10-11, additively. Absorbed by the ratified A-4FP-12
> (§28.3)**: the companion service, the e2e services and `primary_user_id` are
> merged.
>
> - **One residual:** the stack-completeness test was not extended. Other P8
>   guards cover those services instead.
> - The companion runs as its image's uid 1000, the same uid as
>   `capability-engine`. §28.7 (B) would change that default.

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

> **Re-verified 2026-10-11, additively (§28.4). All five requirements are met
> by merged 4F.P**, with evidence at `1ccce7a`.
>
> - Item 4 holds **only from distinct new paths**: a path initiates at most
>   once (FP-14, §28.9).
> - Item 5 holds. `cognitive-state-engine` only logs its own trigger's reply,
>   and reads no autonomy store or route.

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

> **Re-verified 2026-10-11, additively.** E-1 … E-17 are kept as written, and
> remain subject to their §7 decisions.
>
> - **FP-14 (§28.9):** E-1, E-3, E-6, E-8 and E-9 each use file paths never
>   observed before in the stack.
> - **F-4F8-14:** every new path also starts an initiative. So E-8, E-10,
>   E-12 and P-AC8-1 must be sequenced and attributed by `subject_id`.
> - **F-4F8-15:** E-6 alone cannot distinguish D2's gate from the companion's
>   silent stop. E-5, N-5, N-8 and D2's `real_infra` tier carry that.
> - **E-17's denial already ran** in 4F.P's composed run (§28.2).

> **Added 2026-10-11 (§29.4.6), additively.** **E-18: the revocation is
> specific to the sensor.** After the revocation:
>
> - `docker compose exec -T nova-companion ls /workspace` fails;
> - `docker compose exec -T capability-engine ls /workspace` succeeds.
>
> This is a read-only OS inspection inside the real containers, disclosed as
> infrastructure evidence. §29.4.5 maps every clause to its evidence source.

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

> **Added 2026-10-11 (§29.4.6), additively.** **N-16:** drop the acceptance
> override, so the companion runs as uid 1000. E-18 must then fail, because
> `capability-engine` loses access too.
>
> ***Corrected 2026-10-12, additively (§39.4):*** the note above is preserved
> as written. In CI, E-18 did fail under N-16, but `capability-engine` kept its
> access. E-18 failed because the companion, as uid 1000, was **not denied at
> all**: it reads through the *other* bits of `0705`.

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

> **Re-verified 2026-10-11, additively (§28.13).**
>
> - **Step 2 is done**: 4F.P is merged as `1ccce7a`.
> - **Step 3 is done** by §28, on `phase-4f8-tdd`.
> - **Step 1 is outstanding**: A-4F8-1, -2, -4, -6, -7 and -8, with §28.7's
>   choice. A-4F8-3 and A-4F8-5 are answered, and A-4F8-10 is absorbed.
> - **Step 4 is outstanding**: the user's explicit GO.
> - **No implementation branch exists.**

> **Ratified 2026-10-11 (§29.6), additively.**
>
> - **Step 1 is done:** the six candidates and §28.7 (B) are ratified.
> - **Steps 2 and 3 are done.**
> - **Step 4 is outstanding:** the user's explicit GO to cut the
>   implementation branch from the then-current `phase-4` HEAD.
> - **Implementation follows §29.4's acceptance plan**, and §29.5's acceptance
>   checks.

> **Step 4 authorized 2026-10-11 (§30.4), additively.** The user authorized
> cutting the implementation branch, **`phase-4f8`**, from `phase-4` at
> `1ccce7a`, after the D-4F-1 record. Implementation follows §29.4 and §29.5,
> plus §30.3.

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

> **Re-verified 2026-10-11, additively (§28.1).** The base is now **47,817**
> at `1ccce7a`, measured by the same `cloc` methodology, which reproduces
> 47,433 at `9d2d636`.
>
> - **The headroom is 2,183.**
> - The 4F.8 estimate above is unchanged. At its top of 450, 1,733 would
>   remain.
> - The table's 4F.P row is now measured: +384 (4F.P record §7.4).

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

> **Status on `phase-4f8-tdd`, 2026-10-11, additively.** The status above is
> kept as written. Its *"Blocking: … 4F.P's merge"* and *"4F.P is not
> started"* are historical: 4F.P is merged (`1ccce7a`).
>
> - **Still PREPARED. NOT RATIFIED. NOT implementation-ready.**
> - **Blocking:** A-4F8-1, -2, -4, -6, -7 and -8, with §28.7's choice.
> - **A-4F8-9** still blocks 4F's GO.
> - **CF-9, CF-10 and CF-11 stay OPEN.** AC-8 is not claimed.
> - **4F.8 is not started.** §28 is the re-verification.

> **Status on `phase-4f8-tdd`, 2026-10-11, after ratification (§29.6).**
>
> - **RATIFIED:** A-4F8-1, -2, -4, -6, -7 and -8, and §28.7 (B).
> - **Implementation waits only for the user's explicit GO.**
> - **One scope decision is open:** reopening D-4F-1 (§29.3).
> - **A-4F8-9** still blocks 4F's GO.
> - **CF-9, CF-10 and CF-11 stay OPEN.** AC-7 and AC-8 are not met, and not
>   claimed.
> - No implementation branch exists.

---

## 28. Re-verification against merged 4F.P — 2026-10-11

**Added 2026-10-11, additively** (protocol §0.3.4). §0–§27 are preserved as
written. They describe the repository at `9d2d636`; this section records it at
`1ccce7a`. Where the two differ about the repository's state, this section is
the current one. Short dated pointer notes in the earlier sections lead here.

- **Authority.**
  - §22 step 3: *"Re-verify this TDD against merged `phase-4`, and amend it
    additively where 4F.P fixed a detail."*
  - TDD 4F.P §30.6 item 2 and §30.9, ratified 2026-09-29. The re-verification
    *"records the settlements in §30.9 additively, on the branch that carries
    TDD 4F.8"*.
- **Authorized by the user on 2026-10-11 as step 1 only.** It covers
  documentation and verification. **Nothing in this section ratifies an A-4F8
  candidate, cuts an implementation branch, or authorizes implementation.**
- **Status is unchanged: PREPARED. NOT RATIFIED. NOT implementation-ready.**

### 28.1 Baseline, re-verified at `1ccce7a`

| Fact | Value at `1ccce7a` | Evidence | Change since §3 (`9d2d636`) |
|---|---|---|---|
| `origin/phase-4` | **`1ccce7a703cfc5c6d7c164467c5e8ed8c5820c90`**, the merge of PR #39 (4F.P). Parents `88fa46f` and `2b0757d` | `git rev-parse`; `git log -1 --format=%P` | Advanced by PR #40 (`88fa46f`, dependency security) and PR #39 (4F.P) |
| `origin/main` | **`7e273e62e942ecd5528ca807e65933d6bb675669`** | `git rev-parse` | Unchanged |
| The merged tree | Identical to PR #39's head `2b0757d`: both are tree `673bd28`. **40 of 40** check runs were `success` at `2b0757d`, all on attempt 1. No workflow runs on the merge commit itself, since the workflows trigger on `pull_request` and on `push` to `main` only | `git rev-parse <sha>^{tree}`; the GitHub API | — |
| Slices merged | 4F.1 … 4F.7, and **4F.P** | Master scope §5; the eight completion records | 4F.P added |
| Registered Event Bus subjects | **120**. The only `autonomy.*` subject is still `autonomy.decision.requested` | `len(nova_contracts.registry._REGISTRY)`, after importing every `nova_contracts.events` module from a `git archive` of `1ccce7a` | Unchanged |
| `PUBLIC_TOPICS` | **18**. Three are `perception.*`: `identity.observed`, `presence.observed` and `sensor.health_changed` | AST parse of `ws-gateway/domain/protocol.py` at `1ccce7a` | Unchanged |
| `api-gateway` prefixes | **The same nine.** No `/v1/perception`, `/v1/world` or `/v1/memories` | `api-gateway/domain/routing.py` at `1ccce7a` | Unchanged |
| The e2e stack | **It now starts `perception-engine`, `perception-engine-worker` and `nova-companion`** in its own step after the golden path, *"Start the P8 services"* (`pr-checks.yml` l.690). It then runs the P8 proof (l.700) | `pr-checks.yml` at `1ccce7a` | Changed by A-4FP-12 (§28.3) |
| The `nova-companion` compose service | **Present** (`docker-compose.local.yml` l.696). `NOVA_COMPANION_WATCH_ROOT=/workspace` (l.702), bind-mounted read-only from `${NOVA_WORKSPACE_DIR:-./workspace}` (l.705) | Compose at `1ccce7a` | Added by A-4FP-12 |
| `perception-engine`'s `primary_user_id` | **Set**, to `PERCEPTION_ENGINE_PRIMARY_USER_ID: 00000000-0000-0000-0000-000000000001` (l.637) | Compose at `1ccce7a` | Set by A-4FP-12 |
| `capability-engine`'s sandbox root | `/workspace`, bind-mounted read-write from **the same** host directory (l.775, l.782) | Compose at `1ccce7a` | Added by A-4FP-12 |
| Perception outbox dispatch | An Arq cron at seconds `{0, 10, 20, 30, 40, 50}` | `perception-engine/workers/__init__.py` at `1ccce7a` | Unchanged |
| **SLOC, 4F scope** | **47,817**: Comparable 37,797, Wider 43,138, Full 47,171, plus the companion less its tests, 646. **Headroom to 50,000: 2,183** | `cloc` v2.06 `--skip-uniqueness --quiet` over a pristine `git archive` of `1ccce7a`, by the 4E methodology. The same run reproduces §3's 47,433 at `9d2d636`, and the 4F.P record's 47,817 at `d1ae981`, exactly | +384, all of it 4F.P's (4F.P record §7.4) |
| Docker in this environment | **Not available**: `docker info` fails | — | Unchanged. Every real-infrastructure and browser result remains CI's |
| Protocol | sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`, 1131 lines, `origin/main`. Read in full for this re-verification | `sha256sum` | Unchanged |

**§23's base becomes 47,817, with headroom 2,183.** §23's 4F.8 estimate of
180–450 is unchanged. At its top, it would leave 1,733.

### 28.2 A-4F8-3 and A-4F8-5: answered by 4F.P, recorded as §30.9 directs

**These two are recorded here, not decided here.** TDD 4F.P §30.9, which is
ratified, says each one is *"recorded as settled at re-verification"* once 4F.P
is merged.

- Their answers are 4F.P's ratified decisions, as built and merged.
- **Neither is one of the six candidates that still await the user (§28.11).**

| Candidate | Answer | Evidence at `1ccce7a` |
|---|---|---|
| **A-4F8-3**: executability, and AC-8's low-risk case | **Option (a), owned by 4F.P.** `ProposedAction` carries `operation` and `parameters` (A-4FP-4). They are authored only from the closed table (A-4FP-3), and carried through the trigger, `DecisionRequest` and `action.execute` (A-4FP-6). **AC-8's low-risk case is T1**: `read` / `low` / `filesystem` / `filesystem` / `list` / `{}` / `adapter_success` | **T1:** `cognitive-state-engine` `domain/authoring.py` l.98–100. **The dispatch:** `autonomy-engine` `domain/decision.py` l.204 (`_execution_payload`) and l.248 (`{"operation": …, **parameters}`). **Rule 1's drift test:** `tests/contract/test_authoring_risk_drift.py` |
| — A-4F8-3's four-part low-risk constraint | (1) T1 is authored `low`. (2) `classify_risk("filesystem", "list")` is `negligible`, below `low`. (3) `filesystem` is a bootstrap-installed built-in. (4) The effect, the listed `entries`, is read by independent SQL from `action.action.result` | (1) `authoring.py` l.100. (2) `action-engine` `domain/risk.py` l.31 and l.39–40. (3) `capability-engine` `main.py` l.191. (4) The 4F.P record §1.1, links K–N |
| **A-4F8-5**: the stage-3 configuration | **Option (a), as A-4FP-11 ratifies it.** `minimum_confidence_by_risk = {<tier>: 0.0}` is written through the production `PUT /v1/action/identity-confidence-policy`. It covers **exactly** the tier `action-engine` assigns to the executed action, which is **`negligible`** for T1. It is disclosed test configuration, never a production default. Stage 3's code, its absent-policy default of `1.0` and the `0.75` ceiling are unchanged, and D-4F4-4 is kept | The 4F.P record §1.1, link H. **The negative control ran in CI.** Without the row, the real `action-engine` denied with `identity_confidence_denied`, and P7 recorded `propose` with zero capability invocations: the 4F.P record §1.2, and job `114437089762` at `2b0757d`, 67/67 |

- **What this changes in this TDD.** §7, §13.3, §15 step 11, §16 (E-17), §17
  (N-10) and §23 depend on A-4F8-3 or A-4F8-5. They now read under these
  answers.
- **A-4F8-5's tier is `negligible`, not `low`.**
  - E-11's *"`action.action.risk` at or below `low`"* still holds.
  - A-4FP-11 scopes the threshold to `negligible` only.
- **E-17's denial has already run once**, in 4F.P's composed run. 4F.8 still
  runs it again in its own acceptance sequence.

### 28.3 D4 and A-4F8-10: absorbed by A-4FP-12, with one residual

A-4FP-12, which is ratified, *"moves 4F.8's proposed D4 and A-4F8-10 into
4F.P"*. As merged:

| A-4F8-10 sub-question (§7), or D4 | Recommended default | Merged at `1ccce7a` | Absorbed? |
|---|---|---|---|
| How the companion runs | (a) A compose service, running as its image's non-root user, watching a bind-mounted host directory the harness writes to | The `nova-companion` service (compose l.696). It runs as the image's `nova`, uid 1000 (`companion/nova-companion/Dockerfile` l.34 and l.37), with `/workspace` bind-mounted read-only (l.705) | **Yes.** But see §28.7: the same directory is also `capability-engine`'s sandbox root |
| `perception-engine` and its worker in the e2e job | Added | Started by *"Start the P8 services"* (`pr-checks.yml` l.690), **after** the golden path (4F.P record §3.2, C-1) | **Yes**, with C-1's sequencing (§28.6, F-4F8-16) |
| `perception-engine`'s `primary_user_id` | The stack's one user (ADR-025) | `…0001` (compose l.637). Guarded by `test_one_user_perception_engine_resolves_every_other_engines_primary_user` | **Yes** |
| `tools/tests` stack-completeness, extended to require the new services and workers | Extended | **Not extended.** `tools/tests/test_e2e_stack_completeness.py` is unchanged since `9d2d636`, and its `_started_services()` parses only the *"Start the stack"* `up` block (l.111–115). See the note below the table | **No: a residual.** Other guards cover the P8 services. The stack-completeness file does not know them. Recorded here, not changed, because this step is documentation only |
| D4 itself | The acceptance stack runs AC-7's services | As above | **Yes** |

The P8 services are guarded instead by five tests in
`tools/tests/test_e2e_real_execution.py`:

- `test_the_companion_is_a_compose_service_watching_the_bind_mounted_workspace`;
- `test_one_workspace_the_capability_sandbox_root_is_the_watched_directory`;
- `test_the_workspace_exists_before_the_first_up`;
- `test_the_p8_services_start_after_the_golden_path_not_with_it`;
- `test_the_proof_runs_after_its_services_and_its_failure_fails_the_job`.

- **D4 leaves 4F.8's deliverable list in §1.1**, because A-4FP-12 built it.
  What 4F.8 still adds to the stack is configuration for D3's bindings
  (A-4F8-2), plus whatever §28.7's decision requires.
- **A-4F8-10 is absorbed, and is not one of the six.** Its content was ratified
  as A-4FP-12. What remains of it for 4F.8 is the residual above, and §28.7
  option (B)'s companion uid, if that option is chosen.

### 28.4 §11's interface requirements, against merged 4F.P

| # | Requirement | Met? | Evidence at `1ccce7a` |
|---|---|---|---|
| 1 | A production-reachable promotion | **Yes** | `ingestion_orchestration.py` l.98 (insert-if-absent) and l.103 (`promote_thought`). It is the only production caller (`test_p14_promote_thought_has_exactly_one_production_caller`). In CI: the P8 proof's links C–G at `2b0757d` |
| 2 | A reproducible input in CI | **Yes** | A real file write in the shared workspace, observed by the real companion (link A). Every `perception.workspace.observed` of the stack's user is ingested (A-4FP-1). **A `project_id` is not required** |
| 3 | An executable proposal, under A-4F8-3's four-part constraint | **Yes** | T1 (§28.2) |
| 4 | Two runs of the same category in one acceptance run | **Yes, but only from distinct new paths** | A path initiates at most once (A-4FP-9; FP-14). The P8 driver writes `p8-{run_id}-{tag}.txt` per run (`tools/e2e_real_execution.py` l.492). It runs A, B and C in one stack: two executions and one denial. §28.9 carries the rule forward |
| 5 | No coupling to autonomy data (RS-4b) | **Yes** | `git grep` over `cognitive-state-engine/src` at `1ccce7a` finds no read of `autonomy.*` tables or of `/v1/autonomy`. The trigger's own reply, which is 4F.6's contract, is **logged** with its outcome and `subject_id` (`events/handlers.py` l.196–209). Nothing from it is persisted |

### 28.5 F-4F8-1, F-4F8-2 and F-4F8-8, re-checked

| Finding (at `9d2d636`) | At `1ccce7a` | Evidence | Limitation preserved |
|---|---|---|---|
| **F-4F8-1**: no real Level-2 dispatch can execute, because `parameters={}` | **Resolved for T1** | `decision.py` l.248 builds `{"operation": request.operation, **request.parameters}`. `action-engine`'s stage 2 is unchanged (`pipeline.py` l.128–135), and `git diff --stat 9d2d636 1ccce7a -- services/action-engine services/capability-engine` is empty. Composed, in CI at `2b0757d`: link J (`parameters == {"operation": "list"}`) and link K (`completed`) | **Only T1 exists.** An input kind with no authoring entry yields no proposal. A trigger without the pair stays a suggestion (A-4FP-6; `test_p4_a_trigger_without_the_pair_stays_a_suggestion_on_the_real_path`). Adding an entry is a new ratification (A-4FP-3) |
| **F-4F8-2**: `EXECUTE` is recorded for any reply | **Resolved** | `decision.py` l.255 (`ACTION_STATUS_OUTCOMES`) and l.294, applied at l.545. Unit: `test_p7_the_ratified_table_exactly` and `test_p7_completed_is_the_only_status_that_maps_to_execute`. Composed, in CI: `completed` → `execute` (links O–P), and a real `denied` → `propose` (4F.P record §1.2) | **The `failed` mapping is evidenced by two per-engine halves, not by one integrated real-adapter failure.** This is the 4F.P record §8.1, F-4FP-1, accepted with that limitation on 2026-10-11. **E-9 keeps its independent `action.action.status = completed` read.** P7 makes `EXECUTE` mean a `completed` reply, and the second read stays as defence in depth |
| **F-4F8-8**: the acceptance stack cannot run AC-7 | **Partly resolved** | §28.3. The services, the companion, the user and the e2e step exist, and they ran in CI | **AC-7 still cannot be demonstrated.** There is no revocation path (F-4F8-7; D1, D2), no known-project correlation (F-4F8-5; D3) and no latency harness (D5). The P8 services start after the golden path (F-4F8-16) |

F-4F8-1 … F-4F8-12 keep their §5 text.

### 28.6 New findings of this re-verification

| # | Finding | Evidence | Goes to |
|---|---|---|---|
| **F-4F8-13** | **The companion and `capability-engine` share one directory with identical OS credentials.** So a permission revocation on the watched root also revokes `capability-engine`'s sandbox root | §28.7 | **A user decision**, made with A-4F8-1 and the acceptance sequence (§28.7) |
| **F-4F8-14** | **Since 4F.P, every new observed path starts an initiative.** Each `perception.workspace.observed` of the stack's user with a never-seen `object_id` becomes one thought, is promoted, and sends one `autonomy.decision.requested` (A-4FP-1, A-4FP-2, A-4FP-10). So AC-7's latency samples, its revocation writes and AC-8's runs all drive the AC-8 path. At Level 1, each sample yields a suggestion visible in the Autonomy panel. At Level 2, with T1's `AUTO_EXECUTE` policy in place, each sample executes `list` | `ingestion_orchestration.py` l.98–103; `domain/ingestion.py` l.68–70 | **The acceptance design (D5, D6, D7).** It must sequence AC-7's samples and AC-8's two runs, and attribute each decision by `subject_id`. Otherwise AC-7's samples confound E-8, E-10, E-12 and P-AC8-1 (*"no new proposal appears"*). Also, a `project_id` added by D3 lands in the thought's `related_projects` (A-4FP-1), with no other effect |
| **F-4F8-15** | **After a revocation, the merged companion drops events silently.** An existing inotify watch keeps delivering events after the watched root's mode changes. This is F-4F8-7's expectation, now demonstrated locally (§28.7, demonstration 3). But `observation_from`'s `std::fs::metadata` then fails with `EACCES`, and the event is dropped as `Ignored::NotARegularFile`, with no report | `companion/sensors/src/lib.rs` l.88–91 and l.101–102; §28.7 demonstration 3 | **E-6 alone cannot tell D2's gate apart from this silent stop.** That distinction rests on E-5 (`failed`, visible), on N-5 and N-8, and on D2's `real_infra` tier (§18). D1 must replace the silent drop with a report (A-4F8-1). Nothing is changed here |
| **F-4F8-16** | **The P8 services start after the golden path** (4F.P C-1), because `cognitive-state-panel.spec.ts › shows the honest empty states of an unseeded stack` asserts that no `perception-engine` runs. P-AC7-1 needs `perception-engine` running, with the panel showing `companion-filesystem` | 4F.P record §3.2, C-1; `pr-checks.yml` l.690; `test_the_p8_services_start_after_the_golden_path_not_with_it` | **D7's sequencing.** P-AC7-1 runs after the P8 services start, or the unseeded spec is retargeted, disclosed. This is a choice inside A-4F8-7 and D7, not a new decision |

### 28.7 The shared workspace and A-4F8-1 (a), analysed

**The question.** A-4F8-1 (a)'s acceptance demonstration withdraws the
companion's OS permission on its watched directory. Under A-4FP-12, that
directory is also `capability-engine`'s sandbox root. Does revoking it revoke
`capability-engine` too?

**Repository evidence, at `1ccce7a`:**

- **`nova-companion` runs as `nova`, uid 1000** (`companion/nova-companion/Dockerfile`
  l.34, `useradd --create-home --uid 1000 nova`, and l.37, `USER nova`).
- **`capability-engine` also runs as `nova`, uid 1000**
  (`services/capability-engine/Dockerfile` l.23 and l.27).
  - So does `perception-engine` (l.23 and l.27).
  - All three Dockerfiles run the same `useradd` line, with no `--gid`, on
    Debian-based images, so all three get the same primary group. With the
    same uid and the same gid, no mode bit and no ACL entry can tell the
    services apart.
- **Compose overrides none of this.** `user:`, `userns_mode` and `group_add`
  do not occur in `docker-compose.local.yml`.
- **Both services mount the same host directory**,
  `${NOVA_WORKSPACE_DIR:-./workspace}`, at `/workspace`. It is read-only for
  the companion (l.705) and read-write for `capability-engine` (l.782).
- **CI creates that directory** with `mkdir -p "$RUNNER_TEMP/nova-workspace"`,
  as the job's user (`pr-checks.yml`, *"Provision the shared workspace (4F.P
  P8)"*). So uid 1000 reaches it through the group or other bits, never as
  its owner.
- **A-4FP-12 fixes the one workspace**, and
  `test_one_workspace_the_capability_sandbox_root_is_the_watched_directory`
  enforces it.

**OS semantics.**

- A bind mount shares the host inode. Linux checks a container process's uid
  and gid against that inode's mode bits and ACL entries.
- A `:ro` mount flag restricts writes through that one mount. It is not a
  permission.
- **Two processes with the same uid and gid are indistinguishable** to every
  mode bit and every POSIX ACL entry.
- Docker's `userns-remap`, if a daemon enabled it, would remap every container
  the same way. So it would not separate them either.

**Demonstrated locally.** This ran in this session, on kernel `6.18.44`, as
real processes under the stack's uids, via `setpriv`. **It is local evidence:
not CI, and not containers.**

| # | Arrangement | Before | After the revocation | The harness (directory owner) |
|---|---|---|---|---|
| 1 | As merged. The companion is uid 1000, and so is `capability-engine`. The directory's owner is 1001, a stand-in for the runner. Mode `0755` | Both can list it | After `chmod 0700`, **both get `PermissionError` (EACCES, 13)** | Can still write |
| 1b | The same uids, with the directory's group set to `nova` (1000) and mode `0750` | Both can list it | Group bits cannot separate them, because both have the same gid | — |
| 2 | **The alternative.** The companion is uid 1100. The directory's group is 1000, which is `capability-engine`. Mode `0755` | Both can list it | After `chmod 0750`, which removes the other bits, **the companion gets EACCES and `capability-engine` can still list it** | Can still write |
| 3 | An inotify watch, held by uid 1000, across a `chmod 0700` of the watched directory | — | See below | — |

For demonstration 3:

- **Events keep arriving.** `IN_CREATE` and `IN_CLOSE_WRITE` are delivered for
  a file written after the revocation.
- `IN_ATTRIB` arrives on the root itself, at the moment of the `chmod`.
- `stat` of the new file fails with EACCES.

**Conclusion: the conflict is real.** Under the merged arrangement, **no
permission change on the watched directory can revoke the companion's access
without revoking `capability-engine`'s identically.**

- **What it does not invalidate:** evidence already collected. The 4F.P P8
  proof and AC-8's runs read `action.action`, the decision log and the
  capability's result **before** any revocation. A revocation sequenced after
  them changes none of that.
- **What it does make impossible:**
  - any successful `filesystem` capability invocation in that stack after the
    revocation;
  - so, any AC-8 run, or any re-run of the P8 proof, after AC-7's revocation.

  With A-4F8-1 (a2), which has no automatic recovery, the revocation is
  terminal for that stack until it is restarted.
- **A-4F8-1 (a)'s ownership decision is not affected.** The companion still
  detects the revocation, and `perception-engine` still owns the transition.
  Demonstration 3 supports (a)'s detection: the root's `IN_ATTRIB` arrives at
  the revocation, and the next `stat` fails. **The conflict is in how the
  acceptance stack exercises the revocation, not in who owns it.**

**Options, for the user's decision. Nothing is changed in this step.**

| Option | What changes | Consequence | Does it amend a ratified decision? |
|---|---|---|---|
| **(A) Sequence the revocation last** | Nothing in the stack. The acceptance sequence runs, in order: the P8 proof → AC-8's Level-1 and Level-2 runs → AC-7's latency samples → the revocation → E-5, E-6 and P-AC7-1 | No configuration change. **But** the revocation also withdraws `capability-engine`'s access, and the evidence must disclose that. The run is order-dependent and destructive: nothing that executes `filesystem` may follow the revocation. *"Revoking that sensor's OS-level permission"* is satisfied, but with a collateral revocation | No |
| **(B) Give the companion its own uid in the acceptance stack** | The `nova-companion` service gets a compose `user:` with a distinct non-root uid. The job sets the workspace's group to `capability-engine`'s gid 1000, which is a privileged `chgrp`, because the runner's user is not in that group. The companion then reaches the directory through the other bits, and `capability-engine` through the group bits. The revocation becomes `chmod o-rx` | **The revocation is specific to the sensor** (demonstration 2). The stack keeps executing afterwards, so the sequence is not destructive. This is a deployment-configuration change in 4F.8's `infra/docker` and `pr-checks.yml`, inside A-4F8-8's scope, with **no production code**. It departs from A-4F8-10 (a)'s *"its image's non-root user"* default, which A-4FP-12 absorbed | No ratified text: A-4FP-12 fixes one workspace and one **NOVA** user, not an OS uid. It **does** change A-4F8-10 (a)'s unratified default, disclosed here |
| (C) Separate directories | `capability-engine`'s sandbox root and the companion's watch root become different directories | **It amends A-4FP-12** (*"One workspace"*) and breaks its guard. The P8 proof's link M, the capability listing the observed file, would change | **Yes: A-4FP-12.** Not recommended |
| (D) Revoke one project subdirectory only | The revocation targets a known project's root, inside the watch root | **It changes A-4F8-1's meaning** (*"the configured directory"*), and AC-7's *"stops the perception stream"*, because other files keep flowing | It changes A-4F8-1 (a)'s text. Not recommended |

**Recommendation: (B)**, with (A) as the fallback if a compose `user:`
override is not wanted.

- (B) makes the demonstrated revocation exactly AC-7's *"revoking that sensor's
  OS-level permission"*.
- It keeps A-4FP-12's one workspace and its guard.
- It keeps the acceptance stack usable after the revocation.

**This is a recommendation, not a decision.**

- It is decided together with A-4F8-1 and A-4F8-8 (§28.11).
- D1's Cargo tier (§18) must still establish the companion's real behaviour on
  the CI runner.

> **RATIFIED 2026-10-11 (§29.1): option (B).** The acceptance-stack companion
> runs under a distinct non-root uid.
>
> - **The plan is B2**: uid 1100 with the runner's gid, revoked by
>   `chmod g-rx`, in an acceptance-only compose override.
> - **B2 and B1 were verified at runtime** with the real companion binary and
>   `capability-engine`'s real adapter. The revocation removed the companion's
>   access, and `capability-engine` still listed the directory (§29.2).
> - **The Dockerfile and the base compose are unchanged.**

### 28.8 A-4F8-8, re-scoped and not ratified

A-4F8-8 asks whether the 4F.8 PR is granted RS-9's kind of exception to SAD 15
§4 item 1. After 4F.P, the surfaces 4F.8's remaining deliverables need are:

| Surface | For | Under A-4FP-13's precedent |
|---|---|---|
| `companion/` | D1, revocation detection | **Governed**: needs the exception |
| `services/perception-engine/` | D2: the `failed` path and one internal route. D3: the correlation, plus an Alembic migration only under A-4F8-2 (a1) | **Governed** |
| `infra/docker/` | D3's operator-declared bindings. §28.7 (B)'s companion uid, if that option is chosen | **Governed** |
| `tools/` | D5, D6 and D8: the harnesses and structural controls | Recorded, not governed |
| `.github/workflows/pr-checks.yml` | Running D5–D7 in the e2e job | Recorded, not governed |
| `apps/web-client/tests/` | D7, the Playwright specs | Not an engine's `src/`. Recorded |

- **Removed from its scope by 4F.P:** D4's deployment wiring (A-4FP-12).
- **The precedent:** A-4FP-13 granted 4F.P an exception for four surfaces.
  `pr-checks.yml` and `tools/` were recorded, not governed, and items 2–5 stayed
  mandatory.
- **Item 5 applies to the 4F.8 PR.** Its description must cite the Bible
  sections implemented, per this document's header table and §25 row 16:
  - Part 11, PERCEPTION SECURITY (l.567–589, including l.569) and SENSOR HEALTH
    (l.529–548);
  - Part 14, AUTONOMY LEVELS, Level 2 (l.101–107);
  - Part 12, THE ACTION PRINCIPLE (l.43–93).
- **It is not ratified.** Its final scope depends on A-4F8-1, A-4F8-2 and §28.7.

### 28.9 FP-14, carried forward

TDD 4F.P A-4FP-9 and §30.9, both ratified: **every independent acceptance run
uses file paths never observed before in that stack.** A path initiates at most
once in the lifetime of its thought, and a re-observation writes nothing.

- **AC-8.** The Level-1 run and the Level-2 run use **two distinct new paths**
  (§30.9). A reused path would yield no second trigger, and E-8 and E-9 would
  compare one decision with nothing.
- **AC-7's latency samples (E-3).** Each sample uses a new path.
  - A rewritten path's World Model object already exists, so *"the first
    observation of its World Model object"* is not measurable for it.
  - Each new path is also a new initiative (F-4F8-14).
- **E-6's post-revocation write** uses a new path. Then the expected absence
  of an outbox row and of a World Model object is unambiguous.
- **Evidence that the rule holds as built:**
  - `insert_thought_if_absent` (`ingestion_orchestration.py` l.98);
  - the P8 proof's composed V-7 (a1) checks, which passed in CI at `2b0757d`. A
    second modification of the same file gives one thought, one trigger and
    one action.

### 28.10 The master-scope reconciliation

**Why a merge.**

- Master scope §16 rule 5: *"Every milestone branches from the freshly merged
  `phase-4` HEAD — never from an older snapshot."*
- TDD 4F.P §30.6 item 2 places this re-verification *"on the branch that
  carries TDD 4F.8"*.
- Both are met by bringing `phase-4` @ `1ccce7a` onto `phase-4f8-tdd` with a
  normal two-parent merge, as `9afddf6` and `fee1fea` did for milestone
  branches. There was no rebase and no rewrite.

**The merge commit** is **`1ea0d0ff399d051e057b181cc86c7b261dcd642e`**, with
parents `5a95475` and `1ccce7a`.

**The conflict.** There was one hunk, in `00-master-scope.md` §17's table of
TDDs. It is the cost that §16's *"No parallel branch ever modifies the same
file as another"* guards against: `phase-4p-tdd` (later `phase-4fp`) and
`phase-4f8-tdd` both edited §17, starting from `9d2d636`.

- `phase-4`'s side left the 4F.7 row unchanged, and added row 13 (TDD 4F.P).
- This branch's side inserted its dated 2026-09-27 note into the 4F.7 row's
  last cell, insert-only, and added row 12 (TDD 4F.8).

**The resolution, by protocol §0.3.4: corrections are additive.**

- Every line of both sides is kept: the 4F.7 row with its note, then row 12,
  then row 13.
- The only line of `phase-4`'s side that does not appear verbatim is the 4F.7
  row's `9d2d636` text. It appears, unchanged, inside the noted row.
- The §5 notes merged without a conflict. They keep both sides' order: 4F.P's
  notes, then this branch's 2026-09-27 slice status.

**A correction to the merge commit's message, made additively.**

- The message says the branch differs from `phase-4` by exactly `5a95475`'s
  change, *"(identical patch-id)"*.
- Precisely:
  - The added and removed lines (993 of them) are identical.
  - The diffstat is identical: 2 files, +1431/−1.
  - **The zero-context patch-id is identical**:
    `git diff -U0 … | git patch-id --stable` gives `0c1f3fc…` for both.
  - The default-context patch-id differs (`49d326c…` against `6682427…`), only
    because the hunk's context now includes row 13.
- The commit cannot be rewritten. This paragraph corrects it.

### 28.11 The six candidates awaiting the user's decision

**None is ratified, resolved or accepted by this re-verification.** Each keeps
its §7 text. This table states what 4F.P's merge changed about each one.

| Candidate | Question (§7) | Recommended in §7 | What changed since §7 | Unresolved trade-offs |
|---|---|---|---|---|
| **A-4F8-1** | Who detects OS-level permission revocation, and how does it reach the sensor lifecycle? This is RS-3b's owner | (a): the companion detects, and `perception-engine` owns `running → failed` through one internal route. (a1): a separate internal route. (a2): no automatic recovery | **§28.7:** the acceptance stack cannot revoke the companion without also revoking `capability-engine`, so option (A) or (B) must be chosen with it. Demonstration 3 supports (a)'s detection: `IN_ATTRIB` arrives at the revocation, and `stat` fails with `EACCES`. F-4F8-15: today's companion stops silently | (a2): re-granting needs restarts. One more internal route against TDD 4F.3 §7's scope, disclosed in §26. §28.7's choice |
| **A-4F8-2** | What makes a project "known", and how is the correlation populated? | (a): operator-declared root bindings, activated by identities from `memory.long_term.created`. (a1): an additive `perception` table. (a2): the World Model unchanged | A-4FP-1 needs no `project_id`. A D3 `project_id` lands in the thought's `related_projects` (F-4F8-14). L-13 stays 4F.8's | One new subscription. (a1)'s table means a migration in `perception-engine`. *"Known"* is evidenced on the observation, not on the per-file World Model object (F-4F8-6) |
| **A-4F8-4** | Does AC-8's evidence require the production trigger? | (a): the production trigger only, in one 4F.8 slice after 4F.P | **Its execution is now unblocked**: 4F.P's production caller is merged (§28.4 item 1). The P8 guards are a precedent for E-13's structural check | Option (c)'s split, AC-7 first and AC-8 in a second PR, stays the user's sequencing choice |
| **A-4F8-6** | How is AC-7 measured? | Observe through `world-model-engine`'s own REST, starting at the file's mtime. At least ten independent samples, every figure reported. Pass only if all are ≤ 5.0 s. A 30 s deadline per sample | FP-14: each sample uses a new path (§28.9). F-4F8-14: each sample also starts an initiative. The 10 s cron is unchanged, so **most runs are still expected to fail** and report their figures (§20.1) | A red result is expected. A decision on D-4F-1 belongs to the Gate Review, not to 4F.8 |
| **A-4F8-7** | Where is AC-8's execution evidenced, and what does *"both criteria in a browser"* mean? | (a): no new surface. The browser shows each browser-visible clause; SQL on `autonomy.decision_log` and `action.action` shows the rest. TDD 4F §18's phrase is clarified additively | P7 makes the decision log truthful: `execute` only for `completed`, and `denied` and `execution_failed` are now distinct outcomes. F-4F8-16: P-AC7-1's sequencing. F-4F8-14: AC-7's samples must not confound P-AC8-1 | It requires the additive clarification of TDD 4F §18 (§26) |
| **A-4F8-8** | SAD 15 §4 item 1 for the 4F.8 PR | (a): an exception scoped to 4F.8's ratified surfaces, with items 2–5 mandatory | **Re-scoped (§28.8).** `companion/`, `services/perception-engine/` and `infra/docker/` are governed. `tools/`, `pr-checks.yml` and `apps/web-client/tests/` are recorded. D4's wiring is removed | The final scope waits on A-4F8-1, A-4F8-2 and §28.7 |

**Not among the six:**

- A-4F8-3 and A-4F8-5, answered (§28.2);
- A-4F8-10, absorbed (§28.3);
- **A-4F8-9**, which still blocks **4F's GO** but not 4F.8's implementation. It
  creates no new milestone.

### 28.12 Acceptance criteria and open findings, unchanged

- **AC-7: NOT MET, and not yet demonstrable.** D1, D2, D3 and D5 do not exist.
- **AC-8: NOT MET, and not claimed.**
  - 4F.P evidences the production mechanism (its links A–P), and it does not
    claim AC-8.
  - No run has compared one category at Level 1 against Level 2. There is no
    browser clause (P-AC8-1).
  - E-8 … E-17 have not been executed under a ratified A-4F8-4 and A-4F8-7.
- **CF-9, CF-10 and CF-11 stay OPEN.** CF-11's claim 3 stays 4F.8's, and claim 4
  stays 4F closure's.
- **Carried open, and unchanged by this re-verification:**
  - C-7's carried finding, F-4FP-7;
  - FP-24, as L-23;
  - F-4FP-3 … F-4FP-10, including **F-4FP-6**, the `perception-engine`
    flaky-test finding;
  - L-24 … L-28. **L-26 is the work this section performs**, but it stays OPEN
    in the 4F.P record until this change reaches `phase-4`;
  - L-1 … L-6, L-8 … L-11 and L-13 … L-22.

### 28.13 Status after this re-verification

- **§22 step 2 is done.** 4F.P is merged, as `1ccce7a`.
- **§22 step 3 is done**, by this section, on `phase-4f8-tdd`.
- **§22 step 1 is outstanding**: the six candidates in §28.11, and §28.7's
  choice.
- **§22 step 4 is outstanding**: the user's explicit GO to cut the
  implementation branch from the then-current `phase-4` HEAD (master scope §16
  rule 5).
- **PREPARED. NOT RATIFIED. NOT implementation-ready.** No implementation branch
  exists. This re-verification modified no production file, test, migration,
  Dockerfile, workflow, contract or package.

> **Ratified 2026-10-11, additively.** The status above is preserved. **§29
> records the ratification**, the runtime verification of §28.7 (B), the AC-7
> latency analysis and the acceptance plan.

---

## 29. Ratification and pre-implementation verification — 2026-10-11

**Added 2026-10-11, additively** (protocol §0.3.4). §0–§28 are preserved as
written. **Where §29 and an earlier section differ, §29 governs.**

### 29.0 Authority and baseline

**The user's decision, 2026-10-11, verbatim:**

> *"The user explicitly approves the proposed 4F.8 decision set and trusts the
> engineering recommendations. Record the decisions as ratified, subject to the
> technical verification and constraints below."*

- **Ratified:** A-4F8-1, -2, -4, -6, -7 and -8, and §28.7 option (B) (§29.1).
- **How "subject to the technical verification" is applied:**
  - What could be verified before implementation was verified, and is recorded
    with its evidence (§29.2, §29.3).
  - What cannot be verified until the code exists is an **acceptance check
    carried into implementation** (§29.5). It is not assumed.
- **Not ratified by §29:** A-4F8-9, which still blocks 4F's GO.
- **Unchanged:**
  - A-4F8-3 and A-4F8-5 are answered by 4F.P (§28.2).
  - A-4F8-10 is absorbed by A-4FP-12 (§28.3).
  - **D-4F-1 is unchanged** (§29.3).
- **Baseline:** `phase-4` at `1ccce7a`, `main` at `7e273e6`, and `phase-4f8-tdd`
  at `f28e373` before this change. The protocol (sha256 `21185dd1…`, 1131
  lines, `origin/main`) was read in full for this ratification.

### 29.1 The ratified decisions. **RATIFIED 2026-10-11**

#### A-4F8-1 — the revocation owner (RS-3b). **RATIFIED: option (a), with (a1) and (a2)**

- **The companion detects** OS-level permission revocation on its configured
  watch root. It is the only process that holds that permission.
- **It reports the loss over exactly one additional internal route** on
  `perception-engine`'s existing internal surface (a1). That route is not
  fronted by `api-gateway`. `POST /v1/perception/workspace-observations` stays
  frozen.
- **`perception-engine` owns the transition.** It moves the filesystem sensor
  `running → failed` through the existing `report_error` path, and publishes the
  change through 4F.7's `perception.sensor.health_changed` path. It then drops
  every further observation, because the sensor is no longer `running`.
- **No automatic recovery (a2).** A re-granted permission takes effect only
  after the companion and the engine restart. This is a disclosed limitation.
- **None of these is added:** a new subject, a `PUBLIC_TOPICS` change, a gateway
  prefix, a consent mechanism, or an inference of failure from silence (N-8).
- **Detection must replace today's silent drop** (F-4F8-15).
- **It settles RS-3b's owner** (TDD 4F §24.4). It **amends TDD 4F.3 §7**'s
  *"no new route"* for this later slice. A dated note is added at both places in
  this change.

#### A-4F8-2 — known projects. **RATIFIED: option (a), with (a1) and (a2)**

- **Operator-declared folder bindings** bind a watched root to a project
  identity.
- **A binding becomes active only once its project identity has been observed**
  on the existing `memory.long_term.created`. Until then it is inert.
- **Correlation happens inside `perception-engine`'s trust boundary**
  (D-4F3-2).
  - A file whose ancestor root matches an active binding is published on
    `perception.workspace.observed` with that `project_id`.
  - A miss is published with `None`. It is never guessed (N-13).
- **(a1):** the learned project identities persist in **one additive
  `perception` table**, holding current state only.
- **(a2):** `world-model-engine` is unchanged. *"Known"* is evidenced on the
  observation (E-2), and *"reflected in the World Model"* by the `WorldObject`
  (E-1).
- **It adds one subscription to an existing subject.** The registry and
  `PUBLIC_TOPICS` are unchanged. It settles L-13 when implemented.

#### A-4F8-4 — the AC-8 trigger source. **RATIFIED: option (a)**

> *"AC-8's acceptance evidence is produced by the production initiative path,
> from a real input to execution, with no test code standing in for any
> production component. A stand-in trigger is supplementary evidence only, is
> labelled as such, and never makes AC-8 met."*

- **One 4F.8 slice.** Option (c)'s split is not taken, as the approved
  recommendation advised.
- E-13's structural check applies.

#### A-4F8-6 — the AC-7 measurement. **RATIFIED**

- **At least 10 independent latency samples.**
- **Each sample uses a file path never observed before in the stack** (FP-14,
  §28.9).
- **Every sample is reported.**
- **AC-7 passes only if every sample is at or below 5.0 s.**
- **The interval:**
  - **Start:** the file's OS modification time, which is the `observed_at` the
    companion reports. It is asserted not earlier than the harness's clock
    before the write.
  - **End:** the harness's clock at the first successful read of the object
    through `world-model-engine`'s own `GET /v1/world/objects/{object_id}`, on
    the internal network. It is polled at ≤ 100 ms intervals, which is
    observation, not retry. Independent SQL on `world_model`'s tables is a
    cross-check.
  - **Deadline: 30 s per sample.** A sample over 5.0 s fails the test and
    prints its figure.
- **Writes are made at times uncorrelated with the dispatcher.**
  - The harness never references the cron (N-1).
  - It never retries or discards a sample (N-2).
  - It uses no fake clock (N-3).
- **The chain measured is the unchanged one** (TDD 4F §20.1; D-4F-1). §29.3
  states what it is expected to produce.
- **Never:** lower the threshold, omit a slow sample, reuse a path, or report
  AC-7 as passed without every required sample.

#### A-4F8-7 — the evidence surface. **RATIFIED: option (a)**

> *"Each acceptance criterion's browser-visible clause is demonstrated in a real
> browser. Everything else is demonstrated by real-infrastructure evidence read
> independently of the code under test. No route, subject or prefix is added to
> make a fact browser-visible."*

- **In the browser:**
  - the Level-1 proposal, and the absence of a Level-2 proposal (P-AC8-1);
  - the level selector;
  - the revocation as `failed` (P-AC7-1).
- **By SQL and internal REST:**
  - `autonomy.decision_log`;
  - `action.action`;
  - the capability's effect;
  - the World Model object (§29.4.5).
- **TDD 4F §18's *"Both criteria in a browser"* is clarified additively.** A
  dated note is added there in this change.

#### A-4F8-8 — SAD 15 §4 item 1. **RATIFIED: option (a), restricted to §28.8's surfaces**

- **The exception is granted for exactly these surfaces:**
  - `companion/`;
  - `services/perception-engine/`, including one Alembic migration, for A-4F8-2
    (a1);
  - `infra/docker/`: D3's bindings configuration, and §28.7 (B)'s
    acceptance-only override (§29.2).
- **Recorded, not governed:** `tools/`, `.github/workflows/pr-checks.yml` and
  `apps/web-client/tests/`.
- **Items 2–5 stay mandatory.** Item 5: the PR description cites:
  - Part 11, PERCEPTION SECURITY (l.567–589) and SENSOR HEALTH (l.529–548);
  - Part 14, AUTONOMY LEVELS, Level 2 (l.101–107);
  - Part 12, THE ACTION PRINCIPLE (l.43–93).
- **Any other surface needs a new decision.**

#### §28.7 option (B) — the shared folder. **RATIFIED**

- **The acceptance-stack companion runs under a distinct non-root uid.** So a
  revocation of its watched-folder permission does not also block
  `capability-engine`.
- **It departs from A-4F8-10 (a)'s default**, *"its image's non-root user"*,
  which A-4FP-12 absorbed. This is disclosed here.
- **A-4FP-12's one workspace and one NOVA user are unchanged.**
- **Configuration and verification:** §29.2.

### 29.2 Option (B): configuration, and its verification

**The configuration, planned for 4F.8's acceptance wiring. Nothing is
implemented in this change.**

| Element | Plan |
|---|---|
| The override | A new acceptance-only file, `infra/docker/docker-compose.acceptance.yml`, setting **only** `services.nova-companion.user: "1100:${NOVA_ACCEPTANCE_COMPANION_GID}"` |
| Where it applies | Only the e2e job's acceptance `up` of the P8 services passes `-f infra/docker/docker-compose.local.yml -f infra/docker/docker-compose.acceptance.yml` |
| The gid | `NOVA_ACCEPTANCE_COMPANION_GID=$(id -g)`, the runner's own primary gid |
| The workspace | Unchanged: `mkdir -p` by the runner, mode `0755`. The companion reaches it through the **group** bits. `capability-engine` (uid/gid 1000) reaches it through the **other** bits |
| The revocation | `chmod g-rx` on the workspace root, giving mode `0705`. The harness, as the owner, can still write (E-6) |
| Unchanged | The companion Dockerfile's runtime `USER nova` (uid 1000); `docker-compose.local.yml`; `capability-engine`; and the local-first deployment model in doc 14 §2 |
| A structural guard (D8) | It checks four things. (i) The override sets exactly one key on exactly one service. (ii) Its uid is non-root and is not 1000. (iii) The Dockerfile's `USER` is unchanged. (iv) No other step or compose file uses the override |
| Alternative B1 | `sudo chgrp 1000` on the workspace. The companion, at uid 1100, reaches it through the other bits, and the revocation is `chmod o-rx`. This was verified too, but it needs a privileged step on the runner |

**Runtime verification.** This ran locally in this session, on kernel
`6.18.44`, with the **real** binaries:

- the real `nova-companion` release binary, built from `companion/`, which is
  unchanged since 4F.3. It ran under the scenario's uid via `setpriv`, with a
  clean environment: no `HOME`, and a uid absent from `/etc/passwd`. It
  submitted to a stub intake that records each request;
- `capability-engine`'s real `FilesystemAdapter.invoke("list", …)`, run as uid
  1000;
- an inotify watcher under the companion's uid.

**This is not containers and not CI.** The scenarios:

| # | Arrangement | Before the revocation | After the revocation |
|---|---|---|---|
| A | As merged. The companion and `capability-engine` are both uid 1000. Owner 1001, mode `0755`. Revoked with `chmod 0700` | The companion submits `before.txt`, with `observed_at` equal to its mtime. `capability-engine` lists it | The companion submits nothing and keeps running. **`capability-engine`: `PermissionError` (13)** |
| B1 | Companion uid 1100. The directory's group is 1000. Revoked with `chmod 0750` | As in A | The companion submits nothing and keeps running. **`capability-engine` lists `after.txt` and `before.txt`** |
| B2, **the plan** | Companion uid 1100, with the runner's gid. Owner and group are the runner's, mode `0755`. Revoked with `chmod 0705` | As in A | The companion submits nothing and keeps running. **`capability-engine` lists `after.txt` and `before.txt`** |

In every scenario, the companion's uid received `IN_ATTRIB` on the root at the
moment of revocation. A `stat` of each later file failed with `PermissionError`.

**Static verification.** Compose CLI v5.1.1's `config` was run over
`docker-compose.local.yml`, with and without a scratchpad probe of the
override. **Only `nova-companion.user` differs**, and the companion's mount is
unchanged: `/workspace`, read-only.

**What this verifies:**

- **Isolation.** Under B1 and B2, the revocation removes the companion's access
  and leaves `capability-engine`'s.
- **The companion runs under a non-1000 uid**, with a clean environment, and
  works.
- **A revocation stops its submissions** without crashing it.
- **The kernel delivers the signals D1 needs to the companion's uid**:
  `IN_ATTRIB` on the root, and `EACCES` on `stat`.

**What it does not verify, because it cannot before implementation:**

- **The companion detecting and reporting the loss.** D1 does not exist yet.
  Today the companion drops events silently (F-4F8-15).
- **`perception-engine`'s `failed` transition** (D2).
- **Container and CI behaviour.** Docker is unavailable here.
- **The runner's actual uid and gid.**

These are acceptance checks (§29.5), not assumptions. **Option (B) is
technically sound, and its ratification stands.**

### 29.3 AC-7's latency against the dispatch architecture

**The traced path, at `1ccce7a`:**

| # | Step | Where | Time |
|---|---|---|---|
| 1 | A file write. Its mtime is t₀ | The host | — |
| 2 | inotify reaches the companion, which `stat`s the file and submits | `companion/sensors/src/lib.rs` (`RecommendedWatcher`, no debounce; `observation_from` l.72–102); `nova-companion/src/main.rs` `run()` | ms. Locally, the submission arrived 2–4 ms after the mtime |
| 3 | `POST /v1/perception/workspace-observations`. The handler applies the running gate and the user, computes `object_id`, and calls the debouncer, which admits a first observation at once and drops repeats within 1 s. Then `enqueue_outbox` | `workspace_orchestration.py` l.94–125; `config.py` `workspace_debounce_seconds = 1.0` | ms |
| 4 | **Wait for the next dispatch tick** | The perception worker's `service_cron(…, second={0, 10, 20, 30, 40, 50})` (`workers/__init__.py` l.87). It is **the only caller** of `dispatch_ready_events` in `perception-engine` | **0–10 s** |
| 5 | Publish `perception.workspace.observed` | `nova_service_kit/outbox.py` | ms |
| 6 | `world-model-engine` writes the object **synchronously** in its handler (`observe_object`) | `world-model-engine/events/handlers.py` l.79–110 | ms |
| 7 | The harness reads `GET /v1/world/objects/{object_id}` | A-4F8-6 | ≤ 0.1 s |

**The 10-second cron is on the critical path.** There is no other dispatch path.

**Runtime evidence** comes from 66 real observations in 4F.P's local P8 runs on
2026-10-04/05. Those runs used real `perception-engine`, its worker and
`cognitive-state-engine`, as processes. This is local evidence, not CI.

- **The figure measured** is the delay from the file's mtime to the creation of
  its Active Thought. `cognitive-state-engine` is the first consumer after
  dispatch, so this is a proxy for the World Model's write, which happens on the
  same publish.
- **The delays:** 2.848–9.999 s, with a mean of 9.184 s. **64 of the 66 exceed
  5 s.**
- **Every thought was created 0.133–0.630 s after a 10-second boundary.** So
  dispatch is tick-aligned.
- **Why those delays cluster near 10 s:** the P8 driver writes right after the
  previous tick, so its writes are correlated with the cron.
  - For writes uncorrelated with the cron, as A-4F8-6 requires, a sample is
    roughly uniform on [≈0.2, ≈10.6] s.
  - So P(a sample is ≤ 5 s) ≈ 0.46, and **P(all 10 are ≤ 5 s) ≈ 4 × 10⁻⁴**.

**Conclusion: AC-7 cannot reliably be met with the current dispatch
architecture.** Under the ratified TDD, this is reported, not engineered
around:

- D-4F-1 is RATIFIED;
- TDD 4F §20.1 forbids shortening the cron in order to satisfy AC-7;
- a measured failure is an acceptable 4F.8 output, and a **blocking Gate Review
  finding**.

4F.8 implements and runs the honest measurement either way.

**The smallest compliant architectural change.** It is **not implemented**. It
needs the user to reopen D-4F-1.

- **Scope:** `services/perception-engine/src/nova_perception_engine/workers/__init__.py`
  only.
  1. Run the perception outbox cron every second: `second=set(range(60))`
     instead of `{0, 10, 20, 30, 40, 50}`.
  2. Set `max_jobs = 1` in its `WorkerSettings`, so that dispatch runs never
     overlap.
- **Why (2) is required.**
  - `list_dispatch_ready` takes no row lock: `with_for_update` and `SKIP LOCKED`
    occur 0 times, re-verified at `1ccce7a`. That is why TDD 4F §1.1 (b)
    rejected push-triggered dispatch.
  - arq's default allows concurrent jobs. At a 1-second cadence, a slow run
    could overlap the next and publish a row twice.
  - One serial dispatcher keeps the property §1.1 (b) relies on.
- **Expected latency:** about 1.7 s in the worst case. That is 1 s, plus the
  observed tick phase of ≤ 0.63 s, plus milliseconds. **It is an estimate, to be
  measured.**
- **Kept:**
  - the transactional outbox;
  - at-least-once delivery, durability and replay;
  - ordering;
  - every other engine's cadence.
- **Not proposed:** push-triggered dispatch or a direct publish. TDD 4F §1.1
  rejected both.
- **Risks:**
  - About 10× more dispatch polls for `perception-engine`: one indexed query
    and one Redis cron enqueue per second.
  - A run longer than 1 s delays the next one; it is never duplicated.
  - **It reopens a RATIFIED decision**, D-4F-1, and §20.1's prohibition.
- **Affected tests and documents:**
  - **No existing test pins the perception cadence.** `perception-engine`'s
    tests and `tools/tests` reference none, and `nova-service-kit`'s tests use
    their own values.
  - **New:** one test asserting the cadence and `max_jobs = 1`.
  - **Unaffected:** `perception-engine`'s `real_infra` tests, which call
    `dispatch_ready_events` directly, and
    `tools/tests/test_worker_queue_isolation.py`.
  - **Dated notes needed:** TDD 4F (§1.1, D-4F-1 and §20.1), this TDD, the
    master scope, and `perception-engine`'s README. The 10-second figure appears
    in `infra/docker/docker-compose.local.yml`'s comments and TDD 4F.7 too.
- **If it is not authorized**, AC-7 is measured as ratified, and is expected to
  be **NOT MET**.

> **Authorized 2026-10-11 (§30), additively.** The user reopened D-4F-1 for
> `perception-engine`'s dispatch interval only.
>
> - **§30.2 verified the concurrency model.** The one-second cadence is safe
>   only **with** `max_jobs = 1`, and only under the single-replica deployment.
>   The cadence alone overlapped, and so did two replicas.
> - **§30.3 lists what implementation must prove.**
> - The latency estimate here is not evidence. **AC-7 is met only by measured
>   samples.**

### 29.4 The acceptance plan (F-4F8-13 … F-4F8-16)

#### 29.4.1 Startup sequencing (F-4F8-16)

1. **The stack starts, and the golden path runs**, including
   `cognitive-state-panel.spec.ts`'s unseeded spec. This is unchanged (4F.P C-1).
2. **The P8 services start**, with the acceptance override (§29.2).
3. **Readiness gates**, each a bounded poll with no sleeps:
   - `perception-engine` is healthy;
   - `GET /v1/cognitive-state/sensors` shows `companion-filesystem` as
     `running`. That proves `cognitive-state-engine` is subscribed (K-1);
   - the companion has logged `nova-companion starting`.
4. **4F.P's P8 proof runs, unchanged.**
5. **AC-8's runs** (D6), then P-AC8-1.
6. **AC-7's latency samples** (D5), at **Level 0**.
7. **AC-7's revocation** (D1, D2), then E-5, E-6 and E-18, then P-AC7-1.
8. Teardown.

**P-AC7-1 and P-AC8-1 run in a second Playwright invocation**, after the
services start, and are tagged so that the unseeded spec still runs first. The
unseeded spec is not retargeted.

#### 29.4.2 Attribution (F-4F8-14)

Every run is followed along one chain of keys:

| Key | From |
|---|---|
| `path` | Never observed before (§29.4.4) |
| `object_id` | `perception-engine`'s path hash. The harness restates it, drift-guarded like the P8 guards G9 and G10 |
| The `perception.outbox_event` row | `payload.object_id` |
| `thought_id` | `uuid5(77980e9a-8808-5af9-8e41-2442669868a1, object_id)` |
| The `autonomy.decision.requested` envelope | Tapped. It carries `thought_id`, and has an `event_id` |
| `subject_id` | `uuid5(<the trigger namespace>, event_id)`. It equals `decision_log.subject_id`, `suggestion.id`, `action.execute`'s `action_id` and `action.action.id` |
| `capability.invoke.request` | Tapped |
| `result.entries` | Contain the run's file name |

**Each run asserts exactly one record of each kind for its own keys, and zero
for any other run's keys.** 4F.P's run B suggestion, which exists before AC-8,
is excluded by its `subject_id`.

#### 29.4.3 No cross-contamination (F-4F8-14)

- **The phases are strictly sequential.** None overlaps another.
- **AC-8 runs at Level 1, then at Level 2.** The policies, grants and the
  identity row are read back by SQL before each run, and must be identical
  (E-12).
- **AC-7's samples run at Level 0.** Level 0 is selectable (`SELECTABLE_LEVELS`,
  `domain/models.py` l.93–95), and at Level 0 `decide()` records `observe_only`
  with no suggestion and no dispatch (`domain/decision.py` l.670–690).
  - The harness asserts one `observe_only` row per sample, and zero
    `action.execute` messages and zero `action.action` rows for the samples'
    `subject_id`s.
  - So the samples add nothing to the Autonomy panel (P-AC8-1), and execute
    nothing.
- **The revocation comes last among the steps that need observations.** The
  companion does not recover (a2), and under (B) the revocation no longer blocks
  `capability-engine`.

#### 29.4.4 Never-before-observed paths (FP-14)

- **Every file is named `{phase}-{run_id}-{n}.txt`.** `run_id` is fresh and
  random for each job, as in the P8 driver.
- **Before each write, the harness asserts by `SELECT` only** that its
  `object_id` is absent from `perception.outbox_event` and from the World Model.
- **No path is reused**, within a phase or across phases.

#### 29.4.5 Evidence sources, per criterion clause

| Clause | E-items | Source |
|---|---|---|
| AC-7 *"a known project"* | E-2 | SQL: `perception.outbox_event.payload.project_id`, one match and one miss |
| AC-7 *"detected by a `nova-companion` sensor"* | E-1 | SQL: the outbox row's `sensor_id = companion-filesystem`. The companion's log |
| AC-7 *"without user action"* | E-4 | A structural (AST) check of the harness |
| AC-7 *"reflected in the World Model"* | E-1 | `world-model-engine`'s REST, plus SQL. `correlation_id` provenance |
| AC-7 *"within five seconds"* | E-3 | The harness's figures: every sample, all ≤ 5.0 s, or the test fails |
| AC-7 *"revoking … OS-level permission"* | E-5, E-18 | The `chmod g-rx`. The companion's report on the internal route. SQL: `perception.sensor.health_changed{failed}` |
| AC-7 *"stops the perception stream"* | E-6 | SQL: no outbox row. REST: no World Model object for a new path, for ≥ 25 s |
| AC-7 *"visibly … in the panel"* | E-5, P-AC7-1 | The browser, plus `GET /v1/cognitive-state/sensors` |
| AC-8 *"the same action category"* | E-10, E-12 | SQL: `autonomy.decision_log` and the autonomy configuration tables |
| AC-8 *"blocked at Level 1"* | E-8, P-AC8-1 | SQL: `PROPOSE` plus a suggestion, and no `action.action` row. The browser |
| AC-8 *"auto-executes at Level 2"* | E-9, E-13, E-14, E-17 | SQL: `EXECUTE`, and `action.action.status = completed` with the run's `entries`. An AST check. The denial control |
| AC-8 *"for a low-risk case"* | E-11 | SQL: `action.action.risk = negligible`, and T1's authored `low` |
| AC-8 *"purely by policy"* | E-12 | SQL read-backs before each run |
| AC-8 *"no code path differs"* | E-10 | SQL, plus the X-8 unit control |

#### 29.4.6 A new item, E-18, and a new control, N-16

- **E-18: the revocation is specific to the sensor.** After the revocation,
  inside the real containers:
  - `docker compose exec -T nova-companion ls /workspace` fails with permission
    denied;
  - `docker compose exec -T capability-engine ls /workspace` succeeds.

  This is a read-only OS inspection, disclosed as infrastructure evidence. It is
  not a production route.
- **N-16:** drop the override, so the companion runs as uid 1000. E-18 must then
  fail, because `capability-engine` is denied too.

  ***Corrected 2026-10-12, additively (§39.4):*** the bullet above is preserved
  as written. In CI, E-18 failed under N-16 because the companion was **not
  denied at all**. `capability-engine` kept its access.

### 29.5 Acceptance checks carried into implementation, not assumed

1. **D1's Cargo tier.** A real directory and a real `chmod`. The companion must
   detect the loss, through the root's `IN_ATTRIB` and `EACCES` before a
   submission, and call the internal route. This also establishes F-4F8-7 on the
   CI kernel.
2. **D2's `real_infra` tier.** A report moves the sensor to `failed`, writes one
   outbox row, and makes a later observation be dropped.
3. **E-5, E-6 and E-18** in CI's containers, under the override.
4. **The runner's gid**, used by B2, or `sudo` for B1.
5. **AC-7's measured figures.** They are expected to fail unless D-4F-1 is
   reopened (§29.3).

### 29.6 Status after ratification

- **RATIFIED 2026-10-11:** A-4F8-1, -2, -4, -6, -7 and -8, and §28.7 (B).
  - A-4F8-3 and A-4F8-5 are answered by 4F.P.
  - A-4F8-10 is absorbed.
  - **A-4F8-9 is not ratified**, and still blocks 4F's GO.
- **§22:**
  - steps 1, 2 and 3 are done;
  - **step 4, the user's explicit GO to cut the implementation branch, is
    outstanding.**
- **One decision affects 4F.8's scope:** whether to reopen D-4F-1 for §29.3's
  perception-only change.
  - The TDD does not require it before implementation, because a measured
    failure is an acceptable 4F.8 output.
  - But without it, AC-7 is expected to be NOT MET.
- **Open, and unchanged:**
  - CF-9, CF-10 and CF-11;
  - C-7's carried finding, F-4FP-7;
  - FP-24, as L-23;
  - F-4FP-3 … F-4FP-10, including F-4FP-6;
  - L-24 … L-28;
  - L-1 … L-6, L-8 … L-11 and L-13 … L-22.
- **AC-7 and AC-8: NOT MET, and not claimed.**
- **No implementation branch exists.** This change is documentation only.

---

## 30. D-4F-1 reopened for `perception-engine`'s dispatch interval — 2026-10-11

**Added 2026-10-11, additively** (protocol §0.3.4). §0–§29 are preserved as
written. **Where §30 and an earlier section differ, §30 governs.**

### 30.0 The user's decision

**Verbatim:**

> *"I approve reopening D-4F-1, strictly and exclusively to enable the
> perception-engine dispatch path to satisfy AC-7's existing 5-second latency
> requirement."*

**The constraints given with it:**

- reopen D-4F-1 only for `perception-engine`'s outbox dispatch interval;
- keep AC-7's threshold of at most 5.0 s;
- keep the transactional outbox design, and every unrelated service schedule;
- change no other engine, no retry semantics, no event contract and no
  unrelated behaviour;
- treat the one-second interval and `max_jobs = 1` as the initial approach,
  subject to verifying the worker's scheduling and its safety against
  duplicate dispatch;
- never mark AC-7 met on an estimate.

### 30.1 The exception, as ratified. **RATIFIED 2026-10-11**

- **Scope:** `perception-engine`'s outbox dispatch interval only, plus the
  serial-dispatch setting that interval requires.
  - Both live in
    `services/perception-engine/src/nova_perception_engine/workers/__init__.py`.
  - This is inside A-4F8-8's governed surface, `services/perception-engine/`.
- **The initial approach:**
  - `second=set(range(60))`, replacing `{0, 10, 20, 30, 40, 50}`;
  - `max_jobs = 1` in `perception-engine`'s `WorkerSettings`.
  - It is subject to §30.2's verification, and to §30.3's tests during
    implementation.
- **Unchanged:**
  - **AC-7's threshold, at most 5.0 s**, and A-4F8-6's measurement rule;
  - **the transactional outbox**: `enqueue_outbox`,
    `nova_service_kit.dispatch_ready_events`, publish-then-mark,
    `event_id = row id`, and at-least-once delivery;
  - **every other engine's schedule**, and every other worker;
  - **retry semantics, event contracts and subjects**;
  - **the exclusions of push-triggered dispatch and of a direct publish** (TDD 4F
    §1.1);
  - **every other prohibition in TDD 4F §20.1**: no aligning to the cron, no
    retry or re-run, no fake clock, and no injected message.
- **AC-7 is not met on an estimate.** It is met only by A-4F8-6's measured
  samples: at least 10, each on a never-before-observed path, all reported, and
  all ≤ 5.0 s.
- **The evidence that motivated it** (§29.3), with its limitations:
  - **66 real observations, of which 64 exceeded 5 s.** The mean delay was
    **9.184 s (≈ 9.2 s)**, the range 2.848–9.999 s.
  - Every dispatch was tick-aligned, landing 0.133–0.630 s after a 10-second
    boundary.
  - **Limitations:**
    - These were 4F.P's local P8 runs, on 2026-10-04/05: real
      `perception-engine`, its worker and `cognitive-state-engine` as
      processes. **They are not CI evidence.**
    - The delay was measured to the Active Thought's creation, which is a
      proxy for the World Model write on the same publish.
    - The P8 driver writes right after a tick, so its samples are correlated
      with the cron.
- **What it amends**, each by a dated note in this change:
  - D-4F-1 (TDD 4F §19, and §1.1's row 1.1), for `perception-engine`'s dispatch
    interval only;
  - TDD 4F §20.1's *"the existing 10-second cron dispatcher (unchanged)"* and
    *"shortening the cron … in order to satisfy this criterion"*, for
    `perception-engine` only;
  - this TDD's §2 non-goal row 2;
  - §29.3's *"not implemented"*, which now reads as authorized for
    implementation.

### 30.2 The concurrency model, verified before implementation

**The scheduler.** arq is pinned at **0.28.0** in `uv.lock`. From its installed
source:

- **A worker starts a job only while `job_counter < max_jobs`**, and it
  decrements the counter only when the job's task completes (`arq/worker.py`
  l.389 and l.436–475). With `max_jobs = 1`, at most one job runs at a time
  within one worker process.
- **Each cron tick is enqueued under its own job id**, `name:timestamp`
  (`run_cron`, l.736–771).
- **An in-progress key** stops two workers from running the *same* tick
  (l.450–471). **It does not stop two workers from running *different* ticks at
  the same time.**

**The outbox.**

- **`list_dispatch_ready` is a plain `SELECT … WHERE dispatched_at IS NULL ORDER
  BY created_at LIMIT n`.** It takes no lock, and claims no row
  (`postgres_perception_repository.py` l.237–256). No `with_for_update` or `SKIP
  LOCKED` appears in `perception-engine`'s source or in `nova-service-kit`.
- **`dispatch_ready_events` publishes each row, then marks it**
  (`nova_service_kit/outbox.py` l.96–107).
- **So two concurrent runs can publish the same row twice.**

**The deployment.**

- **`docker-compose.local.yml` defines exactly one `perception-engine-worker`**,
  running `arq nova_perception_engine.workers.WorkerSettings`. It has no
  `replicas` or `scale` anywhere, and the e2e job starts one.
- **`perception-engine`'s API process runs no arq worker.**
- **Its `WorkerSettings` has only this cron** (`functions = []`), so
  `max_jobs = 1` starves no other job.

**Experiment.** Real arq 0.28.0 workers ran against a real local Redis 7.0.15,
using the repository's own `service_cron` and `worker_queue_name`, with a
per-second cron. The job stood in for `arq_run_outbox_dispatch`. **This is local
evidence, not CI.**

| Scenario | Runs | Max concurrent | Overlapping pairs |
|---|---|---|---|
| A 2.5-s job, the default `max_jobs` (10), one worker | 11, one starting every 1.0 s | **3** | 19 |
| A 2.5-s job, **`max_jobs = 1`**, one worker | 4. Later ticks queued, then ran serially | **1** | **0** |
| A 2.5-s job, `max_jobs = 1`, **two worker replicas** | 8 | **2** | 7 |
| A 0.05-s job, `max_jobs = 1`, one worker | 13, one starting every ≈ 1.0 s | 1 | 0 |

**The four questions, answered:**

1. **Can a previous run still be running when the next starts?**
   - **Yes, with the default `max_jobs`.** It was demonstrated, with three
     concurrent runs.
   - **No, with `max_jobs = 1` in one worker.** Later ticks queue, and run
     serially.
2. **Can several replicas dispatch the same row?**
   - **Yes.** Two replicas with `max_jobs = 1` each still overlapped, and
     `list_dispatch_ready` claims nothing.
   - This is equally true of today's 10-second cron. It is only less likely,
     because a run must outlast 10 s.
   - **The supported deployment has exactly one replica.**
3. **Does the code claim or lock rows?** **No.**
4. **Is a minimal perception-only configuration sufficient?** **Yes, for the
   supported single-replica deployment**, provided that:
   - the per-second cadence comes **with** `max_jobs = 1`. **The cadence alone
     is unsafe**, as demonstrated;
   - **a perception-only structural guard** enforces the single replica: compose
     defines exactly one `perception-engine-worker`, with no `replicas` or
     `scale`.

   **Making several replicas safe would need row claiming in
   `nova_service_kit`'s shared outbox**. At `1ccce7a`, ten engines import its
   `dispatch_ready_events`. That is an outbox redesign outside this exception.
   **It is not proposed.**

**Residuals, unchanged by the cadence:**

- **At-least-once delivery.** A crash, a shutdown, or arq's 300 s job timeout
  between a publish and its mark republishes that row on the next run, with the
  same `event_id`. This is today's semantics.
- **A backlog.** If a run outlasts 1 s, later ticks queue, one per second, and
  run serially. Each is a single indexed `SELECT` once the outbox is drained.

### 30.3 What implementation must prove, in addition to §29.5

1. **A structural test:**
   - `perception-engine`'s `WorkerSettings` dispatches every second, with
     `max_jobs == 1`;
   - compose defines exactly one `perception-engine-worker`, with no `replicas`
     or `scale`;
   - **every other engine's `WorkerSettings` cron schedule is unchanged** from
     `1ccce7a`.
2. **A real test: no overlap and no duplicate.** It runs the actual
   `perception-engine` `WorkerSettings` schedule and `max_jobs`, in an arq
   worker against real Redis, with the real dispatch coroutine against real
   PostgreSQL and NATS.
   - It seeds enough real outbox rows that one dispatch run **naturally** outlasts
     the 1-second interval. Nothing is mocked or slowed.
   - It subscribes on the real bus, and asserts that **every `event_id` is
     delivered exactly once** and that **no two dispatch runs overlap**.
3. **That test's negative control:** remove `max_jobs = 1`. The test must then
   fail.
4. **AC-7 measured in the acceptance stack in CI**, by A-4F8-6's rule. **AC-7 is
   met only if every one of at least 10 samples is ≤ 5.0 s.**
5. **Documentation, as dated notes:**
   - `perception-engine`'s README, for the worker cadence;
   - the compose comment on `perception-engine-worker`, if it states the
     cadence;
   - the TDD and master-scope notes already added in this change.

### 30.4 Status

- **D-4F-1 is reopened for `perception-engine`'s dispatch interval only.** The
  approach is verified safe under the supported single-replica deployment. **It
  is not implemented.**
- **The user authorized cutting the 4F.8 implementation branch** from `phase-4`
  at `1ccce7a`, after this record (§22 step 4). The branch follows the
  `phase-4f6`, `phase-4f7` and `phase-4fp` convention: **`phase-4f8`**.
- **Unchanged:**
  - A-4F8-9 still blocks 4F's GO;
  - CF-9, CF-10 and CF-11, and every carried open finding and ledger row, stay
    OPEN;
  - **AC-7 and AC-8 are not met, and not claimed.**

---

## 31. Implementation record — the D-4F-1 dispatch change — 2026-10-11

**Added 2026-10-11, additively** (protocol §0.3.4), on the implementation branch
`phase-4f8`. §30 is preserved as written. Its *"It is not implemented"* (§30.4)
is historical from this commit on.

### 31.1 What changed

- **`services/perception-engine/src/nova_perception_engine/workers/__init__.py`.**
  `WorkerSettings` sets `max_jobs = 1`, and its one cron job runs on
  `second=set(range(60))` instead of `{0, 10, 20, 30, 40, 50}`. Nothing else in
  the module changed. The comments state why, and the single-replica limit.
- **`infra/docker/docker-compose.local.yml`.** A comment on
  `perception-engine-worker`, stating the single-replica constraint. No
  service, command or setting changed.
- **`services/perception-engine/README.md`.** A new *"Outbox dispatch"*
  section.
- **No other engine, worker, contract, migration, subject or workflow
  changed.** The dispatch coroutine, `nova_service_kit.dispatch_ready_events`,
  the 100-row batch, publish-then-mark and `event_id = row id` are unchanged.

### 31.2 The tests, against §30.3

| §30.3 item | Test |
|---|---|
| 1. Structural | `tools/tests/test_perception_dispatch_cadence.py`, 16 tests: every second; `max_jobs == 1`; exactly one compose service runs the worker, in any `docker-compose*.yml`; no `scale` or `replicas` above 1; no workflow uses `--scale`; the API image runs no worker; every other engine's cron schedule equals its `1ccce7a` value, with no tuning field |
| 1. Through arq | `services/perception-engine/tests/unit/test_worker_settings.py`, 3 tests: arq's own `CronJob.calculate_next` fires every second across a minute boundary, and `get_kwargs(WorkerSettings)` gives `max_jobs == 1` |
| 2. No overlap, no duplicate | `services/perception-engine/tests/integration/test_outbox_dispatch_cadence_real_infra.py`: a drain test and a stall test, `real_infra` |
| 3. Negative control | The same file's control test, plus the manual source reverts below |
| 4. AC-7 measured | **Not yet.** D5 (§29.5) |
| 5. Documentation | §31.1 |

### 31.3 One correction to §30.3 item 2, and why

§30.3 item 2 says the real test *"seeds enough real outbox rows that one dispatch
run **naturally** outlasts the 1-second interval. Nothing is mocked or
slowed."* **The first half cannot be done.**

- **`arq_run_outbox_dispatch` reads at most 100 rows a run**
  (`DEFAULT_BATCH_SIZE`). More rows only make more runs.
- **A full 100-row run took 0.247–0.286 s** in five trials. The trials used the
  real repository and a real `NatsEventBus`, against local PostgreSQL 16 and
  nats-server.

**What the test does instead.** A concurrent transaction holds `SHARE` on
`perception.outbox_event`. That is the lock a non-concurrent `CREATE INDEX`
takes: reads proceed, and every `UPDATE` waits.

1. The first run selects its batch and publishes its first row.
2. Its `mark_dispatched` then waits on that lock until the test releases it.
3. **The dispatcher is not mocked, patched or delayed.** The long run comes from
   a real database condition, which a production migration can produce.

**The second half of the sentence holds:** nothing is mocked. This is a
test-construction correction, and changes no behaviour.

### 31.4 Evidence (local; not CI)

**Environment.** No Docker daemon (`docker info` fails). PostgreSQL 16, Redis
and nats-server ran as local processes. A scratchpad-only pytest plugin pointed
`nova-testkit`'s container fixtures at them. **This is local evidence, not CI
evidence.**

**The real runs**, measured from arq's own job hooks and a real NATS
subscription:

| Test | Runs | Overlapping pairs | Delivered | Duplicated `event_id`s |
|---|---|---|---|---|
| Drain, 350 rows, `max_jobs = 1` | 7, with ticks exactly 1.000 s apart | **0** | 350 of 350 | **0** |
| Stall, 150 rows, `max_jobs = 1` | 8. The first lasted 3.227 s; the three ticks that came due during it started at +3.508, +4.008 and +4.511 s, after it ended | **0** | 150 of 150 | **0** |
| Control: the same stall, `max_jobs = 10` (arq's default) | 8, the first four alive at once | **10** | 466 deliveries for 150 rows | **100**, up to 5 copies |

**Negative controls**, each a temporary source change, reverted afterwards:

| Removed | Result |
|---|---|
| `max_jobs = 1` | The stall test **failed**: ticks started while the stalled run was alive. The structural and unit tests **failed** |
| The one-second cadence, back to 10 s | The structural cadence test and the arq unit test **failed** |
| `memory-engine`'s outbox moved to every second | `test_other_engines_schedules_are_unchanged[memory-engine]` **failed** |
| `deploy: replicas: 2` on `perception-engine-worker` | `test_no_compose_file_replicates_the_perception_worker` **failed** |
| A second compose service running the worker | `test_compose_defines_exactly_one_perception_worker` **failed** |

**Flakiness.** The real-infra file ran **10 times: 10 × 3 passed**, 24.4–26.0 s
each.

### 31.5 Status

- **The dispatch change is implemented and tested locally.** CI evidence is
  pending: `pr-checks` and `real-infra-checks`, whose matrix includes
  `perception-engine`.
- **Multi-replica dispatch is not safe, and not claimed.** It stays outside the
  exception (§30.2).
- **AC-7 is not met, and not claimed.** It is met only by D5's measured samples.
- **AC-8 is not met, and not claimed.** A-4F8-9, CF-9, CF-10 and CF-11 stay OPEN.

---

## 32. Implementation record — D1 and D2 — 2026-10-11

**Added 2026-10-11, additively**, on `phase-4f8`. It records A-4F8-1 (a), (a1)
and (a2) as built. §29.1 governs what they mean.

### 32.1 D1 — `nova-companion` (commit `6ba6f27`)

- **Detection** (`companion/sensors/src/lib.rs`):
  - `check_access(root)` checks read permission (`read_dir`) and search
    permission (resolving `root/.`).
  - `access_lost` reduces it to `PermissionDenied` only. A vanished root or
    another I/O failure is not reported as a revocation.
  - `next_event()` replaces `next_batch()`. It re-checks the root on the root's
    own `IN_ATTRIB` and before every observation is emitted. A denial surfaces
    as `SensorEvent::AccessLost`, which replaces F-4F8-15's silent drop.
- **Reporting** (`nova-companion/src/main.rs`, `intake.rs`):
  - `permission_revoked` is logged once.
  - The loss is reported on `POST /v1/perception/permission-revocations`, with
    body `{"detected_at": …}` and no path or identity.
  - It is checked again before each submission.
  - An unacknowledged report is resent on the next event.
  - After a loss nothing is submitted, for the life of the process (a2).
- **The workspace-observation contract is unchanged.**

### 32.2 D2 — `perception-engine`

- **`SensorErrorReport.kind`** is an additive field, `"error"` or
  `"permission_revoked"`, with `"error"` as the default. The model is internal:
  it is not persisted, and it is not a contract.
- **`FilesystemSensor.report_error`** moves `running → failed` only for
  `permission_revoked`, and `permission_status().granted` becomes `False`. Any
  other error is recorded and changes nothing, as before.
- **The one internal route**, `api/permission_revocations.py`:
  - `POST /v1/perception/permission-revocations?source=filesystem`, with an
    `extra="forbid"` body `{detected_at}`;
  - only the `filesystem` source is accepted, and any other is 404;
  - it calls `sensor_lifecycle.report_sensor_error`, which publishes `failed`
    on `perception.sensor.health_changed` through the outbox;
  - a repeat returns `transitioned: false` and publishes nothing.
- **Unchanged:** the subjects, `PUBLIC_TOPICS`, every gateway prefix,
  `api/consent.py` and the workspace route.
- **N-8 is structural.** `tests/unit/test_revocation_is_the_only_failed_path.py`
  checks two things:
  - the sensor's only `fail` transition is inside `report_error`, under
    `kind == "permission_revoked"`;
  - only the route builds that kind.

### 32.3 Evidence (local; not CI)

**Environment.** No Docker daemon; local PostgreSQL 16, Redis and nats-server.
The tests that change permissions **ran as uid 1100** via `setpriv`, because root
bypasses permission checks. **As root, they fail loudly** with that explanation;
this was observed.

| Tier | Tests | Result |
|---|---|---|
| Cargo, `sensors/tests/revocation.rs` | 4: the root's own `IN_ATTRIB` reported; a change after the revocation reported, never observed or dropped; a `chmod` that keeps access not reported; read and search both checked | **4 passed**. Events keep arriving after the `chmod`: F-4F8-7 is established on kernel 6.18.44 |
| Cargo, `nova-companion/tests/revocation.rs` | 4: the report's wire shape; 404 and 503 as distinct outcomes; the real binary reports once and submits nothing after; an unacknowledged report is resent on the next event | **4 passed** |
| Cargo, the existing suites | Unit 9, `intake_client` 10, `real_filesystem` 8, `watch_error_redaction` 6 | **33 passed** |
| `perception-engine` unit and API | `test_filesystem_sensor.py` (+4), `test_sensor_lifecycle.py` (+1), `test_revocation_is_the_only_failed_path.py` (2), `test_api_permission_revocations.py` (8) | All pass. The full suite: **226 passed**, 26 deselected, domain coverage 99% |
| `perception-engine` `real_infra` | `test_permission_revocation_real_infra.py`: the real companion binary, a real `chmod`, real uvicorn, real PostgreSQL and the real dispatcher to real NATS. It checks `failed`, exactly one committed `failed` row delivered over NATS, a write the OS accepted producing no row, and the engine's own gate dropping a direct post | **1 passed.** All 26 `real_infra` tests pass as uid 1100 |

**Negative controls**, each a temporary source change, reverted afterwards:

| Mutation | Failed |
|---|---|
| The sensor's access check removed | 3 Cargo tests, in both revocation files |
| The binary never reports | The 2 real-process Cargo tests |
| A revocation does not fail the sensor | Unit tests, and the real-infra test |
| The route does not transition (N-5) | The route tests, and the real-infra test |
| No `running` gate (N-6) | `test_a_sensor_that_is_not_running_publishes_nothing`, `test_every_later_observation_is_dropped`, and the real-infra test's direct post |

**Flakiness:**
- the two Cargo revocation binaries and `real_filesystem`: **10 of 10** each;
- the D2 real-infra test: **10 of 10**.

**One correction, additively.** Commit `6ba6f27`'s message says *"the 24
existing ones pass"*. The existing companion tests number **33**, as above, and
all 33 pass. The message cannot be amended, so this records it.

### 32.4 What this does not show

- **Container or CI behaviour.** Docker is unavailable here. CI's `cargo test`
  runs as the runner's own user, and `real-infra-checks` is non-blocking.
- **E-5, E-6 and E-18 in the acceptance stack**, under §29.2's override. That
  is D4/D5's sequence.
- **AC-7 and AC-8 are not met, and not claimed.**

---

## 33. Implementation record — D3 — 2026-10-11

**Added 2026-10-11, additively**, on `phase-4f8`. It records A-4F8-2 (a), (a1)
and (a2) as built, and settles ledger row **L-13** once merged.

### 33.1 What changed (`perception-engine`, `infra/docker`)

- **The operator's declaration:** `Settings.project_folder_bindings`, JSON from
  `PERCEPTION_ENGINE_PROJECT_FOLDER_BINDINGS`.
  - It maps absolute folders to project UUIDs. Relative paths and `/` are
    refused.
  - It is **empty by default**.
  - Compose passes it through from `NOVA_PROJECT_FOLDER_BINDINGS`, defaulting to
    `{}`.
- **The match:** `domain/workspace.py::bound_project_for_path`.
  - The nearest declared ancestor folder wins, compared by whole path segments.
  - A miss returns `None`.
  - It replaces `resolve_project_id(object_id, known)`, whose table had no
    population path (F-4F8-5).
- **The activation**, in `workspace_orchestration.py::_known_project_for`. A
  bound project counts only if `repository.is_project_known(project_id)`, one
  primary-key read.
- **The learning:**
  - `memory.long_term.created` is added to `SUBSCRIBABLE_SUBJECTS` and
    subscribed in the lifespan.
  - `events/handlers.py::make_known_project_handler` records a `project_id` of
    `primary_user_id`'s memories, and ignores everything else.
  - **Not read:** the memory's content, type or privacy level.
- **The store (a1):** migration `0002_known_project.py` creates
  `perception.known_project` (`project_id` PK, `first_observed_at`,
  `source_event_id`). It holds current state only, and is written with
  `ON CONFLICT DO NOTHING`.
- **Unchanged:** `world-model-engine` (a2), `memory-engine`, the registry
  (120), `PUBLIC_TOPICS` (18), the gateway prefixes, and the published
  payload's shape.

### 33.2 Evidence (local; not CI)

| Tier | Tests | Result |
|---|---|---|
| Unit | `test_workspace.py` (the match, rewritten for folders: 5); `test_workspace_orchestration.py` (known, inert and miss: 3 new); `test_known_projects.py` (12: subscription, handler, defaults, validation) | The suite: **242 passed**, 28 deselected |
| `real_infra` | `test_known_project_real_infra.py` (2). A real `memory.long_term.created` from a producer bound as `memory-engine` (control 7), over real NATS, reaches the real app's lifespan subscription. Real PostgreSQL, and the real companion binary writing under a declared, an inert and an undeclared folder | **2 passed**. Match: `project_id = KNOWN`. Inert: `None`. Miss: `None`. One row, recording the first event |

**Negative controls**, each reverted afterwards:

| Mutation | Failed |
|---|---|
| A declared folder counts without its project being known | `test_a_declared_folder_of_a_project_never_seen_is_inert`, and the real-infra match test |
| A miss guesses a project (N-13) | 4 unit tests, and the real-infra match test |
| No subscription | Both real-infra tests. **Only this tier catches it**, because the unit tiers do not run the lifespan |

**Flakiness:** the real-infra file passed **10 of 10**.

**`docker compose … config`:** valid. The default resolves to `'{}'`.

### 33.3 What this does not show

- **E-2 in the acceptance stack.** The project must become known there through
  `memory-engine`'s production `POST /v1/memories`, and that is D5's harness.
- **AC-7 and AC-8 are not met, and not claimed.**

---

## 34. Implementation record — the acceptance-only override (§28.7 (B), §29.2) — 2026-10-11

**Added 2026-10-11, additively**, on `phase-4f8`. It records §29.2's plan as
built.

### 34.1 What changed

- **`infra/docker/docker-compose.acceptance.yml`** sets exactly one key:
  `services.nova-companion.user: "1100:${NOVA_ACCEPTANCE_COMPANION_GID:?…}"`.
  - It refuses to interpolate without the gid.
  - `docker compose config` of the base file plus the override differs from the
    base alone **by that one line only**.
- **`pr-checks.yml`.** *"Start the P8 services"* sets
  `NOVA_ACCEPTANCE_COMPANION_GID="$(id -g)"`, exports it to `$GITHUB_ENV`, and
  passes both files. **No other step uses the override.** `logs` and `exec` act
  on the running containers, whose user is already set.
- **Unchanged:**
  - the companion `Dockerfile` (`useradd --uid 1000 nova`, `USER nova`);
  - `docker-compose.local.yml`, which gives the companion no `user:`;
  - `capability-engine`;
  - the workspace provisioning (`mkdir -p`, mode 0755, owned by the runner);
  - doc 14 §2's local-first model.
- **The structural guard (D8):** `tools/tests/test_acceptance_override.py`, 6
  tests, pinning §29.2's four properties:
  1. one key on one service;
  2. a non-root uid, other than `capability-engine`'s 1000;
  3. the companion image's user unchanged, and no `user:` in the base compose;
  4. exactly one workflow step applies the override, deriving the gid from the
     runner, and no compose file or script elsewhere names it.

### 34.2 Evidence (local; not containers and not CI)

**The guard's negative controls**, each reverted afterwards. Each of these
failed its named test:
- a second key;
- uid 1000;
- uid 0;
- `user:` in the base compose;
- a second step applying the override.

**Runtime.** This used the **real D1 companion** (the debug binary from this
branch) under `setpriv`, and the **real `perception-engine`** under uvicorn, with
real PostgreSQL and the in-memory bus. It also used `capability-engine`'s
**real** `FilesystemAdapter.invoke("list")` as uid 1000. The workspace was owned
by 1001:1001, mode 0755, and revoked with `chmod g-rx` to 0705.

| | B2: the companion as 1100:1001 (the plan) | N-16's analogue: the override dropped, the companion as 1000:1000 |
|---|---|---|
| The engine's filesystem sensor after the revocation | **`failed`** | `running` |
| The companion's own `ls` of the workspace (E-18) | **denied** | allowed |
| `capability-engine`'s `list` after the revocation (E-18) | **`after.txt`, `before.txt`** | `after.txt`, `before.txt` |
| The companion's logs | `permission_revoked`, `revocation_reported` | none |
| A file written after the revocation, submitted? | **no** | yes |

So under the override the revocation is **specific to the sensor**. Without it,
E-18's companion half fails: the companion is not revoked at all, as N-16
predicts.

### 34.3 What this does not show

- **Container and CI behaviour.** It does not show the runner's actual gid,
  Docker's handling of a uid absent from the image's `/etc/passwd`, or
  `docker compose exec` in CI (§29.5 items 3 and 4). These are E-5, E-6, E-18
  and N-16 in the acceptance run.
- **AC-7 and AC-8 are not met, and not claimed.**

---

## 35. Implementation record — the acceptance harness (D5, D6, D7, D8) — 2026-10-11

**Added 2026-10-11, additively**, on `phase-4f8`. It records D5–D8 as built,
two sequencing details §29.4 left to D7, and one new finding.

### 35.1 What changed

**`tools/e2e_acceptance.py`.** It has three phases, each its own `e2e` step.
It reuses P8's passive `Tap`, `Stores`, `real_run`, `configure` and
`check_executed`, rather than restating them.

- **`ac8` (D6).** It re-applies P8's configuration through the production
  routes, then:
  1. **Level 1** from a never-observed path. E-8: `propose`, one `proposed`
     suggestion whose title names the file, no `action.execute`, and no
     `action.action` row.
  2. **Level 2** from another path. E-12: before it, the configuration is read
     back by SQL and must be identical except the level. E-9: P8's full
     executed-run checks, including `completed`, the listing and exactly one
     invocation.
  3. **E-10**: the two decision rows have identical `policy_checks`, `risk` and
     `confidence`. Only the outcome and the level differ, and the two triggers
     carry the same T1 category, action type and authored risk.
  4. **E-11**: authored `low`, and `negligible` in `action-engine`.
  5. **E-13**: each decision's subject is `uuid5` of the trigger
     `cognitive-state-engine` published.
  6. **E-17**: the identity row is removed, then a third path. The real stage 3
     denies, the outcome is `propose`, and nothing is invoked. The row is
     restored.
- **`ac7-latency` (D5).** It runs at Level 0.
  1. **Readiness (K-1).** `cognitive-state-engine` holds `companion-filesystem`
     as `running`.
  2. **The project is made known** through `memory-engine`'s own
     `POST /v1/memories`. The harness then waits for `perception.known_project`.
  3. **E-2's miss:** a path at the workspace root carries `project_id = None`.
  4. **≥ 10 samples, each on a never-observed path in the declared folder**, so
     each is also E-2's match. Every sample:
     - is asserted absent first (FP-14);
     - is preceded by a pause drawn from the OS's entropy (N-1);
     - runs from the file's OS mtime to the first `200` from
       `world-model-engine`'s `GET /v1/world/objects/{id}`, polled every 50 ms,
       with a 30 s deadline.
  5. **Per sample, after measuring:**
     - E-1: one observation from `companion-filesystem`;
     - N-3: `observed_at` equals the OS time, and is not before the write;
     - E-2: the known `project_id`;
     - E-1 provenance: the World Model transition's `correlation_id` equals the
       outbox row's;
     - §29.4.3: exactly one `observe_only` row, no suggestion, no
       `action.execute`, and no action row.
  6. **E-3.** It passes only if every sample was observed and is ≤ 5.0 s. Every
     figure is printed either way.
- **`ac7-revocation` (E-5, E-6, E-18).** It runs after P-AC7-1 has revoked.
  1. **The workspace mode:** the group bits are withdrawn, and the owner's are
     intact.
  2. **E-5:**
     - the companion's logs show `permission_revoked` and `revocation_reported`
       once each;
     - `perception-engine` holds `failed`;
     - exactly one `failed` report was dispatched;
     - `cognitive_state.sensor_state` holds it, by `last_event_id`.
  3. **E-18:**
     - `docker compose exec nova-companion id -u` is `1100`, and its `ls` is
       denied;
     - `capability-engine`'s `ls` succeeds.
  4. **E-6:** a write the OS accepted produces no outbox row, no World Model
     object and no submission for 25 s.

**The specs (D7):**
- `acceptance-ac8.spec.ts` (P-AC8-1): the gateway serves the Level-1 subject
  and not the Level-2 one. The panel shows Level 2. The Level-1 run is
  `proposed`, `low` and approvable. No row carries the Level-2 file. Nothing is
  approved.
- `acceptance-ac7.spec.ts` (P-AC7-1): `running`, then the genuine `chmod g-rx`
  (by the owner), then `failed` with *"last reported"* after Refresh. The panel
  equals the gateway both times.
- **Both** skip without their inputs, so they never run inside the golden path,
  and both set `retries: 0`.

**`pr-checks.yml`:**
- *"Declare the AC-7 known project"*, before the P8 services start. It creates
  `ac7-known-<run>` in the workspace and exports `NOVA_PROJECT_FOLDER_BINDINGS`
  and the run's inputs.
- **Five steps after P8**, in §29.4.1's order:
  1. AC-8;
  2. P-AC8-1;
  3. AC-7 latency;
  4. P-AC7-1;
  5. AC-7 revocation.
- **Each step** runs whatever came before (`!cancelled()`), and fails the job
  when it fails.
- **The two Playwright runs** override the reporter, so the golden path's
  report files are kept.

**`tools/tests/test_e2e_acceptance.py` (D8), 29 tests:**
- E-13 / N-4: no engine import, publish, request, `promote_thought` or
  `decide`;
- `SELECT`-only SQL;
- declared routes only;
- N-1: no schedule reference, and no modulo;
- N-2: one call site, no `continue` or `break`, every result kept;
- N-3: no fake clock, and `observed_at` checked against the OS time;
- E-4: the sample function only reads;
- the ratified figures;
- the restated path hash equals `perception-engine`'s;
- the step order, `!cancelled()`, no `continue-on-error`, `retries: 0`, and no
  acceptance input on the golden-path step.

### 35.2 Two sequencing details, within D7 (A-4F8-7; F-4F8-16)

1. **P-AC8-1 and P-AC7-1 run in two later Playwright invocations, not one.**
   - Both still run after the P8 services start, and after the golden path's
     own invocation.
   - P-AC8-1 runs right after AC-8, while the level is still 2 (§29.4.1
     step 5).
   - P-AC7-1 runs after the AC-7 samples, which run at Level 0 (step 7).
   - One invocation could not be in both places.
2. **The genuine revocation is made by P-AC7-1, in the browser run**, followed
   by E-5, E-6 and E-18 in the harness.
   - §19 requires P-AC7-1 to show `running`, *then* `failed`. A revocation made
     before the spec would leave only `failed` to show.
   - The revocation is still made once, by the workspace's owner, and is
     still the companion's alone (§29.2).

### 35.3 A new finding, F-4F8-17, fixed in the P8 driver

**F-4F8-17: P8's V-7 (a1) relied on the 10-second dispatch to space its second
modification past the 1-second debounce.**

- **What happened.** V-7 (a1) modifies run A's file again *"after the debounce
  window"*, but nothing enforced that. Run A always took longer than 1 s,
  because of the 10 s dispatch. With D-4F-1's one-second dispatch, the local run
  finished run A in under a second.
- **The evidence, from that run:**
  - A was observed at `16:36:42.79`;
  - the modification was observed at `16:36:43.56`;
  - `perception-engine` correctly debounced it;
  - P8 timed out waiting for a second observation.
- **The fix**, in `tools/e2e_real_execution.py`:
  - it sleeps until A's own `observed_at`, plus `DEBOUNCE_SECONDS` (1.0), plus
    0.5 s;
  - `DEBOUNCE_SECONDS` is restated from `perception-engine`'s
    `workspace_debounce_seconds`, and drift-guarded by
    `test_the_debounce_window_is_perception_engines`;
  - `real_run` also gains a `prefix` argument, defaulting to `p8`.
- **No engine changed.** Re-run, P8 passed **67 of 67**.

### 35.4 Evidence (local processes; not containers, not CI)

**The local stack.** The real engines ran as processes against real PostgreSQL
16 with pgvector, nats-server and redis-server:
- `world-model-engine` used the in-memory graph store;
- `memory-engine` used the in-memory embedding backend;
- the companion ran as uid 1100 with gid 1001 (the "runner"), and the workspace
  was owned by 1001 with mode 0755;
- `capability-engine` ran as root;
- there were no gateways and no browser.

| Phase | Result |
|---|---|
| P8 (4F.P) | **67 of 67**, after the F-4F8-17 fix. Before it: 66, with V-7 (a1) timing out |
| `ac8` | **54 of 54**: E-8, E-9 (through P8's executed-run checks), E-10, E-11, E-12, E-13, E-17, and P-AC8-1's premise |
| `ac7-latency` | **70 of 70**. Ten samples, below |
| `ac7-revocation` | **7 of 10.** The three that failed need Docker: the companion log read through `docker compose logs`, and E-18's two `docker compose exec` checks. The companion's own process log showed `permission_revoked` once and `revocation_reported` once (`state: failed`, `transitioned: true`), and no submission for the post-revocation file. The remaining checks passed: `failed` in `perception-engine`; exactly one dispatched `failed`; `cognitive_state.sensor_state = failed` from it; and E-6's 25 s watch |

**AC-7's ten local samples**, from OS mtime to the first World Model read:

| # | Pause before (s) | Elapsed (s) |
|---|---|---|
| 1 | 1.916 | 0.284 |
| 2 | 0.435 | 0.574 |
| 3 | 1.322 | 0.680 |
| 4 | 0.920 | 0.064 |
| 5 | 1.603 | 0.400 |
| 6 | 0.037 | 0.955 |
| 7 | 0.531 | 0.458 |
| 8 | 1.708 | 0.284 |
| 9 | 0.808 | 0.172 |
| 10 | 0.175 | 0.834 |

The maximum was **0.955 s**, and all ten were ≤ 5.0 s. **This is local evidence
and does not make AC-7 met:** A-4F8-6's measurement is the CI acceptance run's.

**The guard's negative controls**, each reverted afterwards. Each of these
failed its named test:
- a 5.5 s budget;
- a write aligned to a clock boundary (N-1);
- discarding an unobserved sample (N-2);
- a `POST` inside a sample (E-4);
- a non-`SELECT` statement;
- `retries` allowed in P-AC7-1;
- `continue-on-error` on the latency step.

### 35.5 What this does not show

- **CI.** The acceptance run in containers, with E-18, N-16, the runner's gid,
  and both Playwright specs. Neither spec ran here, because the local stack has
  no gateways.
- **AC-7 and AC-8 are not met, and not claimed**, until that run's evidence
  exists.

---

## 36. Implementation record — flakiness, F-4F8-18, and the documentation notes — 2026-10-11

**Added 2026-10-11, additively**, on `phase-4f8`. It records:
- the flakiness run §29.4.6 requires;
- the finding that run produced, and its fix;
- the dated notes this slice owes other documents.

### 36.1 The flakiness run, before the fix

**The method.** Ten cycles, each on a **fresh** local stack. A fresh stack means
a new database, a new workspace, a new run id and a new known project. Each
cycle runs CI's order:
1. P8;
2. `ac8`;
3. `ac7-latency`;
4. the revocation;
5. `ac7-revocation`.

**The revocation stands in for P-AC7-1.** It is the same `chmod g-rx`, made by
the workspace's owner (uid 1001). The local stack has no browser. Nothing was
retried.

**The local stack** is §35.4's: real engines as processes, real PostgreSQL 16,
nats-server and redis-server, and the companion as uid 1100.

| Phase | Result, in each of the 10 cycles |
|---|---|
| P8 | **67 of 67**, 10 of 10 cycles |
| `ac8` | **54 of 54**, 10 of 10 cycles |
| `ac7-latency` | **70 of 70 in 9 cycles. 69 of 70 in cycle 6**: sample 9's N-3 failed (§36.2) |
| `ac7-revocation` | **7 of 10**, 10 of 10 cycles. The same three Docker-only checks failed each time (§35.4) |

**The companion's own log**, in each cycle, had exactly one
`permission_revoked` and one `revocation_reported` line.

**AC-7's latency, all 100 samples:**
- the range was **0.059–1.064 s**;
- the median was 0.592 s and the mean 0.584 s;
- the 95th percentile was 1.015 s;
- **none exceeded 5.0 s.**

Every figure is kept in the run's logs, in this session's scratchpad. They are
not committed.

### 36.2 F-4F8-18: the harness started its interval at the wrong mtime

**What failed.** In cycle 6, sample 9's N-3 check failed. The companion
reported `observed_at = …43.696272`. The harness had read `…43.700272` from the
file after writing it. That is exactly 4.000 ms later, which is this kernel's
coarse-clock step.

**Why.**
1. **Writing a new file is two syscalls**: `open(O_CREAT)`, then `write()`.
   `Path.write_text` does both. Each may stamp the file's mtime, so one file can
   carry two different OS times.
2. **The companion handles inotify's create event, and reads the mtime then**
   (`companion/sensors/src/lib.rs`, `is_observable` and `metadata.modified()`).
   So it may legitimately report **either** of the two.
3. **The harness read only the second.** So its interval could start late,
   shortening a sample, and N-3's equality could fail.

**When the two stamps differ, as observed on this kernel (6.18.44):**
- **A query of the file's times between the two calls makes them differ.** A
  probe ran 200 creates with no query between create and write: the write's
  stamp equalled the creation's every time. With an `fstat` between them, it
  differed in 114 of 200.
- In cycle 6, the companion's own stat on the create event was that query.
  The 4.000 ms gap is consistent with the coarse clock also stepping.
- This is consistent with Linux's multigrain timestamps (6.13 and later). The
  mechanism is recorded as observed, not as established.

**No engine or companion defect.** The companion reported the file's own OS
time, as TDD 4F §20.1 requires.

**Reproduced, three of three.** A probe created a file, read its mtime, waited
50 ms, wrote it, and read its mtime again. Each time the companion reported
the **creation** mtime, and never the write's.

**The fix, in `tools/e2e_acceptance.py`'s `measure_sample`:**
- it creates the file with `os.open(O_WRONLY | O_CREAT | O_EXCL)`;
- it reads the creation mtime with `os.fstat`, writes, and reads the write's
  mtime;
- **the interval starts at the creation**, the earlier of the two, so it never
  shortens a sample;
- N-3 accepts `observed_at` equal to either of the file's own two OS times,
  and nothing else;
- `O_EXCL` makes the OS refuse a path that already exists, strengthening
  FP-14.

**Unchanged:** AC-7's 5.0 s budget, the sample count, the 50 ms poll, the
30 s deadline, and the 10 ms allowance for "not before the write".

**The guards.** One test is new:
`test_f4f8_18_the_interval_starts_at_the_files_creation`. The N-3 guard now
pins both comparisons. Each negative control below was a temporary mutation,
reverted afterwards, and each failed its named test:
- `elapsed` measured from the write;
- `O_EXCL` removed;
- the creation's mtime read after the write;
- N-3 compared against the write's mtime only;
- N-3 compared against the creation's mtime only.

**A runtime control.** A temporary 50 ms sleep was put between the creation
and the write, so every sample hit cycle 6's case, and `ac7-latency` was run.
It was removed afterwards, and the file was compared byte for byte.
- **N-3 passed 10 of 10**, with the two mtimes about 50 ms apart each time.
- Its §29.4.3 checks failed. That stack had not run P8 and `ac8` first, so
  the real autonomy-engine **denied** at Level 0 for want of a grant: *"no
  permission grant for category=read"*. See §36.4.

### 36.3 The flakiness run, after the fix

The same method as §36.1: ten new fresh stacks, with the fixed harness. Every
cycle's report carries `os_created`, the fixed harness's field.

| Phase | Result, in each of the 10 cycles |
|---|---|
| P8 | **67 of 67**, 10 of 10 cycles |
| `ac8` | **54 of 54**, 10 of 10 cycles |
| `ac7-latency` | **70 of 70**, 10 of 10 cycles. N-3 passed **100 of 100** |
| `ac7-revocation` | **7 of 10**, 10 of 10 cycles. The same three Docker-only checks failed each time |

The companion's own log, in each cycle, had exactly one `permission_revoked`
and one `revocation_reported` line.

**The two mtimes, in all 100 samples.**
- **The creation's stamp and the write's stamp differed every time**, by
  1.13–4.99 ms. The creation's stamps are aligned to the coarse clock's 4 ms
  steps. The write's stamps are not: the harness's own `fstat` had queried the
  file in between (§36.2).
- **The companion reported the write's stamp in 100 of 100 samples.**
- **So every interval starts 1.13–4.99 ms earlier** than it would from the
  write's stamp. That is the conservative direction.

**AC-7's latency, all 100 samples:**
- the range was **0.062–1.083 s**;
- the median was 0.554 s and the mean 0.530 s;
- the 95th percentile was 0.992 s;
- **none exceeded 5.0 s.**

The ten per-cycle maxima were 0.888, 1.018, 0.945, 1.065, 0.958, 1.061, 0.992,
0.835, 1.083 and 0.892 s.

**Neither run is CI evidence, and neither makes AC-7 met.** A-4F8-6's
measurement is the CI acceptance run's (§35.5).

### 36.4 One precondition, stated

**`ac7-latency` presupposes the configuration P8 and `ac8` leave in place**:
the grant, the `auto_execute` policy and the identity threshold. That is
§29.4.1's order, and CI's.

**That configuration is what makes §29.4.3 meaningful.** Level 0 records
`observe_only` *even though* a matching `auto_execute` policy exists. Run
alone, the phase fails §29.4.3, as the runtime control in §36.2 shows. It
fails loudly, with `deny` and its reason, and never passes vacuously.

### 36.5 One residual risk, stated

**`MTIME_GRANULARITY_SECONDS` (10 ms)** bounds how far the creation's mtime may
precede the harness's own `before`.
- The creation's stamp comes from the coarse clock, which trails the
  harness's clock. Over the 100 samples in §36.3, it preceded `before` by
  **0.93–4.88 ms**. In cycle 6 before the fix, the gap was 4.27 ms. This
  kernel's coarse clock moves in 4 ms steps.
- A CI kernel with a coarser clock could exceed 10 ms. N-3 would then fail
  with the figures printed.
- **It is not widened on speculation.** If CI shows it, that is reported as
  found.
- **It never affects a latency figure.** Every interval starts at the OS time.

### 36.6 The documentation notes this slice owed

Each note is dated and additive. The original text is preserved.

| Document | Note |
|---|---|
| TDD 4F §15 | The *"Outbox dispatch delayed"* row: about one second plus any backlog, on `phase-4f8` |
| TDD 4F §16.2 | *"The unchanged dispatcher"* is historical for `perception-engine`. The honesty rules are unchanged |
| TDD 4F §18 | The 4F.8 row carries the dispatch exception. Still one milestone, and still its final slice |
| Master scope, AC-7's revision note | The *"fixed 10-second cron"* is historical for `perception-engine` only |
| Master scope, slice status | What `phase-4f8` built. CI has not run. AC-7 and AC-8 are not met |
| TDD 4F.7 §3 | The dispatch row, and where §7, §8, §9 and §15 cite 10 s |
| TDD 4F.7 §15 | K-2 is addressed by A-4F8-1 (a), with CI evidence owed. K-3's bound is now about one second |
| `docs/architecture/11-api-architecture.md` §3 | The engine-level `/v1/perception/*` routes the companion calls, including D2's `permission-revocations`. Not fronted by `api-gateway` |

### 36.7 What this does not show

- **CI and containers**: the acceptance run, E-5's log check through
  `docker compose logs`, E-18, N-16, the runner's gid, and both Playwright
  specs.
- **AC-7 and AC-8 are not met, and not claimed.** A-4F8-9, CF-9, CF-10 and
  CF-11 stay OPEN.

---

## 37. Implementation record — the remaining negative controls, and F-4F8-19 — 2026-10-11

**Added 2026-10-11, additively**, on `phase-4f8`. It records §17's N-9 and N-11
run as real mutations, the finding the first attempt produced, and its fix.

### 37.1 N-9 and N-11, as real mutations

**The method.** Each control ran on a fresh local stack, with `ac8` alone and
no P8 first. So the mutated configuration or authoring was the only one the
stack ever saw. Each mutation was temporary, and the file was restored byte for
byte afterwards.

| # | Mutation | Result |
|---|---|---|
| N-9 | The `AUTO_EXECUTE` policy's `POST` names `write`, not `read`. The route refuses the category with a `422`, so **no `AUTO_EXECUTE` policy exists** | **Caught: 24 named checks failed.** The policy check; every E-9 execution check (no `action.execute`, no `completed`, no action row, no invocation); E-10; E-11; P-AC8-1's premise (the Level-2 run proposed); and E-17 |
| N-11 | T1 authored `moderate` (`cognitive-state-engine`'s `domain/authoring.py`) | **Caught: 26 named checks failed.** T1's identity check; E-8 (the real `autonomy-engine` denied at Level 1, because *"risk=moderate exceeds the maximum low granted for category=read"*); every E-9 execution check; E-10; E-11; and E-17 |

**Not run as mutations in this slice:**
- **N-10** is E-17's own denial run, which every `ac8` run performs.
- **N-12** rests on E-9's `completed` assertion, which P8's executed-run
  checks make independently of the decision's outcome. 4F.P's NP-1
  negative-controlled the `failed → EXECUTE` mapping itself.
- **N-14 and N-15** are carried by the unchanged pinned tests.

### 37.2 F-4F8-19: a failing `ac8` run could end before reporting

**What happened.** The first N-11 attempt failed its E-9 checks by name. Then
`_check_same_path` raised `ValueError` on `(action,) = …`, because the Level-2
run had, correctly, no action row. **The phase still exited non-zero.** But E-10
and E-11 were never evaluated, and the evidence dump and summary line were
never printed.

The first N-9 attempt was a malformed mutation (`if False:`). It sent P8's
`configure` down its other branch, which indexed an empty list. **It proved
nothing, and is not counted.**

**The fix, in `tools/e2e_acceptance.py`:**
- **`_check_same_path` reads counts, and checks them.** A missing row is the
  failed check *"E-10. each run recorded exactly one decision, and the Level-2
  run exactly one action"*, and never an unpacking error.
- **Every phase records any other error as a failed check**, with its
  traceback, through `_unexpected`. `_finish` still prints the evidence, and
  the exit status is still non-zero. Nothing is retried.
- **`ac7-latency` decides E-3 before the per-sample attribution checks.** So
  the latency verdict and every figure are recorded even if a later check
  cannot complete. Each figure was already printed as it was measured. **The
  measurement, the budget and the pass rule are unchanged.**

**The guards**, with their negative controls. Each mutation was temporary and
reverted, and each failed its named test:

| Guard | Mutation |
|---|---|
| `test_f4f8_19_an_unexpected_error_fails_the_phase_and_keeps_its_evidence` (×3) | `ac8` without the catch-all; `_unexpected` passing its check (all three failed) |
| `test_f4f8_19_e3_is_decided_before_the_attribution_checks` | E-3 decided after `_check_samples` |
| `test_f4f8_19_check_same_path_never_unpacks_a_row` | A tuple unpack restored |

**The controls, re-run with the fix.** The results in §37.1 are those runs:
- N-9 ended with *"=== AC-8: 24 check(s) FAILED ==="*;
- N-11 ended with *"=== AC-8: 26 check(s) FAILED ==="*;
- neither printed a traceback.

### 37.3 What this does not show

- **CI.** These are local runs.
- **AC-7 and AC-8 are not met, and not claimed.**

### 37.4 Ten cycles at `3bca553`

**Added 2026-10-11, additively**, after the commit that §37.1–§37.3 describe.
Because F-4F8-19 changed the harness, §36.1's method was run again: ten new
fresh stacks, at `3bca553`.

| Phase | Result, in each of the 10 cycles |
|---|---|
| P8 | **67 of 67**, 10 of 10 cycles |
| `ac8` | **55 of 55**, 10 of 10 cycles. The 55th check is F-4F8-19's E-10 count |
| `ac7-latency` | **70 of 70**, 10 of 10 cycles. N-3 passed **100 of 100** |
| `ac7-revocation` | **7 of 10**, 10 of 10 cycles. The same three Docker-only checks failed each time |

- The companion's own log, in each cycle, had exactly one
  `permission_revoked` and one `revocation_reported` line.
- **AC-7's latency, all 100 samples:**
  - the range was **0.063–1.039 s**;
  - the median was 0.564 s and the mean 0.558 s;
  - the 95th percentile was 0.963 s;
  - **none exceeded 5.0 s.**
- The creation's stamp preceded the harness's `before` by 0.11–4.74 ms, within
  §36.5's 10 ms allowance.

**Across §35.4, §36.1, §36.3 and this run: 310 local samples, 0.059–1.083 s,
none over 5.0 s.** None of it is CI evidence. **AC-7 and AC-8 are not met, and
not claimed.**

---

## 38. CI verification, run 1, and F-4F8-20 — 2026-10-11

**Added 2026-10-11, additively.** The user authorized a draft PR so that CI
could run. This section records that first run, the one failure it found, and
the fix the user then authorized.

### 38.1 The baseline run

**Draft PR [#41](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/pull/41)**,
`phase-4f8` → `phase-4`.
- Head **`3e44a1938457429502821d02fd111eefadd12723`**; base `1ccce7a`.
- All three workflows ran at that exact head, on attempt 1.

| Workflow | Run | Jobs | Conclusion |
|---|---|---|---|
| `PR Checks` | `38183904818` | `checks` success; `e2e` **failure** | **failure** |
| `Real-Infrastructure Checks` | `38183904782` | **15/15** success. `perception-engine`: **28 passed**, 242 deselected | success |
| `Build & Scan` | `38183904822` | **23/23** success: `dependency-audit` and 22 image builds with Trivy | success |

**39 of 40 jobs succeeded.** The `e2e` job's steps:

| Step | Result |
|---|---|
| The golden path (Playwright) | **20 passed** |
| *Declare the AC-7 known project* | success |
| *Start the P8 services*, with the override | success |
| P8 (4F.P) | **67/67** |
| AC-8 (D6) | **55/55** |
| **P-AC8-1** | **failed** (§38.2) |
| AC-7 latency (D5) | **70/70** |
| P-AC7-1, with the genuine revocation | **passed** (11.5 s) |
| AC-7 revocation (E-5, E-6, E-18) | **10/10** |

**AC-7's ten CI samples**, at run id `511abb139854`, from each file's
creation mtime to the first World Model `200`:

| # | File | Pause before (s) | Elapsed (s) |
|---|---|---|---|
| 1 | `ac7-511abb139854-1.txt` | 1.152 | 0.827 |
| 2 | `ac7-511abb139854-2.txt` | 1.075 | 0.938 |
| 3 | `ac7-511abb139854-3.txt` | 0.273 | 0.723 |
| 4 | `ac7-511abb139854-4.txt` | 1.531 | 0.494 |
| 5 | `ac7-511abb139854-5.txt` | 1.529 | 0.452 |
| 6 | `ac7-511abb139854-6.txt` | 1.737 | 0.280 |
| 7 | `ac7-511abb139854-7.txt` | 0.368 | 0.612 |
| 8 | `ac7-511abb139854-8.txt` | 0.065 | 0.942 |
| 9 | `ac7-511abb139854-9.txt` | 0.380 | 0.618 |
| 10 | `ac7-511abb139854-10.txt` | 1.233 | 0.727 |

- **The maximum was 0.942 s.** All ten were ≤ 5.0 s, none was discarded,
  and E-3 passed.
- **N-3 passed 10 of 10.** In every sample the companion reported the write's
  stamp.
- **The creation's stamp preceded the harness's `before` by 0.21–1.81 ms.**
  That is far inside §36.5's 10 ms allowance. This kernel's coarse clock
  appears to step about every 1 ms. The residual risk did not occur.

**The revocation in CI's containers:**
- the workspace's mode was `0705`;
- E-5: the companion's container log had `permission_revoked` and
  `revocation_reported`, once each; `failed` in `perception-engine`; one
  `failed` report; `cognitive_state` held `failed`;
- **E-18:** the companion ran as uid `1100` and got *"ls: cannot open
  directory '/workspace': Permission denied"*. `capability-engine`'s `ls`
  returned 0;
- E-6: a write the OS accepted produced no outbox row and no World Model
  object (`404`) for 25 s, and the companion submitted nothing.

**AC-8 in CI:**
- E-8, E-10, E-11, E-12, E-13 and E-17 all passed.
- **E-9:** every one of P8's executed-run checks passed for the Level-2 run:
  - exactly one `action.execute`, carrying `{"operation": "list"}`;
  - the real `action-engine` replied `completed`, with exactly one action row;
  - the real `capability-engine` ran the filesystem `list` once, and its
    counter rose by one;
  - `EXECUTE` was written after `action-engine`'s terminal writes.

### 38.2 F-4F8-20: the Autonomy panel could not read an `AUTO_EXECUTE` policy

**What failed.** P-AC8-1 passed its gateway assertions and the level check.
- The gateway served the Level-1 subject `b4be5a26…` as `proposed`.
- It did not serve the Level-2 subject.
- The panel showed Level 2.

It then found **no** suggestion row naming `ac8-511abb139854-level1.txt`.

**Why.** `apps/web-client/src/entities/autonomy.ts` read policies and gate
reports with `POLICY_EFFECTS = ["deny", "require_approval"]`, the authoring
enum.
- Once AC-8's `AUTO_EXECUTE` policy exists, every gate report carries its
  `auto_execute` policy check.
- So the whole suggestion list failed its zod parse.
- `AutonomyPanel` renders `suggestions.data?.data.items ?? []`, so it showed
  the empty inbox: *"Nothing is awaiting your decision"*. The gateway was
  serving the proposal at the same time.
- The policy list failed the same way.

**This contradicts TDD 4F.5 §17.1.1 (L-17)**, which says *"Nothing is
mis-rendered"*. A dated correction is added there.

**Reproduced locally first**, through the panel's own unit-test fixtures, with
a positive control: the same suggestion without the `auto_execute` check
rendered.

**The user's decision (2026-10-11): the narrow read-path fix.** It extends
A-4F8-8's governed surfaces to `apps/web-client/src/entities/autonomy.ts`, for
this fix only.
- **`SERVED_POLICY_EFFECTS`** is `POLICY_EFFECTS` plus `auto_execute`. It is
  used only by `policySchema` and `policyCheckSchema`.
- **Authoring is unchanged.** The editor still offers `POLICY_EFFECTS` alone,
  so the panel cannot create an `AUTO_EXECUTE` policy. **L-17 stays OPEN** for
  authoring.
- **Disclosed:** an `AUTO_EXECUTE` policy now appears in the list with the same
  enable, disable and delete controls every policy already had.
- No route, contract, engine or prefix changed.

**The tests** are in `apps/web-client/tests/unit/autonomy-panel.test.tsx`. Each
mutation was temporary and reverted, and each failed its named test:

| Test | Mutation |
|---|---|
| *"a suggestion whose gates carry an auto_execute check still renders"* | Gate checks read with the authoring enum |
| *"an auto_execute policy is listed with its effect, never as an empty set"* | Policies read with the authoring enum |
| *"is read only: the editor still cannot author auto_execute (L-17 stays open)"*, and the existing *"offers deny and require_approval only"* | The editor offering every served effect |

**Local results:** web-client 248 passed (245 before), with eslint and `tsc`
clean. `tools/tests`: 385.

### 38.3 What this does not show

- **CI at the fix's commit.** It runs on the push that carries this section.
- **N-16.** It waits for a green baseline (the user's sequencing).
- **AC-7 and AC-8 are not yet met.** P-AC8-1, AC-8's browser-visible clause,
  has not passed in CI.

---

## 39. CI verification: the baseline, N-16, F-4F8-21, and the restored configuration — 2026-10-12

**Added 2026-10-12, additively.** §38.3 left two things open: CI at F-4F8-20's
commit, and N-16. This section records, in order:
- the green baseline at `3aab37f` (§39.1);
- N-16's first CI run, and the finding it surfaced (§39.2, §39.3);
- N-16's re-run (§39.4);
- the restoration, and its run (§39.5).

**The mutation runs (§39.2, §39.4) are negative-control evidence only.** They
are kept apart from the acceptance evidence (§39.1, §39.5).

Every run is PR #41's, on `pull_request`, at attempt 1. A run's URL is
`https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/<id>`.

| Head | What it is | `PR Checks` | `Real-Infrastructure Checks` | `Build & Scan` | Jobs |
|---|---|---|---|---|---|
| `3e44a19` | §38.1's run 1 | `38183904818` failure | `38183904782` success | `38183904822` success | 39/40 |
| `3aab37f` | F-4F8-20's fix (§38.2) | `38184998345` **success** | `38184998370` success | `38184998342` success | **40/40** |
| `dfb26f3` | N-16: the override removed (TEMPORARY) | `38185485137` failure | `38185485109` success | `38185485125` success | 38/40 |
| `a1a6752` | F-4F8-21's fix, with N-16 still in place | `38186438469` failure | `38186438436` success | `38186438433` success | 38/40 |
| `c04eaff` | The revert of `dfb26f3` | `38187227734` **success** | `38187227720` success | `38187227711` success | **40/40** |

### 39.1 The baseline: `3aab37f`, 40 of 40

- **`checks`** succeeded, and so did **`e2e`**.
- **`Real-Infrastructure Checks`:** 15/15 jobs.
- **`Build & Scan`:** 23/23 jobs, with Trivy.

The `e2e` job's steps:

| Step | Result |
|---|---|
| The golden path (Playwright) | **20 passed** |
| P8 (4F.P) | **67/67** |
| AC-8 (D6) | **55/55** |
| **P-AC8-1** | **passed** |
| AC-7 latency (D5) | **70/70** |
| P-AC7-1, with the genuine revocation | **passed** |
| AC-7 revocation (E-5, E-6, E-18) | **10/10** |

**P-AC8-1 passed in a browser:**
- the gateway served the Level-1 proposal, and not the Level-2 run;
- the panel showed Level 2;
- exactly one suggestion row named the Level-1 file. It was `proposed`, with
  risk `low` and its approve control enabled;
- no row named the Level-2 file.

**AC-7's ten CI samples**, at run id `69e14d5ef961`. Each runs from its file's
creation mtime to the first World Model `200`:

| # | File | Pause before (s) | Elapsed (s) |
|---|---|---|---|
| 1 | `ac7-69e14d5ef961-1.txt` | 1.630 | 0.846 |
| 2 | `ac7-69e14d5ef961-2.txt` | 0.623 | 0.374 |
| 3 | `ac7-69e14d5ef961-3.txt` | 1.121 | 0.899 |
| 4 | `ac7-69e14d5ef961-4.txt` | 1.767 | 0.217 |
| 5 | `ac7-69e14d5ef961-5.txt` | 1.813 | 0.202 |
| 6 | `ac7-69e14d5ef961-6.txt` | 1.574 | 0.448 |
| 7 | `ac7-69e14d5ef961-7.txt` | 0.943 | 1.003 |
| 8 | `ac7-69e14d5ef961-8.txt` | 0.328 | 0.688 |
| 9 | `ac7-69e14d5ef961-9.txt` | 0.900 | 0.111 |
| 10 | `ac7-69e14d5ef961-10.txt` | 0.359 | 0.633 |

- **The maximum was 1.003 s.** All ten were ≤ 5.0 s, none was discarded,
  and E-3 passed.
- **N-3 passed 10 of 10.** The companion reported the write's stamp each time.
- **The creation's stamp preceded the harness's `before` by 0.176–0.996 ms**,
  inside §36.5's 10 ms allowance.

**The revocation, in CI's containers:**
- the workspace's mode was `0705`;
- **E-5:** the companion's container log had `permission_revoked` and
  `revocation_reported`, once each. `perception-engine`'s sensor was `failed`,
  and exactly one `failed` report went out through the outbox.
  `cognitive-state-engine` held `failed`;
- **E-18:** the companion ran as uid `1100` and got *"ls: cannot open
  directory '/workspace': Permission denied"*. `capability-engine`'s `ls`
  returned 0 with an empty stderr;
- **E-6:** a write the OS accepted produced no outbox row and no World Model
  object for 25 s, and the companion submitted nothing for it.

### 39.2 N-16, first run: `dfb26f3`

**The mutation was one line**, in `pr-checks.yml`'s *"Start the P8 services"*
step: `-f infra/docker/docker-compose.acceptance.yml` was removed. So the
companion ran as the image's uid.

**What caught it:**
- **`checks`:** the two structural guards in `test_acceptance_override.py`
  failed:
  - `test_exactly_one_workflow_step_applies_the_override`;
  - `test_the_applying_step_derives_the_gid_from_the_runner`;
- **`e2e`, P-AC7-1:** *Expected: "failed" / Received: "running"*;
- **`e2e`, `ac7-revocation`:**
  - E-5's companion log had neither `permission_revoked` nor
    `revocation_reported`;
  - the sensor stayed `running`;
  - the chain timed out after 180 s.

**Unaffected:** AC-8 55/55, P-AC8-1 and AC-7 latency 70/70.
- Its ten samples, at run id `47e4e05df69e`, were 0.167, 0.323, 0.324, 0.501,
  0.955, 0.503, 0.749, 0.693, 0.057 and 0.488 s.
- They are a mutation run's, and are not acceptance evidence.

**E-18 was never evaluated.** That is F-4F8-21.

### 39.3 F-4F8-21: E-18 could not fail under N-16

**What was wrong.** `ac7_revocation` inspected E-18 after E-5's two
`wait_for` calls.
- Under N-16 the companion is never revoked, so the first wait times out.
- The phase then records *"the chain completed within the deadline"* as
  failed, and ends.
- **So E-18's container checks never ran.**

§17's note and §29.4.6 both say of N-16: *"E-18 must then fail."* As ordered,
it could not.

**The fix (`a1a6752`).** E-18 is a read-only OS inspection (§29.4.6), and it
does not depend on E-5. It now runs first: right after the
revocation-in-place check, before anything waits.
- No check, threshold or deadline changed.
- Only `tools/e2e_acceptance.py` and its guard file changed.

**The guard:** `test_f4f8_21_e18_is_inspected_before_anything_waits`. It
requires E-18's check to come before the first `wait_for(` and the first
`companion_log_messages(` in `ac7_revocation`'s source.
- **Negative-controlled.** With the old order restored it failed. With the
  fix it passes.
- `tools/tests` is 386 tests (385 + 1).

**Classification:** a defect in test infrastructure, found by a negative
control, fixed and guarded. No engine changed.

### 39.4 N-16, re-run: `a1a6752`

The same mutation, with F-4F8-21's order. **What caught it:**
- **`checks`:** the same two guards. *"2 failed, 384 passed."*
- **E-18's companion half: FAILED.** The evidence was
  `{"uid": "1000", "ls": ""}`:
  - the companion ran as uid 1000, not 1100;
  - its `ls` of `/workspace` printed no error. The check records `ls`'s
    stderr, not its exit code. A denied `ls` writes *"Permission denied"*
    there.
- **E-18's `capability-engine` half: passed**, with return code 0.
- **E-5:**
  - neither message was in the companion's log;
  - the sensor stayed `running`;
  - the chain timed out after 180 s.
- **P-AC7-1:** *Received: "running"*.

**Unaffected:** P8 67/67, AC-8 55/55, P-AC8-1 and AC-7 latency 70/70.
- Its samples, at run id `30eff9b34bbc`, were 0.152, 0.327, 0.218, 0.921,
  1.035, 0.114, 0.335, 0.304, 0.540 and 0.223 s.
- They are a mutation run's, and are not acceptance evidence.

**N-16 is caught in CI**: by the guard, by E-18, by E-5 and by P-AC7-1.

**Its stated mechanism did not hold.** §17's note says E-18 fails *"because
`capability-engine` loses access too"*. §29.4.6 says *"because
`capability-engine` is denied too"*. In CI, `capability-engine` kept access.
- E-18 failed because **the companion was not denied at all**.
- Under `chmod g-rx` to `0705`, uid 1000 is neither the owner nor in the
  group, so it reads through the *other* bits.
- §34.2's local analogue showed the same, and `dfb26f3`'s message predicted
  it.
- **The prediction held, and the reason given for it did not.** Dated notes
  are added at §17 and §29.4.6. No check depends on the reason.

### 39.5 The restoration: `c04eaff`

`c04eaff` reverts `dfb26f3` with a normal new commit.
- **No history was rewritten.**
- After it, **`pr-checks.yml` is byte-identical to `3aab37f`'s**:
  `git diff --quiet 3aab37f c04eaff -- .github/workflows/pr-checks.yml`
  exits 0.
- `git diff --stat 3aab37f c04eaff` lists two files: `tools/e2e_acceptance.py`
  and `tools/tests/test_e2e_acceptance.py`. Those are F-4F8-21's.

**The restored run is 40 of 40.**
- **`checks`:**
  - `tools/tests`: 386 passed;
  - `turbo` lint and test: 32/32 each, 0 cached; typecheck: 5/5;
  - `web-client`: 248 passed; `perception-engine`: 242 passed, 28 deselected;
  - `lint-imports`: 7 kept, 0 broken;
  - Cargo: 41 passed, including both `revocation` binaries (4 + 4).
- **`Real-Infrastructure Checks`:** 15/15. `perception-engine`: **28 passed**,
  242 deselected.
- **`Build & Scan`:** 23/23, with Trivy.

The `e2e` job's steps:

| Step | Result |
|---|---|
| The golden path (Playwright) | success |
| P8 (4F.P) | **67/67** |
| AC-8 (D6) | **55/55** |
| **P-AC8-1** | **passed** |
| AC-7 latency (D5) | **70/70** |
| **P-AC7-1**, with the genuine revocation | **passed** |
| AC-7 revocation (E-5, E-6, E-18) | **10/10** |

**AC-7's ten CI samples**, at run id `45d446e16342`:

| # | File | Pause before (s) | Elapsed (s) |
|---|---|---|---|
| 1 | `ac7-45d446e16342-1.txt` | 0.955 | 0.729 |
| 2 | `ac7-45d446e16342-2.txt` | 0.821 | 0.165 |
| 3 | `ac7-45d446e16342-3.txt` | 0.587 | 0.432 |
| 4 | `ac7-45d446e16342-4.txt` | 0.261 | 0.737 |
| 5 | `ac7-45d446e16342-5.txt` | 0.636 | 0.368 |
| 6 | `ac7-45d446e16342-6.txt` | 1.830 | 0.160 |
| 7 | `ac7-45d446e16342-7.txt` | 1.107 | 0.887 |
| 8 | `ac7-45d446e16342-8.txt` | 0.299 | 0.676 |
| 9 | `ac7-45d446e16342-9.txt` | 0.993 | 1.049 |
| 10 | `ac7-45d446e16342-10.txt` | 0.843 | 0.115 |

- **The maximum was 1.049 s.** All ten were ≤ 5.0 s, none was discarded,
  and E-3 passed.
- **N-3 passed 10 of 10.**
  - In samples 1–9 the companion reported the write's stamp.
  - **In sample 10 it reported the creation's.** That is F-4F8-18's case
    (§36.2), and the interval had started there.
- **The creation's stamp preceded `before` by 0.116–0.771 ms.**

**The revocation:**
- the workspace's mode was `0705`;
- **E-18:** the companion ran as uid `1100`, and got *"ls: cannot open
  directory '/workspace': Permission denied"*. `capability-engine`'s `ls`
  returned 0;
- **E-5:**
  - `permission_revoked` and `revocation_reported` appeared once each in the
    companion's container log;
  - the sensor was `failed`, and one `failed` report went through the outbox;
  - `cognitive-state-engine` held `failed`;
- **E-6:** 25 s with no outbox row, no World Model object and no submission.

**AC-7's CI samples, in every run.** Fifty samples, none over 5.0 s, and none
discarded:

| Head | Run id | Kind | Range (s) |
|---|---|---|---|
| `3e44a19` | `511abb139854` | Run 1. The run was red, on P-AC8-1 (§38) | 0.280–0.942 |
| `3aab37f` | `69e14d5ef961` | **Acceptance** | **0.111–1.003** |
| `dfb26f3` | `47e4e05df69e` | N-16, mutated | 0.057–0.955 |
| `a1a6752` | `30eff9b34bbc` | N-16, mutated | 0.114–1.035 |
| `c04eaff` | `45d446e16342` | **Acceptance** | **0.115–1.049** |

### 39.6 What this shows, and what it does not

- **It shows** AC-7 and AC-8 measured in CI's containers and in a browser.
  They were measured at `3aab37f`, and again at `c04eaff`, the restored
  configuration. Every sample was ≤ 5.0 s, and none was discarded.
- **It shows** N-16 caught in CI, and the branch restored.
- **It does not show** the PR reviewed, or a merge authorized. **4F.8 is not
  complete** until both, and the merge itself.
- **It does not resolve** A-4F8-9 (F-4F8-10), CF-9, CF-10, CF-11 or F-4F8-12:
  - both acceptance-carrying workflows are still non-blocking;
  - **L-17 stays OPEN** for authoring.
- **It does not show multi-replica safety.** That is not claimed (§30.2).
- **It does not meet §17's flakiness rule for the two browser tests.** §17 says
  *"Every real-infrastructure and browser test in 4F.8 involves timing. Each is
  run ≥ 10 times and reported."*
  - The real-infrastructure tests and the acceptance phases were run 10 times
    (§31–§37).
  - **P-AC7-1 and P-AC8-1 were not.** They can run only in CI.
  - In CI, P-AC8-1 has passed **4 times** (`3aab37f`, `dfb26f3`, `a1a6752`,
    `c04eaff`). It failed once at `3e44a19`, on F-4F8-20.
  - P-AC7-1 has passed **3 times** with the override (`3e44a19`, `3aab37f`,
    `c04eaff`). It failed twice under N-16, as designed.
  - **This is open, and needs the user's decision:** the completion record,
    §12.

  ***Superseded 2026-10-12, additively (§40):*** the bullet above is preserved
  as written.
  - P-AC8-1 has now passed **11** times in CI, and P-AC7-1 **10** times.
  - At `9f09b5b` alone, each passed 7 of 7.
  - L-31 is discharged.

---

## 40. The browser specs' ten runs (L-31) — 2026-10-12

**Added 2026-10-12, additively.** §39.6 recorded that §17's flakiness rule was
not met for the two browser tests. §17's rule:
> *"Every real-infrastructure and browser test in 4F.8 involves timing. Each
> is run ≥ 10 times and reported."*

The user chose option (a) of the completion record's §12.8: re-run the `e2e`
job at the PR's final head. This section records that, and supersedes §39.6's
last bullet.

### 40.1 Method

- **Head:** `9f09b5b`, PR #41's final head. No source, test, workflow or
  threshold changed for these runs, and no commit was made to trigger them.
- **The run:** `PR Checks` run
  [`38246972802`](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/38246972802),
  on `pull_request`, attempts 2–7.
  - Each was a **re-run of the `e2e` job alone**. The `checks` job in every
    attempt carries attempt 1's own timestamps, 12:07:20–12:13:01 UTC.
  - Each run is a fresh stack, with its own acceptance run id (`uuid4`), so
    every AC-7 path is never-observed.
  - The specs are configured `retries: 0`.
- **Who triggered them:** the user, by hand.
  - This session's GitHub integration was refused:
    `POST /actions/jobs/{id}/rerun` returned **HTTP 403 "Resource not
    accessible by integration"**, needing `actions=write`.
  - It was refused at 12:17, 12:19–12:20 and 13:14–13:15 UTC, before and
    after the user granted the permission.
  - No attempt was started from this session.
- **What counts as a success.** The spec's own `✓ … 1 passed` line in the job
  log, and the GitHub reporter's `1 passed` notice. A green step alone does
  not count: a spec whose inputs are missing *skips*, and its step is still
  green.

### 40.2 The attempts at `9f09b5b`

| Attempt | `e2e` job | Acceptance run id | P8 | AC-8 | P-AC8-1 | AC-7 latency | AC-7 samples (s) | P-AC7-1 | Revocation | Golden path |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `114803175834` | `2732616c34a9` | 67/67 | 55/55 | **✓** | 70/70 | 0.228–0.919 | **✓** | 10/10 | 20 passed |
| 2 | `114808685875` | `a819ce276ce5` | 67/67 | 55/55 | **✓** | 70/70 | 0.095–1.027 | **✓** | 10/10 | 20 passed |
| 3 | `114811346379` | `e7fa7de185ef` | 67/67 | 55/55 | **✓** | 70/70 | 0.114–0.880 | **✓** | 10/10 | 20 passed |
| 4 | `114814470987` | `3df70a33be19` | 67/67 | 55/55 | **✓** | 70/70 | 0.064–0.993 | **✓** | 10/10 | 20 passed |
| 5 | `114822584441` | `e825d45fbb0d` | 67/67 | 55/55 | **✓** | 70/70 | 0.276–0.876 | **✓** | 10/10 | 20 passed |
| 6 | `114825522817` | `d2eb180931e0` | 67/67 | 55/55 | **✓** | 70/70 | 0.270–1.011 | **✓** | 10/10 | 20 passed |
| 7 | `114828825494` | `f80e8c8858e5` | 67/67 | 55/55 | **✓** | 70/70 | 0.060–0.824 | **✓** | 10/10 | 20 passed |

The golden path also had 3 skipped in every attempt. Those are its own
by-design skips: the approval spec, and the two acceptance specs in that
invocation.

**No attempt failed. No step and no check failed in any of them.**

**AC-7, at `9f09b5b`: 70 samples, 0.060–1.027 s.** Every one was ≤ 5.0 s, and
none was discarded.
- N-3 passed 70 of 70. The 10 ms allowance was not changed.
- The signed gap, the harness's `before` minus the creation stamp, was
  −0.061 ms to +1.795 ms.
  - In attempt 3, one creation stamp fell **0.061 ms after** `before`.
  - That is inside the allowance, and N-3 passed.
- So the creation stamp does not always *precede* `before`, as §38.1 and
  §39.5's wording suggested. Their figures are unaffected.

**The revocation, in every attempt:**
- E-18: the companion ran as uid `1100` and got *"Permission denied"*.
  `capability-engine`'s `ls` returned 0;
- E-5 and E-6 passed.

**The N-16 mutation was not repeated.** Its evidence (§39.2–§39.4) is
unchanged.

### 40.3 The cumulative count of successful runs

Successes only. A run of the spec at a mutated head is counted only where the
mutation does not touch that spec.

| Spec | Successful CI runs | Where | Not counted |
|---|---|---|---|
| **P-AC8-1** | **11** | `3aab37f`; `dfb26f3` and `a1a6752` (N-16 removes the companion's override, which this spec does not use); `c04eaff`; `9f09b5b` attempts 1–7 | `3e44a19`: failed, F-4F8-20 |
| **P-AC7-1** | **10** | `3e44a19`, `3aab37f`, `c04eaff`; `9f09b5b` attempts 1–7 | `dfb26f3`, `a1a6752`: failed, as N-16 designs |

**At the final head alone, each spec passed 7 of 7.** §17's ≥ 10 is met for
both. **L-31 is discharged.** I-11 is met.

### 40.4 What this does not show

- **The PR reviewed, or a merge authorized.** 4F.8 is not complete until both
  have happened, and the merge itself.
- **It does not resolve:**
  - A-4F8-9 (F-4F8-10);
  - CF-9, CF-10 and CF-11;
  - F-4F8-12;
  - L-17.
- **Multi-replica dispatch.** It is not claimed.
