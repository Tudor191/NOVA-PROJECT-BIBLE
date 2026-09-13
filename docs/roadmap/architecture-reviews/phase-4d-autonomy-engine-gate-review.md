# Phase 4D — Autonomy Engine — Gate Review

**Milestone:** Phase 4D, the Autonomy Engine (Bible Part 14) and the `autonomy/` panel
**Branch:** `phase-4d`, head **`de6dbc979ada8b46b07de9bea195808f0a2a934d`**
**Base:** `f5ca9150b142b1a6f87bbbe9d74273014ad8a6fb` on `phase-4d`, itself cut from
`phase-4`'s merged head `eedb8ade956862cc9230a2ea5fa3c33c36391aed`
**TDD:** [`docs/design/phase-4/04-tdd-4d-autonomy-engine.md`](../../design/phase-4/04-tdd-4d-autonomy-engine.md)
**Date:** 2026-09-13
**Protocol:** [`docs/PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md)
read from `origin/main` at the start of this review and verified byte-identical —
sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`, 1131 lines

---

## 0. Read this section first

**The verdict is CONDITIONAL-GO, and the condition is evidential rather than
technical.** No CI run exists for this milestone at any SHA. Both workflows that
would produce one trigger on `pull_request` or a push to `main`
(`pr-checks.yml:15-18`, `build-and-scan.yml:6-9`); `phase-4d` was pushed and no
pull request was opened, because opening one was not authorized. Every gate
reported in §6 was therefore run **locally**, and is labelled as such. Nothing
here claims CI evidence it does not have.

**Three further things a reader should know before the detail:**

1. **Two TDD clauses were found to presuppose surfaces that do not exist**, and
   both are named rather than built around — §4.1 and §4.2. One is the
   conversational-trust read; the other is the origin of a suggestion. Neither
   blocks AC-5, and neither was resolved by inventing the missing surface.
2. **CF-9 is still OPEN by ratified decision** (D-4D-2). This review does not
   close it and does not reinterpret it.
3. **`action-engine` and `nova-contracts` are untouched** — verified by diff, not
   asserted: `git diff --name-only f5ca915..HEAD | grep -c "action-engine\|nova-contracts"`
   returns **0**. `ws-gateway` is untouched too: the same diff restricted to
   `services/ws-gateway/` is **0 lines**.

---

## 1. What was implemented

Four commits, linear, no merge commits:

| Commit | Slice |
|---|---|
| `eb48d0f` | The domain layer — levels, policy, permissions, trust, the decision pipeline, and 137 tests |
| `5eae4c2` | The `autonomy` Postgres schema, the `/v1/autonomy/*` REST surface, and the boundary controls |
| `152d347` | The `real_infra` tier, both CI matrices, the `api-gateway` route and the compose service |
| `de6dbc9` | The `autonomy/` panel, the AC-5 Playwright spec and its producer driver |

**Scope, against TDD §1's twelve deliverables:** all twelve are addressed. Items
8 (*"No Event Bus contracts"*) and 10 (*"CF-9: no implementation"*) are
deliverables whose content is a deliberate absence, and both are enforced by test
rather than left to review.

The engine was scaffolded with `tools/scaffold-engine.py`, which wired
`nova_autonomy_engine` into `pyproject.toml`'s `root_packages` and all four
import-linter contracts — no hand-editing of the contract lists.

---

## 2. Why each architectural decision was made

**`SELECTABLE_LEVELS` is a strict subset of `DEFINED_LEVELS`, as two separate
sets.** Collapsing them into one would make "defined" and "enabled" the same
idea, and decision D-1 turns on exactly that distinction: Level 2 is defined in
4D and enabled in 4F. `tests/unit/test_levels.py` asserts the strict-subset
relation directly, so a future edit that merges them fails.

**The level is applied at the Decide step, not as the first gate.** TDD §4.3's
table makes `deny` reachable at *every* level, Level 0 included. Gating on the
level first would report a policy denial at Level 0 as `observe_only`, hiding the
policy that actually refused. So the two denying gates run regardless of level,
and the level chooses between `observe_only` and `propose` only once nothing has
denied — which is where Bible Part 14 puts step 8.

**The trust input is a port the pipeline `await`s, not a value it is handed.**
That is what makes TDD §4.2's *"order is binding and must be asserted by test"*
an assertion about control flow rather than about a message string: a spy source
records whether it was consulted, and a policy denial leaves it unconsulted.
Asserting the order from a reason string would keep passing if the flow changed
underneath it.

**`PolicyEffect` has no `ALLOW`, and neither verdict type has an affirmative
field.** An `allow` effect can only matter where something would otherwise not
happen automatically — Level 2+, which 4D does not enable. Shipping it would ship
an effect with no reachable behaviour and invite a later reader to assume
auto-execution exists. `PermissionEvaluation` likewise carries only `denied`,
`reason` and `requires_approval`; there is no value it can hold that means "may
act unattended".

**`domain/risk.py` exists because `RiskLevel` is a `StrEnum`.** `"critical" >=
"low"` is `False` — the two most consequential tiers compare backwards. Every
risk comparison goes through the tier ordering rather than being open-coded at
each site, and `test_risk.py` demonstrates the naive form's inversion rather than
describing it.

**The decision log's foreign key is `ON DELETE RESTRICT`, and the
`relationship()` is declared on the parent.** 4C.2's `4eafa80` defect was
SQLAlchemy ordering unrelated mappers by name within a flush, emitting a child
INSERT before its parent; `decision_log` < `suggestion` alphabetically, so this
engine had the identical trap. It is designed out twice — the relationship *and*
an explicit `flush()` — because TDD §9 requires designing it out rather than
rediscovering it. `RESTRICT` rather than `CASCADE` so deleting a suggestion
cannot erase the record of the decision that produced it.

**The status transition is a conditional `UPDATE ... WHERE status = 'proposed'`,
not a read followed by a write.** A check-then-write would let two concurrent
approvals both observe `proposed` and both succeed.

**The cursor codec is its own module.** Three places must agree on the format
exactly — the Postgres repository that mints and seeks on it, the fake the
default tier runs against, and the API layer that turns a malformed one into a
422. A codec duplicated across three places is one that eventually differs in
one of them.

---

## 3. Tradeoffs considered

| Question | Options | Chosen, and why |
|---|---|---|
| How to surface a degraded trust source | (a) `score: null` only; (b) `null` plus a three-state status | **(b).** `null` alone cannot distinguish "no history yet" from "the source is unreachable", and reporting the second as the first is reporting a degraded upstream as an empty success — which TDD §16 control 12 forbids. Cost: one field beyond §5.2's sketch, disclosed in `models.py` |
| Where the conversational trust read lives | (a) add a `digital_twin.*` served subject; (b) a port with a degraded adapter | **(b)** — see §4.1. (a) needs a served subject and a `nova_contracts` payload in another engine, and a non-empty `PUBLISHABLE_SUBJECTS`, which D-4D-1 forbids |
| Whether to add a suggestion-creation route | (a) add `POST /v1/autonomy/suggestions`; (b) no route, disclose the gap | **(b)** — see §4.2. §8.1's table defines no such route, and the instruction was explicit that an endpoint must not exist merely because it would be convenient |
| Approving a suggestion a policy now denies | (a) allow it; (b) 409, suggestion stays proposed | **(b).** Bible Part 14: policies are *"absolute unless modified by the user"*, so a policy must hold against an approval authored before it. 409 rather than a new status code: it is a conflict with the system's current state, not a malformed request |
| Whether a refused decision is logged | (a) log only applied decisions; (b) log every attempt | **(b).** TDD §13: *"The decision log is append-only and records both attempts."* A log of successes is not a log of decisions |
| Whether trust gates | (a) deny below a threshold; (b) compute and record only | **(b).** Nothing executes at Levels 0-1, so there is no threshold for trust to gate. `satisfies_threshold` exists and is control-4-protected now so the fail-closed semantics of an unknown score are fixed before the milestone that first needs to gate on it writes them |
| Scaffold-generated `BoundEventBus` | (a) remove it; (b) bind it with two empty allow-lists | **(b).** Binding it makes "publishes and subscribes to nothing" a **runtime** guarantee: any future call raises `SubjectNotAllowedError` rather than succeeding against an unbound client |

---

## 4. Known limitations

### 4.1 TDD §5.3's Event Bus trust read is not implementable, and is not implemented

**The finding, verified against the repository rather than assumed:**

| Fact | Evidence |
|---|---|
| `digital-twin-engine` serves exactly **one** RPC subject | `digital_twin_engine/events/subscribed.py` — `digital_twin.preferences.get.request`. No `digital_twin.trust.*` subject exists anywhere |
| Its HTTP surface exposes **no** trust route | `api/preferences.py`, `api/proactive_policy.py`, `api/profile.py` — `GET /preferences`, `GET`/`PATCH /proactive-policy`, `GET`/`PATCH /profile`, `POST /reset` |
| `TrustMetric` is reachable only through its **own** repository | `DigitalTwinRepository.get_trust_metric`, over its own tables |
| `BoundEventBus.request()` checks the **publishable** allow-list | `nova_eventbus_sdk/boundary.py:100`. Any request/reply read needs `PUBLISHABLE_SUBJECTS` non-empty — which TDD §10 item 3 forbids and §16 control 8 requires to fail the suite |

TDD §5.3 says the read *"is an **Event Bus request/reply**"*. It is not, and
cannot be within this milestone's ratified boundary. **This is structurally the
same error D-4D-2 already identified and withdrew for CF-9** — a clause
presupposing a cross-engine surface that does not exist — and it is handled the
same way.

**Why this changes no behaviour.** TDD §13's first row already binds it:
*"`digital-twin-engine` unreachable → conversational input `None` → trust score
`None` → fail-closed. Panel shows 'insufficient evidence', never a number."*
`clients/conversational_trust.py` is that row, and it reports `UNAVAILABLE` with
the reason attached rather than `NO_DATA`, so control 12 is satisfied.

**Why it is not a stub.** `ConversationalTrustSource` is a port with real,
asserted semantics: the Trust Engine consumes a snapshot when one is supplied,
and `tests/unit/test_trust.py` drives every 2D-D field path — including all three
`None` paths — through a fake source. AC-3 is met on the consumption side. When a
transport exists, only `clients/conversational_trust.py` changes.

**The §4.1 diagram's `TrustMetric read (request/reply, §5.3)` edge is likewise
not built.** It is residue from before D-4D-1 and was not caught in the
correction pass; §7 of this review records the TDD reconciliation.

### 4.2 No shipped component produces a suggestion

D-4D-1 removed the Event Bus origin; TDD §8.1's endpoint table defines no
creation route. Together those leave the decision pipeline with **no production
caller that proposes**. This is disclosed rather than worked around, because
adding a route would be inventing production surface to make a test pass.

**What that costs, stated exactly:**

- In production the suggestion inbox is permanently empty, and the panel says so:
  *"no suggestion source is enabled in this release"*. That is TDD §12's
  healthy-empty-state rule, not a workaround.
- The pipeline is **not** dead code. It has two real production callers:
  `GET /v1/autonomy/suggestions` evaluates the gates for every stored suggestion
  (TDD §12's *"which gates passed"*), and `POST …/decide` re-evaluates them
  before permitting an approval.
- AC-5's Playwright spec obtains its suggestion from
  `tools/e2e_seed_autonomy_suggestion.py`, which runs the **real** pipeline with
  the real gates in their binding order and persists through the **real**
  repository in one transaction. Only the *trigger* is a stand-in — the same
  shape, and the same disclosure, as 4B's `e2e_request_risky_action.py`.

**This does not prove that NOVA proposes on its own initiative.** 4D builds the
decision surface, not the initiative surface (TDD §1.1), and no milestone has
built a producer. Recorded as a carry-forward in §13.

### 4.3 Other limitations

- **No CI evidence at any SHA** — §0, §11.
- **`real_infra` was never executed.** Docker is unreachable in this environment
  (`docker info` fails). The 16 `real_infra` tests **collect** cleanly and are
  wired into `real-infra-checks.yml`, but have never run. §8.
- **Playwright was never executed.** The AC-5 spec is written and wired; it has
  not run in a browser. §9's AC-5 row says so.
- **Prometheus still scrapes only `nova-core`** — carried forward unchanged from
  the 4C.2 Gate Review §13.3. 4D does not close it.
- **`ExecutionOutcomeSummary` is always empty**, by construction: nothing
  executes at Levels 0-1. Declared now rather than migrated in later, following
  2D-D's own reserved-field precedent.
- **Levels 3-5 are named and undefined.** `require_selectable` rejects them with
  a *different* reason from Level 2's, so the two answers stay distinguishable.

---

## 5. Technical debt introduced

**One item, and it is small.** `TrustScore` carries two fields beyond TDD §5.2's
sketch — `input_status` and `detail` — because §13's first row and §16 control 12
together require the degraded/no-data distinction to survive as far as the API,
and the score is the only place available to every reader of one. The deviation
is documented at the definition site.

**No other debt.** No `TODO` or `FIXME` was added; no test is skipped or xfailed;
no guard anywhere in the repository was weakened. The scaffold's two `TODO`
comments inside the empty allow-list literals are the scaffold's own and are
load-bearing as documentation of why the sets are empty.

---

## 6. Verification results — **all local, no CI**

Run against head `de6dbc9`, working tree clean:

| Gate | Command | Result |
|---|---|---|
| Workspace tests | `npx turbo run test --force` | **31/31 successful, `Cached: 0`**, **2,491 passing** |
| Repo tooling | `uv run pytest tools/tests -q` | **224 passed** |
| Workspace lint | `npx turbo run lint` | **31/31 successful** |
| Typecheck | `npx turbo run typecheck` | **5/5 successful** |
| `autonomy-engine` | `pytest -m "not real_infra" --cov=nova_autonomy_engine.domain` | **222 passed, 16 deselected** |
| Domain coverage | same | **99%** (350 stmts / 3 miss) against the 85% `fail_under` gate |
| `api-gateway` | `pytest -m "not real_infra"` | **88 passed** |
| `web-client` | `vitest run` | **199 passed** (12 files), of which **24** are the new panel suite |
| Import boundaries | `uv run lint-imports` | **7 contracts kept, 0 broken** |
| Compose validity | `python -c "yaml.safe_load(...)"` on all four changed YAML files | parses |
| Codegen drift | `uv run python codegen/generate_typescript.py` | **116 files, zero drift** — 4D adds no wire contract |

`autonomy-engine` test composition: 238 collected = **222 default tier** (166
unit, 38 integration, 18 contract) + **16 `real_infra`**.

---

## 7. Negative controls and flakiness

**All twelve of TDD §16's required negative controls were verified by removing
the property and observing the suite fail.** Each row names the mutation applied
and the first test that failed; every mutation was reverted and the suite returns
to 222 passed with a clean tree.

| # | Property removed | First failure |
|---|---|---|
| 1 | `permits_execution` → `True` | `test_decision_pipeline.py::test_a_proposal_and_its_log_row_share_one_subject_id` |
| 2 | `AutonomyLevel.ASSISTED` added to `SELECTABLE_LEVELS` | `test_autonomy_api.py::test_level_two_is_refused_as_defined_but_not_yet_enabled` |
| 3 | `correction_frequency is None` coerced to `0.0` | `test_trust.py::test_control_3_absent_correction_frequency_yields_no_score_not_zero` |
| 4 | `satisfies_threshold(None, …)` → `True` | `test_trust.py::test_control_4_an_unknown_score_never_satisfies_any_threshold[1.0]` |
| 5 | absent grant → `denied=False` | `test_autonomy_api.py::test_a_listed_suggestion_reports_which_gates_it_passes` |
| 6 | policy-deny branch disabled in the pipeline | `test_autonomy_api.py::test_approving_a_policy_denied_suggestion_is_refused_and_leaves_it_proposed` |
| 7 | `"autonomy.decision.made"` added to `PUBLIC_TOPICS` | `test_autonomy_boundaries.py::test_control_7_public_topics_is_unchanged_at_its_eighteen_exact_strings` |
| 8a | `PUBLISHABLE_SUBJECTS` made non-empty | `test_autonomy_boundaries.py::test_control_8_both_allow_lists_are_empty` |
| 8b | `SUBSCRIBABLE_SUBJECTS` made non-empty | same |
| 9 | `IdentityConfidencePolicy` model added to this engine | `test_autonomy_boundaries.py::test_control_9_no_identity_confidence_policy_exists_in_this_engine` |
| 10 | `from nova_action_engine…` added to `domain/risk.py` | `test_autonomy_boundaries.py::test_control_10_no_module_imports_another_engine` |
| 11 | `may_execute` field added to `PermissionEvaluation` | `test_permissions.py::test_control_11_the_verdict_type_can_express_only_denial_or_approval` |
| 12a | degraded trust source reports `NO_DATA` | `test_autonomy_api.py::test_control_12_a_degraded_trust_source_is_named_not_silently_empty` |
| 12b | readiness stops probing the database | `test_health.py::test_readiness_reports_not_ready_when_the_database_is_unreachable` |

**A precision failure found and fixed during this work, recorded because it is
the failure mode controls are prone to.** The first drafts of controls 9 and 10
and of the RBAC guard used substring search over source text, and **fired on this
engine's own docstrings** — the prose that explains *why* `IdentityConfidencePolicy`
stays in `action-engine` names it. A control that fires on its own rationale is a
control that gets loosened. They were rewritten to parse the AST and inspect
code only, with `_strip_docstrings` removing **every** bare string-literal
statement rather than only `body[0]`, because this codebase documents constants
and model fields with PEP 258 attribute docstrings.

**Anti-decoration checks.** `test_risk.py` asserts `RISK_ORDER` covers the
canonical enum exactly; `test_permissions.py` asserts the order tuple covers the
category enum exactly; `test_autonomy_boundaries.py::test_every_module_imports_cleanly`
guards against AST walks passing over a package that would not boot.

**Flakiness, protocol §9.2's ≥10× discipline:**

| Suite | Runs | Result |
|---|---|---|
| `autonomy-engine`, default tier | **10×** | 222 passed every run, 0.91–1.04 s |
| `autonomy-panel.test.tsx` (contains the no-polling timing assertion) | **10×** | 24 passed every run |

---

## 8. Real-infrastructure status

**Written and wired; never executed. Docker is unreachable in this environment**
(`docker info` fails), so this field cannot be filled by this review and is not
claimed.

`tests/integration/test_repository_real_postgres.py` — **16 tests, collect
cleanly** — covers the four things TDD §16 names, each chosen because 4C.2 proved
a fake repository cannot reach them:

1. **Transaction coupling**, including a direct test that the foreign key is
   real, so the ordering test means something.
2. **Append-only against the real `ON DELETE RESTRICT`** — deleting a suggestion
   raises rather than cascading the decision away.
3. **Keyset pagination across a timestamp tie**, where only the `id` tiebreaker
   makes the page boundary deterministic under a real index scan.
4. **The Alembic chain**, asserted against doc 07's column definition
   (`confidence` is `real NOT NULL`, `autonomy_level` `smallint NOT NULL`, and so
   on), plus that it creates no `action` schema and issues no `INSERT`.

`real-infra-checks.yml` gained the `autonomy-engine` matrix entry, so this tier
runs on the first pull request.

---

## 9. Acceptance criteria

TDD §17's twelve criteria plus AC-5:

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Levels 0-2 defined with Part 14's vocabulary; 0-1 selectable; 2 disabled | **Met** | `test_levels.py` (all six names verbatim); `test_autonomy_api.py` (`[(0,True),(1,True),(2,False)]`); `autonomy-panel.test.tsx` (disabled attribute present); control 2 |
| 2 | No execution path exists at Levels 0-1 | **Met** | Control 1; plus an exhaustive sweep of 10 categories × 5 risks × 6 ceilings × 2 levels = **600 decisions**, none reaching `EXECUTE` |
| 3 | Trust Engine consumes 2D-D's `TrustMetric`; does not re-derive it; `None` stays `None` | **Met on the consumption side; the transport does not exist** | `test_trust.py` drives every 2D-D field path through a fake source; controls 3 and 4. §4.1 records that no read surface exists, so no shipped adapter returns a snapshot |
| 4 | Policy Engine: deny wins, evaluated before permissions and trust | **Met** | `test_policy.py`; `test_decision_pipeline.py` asserts the spy source was never consulted on a policy deny; control 6 |
| 5 | Permission Matrix: ten categories, absent grant fails closed | **Met** | `test_permissions.py` asserts the ten verbatim and in order; control 5 swept over every category × risk |
| 6 | `autonomy.decision_log` append-only, matching doc 07 | **Met by construction; `real_infra` half unexecuted** | `test_repository_contract.py` asserts the forbidden method names absent from the Protocol, the Postgres repository **and** the fake; the constraint half is in the unexecuted `real_infra` tier (§8) |
| 7 | One transaction per logical operation | **Implemented; verification unexecuted** | Source: one `session.begin()` per method, coupled rows inside it. The proof needs real Postgres (§8) |
| 8 | `/v1/autonomy/*` fronted 1:1 by `api-gateway` | **Met** | One `UpstreamRoute`; `api-gateway`'s own allow-list tests updated to name the new prefix, so the table still cannot grow silently. 88 passed |
| 9 | Security boundaries preserved; `PUBLIC_TOPICS` byte-identical; both allow-lists empty | **Met** | `git diff f5ca915..HEAD -- services/ws-gateway/` is **0 lines**; controls 7, 8, 11 |
| 10 | CF-9 correctly left open | **Met** | Controls 9 and 10; no route, no model, no table, no `action-engine` change (diff count 0) |
| 11 | Panel renders all four widgets; no polling; no fabricated data | **Met** | 24 vitest cases, including a no-polling assertion over a 250 ms window and an empty-inbox state that names its own cause |
| 12 | Degraded upstream → never an empty success | **Met** | Controls 12a and 12b |
| **AC-5** | *"An autonomous suggestion at Autonomy Level 1 is **proposed, not executed**, is visible in the Autonomy panel, and executing it requires explicit user approval."* | **Met at the unit and integration tiers; the browser tier is written and unexecuted** | See below |

### AC-5, clause by clause

| Clause | Discharged by | Status |
|---|---|---|
| *"at Autonomy Level 1"* | `test_decision_pipeline.py`: L0 yields `observe_only`, L1 yields `propose` | **Met** |
| *"is proposed, not executed"* | Control 1, plus the 600-decision sweep. `DecisionResultResponse.executed` is `False` and says so in a field rather than by absence | **Met** |
| *"is visible in the Autonomy panel"* | `autonomy-panel.test.tsx` renders a real suggestion from a real response shape, with its risk and gate report | **Met** |
| *"executing it requires explicit user approval"* | `POST …/decide` is the only transition out of `proposed`, asserted against the OpenAPI document: the eleven published `/v1/autonomy` operations are exactly §8.1's table. 409 on double-decide; 409 on approving what a gate denies, leaving it `proposed`; 422 on an empty body | **Met** |
| End-to-end in a browser | `tests/e2e/autonomy-suggestion.spec.ts`, wired into `pr-checks.yml` with its producer driver | **Written, never executed** |

---

## 10. Security sweep

| Control | Result |
|---|---|
| Browser never reaches NATS (ADR-006 / doc 09 §6) | Unchanged. `ws-gateway` untouched — 0 diff lines |
| `PUBLIC_TOPICS` | **Byte-identical.** 18 exact strings, zero wildcards. Control 7 also demonstrates the mechanism it protects against: `fnmatchcase("autonomy.decision.made", "autonomy.*")` is `True`, so a wide form would subscribe the gateway to every future `autonomy.*` subject |
| Engine allow-lists | Both **empty frozensets**. Stronger still: `test_control_8_this_engine_never_calls_the_bus_at_all` asserts no `publish`/`subscribe`/`request`/`serve`/`open_stream` call exists anywhere in the package, so there is no site at which a subject could be introduced |
| `autonomy.*` namespace | **Unclaimed.** No registered payload (`known_subjects()` sweep), no `register_payload` in this engine, and `action-engine`'s `test_fork_e2_namespace_boundary_never_uses_autonomy_prefix` **still passes, unmodified** |
| `/internal/*` unroutable | Unchanged — `RouteTable` refuses any prefix outside `/v1/` at construction |
| Single trusted user (ADR-025, D-3) | Preserved. `Settings`' only identity field is `primary_user_id`, asserted by test. No role, RBAC, tenant or scope concept — asserted over code with docstrings stripped |
| No 4D setting can weaken `action-engine`'s gate | Control 11, both halves: the verdict type carries no affirmative field, and the 600-decision sweep reaches no `EXECUTE`. 4D calls `action-engine` at no point |
| CF-9 fail-closed defaults | Untouched. `action-engine` diff is 0 files; the migration issues no `INSERT` and creates no `action` schema |
| New dependencies | **None.** `autonomy-engine` declares only packages already in the workspace (`sqlalchemy`, `asyncpg`, `alembic`, `nova-service-kit` and the scaffold's four) |

---

## 11. CI and branch evidence

| Item | Value |
|---|---|
| Branch | `phase-4d`, head `de6dbc979ada8b46b07de9bea195808f0a2a934d`, pushed to `origin` |
| Commits | 4, linear, **zero merge commits** |
| Base | `f5ca915` on `phase-4d` (the TDD correction), itself descended from `phase-4`'s merged head `eedb8ad` |
| Working tree | Clean; nothing unpushed |
| Pull request | **None opened.** Not authorized |
| **CI status** | **NONE — no run exists at any SHA on this branch.** Verified through the workflow-runs API filtered to `head_branch: phase-4d`: `total_count: 0`. Both workflows trigger only on `pull_request` or a push to `main`. **This is condition C-1** |
| `main` | Untouched, still `7e273e6` |
| `phase-4` | Untouched |

---

## 12. Compatibility with the NOVA Project Bible

| Bible Part 14 section | 4D |
|---|---|
| Autonomy Levels | **All six named verbatim.** 0-2 defined, 0-1 selectable |
| Permission Matrix | **All ten categories verbatim and in Part 14's order**, order pinned separately from enum membership so a reorder fails |
| Risk Classification | **Reused, never redefined.** `nova_contracts.events.planning.RiskLevel`, whose docstring cites Part 14 lines 271-279 |
| Policy Engine | *"Policies override autonomous decisions… absolute unless modified by the user"* — deny wins, and a policy holds against an approval authored before it |
| Trust Engine | *"NOVA maintains a dynamic trust score for every category"* — per category, not one global number. *"Trust is earned. Not assumed"* — unknown is fail-closed, never a default number |
| The Autonomy Principle (11 steps) | The gating subset 5, 6, 8 and 9's **approval branch only**; the other seven named as deferred in TDD §1.1 rather than silently narrowed |
| Explanation Engine | Reduced to what 4D can honestly provide — *what policies were applied, what risks were considered* — with every consulted policy recorded, not only those that fired |
| Adaptive Autonomy, Initiative Engine, Proactive Assistance, Interruption Awareness, Objective Monitoring, Self Scheduling, Multi-Agent Autonomy, Governance tiers, Reversibility | **Deferred and disclosed** (TDD §1.1) |
| *"As NOVA demonstrates reliable performance, **the user may** gradually increase autonomy"* | Level changes are a user action. Nothing in `domain/trust.py` writes `AutonomyLevelSetting` |

No Bible part is contradicted. No terminology was invented: the level names,
category names and risk tiers are Part 14's own strings.

---

## 13. Gaps, ambiguities, and deferred findings

### 13.1 New carry-forwards this milestone creates

| ID | Item | Disposition |
|---|---|---|
| **CF-10** | **No read surface exists for 2D-D's `TrustMetric`.** TDD §5.3 presupposed an Event Bus request/reply; `digital-twin-engine` serves no trust subject and exposes no trust route, and `BoundEventBus.request()` gates on the allow-list D-4D-1 requires to stay empty | **OPEN.** The conversational trust input is reported `UNAVAILABLE` with its reason. Closing it needs a decision about where the read surface belongs — a served `digital_twin.*` subject with its `nova_contracts` payload, or an HTTP route — both of which modify another engine and lie outside 4D's ratified boundary |
| **CF-11** | **No component produces a suggestion.** D-4D-1 removed the Event Bus origin; §8.1 defines no creation route. The inbox is permanently empty in production | **OPEN.** 4D builds the decision surface, not the initiative surface (TDD §1.1). The Initiative Engine is the natural owner |
| **CF-12** | **`real_infra` and Playwright were never executed for 4D.** Docker unreachable locally; no CI run exists | **OPEN, and identical in kind to condition C-1.** Both tiers are written and wired; the first pull request runs them |

### 13.2 Carried forward unchanged, not closed by 4D

- **CF-9** — ADR-032 point 2 has no policy write path. **Still OPEN** by ratified
  decision D-4D-2. 4D was the routed surface and declines to close it on the
  grounds TDD §11.2 establishes against the repository.
- **AC-4 clauses 2 and 3** — Deferred by explicit user approval of 2026-09-07.
  **Untouched.** 4D adds no model provider.
- **4C.1 has no Gate Review**; **Phase 4A has no Gate Review or health record**;
  **`README.md` has no Phase 4 status line** — Phase 4 closure obligations,
  recorded in Phase 4C's health record, not 4D's.
- **Over-broad `communication.*` / `personality.*` bus patterns** — 4D adds no
  wildcard and does not widen them.
- **Prometheus scrapes only `nova-core`** — carried forward; TDD §14.
- **CF-8's six Phase 3E narrowings** — unchanged.
- **SLOC methodology Option A / Option B** — open, undecided, not decided here.

### 13.3 TDD reconciliation this review records rather than performs

Two clauses of the 4D TDD are contradicted by the repository and by D-4D-1:

1. **§5.3** states the trust read *"is an Event Bus request/reply"*. It cannot
   be — §4.1.
2. **§4.1's diagram** draws a `TrustMetric read (request/reply, §5.3)` edge two
   lines after stating *"REST only, no Event Bus edge in either direction"*.

Both are residue from before D-4D-1 and were missed by its correction pass, which
touched §§0, 1, 3, 4.1, 8.1, 8.2, 10, 11, 12, 13, 16, 17, 19 and 20 but **not**
§5.3. **This review records the contradiction; it does not edit the TDD**, because
a TDD correction is a documentation decision of the same kind D-4D-1 and D-4D-2
were explicitly ratified as, and it is offered for ratification rather than
applied silently. No implementation depends on the outcome: §13's binding
behaviour is what shipped either way.

---

## 14. Documentation this review is accompanied by

| Document | Change |
|---|---|
| This Gate Review | New |
| [`docs/project-health/phase-4d.md`](../../project-health/phase-4d.md) | New — the 23-field record |
| [`docs/project-health/project-health-master.md`](../../project-health/project-health-master.md) | 4D row appended |
| [`docs/roadmap/ENGINEERING_ROADMAP.md`](../ENGINEERING_ROADMAP.md) | 4D row corrected as a living reference (protocol §6.3) |

**No historical section of any document was rewritten.** Every superseded figure
stays as written for its own head.

---

## 15. Gate verdict

### **CONDITIONAL-GO**

Against protocol §3.2's eleven conditions:

| # | Condition | Assessment |
|---|---|---|
| 1 | Scope delivered as specified | **Yes.** All twelve TDD §1 deliverables, two of which are deliberate absences enforced by test |
| 2 | Acceptance criteria met | **Eleven of twelve fully Met.** #3 is met on its consumption side with its transport absent (§4.1); #6 and #7 have unexecuted `real_infra` halves. AC-5 is met at unit and integration tier, unexecuted in a browser |
| 3 | No regression | **Yes.** 31/31 packages green locally; `action-engine`'s reservation test still passes unmodified; `ws-gateway` 0 diff lines |
| 4 | Tests adequate, negative controls demonstrated | **Yes.** All twelve controls verified by removing the property and observing failure (§7); flakiness ≥10× on both timing-sensitive suites |
| 5 | Coverage gate | **Yes.** 99% domain against the 85% gate |
| 6 | **CI green against the exact head SHA** | **NO. No CI run exists** — condition **C-1** |
| 7 | Security controls preserved | **Yes**, and strengthened: the no-bus-call assertion is a stronger form than the allow-list check alone |
| 8 | Architecture boundaries respected | **Yes.** `lint-imports` 7/7; no engine import; domain layer framework-free, asserted by test |
| 9 | Documentation honest and current | **Yes**, including two TDD contradictions recorded rather than papered over |
| 10 | Deferred obligations ledgered | **Yes.** §13, with three new carry-forwards |
| 11 | Branch hygiene | **Yes.** Linear, no merge commits, `main` and `phase-4` untouched, nothing force-pushed |

### Conditions

| ID | Condition | Status |
|---|---|---|
| **C-1** | **CI must run green against the exact head SHA.** No run exists, because both workflows require a pull request and none was opened. This is the only condition of the eleven that is unmet | **OPEN.** Discharged by opening a pull request and recording the Check Run result against the head SHA |
| **C-2** | **The `real_infra` tier must execute.** 16 tests written and wired; Docker unreachable locally. 4C.2's history is the reason this is a condition and not a note: the first real-database run of that milestone found two defects no Docker-free gate could catch | **OPEN.** Discharged by C-1's run, which includes the `autonomy-engine` matrix entry |
| **C-3** | **The AC-5 Playwright spec must execute.** Written and wired with its producer driver; never run in a browser | **OPEN.** Discharged by C-1's run |
| **C-4** | **TDD §5.3 and the §4.1 diagram need reconciling** with D-4D-1 and with the repository (§13.3) | **OPEN.** A documentation decision, offered for ratification rather than applied. No implementation depends on it |

**Why CONDITIONAL-GO and not GO.** Protocol §3.2 condition 6 is unmet, and C-2
and C-3 mean two of the three test tiers this milestone defines have never
executed. **Why not NO-GO.** Nothing is known to be broken: every gate that
*could* run locally is green, all twelve negative controls are demonstrated, and
the three unexecuted items are unexecuted for one environmental reason — no pull
request exists — which a single authorized action resolves.

**This verdict is not to be read as GO.** Protocol §2.1's rule stands
unaltered: partially met is not met. The four conditions above are open, and none
of them is an approved deferral.

---

## 16. Project Metrics

| Metric | Value |
|---|---|
| Production SLOC, comparable scope (`services/*/src` + `packages/*/src` + `services/*/alembic/versions`) | **34,413** (base `f5ca915`: 32,948 — **+1,465**) |
| Production SLOC, 4C.2's wider scope (adds `agent-os/*/src`, `agent-os/*/alembic/versions`, `agents/*`) | **39,754** (base: **38,289**, which reproduces the 4C.2 health record exactly — **+1,465**) |
| Production SLOC, full scope (also `apps/*/src`) | **43,058** (base: 40,974 — **+2,084**) |
| SLOC tool | **`cloc` v2.06** — same tool and version as Phase 4B's and 4C.2's closure passes, so the series continues comparably. The `scc` series (2D-B → 2D-C) remains separate and non-comparable |
| 4D's own footprint (engine + panel + entity + driver + specs) | 49 files, **4,193 code lines**, 2,402 comment lines |
| Diff vs base | 76 files changed, +8,149 / −23 |
| Files touched outside `autonomy-engine` | 17, all additive wiring: 3 CI workflows, 4 `infra/docker`, 5 `api-gateway`, 3 `apps/web-client`, `pyproject.toml`, `uv.lock` |
| Tests, workspace | **2,491 passing** via turbo + **224** `tools/tests` = **2,715 passing, 0 failing** |
| Tests, `autonomy-engine` | 238 collected: **222 default** (166 unit, 38 integration, 18 contract) + **16 `real_infra`** |
| Domain coverage | **99%** (350 statements, 3 missed) |
| Negative controls | **12 of 12 demonstrated** by property removal |
| Flakiness runs | 10× engine suite, 10× panel suite — 0 failures |
| Import contracts | 7 kept, 0 broken |
| Codegen | 116 TypeScript files, **zero drift** — 4D adds no wire contract |
| New Event Bus subjects | **0** |
| New `PUBLIC_TOPICS` entries | **0** |
| New dependencies | **0** |
| New `/v1` prefixes at the gateway | **1** (`/v1/autonomy`) |
| Database tables added | 5, all in the new `autonomy` schema; 0 existing tables altered |

---

## 17. Definition of Done — the ten items

| # | Item | Status |
|---|---|---|
| 1 | Code implemented to the TDD | **Yes**, with two TDD clauses found unimplementable and recorded (§13.3) |
| 2 | Tests written at every tier the TDD names | **Yes** — 222 default, 16 `real_infra`, 24 vitest, 2 Playwright. Two tiers unexecuted (C-2, C-3) |
| 3 | Negative controls demonstrated | **Yes**, 12/12 |
| 4 | Coverage gate met | **Yes**, 99% vs 85% |
| 5 | Lint, typecheck, import boundaries green | **Yes**, 31/31 · 5/5 · 7/7 |
| 6 | CI green at head | **No** — C-1 |
| 7 | Security controls verified preserved | **Yes** (§10) |
| 8 | Documentation written and honest | **Yes**, including this review's own limitations |
| 9 | Deferred obligations ledgered | **Yes** (§13), three new carry-forwards |
| 10 | Branch hygiene | **Yes** |

---

## Sign-off

Phase 4D delivers the Autonomy Engine's decision surface — Bible Part 14's
Autonomy Levels, Policy Engine, Permission Matrix, Trust Engine and append-only
decision log — plus the `autonomy/` panel and the `/v1/autonomy/*` REST surface,
with **no Event Bus contract, no `PUBLIC_TOPICS` change, no new dependency, and
no modification to `action-engine`, `nova-contracts` or `ws-gateway`**.

All twelve negative controls TDD §16 requires are demonstrated by removing the
property and watching the suite fail, not by being declared. Two TDD clauses
turned out to presuppose surfaces the repository does not have; both are named,
neither is built around, and the fail-closed behaviour §13 specifies is what
shipped.

**Verdict: CONDITIONAL-GO**, with four open conditions — C-1 (no CI run exists),
C-2 (`real_infra` unexecuted), C-3 (Playwright unexecuted) and C-4 (a TDD
reconciliation offered for ratification). C-1 is the root of the first three, and
one authorized action resolves it.

**Nothing is merged.** `phase-4d` is pushed and unmerged; `phase-4` and `main`
are untouched.
