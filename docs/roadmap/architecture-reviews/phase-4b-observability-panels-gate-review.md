# Architecture Review Report — Phase 4B: Observability Panels

**Phase:** 4B — Observability panels (Planning, Reasoning Trace, Capabilities,
Approvals, Events, Health)
**Completed:** implementation and engineering verification complete 2026-09-06;
**gate verdict NO-GO** pending one user decision (§15)
**Design document(s):** [`docs/design/phase-4/00-master-scope.md`](../../design/phase-4/00-master-scope.md)
§5 (4B), §6 (panel scope table), decision **D-8**. **No 4B TDD exists** — see §4.1.
**Author:** AI-assisted (Claude Opus 5), executing
[`docs/PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md)
as read from `origin/main` at `733a31d`.
**Verified code SHA:** `0f3412c73b6dbd28b48c6f1ff9de14db3c238e53` — every figure in
§6–§8 was produced against it. Commits after it change documentation only.

---

## 0. Read this section first

Phase 4B's **engineering** verification is unambiguous and green: 30 of 30 GitHub
Actions Check Runs succeeded against the exact head SHA, including a full
Docker-backed end-to-end run of the real stack. That result is recorded in §6–§8
and is not in doubt.

This Gate Review nonetheless returns **NO-GO**, for one reason: **acceptance
criterion AC-3, the criterion the master scope assigns to this milestone, is not
met** (§9). Three approved panel capabilities named in master scope §5 were also
not built (§2). Neither fact was visible from CI, because no test asserts them —
which is precisely why this protocol requires the acceptance criteria to be
enumerated from the design documents rather than inferred from a green pipeline.

The verdict is a NO-GO under [protocol §3.2](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md),
which states that an unmet acceptance criterion is a NO-GO *unless the user has
explicitly approved deferring it*, and that CONDITIONAL-GO "is not a way to pass a
phase with an unmet acceptance criterion." The user has not been asked. §15 states
exactly what an approval would need to say and what the verdict becomes if given.

**Nothing in this review asks for Phase 4A to be reopened, and nothing in it
changes any Phase 4B production code.**

---

## 0.1 Update — 2026-09-06, second pass (head `2f0414a`)

The three narrowings this review reported as unbuilt (**DEV-1**, **DEV-2**,
**DEV-3**) have since been **built and verified against the real stack**. The
register in §2.1 and the criteria table in §9 are preserved verbatim below as
the first pass wrote them; this section records what changed, per principle
0.3.4.

| Was | Now |
|---|---|
| **DEV-1** Capabilities list-only | **Built.** Install and uninstall through `api-gateway` → `capability-engine`'s existing `POST /v1/capabilities/install` and `DELETE /v1/capabilities/{id}`. No backend change was needed. Three E2E tests green against the live stack: install→appears→uninstall→gone; a 422 surfacing the engine's own failing stage; malformed JSON refused client-side. Not routed through Approvals — the install pipeline's stage 4 is explicitly non-blocking disclosure, unlike `action-engine`'s Critical-risk loop, so routing it there would invent a gate the architecture does not have |
| **DEV-2** Events unfilterable | **Built.** Filterable by subject and by `correlation_id` — the two dimensions a raw bus frame is identified by, taken from the envelope rather than invented. Filters live in the Zustand store (doc 04 §5's "local filters") and apply **at render, never at ingest**, so the feed keeps recording while filtered and clearing restores everything that arrived meanwhile. E2E green, including that realtime keeps delivering *through* an active filter |
| **DEV-3** `reasoning_level` shown as depth | **Built.** The panel now shows both, because they are different facts: `reasoning_level` is Bible Part 8's 1–4 dial the caller sets, the depth is what the Multi-step pipeline did. No contract changed and no field invented — `ReasoningTrace.steps` (§11's recursion tree) and `multistep_recursion_exhausted` were already on the trace the engine returns; depth is derived from the tree, counted so that an un-recursed trace reads 1 and is directly comparable with `ModeConfig.max_step_depth` |

**Blocker B-2 is therefore discharged.** Blocker **B-1** (AC-3) is not, and its
composition has changed — see §9.1.

### 0.2 A new architectural finding: the approval loop is unreachable here

AC-3's remaining clause is *"a risky action is blocked pending approval and then
approved"*. Building the E2E for it surfaced a mechanism no document had
connected to this criterion:

```
threshold = 1.0  # absent-policy fails closed (domain/pipeline.py:182)
effective_confidence = confidence if confidence is not None else 0.0
if effective_confidence < threshold:  ->  denied
```

Stage 3's **ADR-032 identity-confidence gate** requires confidence ≥ 1.0 when no
`IdentityConfidencePolicy` row exists, and observes 0.0 when no perception
activity has scored the requesting user. Every Critical-risk Action in the 4B
stack is therefore **denied at Check Permissions and never reaches the approval
loop**. Nothing writes a `pending_approval` row, so nothing can appear in the
Approvals panel.

This is the gate working exactly as designed and documented (TDD 3D §10,
`action-engine/README.md`), not a Phase 4B defect. **Seeding a zero-threshold
policy for the test user would have made the spec green by weakening a security
control**, so it was not done — protocol §13's stop rule applies, and the
decision is recorded in §13 as **G-7** rather than taken here.

A second, independent blocker on the same clause: `action.execute` may only be
published by `agent-os/kernel`, which has no compose service until 4C (D-5).
`tools/e2e_request_risky_action.py` stands in for it using the Kernel's own
`BoundEventBus` allow-list, and that part works — the request reaches
`action-engine`, which then denies it at stage 3.

---

## 0.3 Update — 2026-09-06, third pass: AC-3's approval clause is deferred by explicit user approval

The user explicitly approved deferring AC-3's approval-execution clause on
2026-09-06. Recorded here under [protocol §2.4](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md)
as **"Deferred by approval (approval cited)"**, which §3.2 requires before an
unmet criterion can be anything other than a NO-GO. §9 and §9.1 carry the
status; §15 carries the resulting verdict.

**The approval's own stated reason, which is not the obvious one and must not
be paraphrased away.** The deferral is **not** because AC-3 depends on Phase
4D. [`00-master-scope.md`](../../design/phase-4/00-master-scope.md) §1.1 says
the opposite in as many words — *"AC-1 through AC-4 do not depend on any new
engine. They depend only on surfacing what Phase 3 already built."* The
deferral is because the **Phase 3D** `IdentityConfidencePolicy` configuration
mechanism required by [**ADR-032**](../../architecture/adr/ADR-032-identity-confidence-is-also-an-authorization-signal.md)
decision point 2 — *"a configurable identity-confidence threshold per
privileged capability (or per capability class)"* — was never built.
`domain/models.py:46` defines the model and `repository/models.py:87` defines
the `action.identity_confidence_policy` table, but the only code path is the
read (`find_identity_confidence_policy`). There is **no endpoint, no seed, no
migration insert and no admin surface** that can create a row. Protocol §13.1's
*"missing mechanisms — a required capability the architecture has no defined
home for"* is exactly this, and §13.3's stop rule says to report it rather than
improvise one.

| | |
|---|---|
| **Original ownership** | **Phase 3D / ADR-032.** The gate, the model and the table are `action-engine`'s, and ADR-032 point 2 places the obligation to expose a configurable threshold on the gating engine |
| **Discovering phase** | **Phase 4B.** 4B did not create the gap; building AC-3's E2E is what surfaced it |
| **Phase 4B deliverable, retained in scope** | The Approvals **panel and surface**: REST reads through `api-gateway`, `action.approval.requested`/`.decided` bound through `ws-gateway`, Approve/Deny controls, and the reducer that removes a row only when the bus says it was decided. All built, all rendering, all verified live |
| **Deferred clause** | The **end-to-end Critical-risk approval execution demonstration** — "blocked pending approval and then approved", driven from the browser |
| **Future routing** | **Phase 4D's `autonomy-engine` policy surface** (Policy Engine, Permission Matrix), as the appropriate future home for a per-user, per-risk-tier authorization threshold. Recorded as **CF-9** in master scope §4. This is a **forward routing decision, not a reassignment of historical ownership** |
| **Security rule** | **No identity-confidence threshold was invented, and the fail-closed default was not weakened** |

**What was deliberately not done, and why.** With no policy row the required
confidence is 1.0 (TDD 3D §7: *"Absent policy → fails closed"*); with
`perception-engine` absent from the E2E stack the observed confidence is 0.0.
Seeding a zero-threshold policy would have made the spec green by disabling the
ADR-032 gate for that user. `perception-engine` was not added to the stack to
force the clause green either — and could not have sufficed:
`identity_fusion.py:46` caps a single-signal identity at
`SINGLE_SIGNAL_CONFIDENCE_CEILING = 0.75`, below the 1.0 the absent-policy
default requires. **The gate is passable only *with* a policy row**, which is
what makes the missing mechanism mandatory rather than optional, and what makes
choosing its value a security decision reserved to the user by §2.1's *"descoping
a criterion requires the user's explicit approval, recorded; it is never the
agent's call"*.

**AC-3 is not "met".** One of its four sub-clauses is met, one is deferred by
this approval, and two cannot be verified in this environment. §9.1 carries the
accounting.

### 0.4 G-8: the golden path was red because the outbox never reached the bus

Separately from G-7, the 4A golden path had been intermittently failing since
Phase 4B — including on `85f7682`, a **documentation-only** commit, where
`2f0414a` had passed with identical application code. Diagnosed to root cause
and fixed in `26eb4f4`. Full account in §4.1; the finding in one line: **all ten
engine workers shared one Redis, one arq queue and one cron job name**, so
`communication-engine`'s outbox was dispatched on roughly one tick in four. It
is a pre-existing Phase 2/3 defect that Phase 4B's four-worker E2E stack was the
first configuration to expose.

---

## 1. What was implemented

Five commits on `phase-4b`, branched from the merged `phase-4` head `481ceac`.

| Commit | Scope |
|---|---|
| `9af0708` | `api-gateway` route table 2 → 5 prefixes; `ws-gateway` `PUBLIC_TOPICS` 8 → 17; topic-guard correction |
| `b10e30d` | `GET /v1/plans` (planning-engine), `GET /v1/action/approvals` (action-engine) |
| `a7cf674` | Six panels, six `entities/` modules, reducers, lazy routing, 30 new frontend tests, E2E spec |
| `b22ec83` | E2E correction — Capabilities asserts rows, not emptiness |
| `0f3412c` | E2E correction — panels asserted to *settle*, not what they settle on |

43 files, +2,619 / −71. `packages/nova-contracts/` untouched.

### 1.1 Gateway surface

`build_route_table` returns five `UpstreamRoute`s: `/v1/communication`,
`/v1/plans`, `/v1/reasoning`, `/v1/capabilities`, `/v1/action`. Paths are
forwarded verbatim against an allow-list, not a pattern — decision **D-6**.
`executive-cognition-engine` and `nova-core` are deliberately not fronted;
`services/api-gateway/src/nova_api_gateway/domain/routing.py`'s docstring records
why.

`ws-gateway` `PUBLIC_TOPICS` grew to 17, with matching narrow patterns in
`events/subscribed.py`: `planning.task_graph.*`, `reasoning.process.*`,
`reasoning.human_override.*`, `action.approval.*`, `ai_model.model.*`,
`nova.module.status_changed`. `capability-engine` gets no entry — it publishes no
domain events, and inventing one is how `PUBLIC_TOPICS` acquired three dead topics
that 4A had to remove.

**A 4A guard defect was found and corrected.** `test_every_public_topic_is_reachable_on_the_bus`
compared `topic in SUBSCRIBABLE_SUBJECTS or f"{first}.*" in SUBSCRIBABLE_SUBJECTS`,
which silently passes any subject containing `*`. `BoundEventBus` authorises
subscriptions with `fnmatchcase`, where `*` spans dots. The guard now uses
`fnmatchcase`, and a parametrised test pins that it matches the way the SDK does.

### 1.2 Backend endpoints

Two, both additive; no existing route changed.

- `planning-engine` `GET /v1/plans` — declared **before** `/{task_graph_id}`
  because FastAPI matches in declaration order. Ordering lives in the repository
  (`ORDER BY created_at DESC`) because the `TaskGraph` domain model carries no
  `created_at` field.
- `action-engine` `GET /v1/action/approvals` — undecided only, oldest first,
  matching the order the panel's reducer maintains.

### 1.3 Panels

Six panels, six `entities/` modules, seven lazily-loaded routes beneath a layout
shell. `RealtimeProvider` sits above the router outlet so navigation does not
remount the socket and lose frames — most visible in the Events panel, exactly
where a gap in the stream is the subject.

One envelope throughout (`{data, meta, error}`). No polling for realtime state.
No optimistic mutation of shared cognitive state.

---

## 2. Why each architectural decision was made

| Decision | Alternative | Why this one |
|---|---|---|
| Health panel is **push-fed**, with no REST source | Build `GET /v1/system/health` on `nova-core` | `nova-core` exposes only `/internal/*`, which [doc 11 §3](../../architecture/11-api-architecture.md) makes permanently unroutable. Building the endpoint means giving `nova-core` a public HTTP surface — an architectural decision outside 4B's remit (§13, item G-1) |
| Approvals reconcile from the bus, never from the click | Optimistic removal | Shared cognitive state. A 409 (someone else decided first) would already have rendered as done. Negative-controlled (§7) |
| Confidence rendered as a tier word | Raw score or percentage | A number implies a precision the engine does not claim |
| A failed reasoning process reports **no** confidence | `0` | Zero asserts the engine was certain it was wrong; absence is the fact |
| A silent module goes `unknown` after 45s | Keep last good status | Silence is not health. Negative-controlled (§7) |
| Events keeps **arrival** order | Sort by `generated_at` | Re-sorting hides the out-of-order delivery the panel exists to show |
| Panels lazily loaded | One bundle | The Conversation panel — the one AC-1 measures — must not wait for six panels the operator may never open |

### 2.1 Deviation register

| # | Deviation | Class | Approval |
|---|---|---|---|
| **DEV-1** | Capabilities panel is **list-only**. Master scope §5 specifies "(list / install / uninstall)" | **Undisclosed narrowing** | **None.** `capability-engine` already exposes `POST /v1/capabilities/install` and `DELETE /v1/capabilities/{id}`, and `api-gateway` forwards `/v1/capabilities` — both were reachable and simply not built |
| **DEV-2** | Events panel has **no filter**. Master scope §5 specifies "filterable raw bus inspector" | **Undisclosed narrowing** | **None** |
| **DEV-3** | Reasoning Trace renders `reasoning_level` (the 1–4 reasoning tier), not **3A's recursion depth**. Master scope §5 specifies "including 3A's recursion depth" — which is `MultiStepConfig.max_step_depth` / `multistep_recursion_exhausted` (`services/reasoning-engine/src/nova_reasoning_engine/domain/models.py:298,351,378`), a different field | **Undisclosed narrowing** | **None** |
| **DEV-4** | `GET /v1/system/health` not built; Health is push-fed | **Disclosed narrowing** | Disclosed in PR #24 and in §2 above; grounded in doc 11 §3. Still requires ratification (§15) |
| **DEV-5** | `useLiveProcesses` uses `queryFn: undefined, enabled: false` rather than `skipToken`, unlike the other two push-fed keys | **Defect (cosmetic)** | None needed. Behaviour identical; emits a TanStack "no queryFn was passed" warning on mount |

DEV-1 through DEV-3 are the substance of the NO-GO alongside AC-3. Protocol
principle 0.3.6: *"Never narrow scope unilaterally. If part of a phase's approved
scope was not built, the phase is not complete."*

---

## 3. Tradeoffs considered

- **Six panels at once (D-8) over a subset.** Approved. Marginal cost of the sixth
  is far below a second pass. Held: the shared `AsyncPanelBody` and `entities/`
  layer made panels 2–6 cheap.
- **Reading existing surfaces over inventing new ones.** Only two endpoints were
  added; all 115 generated TypeScript contract types already existed. The cost is
  that panels show what the engines happen to expose, not an ideal shape.
- **Empty-state honesty over a populated-looking demo.** Seeding data would have
  made the panels look busy and stopped them testing the transport. The cost is
  that a green E2E proves reachability, not richness — which is exactly the gap
  AC-3 measures and §9 reports as unmet.

---

## 4. Known limitations

Every item here is disclosed, none is hidden, and none is presented as resolved.

1. **AC-3 is not met** — §9. The governing limitation of this milestone.
2. **DEV-1/2/3** — install/uninstall, event filtering, and recursion depth are
   not built (§2.1).
3. **`reasoning.process.*` and `ai_model.model.*` carried no observed frame.**
   Both subjects are authorised (negative-controlled topic guard, §7) and both
   owning workers start in the real stack (§8). But no test observed a frame on
   either subject, because with `ANTHROPIC_API_KEY` unset
   (`infra/docker/docker-compose.local.yml:340,408`) nothing produces one.
   Subject-level delivery for these two is **verified as reachable, not as
   delivered**.
4. **`GET /v1/system/health` does not exist** (DEV-4).
5. **No 4B TDD was ever written.** `docs/design/phase-4/02-tdd-4b-observability-panels.md`
   is listed as *"not yet written / Planned"* at `00-master-scope.md:520`. Master
   scope §5/§6 and D-8 are therefore the authoritative acceptance source, and
   there is no module-by-module conformance table to check against.
6. **`list_all` and `list_pending_approvals` have no real-Postgres test.** Both
   new endpoints' SQL is covered by fakes plus the live E2E stack only — see §8
   for the enumerated `real_infra` sets, in which neither method appears.
7. **`useLiveProcesses`** (DEV-5).
8. **Phase 4A has no Gate Review and no Project Health record.** Pre-existing,
   outside this milestone, analysed in §13 (G-4). Not repaired here, and — per
   the protocol as read — not a blocker on 4B.

### 4.1 G-8 — every engine worker shared one arq queue and one cron job name

*Added 2026-09-06 (third pass). Items 2 and 3 above are superseded in part: item
2 by §0.1, and item 3's attribution by this section — see the re-verification
note at the end.*

**Symptom.** The Phase 4A golden path (`golden-path.spec.ts:26`) was red in CI
runs #73, #74 and #77 and green in #69–#72, #75 and #76 — three failures in nine
runs, with an identical signature every time:

```
Locator:  getByTestId('transcript-entry').filter({ hasText: 'Hello NOVA, are you there?' })
Expected: 1   Received: 0   Timeout: 30000ms   64 × locator resolved to 0 elements
```

Run #77 failed on `85f7682`, a **documentation-only commit**, where #76 on
`2f0414a` had passed with byte-identical application code. Whatever it was, it
was not a code regression.

**Root cause, from the repository's own CI diagnostics.** The `Trace the reply
through the transport` step queries Postgres directly on failure. Run #77:

```
              subject               | rows | dispatched | undispatched
-------------------------------------+------+------------+--------------
 communication.intent.delivered      |    2 |          0 |            2
 communication.session.created       |    2 |          0 |            2
 communication.session.state_changed |    8 |          0 |            8
 communication.turn.received         |    2 |          0 |            2
```

**Zero of fourteen outbox rows ever reached the Event Bus.** Both turns were
persisted and NOVA's reply was produced and personality-validated
(`conversation_turn` shows `outbound | t`). Nothing was published, so nothing
could arrive over `ws-gateway`, and the transcript was **correctly** empty. The
browser was never the problem. The worker was alive and had run its cron
**exactly once**, at 16:07:20 — seven seconds after startup, before the
conversation existed — then nothing for the remaining 110 seconds. Run #75,
where the golden path passed, shows the same cron firing every 10s and every
row dispatched.

**Mechanism.** All ten engine workers use `RedisSettings.from_dsn(redis_url)`
against one Redis, none set `queue_name` (so all land on arq's global
`arq:queue`), and all ten schedule a coroutine named `arq_run_outbox_dispatch`
on `second={0,10,20,30,40,50}`. Two independent failures follow, and each needs
its own half of the fix:

1. **Enqueue collision.** `arq/cron.py:184` names a cron job
   `'cron:' + coroutine.__qualname__`, and `arq/worker.py:758` builds the job id
   as `f'{name}:{to_unix_ms(next_run)}'`. Ten engines derive one id per tick.
   The duplicate guard is `arq:job:<job_id>` — **not namespaced by queue** — and
   `arq/connections.py:158-160` returns `None` rather than raising, so nine
   enqueues vanished with no log line. **Distinct queues alone would not have
   fixed this**, and the real-Redis test asserts exactly that.
2. **Consume theft.** That one job sits in the shared queue and whichever worker
   polls first claims it, running *its own* coroutine of that name — draining
   its own outbox and no one else's. Where the function is genuinely absent,
   `arq/worker.py:534-535` logs `function ... not found` and calls `job_failed`:
   the job is finished and **never re-enqueued**. Run #75's worker log carries
   that warning verbatim, `communication-engine-worker` discarding
   `cron:arq_run_health_checks`, which belongs to
   `ai-model-orchestration-engine`. Cross-engine job theft, in this
   repository's own CI output. **Distinct names alone would not have fixed
   this** either.

`communication-engine`'s outbox was therefore drained on roughly one tick in
four — an expected interval of ~40s against a 30s assertion. P(missing three
consecutive ticks) = (3/4)³ ≈ 42%; observed 3 red in 9 runs ≈ 33%.

**Why it appeared in Phase 4B, and whose defect it is.** The defect is in
`services/*/workers/__init__.py`, which are **Phase 2/3 artefacts** — it
predates Phase 4 entirely and is not a Phase 4A artefact, so no phase-4a
lineage correction is implied. It was unobservable while the E2E stack ran a
**single** arq worker, which is what it ran through all of Phase 4A. The
`phase-4`→`phase-4b` diff of `pr-checks.yml` adds `planning-engine-worker`,
`reasoning-engine-worker` and `ai-model-orchestration-engine-worker`: 4B took
the stack from one worker to four and turned a latent defect into a
~40%-per-run failure. It is also a **production** defect, not a test artefact —
any deployment running more than one engine worker against one Redis silently
strands outboxes.

**Fix** (`26eb4f4`), in `nova-service-kit` because that package already owns
worker boilerplate (Extraction C) and ADR-034 already forbids it any
engine-specific knowledge:

```
worker_queue_name("memory-engine") -> "arq:queue:memory-engine"
service_cron("memory-engine", fn)  -> name "cron:memory-engine:<fn>"
```

Each engine names itself once in `_SERVICE_NAME` and derives its queue, its
cron identities and its Event Bus binding from that one string. `service_cron`
**refuses** a caller-supplied `name=` rather than forwarding it, because a
hand-written name is exactly how the collision would return. No contract
changed: no subject, payload, REST path, WebSocket frame, table, migration or
schedule. `apps/web-client/src/` is untouched, `PUBLIC_TOPICS` is unchanged,
and the golden path's assertions, timeout, retries, waits and selectors are
exactly as they were — the point was to make the property hold, not to stop
asserting it.

**Re-verification of item 3's attribution.** `phase-4b.md` field 20(b) and item
3 above attribute the unobserved `reasoning.process.*` and `ai_model.model.*`
frames to the absent `ANTHROPIC_API_KEY` alone. Those two engines' outboxes
were drained by the same broken mechanism, so the attribution was checked again
after the fix rather than assumed still correct — see §6.1. It stands: with no
provider configured nothing *produces* an event for either subject, so there is
no outbox row for a worker to strand. The worker collision was a second,
independent reason the same subjects could not have been delivered, and item 3
is left as written with this note beside it.

---

## 5. Technical debt introduced

- **DEV-5**, one line.
- **Two untested repository methods** (limitation 6). The correct fix is one
  `real_infra` test per method in each engine's existing
  `test_repository_real_postgres.py`. Low cost, and the absence is exactly the
  defect class that produced Phase 3E's D-1/D-2 findings.
- Nothing else. The panels add no schema, no migration, no contract, and no new
  event subject.

---

## 6. Verification results

All figures uncached, produced against `0f3412c`.

| Gate | Command | Result |
|---|---|---|
| Lint + types | `pnpm turbo run lint --force` | **30/30 successful, 0 cached** |
| Tests (uncached) | `pnpm turbo run test --force` | **30/30 successful, 0 cached** — 1,813 pytest + 146 vitest |
| Scaffolding tools | `uv run pytest tools/tests -q` | **146 passed** |
| Import boundaries | `uv run lint-imports` | **7 kept, 0 broken** |
| compose | `docker compose -f infra/docker/docker-compose.local.yml config --quiet` | **valid** (exit 0) |
| Codegen drift | generate + `git status --short packages/nova-contracts` | **114 files, zero drift** (empty output) |

**Total: 2,105 passing**, 104 `real_infra` deselected locally (§8).

Coverage against the 85% `fail_under` gate, per affected package:
`api-gateway` **98%** (109 stmts / 2 miss) · `ws-gateway` **98%** (66/1) ·
`planning-engine` **99%** (286/2) · `action-engine` **97%** (255/8).
No affected package is below the gate.

`ruff format` and `prettier` are **not gates** in this repository — neither
appears in `package.json`, `turbo.json`, or any workflow, per protocol §9.2. They
were not run as gates and nothing was reformatted.

### 6.1 Verification of the G-8 fix (2026-09-06, third pass)

Re-run in full after `26eb4f4`. Nothing in the table above regressed.

| Gate | Command | Result |
|---|---|---|
| Lint (uncached) | `pnpm turbo run lint --force` | **30/30 successful, 0 cached** |
| Tests (uncached) | `pnpm turbo run test --force` | **30/30 successful, 0 cached** — **1,992 passing**, 107 deselected |
| TypeScript | `pnpm turbo run typecheck --force` | **5/5 successful, 0 cached** |
| Scaffolding tools | `uv run pytest tools/tests -q` | **179 passed** (was 146; +33 from the new isolation guard) |
| Import boundaries | `uv run lint-imports` | **7 kept, 0 broken** |
| Lockfile | `uv sync --all-packages --frozen` | **clean** — the new `arq` and `nova-testkit` edges are locked |

**Total: 2,171 passing, 0 failing** (1,992 + 179), against 2,127 before this
pass. The delta is exactly **+44**: 11 unit tests for the derivation, 33
repository-level isolation guards. Coverage figures are unchanged — the fix
touches worker wiring, not any `domain/` package.

**Tests added, and what each is for:**

| Where | Count | Property |
|---|---|---|
| `packages/nova-service-kit/tests/test_worker.py` | 11 | The derivation, checked against arq's **real** `CronJob` and real name derivation — including that the schedule is forwarded untouched, that a caller-supplied `name=` is refused, and that plain `cron()` really does collide across two engines |
| `tools/tests/test_worker_queue_isolation.py` | 33 | Every `services/*/workers/__init__.py`, parsed with `ast` (never imported — importing one constructs that engine's `Settings()`): each declares `_SERVICE_NAME`, each sets `queue_name = worker_queue_name(_SERVICE_NAME)`, every cron goes through `service_cron(_SERVICE_NAME, …)`, and no two workers share a service name or a derived cron identity |
| `packages/nova-service-kit/tests/test_worker_real_redis.py` | 3 (`real_infra`) | Real arq workers against a real Redis: a worker leaves another's queued job alone; the un-namespaced `arq:job:` guard swallows a second engine's colliding enqueue **even across distinct queues**; and, as the negative control, the shared default queue really does let one worker claim, fail and discard another's job unrun |

**Negative control on the repository-level guard.** `perception-engine` was
reverted to a bare `cron(...)` with no `queue_name`; both assertions fired,
naming the engine and the mechanism:

```
AssertionError: perception-engine schedules arq_run_outbox_dispatch with `cron(...)`.
A bare `cron(...)` names the job after the coroutine alone … arq silently drops
all but the first enqueue.
2 failed, 31 passed
```

Restored: 33/33.

**Standing CI evidence.** A new `Confirm no engine outbox was left stranded`
step runs `if: always()` — on green runs as well as red. That ordering is the
point: the existing transport trace runs only `on failure()`, so for as long as
a run was green **nothing ever looked at whether the outboxes had drained**,
which is exactly how this defect survived nine runs. The step reports every
engine's outbox (`communication`, `reasoning`, `model_orchestration`,
`planning`) and **asserts** that no `communication.turn.received` row is left
undispatched. Other engines are reported, not asserted: how much any of them
publishes is a fact about what the stack was asked to do on the day, and pinning
that is what made the 4B E2E assertions wrong twice already (§0.1, run #69/#70).

**Re-verification of the `reasoning.process.*` / `ai_model.model.*` attribution**
(§4 item 3, `phase-4b.md` field 20(b)). Because the worker collision stranded
*every* engine's outbox, that attribution was re-checked rather than assumed to
survive the fix — and **it was half wrong.** Run #80 against `51ce2f9`, the
first run with the always-on step:

```
--- communication.outbox_event ---
 communication.intent.delivered      |    1 |          1 |            0
 communication.session.created       |    1 |          1 |            0
 communication.session.state_changed |    4 |          4 |            0
 communication.turn.received         |    1 |          1 |            0
--- reasoning.outbox_event ---
 reasoning.process.failed            |    1 |          1 |            0
--- model_orchestration.outbox_event ---   (0 rows)
--- planning.outbox_event ---              (0 rows)

communication.turn.received: 1 row(s), 0 undispatched
```

| Subject | Original attribution | What the evidence says |
|---|---|---|
| `reasoning.process.*` | "no frame because `ANTHROPIC_API_KEY` is unset" | **Incorrect.** A reasoning process *is* started by the golden path's RPC and *does* fail without a provider — `domain/pipeline.py:606` writes a `reasoning.process.failed` outbox row for exactly that. One row exists and is now **dispatched**. Before the fix it was subject to the same ~1-in-4 drain, which is a far better explanation of "no observed frame" than provider absence |
| `ai_model.model.*` | "no frame because `ANTHROPIC_API_KEY` is unset" | **Stands.** `model_orchestration.outbox_event` is empty — with no provider configured there is no model whose health could change, so no row is created and none could be stranded |

This is why the step reports every engine rather than only the one under
assertion, and why it runs on green. Field 20(b) is corrected accordingly.

---

## 7. Negative controls and flakiness

Protocol §9.2 requires every property-asserting test to be proven to fail when the
property is removed. Three were controlled; all three fired; all three restored
green.

| Property | Injected break | Result |
|---|---|---|
| Every public topic is reachable on the bus | Removed `reasoning.process.*` from `events/subscribed.py` | **FAILED** — `'reasoning.process.completed' is public but not declared in events/subscribed.py`. Restored: 39/39 pass |
| No optimistic removal of an approval | Added an `onMutate` `setQueryData` filter | **FAILED** — *"does not remove a row optimistically when a decision is clicked"*. Restored: green |
| A silent module goes `unknown` | Made `withStaleness` return the entry unchanged | **FAILED** — *"falls back to unknown when a module stops reporting"*, `expected 'healthy' to be 'unknown'`. Restored: green |

**Flakiness:** the two 4B suites (`observability-panels.test.tsx`,
`observability-reducers.test.ts`) run **10×, 10/10 green, 0 failures**.

### 7.1 The E2E flakiness, resolved (2026-09-06, third pass)

The statement above covers the **unit** suites and remains accurate. It said
nothing about the Docker E2E job, which was genuinely unstable — and the
instinct to call that "flakiness" was wrong. It was a real defect in the
transport, diagnosed in §4.1 and fixed in `26eb4f4`.

| Run | Head | Golden path | Cause |
|---|---|---|---|
| #69 | `24a5cdf` | passed | (`observability-panels` failed: a wrong assertion in the new spec — §0.1) |
| #70 | `b22ec83` | passed | (same spec, next loop position) |
| #71–#72 | `0f3412c`, `56f74f4` | **passed** | The outbox tick happened to land on `communication-engine-worker` |
| #73 | `04fed6d` | **failed** | G-8 |
| #74 | `a41b846` | **failed** | G-8 |
| #75 | `55150fe` | passed | (`approval-lifecycle` failed: G-7) |
| #76 | `2f0414a` | **passed** | |
| #77 | `85f7682` | **failed** | G-8 — on a **documentation-only** commit |
| **#78** | `26eb4f4` | **passed** | First run with the fix. Golden-path step 46s, **no retry** |
| **#79** | `e841618` | **passed** | |
| **#80** | `51ce2f9` | **passed** | First run with the always-on outbox assertion. Golden-path test 1 in **15.2s**; 12 passed, 1 skipped, 0 failed; `communication.turn.received: 1 row(s), 0 undispatched` |

Three failures in nine runs before the fix ≈ 33%, against the ~42% the
mechanism predicts. **Three for three green after it**, with the third run
carrying a positive assertion rather than an absence of failure.

**How much three green runs are worth, stated honestly.** At the pre-fix rate a
run passed ~2 times in 3, so three consecutive passes would happen by luck
about 30% of the time. Three runs alone are **not** a demonstration of
stability, and this review does not claim they are. What carries the weight is
the combination: the mechanism is understood and reproduced in a test
(§6.1), the two halves of it are asserted against a real Redis, a repository
guard fails if any worker returns to the shared queue, and — the part that
changes the character of the evidence — **every run from #80 onward positively
asserts that no `communication.turn.received` row was stranded**, rather than
merely failing to fail. Before the fix a green run recorded that the run was
lucky; now a green run records that the outbox drained.

**Neither a re-run nor a manual dispatch was available to this session.** The
GitHub integration in use is refused both (`403 Resource not accessible by
integration` on `POST .../rerun` and on `.../dispatches`), and `pr-checks.yml`
had no `workflow_dispatch` trigger at all. One was added in `e841618` so a
human can click *Run workflow* and extend this series against an unchanged SHA
without pushing a commit to do it — which is what C-7 asks for before the job
is promoted to a required check.

**What this changes about how the job should be read.** Protocol §3.2's GO
condition 7 requires real CI green against the exact head SHA, and §0.3.3
requires evidence rather than assertion. Before the fix, a green E2E run was
not evidence of anything — it recorded that the run was lucky. The workflow's
own comment set the right bar (*"do NOT add it to branch protection until it has
demonstrated stable, non-flaky runs"*), and that bar was not met. The stability
series establishing it is recorded in [`phase-4b.md`](../../project-health/phase-4b.md)
field 15.

**Nothing in the golden path was changed to achieve this.** Its assertions,
timeout, retry count, waits, selectors and ordering are byte-identical to what
they were when it was failing; `apps/web-client/src/` is untouched. The test was
right and the transport was wrong.

---

## 8. Real-infrastructure status

Reported as its own section, per protocol §10.2, and never folded into §6.

1. **Docker locally: NOT available.** `docker info >/dev/null 2>&1 && echo
   available || echo NOT available` → `NOT available`. Testcontainers cannot run
   in this environment.
2. **Deselected `real_infra` tests in the packages 4B changed — enumerated by
   name:**
   - `api-gateway`: **none.** `pytest -m real_infra --collect-only` → *"no tests
     collected (72 deselected)"*.
   - `ws-gateway`: **none.** → *"no tests collected (64 deselected)"*.
   - `planning-engine` (15), all in `tests/integration/test_repository_real_postgres.py`:
     `test_insert_then_find_by_id_round_trips`,
     `test_insert_persists_multiple_nodes_in_order`,
     `test_find_node_locates_the_graph_containing_it`,
     `test_find_node_returns_none_for_an_unknown_id`,
     `test_append_nodes_mutates_in_place_and_recomputes_critical_path`,
     `test_append_nodes_raises_for_an_unknown_task_graph_id`,
     `test_set_approved_at_persists_the_decision`,
     `test_set_approved_at_raises_for_an_unknown_task_graph_id`,
     `test_apply_transitions_mutates_status_and_republishes`,
     `test_apply_transitions_advances_a_completion_and_its_dependent_atomically`,
     `test_apply_transitions_raises_for_an_unknown_task_node_id`,
     `test_apply_transitions_raises_for_an_unknown_task_graph_id`,
     `test_insert_hands_off_admitted_nodes_while_publishing_them_as_ready`,
     `test_outbox_list_dispatch_ready_and_mark_dispatched_round_trip`,
     `test_a_fresh_repository_instance_reads_back_a_graph_written_earlier`.
   - `action-engine` (12), same file name:
     `test_insert_then_find_by_id_round_trips`,
     `test_insert_round_trips_a_rollback_strategy`,
     `test_inserting_a_duplicate_action_id_raises_action_already_exists`,
     `test_update_status_and_record_result_persist`,
     `test_get_result_returns_none_before_any_result_is_recorded`,
     `test_pending_approval_insert_find_and_decide_round_trips`,
     `test_record_execution_history_persists`,
     `test_identity_confidence_policy_round_trips`,
     `test_insert_round_trips_an_empty_depends_on`,
     `test_insert_round_trips_a_single_dependency`,
     `test_insert_round_trips_multiple_dependencies_in_order`,
     `test_a_dependent_action_survives_a_full_write_read_lifecycle`.
3. **Do they cover code 4B changed?** **No — and that is itself the finding.**
   4B added exactly two repository methods, `PostgresPlanningRepository.list_all`
   and `PostgresActionRepository.list_pending_approvals`. **Neither name appears
   in either list above.** The 27 enumerated tests exercise pre-existing methods.
   4B's own new SQL — including the `ORDER BY created_at DESC` clause — has no
   dedicated real-Postgres test in any environment.
4. **Matrix coverage:** `planning-engine` and `action-engine` are both in
   `.github/workflows/real-infra-checks.yml`'s 11-entry matrix. `api-gateway` and
   `ws-gateway` are not, correctly — they have no `real_infra` tests and no
   repository layer.
5. **Has the workflow run against this head?** **Yes.** Real-Infrastructure Checks
   run [34023254679](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/34023254679)
   (#100), **all 11 matrix jobs success**, against `0f3412c`.
6. **What remains unverified:** the two repository methods 4B added are exercised
   only by in-memory fakes and by the live Docker E2E stack, which reads them
   through the browser but asserts only that the panel settled without a
   degradation notice. **No test anywhere asserts their SQL returns the right rows
   in the right order against a real PostgreSQL.** The 11 `nova-testkit` fixture
   tests (Redis/Neo4j/NATS) remain unrun locally and touch no code 4B changed.

---

## 9. Acceptance criteria

Enumerated from all four sources protocol §2.1 requires: master scope §1.1,
master scope §5, `ENGINEERING_ROADMAP.md`'s Phase 4 entry, and this session's
instructions. **4B owns exactly one criterion.**

| # | Criterion (verbatim) | Source | Status | Evidence |
|---|---|---|---|---|
| **AC-3** | "Every Phase 3 sub-phase 3A–3D is exercised end-to-end **from the browser**: a plan is generated and rendered, a reasoning trace is inspected, a capability is installed, and a risky action is blocked pending approval and then approved." | `00-master-scope.md:55`, assigned to 4B at `:157` | **Not met** *(first pass. Superseded by §9.1 and §9.2: the approval clause is now **Deferred by approval (approval cited)**; AC-3 as a whole is still not "met")* | Four sub-clauses, none satisfied — see below |

**Sub-clause accounting:**

| Sub-clause | Status | Why |
|---|---|---|
| "a plan is generated and rendered" | Not met | The Planning panel renders; **no plan was generated**. Generation needs an LLM provider; `ANTHROPIC_API_KEY` is unset in the E2E stack |
| "a reasoning trace is inspected" | Not met | Panel renders; **no trace exists**, same cause |
| "a capability is installed" | Not met | Four built-ins are installed **by `capability-engine`'s own boot bootstrap** (`main.py:191`) and are rendered in the browser — but not installed *from the browser*. **DEV-1**: no install control was built |
| "a risky action is blocked pending approval and then approved" | Not met | Approve/Deny controls exist and the reducer is correct, but **no risky action was created, blocked, or approved end-to-end** |

**0 of 1 acceptance criteria are met. The unmet criterion is AC-3.**

### 9.1 AC-3 re-assessed after the second pass (2026-09-06, head `2f0414a`)

The table above is the first pass's assessment, preserved. After DEV-1 was
built, the sub-clause accounting is:

| Sub-clause | First pass | Now | Why |
|---|---|---|---|
| "a capability is installed" | Not met | **Met** | Installed from the browser, through `api-gateway`, running `capability-engine`'s real 8-stage pipeline. Verified live in CI run #76 |
| "a risky action is blocked pending approval and then approved" | Not met | **Blocked — cannot be verified in this stack** | ADR-032's fail-closed identity gate denies the Action at stage 3; it never reaches the approval loop (§0.2). Requires a user decision (G-7) |
| "a plan is generated and rendered" | Not met | **Cannot be verified in this environment** | Requires an LLM provider; `ANTHROPIC_API_KEY` is unset and Phase 4 does not add one |
| "a reasoning trace is inspected" | Not met | **Cannot be verified in this environment** | Same cause. The panel renders traces and now renders 3A's recursion depth; no trace exists to render |

**1 of AC-3's 4 sub-clauses is met; 1 is blocked by an architectural gate; 2
cannot be verified without a provider. AC-3 as a whole remains Not met**, per
protocol §2.1 — "partially met criteria are not met".

**On the two provider-dependent clauses and the protocol.** §2.4 provides the
status *"Cannot be verified in this environment (reason)"*, so they are
legitimately reportable rather than failures of the implementation — the panels
that would render them are built and unit-tested. But §3.2's GO condition 1
requires every criterion **Met**, "or narrowed/deferred with a cited user
approval", and §2.1 is explicit that "descoping a criterion requires the user's
explicit approval, recorded; it is never the agent's call". **The protocol
therefore permits deferral but not self-granted deferral.** No such approval
exists, so AC-3 stays unmet and the verdict stays NO-GO.

Protocol §2.1: *"Partially met criteria. These are not met."* Two sub-clauses fail
for an environment reason (no provider); two fail because the capability was not
built. The criterion's own wording — "end-to-end **from the browser**" — is
binding and is not softened here.

**AC-1 and AC-2 (Phase 4A) were re-verified as still passing** by the same CI run
and are not reopened: the four golden-path specs, including `/internal`
indistinguishability and the refused direct NATS socket, passed against `0f3412c`.

### 9.2 AC-3 after the approved deferral (2026-09-06, third pass)

The user's explicit approval (§0.3) changes the **consequence** of the approval
sub-clause, not the criterion's own status. Per protocol §2.4 the recordable
status is *"Deferred by approval (approval cited)"*, and per §2.1 a partially
met criterion is still not met — so AC-3 is **not** relabelled as met here.

| # | Criterion | Source | Status | Evidence / approval |
|---|---|---|---|---|
| **AC-3** | "Every Phase 3 sub-phase 3A–3D is exercised end-to-end **from the browser** …" | `00-master-scope.md:55` | **Not met — one sub-clause Deferred by approval (approval cited)** | Sub-clause table below |

| Sub-clause | Status | Evidence / basis |
|---|---|---|
| "a capability is installed" | **Met** | Installed **from the browser**, through `api-gateway`, running `capability-engine`'s real 8-stage pipeline. `capability-lifecycle.spec.ts`, 3 tests green against the live stack (CI #74 onward) |
| "a risky action is blocked pending approval and then approved" | **Deferred by approval (approval cited)** | User approval, 2026-09-06, recorded in §0.3. The Phase 4B **surface** is delivered and rendering; the **end-to-end execution demonstration** is deferred. Blocked by an unbuilt **Phase 3D / ADR-032** configuration mechanism (CF-9), routed forward to Phase 4D's policy surface. **No threshold was invented and the fail-closed default is unchanged** |
| "a plan is generated and rendered" | **Cannot be verified in this environment** (no LLM provider) | The panel renders and is unit-tested; `ANTHROPIC_API_KEY` is unset in the E2E stack (`docker-compose.local.yml:340,408`) and Phase 4 does not add a provider |
| "a reasoning trace is inspected" | **Cannot be verified in this environment** (no LLM provider) | Same cause. The panel renders traces and 3A's recursion depth beside `reasoning_level` |

**1 of AC-3's 4 sub-clauses is met, 1 is deferred by explicit user approval,
and 2 cannot be verified in this environment. AC-3 as a whole is not met**, and
is carried as **deferred by approval** rather than as a silent pass.

**What the approval does and does not do.** §3.2's *"an unmet criterion is a
NO-GO unless the user has explicitly approved deferring it"* is satisfied for
the approval clause, so that clause no longer forces NO-GO. §2.1's *"descoping a
criterion requires the user's explicit approval, recorded; it is never the
agent's call"* is satisfied by recording it here with the approval cited. What
the approval does **not** do is make the criterion met, and nothing in this
document says it does.

---

## 10. Forward and backward contamination

- **Backward:** 4B changed no Phase 4A production file's behaviour. It corrected
  one 4A **test** (the `fnmatch` topic guard, §1.1), which strengthens a 4A
  assertion rather than relaxing it. Phase 4A's golden path is untouched and still
  green.
- **Forward:** no 4C/4D/4E/4F work leaked in. No Agents, Autonomy, Digital Twin, or
  Cognitive State panel exists. `agent-os` remains uncontainerized (Phase 3E's
  ratified deferred obligation, untouched).
- **Owed-but-pushed-forward:** DEV-1/2/3 are work 4B owed and did not do. They are
  **not** silently reassigned to a later milestone — they are reported here as
  unbuilt scope requiring a user decision (§15).

---

## 11. CI and branch evidence

- **Branch** `phase-4b`, head `0f3412c73b6dbd28b48c6f1ff9de14db3c238e53`, working
  tree clean, nothing unpushed at the time of verification.
- **Ancestry:** branched from `phase-4` `481ceac` (the PR #23 merge commit).
  `main` `7e273e6`, `phase-4` `481ceac`, `phase-4a` `fbd75d7` — all untouched.
- **PR #24**, `phase-4b` → `phase-4`, open, **not merged**, opened at the user's
  explicit request so CI could run the Docker-backed verification (protocol §11.1
  satisfied).

| Workflow | Run | Conclusion | Against |
|---|---|---|---|
| PR Checks | [34023254683](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/34023254683) (#71) | **success** (both jobs) | `0f3412c` |
| Build & Scan | [34023254685](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/34023254685) (#71) | **success** | `0f3412c` |
| Real-Infrastructure Checks | [34023254679](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/34023254679) (#100) | **success**, 11/11 | `0f3412c` |

**30 of 30 Check Runs `completed`/`success`.** Verify via the Check Runs API — the
legacy commit-status endpoint returns `total_count: 0` for this repository, as
Phase 3E's record also notes.

**Trivy:** no Dockerfile was touched by 4B. `build-and-scan` ran its full 14-service
matrix green regardless.

**Live-stack evidence** (PR Checks, Playwright job): stack start **success** (86s,
34 compose services); schema migration **success**; engines-not-crash-looping
**success**; both gateways answer **success**; golden path **success — 8 specs, 0
failures**. Both new workers, `reasoning-engine-worker` and
`ai-model-orchestration-engine-worker`, start and tear down cleanly by name.

**Commit-message accuracy** (protocol §11.1): every factual claim in the five
commit messages was re-checked. One is now known **overstated**: `a7cf674`'s body
says the E2E "asserts what a live stack can honestly show — every panel renders,
no panel reports an unreachable engine". Two of its assertions were in fact wrong
and were corrected in `b22ec83` and `0f3412c`, whose own messages record exactly
what was wrong and why. Per protocol principle 0.3.4 the original message is left
as written; this paragraph is the additive correction.

---

## 12. Compatibility with the NOVA Project Bible

**Part 01 §Personality** — *"Transparent … Never fabricate information. Never hide
uncertainty."* This is the requirement the panels are built against, and it is
implemented literally:

- Every panel distinguishes "has no data" from "could not reach its engine"
  (`AsyncPanelBody`'s four states).
- A module that stops reporting goes `unknown`, never keeps its last good status.
- A failed reasoning process reports no confidence rather than `0`.
- The Events panel shows the event's own time *and* arrival time, labelled.
- Confidence is a tier word, never a raw number.

**Faithfulness assessment: high for what was built, incomplete in coverage.** The
engine state each panel exposes is specified in Part 08 (reasoning), Part 09 (task
graphs, critical path), Part 12 (approval gating), Part 15 (installed
capabilities), Part 20 (heartbeat, module status). Part 15's capability *lifecycle*
(install/uninstall) is named in the Bible and in master scope §5 but is
**not surfaced** — DEV-1 is a Bible-coverage gap as well as a scope gap.

---

## 13. Gaps, ambiguities, and decisions requiring the user's approval

| # | Item | Options | Recommendation |
|---|---|---|---|
| **G-1** | **AC-3 is unmet** (§9). Two sub-clauses need an LLM provider the phase does not add; two need UI that was not built | (a) Ratify AC-3 as **deferred to a later milestone**, recording that the panels are the surface and the end-to-end demonstration follows when a provider exists; (b) build DEV-1 and drive an approval end-to-end, leaving only the two provider-dependent sub-clauses; (c) treat 4B as incomplete and extend it | **(b)**, then defer only the provider-dependent half. It closes the two sub-clauses that are genuinely 4B's to close, and leaves a narrow, honest deferral |
| **G-2** | **DEV-1/2/3** — three approved capabilities not built | (a) Build them in 4B; (b) ratify as explicit 4B narrowings and reassign to a named later milestone | **(a) for DEV-1** (it is also half of AC-3), **(b) for DEV-2 and DEV-3**, which are presentation refinements with no acceptance criterion depending on them |
| **G-3** | **`GET /v1/system/health` does not exist**; doc 11 §2 names it, master scope §5 lists it as a 4B backend addition | (a) Ratify the push-fed Health panel as the permanent design and correct doc 11 §2; (b) give `nova-core` a public surface and build it | **(a).** `nova-core` publishing its own heartbeat is already the architecture; a REST aggregate would duplicate it |
| **G-4** | **Phase 4A has no Gate Review and no Project Health record** | (a) Leave the gap recorded and repair it when `phase-4` closes; (b) write both retroactively now | **(a).** See §13.1 — the protocol as read does not require it before 4B |
| **G-5** | **SLOC not measured** — neither `cloc` nor `scc` is installed | (a) Install one and re-measure; (b) record "Not measured" | **(b) for this pass, (a) before `phase-4` merges to `main`.** The open Option A/B methodology decision in `project-health-master.md` §2 also remains open |
| **G-7** | **The approval loop is unreachable in the 4B stack.** ADR-032's gate requires identity confidence 1.0 with no policy row, and no perception activity scores the user, so every Critical-risk Action is denied at stage 3 (§0.2). AC-3's approval clause cannot be demonstrated end-to-end without changing this | (a) Seed an `IdentityConfidencePolicy` for the instance's primary user in the E2E stack, with a per-risk threshold the operator chooses; (b) give the E2E a real identity signal via `perception-engine`; (c) defer the clause to a milestone that has one | **(a), with the threshold chosen deliberately and documented** — it is the mechanism ADR-032 already defines for exactly this, and it configures the gate rather than removing it. It was **not** done here because choosing a confidence threshold for a security control is the user's decision, not the agent's |
| **G-6** | Master scope prose says *"Phase 4 builds eight"* panels while its own §6 table lists **eleven** Phase-4 rows (conversation, six 4B, agents, autonomy, digital-twin, cognitive-state) | Correct the prose, or the table | Pre-existing, not caused by 4B. Recorded; an additive note has been added. Needs the user's call on which number is right |

### 13.1 Does the protocol require repairing the Phase 4A gap before 4B can receive GO?

**No.** Determined by direct inspection, not assumption:

- **Protocol §3.2 GO condition 9** requires *"Gate Review, Project Health record,
  roadmap entry, and README status all exist and are current"* — for the phase
  being gated. It is not a statement about sibling milestones.
- **`project-health/README.md`** establishes that *"a phase is not fully closed
  until both its Gate Review and its Project Health record exist."* That makes
  **Phase 4A not closed**. It does not make Phase 4B blocked.
- **Protocol §0.2**'s bar — *"A Sub-Phase may not be declared complete while any
  ledger row from any of its Slices is unsettled"* — is about a Sub-Phase's own
  Slices. Phase 4A is a sibling milestone of 4B, not a Slice of it.
- **Protocol §3.2 GO condition 10 / §12** would be triggered if any document
  claimed Phase 4A was complete, closed, or GO while no such record existed. A
  repository-wide sweep found **zero** such claims:
  `grep -rniE 'phase 4[ab][^|]{0,60}(complete|closed|merged|go\b|gate review)' docs/ README.md` →
  **0 hits.** There is therefore no contradiction to resolve.

Phase 4A is consequently left **entirely untouched** — no production code, no
history, no retroactive Gate Review — and the gap is recorded here (G-4) and in
[`phase-4b.md`](../../project-health/phase-4b.md) field 21 so `phase-4`'s eventual
closure inherits it rather than rediscovering it.

### 13.2 Update — 2026-09-06, third pass: G-7 decided, G-8 opened and closed

**G-7 — decided by the user.** The user chose neither of the two options the
table above offered for making the clause demonstrable, and chose the third:
**defer the clause**. Recorded in full in §0.3, with the status §2.4 provides
and the ownership distinction stated explicitly — original ownership **Phase 3D
/ ADR-032**, discovering phase **4B**, future routing **Phase 4D's policy
surface**, and **not** a Phase 4D dependency. The approval is explicit that no
identity-confidence threshold is to be invented, no zero-confidence policy
seeded, `perception-engine` not added merely to force the clause green, and the
fail-closed behaviour left unchanged. None of those was done.

The recommendation this table made — *"(a), with the threshold chosen
deliberately and documented"* — was **not** followed, and that is the correct
outcome: the recommendation named the mechanism ADR-032 intends, but that
mechanism does not exist to be used, and choosing its first value is a security
decision. The missing mechanism is tracked as **CF-9** in master scope §4.

**G-8 — opened and closed in this pass.**

| # | Item | Disposition |
|---|---|---|
| **G-8** | **Every engine worker shared one arq queue and one cron job name**, so `communication-engine`'s outbox was dispatched on ~1 tick in 4 and the 4A golden path failed ~40% of runs. A pre-existing Phase 2/3 defect, unobservable until 4B's E2E stack went from one arq worker to four. Also a production defect: any deployment with more than one engine worker on one Redis silently strands outboxes | **Closed by `26eb4f4`.** Per-service queue and cron identity derived in `nova-service-kit` (§4.1), guarded by 33 repository-level tests and 3 real-Redis tests (§6.1). No user decision was required — no contract, threshold or security control is involved, and there was no design ambiguity to resolve once the cause was known |

G-8 needed no entry in the table above because it did not exist when that table
was written: it was found by taking the E2E instability seriously as a possible
defect rather than accepting it as flakiness.

---

## 14. Documentation updated by this review

| Document | Change |
|---|---|
| This Gate Review | Created |
| [`docs/project-health/phase-4b.md`](../../project-health/phase-4b.md) | Created — 23-field record |
| [`docs/project-health/project-health-master.md`](../../project-health/project-health-master.md) | §1 row added; §3 index entries added for `phase-3e.md` (missing) and `phase-4b.md`; a stray blank line that had split §1 into two tables removed |
| [`docs/roadmap/ENGINEERING_ROADMAP.md`](../ENGINEERING_ROADMAP.md) | Additive status block on the Phase 4 entry: the 4A–4F restructure, 4A merged, 4B verified-but-NO-GO, and which document is authoritative for the criteria |
| [`docs/architecture/11-api-architecture.md`](../../architecture/11-api-architecture.md) | §2 catalogue: `GET /v1/plans` and `GET /v1/action/approvals` added; `GET /v1/system/health` annotated as not implemented |
| [`services/api-gateway/README.md`](../../../services/api-gateway/README.md) | Scaffold TODOs replaced with the real responsibility and the five forwarded prefixes |
| [`services/ws-gateway/README.md`](../../../services/ws-gateway/README.md) | Scaffold TODOs replaced with the real responsibility and the 17 public topics |
| [`services/planning-engine/README.md`](../../../services/planning-engine/README.md) | "Owned APIs" listed only `/internal/*`; the public `/v1/plans` surface added |
| [`services/action-engine/README.md`](../../../services/action-engine/README.md) | `GET /v1/action/approvals` added |
| [`docs/design/phase-4/00-master-scope.md`](../../design/phase-4/00-master-scope.md) | Additive 4B status note: what was built, DEV-1/2/3, the `system/health` decision, and the eight-vs-eleven count (G-6) |

> **Correction, 2026-09-06 (same day).** The row above for the four READMEs
> originally also recorded removing a `GET /internal/metrics` claim from each,
> asserting the route did not exist. **That was wrong.** All four services do
> expose it — `main.py` mounts `prometheus_asgi_app()` at `/internal/metrics`
> as a sub-application, which is why it is absent from `api/health.py` where
> the check had looked. The four READMEs have been corrected back, and the
> claim that it was a "scaffold artifact" is withdrawn. Recorded here rather
> than silently reverted, per principle 0.3.4.

**Inspected and found already accurate** — evidence the sweep was not selective:
`docs/architecture/09-event-bus-architecture.md` §6 (names `ws-gateway` as the sole
bridge; enumerates no subject list, so nothing went stale) ·
`docs/architecture/10-inter-engine-communication.md` (4B added no subject or RPC) ·
`docs/architecture/adr/` (no ADR falsified; 4B added none) ·
`docs/architecture/07-database-architecture.md` (no table, no migration) ·
`docs/architecture/17-cicd-pipeline.md` (no gate changed) ·
`docs/architecture/16-testing-strategy.md` (no tier, marker, or coverage rule
changed) · `docs/bible/part-01`, `08`, `09`, `12`, `15`, `20` (checked for
compatibility, not edited — §12) · top-level `README.md` (its Status section
describes `main`, where Phase 4 is not yet merged; correctly silent on Phase 4 —
see [`phase-4b.md`](../../project-health/phase-4b.md) field 17).

### 14.1 SAD 15 §9.1 — ten-item build-time deliverable checklist

4B introduced **no new subsystem** — no engine, package, or `agent-os` component.
It extended four existing services and one existing app. The checklist is therefore
assessed against the extended surface rather than a new one.

| # | Item | Status |
|---|---|---|
| 1 | Architecture documentation | **Present** — doc 11 §2 updated; both gateway READMEs written |
| 2 | Sequence diagrams | **Absent.** No new diagram for the panel read/realtime paths |
| 3 | Component diagrams | **Absent** |
| 4 | API documentation | **Present** — doc 11 §2 + engine READMEs |
| 5 | Unit tests | **Present** — 30 new frontend tests; 146 tools; gateway/engine suites green |
| 6 | Integration tests | **Present** — `test_plans_api.py`, `test_approvals_api.py`, plus the Docker E2E |
| 7 | Performance benchmarks | **Absent.** No benchmark for panel load or socket throughput |
| 8 | Failure scenarios | **Present** — `AsyncPanelBody`'s degradation path, asserted in the E2E; health staleness; `/internal` and NATS boundary specs |
| 9 | Logging strategy | **N/A** — no new backend service; the two endpoints inherit their engines' existing logging |
| 10 | Observability metrics | **N/A** — same reason; no new metric introduced |

**Three items absent (2, 3, 7).** Recorded, not waived; they are inputs to the §15
decision.

---

## 15. Gate verdict

### **NO-GO**

Under protocol §3.2, which is explicit: *"An unmet acceptance criterion is a NO-GO
unless the user has explicitly approved deferring it,"* and *"CONDITIONAL-GO is not
a way to pass a phase with an unmet acceptance criterion."*

> **Verdict re-confirmed 2026-09-06 after the second pass (head `2f0414a`).**
> **B-2 is discharged** — DEV-1, DEV-2 and DEV-3 are built and verified live
> (§0.1). **B-1 stands**, narrowed: AC-3 is now 1 of 4 sub-clauses met, 1
> blocked by ADR-032's gate (G-7), 2 unverifiable without a provider. CI is
> **green, 30/30 Check Runs** against `2f0414a` — PR Checks #76, Build & Scan
> #76, Real-Infrastructure Checks #105, all `success`. The verdict is NO-GO on
> the acceptance criterion alone; every engineering gate passes.

**What is blocking:**

| # | Blocker | What would clear it |
|---|---|---|
| **B-1** | **AC-3 unmet** (§9) — 0 of 1 acceptance criteria met | Either the user's explicit approval to defer AC-3 (recorded, with the milestone that inherits it), or the work in G-1(b) |
| **B-2** | **DEV-1/2/3 are undisclosed narrowings** of master scope §5 (§2.1) — protocol principle 0.3.6 forbids narrowing scope unilaterally | Either building them, or the user's explicit ratification of each as a disclosed 4B narrowing |

**What is *not* blocking**, stated so it is not mistaken for a blocker:

- Every engineering gate is green (§6, §7, §11). 30/30 Check Runs, real Docker E2E.
- Real-infrastructure ran and passed in CI against this exact SHA (§8).
- The Phase 4A documentation gap (§13.1) — analysed against the protocol and found
  not to be a precondition for 4B.
- The unobserved `reasoning.process.*` / `ai_model.model.*` frames (§4 item 3) —
  a disclosed limitation, and no acceptance criterion turns on delivery of those
  two subjects specifically.
- SLOC not measured (G-5) — a disclosure, and both SLOC milestones are addressed
  in §16.

### If the user approves the deferral

If the user explicitly approves deferring AC-3 and ratifies DEV-1/2/3 as disclosed
4B narrowings, **both blockers convert to disclosed narrowings and this verdict
becomes CONDITIONAL-GO**, with these conditions:

- **C-1** AC-3 is reassigned, by name, to the milestone that will demonstrate it.
  Discharged when that milestone's Gate Review records it met.
- **C-2** DEV-1 (capability install/uninstall), DEV-2 (event filtering), DEV-3
  (recursion depth) each get an owning milestone. Discharged the same way.
- **C-3** A `real_infra` test for `list_all` and `list_pending_approvals`
  (§8 item 6). Discharged by a green `real-infra-checks` run covering them.
- **C-4** SLOC measured with `cloc` or `scc` before `phase-4` merges to `main`
  (G-5).
- **C-5** SAD 15 §9.1 items 2, 3, 7 (§14.1) supplied or explicitly waived.
- **C-6** Phase 4A's Gate Review and Project Health record written before
  `phase-4` closes (G-4).

That decision is the user's and is not taken here.

### 15.1 Verdict after the approved deferral — 2026-09-06, third pass

**The decision the section above described has been taken.** The user
explicitly approved deferring AC-3's approval-execution clause (§0.3), and
DEV-1/2/3 were built rather than ratified as narrowings (§0.1), so **B-2 was
discharged by the work and B-1 is discharged by the approval**.

### **CONDITIONAL-GO**

Under protocol §3.2: an unmet criterion is a NO-GO *"unless the user has
explicitly approved deferring it"*. That approval now exists and is cited. The
conditions below are the ones §15 drafted, updated for what has since been
built or decided; each names what discharges it.

| # | Condition | Owner | Discharged when |
|---|---|---|---|
| **C-1** | **AC-3's approval-execution clause** is reassigned by name to the milestone that will demonstrate it, together with the **Phase 3D / ADR-032** configuration mechanism it depends on (CF-9). Routed to **Phase 4D** | Phase 4D | 4D's Gate Review records a Critical-risk action blocked pending approval and approved from the browser, against a policy whose threshold the user set |
| **C-2** | The two provider-dependent AC-3 sub-clauses ("a plan is generated and rendered", "a reasoning trace is inspected") are demonstrated once a provider exists | The milestone that configures a provider | That milestone's Gate Review records both, from the browser |
| **C-3** | A `real_infra` test for `list_all` and `list_pending_approvals` (§8 item 6) | Phase 4C or the next milestone touching either | A green `real-infra-checks` run covering them |
| **C-4** | SLOC measured with `cloc` or `scc` before `phase-4` merges to `main` (G-5) | `phase-4` closure | A measured figure in `project-health-master.md` |
| **C-5** | SAD 15 §9.1 items 2, 3, 7 (§14.1) supplied or explicitly waived | `phase-4` closure | Supplied, or waived with the waiver recorded |
| **C-6** | Phase 4A's Gate Review and Project Health record written before `phase-4` closes (G-4) | `phase-4` closure | Both exist |
| **C-7** | The E2E job is promoted to a required check **only** once it has demonstrated stable runs (the workflow's own bar). Branch protection is **not** changed here | `phase-4` closure | The stability series in [`phase-4b.md`](../../project-health/phase-4b.md) field 15 is judged sufficient by the user |

**DEV-1/2/3 need no condition** — they are built and verified live (§0.1), which
is why they appear here as discharged rather than as reassigned narrowings.
**DEV-4** and **DEV-5** remain disclosed and open (§2.1), unchanged by this pass.

**What CONDITIONAL-GO does not claim.** AC-3 is **not** met, and §9.2 says so.
Protocol §2.1's *"partially met criteria are not met"* is not softened here; the
approval changes the criterion's consequence for the gate, not its status. A
reader who wants the one-line summary should read: *0 of 1 acceptance criteria
met outright; AC-3 deferred by explicit user approval of 2026-09-06, with 1 of
its 4 sub-clauses met, 1 deferred by that approval, and 2 unverifiable without a
provider.*

**What changed the verdict, and what did not.** The verdict moved because of the
user's approval and because DEV-1/2/3 were built — not because of the G-8 fix.
G-8 was a Phase 4A regression surfaced by 4B's stack, and closing it removed an
obstacle to *trusting* the evidence, not an obstacle to the criterion.

---

## 16. Project Metrics

Per SAD 15 §10 and `METRICS_TEMPLATE.md`.

**Production SLOC: Not measured.** Neither tool is installed in this environment:

```
$ command -v cloc || echo "cloc NOT installed"     → cloc NOT installed
$ command -v scc  || echo "scc NOT installed"      → scc  NOT installed
```

Per `project-health/README.md`, a value that cannot be measured reads **"Not
measured"** and is never estimated, inferred, or backfilled. No substitute line
count is offered here, because a hand-rolled count would not be comparable to
either historical series.

**SLOC milestone status:**

- **~30,000 reminder** — already crossed at Phase 3E (31,319, `cloc` v1.98,
  comparable scope) and already discharged by the
  [Project Health Review 2026-08-29](project-health-review-2026-08-29.md)
  (verdict HEALTHY). Not re-triggered by 4B.
- **~50,000 gate** — **not crossed.** Stated as a bound rather than a
  measurement: the last measured figure is 31,319 in the comparable scope, and
  4B's *entire* diff against `phase-4` is +2,619 lines across all file types —
  tests, TypeScript, YAML and Markdown included, none of which count as Production
  SLOC. Even attributing every added line to production code leaves the figure
  below 34,000, far short of 50,000. **This is a bound derived from the diff, not
  a measurement**, and it is not entered into the series.

**Implementation statistics:** 43 files changed, +2,619 / −71. 5 commits.
**Architecture metrics:** 16 `services/`, 4 `agent-os/`, 5 `agents/`, 9
`packages/`, 24 ADRs, 7 import-linter contracts (0 broken), 115 generated
TypeScript files, 34 compose services, 30 CI Check Runs.
**Quality metrics:** 2,105 tests passing, 0 failing; coverage 97–99% on the four
affected packages against an 85% gate; 3/3 negative controls fired; 10/10 flake
runs clean.

---

## 17. Definition of Done — all ten items

Per [`definition-of-done.md`](../../project-health/definition-of-done.md), checked
item by item.

| # | Item | Status |
|---|---|---|
| 1 | Gate Review | **Done** — this document |
| 2 | Project Health record + master row | **Done** — [`phase-4b.md`](../../project-health/phase-4b.md), master §1 row and §3 index |
| 3 | TDD / design currency | **Partial** — no 4B TDD exists (§4 item 5); master scope carries an additive 4B status note |
| 4 | Roadmap status | **Done** — additive Phase 4 status block |
| 5 | README / project status | **Done** — four subsystem READMEs; top-level README correctly unchanged (it describes `main`, where Phase 4 is not merged) |
| 6 | Additive corrections | **Done** — every historical edit is an additive dated note; nothing rewritten |
| 7 | Tests and verification evidence | **Done** — §6, §7, real counts and percentages |
| 8 | CI / Trivy / real-infra | **Done** — §8, §11; Trivy N/A (no Dockerfile touched) |
| 9 | Final acceptance-criteria status | **Done** — §9, and the gap is flagged, not glossed |
| 10 | Final merge-readiness review | **Done, and it does not pass** — head SHA, CI, clean tree and diff scope all confirmed; the gate verdict is NO-GO on B-1/B-2 |

---

## Sign-off

- [x] All items in the phase's design-doc review checklist are either satisfied or
      explicitly noted as changed, with reasoning above — **with three
      exceptions, DEV-1/2/3, reported as unbuilt scope rather than as changes.**
- [ ] The phase's Definition of Done ([SAD 15 §4](../../architecture/15-development-workflow.md#4-definition-of-done-per-pr))
      was met for every PR. **Item 1 ("touches exactly one engine's `src/`") is not
      met**: PR #24 spans both gateways, two engines, `apps/web-client` and
      `packages/nova-ui`. It is a milestone PR, and no change-scope linter enforces
      item 1 in CI. Items 2–5 are met; item 3 is N/A (no contract changed); item 4
      is satisfied — both new endpoints are purely additive and no existing route
      changed.
- [x] The per-subsystem deliverable checklist ([SAD 15 §9](../../architecture/15-development-workflow.md#9-per-subsystem-deliverable-checklist))
      was assessed for every subsystem this phase touched — §14.1, **three items
      absent (sequence diagrams, component diagrams, performance benchmarks).**

**Completing this Gate Review is not authorization to begin Phase 4C, and not
authorization to merge PR #24.**
