# Phase 4E Gate Review — `digital-twin-engine` extension, Bible Part 16's nine
## remaining domains, and the `digital-twin/` panel

**Date:** 2026-09-15
**Branch:** `phase-4e`
**Head reviewed:** `a044782360591e1d064e6dc053ce6926fc32c3e2`
**Base:** `phase-4` at `f39fa6cd0b02bd4e55a42f17b0d748f636f812d4`
**PR:** [#29](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/pull/29) — `phase-4e` → `phase-4`, **open, not merged**
**Protocol:** [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md),
sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`, 1131 lines,
read from `origin/main` and verified byte-identical on `phase-4e`

---

## 0. Read this section first

**This review was performed against the repository at `a044782`, not against the
implementation report.** Every figure below was re-measured during the review:
the CI results were re-read from the GitHub Actions job logs at that exact SHA,
the SLOC figures were re-measured from pristine `git archive` extracts, the test
counts come from a fresh `turbo run test --force`, and the boundary properties
were re-derived from the code rather than quoted. Where a re-measurement
disagreed with the pre-Gate record, **this document carries the re-measured
value and says so** — §6.3 lists the two that moved.

**Three things this review explicitly does not do.**

1. It does **not** close CF-9, CF-10 or CF-11. All three remain **OPEN** and
   4E claims none of them.
2. It does **not** resolve the four known findings carried into it. Each is
   dispositioned in §13 with its status stated, not silently absorbed.
3. It made **no implementation change**. The review found no acceptance,
   security, architectural or correctness blocker requiring one. The only
   commits this review adds are documentation.

**One term used throughout.** *"The two-hop path"* is Phase 4E's novel
deployment shape: a **non-public** Event Bus subject (`memory.long_term.created`,
which is not in `PUBLIC_TOPICS`) consumed by a **gateway-fronted** engine
(`digital-twin-engine`) whose panel renders the derivation. The browser never
sees the subject; it sees what the subject caused. §4.2 and §11.4 explain why
this shape defeated the pre-existing stack-completeness guard and how the guard
was taught to catch it.

---

## 1. What was implemented

Phase 4E extends `digital-twin-engine` from Phase 2D-D's two shipped Part 16
domains to the full **eleven**, and surfaces the result in the browser.

### 1.1 The eleven domains, verbatim from Part 16

[`docs/bible/part-16-digital-twin-engine.md`](../../bible/part-16-digital-twin-engine.md)
lists eleven domains. `PART_16_DOMAIN_ORDER` reproduces them in the Bible's own
order, with the Bible's own names:

| # | Domain | Shipped in |
|---|---|---|
| 1 | Personal Workflow | **4E** |
| 2 | Projects | **4E** |
| 3 | Software Environment | **4E** |
| 4 | Hardware Environment | **4E** |
| 5 | Knowledge Profile | **4E** |
| 6 | Skill Profile | **4E** |
| 7 | Communication Style | 2D-D |
| 8 | Productivity Patterns | **4E** |
| 9 | Goals | **4E** |
| 10 | Preferences | 2D-D |
| 11 | Learning Progress | **4E** |

**11 − 2 = 9.** Verified by executing the enum, not by reading it: nine members
of `PHASE_4E_DOMAINS`, two of `SHIPPED_2DD_DOMAINS`, eleven in
`PART_16_DOMAIN_ORDER`, and `DOMAIN_SPECS`' key set equal to `PHASE_4E_DOMAINS`.
No domain is invented, renamed or merged.

### 1.2 Four evidence states and six machine-readable reason codes

`DomainState` — `populated`, `partially_populated`, `empty`, `unavailable`.
`DomainReasonCode` — `no_source_engine`, `no_autonomous_producer`,
`no_evidence_observed`, `evidence_partial`, `source_unavailable`,
`source_timestamp_missing`.

**The controls are the type, not a test.** `DomainModel` carries two
`model_validator(mode="after")` validators that make the forbidden states
*unconstructible*:

- `_state_is_supported_by_its_evidence` — `populated` with zero evidence rows
  raises, quoting Part 16's own *"Never create assumptions without evidence."*
  A non-`populated` state without an enumerated reason code raises.
  `populated` *with* a reason raises.
- `_respects_the_ratified_per_domain_floor` — `Software Environment` and
  `Hardware Environment` (no source until 4F) can represent only `empty` or
  `unavailable`; `Knowledge Profile` and `Skill Profile` can be
  `partially_populated` at most.

A derivation bug therefore raises rather than rendering a plausible number.
Twelve unit tests in `test_domain_model_invariants.py` assert each forbidden
construction, including the three `ProjectModel` invariants (no activity
timestamps without memories, `first_activity_at ≤ last_activity_at`, `gap_days`
non-negative).

### 1.3 Evidence sources — real, and only where a real publisher exists

`events/subscribed.py` adds **three** subjects and registers **none**:

| Subject | Publisher | Serves |
|---|---|---|
| `memory.long_term.created` | `memory-engine` (since Phase 1) | Personal Workflow, Projects, Knowledge Profile, Skill Profile, Learning Progress |
| `memory.decision.recorded` | `memory-engine` (since Phase 1) | Goals |
| `perception.attention.observed` | `perception-engine` (since 2D-B) | Productivity Patterns |

All three already existed in `nova-contracts` with shipping publishers. 4E is a
**new consumer of existing contracts** — D-4D-1's governing principle.

### 1.4 The AC-6 temporal mechanism (ratified §20.1, Option A)

`PostgresMemoryRepository.create_long_term` built its ORM row from nineteen
fields and **omitted `created_at` and `updated_at`**, so both column
`server_default=func.now()` values fired and the caller's timestamps were
silently discarded — while `_memory_to_domain()` read them back, so a caller
handed in one value and got a different one out. Two lines now pass both
through (`postgres_memory_repository.py:153-154`).

This **removes** a timestamp authority rather than adding one: `update()`
already set `updated_at=record.updated_at`, so only the insert path deferred to
the database. Columns keep their `server_default`; **no migration is required**.

`LongTermMemoryCreatedPayload` gained one additive, defaulted field —
`created_at: datetime | None = None` — per ADR-024.

### 1.5 Persistence

Migration `0003_part_16_domains.py`, three additive tables, **zero existing
tables altered**. `domain_evidence` carries a composite foreign key into
`domain_model` (`ON DELETE CASCADE`), so provenance cannot exist for a domain
that was never derived, and its primary key `(user_id, domain,
source_record_id)` makes an at-least-once redelivery a no-op rather than an
inflated count.

### 1.6 API, gateway and panel

Five REST routes on `digital-twin-engine`, in this declaration order (the
`/domains/projects` literal must precede `/domains/{domain}`):

```
GET  /v1/digital-twin/domains
GET  /v1/digital-twin/domains/projects
GET  /v1/digital-twin/domains/projects/{project_id}
GET  /v1/digital-twin/domains/{domain}
POST /v1/digital-twin/domains/{domain}/refresh
```

**None takes a `user_id`.** `_user_id(request)` resolves
`request.app.state.settings.primary_user_id` server-side (ADR-025).

One `api-gateway` entry — `prefix="/v1/digital-twin"`,
`upstream_name="digital-twin-engine"`, forwarded **1:1** per D-6. One lazy panel
chunk, `DigitalTwinPanel`, 6.61 kB in the CI production build.

### 1.7 Deployment topology (commit `a044782`)

`memory-engine-worker` was added to `docker-compose.local.yml`, mirroring
`perception-engine-worker` exactly: same Dockerfile, `command: ["arq",
"nova_memory_engine.workers.WorkerSettings"]`, `healthcheck: disable: true`,
same four `depends_on`. `pr-checks.yml`'s e2e start list gained
`memory-engine memory-engine-worker digital-twin-engine`. §4.2 explains why.

---

## 2. Why each architectural decision was made

### 2.1 The Event Bus, not HTTP — because ADR-004 forbids HTTP

The 4E TDD's own §6.1/§6.2 originally specified an **HTTP read** of
`memory-engine` from `digital-twin-engine`.
[ADR-004](../../architecture/00-overview-and-decisions.md#adr-004--event-bus-is-the-only-legal-cross-engine-channel)
states there is *"never a raw HTTP call from one engine's code straight into
another engine's module"*, and the TDD's §3.2 lists ADR-004 as binding. The TDD
contradicted an ADR it was bound by.

Resolved by the Event Bus, which §8.1 had already designed for. This is TDD
finding **§0.1.5**, recorded rather than worked around.

**The existing `memory.retrieve.request` RPC was rejected for a second, separate
reason:** `retrieval.retrieve()` calls `_record_access()`, which **writes**. Using
it would have made `digital-twin-engine` mutate `memory-engine`'s state, breaking
§14.5 control 4. Verified at review: `grep` for `httpx|aiohttp|requests\.|urllib`
across `services/digital-twin-engine/src/` returns **zero matches**.

### 2.2 Simulate the gap in the *data*, not in the clock

AC-6 names a *"simulated multi-week gap"* and the repository defines no
simulation mechanism — no clock injection, no time-travel fixture (TDD §0.1.3).
Ratified §20.1 approved simulating in the data: real `created_at` column values
written months in the past, through the real repository write path, into real
PostgreSQL.

**The system clock is never faked.** Verified at review by sweeping
`services/digital-twin-engine/`, `services/memory-engine/`,
`tools/e2e_seed_digital_twin_project.py` and `apps/web-client/src/` for
`freeze_time`, `freezegun`, `time_machine`, `FakeClock`, `fake_clock` and
`monkeypatch.setattr(...datetime...)` — **zero matches in any of them**.
`derive_project_models` reads no clock at all: `now` is a caller-supplied
parameter, and the module docstring says so.

### 2.3 Privacy: a fail-closed allow-list, because `PRIVATE` does not exist

Ratified §19.3 names a `PRIVATE` privacy level. `PrivacyLevel` has **no
`PRIVATE` member** (TDD finding §0.1.6). Implemented as
`CONTRIBUTING_PRIVACY_LEVELS = frozenset({PUBLIC, INTERNAL})` — an allow-list,
so a level added later is excluded by default. This is **stricter** than the
ratified rule, not a narrowing of it.

### 2.4 Identity resolved server-side

4E's five routes resolve `primary_user_id` from settings. This was a
self-corrected boundary violation during implementation: the first draft took
`user_id` as a query parameter, which ADR-025 and TDD §10 forbid.
`test_control_7_no_route_accepts_a_user_id_parameter` pins it.

### 2.5 `updated_at` travels with `created_at`

Not scope creep — the opposite. Passing only `created_at` would have left the
insert path with one authority for one column and another for its neighbour.
Passing both makes `create_long_term` consistent with `update()`, and makes the
write/read round trip lossless.

---

## 3. Tradeoffs considered

| Decision | Alternative rejected | Why |
|---|---|---|
| One `/v1/digital-twin` gateway prefix | Five exact-path entries | Drifts from the engine every time a route is added — D-6 rejects it by name |
| One `/v1/digital-twin` gateway prefix | A path-rewriting layer | D-6 rejects rewriting explicitly as *"a permanent source of drift"* |
| Additive event field | A new `memory.*` subject for Digital Twin | D-4D-1: no Event Bus contract without a genuine producer/consumer need. The field is defaulted and ADR-024-compatible |
| Repository-level `created_at` fix | `created_at` on `CreateMemoryRequest` | Would change the Memory HTTP contract. §20.1 forbids it |
| Dedicated test driver | Seeding through `POST /v1/memories` | No layer of `memory-engine` accepts a caller-supplied `created_at` — proven at four layers in §20.1 |
| Deploy the existing `memory-engine` worker | Write a new dispatcher, or publish from the test | `dispatch_ready_events` already exists and is the only legal publish path; a test-fabricated event would not prove the production path works |
| Structural two-hop guard rule | Hardcode a `memory-engine` filename check | A hardcoded check would not catch the next engine that lands in this shape |

---

## 4. Known limitations

### 4.1 Five domains have no evidence source and say so

`Software Environment` and `Hardware Environment` have **no source engine until
4F** — `nova-companion`'s sensors do not exist. They report `empty` with
`no_source_engine`, and the type makes any richer state unconstructible.

`Productivity Patterns` depends on `perception.attention.observed`, which has
**no autonomous producer until 4F** (TDD §0.1.4/§5.1). It reports `empty` with
`no_autonomous_producer` when nothing has been observed.

`Knowledge Profile` and `Skill Profile` are capped at `partially_populated`:
`memory.long_term.created` carries ids, scores and enums but **no content
field**, so density is derivable and depth is not.

**None of these is a defect and none is hidden.** Each carries an enumerated
reason code and human-readable detail, which the panel renders instead of a
zero. `renders an unpopulated domain's reason rather than a zero` asserts this
in a real browser.

### 4.2 The stack-completeness guard could not see the two-hop path, and now can

Phase 4A's `_needs_a_worker` rule required a compose worker only for an engine
whose outbox subjects appear in `PUBLIC_TOPICS` — the *direct* browser path.
`memory.long_term.created` is **not public**, so `memory-engine` sat on the
guard's exemption list and **no compose service ran `memory-engine`'s arq
worker**. Since `nova_service_kit.outbox.dispatch_ready_events` is the only
caller of `bus.publish()` for engine domain events, and
`arq_run_outbox_dispatch` is its only caller, **no `memory.*` subject had ever
been published in the local stack.** The three AC-6 Playwright specs failed with
404s on the first CI run, and the guard passed.

The rule now has two halves. The direct half is unchanged. The **two-hop half**
requires a worker when an engine's outbox subjects are subscribed by a
*gateway-fronted, browser-observable* service. Both halves are derived
structurally, not hardcoded:

- `_outbox_subjects` parses real `OutboxEvent(subject="…")` call sites, so RPC
  `*.request` subjects that never touch an outbox cannot trigger it (this was a
  real over-fire during implementation: deriving from `PUBLISHABLE_SUBJECTS`
  demanded a worker for `digital-twin-engine` on
  `communication.intent.deliver.request`).
- `_gateway_fronted_services` parses `upstream_name="…"` out of the real route
  table.

`memory-engine` was removed from the exemption list. Four anti-vacuity controls
prove the rule is live: it still fires for `communication-engine`, still does
**not** fire for engines off the public path, fires for `memory-engine` through
the Digital Twin, and the parsers are asserted against real call sites.

### 4.3 Carried-forward limitations, unchanged by 4E

- **Prometheus scrapes only `nova-core`** — unchanged since 4B.
- **Over-broad `communication.*` / `personality.*` bus patterns** — 4E adds no
  wildcard.
- **`README.md` has no Phase 4 status line** — a Phase-4-level closure
  obligation recorded in Phase 4C's health record and re-stated in 4D §13.2.
  §14.3 explains why 4E does not discharge it.

---

## 5. Technical debt introduced

**One item, and it is small.** The stranded-outbox assertion in `pr-checks.yml`'s
Playwright job inspects four schemas — `communication`, `reasoning`,
`model_orchestration`, `planning` — and **does not inspect `memory`**. Confirmed
at review by reading the job's own step at `a044782`. Now that
`memory-engine-worker` is deployed and the AC-6 path depends on its dispatch, a
stranded `memory.long_term.created` row would be invisible to that guard; the
AC-6 Playwright specs would fail, but with a symptom (a missing project) rather
than a cause.

**Not fixed here, deliberately.** The user's ratified scope for `a044782` was
exactly three files, and the instruction for this Gate Review is *"do not expand
scope merely to improve the guard."* It is recorded as finding 3 (§13.1) with
its one-line remedy named, not as a silent gap.

**No other debt.** Zero new dependencies. Zero new Event Bus subjects. Zero
`PUBLIC_TOPICS` entries. Zero existing tables altered. Zero files changed in
`autonomy-engine`, `personality-engine`, `action-engine`, `ws-gateway`,
`perception-engine` or `agent-os`.

---

## 6. Verification results

### 6.1 Local, at `a044782`, working tree clean

| Command | Result |
|---|---|
| `npx turbo run test --force` | **31 successful / 31 total, `Cached: 0`, 51.099s** |
| Tests in that run | **2,614 passed, 384 deselected, 0 failed** |
| `uv run pytest tools/tests -q` | **283 passed** in 6.84s |
| **Workspace total** | **2,897 passing, 0 failing** |
| `npx turbo run lint` | **31 / 31** |
| `npx turbo run typecheck build` | **34 / 34** |
| `uv run lint-imports` | **7 kept, 0 broken** |
| Codegen regeneration | **116 TypeScript files, zero drift** (`git status --porcelain` empty afterwards) |

Per-package, from the same run:

| Package | Result |
|---|---|
| `digital-twin-engine` | 143 passed, 18 deselected, 7.53s |
| `memory-engine` | 126 passed, 4 deselected, 6.47s |
| `web-client` | 217 tests passed |

### 6.2 Coverage

`nova_digital_twin_engine.domain` — **100%**, 357 statements, **0 missed**,
against the repository's 85% `fail_under` gate. Every affected Python domain
package meets the gate (protocol §3.2 condition 4).

### 6.3 Two figures this review corrected

The pre-Gate record cited `real_infra` durations of 13.61 s (digital-twin) and
15.83 s (memory-engine). Re-read from the CI job logs at `a044782`, the actual
values are **10.47 s** and **15.56 s**. The pass/deselect counts were correct.
Recorded here rather than left to stand, per protocol §0.3.4.

### 6.4 SLOC re-measured at HEAD

TDD §17's table was measured at `407457d`. Re-measured at `a044782` with the
identical method — `cloc` v2.06 `--skip-uniqueness --quiet` from pristine
`git archive` extracts:

| Scope | Base `f39fa6c` | Head `a044782` | Δ |
|---|---|---|---|
| Comparable | 34,469 | **35,733** | +1,264 |
| Wider | 39,810 | **41,074** | +1,264 |
| Full | 43,114 | **44,706** | +1,592 |

**Identical to §17's `407457d` figures.** The three commits since are
documentation, workflow, compose, tests, and one **comment-only** change to
`api-gateway`'s `routing.py` — cloc's comment column moves by +23 while its code
column does not move at all, which is the confirmation rather than a
coincidence.

The base figures **reproduce Phase 4D's corrected closing values exactly**
(34,469 / 39,810 / 43,114, 4D Gate Review §22.6), which is what makes the series
continuous.

**The 50,000 SLOC milestone is NOT crossed** — 5,294 to spare on the widest
scope. The 30,000 milestone was crossed before 4D.

---

## 7. Negative controls and flakiness

TDD §14.5 defines **ten** controls. Each has a named test; controls 5 and 10 are
additionally enforced by the type system.

| # | Control | Enforced by |
|---|---|---|
| 1 | No new Event Bus subject registered | `test_control_1_this_engine_publishes_exactly_what_2dd_shipped`, `…_the_three_new_subscriptions_all_predate_4e`, `…_no_digital_twin_subject_beyond_the_2dd_rpc_pair` |
| 2 | `PUBLIC_TOPICS` byte-identical at 18 exact strings | `test_control_2_public_topics_is_unchanged_at_eighteen_exact_strings` |
| 3 | No cross-engine import; no HTTP client into another engine | `test_control_3_no_module_imports_another_engines_internals`, `test_control_3_no_http_client_reaches_another_engine`, plus import-linter |
| 4 | No write into `memory-engine` or `perception-engine` | `test_control_4_the_only_repository_this_engine_writes_is_its_own` |
| 5 | Zero-evidence `populated` impossible; the 4F floor holds | **The `DomainModel` validators**, with 12 tests in `test_domain_model_invariants.py` |
| 6 | A non-contributing privacy level never reaches a rendered domain | Asserted at four tiers: unit (`test_derivation.py:213`), integration ingestion (`test_events_phase_4e.py:139`), integration render (`test_api_digital_twin.py:245`), real Postgres (`test_repository_real_postgres.py:507`), **and in the browser** (`digital-twin-reconstruction.spec.ts:86`) |
| 7 | Exactly five new routes; no `user_id`; no internal route | Six `test_control_7_*` tests including `…_the_gateway_cannot_route_an_internal_path_at_all` and `…_no_route_accepts_a_user_id_parameter` |
| 8 | No `autonomy.*` subject, no autonomy behaviour | Three `test_control_8_*` tests |
| 9 | CF-10 unresolved — five separate sub-properties | `test_control_9a…9e`, including a sha256 pin on `autonomy-engine`'s trust adapter and the fail-closed check that `satisfies_threshold(None, t)` is `False` for every `t` including `0.0` |
| 10 | Every non-`populated` state carries a machine-readable reason | **The `DomainModel` validators**, plus `test_control_10_is_enforced_by_the_type_not_only_by_a_test` |

Two additional tests pin finding 2 (§13.1) so the exposed set cannot widen
unnoticed: `test_finding_3_the_prefix_exposes_exactly_these_six_pre_4e_operations`
and `test_finding_3_only_the_pre_4e_operations_take_a_caller_supplied_user_id`.

**Mutation verification.** Ten mutations were applied during implementation and
audit — seven against the Phase 4E controls (privacy allow-list, populated-needs-
evidence, the 4F floor, `PUBLIC_TOPICS`, the trust-adapter hash, the five-route
cap, the panel's null-gap rendering) and three against the stack-completeness
rule. Each failed a named test.

**Three precision failures, recorded because they are the failure mode controls
are prone to.** (a) The no-polling check first fired on the module's own
docstring and was rewritten to strip comments. (b) `derive_domain`'s empty
branch omitted `unavailable_fields`, caught by its own test. (c) The two-hop
rule's first draft over-fired on RPC `*.request` subjects (§4.2). A control that
fires on its own rationale is a control that gets loosened rather than obeyed.

**Flakiness.** `turbo run lint --force` flaked once in parallel during
implementation on a mypy cache race; a serial run and two subsequent parallel
runs all passed 31/31, and the lint run for this review passed 31/31.

---

## 8. Real-infrastructure status

**Executed in CI at `a044782`.** Docker is unreachable in the development
environment, so **no real-Postgres or Playwright result in this document is a
local one** — every figure below is read from the GitHub Actions job logs at
that exact SHA.

| Suite | Result | Job |
|---|---|---|
| `real-infra (digital-twin-engine)` | **18 passed, 143 deselected, 10.47 s** | `104334588898` |
| `real-infra (memory-engine)` | **4 passed, 126 deselected, 15.56 s** | `104334588924` |
| Real-Infrastructure Checks, whole matrix | **14 / 14 success** | run `34954932413` |

`real-infra (memory-engine)` is **new in 4E** and is the point of the tier:
`memory-engine` had no real-Postgres coverage at all, which is exactly how
`create_long_term` shipped discarding `created_at` — every tier above the real
driver saw a plausible timestamp. The named test is
`test_a_historical_created_at_is_persisted_not_overwritten_by_the_column_default`.

`digital-twin-engine` was already in the `real-infra-checks.yml` matrix from
2D-D, so 4E adds its tests to an existing entry and adds **one** matrix row
(`memory-engine`).

---

## 9. Acceptance criteria

Phase 4E claims exactly one acceptance criterion. Master scope §1.1:

> **AC-6** — *"The Digital Twin's project model correctly reconstructs 'what was
> I doing on Project X' after a simulated multi-week gap, and the reconstruction
> is visible in the Digital Twin panel."*

### 9.1 AC-6 — **MET**, at four tiers

| Tier | Evidence |
|---|---|
| Unit | `test_derivation.py` over real record shapes; `test_domain_model_invariants.py` |
| Integration | `test_api_digital_twin.py`, `test_events_phase_4e.py` |
| Real Postgres | 18 digital-twin + 4 memory-engine `real_infra` tests, CI at `a044782` |
| Browser | `digital-twin-reconstruction.spec.ts`, **3 of 3 passed** in a real Chromium against the real stack |

### 9.2 Clause by clause

| Clause | Discharged by | Proof at `a044782` |
|---|---|---|
| *"The Digital Twin's project model"* | `ProjectModel`, derived from `MemoryRecord.project_id` — the only project identity in the system | `twin-project` row located by project id in the browser |
| *"correctly reconstructs 'what was I doing on Project X'"* | `GET /v1/digital-twin/domains/projects/{project_id}` | `5 memory records`, the activity window, and the memory-type breakdown asserted in the browser |
| *"after a simulated multi-week gap"* | Real persisted `created_at`, real repository write path, real PostgreSQL | `gapDays` **parsed as a number** and asserted `≥ MIN_GAP_DAYS` |
| *"visible in the Digital Twin panel"* | The reconstruction widget, through `api-gateway`, in a browser | True by construction — every assertion above reads the rendered page |

**The gap assertion is deliberately not a string match.** The spec parses
`/^(\d+) days/` and compares numerically, because an assertion on the *words*
would pass just as happily on `"0 days since last activity"` — the one answer
that would mean the whole mechanism had failed. It also asserts the text does
not contain `"no dated activity"`.

### 9.3 The three browser specs, from the CI log

```
✓ 7 digital-twin-reconstruction.spec.ts:50  reconstructs a project across a genuine multi-week gap (1.3s)
✓ 8 digital-twin-reconstruction.spec.ts:110 renders an unpopulated domain's reason rather than a zero (800ms)
✓ 9 digital-twin-reconstruction.spec.ts:139 a confidential memory never reaches the rendered twin (429ms)
```

All three had failed with 404s before `a044782`; all three pass now, **with no
assertion weakened, no test skipped, and no expected-failure marker**. The diff
`407457d..a044782` touches no Playwright spec.

### 9.4 The AC-6 sub-items, enumerated

Each was verified individually at `a044782`.

| # | Sub-item | Status |
|---|---|---|
| 1 | Nine domains implemented, names verbatim from Part 16 | **Met** — §1.1, verified by executing the enum |
| 2 | Eleven total; two are 2D-D's, unchanged | **Met** — `communication_style`, `preferences` |
| 3 | Four evidence states | **Met** — `populated`, `partially_populated`, `empty`, `unavailable` |
| 4 | Machine-readable reason code on every non-`populated` state | **Met** — six codes; enforced by validator, not by convention |
| 5 | `populated` with zero evidence is impossible | **Met** — unconstructible; raises quoting Part 16 §69 |
| 6 | The ratified 4F floor holds for `Software`/`Hardware Environment` | **Met** — only `empty`/`unavailable` constructible |
| 7 | `Knowledge`/`Skill Profile` capped at `partially_populated` | **Met** — `populated` unconstructible |
| 8 | PRIVATE-class exclusion, fail-closed | **Met** — `PUBLIC`/`INTERNAL` allow-list; asserted at five tiers including the browser |
| 9 | Five REST routes, exactly | **Met** — asserted against the OpenAPI document |
| 10 | No route takes `user_id` | **Met** — `primary_user_id` server-side |
| 11 | `api-gateway` forwards 1:1, no rewriting | **Met** — one prefix entry, D-6 |
| 12 | No polling in the panel | **Met** — asserted over comment-stripped source |
| 13 | No direct browser-to-NATS path | **Met** — `assertGatewayUrl` admits only `ws:`/`wss:`; `golden-path.spec.ts:164` proves it in a browser |
| 14 | `created_at` persisted by the repository insert | **Met** — `postgres_memory_repository.py:153-154` |
| 15 | No `created_at` on `CreateMemoryRequest` | **Met** — request model unchanged |
| 16 | No `created_at` on `long_term.write()`'s parameters | **Met** — domain write signature unchanged |
| 17 | Memory HTTP contract unchanged | **Met** — no route, request or response model changed |
| 18 | No new Memory endpoint | **Met** |
| 19 | No `UpdateMemoryRequest` change | **Met** |
| 20 | No fake clock, no system-time manipulation, no new time abstraction | **Met** — §2.2; zero matches in a repository-wide sweep |
| 21 | No migration required | **Met** — columns keep `server_default=func.now()` |
| 22 | The event carries `created_at`, additively and defaulted | **Met** — ADR-024-compatible; TS regenerated |
| 23 | The driver is test-only, uses the real write path and real Postgres, writes a real outbox row in the same transaction, uses no raw SQL, and adds no public API | **Met** — `tools/e2e_seed_digital_twin_project.py`, documented as test-only in its own module docstring |
| 24 | The gap is a genuine multi-week historical gap in persisted values | **Met** — ages 118/96/74/52/37 days; the driver exits non-zero if the measured gap is under 21 days |

### 9.5 What AC-6 is not

AC-6 is **provider-free** and inherits no deferral. It does not claim AC-5, and
it closes no carry-forward. Phase 4's other criteria (AC-1…AC-5, AC-7, AC-8) are
not 4E's and are untouched.

---

## 10. Security sweep

| Property | Result at `a044782` |
|---|---|
| `PUBLIC_TOPICS` | **Byte-identical.** `git diff f39fa6c..a044782 -- services/ws-gateway/` is **0 lines** |
| New Event Bus subjects | **0.** 118 registered subjects at base, 118 at head; `@register_payload` call sites 119 at both |
| `autonomy.*` subjects | **0**, anywhere in the repository |
| `TrustMetric` surface | **Unchanged.** No `+`/`−` line in the whole diff touches it; the trust adapter is sha256-pinned |
| Engine-to-engine HTTP | **None.** Zero HTTP-client imports in `digital-twin-engine/src` |
| Duplicated approval state | **None.** Zero occurrences of `approval` in `digital-twin-engine/src` |
| Browser-to-NATS | **Impossible.** The realtime client accepts only `ws:`/`wss:`; a `nats://` URL is rejected at construction |
| Identity | ADR-025 preserved — 4E's routes resolve `primary_user_id` server-side; no role, RBAC, tenant or scope concept introduced |
| New dependencies | **0** |
| Trivy | **Build & Scan 21 / 21 success** at `a044782`, including `digital-twin-engine`, `memory-engine` and `api-gateway`, plus `dependency-audit` |

**One security surface is newly reachable and is disclosed, not buried** — see
finding 2 in §13.1. It is an *integrity* and *latent multi-user* surface, not a
confidentiality vector under ADR-025, and the analysis is written into
`routing.py` itself so it cannot be lost.

---

## 11. CI and branch evidence

### 11.1 The exact head

All CI evidence below is **against `a044782360591e1d064e6dc053ce6926fc32c3e2`**,
the head of `phase-4e` and of PR #29. The Playwright job's own log line reads
`golden path @ a044782360591e1d064e6dc053ce6926fc32c3e2`.

### 11.2 37 of 37 check runs green

| Workflow | Run | Result |
|---|---|---|
| PR Checks #102 | `34954932427` | **success** — `checks` and `Playwright golden path` |
| Real-Infrastructure Checks #140 | `34954932413` | **success** — 14 / 14 |
| Build & Scan #102 | `34954932430` | **success** — 20 images + `dependency-audit` = 21 / 21 |

**Zero failed, zero cancelled.** Re-read from the GitHub Actions API during this
review, not quoted from the implementation report.

### 11.3 Playwright — 17 passed, 1 skipped, 0 failed (55.1 s)

18 tests, 1 worker. The single skip is **4B's `approval-lifecycle`**, which skips
when the Critical action is denied at `action-engine`'s identity-confidence
gate — **CF-9's fail-closed default working as designed**, pre-existing, and not
4E's. Previous run at `407457d`: 14 passed, **3 failed**, 1 skipped.

### 11.4 The deployment fix is observable in the CI log

`nova-local-memory-engine-worker-1` appears in the e2e stack's teardown at
`a044782` alongside `communication-engine-worker`, `planning-engine-worker`,
`reasoning-engine-worker` and `ai-model-orchestration-engine-worker`. The
container really ran. `docker compose config --quiet` also passed in the
`checks` job.

### 11.5 Branch hygiene

| | |
|---|---|
| `phase-4e` head | `a044782360591e1d064e6dc053ce6926fc32c3e2` |
| Commits | **8, linear, zero merge commits** |
| History | `d39b5b8` · `ae82fe0` · `04eb77c` · `87c1b32` · `407457d` · `0f44cdd` · `73ea3f2` · `a044782` |
| Force push / rebase / squash / history rewrite | **None, at any point** |
| `phase-4` | **`f39fa6cd0b02bd4e55a42f17b0d748f636f812d4` — untouched** |
| `main` | **`7e273e62e942ecd5528ca807e65933d6bb675669` — untouched** |
| `phase-4f` | **Does not exist** |
| Working tree | Clean, nothing unpushed |
| PR #29 | **Open, not merged**, `mergeable_state: clean` |

`phase-4e` was cut from the merged `phase-4` head per master scope §16 rule 5.

---

## 12. Compatibility with the NOVA Project Bible

| Bible / ADR | 4E's relationship |
|---|---|
| **Part 16** — the eleven Digital Twin domains | Implemented verbatim, in the Bible's own order and names. *"Never create assumptions without evidence"* is enforced by a type validator that quotes it |
| **ADR-004** — no raw engine-to-engine HTTP | **Honoured against the TDD's own text.** The TDD specified an HTTP read; ADR-004 wins, the Event Bus carries it (§2.1) |
| **ADR-024** — additive, defaulted contract evolution | One field, `created_at: datetime \| None = None` |
| **ADR-025** — single trusted user per instance | Preserved. 4E adds no identity parameter; the pre-existing asymmetry is disclosed as finding 2, not extended |
| **ADR-030** — Personality stores, Digital Twin learns | Preserved. 4E derives; it stores nothing on Personality's behalf |
| **ADR-033** — two-tier testing, `real_infra`, 85% coverage | Both tiers present; domain coverage 100% |
| **D-6** — `api-gateway` forwards 1:1, no rewriting | One prefix entry; no rewriting layer introduced |
| **D-4D-1** — no Event Bus contract without a genuine need | Zero new subjects; 4E is a consumer of three existing ones |
| **Part 14 / Autonomy** | Untouched. Zero `autonomy.*` subjects; `autonomy-engine` has zero changed files |

**Forward contamination:** none. No `cognitive-state-engine`, no `companion/`,
no Autonomy Level 2, no `nova-companion` sensor — all 4F. The two
no-source-until-4F domains are represented as `empty` with a reason, which is
the *absence* of 4F functionality, not a partial implementation of it.

**Backward contamination:** none. Phase 2D-D's two domains, its three route
groups and its `digital_twin.preferences.get.request` RPC are unchanged and
pinned by `test_control_7_the_three_2dd_route_groups_are_unchanged`.

---

## 13. Gaps, ambiguities, and deferred findings

### 13.1 The four known findings — status, stated not absorbed

| # | Finding | Status |
|---|---|---|
| **1** | **`nova_testkit`'s Postgres fixture image drift.** `_POSTGRES_IMAGE = "postgres:16-alpine"` while `docker-compose.local.yml` uses `pgvector/pgvector:pg16`; two engines' migration `0001` needs `CREATE EXTENSION vector` | **OPEN.** Pre-existing, not 4E's, and explicitly excluded from the approved fix scope. Recorded in TDD §0.1.8. Does not affect any 4E acceptance criterion — the `real_infra` tiers that matter for AC-6 both pass in CI |
| **2** | **The D-6 prefix exposes six pre-4E operations that take a caller-supplied `user_id`**, three of them writes (`PATCH /profile`, `PATCH /proactive-policy`, `POST /reset`) | **OPEN, reported not fixed, and pinned.** Not a confidentiality vector under ADR-025; it is an integrity surface and a latent multi-user hazard. Fixing it would change 2D-D's shipped routes and desynchronise them from an RPC that carries `user_id` by design — outside 4E's ratified scope, and a decision to take explicitly. The full analysis is in `routing.py`; two tests pin the exposed set |
| **3** | **The stranded-outbox guard omits the `memory` schema** | **OPEN, new, minor.** §5. The one-line remedy is known. Not fixed because the approved scope for `a044782` was three files and this review is instructed not to expand scope to improve the guard |
| **4** | **CF-9, CF-10, CF-11** | **All three OPEN.** §13.2 |

Two further TDD findings were **resolved in design during implementation** and
are recorded as such, not carried: **§0.1.5** (the ADR-004 HTTP violation,
resolved by the Event Bus) and **§0.1.6** (`PrivacyLevel` has no `PRIVATE`
member, resolved by a stricter fail-closed allow-list).

One finding recorded during the pre-Gate audit is **RESOLVED by `a044782`**: the
absent `memory-engine` worker (§4.2).

### 13.2 Carry-forwards — none closed by 4E

- **CF-9** — ADR-032 point 2 has no policy write path. **OPEN** by ratified
  decision D-4D-2. 4E is not the routed surface and does not touch it. Its
  fail-closed default is incidentally re-demonstrated by the one Playwright skip
  (§11.3).
- **CF-10** — no read surface exists for 2D-D's `TrustMetric`. **OPEN** by
  ratified §19.2, and asserted as five separate properties by
  `test_control_9a…9e`.
- **CF-11** — no component produces a suggestion. **OPEN.** 4E adds no producer.
- **AC-4 clauses 2 and 3** — deferred by explicit user approval of 2026-09-07.
  Untouched; 4E adds no model provider.
- **4C.1 has no Gate Review; Phase 4A has no Gate Review or health record;
  `README.md` has no Phase 4 status line** — Phase 4 closure obligations,
  unchanged (§14.3).
- **CF-8's six Phase 3E narrowings** — unchanged.
- **SLOC methodology Option A / Option B** — open, undecided, and **not decided
  here**.

### 13.3 Category-13 items requiring a user decision

**One exists and it does not block this gate.** Finding 2 names a decision the
user may want to take — whether 2D-D's six operations should resolve identity
server-side. It is *reported* per protocol §13.1, it affects **no Phase 4E
acceptance criterion**, and 4E neither extends nor depends on the behaviour.
Protocol §3.2 condition 11 asks that no open category-13 item *require* a
decision for this gate; this one does not.

---

## 14. Documentation this review is accompanied by

### 14.1 Written by this pass

1. **This Gate Review** (DoD item 1).
2. **[`docs/project-health/phase-4e.md`](../../project-health/phase-4e.md)** —
   the standardized 23-field snapshot (DoD item 2).
3. **A row in
   [`project-health-master.md`](../../project-health/project-health-master.md)**'s
   master timeline (DoD item 2).
4. **The Phase 4E roadmap entry** in
   [`ENGINEERING_ROADMAP.md`](../ENGINEERING_ROADMAP.md) — the 4E row read
   *"Not started"*, which the repository contradicts. Corrected additively, with
   the original cell text preserved and marked (DoD items 4 and 6).

### 14.2 Already current before this pass

- **TDD 4E** (`docs/design/phase-4/05-tdd-4e-digital-twin-extension.md`) —
  1,079+ lines, carrying §0.1's four findings, §19's and §20's ratified
  decisions, and §17's SLOC table. §17's table is labelled `407457d`; this review
  re-measured at `a044782` and the figures are **identical** (§6.4), so the table
  is accurate and **no edit is required** — only this cross-reference.
- **Master scope** (`00-master-scope.md`) — §15's CI note and the 4E section are
  current at `a044782`, including the nine-domain arithmetic correction.

### 14.3 One documentation gap deliberately not closed here

`README.md`'s Status section stops at Phase 3E and has **no Phase 4 status
line**. DoD item 5 triggers *"where the phase changes what a reader of the
top-level README would reasonably expect to be told (a new phase completed, the
canonical branch changed, a new engine now exists)"*. Phase 4E creates **no new
engine** (it extends one that has existed since 2D), **changes no canonical
branch**, and **is not merged**. None of item 5's triggers fires.

The gap is real but it is **Phase 4's**, not 4E's: it predates 4A, was recorded
in Phase 4C's health record, and was re-stated as a Phase 4 closure obligation
by 4D §13.2. Writing a Phase 4 status line now would assert a phase-level state
that Phase 4 has not reached. It is carried forward unchanged and named here so
it cannot be lost.

### 14.4 One correction to PR #29's description

PR #29's body was written at `407457d` and says *"45 files"*; the head is now 46
files, and its verification block predates the CI run. The body is preserved and
an additive, dated note has been added rather than a rewrite, per protocol
§0.3.4. Nothing in the body's technical content was wrong when written.

---

## 15. Gate verdict

### **GO**

Phase 4E's scope is complete, verified at every tier its TDD names, and green in
real CI against the exact head SHA.

**Why GO rather than CONDITIONAL-GO.** Protocol §3.2 lists four triggers for
CONDITIONAL-GO: a real-infrastructure suite that could not run locally and has
not yet run in CI; a non-blocking workflow that has not yet reported; a
documented, accepted limitation that does not affect an acceptance criterion; a
documentation update queued behind a merge that has not happened. **None
applies.** Real infrastructure ran and passed in CI at the exact head SHA.
Every workflow ran and is reported. No condition needs attaching, because the
remaining findings are explicitly non-blocking carry-forwards that this review
disposes of rather than defers — and §3.2 requires each CONDITIONAL-GO condition
to carry *"an owner and the specific event that discharges it"*, which none of
them has, because none of them is awaiting an event this phase can name.

**Why not NO-GO.** §3.2's six NO-GO criteria, each checked:

| NO-GO criterion | Finding |
|---|---|
| An acceptance criterion unmet without approval | **No** — AC-6 is Met at four tiers |
| An undisclosed deviation from TDD / ADR / ratified decision | **No** — two deviations exist (§0.1.5, §0.1.6) and both are disclosed, ratified in shape, and resolved *toward* the binding ADR |
| Any blocking gate red | **No** — 37/37 CI green; lint, test, typecheck, build, import-linter, codegen, coverage all green |
| A document contradicting repository state, uncorrected | **No** — the one that did (the roadmap's *"Not started"*) is corrected in this pass |
| An unresolved architectural ambiguity | **No** — §0.1.3's ambiguity was ratified as §20.1 before implementation |
| Scope silently narrowed | **No** — nine domains shipped, five routes shipped, nothing dropped; every narrowing (the 4F floor, the `partially_populated` cap) is a *ratified* floor, disclosed and type-enforced |

**GO records that Phase 4E's own scope is complete. It closes no
carry-forward.** CF-9, CF-10 and CF-11 remain OPEN, and this verdict must not be
read as closing them. Findings 1, 2 and 3 remain OPEN and are not retired by it.

**No conditions are attached.** Merge authorization is separately the user's.

### 15.1 Protocol §3.2 — the eleven GO conditions

| # | Condition | Status |
|---|---|---|
| 1 | Every acceptance criterion Met, or narrowed/deferred with cited approval | **Yes** — AC-6 Met (§9); no deferral needed |
| 2 | No undisclosed deviation from TDD / ADR / approved decision | **Yes** — §0.1.5 and §0.1.6 disclosed; §20.1's and §19's terms each checked against the diff (§9.4) |
| 3 | `turbo run lint` and `test --force` pass repo-wide with real counts | **Yes** — 31/31 and 31/31; **2,614 + 283 = 2,897 passing, 0 failing** |
| 4 | Every affected package meets the 85% domain-coverage gate | **Yes** — `nova_digital_twin_engine.domain` **100%** |
| 5 | `uv run lint-imports` 0 broken contracts | **Yes** — 7 kept, 0 broken |
| 6 | Contract / codegen verification clean, zero unexplained drift | **Yes** — 116 files regenerated, working tree unchanged |
| 7 | Real GitHub Actions CI green against the exact head SHA | **Yes** — **37/37 at `a044782`**, 0 failed, 0 cancelled |
| 8 | Real-infrastructure verification passed, or absence explicitly disclosed | **Yes** — passed in CI (§8); local absence of Docker explicitly disclosed |
| 9 | Gate Review, Project Health record, roadmap entry and README status all exist and are current | **Yes** — items 1–3 written by this pass; the roadmap entry corrected; the README's Phase 4 gap is a disclosed Phase-4-level obligation whose DoD item-5 triggers 4E does not fire (§14.3) |
| 10 | No document contradicts repository state | **Yes** — after this pass's two corrections (roadmap row, PR body note) |
| 11 | No open category-13 item requires a user decision | **Yes** — one exists (finding 2) and is explicitly not required for this gate (§13.3) |

---

## 16. Project Metrics

Per [SAD 15 §10](../../architecture/15-development-workflow.md#10-project-metrics--the-sloc-milestone-gate)
and [`METRICS_TEMPLATE.md`](METRICS_TEMPLATE.md).

| Metric | Value |
|---|---|
| Production SLOC, comparable scope (`services/*/src` + `packages/*/src` + `services/*/alembic/versions`) | **35,733** (base `f39fa6c`: 34,469 — **+1,264**) |
| Production SLOC, wider scope (adds `agent-os/*/src`, `agent-os/*/alembic/versions`, `agents/*`) | **41,074** (base: 39,810 — **+1,264**) |
| Production SLOC, full scope (also `apps/*/src`) | **44,706** (base: 43,114 — **+1,592**) |
| SLOC tool | **`cloc` v2.06**, `--skip-uniqueness --quiet`, from pristine `git archive` extracts — 4D §22.6's corrected methodology, continuing 4B's and 4C.2's series comparably. The `scc` series (2D-B → 2D-C) remains separate and non-comparable |
| SLOC milestone gate | **50,000 NOT crossed** — 5,294 to spare on the widest scope |
| Diff vs base | **46 files changed, +6,716 / −45** |
| Files by area | `digital-twin-engine` 20 · `web-client` 8 · `api-gateway` 5 · `memory-engine` 4 · `tools` 2 · `nova-contracts` 2 · `docs` 2 · `.github` 2 · `infra` 1 |
| Files touched in engines 4E does not own | **0** in `autonomy-engine`, `personality-engine`, `action-engine`, `ws-gateway`, `perception-engine`, `agent-os` |
| Tests, workspace | **2,614** via turbo + **283** `tools/tests` = **2,897 passing, 0 failing** |
| Tests, `digital-twin-engine` | **161 collected** — 143 default + **18 `real_infra`** |
| Tests, `memory-engine` | **130 collected** — 126 default + **4 `real_infra`** |
| Tests, `web-client` | **217** vitest |
| Playwright | **18 specs — 17 passed, 1 skipped, 0 failed** (55.1 s); 3 of them are AC-6's |
| Domain coverage | **100%** (357 statements, 0 missed) vs the 85% gate |
| Negative controls | **10 of 10**, plus 10 mutations each failing a named test |
| Import contracts | **7 kept, 0 broken** |
| Codegen | **116 TypeScript files, zero drift** |
| New Event Bus subjects | **0** (118 registered at base, 118 at head) |
| New `PUBLIC_TOPICS` entries | **0** (byte-identical, 18 strings) |
| New dependencies | **0** |
| New `/v1` prefixes at the gateway | **1** (`/v1/digital-twin`) |
| New compose services | **1** (`memory-engine-worker`) — an existing worker deployed, not new code |
| Database tables added | **3**, all additive; **0** existing tables altered; migration `0003` |
| CI check runs at head | **37 of 37 success**, 0 failed, 0 cancelled |

---

## 17. Definition of Done — `definition-of-done.md`'s ten items

Note: 4D's Gate Review §17 used a differently-worded ten-item list of its own.
This section follows
[`docs/project-health/definition-of-done.md`](../../project-health/definition-of-done.md),
which is the standing policy protocol §3.1 names.

| # | Item | Status |
|---|---|---|
| 1 | **Gate Review** under `docs/roadmap/architecture-reviews/` in the established shape | **Yes** — this document |
| 2 | **Project Health record** — a 23-field `phase-4e.md` plus a master-timeline row | **Yes** — both written by this pass |
| 3 | **TDD / design documentation currency** | **Yes** — TDD 4E carries §0.1's findings, §19/§20's ratifications and §17's SLOC table; re-measurement at HEAD confirms the table (§6.4, §14.2) |
| 4 | **Roadmap status** | **Yes** — the 4E row read *"Not started"*; corrected additively with the original preserved |
| 5 | **README / current project status** | **Not triggered by 4E, and disclosed** — §14.3. The Phase 4 gap is a Phase-4-level obligation carried forward, not created or worsened here |
| 6 | **Reconciliation / correction notes are additive** | **Yes** — the roadmap cell and the PR body both preserve their original text under a dated note; §6.3 marks the two re-measured figures rather than overwriting them |
| 7 | **Tests and verification evidence with real counts** | **Yes** — §6, §7, §8, §16; every count from a command run at `a044782` |
| 8 | **CI, Trivy and real-infrastructure cited with the exact SHA** | **Yes** — §8 and §11, all at `a044782`; Trivy green across 20 images |
| 9 | **Final acceptance-criteria status enumerated** | **Yes** — §9, AC-6 clause by clause plus 24 sub-items |
| 10 | **Final merge-readiness review** | **Yes** — §17.1 |

### 17.1 Merge-readiness review

| Check | Result |
|---|---|
| Exact head SHA | `a044782360591e1d064e6dc053ce6926fc32c3e2` |
| CI against that exact SHA | **37 / 37 success**, 0 failed, 0 cancelled |
| Working tree | **Clean** at the time of review; documentation commits are this pass's only additions |
| Diff contains only intended changes | **Yes** — 46 files, all within 4E's ratified scope; zero files in six engines 4E does not own; no undisclosed scope creep |
| Branch protection rules observed | **Yes** — no force push, no rebase, no squash, no history rewrite; `phase-4` and `main` untouched |
| PR state | #29 **open, not merged**, `mergeable_state: clean` |

**Merge is not performed by this review.** Authorization is the user's, separately.

---

## Sign-off

Phase 4E delivers Bible Part 16's nine remaining Digital Twin domains, derived
from real Memory and Perception evidence carried on **existing** Event Bus
subjects, surfaced through five REST routes behind a 1:1 gateway prefix and a
lazily-loaded panel — with **no new Event Bus subject, no `PUBLIC_TOPICS`
change, no new dependency, no Memory API contract change, no migration on
`memory-engine`, and no modification to `autonomy-engine`, `personality-engine`,
`action-engine`, `ws-gateway` or `perception-engine`.**

AC-6's *"simulated multi-week gap"* is simulated in the **data**, never in the
clock: real `created_at` column values 118 to 37 days in the past, written
through the real repository into real PostgreSQL, carried on the real
transactional outbox by the real arq worker, over the pre-existing
`memory.long_term.created` subject, into the Digital Twin's domain evidence, out
through `api-gateway`, and rendered in a real browser where the gap is parsed as
a number rather than matched as a string. No fake clock exists anywhere in the
chain.

The two controls that matter most are **types, not tests**: a domain cannot be
constructed claiming to be populated with zero evidence, and a non-populated
domain cannot be constructed without an enumerated machine-readable reason. A
derivation bug raises rather than rendering a plausible number — which is Part
16's *"Never create assumptions without evidence"* made structural.

Three findings are carried openly rather than resolved quietly: a pre-existing
`nova_testkit` image drift, the D-6 prefix's exposure of six pre-4E operations
that take a caller-supplied `user_id`, and a stranded-outbox guard that does not
yet watch the `memory` schema. None affects an acceptance criterion; each names
its remedy; each is pinned or ledgered so it cannot quietly widen.

**Verdict: GO.** Phase 4E's own scope is complete and verified. CF-9, CF-10 and
CF-11 remain OPEN.

**Reviewed against `a044782360591e1d064e6dc053ce6926fc32c3e2`, 2026-09-15.**
