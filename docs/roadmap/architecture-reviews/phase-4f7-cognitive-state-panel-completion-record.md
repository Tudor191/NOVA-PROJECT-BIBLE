# Phase 4F.7 — Slice Completion Record
## The read-only Cognitive State panel: `/v1/cognitive-state`, sensor state through an existing subject, and deployment

**Date:** 2026-09-26
**Slice:** 4F.7 (TDD 4F §18, as amended by §24: 4F.7 → 4F.P → 4F.8)
**Branch:** `phase-4f7`. Implementation at **`bf0426d035f4a93a4433475e390e4a8f31f8b07e`**
(the last commit touching code or tests). Documentation commits follow it (§7.1).
**Base:** `phase-4` at **`4e19ed19876f2c76dd6f6591b1aa9cc778dd2e89`**, **unchanged by this slice**
**`main`:** **`7e273e62e942ecd5528ca807e65933d6bb675669`**, **untouched**
**PR:** `phase-4f7 → phase-4`, opened after this record is pushed. Its number,
and CI at its head, are recorded in the PR itself and in the implementation
report; **not merged**.
**Protocol:** [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md),
sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`,
1131 lines. Re-read in full from `origin/main` in this session; byte-identical
to the copy 4F.6 used.
**TDDs:** [TDD 4F.7](../../design/phase-4/11-tdd-4f7-cognitive-state-panel.md),
authoritative, including **§28** (A-4F7-1 and A-4F7-2, RATIFIED). Also
[TDD 4F](../../design/phase-4/06-tdd-4f-companion-and-cognitive-state.md) §24
(RS-1 … RS-11, RATIFIED) and [TDD 4F.6](../../design/phase-4/10-tdd-4f6-initiative-trigger.md).

---

## 0. What this document is, and is not

**This is a Slice completion record. It is not a Gate Review.** Protocol §0.1
gives a Significant Slice categories **1, 2, 8, 9, 10, 11, 13 and 14 in full**,
and categories **3–7 and 12 as a deferred-obligations ledger**. So this record
issues **no GO / CONDITIONAL-GO / NO-GO verdict**. 4F's Gate Review is **L-1**,
owned by 4F closure after 4F.8.

**Phase 4F is NOT complete.** 4F.P and 4F.8 have not started. **Completing this
slice does not authorize starting 4F.P.**

### 0.1 Branch shape — disclosed

`phase-4f7` was created from **`origin/phase-4` @ `4e19ed1`**, as instructed. The
ratified TDD 4F.7 did not exist on `phase-4`: it lived in two documentation-only
commits, `cbf2b34` (RS-1 … RS-11 ratified; TDD 4F.7 prepared) and `598bbc3`
(A-4F7-1 and A-4F7-2 ratified), on the documentation session branch. Following
4F.6's precedent, `phase-4f7` was **fast-forwarded** (`git merge --ff-only`, no
merge commit) through those two commits before any implementation. So the PR
carries the ratified TDD and its implementation together. **No history was
rewritten, squashed, rebased or force-pushed**, and the branch's inherited
upstream (`origin/phase-4`) was unset before the first push so that no push
could land on `phase-4`.

### 0.2 Decisions in force

- **RATIFIED:** RS-1 … RS-11 (TDD 4F §24), A-4F7-1 and A-4F7-2 (TDD 4F.7 §28).
- **PROPOSED, recommended defaults adopted** (TDD 4F.7 §20; the implementation GO
  did not change them), each disclosed here:
  - **A-4F7-3 (a):** fetch on mount plus an explicit Refresh; no polling, no
    realtime;
  - **A-4F7-4 (a):** `nova-service-kit` declared, `create_engine` /
    `create_session_factory` used;
  - **A-4F7-5 (a):** the e2e job adds `cognitive-state-engine` only, with no seed;
  - **A-4F7-6:** **not applied.** The instruction was explicit: *"Do not silently
    repair unrelated 4F.1 controls during this implementation."* Control 11's
    vacuous schema check is untouched and reported separately (§8.1, F-4F7-1).

---

## 1. Status

**Implemented, and verified locally, against every positive criterion
(P-1 … P-26 with P-10′) and every negative control (M1 … M12, M13′, M14 … M17)
of TDD 4F.7 §16 and §28.4.** Real-infrastructure tests ran against substitute
local PostgreSQL 16 and NATS/JetStream, because Docker is unavailable here
(§6). The Playwright spec (P-21) and the image builds are **CI-only**.

### 1.1 The slice's exit criterion

TDD 4F §24's 4F.7 row: *"Only §4.1's row 'visibly … in the panel': the panel
renders the normalized sensor state actually reported."* It is proven by a chain
whose every link runs production code over real infrastructure or real
rendering, with the joins at the registered contract and at the served JSON:

1. a real `perception-engine` lifecycle call → one outbox row → real dispatch →
   real NATS (P-16);
2. a report of that contract, bound as `perception-engine` binds its bus →
   `cognitive-state-engine`'s production subscription → real Postgres → served
   by `GET /v1/cognitive-state/sensors` over a real socket (P-15);
3. that body, parsed by the panel's own strict schema → rendered as the
   lifecycle state with *"last reported …"* (P-18), and in a real browser, panel
   = gateway body (P-21, CI).

No single test runs both engines' production code, because control 7 forbids one
engine's tests importing another (4F.6's precedent). A real sensor report
rendered in a browser is AC-7's demonstration and belongs to 4F.8 (A-4F7-5).

---

## 2. Category 2 — acceptance criteria

Sources consulted: TDD 4F.7 §16 and §28.4 (the criteria), TDD 4F §24's 4F.7 row
and `00-master-scope.md` l.939/l.1108 (the slice's exit criterion),
`ENGINEERING_ROADMAP.md` (no 4F.7-specific criterion), and the in-session
instruction (read-only; no new subject; no `PUBLIC_TOPICS` or registry change;
exactly three `GET`s; no invented fields; sensors from the persisted table;
exact vocabulary; unknown values not stored or returned; drift test; no 4F.P
work; only the `sensor_state` migration).

| # | Criterion (abridged from the TDD) | Status | Evidence |
|---|---|---|---|
| P-1 | Three routes, `GET`-only, the only `/v1/cognitive-state` operations; every other method 405 | **Met** | `tests/contract/test_phase_4f7_boundaries.py::test_p1_exactly_three_get_operations_under_the_prefix`, `::test_p1_no_operation_takes_a_parameter_or_a_body` (served OpenAPI); `tests/unit/test_cognitive_state_api.py::test_every_other_method_is_405` (12 cases) |
| P-2 | Identity server-side: real rows for the primary user and a second UUID; only the first returned, also with `?user_id=`; no `user_id` parameter | **Met** (local real-infra; CI pending) | `tests/integration/test_cognitive_state_api_real_infra.py::test_p2_only_the_primary_users_thoughts_are_served`; unit `test_a_caller_supplied_user_id_is_ignored` |
| P-3 | Empty store returns empty; `capacity` present | **Met** | real-infra `test_p3_an_empty_store_serves_empty_bodies`; unit `test_an_empty_store_serves_empty_lists_and_nothing_synthesized` |
| P-4 | Every Part 6 field, including a `null` `estimated_completion` and all three relation lists | **Met** | real-infra `test_p4_p8_real_rows_serialize_field_for_field`; unit `test_a_thought_serializes_with_every_part_6_field`, `test_not_estimated_is_null_never_a_date` |
| P-5 | Five layers serialize as Part 6 values | **Met** | unit `test_each_attention_layer_serializes_as_its_part_6_value` (5 cases) |
| P-6 | Focus equals `select_focus` over the same real rows; capacity, eligibility, deterministic order | **Met** | real-infra `test_p6_focus_is_select_focus_over_the_same_rows` (cap excludes one, three non-focusable excluded, a priority tie ordered by `thought_id`); unit `test_focus_is_select_focus_over_the_users_thoughts` |
| P-7 | Empty `signals_used` returned as `[]` and labelled in the panel | **Met** | unit `test_signals_used_is_returned_empty_not_hidden`; web `cognitive-state-panel.test.tsx > Focus > shows score and capacity, and labels an empty signals_used honestly (P-7)` |
| P-8 | `ProposedAction` serialized when present, `null` when absent; SQL `NULL` → `null` | **Met** | real-infra `test_p4_p8_…` (independent SQL shows `IS NULL`); unit `test_a_proposed_action_serializes_verbatim_as_a_proposal` |
| P-9 | No response field named status, outcome, decision, `subject_id`, triggered, executed, executing; the proposal block uses none of *triggered, decided, approved, executing, executed, dispatched* | **Met** | `test_p9_no_response_model_carries_a_decision_or_trigger_field`, `test_p9_the_sensor_state_enum_is_the_six_lifecycle_values`; web `… > renders a proposal as a proposal, and nothing about it as acted on` |
| P-10′ | Exactly the six `SensorState` values accepted and returned unchanged; `healthy`, `unhealthy`, `unrecognized`, `Running`, `" running"`, `""`, `degraded` rejected, nothing written, prior record unchanged | **Met** | `tests/unit/test_sensor_state.py` (six accepted; ten rejected, incl. `RUNNING`, `"running "`, `stopping`); `tests/unit/test_sensor_health_handler.py::test_an_unknown_status_is_not_stored_and_is_logged`, `::test_an_unknown_status_leaves_the_previous_known_state_unchanged`; real-infra `test_an_unknown_status_leaves_the_stored_record_unchanged` |
| P-11 | `SUBSCRIBABLE_SUBJECTS == {"perception.sensor.health_changed"}`, retargeting `test_boundaries.py` with its wording preserved; the real subscription is live | **Met** | `tests/contract/test_boundaries.py::test_the_subscribe_allow_list_is_exactly_the_sensor_health_subject` (original preserved in its docstring); P-15 |
| P-12 | Perception publishes on the four existing call-site groups, one event with the new state each; a no-op reports zero | **Met** | `perception-engine/tests/integration/test_sensor_lifecycle_call_sites.py` (startup, revocation, observation failure ×2, shutdown, two no-op cases); `tests/unit/test_sensor_lifecycle.py` (real sensor classes; four no-op cases) |
| P-13 | `PUBLIC_TOPICS` byte-identical; no new subject; registry 120 at runtime | **Met** | `test_p13_the_registry_holds_one_hundred_and_twenty_subjects`, `test_p13_public_topics_are_unchanged_at_eighteen`, `test_p13_this_engines_allow_lists_are_exactly_the_ratified_two`; `git diff --stat 4e19ed1 HEAD -- services/ws-gateway packages` is empty |
| P-14 | No autonomy route, no write route; `api/` and `main.py` never import or call `promote_thought`, `upsert_thought`, `move_layer` | **Met** | `test_p14_nothing_on_the_served_path_writes_a_thought_or_promotes` (4 modules), `test_p14_promote_thought_still_has_no_production_caller`, `test_no_perception_or_autonomy_route_is_served`, `test_the_api_declares_only_get_routes_in_source` |
| P-15 | Real bus, consumer half: a bus bound as `perception-engine` → production lifespan subscription → independent SQL → `GET /sensors`; redelivery and older reports change nothing | **Met** (local real-infra; CI pending) | `tests/integration/test_sensor_state_real_infra.py::test_p15_a_real_report_reaches_the_table_and_the_api`, `::test_p15_redelivery_stale_and_unknown_reports_change_nothing_over_the_real_bus` (row **and** tuple version `xmin` unchanged, §5.1) |
| P-16 | Real bus, producer half: a real lifecycle call → one outbox row by independent SQL → real `dispatch_ready_events` → real subscriber, `event_id == row id`, right subject, lifecycle status | **Met** (local real-infra; CI pending) | `perception-engine/tests/integration/test_sensor_health_real_infra.py::test_p16_a_real_lifecycle_call_travels_the_outbox_to_a_real_subscriber`, `::test_p16_a_no_op_transition_writes_no_row` |
| P-17 | Gateway: the route table fronts the prefix; the exact prefix-set test retargeted to nine with the prior set preserved; `GET` forwarded 1:1 with path and query; a `POST`'s 405 returned unchanged; `/internal/*` never forwarded | **Met** | `api-gateway/tests/integration/test_gateway.py::test_the_route_table_fronts_no_other_agent_os_component` (nine; the eight kept), `::test_cognitive_state_gets_forward_one_to_one`, `::test_cognitive_state_query_is_forwarded_intact_not_interpreted`, `::test_a_cognitive_state_write_is_forwarded_and_its_405_comes_back_unchanged` (×4 methods), `::test_the_cognitive_state_engines_internal_surface_is_never_forwarded`, `::test_cognitive_state_requires_a_session`; `tests/unit/test_domain.py` (3 new) |
| P-18 | Panel rendering over contract-validated fixtures: each empty state; layer grouping; every Part 6 field; the `signals_used` label; the proposal wording; each of the six sensor states plus one out-of-vocabulary fixture rendering the degradation notice; the error path; Refresh re-issues `GET`s only | **Met** | `apps/web-client/tests/unit/cognitive-state-panel.test.tsx`, 20 tests. Every fixture is parsed by `cognitiveStateSchemas` first |
| P-19 | Web boundary: only `gatewayFetch`; only the three `GET`s; no mutating request, no `refetchInterval`, no `setInterval`, no realtime subscription; `routing.test.ts` expects eleven panels | **Met** | `security-boundary.test.ts > the Cognitive State surface is read-only and adds no boundary (TDD 4F.7 P-19)` (6 tests); `routing.test.ts` (eleven, plus lazy-load and nesting) |
| P-20 | `test_compose_migrations.py` and `test_e2e_stack_completeness.py` pass unchanged; `docker compose … config --quiet` valid | **Met** | `uv run pytest tools/tests -q` → **300 passed**, `tools/` unchanged; `docker compose -f infra/docker/docker-compose.local.yml config --quiet` → exit 0 |
| P-21 | Playwright against the real stack: panel loads through the gateway; content equals the three `GET` bodies; each empty state exactly | **Cannot be verified in this environment** (no Docker daemon). **CI-only** | `apps/web-client/tests/e2e/cognitive-state-panel.spec.ts` (3 tests; typechecked and linted locally); `pr-checks` e2e job |
| P-22 | No vocabulary drift: parse `perception-engine`'s `domain/sensor.py` as text; equality in order; anti-vacuity (six) | **Met** | `tests/contract/test_sensor_vocabulary_drift.py` (2 tests) |
| P-23 | Every enqueued `status` is in `get_args(SensorState)` and equals `sensor.state()` after the call | **Met** | `test_sensor_lifecycle.py::test_p23_every_status_is_a_sensor_state_value_equal_to_the_state_after` (3 sensors); `test_startup_reports_each_sensors_initialized_then_running` |
| P-24 | Restart persistence: shut down, re-create against the same DB, same record served; no startup path deletes or resets | **Met** (local real-infra; CI pending) | `test_p24_the_record_survives_a_restart_and_nothing_resets_it` |
| P-25 | Several ordered reports for one sensor leave exactly one row, the newest; two sensors, two rows | **Met** (local real-infra; CI pending) | `test_p25_*` (6 tests) |
| P-26 | After `upgrade head`, exactly two tables; `sensor_state` exactly the five columns | **Met** (local real-infra; CI pending) | `test_p26_the_schema_holds_exactly_two_tables`, `test_p26_sensor_state_has_exactly_the_five_ratified_columns` (types, nullability and the primary key from `information_schema`) |
| X-1 | TDD 4F §24 4F.7 row: the panel renders the normalized sensor state actually reported | **Met, by the chain in §1.1**; the in-browser link for a *non-empty* sensor list is CI's P-21 parity plus P-18 | P-16 + P-15 + P-18 + P-21 |
| X-2 | In-session: read-only; no write route; no `/v1/perception`; no autonomy route; no invented field | **Met** | P-1, P-9, P-14; `test_no_perception_or_autonomy_route_is_served` |
| X-3 | In-session: no new subject; no `PUBLIC_TOPICS` or registry change; internal subjects not exposed via `ws-gateway` | **Met** | P-13; `services/ws-gateway` and `packages/` diff empty |
| X-4 | In-session: only the `sensor_state` migration | **Met** | `git diff --name-only 4e19ed1 HEAD -- '*/alembic/versions/*'` → one file, `services/cognitive-state-engine/alembic/versions/0003_sensor_state.py` |
| X-5 | In-session: `uv.lock` changes only for a real dependency change | **Met** | `git diff 4e19ed1 HEAD -- uv.lock` → +2 lines, `nova-service-kit` in `cognitive-state-engine`'s `dependencies` and `requires-dist` (A-4F7-4) |

**30 of 31 acceptance criteria are met and verified locally. The one not
verified is P-21 (the Playwright spec), which cannot run in this environment and
is CI-only.** P-2,
P-15, P-16 and P-24 … P-26 are met on local substitute infrastructure; their CI
confirmation is pending (§6).

### 2.1 What this slice does not claim

- That NOVA creates, promotes or proposes anything (4F.P).
- That OS-level permission revocation stops a stream, or that the filesystem
  sensor can reach `failed` (RS-3b, OPEN).
- That every sensor report is received (K-1).
- AC-7 or AC-8 end to end (4F.8).
- The closure of CF-9, CF-10 or CF-11. **All three stay OPEN.**

---

## 3. Category 1 — implementation against the TDDs and ADRs

### 3.1 Deliverables (TDD 4F.7 §5)

| # | Deliverable | Verdict | Where |
|---|---|---|---|
| D1 | Sensor-state persistence | **Implemented as specified** (§8.4, §28.1) | `alembic/versions/0003_sensor_state.py:45` (`CREATE TABLE`, five columns, no CHECK, following the `attention_layer` convention), `:57` (`DROP TABLE IF EXISTS`); `repository/models.py:126` `SensorStateORM`; `repository/postgres_cognitive_state_repository.py:169` `apply_sensor_report` — **one** `INSERT … ON CONFLICT … DO UPDATE … WHERE last_event_id <> EXCLUDED.last_event_id AND reported_at <= EXCLUDED.reported_at` (l.204–205); `:212` `list_sensor_states`; `domain/ports.py:132` `SensorStateRepository` |
| D2 | Vocabulary and handler | **Implemented as specified** (§8.2, §8.3 as superseded by §28.2) | `domain/sensor_state.py:41` (the six values), `:52` `accept_lifecycle_state` (exact, case-sensitive, no trimming), `:64` `SensorStateRecord`; `events/handlers.py:49` (validate → accept → conditional write; warns on an invalid payload or an unknown status with `event_id`, `correlation_id`, `sensor_id` and the string; never raises); `events/subscribed.py:32` |
| D3 | The read API | **Implemented as specified** (§7) | `api/cognitive_state.py:64` `_Strict` (`extra="forbid"`); `:190`, `:197`, `:210` — three `@router.get`, no parameter, no body |
| D4 | Lifespan wiring | **Implemented as specified**, A-4F7-4 (a) | `main.py:61–67` (`nova_service_kit` engine and session factory), `:98` the one `subscribe()`, before `:100` `ready = True`; `pyproject.toml:10`, `:33`; `Dockerfile:10`, `:16` |
| D5 | Publication on existing transitions | **Implemented as specified**, with one disclosed choice (§3.2 C-1) | `perception-engine/src/nova_perception_engine/sensor_lifecycle.py:58` `transition`, `:71` `report_sensor_error`, `:96` no report on a no-op, `:101` `status=after`; call sites `main.py:123` (startup), `:183` (shutdown), `api/consent.py:84`, `observation_orchestration.py:162` |
| D6 | The gateway prefix | **Implemented as specified** | `api-gateway/src/nova_api_gateway/domain/routing.py:214`; `config.py:44`; `main.py:48` |
| D7 | Deployment | **Implemented as specified** | `infra/docker/docker-compose.local.yml:814` (service, port `8020`), `:917` (gateway env), `:941` (`service_started`); `run-migrations.sh:107` |
| D8 | The panel | **Implemented as specified**, A-4F7-3 (a) | `apps/web-client/src/entities/cognitiveState.ts` (`.strict()` at l.57–107; hooks l.130–162); `src/panels/cognitiveState/CognitiveStatePanel.tsx`; `src/app/router.tsx:148`; `src/app/AppShell.tsx:45` |
| D9 | Tests | **Implemented** | §2, §5, §6 |
| D10 | Documentation | **Implemented** | §9 |
| §5 non-`src/` | `pr-checks.yml`; `uv.lock` | **Implemented** | `pr-checks.yml:266`; `uv.lock` +2 |
| §17 source notes | RS-11 clarifications | **Implemented, additively** | `promotion_orchestration.py:37` (dated paragraph; the original sentence kept); `main.py` lifespan comment (the 4F.6 comment kept, a dated note added); `events/subscribed.py` docstring (the original kept in a quoted note) |

**"Unchanged: 0 files", asserted** (`git diff --stat 4e19ed1 HEAD -- <path>`, each
empty): `packages/` (incl. `nova-contracts`, `nova-eventbus-sdk`),
`services/ws-gateway`, `services/action-engine`, `services/autonomy-engine`,
`services/world-model-engine`, `services/memory-engine`,
`services/digital-twin-engine`, `companion/`, `agent-os/`, `tools/`.

### 3.2 Implementation choices the TDD left open, each disclosed

| # | Choice | Why | Alternative |
|---|---|---|---|
| C-1 | **A failed outbox enqueue of a lifecycle report is logged (`sensor_lifecycle_report_not_enqueued`) and not raised.** A failure of the sensor call itself still propagates exactly as before | The report is about a transition that has already happened. Raising would make startup refuse to serve when the database is unreachable (it did not before), and would turn an already-handled observation failure or an already-completed revocation into a 500. **No retry, replay or recovery is added**: the report is lost, and the log says so | Let it raise. It is a one-line change if the Gate Review prefers it; it changes startup behaviour |
| C-2 | **One fresh correlation id per startup, and one per shutdown**, shared by that phase's reports | §8.1 says *"a fresh `uuid4()` is used"*, without saying one per report or one per phase. One per phase lets the six startup reports be read as one startup | One per report |
| C-3 | **`reported_at` for an equal-time report with a new `event_id` applies** | §28.1 lists *"a newer **or equal-time** report with a different `event_id`: replaces"*; built exactly so (`test_p25_an_equal_time_report_with_a_new_event_applies`) | — (specified) |
| C-4 | **Refresh is `queryClient.invalidateQueries({queryKey: ["cognitive-state"]})`**, which re-runs the three mounted queries' own `GET`s | No cache write; what renders is what the engine answered. Proven by `Refresh > re-issues the three GETs, and only GETs` (unit) and the Playwright request log (P-21) | Three explicit `refetch()` calls |
| C-5 | **P-15 and P-25 also compare the row's `xmin`** | A redelivery carries identical values, so a row comparison alone cannot distinguish "not written" from "rewritten with the same values". Without this, negative control M4 would fail only P-25, while the TDD names P-15 (§5.1) | — |
| C-6 | **Startup reports in older perception tests are asserted, then removed** (`tests/integration/startup_reports.py`) | Tests written before 4F.7 count outbox rows from an empty outbox. The helper asserts the six reports exactly — sensor, type, state, order, one correlation id — before removing them, so nothing is silently discarded | Rewrite each count |

### 3.3 Ratified decisions, verified as built

| Decision | Built | Verified by |
|---|---|---|
| A-4F7-1 current-state table, one record per sensor, upsert, no history/audit, survives restart | D1 | P-24, P-25, P-26, M15, M16 |
| A-4F7-2 the six `SensorState` values, published as `sensor.state()` after the call, exact acceptance, unknown rejected and never stored, returned or coerced | D2, D5 | P-10′, P-22, P-23, M13′, M14, M17 |
| RS-1b read-only | D3 | P-1, P-14, M1, M11 |
| RS-3a publish the existing subject on existing transitions; subscribe to it | D2, D5 | P-11 … P-16 |
| RS-3b no filesystem `failed` path added | D5 | `test_the_filesystem_sensor_reports_nothing_on_error_it_has_no_failed_path` |
| RS-4a–4d honest empties; no decision data; proposal as proposal | D3, D8 | P-3, P-9, P-18, M8, M9 |
| RS-5 one gateway prefix | D6 | P-17 |
| RS-8 test data is test infrastructure | tests | `test_cognitive_state_api_real_infra.py` docstring; no production seeding |
| RS-9 component exception | §7.3 | boundary audit |
| RS-11 promotion owned by 4F.P | §17 notes | `promotion_orchestration.py:37`, `main.py` |

### 3.4 Retargeted controls: none retired, all wording preserved

| Test | Why it changed | How the original is kept |
|---|---|---|
| `cognitive-state-engine/tests/contract/test_boundaries.py::test_the_subscribe_allow_list_is_exactly_the_sensor_health_subject` | RS-3a; P-11 names it | The former name, assertion and docstring are quoted in the new docstring |
| `…/tests/integration/test_repository_real_postgres.py::test_the_migration_creates_exactly_one_table_in_its_own_schema` | `0003` adds 4F.7's own table | It still asserts that every table other than `sensor_state` is `["active_thought"]`, and now also pins the whole set; the former assertion is quoted. **The test name is kept**, so the name now describes 4F.1's claim rather than the whole schema (F-4F7-5) |
| `…/tests/integration/test_proposed_action_real_postgres.py::test_0002_adds_no_table` | Same | Same approach; a docstring quotes the former assertion |
| `api-gateway/tests/integration/test_gateway.py::test_the_route_table_fronts_no_other_agent_os_component` | P-17: nine prefixes | The eight earlier entries are unchanged; a dated docstring note |
| `perception-engine/tests/unit/test_observation_orchestration.py::test_a_raising_detection_call_reports_the_sensor_error_and_publishes_no_signal` | The failure path now reports `failed` | The former name and `repository.outbox == {}` quoted; it still asserts **no addressee signal** |
| Four perception test modules' harnesses (`test_api_observations.py` — its fixture and three self-built apps — `test_api_workspace_observations.py`, `test_companion_intake_real_http.py`, `test_workspace_real_postgres_e2e.py`) | Startup now enqueues six reports | C-6: asserted exactly, then removed; a dated note in each fixture |
| `apps/web-client/tests/unit/routing.test.ts` | Eleven panels | Appended; the ten kept, order asserted |

**Control 11's schema check (`test_boundaries.py:144–151`) is untouched** — the
only hunk in that file is the P-11 retarget (`@@ -79,10 +79,23`). See F-4F7-1.

### 3.5 ADRs

| ADR | Verdict |
|---|---|
| ADR-004 (engines communicate over the bus only) | **Holds.** `cognitive-state-engine` never calls `perception-engine`'s REST; the vocabulary is restated and guarded by an AST parse, not an import. `uv run lint-imports`: 7 kept, 0 broken |
| ADR-006 (the Event Bus) | **Holds.** One core-NATS `subscribe()`, no queue group, like every engine; the K-1 limitation is stated, not engineered around |
| ADR-025 (one trusted user) | **Holds.** `primary_user_id` server-side; no `user_id` anywhere on the surface; sensors instance-wide |
| ADR-033 (two-tier testing) | **Holds.** New real-infra tests carry `real_infra`; both engines were already in `real-infra-checks.yml` |
| ADR-034 (`nova-service-kit`) | **Holds, and now applied** to `cognitive-state-engine` (A-4F7-4) — the gap 4F.6's record named as D-6 |

No ADR is made false by this slice.

---

## 4. Category 8 — contracts and codegen

- **`packages/nova-contracts/` did not change:** `git diff --stat 4e19ed1 HEAD --
  packages/nova-contracts/` is empty. No payload, no subject.
- **Codegen:** `uv run --package nova-contracts python codegen/generate_typescript.py`
  exits 0, and `git status --porcelain packages/nova-contracts` is empty — **zero
  drift**.
- **Subjects:** the registry holds **120** before and after (`known_subjects()`);
  `PUBLIC_TOPICS` is **18** before and after, and still contains
  `perception.sensor.health_changed` (it was already public).
- **Allow-lists:** `cognitive-state-engine` publishes `{autonomy.decision.requested}`
  (unchanged) and subscribes to exactly `{perception.sensor.health_changed}`.
  `perception-engine`'s lists are unchanged; the subject was already in its
  publish list.
- **The consumer of the now-published payload** (`PerceptionSensorHealthChangedPayload`):
  `cognitive-state-engine` validates it (`events/handlers.py`); `ws-gateway`
  forwards it unchanged, as before.
- **REST surface:** additive only. Three new `GET`s on an engine that had no `/v1`
  surface; one new gateway prefix. No existing route changed.
- **Breaking changes:** none.

---

## 5. Category 9 — tests, lint, types, imports

| Gate | Command | Result |
|---|---|---|
| Lint + types + build + tests (uncached) | `pnpm turbo run lint typecheck build test --force` | **99/99 tasks successful, 0 cached** |
| `cognitive-state-engine` | (in the above) | ruff clean; mypy **23** source files clean; **191 passed**, 45 deselected; **domain coverage 100%** |
| `perception-engine` | | ruff clean; mypy **39**; **208 passed**, 22 deselected; **domain coverage 99%** |
| `api-gateway` | | ruff clean; mypy **18**; **114 passed** (no `--cov` in its script) |
| `web-client` | | eslint clean; `tsc` clean; **245 passed** (14 files); `vite build` OK (`CognitiveStatePanel` a lazy chunk) |
| Other packages | | all green; e.g. `ws-gateway` 110, `autonomy-engine` 311, `action-engine` 103 |
| Import boundaries | `uv run lint-imports` | **Contracts: 7 kept, 0 broken** |
| Scaffolding tools | `uv run pytest tools/tests -q` | **300 passed** |
| compose | `docker compose -f infra/docker/docker-compose.local.yml config --quiet` | **valid** (exit 0) |
| Codegen drift | generate + `git status` | **none** |

`ruff format` is not a gate (protocol §9.2); pre-existing unformatted files were
not reformatted.

### 5.1 Negative controls: each property removed, its tests must fail

Run by a scratchpad-only driver that applied each mutation, ran the named tests,
and restored the file byte for byte (`git status` clean of source changes
afterwards). **All 19 mutations are caught.**

| # | Mutation | Failed (among others) |
|---|---|---|
| M1 | Add `@router.post("/thoughts")` | `test_p1_exactly_three_get_operations_under_the_prefix`, `test_the_api_declares_only_get_routes_in_source`, `test_every_other_method_is_405[POST-thoughts]` |
| M2 | Accept `?user_id=` | `test_p1_no_operation_takes_a_parameter_or_a_body`, `test_a_caller_supplied_user_id_is_ignored` |
| M3 | `SensorStateResponse.state: str` (an unconstrained string) | `test_p9_the_sensor_state_enum_is_the_six_lifecycle_values` |
| M4 | Remove the `event_id` guard | `test_p15_redelivery_stale_and_unknown_reports_change_nothing_over_the_real_bus`, `test_p25_a_redelivery_of_the_current_event_changes_nothing` (real-infra) |
| M5 | Remove the `reported_at` guard | `test_p15_redelivery_…`, `test_p25_an_older_report_never_overwrites_a_newer_one` (real-infra) |
| M6 | Report a no-op | `test_a_no_op_transition_reports_nothing` ×4, `test_the_filesystem_sensor_reports_nothing_on_error_it_has_no_failed_path` |
| M7 | Skip the report on `stop` | 10, incl. `test_revoking_consent_reports_the_stop_correlated_to_the_grant`, `test_shutdown_reports_each_running_sensor_stopped` |
| M8a | Synthesize a default sensor row (API) | `test_an_empty_store_serves_empty_lists_and_nothing_synthesized`; real-infra `test_p3_an_empty_store_serves_empty_bodies` |
| M8b | Synthesize a placeholder thought (panel) | 6, incl. `empty states > renders each empty statement and nothing else` |
| M9 | Label the proposal "Triggered" | `renders a proposal as a proposal, and nothing about it as acted on` |
| M10 | Add `refetchInterval` | `security-boundary … > adds no polling, and no realtime subscription` |
| M11 | Call `promote_thought` from `api/` | `test_p14_nothing_on_the_served_path_writes_a_thought_or_promotes[api/cognitive_state.py]`, `test_p14_promote_thought_still_has_no_production_caller` |
| M12 | Add `perception.workspace.observed` to `PUBLIC_TOPICS` | `test_p13_public_topics_are_unchanged_at_eighteen` |
| M13′ | Coerce an unknown value to `failed` | 17, incl. `test_anything_else_is_rejected_not_coerced`, `test_an_unknown_status_is_not_stored_and_is_logged` |
| M14 | Add `"degraded"` to perception's `SensorState` | `test_the_restated_vocabulary_equals_perceptions_sensor_state_exactly` (and the anti-vacuity count) |
| M15 | Plain `INSERT` | 5 real-infra, incl. `test_p25_a_newer_report_replaces_the_record_and_leaves_one_row` |
| M16 | `DELETE FROM cognitive_state.sensor_state` at startup | `test_p24_the_record_survives_a_restart_and_nothing_resets_it` |
| M17 | Publish `"healthy"` | 15, incl. `test_p23_every_status_is_a_sensor_state_value_equal_to_the_state_after` ×3 and every call-site test |

**M4 and P-15.** Before the mutation run, inspection showed that P-15's row
comparison could not see a same-value rewrite — a redelivery carries identical
values — so M4 would have failed only P-25. The `xmin` comparison (C-5) was
added first; with it, M4 fails P-15 and P-25, as the table shows. M4 was not run
against the earlier form of P-15.

### 5.2 Flakiness (≥ 10 runs, local substitute infrastructure)

| Tests | Runs | Result |
|---|---|---|
| `test_sensor_state_real_infra.py` + `test_cognitive_state_api_real_infra.py` (P-2 … P-8, P-15, P-24 … P-26, K-1; 17 tests) | 10 | **10/10 green** (17 passed each) |
| `test_sensor_health_real_infra.py` (P-16) | 10 | **10/10 green** |

Every real-bus assertion waits on an **ordered marker** or a condition
(`nova_testkit.waiting.wait_until`), never on a sleep.

---

## 6. Category 10 — real infrastructure

1. **Docker: NOT available.** `docker info` fails with *"failed to connect to
   the docker API at unix:///var/run/docker.sock … no such file or directory"*.
2. **What was run instead, disclosed as such.** PostgreSQL **16.13** (distribution
   binaries, a fresh throwaway cluster) and `nats-server` **v2.10.7** with `-js`.
   A **scratchpad-only** pytest plugin, never committed, pointed `nova-testkit`'s
   `postgres_container` / `nats_container` fixtures at them, and every run used a
   fresh database. **This is not the CI environment**; CI's containers remain the
   authoritative evidence.
3. **Harness fidelity.** Before any new test was added, the pre-existing
   cognitive-state tier ran through this harness: the only failures were the two
   table-count tests that `0003` legitimately changed (§3.4).
4. **Results, local, at `33ca95f` (code identical to `bf0426d`):**
   - `cognitive-state-engine -m real_infra`: **45 passed** (28 pre-existing, 17 new);
   - `perception-engine -m real_infra`: **22 passed** (20 pre-existing, incl. the
     companion's real Rust binary, and 2 new).
5. **Every real-infra test, by name, and whether it covers changed code.** All 67
   do: directly, or through the migration chain (`0003`), the lifespan (the new
   subscription and repository wiring), or startup (the new lifecycle reports).
   - **cognitive-state, new** — `test_sensor_state_real_infra.py` (13):
     `test_p26_the_schema_holds_exactly_two_tables`,
     `test_p26_sensor_state_has_exactly_the_five_ratified_columns`,
     `test_p25_the_first_report_inserts`,
     `test_p25_a_redelivery_of_the_current_event_changes_nothing`,
     `test_p25_an_older_report_never_overwrites_a_newer_one`,
     `test_p25_a_newer_report_replaces_the_record_and_leaves_one_row`,
     `test_p25_an_equal_time_report_with_a_new_event_applies`,
     `test_p25_two_sensors_are_two_rows`,
     `test_an_unknown_status_leaves_the_stored_record_unchanged`,
     `test_p15_a_real_report_reaches_the_table_and_the_api`,
     `test_p15_redelivery_stale_and_unknown_reports_change_nothing_over_the_real_bus`,
     `test_p24_the_record_survives_a_restart_and_nothing_resets_it`,
     `test_k1_a_report_published_while_offline_is_not_received`;
     `test_cognitive_state_api_real_infra.py` (4):
     `test_p3_an_empty_store_serves_empty_bodies`,
     `test_p2_only_the_primary_users_thoughts_are_served`,
     `test_p4_p8_real_rows_serialize_field_for_field`,
     `test_p6_focus_is_select_focus_over_the_same_rows`.
   - **cognitive-state, pre-existing** — `test_decision_trigger_real_nats.py` (9),
     `test_proposed_action_real_postgres.py` (7, incl. retargeted
     `test_0002_adds_no_table`), `test_repository_real_postgres.py` (12, incl.
     retargeted `test_the_migration_creates_exactly_one_table_in_its_own_schema`);
     names as listed in the 4F.6 record §6 item 5, unchanged otherwise.
   - **perception, new** — `test_sensor_health_real_infra.py` (2):
     `test_p16_a_real_lifecycle_call_travels_the_outbox_to_a_real_subscriber`,
     `test_p16_a_no_op_transition_writes_no_row`.
   - **perception, pre-existing** — `test_companion_intake_real_http.py` (8;
     harness retargeted), `test_workspace_real_postgres_e2e.py` (5; harness
     retargeted, reading the six startup rows by independent SQL),
     `test_repository_real_postgres.py` (7).
6. **Matrix:** `cognitive-state-engine` and `perception-engine` already have rows
   in `real-infra-checks.yml`. That workflow was not changed.
7. **What the tests do not fake.** No fake clock, no fabricated sensor reading,
   no injected message from outside a bound producer, and no mocked transport
   (TDD 4F.7 §18). The consumer-side producer is a `BoundEventBus` bound with
   `perception-engine`'s engine name and publishing one subject its allow-list
   holds; it is not `perception-engine`'s code (control 7).
8. **Unverified:** *these 67 tests have not been executed in CI's containers for
   this change; the `Real-Infrastructure Checks` workflow is non-blocking and its
   result against the PR head is reported in the PR, not here.*

---

## 7. Category 11 — PR, branch, commit and CI evidence

### 7.1 Branch and commits

- **Branch:** `phase-4f7`, from `origin/phase-4` @ `4e19ed1`; `4e19ed1` is an
  ancestor of HEAD. Tree clean at every commit.

| Commit | Content |
|---|---|
| `cbf2b34`, `598bbc3` | TDD 4F.7 and its ratification (docs only; fast-forwarded, §0.1) |
| `c3d3428` | `cognitive-state-engine`: migration, repository, vocabulary, handler, API, wiring, tests (23 files, +2336/−20) |
| `ed8463d` | `perception-engine`: lifecycle reporting and tests (14 files, +870/−16) |
| `04d8e11` | `api-gateway`, `infra/docker`, `pr-checks.yml` (8 files, +216/−3) |
| `6aa97c1` | `apps/web-client` panel and tests (8 files, +1194) |
| `bf0426d` | The `xmin` strengthening of P-15/P-25 (1 file, +19) — **implementation SHA** |
| `33ca95f` | READMEs and architecture notes (10 files, +218/−3) |
| (next) | This record |

Each commit message's factual claims were checked against the diff and the runs
above; none is false.

### 7.2 CI

Not reachable before the push. **No local result is reported as CI evidence.**
CI at the PR head (the same code tree as `bf0426d`) — `PR Checks` (incl. the
Playwright `e2e` job and P-21), `Build & Scan` (incl. Trivy on the changed
`cognitive-state-engine` image and the rebuilt `perception-engine` and
`api-gateway` images) and `Real-Infrastructure Checks` — is reported in the PR
and in the implementation report.

### 7.3 Boundary audit (`git diff --name-only 598bbc3 HEAD`)

| Area | Files |
|---|---|
| `services/cognitive-state-engine` | src 9, migration 1, `pyproject.toml`, `Dockerfile`, README, tests 10 |
| `services/perception-engine` | src 4 (`sensor_lifecycle.py` new, `main.py`, `api/consent.py`, `observation_orchestration.py`), README, tests 10 |
| `services/api-gateway` | src 3, README, tests 2 |
| `apps/web-client` | src 4, README, tests 4 |
| `infra/docker` | `docker-compose.local.yml`, `run-migrations.sh`, README |
| `.github/workflows` | `pr-checks.yml` (the e2e service list and a comment) |
| `uv.lock` | +2 (A-4F7-4) |
| `docs/architecture` | 07, 09, 10, 11, 14 (dated notes) |
| **Unchanged** | `packages/`, `services/ws-gateway`, `services/action-engine`, `services/autonomy-engine`, every other engine, `agent-os/`, `companion/`, `agents/`, `tools/`, `build-and-scan.yml`, `real-infra-checks.yml`, `infra/observability/` |

**RS-9's component exception** is exactly the four surfaces TDD 4F.7 §5 names
(`cognitive-state-engine`, `perception-engine`, `api-gateway`, `web-client`),
plus `infra/docker` (D7) and the two non-`src/` files §5 lists (`pr-checks.yml`,
`uv.lock`). Nothing outside it changed.

**Stage 3 (action / autonomy):** untouched. No route, subject or dependency
reaches either.

### 7.4 SLOC (4E methodology; `cloc` over a `git archive` export; tests excluded)

| Scope | `4e19ed1` | HEAD | Δ |
|---|---|---|---|
| Comparable | 37,124 | 37,413 | +289 |
| Wider | 42,465 | 42,754 | +289 |
| Full | 46,097 | 46,787 | +690 |
| **4F scope (the gated figure)** | **46,743** | **47,433** | **+690** |

Below TDD 4F.7 §22's estimate (770 – 1,195). **Headroom to 50,000: 2,567.** The
50k gate is not crossed.

---

## 8. Category 13 — findings, gaps and carry-forwards

### 8.1 Findings: OPEN, each with a recommendation. None is silently fixed

| # | Finding | Options → recommendation | Blocks? |
|---|---|---|---|
| **F-4F7-1** | **Control 11's schema check is vacuous** (pre-existing, 4F.1; TDD 4F.7 §20 A-4F7-6). `test_boundaries.py:149–151` looks for `f'"{schema}'` in `ast.unparse` output, which renders every string with single quotes, so it can never match. It passed before 4F.7 with `"autonomy.decision.requested"` in source, and passes now with `"perception.sensor.health_changed"` in `events/handlers.py` and `events/subscribed.py`. **Not touched here, per the instruction.** Note for whoever repairs it: an *effective* check must permit exactly the two ratified subject strings, or it will fail on 4F.7's legitimate subscription | A-4F7-6 (a): inspect `ast.Constant` strings, permit exactly the two subjects, negative-control it. **Recommend (a), in its own ratified change** | No |
| **F-4F7-4** | **`apps/web-client/src/entities/digitalTwin.ts` says its schemas are strict, but they are not.** zod 3's `z.object` strips unknown keys; no schema in `src/` called `.strict()` before 4F.7. TDD 4F.7 §12 cites it as the precedent (*"as in `digitalTwin.ts`"*). 4F.7's own schemas do call `.strict()` | Add `.strict()` to `digitalTwin.ts` in a later slice (it may surface real drift), or correct its docstring. **Recommend `.strict()`, in 4E's owner's change**, with the TDD 4F.7 §12 citation noted | No |
| **F-4F7-5** | **A retargeted test keeps a name that is now narrower than its assertion.** `test_the_migration_creates_exactly_one_table_in_its_own_schema` now asserts 4F.1's one table *and* the two-table set | Rename at 4F closure, or keep for traceability. **Recommend keeping**; its docstring says so | No |
| **F-4F7-6** | **Stale counts in shipped documentation, pre-existing:** `api-gateway/README.md` "the five in the table above" (eight before 4F.7), `run-migrations.sh` and `infra/docker/README.md` "15 distinct names" / "sixteen" / "fourteen" | 4F.7 added dated notes rather than rewriting (protocol §0.3.4). **Recommend the L-9/L-10 sweep settle them** | No |
| **F-4F7-7** | **No Prometheus scrape target for engines added since 4B** — `autonomy-engine`, `digital-twin-engine`, and now `cognitive-state-engine` (pre-existing; `infra/docker/README.md` "Adding a new engine" step 3). `infra/observability/` is not in D7 | Add all three in one observability change. **Recommend with the OPEN `observability.py` packaging item** | No |

### 8.2 CF-9, CF-10 and CF-11: all OPEN

4F.7 contributes **no closure evidence** to CF-9 or CF-10. For CF-11 it deploys
the engine, but no promotion driver exists (RS-6b); **F-6 stays OPEN, owned by
4F.P.**

### 8.3 Deferred to 4F.P, and not implemented here

Thought ingestion; the promotion policy; `ProposedAction` authorship; CAS on the
promotion transition; Layer 2 logical deduplication; a production caller of
`promote_thought`. **Not implemented anywhere in 4F.7**, and not implemented as
a side effect: `upsert_thought` has no production caller; P-14 holds it.

### 8.4 Other carry-forwards, unchanged

- **OPEN:** RS-3b (revocation detection; its owner to be ratified before the 4F.8
  TDD); 4F.6's TTL and stale-trigger semantics; lost-trigger auditability;
  `observability.py` packaging; the `correlation_id` logging convention (4F.7's
  handler warnings carry it as TDD 4F.7 §8.2 and §14 require; no logging
  infrastructure was added); L-14, L-17, L-18, L-19; focus-signal computation
  (`inputs=None`; K-5); Part 6 interruption semantics; the stale
  realtime-hydration row in `docs/architecture/04-frontend-architecture.md:81`
  (not edited, per TDD 4F.7 §17).
- **Not implemented, by instruction:** Level 3+, `TrustMetric`, sensor history or
  audit, TTL, any replay/retry/queue/recovery for sensor reports (K-1).
- **K-1 … K-10** (TDD 4F.7 §15) stand as written. K-1 is asserted by
  `test_k1_a_report_published_while_offline_is_not_received`.

---

## 9. Category 14 — documentation updated by this slice

| Trigger (§14.1) | Document | Change | Additive? |
|---|---|---|---|
| Table / migration | `docs/architecture/07-database-architecture.md` §1 | Dated note: `cognitive_state.sensor_state`, **current-state storage**, one record per sensor, no history, no audit (TDD 4F.7 §17's explicit obligation) | **Yes** |
| Subject gains publisher/consumer | `09-event-bus-architecture.md` §4 | Dated note: first publisher and consumer; **`status` carries `SensorState` lifecycle values**; no new subject; 18/120; at-most-once | **Yes** |
| Same | `10-inter-engine-communication.md` §2 | Dated note: the flow; ADR-004 holds | **Yes** |
| REST endpoints | `11-api-architecture.md` §2 | Dated note: the three `GET`s and their properties | **Yes** |
| Deployment surface | `14-deployment-architecture.md` §2 | Dated note: the new compose service | **Yes** |
| Engine READMEs | `services/cognitive-state-engine/README.md` | 4F.7 status; Subscribe row (the former "*(none)*" quoted); the three `GET`s; the second table (the former "One table" quoted) | **Yes** |
| | `services/perception-engine/README.md` | When the subject is published; **`status` carries `SensorState` values** | **Yes** |
| | `services/api-gateway/README.md` | The ninth prefix | **Yes** |
| | `apps/web-client/README.md` | The panel | **Yes** |
| | `infra/docker/README.md` | The service; the migrator's seventeen histories | **Yes** |
| Source notes | `promotion_orchestration.py`, `main.py`, `events/subscribed.py` | RS-11 and the subscribe history, dated | **Yes** |

**Inspected and found accurate, or N/A:**
- `20-engine-responsibility-boundaries.md`: ownership is unchanged —
  `perception-engine` still owns the sensor lifecycle, and `cognitive-state-engine`
  owns only its derived copy (TDD 4F.7 §6). A note there is a ledger item (L-20).
- `02-repository-and-folder-structure.md`, `pyproject.toml` workspace and
  `[tool.importlinter]`: N/A; no new package or engine.
- `17-cicd-pipeline.md`: the gates did not change; only the e2e job's service list
  did.
- TDD 4F.7: **not edited** by the implementation. F-4F7-4 notes one inaccurate
  citation in its §12.

**SAD 15 §9.1:** no new subsystem is introduced; two existing engines, the
gateway and the web client are extended. For the new *surface*: architecture
documentation (TDD 4F.7 and §9 above) present; sequence diagrams (TDD §9)
present; API documentation (§7 and doc 11) present; unit and integration tests
present; failure scenarios (TDD §14; tests) present; logging (handler decision
points) present; **performance benchmarks: none** (K-8; none ratified);
**observability metrics: none added** (K-7, OPEN).

---

## 10. Deferred-obligations ledger (protocol §0.2)

### 10.1 Settled by this slice

**None.**

### 10.2 Still open

**L-1 … L-6, L-8 … L-11 and L-13 … L-19**, as carried by the 4F.6 record
§10.2–10.3, are carried forward **unchanged**. L-9 and L-10 inherit F-4F7-4 …
F-4F7-6 and the §9 notes as inputs.

### 10.3 Opened by this slice

| Row | Status | Obligation | Owner | Blocks 4F.7? |
|---|---|---|---|---|
| **L-20** | OPEN | `20-engine-responsibility-boundaries.md` does not mention `cognitive_state.sensor_state` as a derived copy owned by `cognitive-state-engine`, with the fact owned by `perception-engine` | 4F closure (with L-9) | No |
| **L-21** | OPEN | TDD 4E §5.1 (F-4F7-2) and the 2D-B design's *"repeated failures"* framing of the subject (F-4F7-3) remain as dated records; the category-12 sweep should note that the subject is now published on lifecycle transitions | 4F closure (L-9) | No |
| **L-22** | OPEN | Project Health, roadmap and top-level README status for 4F.7 (categories 4, 5, 7) | 4F closure | No |

---

## 11. Final status

- **Implementation:** complete against every row of TDD 4F.7 §16 and §28.4.
- **Local verification:** complete, with real numbers (§5, §6).
- **Negative controls:** 19/19 caught. **Flakiness:** 20/20 green.
- **Real infrastructure:** executed locally on substitute PostgreSQL 16 and
  NATS/JetStream; **Docker unavailable**; CI authoritative.
- **Findings:** five new, all OPEN, none blocking (§8.1).
- **CF-9, CF-10, CF-11:** OPEN.
- **4F.7 is read-only:** no write route, no thought creation, no promotion, no
  `ProposedAction` authorship, no decision request, no execution.
- **Gate verdict:** none; this is a slice (§0).
- **`main` and `phase-4`:** untouched.
- **Next step:** completing 4F.7 does **not** authorize starting 4F.P.

### 11.1 What was not verified, and why

- **P-21, the Playwright spec**, and the e2e stack starting
  `cognitive-state-engine`: CI-only; no Docker daemon here.
- **The real-infra tier in CI's containers:** executed only on local substitute
  binaries.
- **Docker image builds and Trivy** for the three changed images: CI-only.
- **A single test running `perception-engine` and `cognitive-state-engine`
  production code together:** structurally excluded by control 7; the halves
  meet at the registered contract (§1.1).
