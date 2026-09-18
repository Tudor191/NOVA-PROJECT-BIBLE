# TDD 4F.3 — `nova-companion`
## The Rust daemon, the filesystem sensor, and the first real OS signal

**Status:** **RATIFIED 2026-09-16 (§20).** All four open questions are answered;
§20 records each decision and what it forbids. *(This line read "Design
preparation. NOT RATIFIED. §20 lists four questions that must be answered before
implementation begins." until the ratification — preserved per protocol §0.3.4.)*
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
why this lands in Python rather than Rust, **ratified as D-4F3-1** (§20.1).

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

**This split is ratified as D-4F3-1** (§20.1). Implementing the Python `Sensor`
Protocol in Rust, and adding a registration endpoint to avoid the split, are both
explicitly prohibited.

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
network only. **Ratified as D-4F3-2** (§20.2), which states the security
requirement over *outputs*: the raw path must not appear in the persisted
payload, the outbox row, the published event, or any downstream world-model
data. It exists transiently in the request path by design, because the engine
needs the source value to derive the handle.

### 9.2 Identity

**Unchanged and non-negotiable.** `user_id` is resolved server-side from
`Settings.primary_user_id` (ADR-025). The request model has no `user_id` field,
so the companion cannot supply one — a property 4F.2 tests directly, and which
4F.3 must not weaken by adding a field "for convenience".

### 9.3 Consent

**Ratified as D-4F3-3** (§20.3): **a policy boundary, not a new implementation.**

`api/consent.py` resolves sensors through the same `sensors_by_source` map, so a
registered `"filesystem"` source becomes consent-addressable the moment it
exists. But 4F.2's `handle_workspace_event` does **not** call
`has_active_consent`, and Doc 22 Principle 8 requires explicit per-source
consent.

**4F.3 adds no consent subsystem** — no API, no database, no policy engine — and
**does not claim one exists**. What it does instead is bind the watcher to an
**explicitly configured directory/source only**, never the whole filesystem and
never a default that resolves to one, which is what makes deferring the policy
question safe. The gap is disclosed and carried as **L-14** (§19).

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

### 13.1 The downstream world-model leg — why it stays outside 4F.3 — 2026-09-17

*Additive, per protocol §0.3.4. Nothing above is rewritten.*

A pre-gate audit raised, as finding **F-5**, that nothing in 4F.3 proves a
workspace observation is **persisted by `world-model-engine`**. That is correct,
and it is deliberate. It is recorded here so 4F's Gate Review inherits the
boundary rather than rediscovering it.

**It is not a shortfall against 4F.3's own acceptance claims.** §6's **S-4** is
ratified as *"Asserted on the enqueued payload, as 4F.2 already does."* That is
met, and exceeded: the raw path is now proven absent from the enqueued payload,
from the committed Postgres outbox row, **and** from the envelope a subscriber
actually receives over a real NATS connection.

**Four reasons it cannot be honestly closed inside this slice**, each a fact
about the current architecture rather than a preference:

1. **`world-model-engine` has no real-infrastructure test tier at all** — zero
   `real_infra` tests, and it is absent from `real-infra-checks.yml`'s matrix.
   Proving its persistence means creating that tier from nothing: a first
   real-Postgres fixture for `object_state_history`, plus a new matrix row.
2. **Driving its real consumer crosses ADR-004.** The subscription lives in that
   engine's own `main.py` lifespan, and import-linter's *"Engines are
   independent"* contract makes `nova_perception_engine` ↔
   `nova_world_model_engine` a structural prohibition. Placing the import in
   `tests/` — where the linter does not look — would evade the control rather
   than honour it.
3. **The one existing multi-engine harness does not contain the companion.**
   `docker-compose.local.yml` runs `perception-engine`, its outbox worker,
   `world-model-engine`, Postgres and NATS together, and the Playwright golden
   path already exercises them — but `nova-companion` is not a service in it.
   Adding one means mounting a watch root into a deployed stack, which decides
   what the companion may observe: exactly the consent-surface decision
   **D-4F3-3** forbids this slice from making.
4. Every remaining route closes the gap only by **faking the consumer, faking
   the transport, or duplicating world-model's implementation** — each forbidden,
   and each would assert the conclusion rather than test it.

**`world-model-engine` having its own handler tests is not proof of this path**,
and a successful NATS publication is not proof of downstream persistence. Both
are true today and neither is claimed as more than it is.

**No new ledger row is required: the leg is already owned.** TDD 4F §20.1 fixes
the AC-7 measurement chain as

```
… → Event Bus → world-model-engine → observable Digital Twin / Cognitive State state
```

and §18 assigns that E2E to **4F.8** — *"The final implementation slice … Performs
the real acceptance verification."* The downstream persistence leg is therefore
an existing 4F.8 obligation, not an unowned gap, and opening a fifteenth row for
it would duplicate one the milestone already carries.

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
admitting a non-Python image. **Ratified as D-4F3-4** (§20.4): the guard is
**generalized structurally for multiple runtime families** — Python images keep
their existing requirement, Rust images get their own explicit permitted base and
hardening line, and **the test must fail if a new runtime family appears without
an explicit rule**. Adding the companion to `UNSCANNED`, bypassing Trivy,
weakening or deleting the test, and changing CI policy to avoid scanning the Rust
image are each explicitly prohibited.

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

### 17.1 Measured at 4F.3, and one scope ambiguity recorded — 2026-09-17

*Additive, per protocol §0.3.4. Nothing above is rewritten and no ratified
methodology is changed here.*

**Measured: 46,005 on the 4F scope. Headroom to the 50,000 hard gate: 3,995.**
`cloc` v2.06 `--skip-uniqueness` over a pristine `git archive`, the 4E Gate
Review's tool and flags unchanged. The methodology is now scripted and
reproduces the 45,982 figure at `d9d922f` exactly.

Of the growth since 4F.2's 45,280, **+481 is the companion's Rust source**, +142
is its `Cargo.toml`/`Dockerfile`/`README.md` (see below), and **+23** is the
`describe()` path-redaction fix in `companion/sensors/src/lib.rs`. The four
integration and regression test files added for S-2/S-3/S-4 and F-7 contribute
**0** — tests are outside every scope (TDD 4F §17).

**The ambiguity, stated precisely rather than resolved here.** Two authoritative
statements do not pick out the same file set for `companion/`:

| Source | Wording |
|---|---|
| TDD 4F §17 | *"the measured scope is **extended to include `companion/`**"* — a directory |
| [Protocol](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md) | *"Production SLOC = **`src/` application code + Alembic migrations**, excluding blanks, comments, tests, generated code, and documentation"* |

They differ by **142 lines** — `Cargo.toml` ×3 (44), `Dockerfile` (15) and
`README.md` (83). The README is *documentation*, which the protocol excludes by
name; the other two are neither application source nor a migration. No Python
component contributes an equivalent, because every other scope entry is written
as `<component>/src`, so `companion/` counted as a bare directory is measured
**more generously than any engine**.

| Reading | Figure | Headroom |
|---|---|---|
| **A — as reported**: `companion/` less `companion/*/tests` | **46,005** | 3,995 |
| **B — protocol definition**: `companion/*/src` only | **45,863** | 4,137 |

**The gate is not crossed under either reading, and the choice changes no
decision** — which is why this is a documentation reconciliation and not a gate
question. **Reading A is retained** as the reported figure because it is the one
the ratified wording produces and the one 4F.2's record and this section's own
baseline series were measured under; changing it now to make the documents agree
would be exactly the silent methodology change the protocol forbids.

**Disposition: this remains OPEN and is not dischargeable at 4F.3.** Ledger
**L-5** already owns it (*"`00-master-scope.md` §17 SLOC table … Settled by 4F
closure"*), §17 above requires the methodology entry to be written into
`project-health-master.md` §2 *"when 4F's health record is written"*, and
protocol §4.3 makes that entry mandatory only when the tool or scope changed. **No
new ledger row is opened**: recording both figures here is what L-5 needs in
order to be settled at 4F closure with an explicit decision rather than a
rediscovery.

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
This slice's ratifications open a fourteenth, **L-14** (§19.1).

| Row | Relevance to 4F.3 |
|---|---|
| **L-7** `perception-engine/README.md` | **Settles in 4F.3** (§18) — the sensor it describes will exist |
| **L-11** fusion | **Becomes possible** in 4F.3 — a real signal exists. **Still not in 4F.3's scope row**; §20 does not propose moving it |
| **L-12** `"filesystem"` source registration | **Settles in 4F.3** — deliverable 6 (§1) |
| **L-13** `known_projects` population | **Does not settle.** Needs a `memory-engine` event path; stays open |
| L-1, L-2, L-3, L-4, L-5, L-9, L-10 | 4F closure. **Unchanged** |
| **L-6** README / *"a new engine now exists"* | **Unchanged and still open.** 4F.3 adds a component, not an engine |
| L-8 `ws-gateway/README.md` | 4F closure. Unchanged |

### 19.1 New ledger row opened by this slice's ratifications

| Row | Obligation | Why it is deferred | Settled by |
|---|---|---|---|
| **L-14** | **Doc 22 Principle 8 per-source consent for the `"filesystem"` source** | D-4F3-3 (§20.3) ratifies consent as a **policy boundary, not a new implementation**: 4F.3 adds no consent subsystem and does not claim one exists. The architecture provides no filesystem-specific consent mechanism today — `has_active_consent` exists and is addressable, but the workspace path does not call it. The risk is bounded by binding the watcher to an **explicitly configured directory/source only** | **4F closure**, or earlier if a filesystem consent policy is ratified |

**Carry-forwards: CF-9, CF-10 and CF-11 all remain OPEN.** 4F.3 touches none of
them. CF-9 is 4F.4's, CF-11 is 4F.6's, CF-10 is not a 4F dependency.

### 19.2 L-11's settler is corrected — 2026-09-18

*Additive, per protocol §0.3.4. The 4F.2 completion record is **not** rewritten;
its L-11 row stands as written and this records the correction against it.*

**L-11 is NOT settled by 4F.3, and its recorded settler is wrong.** The 4F.2
ledger dates it *"Settled by **4F.3**"*. This document — ratified later, and
specifically about this slice's scope — declines it twice: §1.1's non-goals
table lists *"Multi-modal **fusion** of workspace signals … fusion is not in this
slice's row"*, and §19's table says *"**Still not in 4F.3's scope row**; §20 does
not propose moving it."* The ratifications did not move it in, and the
implementation did not quietly add it.

**Verified against the code, not inferred from the prose:**

| Check | Result |
|---|---|
| `workspace_orchestration.py` / `domain/workspace.py` reference `correlation_buffer` or `identity_fusion` | **No** — neither name appears |
| 4F.3 changed `domain/correlation_buffer.py` or `domain/identity_fusion.py` | **No** — `git diff` against `phase-4` is empty for both |
| Either fusion module mentions `workspace` | **No** |

S-1 through S-4 are **not** evidence for L-11 and are not offered as such: they
concern detection, transport, persistence and path absence, none of which is
fusion.

**Correct settler, derived from the ratified documents rather than chosen.**
TDD 4F §18 names fusion in **4F.2's row only**; no row for 4F.4, 4F.5, 4F.6,
4F.7 or 4F.8 names it. With 4F.2 closed and 4F.3 declining it, no slice row owns
it. Protocol §0.2's backstop therefore applies — *"A Sub-Phase may not be
declared complete while any ledger row from any of its Slices is unsettled"* — so
**L-11's settler becomes 4F closure**, where it must be either implemented by a
slice that claims it or recorded as an accepted deferral beyond 4F.

**No new ledger row is opened.** L-11 already exists and keeps its number; only
its *Settled by* field is corrected. Creating a fifteenth row for the same
obligation would duplicate it.

**One observation for whoever settles it, offered as context and not as a
discharge.** TDD 4F §9 defines Fusion as extending `correlation_buffer.py` and
`identity_fusion.py`, under the constraint that it *"never raises confidence
above what its inputs support"* with `SINGLE_SIGNAL_CONFIDENCE_CEILING = 0.75`
unchanged — that is **identity** fusion over multi-modal identity evidence. A
`perception.workspace.observed` payload carries no identity evidence: its
`user_id` is resolved server-side from `Settings.primary_user_id` (ADR-025), not
observed. Whether multi-modal fusion is therefore a no-op for this signal type,
or whether it means something else here, is a determination for 4F closure to
make explicitly. **This document does not make it.**

---

## 20. Ratified decisions — 2026-09-16

All four questions raised by this document's preparation pass are **answered and
binding**. The question each replaced is preserved in its own subsection so the
reasoning that produced the decision is not lost.

### 20.1 D-4F3-1 — the sensor split. **APPROVED.**

**The filesystem sensor is intentionally split across two layers:**

| Layer | Owns |
|---|---|
| **Rust `nova-companion`** | Real OS filesystem observation |
| **Python `perception-engine`** | `sensors_by_source["filesystem"]` registration, and the existing intake and domain processing |

**The registration entry is a required implementation detail, not an
optional convenience** — the existing intake route gates on
`sensors_by_source["filesystem"]`, so without it every request 404s.

**Prohibited:**
- **Do not** attempt to implement the Python `Sensor` Protocol in Rust.
- **Do not** add a registration endpoint merely to avoid this split.

*The question this replaced:* §5 established that a Python `Sensor` registry
entry must exist for 4F.2's route to function and that it performs no detection,
while TDD 4F §7 places "the filesystem sensor" in `nova-companion` without
distinguishing the OS watcher from the registry entry. The alternative
considered and rejected was a sensor-registration endpoint, which would create a
write surface able to register arbitrary sources and would contradict 2D-C's
decision to make registration a startup-time configuration concern.

### 20.2 D-4F3-2 — path hashing. **APPROVED.**

**`nova-companion` sends the real filesystem path to the existing perception
intake. `perception-engine` is the single authority responsible for hashing the
path and producing the persisted/enriched handle.**

**Prohibited:** **do not** implement a second path-hashing algorithm in Rust.

**Ratified clarification of the security requirement.** The path exists
**transiently** inside the companion and the request-processing path, because the
engine needs the source value to derive its handle. The requirement is therefore
stated over *outputs*, not over the wire:

> **The raw path must not be present in the persisted payload, the outbox row,
> the published event, or any downstream world-model data.**

This is the property 4F.2 already tests, and the property 4F.3's S-4 re-asserts
against a **real** OS path. §9.1's framing — "the trust boundary is the engine's
process, not the wire" — is ratified as an accurate description of that boundary.

*The question this replaced:* whether the hash belongs in Rust or Python. Moving
it to Rust would put a second implementation of the handle format in a second
language, where a divergence produces duplicate world objects for one file rather
than a loud failure.

### 20.3 D-4F3-3 — consent. **RATIFIED AS A POLICY BOUNDARY, NOT A NEW IMPLEMENTATION.**

**4F.3 must not invent or introduce a new consent subsystem.**

| Required | |
|---|---|
| Scope of watching | **Only an explicitly configured directory/source.** Never the entire filesystem, and never a default that resolves to one |
| Consent mechanism | **None added.** No new consent API, no consent database, no policy engine in this slice |

**Doc 22 Principle 8's per-source consent requirement is preserved as an
explicitly documented policy boundary and a deferred concern**, because the
current architecture provides no filesystem-specific consent mechanism:
`has_active_consent` exists and is addressable, but 4F.2's workspace path does
not call it and 4F.3 does not add that call.

**Prohibited:** **do not** silently claim that a filesystem consent mechanism
exists. The absence is disclosed, not designed around.

This deferral is carried as a new ledger row — **L-14**, §19 — so 4F's Gate
Review inherits it rather than rediscovering it.

*The question this replaced:* whether watching a user's own configured directory,
under ADR-025's single-trusted-user model, is the same kind of act as capturing
their voice. The decision defers the policy question while binding the
implementation to the narrow, configured-only behaviour that makes deferring it
safe.

### 20.4 D-4F3-4 — the Docker runtime-hardening guard. **APPROVED.**

**The existing runtime-hardening test must be generalized structurally for
multiple runtime families.**

| Runtime family | Requirement |
|---|---|
| **Python images** | Retain the existing Python runtime-base hardening requirement, unchanged |
| **Rust images** | Receive their own **explicit** permitted runtime base and corresponding hardening requirement |

**The test must fail if a new runtime family is introduced without an explicit
hardening rule.** That is the property being preserved: the guard's job is to
make an unhardened runtime stage impossible to ship unnoticed, and generalizing
it must not turn it into a check that silently passes anything it does not
recognize.

**Prohibited, each explicitly:**
- **Do not** add the companion to `UNSCANNED`.
- **Do not** bypass Trivy.
- **Do not** delete or weaken the runtime-hardening test.
- **Do not** hard-code a false Python-only assumption.
- **Do not** modify CI policy to avoid scanning the Rust image.

*The question this replaced:* §14.1's blocking finding — `RUNTIME_STAGE` is
pinned to `"FROM python:3.12-slim"` and the test is parametrized over every
matrix entry, so it fails the moment a Rust image joins. The guard's own failure
message anticipated exactly this and forbade deleting it.

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

### 21.1 How to count Event Bus subjects — 2026-09-17

*Additive. The figure of **119** stated throughout this document is correct and
is not amended; this records only how to reproduce it.*

**Count the runtime registry, never the decorator text:**

```python
len(_REGISTRY)  # after importing every nova_contracts submodule → 119
```

A grep for `@register_payload("…")` across `nova-contracts/src` returns **120**,
and the extra match is not a subject: it is the usage example
`@register_payload("some.subject")` inside `registry.py`'s own **module
docstring**. A pre-gate report of this slice briefly cited 120 as authoritative
on the strength of that grep; it was wrong, and no repository document ever
carried the figure.

The distinction is not new. Phase 4E's Gate Review already recorded both numbers
separately and correctly — *"118 registered subjects at base, 118 at head;
`@register_payload` call sites 119 at both"* — the same one-line offset, from the
same docstring. Adding 4F.2's single subject gives **119 registered / 120 call
sites**, which is what the tree holds today.

**No test pins this total**, so it is a reported figure rather than an enforced
invariant. What *is* enforced is narrower and lives in `ws-gateway`'s
`test_protocol.py`: that no raw perception subject becomes browser-subscribable.
