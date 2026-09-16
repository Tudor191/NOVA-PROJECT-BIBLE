# Phase 4F.2 — Slice Completion Record
## `perception.workspace.observed`: contract, producer and ingestion path

**Date:** 2026-09-16
**Slice:** 4F.2 of 4F's eight (TDD 4F §18)
**Branch:** `phase-4f.2`, preserved at `cc0dcada923dda2bd06f4fc186aabd8e72e5cc6d`
**Merged into:** `phase-4` as **`5b5ebfd03d6b41710fc2f427a78206236d1ff392`**
**Parents:** `4605d64950191bc08c4d1bc9d66a72ca8eaca030` · `cc0dcada923dda2bd06f4fc186aabd8e72e5cc6d`
**PR:** [#31](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/pull/31), merged 2026-09-15T23:46:39Z
**Protocol:** [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md),
sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`,
1131 lines, read from `origin/main` and verified in this session.
**TDD:** [`06-tdd-4f-companion-and-cognitive-state.md`](../../design/phase-4/06-tdd-4f-companion-and-cognitive-state.md)
§8.1, §9, §11.1, §18, §20.1, §20.2.

---

## 0. What this document is, and is not

**This is a Slice completion record. It is not a Gate Review, and 4F.2 does not
get one.**

Protocol **§0.1** assigns a Significant Slice categories **1, 2, 8, 9, 10, 11, 13
and 14 in full**, and categories **3–7 and 12 as a deferred-obligations ledger**
(§0.2). Category 3 is the Gate Review, category 4 is the Project Health record
and category 5 is the roadmap. This record therefore executes the first set and
**defers the second set in writing** — §11 below is that ledger.

Two consequences, stated plainly because they contradict a reasonable
expectation:

- **No `docs/project-health/phase-4f.md` is created here.** Protocol §4.1
  requires every field of a health record to be *"cited back to its source —
  normally a specific section or line of that phase's own Gate Review."* Phase
  4F has no Gate Review yet, so those citations do not exist and the record
  cannot be written without inventing them. It is written once, at 4F's closure.
- **No 4F.2 Gate Review is created or appended to.** None exists, and none is due
  at this point. Phase 4F is **one milestone** (TDD §18: *"4F is one milestone;
  these are slices within it, not new milestones"*); its Gate Review covers the
  whole milestone at the end of 4F.8.

**Phase 4F is NOT complete.** Two of eight slices are merged. Nothing here is a
phase-level verdict.

---

## 1. Status

**4F.2 is COMPLETE, VERIFIED, MERGED and CLOSED — as a slice.**

That wording is used because the evidence supports exactly it: the slice's own
exit criteria are met, its implementation is merged into `phase-4` by a normal
two-parent merge, and its verification is recorded below at the exact commit.
It carries no phase-level claim.

### 1.1 The slice's exit criteria (TDD §18)

| TDD §18 requirement | Status |
|---|---|
| Perception extension: literal widening | **Done** — `SensorConfig.sensor_type` and `PermissionStatus.source` accept `"filesystem"` |
| Structured intake (§8.1) | **Done** — `POST /v1/perception/workspace-observations`, a sibling route |
| Normalization | **Done** — path hashing, label reduction, debounce/coalesce |
| Enrichment | **Done** — project correlation, `None` on failure |
| Fusion | **Deferred to a later slice — see §11.2.** No workspace signal participates in identity fusion, and none can until 4F.3 produces one |
| The `perception.workspace.observed` contract | **Done** — registered, and all eleven §20.2 requirements met (§2) |
| *Proves:* observation reaches the World Model | **Done** — producer→consumer integration test |
| *Proves:* the subject is provably internal | **Done** — four negative controls |

---

## 2. Category 2 — the eleven §20.2 requirements

TDD §18 states 4F.2 is *"not complete until all eleven of §20.2's requirements
are documented and tested."* Each is mapped to the artefact that satisfies it.

| # | Requirement | Evidence |
|---|---|---|
| 1 | Exact subject name, as registered | `perception.workspace.observed`; `payload_model_for()` resolves it to `PerceptionWorkspaceObservedPayload` |
| 2 | Exact payload schema, field by field | §3 below; `test_all_seven_ratified_fields_are_present`, plus a closed-set test that the contract carries **exactly** those fields and no more |
| 3 | Producer named and tested | `perception-engine`, `events/publishers.py::workspace_observed`; 33 tests in `tests/unit/test_workspace.py` and `test_workspace_orchestration.py` |
| 4 | Consumer named and tested | `world-model-engine`, via the existing wildcard; 4 tests in that engine's `tests/integration/test_handlers.py` |
| 5 | Why existing subjects are insufficient, evidenced | `test_no_existing_perception_payload_could_have_carried_this` — asserts no other perception payload carries `object_id`/`entity_id`/`object_label` |
| 6 | Why the subject is internal only | It carries raw sensor provenance — `sensor_id`, `observed_at`, a path hash. Recorded in the payload docstring and §4 below |
| 7 | **NOT in `PUBLIC_TOPICS` — asserted** | `test_4f2_workspace_observed_is_not_a_public_topic`, plus a size guard pinning the count at 18 |
| 8 | **`ws-gateway` does not expose it** | `test_4f2_workspace_observed_is_not_subscribable_by_the_gateway_at_all` — the second allow-list, which 4F.2 had to narrow (§4) |
| 9 | **Raw sensor events are not browser-visible** | Requirements 7 and 8 together; no `/v1/perception` gateway prefix exists |
| 10 | Contract/schema validation against the registry | `test_the_subject_is_registered_and_resolves_to_the_payload`; round-trip through `validate_payload` |
| 11 | **Negative test proving browser/public access is rejected** | `test_4f2_a_browser_naming_the_workspace_subject_is_rejected`, and a second asserting the connection stays usable afterwards |

**All eleven met.**

---

## 3. Category 1 and 8 — the contract as built

```
subject: perception.workspace.observed
payload: PerceptionWorkspaceObservedPayload
```

| Field | Type | Required |
|---|---|---|
| `object_id` | `str` | Yes — a prefixed SHA-256 of the normalized path |
| `label` | `str` | Yes — final path segment only |
| `user_id` | `UUID` | Yes — resolved server-side |
| `object_type` | `Literal["project"]` | Yes — closed |
| `project_id` | `UUID \| None` | No, default `None` |
| `sensor_id` | `str` | Yes |
| `observed_at` | `datetime` | Yes |
| `schema_version` | `int` | No, default `1` |

**Eight fields: the seven ratified workspace fields, unchanged, plus
`schema_version`.** The eighth is ADR-024 compliance, ratified as such — all 118
previously registered payloads carry it, with zero exceptions, so omitting it
would have made this the only registered payload without one. It is not an
eighth functional field.

**Codegen:** 117 generated TypeScript payload types, **zero drift** after
regeneration. `schema_version?: SchemaVersion` — identical in form to
`PerceptionPresenceObservedPayload`.

---

## 4. Category 1 — architectural boundaries, each verified at the merged head

| Property | Evidence at `5b5ebfd` |
|---|---|
| Event Bus subjects | **119** (118 at base, exactly one added) |
| `cognitive_state.*` subjects | **0** — D-4F-6 holds |
| `PUBLIC_TOPICS` | **exactly 18**, unchanged |
| `perception.workspace.observed` public | **False** |
| `perception.workspace.observed` gateway-subscribable | **False** |
| `ws-gateway` perception subscriptions | exactly `presence.observed`, `identity.observed`, `sensor.health_changed`; **no wildcard** |
| `world-model-engine` production code | **0 files changed** (`src/` + `alembic/`) |
| New migration / ORM model | **0 / 0** |
| `POST /v1/perception/observations` | **0 deleted lines** — contract untouched |
| `api-gateway` `/v1/perception` | **absent** — nine proxied prefixes, none of them perception |

### 4.1 The one boundary this slice changed, and why

`ws-gateway`'s bus allow-list was narrowed from `perception.*` to those three
exact subjects. `*` spans dots under `fnmatchcase`, so the old pattern matched
`perception.workspace.observed` — meaning the gateway **process** would have
received raw workspace-sensor events even though `PUBLIC_TOPICS` correctly
stopped a browser naming the subject. Two allow-lists guard that boundary; only
the first was holding.

This is the identical gap `agent_os.*` was narrowed to `agent_os.task.*` to
close, and doc 09 §6 bounds this gateway to *"already-finalized events plus
read-only telemetry, never raw internal engine chatter."* The change was
**found during 4F.2 preparation, reported as an architectural ambiguity rather
than fixed silently, and ratified by the user before implementation.** The three
subjects that remain are exactly the three that are public.

---

## 5. Category 9 — tests, lint, types, imports

Run against the merged `phase-4` at `5b5ebfd`.

| Check | Result |
|---|---|
| `npx turbo run test --force` | **32/32 tasks, `Cached: 0`** — **2,730 passed, 204 deselected, 0 failed** |
| `npx turbo run lint --force` | **32/32** |
| `npx turbo run typecheck build --force` | **35/35** |
| `uv run pytest tools/tests -q` | **286 passed** |
| `uv run lint-imports` | **7 kept, 0 broken** |
| Codegen | **117 payload types, zero drift** |

New coverage added by this slice: `nova-contracts` **+16**, `perception-engine`
**+33**, `ws-gateway` **+7**, `world-model-engine` **+4**.

---

## 6. Category 10 — real infrastructure

**15 `real-infra` matrix rows green in CI**, including
`real-infra (perception-engine)`. **No new matrix row was added** — the existing
`perception-engine` row covers this slice, and 4F.2 introduces no new persistence
to exercise.

**Docker is unreachable in the authoring environment**, so every real-Postgres
and browser result recorded here is CI's and is labelled as such. No local run
is offered as evidence for either tier.

---

## 7. Category 11 — PR, branch, commit and CI evidence

| Item | Value |
|---|---|
| PR | **#31**, `phase-4f.2` → `phase-4`, **merged** 2026-09-15T23:46:39Z |
| Head | `cc0dcada923dda2bd06f4fc186aabd8e72e5cc6d` |
| Base | `4605d64950191bc08c4d1bc9d66a72ca8eaca030` |
| Merge commit | `5b5ebfd03d6b41710fc2f427a78206236d1ff392`, **exactly two parents** |
| Diff | **20 files, +1,296 / −4** |
| CI at the exact head | **39/39 green** — `checks` · 15 `real-infra` · 21 `build-and-scan` (incl. Trivy) · `dependency-audit` · Playwright |
| Reviews / comments | **0** |
| History | No squash, no rebase, no force push. `phase-4f.2` preserved, not deleted, and an ancestor of `phase-4` |
| `main` | **untouched** at `7e273e62e942ecd5528ca807e65933d6bb675669` |

**All four deletions are accounted for**: two widened `Literal` declarations, one
replaced import line, and the `perception.*` gateway pattern. No unrelated
formatting.

**CI's first run on this PR was green on all 39.** One row,
`build-and-scan (reasoning-engine)`, was re-queued by the runner and completed
five minutes after its siblings; `reasoning-engine` has 0 files changed here.

---

## 8. Category 1 — the timing boundary (§20.1)

Audited from the code before the PR was opened, and unchanged since.

| Prohibition | Evidence |
|---|---|
| No fake clock | Zero matches for `freezegun`, `time_machine`, `freeze_time`, `FakeClock`, monkeypatched or mocked `datetime` |
| No fabricated `observed_at` | Flows verbatim request → observation → payload; **required with no default**, so server time cannot silently substitute |
| No internal clock read | **AST analysis with docstrings stripped finds zero clock reads** in both new production modules; a test asserts `admit`'s own source contains none |
| No cron alignment | Zero references to the dispatcher, its cron or its schedule |
| No retry/sleep compensation | Zero matches in production code |
| Outbox dispatcher unchanged | 0 files changed |

**The debouncer is not an independent timing mechanism.** It performs one
subtraction on caller-supplied real event times, and the **first observation of
an object is always admitted**, so it adds nothing to the interval AC-7
measures.

**4F.2 does not prove AC-7 or AC-8.** Neither is claimed. AC-7's genuine OS-event
timing path completes in 4F.3, and its honest end-to-end measurement is 4F.8's
work (TDD §18, §20.1).

---

## 9. Category 1 — the identity boundary

`user_id` is resolved server-side from `Settings.primary_user_id` (ADR-025),
exactly as the pre-existing window pipeline does. With it unset the engine
publishes **nothing** and says why.

A client-supplied identity is **unrepresentable, not merely rejected**:
`WorkspaceObservationRequest` has no `user_id` field, and no `object_id` field
either, so a caller can forge neither an identity nor an object handle. A test
posts an attacker-shaped body and asserts the configured identity is what
reaches the payload.

**The raw filesystem path never reaches the bus.** `object_id` is a one-way
SHA-256 of the normalized path — `WorldObject`'s own docstring names *"a file
path hash"* as a sanctioned handle form — and `label` is the final segment only.

---

## 10. SLOC

`cloc` v2.06, `--skip-uniqueness --quiet`, from a pristine `git archive` extract
of `phase-4` at `5b5ebfd`. Scope includes `companion/` per the ratified
methodology change (TDD §17); the directory does not exist, contributing zero.

| | 4F.1 close `4605d649` | 4F.2 merged `5b5ebfd` | Δ |
|---|---|---|---|
| **4F scope (incl. `companion/`)** | **45,107** | **45,280** | **+173** |
| Comparable | 36,134 | 36,307 | +173 |
| Wider | 41,475 | 41,648 | +173 |

**Headroom to the 50,000 hard gate: 4,720.** The gate is **respected and not
threatened**. TDD §17 estimated 600–1,000 lines for 4F.2's perception work; the
actual cost was lower because the consumer needed no code at all.

---

## 11. Deferred-obligations ledger — protocol §0.2

**This is the ledger §0.2 requires**, so 4F's eventual Gate Review inherits a
complete list rather than rediscovering it. **A Sub-Phase may not be declared
complete while any row here is unsettled.**

### 11.1 Documentation deferred by §0.1 (categories 3–7, 12)

| # | Document / obligation | What changed | Settled by |
|---|---|---|---|
| L-1 | **4F Gate Review** (category 3) | Does not exist. 4F is one milestone; its Gate Review covers all eight slices | **4F closure**, after 4F.8 |
| L-2 | **`docs/project-health/phase-4f.md`** (category 4) | Does not exist. Cannot be written before L-1, since §4.1 requires every field cited to the Gate Review | **4F closure** |
| L-3 | **`project-health-master.md` summary row for 4F** | No 4F row exists | **4F closure** |
| L-4 | **`ENGINEERING_ROADMAP.md` 4F row** — full category-5 treatment | Status corrected additively here (§12); **acceptance-criteria status and deliverable list are NOT reconciled** | **4F closure** |
| L-5 | **`00-master-scope.md`** §17 SLOC table and 4F closure note | SLOC re-measured here but the scope document's own tables are not reconciled | **4F closure** |
| L-6 | **`README.md`** | `definition-of-done.md` item 5's trigger *"a new engine now exists"* **fired at 4F.1** (`cognitive-state-engine`) and has not been settled. README carries no Phase 4 status line and no engine count — verified, not assumed | **4F closure** |
| L-7 | **`perception-engine/README.md`** (category 7) | Does not describe the new subject, the structured intake route, or the `"filesystem"` sensor type | **4F.3**, when the sensor that uses them exists |
| L-8 | **`ws-gateway/README.md`** (category 7) | Does not record the `perception.*` → three-subject narrowing | **4F closure** |
| L-9 | **Cross-file consistency sweep** (category 12) | Not run for this slice | **4F closure** |
| L-10 | **`docs/` staleness sweep** (category 6) | Only the four claims falsified by 4F.1/4F.2 being merged were swept (§12). A full sweep was not run | **4F closure** |

### 11.2 Implementation deferred

| # | Obligation | Why deferred | Settled by |
|---|---|---|---|
| L-11 | **Fusion** for workspace signals (TDD §18 names it in 4F.2's row) | No workspace signal exists to fuse until a sensor produces one; extending `correlation_buffer` for a producer that does not exist is the speculative work the scope rule excludes | **4F.3** |
| L-12 | **`"filesystem"` source registration** in `sensors_by_source` | The sensor is 4F.3's. The route 404s on an unregistered source until then — disclosed in the PR and here | **4F.3** |
| L-13 | **`known_projects` correlation table is empty at runtime** | `memory-engine` owns `project_id` and `perception-engine` must not read its database (ADR-004), so it is populated over the Event Bus. Empty means `resolve_project_id` returns `None` — §9's honest unknown, correct before any project is known, but **the population path does not yet exist** | **4F.3 or later**; named in 4F's Gate Review either way |

### 11.3 A gap in 4F.1's record, recorded here rather than left unnoticed

**The 4F.1 slice completion record carries no deferred-obligations ledger.**
Protocol §0.2 requires one of every Slice completion report. Grepped and
confirmed absent.

This record does **not** retroactively rewrite 4F.1's — protocol §0.3.4 forbids
that, and the user's instruction not to create retrospective records for earlier
milestones applies. Instead, 4F.1's own deferrals are absorbed into this ledger
where they are still live: **L-1, L-2, L-3 and L-6 are as much 4F.1's
obligations as 4F.2's**, and L-6 was triggered by 4F.1 specifically. 4F's Gate
Review inherits them from here.

---

## 12. Category 14 — documentation corrected in this closure

Four documents carried claims that **4F.1 and 4F.2 being merged made false.**
All were already stale before this closure — 4F.1 had no formal closure pass, so
the staleness dates from its merge. Every correction is **additive**: the
original text is preserved with a dated note, per protocol §0.3.4 and
`definition-of-done.md` item 6.

| Document | Falsified claim | Correction |
|---|---|---|
| `ENGINEERING_ROADMAP.md` 4F row | **"Not started"** | 4F.1 and 4F.2 merged; 4F in progress, 2 of 8 slices |
| `ENGINEERING_ROADMAP.md` 4E row | *"no `phase-4f` branch exists — no Phase 4F work has started"* | Superseded note appended |
| `project-health-master.md` 4E row | *"No `phase-4f` branch exists and no Phase 4F work has started"* | Superseded note appended |
| `00-master-scope.md` TDD-4F cell | *"RATIFIED 2026-09-15 (§19), not yet implemented"* | Superseded note: slices 4F.1 and 4F.2 implemented and merged |

**No historical section was rewritten**, and no document outside these four was
touched.

---

## 13. Category 13 — carry-forwards, findings and ambiguities

### 13.1 Carry-forwards — all three remain OPEN

**CF-9 OPEN** — a 4F dependency; **4F.4's** work, in `action-engine`, its owning
engine. 4F.2 writes no policy row and does not touch that engine.
**CF-10 OPEN** — not a 4F.2 dependency; unchanged.
**CF-11 OPEN** — a 4F dependency; **4F.6's** work.

**This closure discharges, reinterprets and closes none of them.**

### 13.2 Findings carried forward, none blocking

| Finding | Disposition |
|---|---|
| `world-model-engine` has **one test-only file** changed | §20.2 requirement 4 requires consumer coverage and the repository has **no cross-engine test location**. The tests build the payload from the shared `nova-contracts` model rather than importing `perception-engine`, so no cross-engine coupling is introduced. **0 production files changed.** Reported, not a defect |
| `api-gateway` has **nine** proxied prefixes, not eight | TDD 4F §8 says eight. The substantive claim — none of them is `/v1/perception` — is still true. Stale count, additive correction due with L-4/L-5 |
| The producer path is **wired but not yet fed** | By design: L-12. The route 404s on an unregistered source until 4F.3 |

### 13.3 Ambiguity found during this closure

**Protocol §0.1 and the instruction for this closure disagree about what a slice
produces.** The closure request asked for a Phase 4F.2 project-health record,
master-index updates, roadmap status updates and an append to a "4F.2 Gate
Review". Protocol §0.1 defers categories 3–7 for a Slice, §4.1 requires health-
record fields to cite a Gate Review that does not exist, and no 4F.2 Gate Review
has ever been written.

**Resolved in favour of the protocol**, which the same instruction directed be
read and followed, and which instruction 7 made conditional on *"only if that is
exactly what the protocol requires from the evidence."* The deferred items are
ledgered above rather than fabricated. The roadmap and master-scope claims that
were **factually false** were corrected additively, because leaving a known
falsehood in place is not a deferral the protocol contemplates (§0.3 principles
2 and 3).

---

## 14. Final status

**4F.2: COMPLETE · VERIFIED · MERGED · CLOSED — as a slice of 4F.**

**Phase 4F is NOT complete.** Slices 4F.3 through 4F.8 remain, and no work on
them has begun: **no `phase-4f.3` branch exists**, `nova-companion` does not
exist, and `companion/` is absent from the tree.
