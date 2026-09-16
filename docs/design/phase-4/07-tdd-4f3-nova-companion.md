# TDD 4F.3 — `nova-companion`
## The Rust daemon, the filesystem sensor, and the first real OS signal

**Status:** **Design preparation. NOT RATIFIED.** §20 lists four questions that
must be answered before implementation begins.
**Date:** 2026-09-16
**Branch:** `phase-4f3-tdd`, cut from `phase-4` at `43d4036f237d416368fee9038981e2eec55e1633`
**Protocol:** [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md),
sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`, 1131 lines,
read from `origin/main` and verified in this session.

**This is a slice TDD, subordinate to
[TDD 4F](06-tdd-4f-companion-and-cognitive-state.md).** 4F is one milestone with
eight slices (TDD 4F §18); this document does not replace it, restate its
ratified decisions, or reopen anything it settled. Where the two disagree, TDD 4F
governs and the disagreement is recorded in §20 rather than resolved here.

---

## 1. Scope

TDD 4F §18's row for this slice, verbatim:

> **4F.3** | `nova-companion`: Cargo workspace, filesystem sensor, intake client,
> Dockerfile, CI (§16.4) | *Proves:* **A real OS signal enters the pipeline**

Five deliverables, and one proof.

| # | Deliverable | Where |
|---|---|---|
| 1 | **Cargo workspace** | `companion/nova-companion/` |
| 2 | **Filesystem sensor** — a real OS watcher | `companion/sensors/` |
| 3 | **Intake client** — HTTP to 4F.2's structured route | `companion/nova-companion/` |
| 4 | **Dockerfile** | `companion/nova-companion/Dockerfile` |
| 5 | **CI** — one `build-and-scan` matrix entry, one `pr-checks` Rust step | `.github/workflows/` |

**Plus one item this slice must close that its TDD 4F row does not name**, carried
from the 4F.2 ledger:

| # | Deliverable | Where | Ledger |
|---|---|---|---|
| 6 | **`FilesystemSensor` registered under `sensors_by_source["filesystem"]`** | `perception-engine` | **L-12** |

Without 6, deliverables 1–5 produce a daemon whose every request 404s. §5 explains
why this lands in Python rather than Rust, and §20.1 asks for that to be ratified.

### 1.1 Non-goals

Each is named because it is adjacent enough to be assumed.

| Not in 4F.3 | Owning slice |
|---|---|
| Desktop/window-focus, clipboard, process/system-health sensors | Later; **only the filesystem sensor is on the CI acceptance path** (TDD 4F §7.1) |
| Actuators — terminal and window control | 4F.5 at the earliest, and only as `action-engine` action types (TDD 4F §7.3) |
| Multi-modal **fusion** of workspace signals | **L-11.** Deferred from 4F.2 because nothing produced a signal; 4F.3 produces one, but fusion is not in this slice's row |
| `project_id` correlation population | **L-13.** `known_projects` stays empty; `resolve_project_id` keeps returning `None` |
| CF-9's write surface | 4F.4 |
| Autonomy Level 2 | 4F.5 |
| The initiative trigger | 4F.6 |
| `/v1/cognitive-state` and the panel | 4F.7 |
| **The AC-7 / AC-8 end-to-end acceptance run** | **4F.8.** See §3.2 |

---

## 2. Dependencies on 4F.1 and 4F.2

### 2.1 On 4F.2 — direct, and load-bearing

| Dependency | State at `43d4036` |
|---|---|
| `POST /v1/perception/workspace-observations` | **Exists.** JSON body `{path, observed_at}`; query `source`, optional `correlation_id`; `202` on accept |
| `WorkspaceObservationRequest` | **Exists.** Exactly two fields — deliberately no `user_id`, no `object_id` |
| `perception.workspace.observed` | **Registered.** Subject 119 of 119 |
| Path hashing, label reduction, debounce, enrichment | **Exist** in `domain/workspace.py` |
| Outbox publication | **Exists** — `enqueue_outbox`, the existing dispatcher |
| `sensor_type` / `source` literals admitting `"filesystem"` | **Widened** in 4F.2 |
| The `sensors_by_source["filesystem"]` **entry itself** | **Absent — this slice adds it (L-12)** |

**4F.3 changes none of the above.** It becomes the first caller.

### 2.2 On 4F.1 — none, directly

`cognitive-state-engine` is not on this slice's path. A workspace observation
reaches `world-model-engine`; nothing routes it to cognitive state until 4F.6.
Stated because the two are adjacent in the milestone, not because a dependency
was found.

### 2.3 On pre-existing architecture

The Sensor Abstraction Layer (2D-B), the `Sensor` Protocol and its lifecycle
state machine, the transactional outbox, and `world-model-engine`'s
`perception.*.observed` subscription — all unchanged by this slice.

---

## 3. Acceptance criteria and definition of done

### 3.1 The slice's own exit criterion

TDD 4F §18: ***"A real OS signal enters the pipeline."*** Decomposed into four
checkable claims:

| # | Claim | How it is proven |
|---|---|---|
| **S-1** | A real filesystem event on a real filesystem is detected by the companion | Cargo integration test: create/modify a file in a temp directory, assert the watcher emits an event. **No synthetic event injection** |
| **S-2** | The companion submits it to the existing route, unmodified | Cargo test against a stub HTTP server asserting method, path, query and body shape |
| **S-3** | `perception-engine` accepts it and enqueues exactly one outbox row | Python integration test with a registered `FilesystemSensor` |
| **S-4** | The raw path never leaves the companion's process boundary in the payload | The companion sends `path`; the **engine** hashes it. Asserted on the enqueued payload, as 4F.2 already does |

### 3.2 What 4F.3 does **not** claim

**AC-7 is not met by this slice and must not be reported as met.** TDD 4F §18
assigns the acceptance run to 4F.8, and §20.1 binds its measurement to be honest
— no cron alignment, no bounded retry, no scheduling technique that avoids the
worst-case dispatch latency.

4F.3 makes AC-7 *measurable* for the first time by supplying the genuine OS event
that starts its interval. It does not measure it. **AC-8 is untouched.**

### 3.3 Definition of done

`definition-of-done.md`'s ten items apply as they do to any slice. Protocol §0.1
assigns a Significant Slice categories **1, 2, 8, 9, 10, 11, 13, 14 in full** and
**3–7 and 12 as a deferred-obligations ledger** — so 4F.3 produces a **slice
completion record with a ledger**, not a Gate Review and not
`docs/project-health/phase-4f.md`. Both remain 4F's, at 4F.8.

**Item 5's trigger — *"a new engine now exists"* — is already outstanding as
L-6**, fired by 4F.1. 4F.3 adds a new *component* but no new engine; L-6 stays
open either way and 4F.3 must not silently absorb it.

---

## 4. Architecture — what the companion is, and is not

From TDD 4F §7, unchanged:

| | |
|---|---|
| **Persistence** | **None.** It owns no store and writes no database |
| **API surface** | **None exposed.** It is a client, never a server |
| **Event Bus** | **None.** It never connects to NATS |
| **Security boundary** | Internal network only; no browser-reachable port |
| **Failure behavior** | A failed sensor transitions `running → failed` and reports through the existing `SensorErrorReport` |

The consequence worth stating plainly: **the companion is not an engine.**
ADR-004's engine-to-engine prohibition is not engaged, because one side is not an
engine — it is a separate OS process speaking HTTP to an engine's internal route,
the posture TDD 4F §8 already recorded and ratified.

---

## 5. The two things called "the filesystem sensor"

This is the slice's central design question, and the TDD 4F does not separate
them. They are different objects in different languages:

| | **(a) The OS watcher** | **(b) The `Sensor` registry entry** |
|---|---|---|
| Language | Rust | Python |
| Lives in | `companion/sensors/` | `perception-engine` |
| Job | Watch a directory, emit events, POST them | Satisfy the `Sensor` Protocol so the route's lookup and lifecycle gate work |
| Knows about | The filesystem, one HTTP endpoint | Nothing about the filesystem |

**Why (b) must be Python, and must exist.** The 4F.2 route does
`state.sensors_by_source.get(source)` and then `sensor.state() != "running"`.
`sensors_by_source` is populated **only** in `main.py` at startup — verified: no
sensor-registration endpoint exists anywhere in `perception-engine`
(`api/sensors.py` exposes list, calibrate and diagnostics only). A Rust process
cannot implement a Python `Protocol`, so (b) is a perception-engine class,
exactly as `VoiceSensor` and `CameraSensor` are perception-engine classes that
represent capabilities executed elsewhere.

**What (b) does not do.** It performs no detection, holds no filesystem handle,
and reads no path. It is the lifecycle and permission representation of a source
whose events arrive over HTTP — which is what makes AC-7 clause 2's revocation
real: pausing it makes the route drop observations at the pipeline level, which
4F.2 already implements and tests.

**§20.1 asks for this split to be ratified**, because it is a design decision the
authoritative TDD leaves implicit.

---

## 6. Event Bus boundaries

**NONE. 4F.3 introduces no Event Bus change of any kind.**

| Property | Required state after 4F.3 |
|---|---|
| New subjects | **0** — total stays **119** |
| `perception.workspace.observed` | Unchanged; 4F.3 is its first real producer, not its author |
| `PUBLIC_TOPICS` | **Unchanged at 18** |
| `ws-gateway` subscriptions | **Unchanged** — the three narrowed in 4F.2 |
| `cognitive_state.*` | **0**, per D-4F-6 |
| The companion's own bus access | **None.** It never connects to NATS |

D-4D-1 governs: a subject exists to be consumed, and 4F.3 needs none that does
not already exist.

---

## 7. API boundaries

**NO NEW ROUTE. NO GATEWAY CHANGE.**

| Property | Required state after 4F.3 |
|---|---|
| New `perception-engine` routes | **0** — 4F.3 *calls* 4F.2's route |
| `POST /v1/perception/observations` | **Unchanged** |
| `POST /v1/perception/workspace-observations` | **Unchanged** — contract frozen by 4F.2 |
| `api-gateway` prefixes | **Unchanged at nine.** No `/v1/perception` |
| Browser-reachable perception surface | **None** |
| The companion's own listening port | **None** |

**If implementation finds the existing route insufficient, that is a blocking
finding to report, not a contract to amend.** 4F.2's route was designed against
this caller; a mismatch means one of the two is wrong and the user decides which.

---

## 8. Persistence

**NONE.**

| Property | Required state after 4F.3 |
|---|---|
| New migrations | **0** |
| New ORM models | **0** |
| Altered tables | **0** |
| The companion's own storage | **None** — TDD 4F §7 |

`sensor_registration` already accepts `"filesystem"`: the column is plain `TEXT`
with no CHECK constraint, verified against the migration chain in 4F.2. The
literal widening was Python-only then and stays Python-only now.

---

## 9. Security and privacy boundaries

### 9.1 The path

**The companion sends the path; the engine hashes it.** This is deliberate and
worth defending, because the opposite arrangement looks safer and is not:

- The engine already owns `object_id_for_path` and is already tested on the
  property that no path segment survives into the payload.
- Hashing in the companion would put a second, independent implementation of the
  handle format in a second language, where a divergence produces **duplicate
  world objects for one file** rather than a loud failure.

**The trust boundary is therefore the engine's process, not the wire.** The
companion → engine hop carries a real path and runs on the internal Docker
network only. §20.2 asks whether that is acceptable or whether the hash must move
into the companion.

### 9.2 Identity

**Unchanged and non-negotiable.** `user_id` is resolved server-side from
`Settings.primary_user_id` (ADR-025). The request model has no `user_id` field,
so the companion cannot supply one — a property 4F.2 tests directly, and which
4F.3 must not weaken by adding a field "for convenience".

### 9.3 Consent

**Open question — §20.3.** `api/consent.py` resolves sensors through the same
`sensors_by_source` map, so a registered `"filesystem"` source becomes
consent-addressable the moment it exists. But 4F.2's `handle_workspace_event`
does **not** call `has_active_consent`, and Doc 22 Principle 8 requires explicit
per-source consent. Whether watching a directory requires a consent grant is a
policy decision, not an implementation detail.

### 9.4 What the companion must not do

No actuator fires (TDD 4F §7.3). No bus connection. No listening port. No
writing anywhere outside its own logs. **No sensor may be started that the
configuration did not name** — a watcher defaulting to `$HOME` would be a
privacy decision made by a default value.

---

## 10. Observability

The companion is a new process class and the repository's observability stack is
Python-side (`nova-observability`). **4F.3 does not port it to Rust.**

| Requirement | Shape |
|---|---|
| Structured logs | JSON lines to stdout, matching the fields the Python stack emits — `timestamp`, `level`, `logger`, `message`, `service` |
| Correlation | The companion generates a `correlation_id` per observation and passes it as the route's existing query parameter, so one OS event is traceable end to end |
| Failure surfacing | A sensor failure transitions `running → failed` and reports through the **existing** `SensorErrorReport` path |
| Metrics | **None in 4F.3.** No Prometheus endpoint — that would require a listening port, which §4 forbids |

**No new observability dependency is introduced on the Python side.**

---

## 11. Testing strategy

### 11.1 Rust, in the companion

| Tier | What it covers |
|---|---|
| Unit | Event filtering and debounce-adjacent logic; config parsing; the request body builder |
| Integration | **A real temp directory and real file operations** — create, modify, delete — asserting the watcher emits. No injected synthetic events |
| Client | The intake client against a stub HTTP server: method, path, query, body, and the handling of `202`, `404` and `5xx` |

### 11.2 Python, in `perception-engine`

| Tier | What it covers |
|---|---|
| Unit | `FilesystemSensor`'s lifecycle against the existing `next_state` machine; `permission_status`; `capabilities` |
| Integration | The route end to end with the sensor **registered**, asserting one outbox row — the case 4F.2 could only reach with an injected sensor |
| Contract | `sensors_by_source` contains `"filesystem"`; the sensor satisfies the `Sensor` Protocol (`runtime_checkable`) |

### 11.3 Negative controls

| Control | Property |
|---|---|
| A paused sensor drops the observation | AC-7 clause 2 at the pipeline level |
| The companion opens no listening port | `§4`'s boundary, asserted rather than assumed |
| The companion imports no NATS client | No bus access |
| No new Event Bus subject is registered | Count stays 119 |
| `PUBLIC_TOPICS` stays 18 | Byte-identical |
| The payload still carries no raw path | The 4F.2 property, re-asserted with a **real** OS path |

### 11.4 What must not appear

**No fake clock, no fabricated `observed_at`, no synthetic filesystem event
standing in for a real one, and no sleep-based latency compensation.** TDD 4F
§20.1 binds this slice as it bound 4F.2. `observed_at` is the OS event's own
timestamp, read from the filesystem event, and travels unmodified.

---

## 12. Real-infrastructure requirements

| Requirement | Disposition |
|---|---|
| New `real-infra-checks` matrix row | **None expected.** 4F.3 adds no persistence; the existing `perception-engine` row covers the engine side |
| Real filesystem | **Required**, and satisfied by Cargo integration tests using a real temp directory — this *is* the real infrastructure for this slice |
| Docker | Needed for the image build only, which CI performs |

**Docker is unreachable in the authoring environment.** Every container and
CI-tier result will be CI's and must be labelled as such, never reported as a
local pass.

---

## 13. Browser / E2E requirements

**NONE in 4F.3.**

There is no UI surface, no panel and no browser-reachable route. Playwright is
untouched. The end-to-end run that exercises a browser is **4F.8's**, and the
panel it would read is **4F.7's**.

---

## 14. CI

TDD 4F §16.4 (D-4F-7) specifies the minimum, and it is correct as far as it goes:

1. **`build-and-scan.yml`** — one matrix entry for the companion's Dockerfile.
   The matrix already carries the path per entry, so no workflow restructuring.
2. **`pr-checks.yml`** — one step running `cargo fmt --check`, `cargo clippy` and
   `cargo test`, alongside the existing non-workspace steps.

### 14.1 What §16.4 does not account for — a blocking finding

**`tools/tests/test_dockerfile_runtime_hardening.py` will fail the moment a
companion entry joins the matrix.** Verified by reading it, not inferred:

```python
RUNTIME_STAGE  = "FROM python:3.12-slim"
HARDENING_LINE = "RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*"
```

`test_every_scanned_image_upgrades_its_base_packages` is parametrized over
**every matrix entry** and calls `_runtime_stage_lines`, which asserts the
Dockerfile contains a `FROM python:3.12-slim` stage. A Rust image has no such
stage, so the assertion fires.

**The guard anticipates this case in its own failure message:**

> *"Either it moved off the shared base — in which case this guard needs to learn
> the new one — or this parser is broken. **Do not delete the test to make this
> go away.**"*

So the sanctioned path is to **teach the guard a second runtime base**, keeping
the property it enforces (the runtime stage upgrades its packages) while
admitting a non-Python image. **§20.4 asks for the shape of that change to be
ratified before implementation**, because a test-infrastructure change is exactly
where a guard gets quietly weakened.

`test_dockerfile_workspace_deps.py` is **not** affected — it globs
`services/*/pyproject.toml` and `agent-os/*/pyproject.toml`, so a Rust component
is outside its scope. Verified.

### 14.2 Expected CI shape after 4F.3

| Workflow | Before | After |
|---|---|---|
| `build-and-scan` | 21 rows | **22** |
| `real-infra-checks` | 15 rows | **15** — unchanged |
| `checks` | 1 | **1** — one step added inside it |
| Total check runs | 39 | **40** |

---

## 15. Files and modules 4F.3 is expected to touch

**New:**

```
companion/nova-companion/          Cargo workspace root, Dockerfile, config
companion/sensors/                 the filesystem watcher crate
services/perception-engine/src/nova_perception_engine/sensors/filesystem_sensor.py
```

**Modified:**

```
services/perception-engine/src/nova_perception_engine/main.py   register the sensor
.github/workflows/build-and-scan.yml                            +1 matrix row
.github/workflows/pr-checks.yml                                 +1 Rust step
tools/tests/test_dockerfile_runtime_hardening.py                teach it the new base (§14.1)
docs/…                                                          the slice completion record
```

**Explicitly untouched:** `world-model-engine`, `nova-contracts`, `ws-gateway`,
`api-gateway`, `action-engine`, `autonomy-engine`, `cognitive-state-engine`,
`apps/`, every `alembic/`, every `repository/models.py`, and
`perception-engine`'s existing routes and contracts.

**Note on the repository tree.** Doc 02 shows `companion/nova-companion/`,
`companion/sensors/` and `companion/actuators/` as siblings, while TDD 4F §7
calls `companion/nova-companion/` "a Cargo workspace". A Cargo workspace normally
contains its member crates. §20 does not block on this; implementation should
follow doc 02's tree and record the reading it chose.

---

## 16. External dependencies

**New Rust crates are unavoidable** — this is the repository's first Rust
component. The expected minimum:

| Need | Note |
|---|---|
| Filesystem watching | The established cross-platform crate for this |
| HTTP client | Async, TLS not required on the internal network |
| Async runtime | Whatever the HTTP client requires |
| Serialization | JSON body construction |
| Structured logging | JSON lines to stdout (§10) |

**No new Python dependency is expected**, and none should be added: the
`FilesystemSensor` uses only what `perception-engine` already has.

`dependency-audit` runs in CI and will see the Rust manifest for the first time.
Whether it must be taught to audit Cargo, or whether Trivy's image scan is the
agreed coverage, is a question for implementation to surface if the job fails —
it is not assumed either way here.

---

## 17. SLOC

**Baseline at `43d4036`: 45,280 on the 4F scope. Headroom to the 50,000 hard
gate: 4,720.**

`companion/` is **inside** the measured scope, per the ratified methodology
change (TDD 4F §17) — which is precisely so this slice cannot land there
uncounted.

| Component | TDD 4F §17 estimate |
|---|---|
| **`nova-companion` (Rust)** | **1,000–2,500** |
| `FilesystemSensor` (Python) | ~80–150, not separately estimated in §17 |

**This is the slice most likely to move the gate.** At the top of the estimate,
45,280 + 2,500 + 150 ≈ **47,930**, leaving ~2,070 for 4F.4–4F.8. The gate is not
projected to be crossed, but the margin after 4F.3 is thin enough that **SLOC
must be measured and reported at 4F.3's closure, not deferred to 4F's**.

If 4F crosses 50,000, SAD 15 §10's hard gate applies: feature development pauses
and the Engineering Review Milestone is filed. **Code is never moved or reduced
to game the metric.**

---

## 18. Documentation requirements

| Document | Obligation |
|---|---|
| `companion/nova-companion/README.md` | New — what it is, what it never does (§4), how to run it |
| `services/perception-engine/README.md` | **L-7 settles here** — the new subject, the structured intake route, and the `"filesystem"` sensor type |
| The 4F.3 slice completion record | Required, **with a deferred-obligations ledger** (protocol §0.2) inheriting every still-open row |
| `00-master-scope.md` document index | A row for this TDD, added additively |

**Corrections are additive** (protocol §0.3.4). No historical record is rewritten,
and the 4F.1 completion record is not retrofitted with the ledger it lacks.

---

## 19. Deferred obligations relevant to 4F.3

From the [4F.2 completion record](../../roadmap/architecture-reviews/phase-4f2-workspace-perception-completion-record.md) §11.
**Thirteen rows exist; none is closed, reinterpreted or deleted by this document.**

| Row | Relevance to 4F.3 |
|---|---|
| **L-7** `perception-engine/README.md` | **Settles in 4F.3** (§18) — the sensor it describes will exist |
| **L-11** fusion | **Becomes possible** in 4F.3 — a real signal exists. **Still not in 4F.3's scope row**; §20 does not propose moving it |
| **L-12** `"filesystem"` source registration | **Settles in 4F.3** — deliverable 6 (§1) |
| **L-13** `known_projects` population | **Does not settle.** Needs a `memory-engine` event path; stays open |
| L-1, L-2, L-3, L-4, L-5, L-9, L-10 | 4F closure. **Unchanged** |
| **L-6** README / *"a new engine now exists"* | **Unchanged and still open.** 4F.3 adds a component, not an engine |
| L-8 `ws-gateway/README.md` | 4F closure. Unchanged |

**Carry-forwards: CF-9, CF-10 and CF-11 all remain OPEN.** 4F.3 touches none of
them. CF-9 is 4F.4's, CF-11 is 4F.6's, CF-10 is not a 4F dependency.

---

## 20. Open questions — ratification required before implementation

Four. The first three are design decisions the authoritative sources leave
implicit; the fourth is a blocking CI finding.

### 20.1 The Python `FilesystemSensor` — is the split ratified?

§5 establishes that a Python `Sensor` registry entry must exist inside
`perception-engine` for 4F.2's route to function, and that it performs no
detection. TDD 4F §7 places "the filesystem sensor" in `nova-companion` without
distinguishing the OS watcher from the registry entry.

**Recommendation: ratify the split as described in §5** — a
`sensors/filesystem_sensor.py` in `perception-engine`, mirroring `VoiceSensor`
and `CameraSensor`, holding no filesystem handle.

**The alternative, for completeness:** add a sensor-registration endpoint so the
companion registers itself at startup. **Not recommended** — it creates a write
surface that can register arbitrary sources, and 2D-C's design explicitly made
registration a startup-time configuration concern rather than a runtime API.

### 20.2 Where is the path hashed?

§9.1 proposes the companion sends the real path and the engine hashes it, so the
handle format has exactly one implementation.

**Recommendation: ratify engine-side hashing**, and with it the statement that
the trust boundary is the engine's process rather than the wire.

**If the wire must carry no path**, the hash moves to Rust and the TDD needs a
pinned, cross-language-tested handle format — a materially larger slice, and one
that trades a clear failure mode for a silent one.

### 20.3 Does a filesystem observation require consent?

Doc 22 Principle 8 requires explicit per-source consent. 4F.2's workspace path
does **not** check `has_active_consent`; the biometric path checks it only before
matching. Once `"filesystem"` is a registered source it becomes
consent-addressable through the existing endpoint.

**No recommendation offered.** This is a policy decision about whether watching a
user's own configured directory, under ADR-025's single-trusted-user model, is
the same kind of act as capturing their voice. **Whichever way it is ratified,
4F.3 must not change 4F.2's route behaviour without that ratification.**

### 20.4 How is the Dockerfile hardening guard taught the new base?

§14.1 is a **blocking** finding: the guard fails the moment the matrix gains a
non-Python image, and its own message forbids deleting it.

**Recommendation: generalize `RUNTIME_STAGE` from one string to a small mapping
of permitted runtime bases**, each with its own required hardening line, and
assert every matrix entry matches exactly one. This preserves the property —
every scanned image upgrades its base packages in its runtime stage — while
admitting a second base, and it keeps the anti-vacuity tests that already guard
the parser.

**What must not happen:** adding the companion to `UNSCANNED`. That would remove
Trivy coverage from the one component in this repository that ships a
compiled binary, and TDD 4F §16.4 explicitly requires the matrix entry.

---

## 21. Consistency audit

Every claim in this document that asserts current repository state was verified
against `phase-4` at `43d4036` during this preparation pass, not recalled.

| Claim | How verified |
|---|---|
| No sensor-registration endpoint exists | Grepped `sensors_by_source` / `sensors_by_id` across `perception-engine`; only `main.py` writes it |
| `api/sensors.py` exposes three routes | Read the decorators |
| The hardening guard is Python-specific | Read `RUNTIME_STAGE`, `HARDENING_LINE`, `_runtime_stage_lines` and the parametrization |
| The matrix guard discovers Dockerfiles repo-wide | Read its `rglob("Dockerfile*")` |
| `test_dockerfile_workspace_deps.py` excludes Rust | Read its glob patterns |
| `api-gateway` has nine prefixes, none perception | Grepped its source |
| Subjects 119, `PUBLIC_TOPICS` 18 | Executed against the merged tree |
| SLOC 45,280 / headroom 4,720 | `cloc` v2.06 from a pristine `git archive` extract |
| doc 02's `companion/` tree | Read it |

**No Rust toolchain, `cargo` job or non-Python artifact exists in CI today** —
confirmed, as TDD 4F §16.4 states.
