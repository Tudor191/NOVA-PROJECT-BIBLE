# Phase 4C.2 — Agents Surface — Gate Review

**Unit:** Phase 4C milestone **4C.2** (six implementation slices + this closure pass)
**Branch:** `phase-4c.2`
**Final HEAD at review:** `a405bca6e1efb48a110cca1de988050e00acf16c`
**Baseline:** `origin/phase-4` = `3433fbea25b19217542cd20155b866ca46589f01`
**Date:** 2026-09-10
**Protocol:** [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md), read from `origin/main` at the start of every slice in this milestone and again for this pass (1131 lines, unchanged throughout).

---

## 0. Read this section first

**Verdict: CONDITIONAL-GO.** Three conditions, none of which is an unmet
acceptance criterion caused by 4C.2. They are listed in §15 with an owner and
a discharge event each.

Two things a reader should not misread:

1. **AC-4 is still NOT MET, and 4C.2 does not claim otherwise.** Two of its
   three clauses were Deferred by explicit user approval on 2026-09-07, for a
   reason traced through code rather than asserted (master scope §1.1). 4C.2
   makes those clauses *demonstrable the moment a model provider exists*. It
   does not make them met, and nothing in this document should be quoted as
   saying it does.
2. **"Zero agent instances" is the correct, healthy output of this system
   today.** It is not a defect, not an empty panel, and not something a future
   slice should "fix" with seed data. §9 explains why, and the panel itself
   says so on screen.

---

## 1. What was implemented

Six slices, each separately reviewed, verified and committed. All six are
ordinary non-merge commits; the branch is linear and 6 ahead / 0 behind
`origin/phase-4`.

| Slice | Commit | Scope | Diffstat |
|---|---|---|---|
| **4C.2a** | `8ed743651630a15b3a01f42e34781060fbf4fc0e` | Registry `agent_os.registry.list_packages` RPC (internal) | 21 files, +1,161 / −11 |
| **4C.2b** | `c1dbd443b61d8ab279447238f3d7f231bf63edf6` | `agent_os.agent_activity` table + transactional repository surface | 8 files, +1,857 / −18 |
| **4C.2c** | `92ba4d796c1cf8d71ed3e9ae2c4563818a011d2d` | Kernel read-only `/v1/agents`, fronted by `api-gateway` | 16 files, +1,261 / −3 |
| **4C.2d** | `e0489b96040b47fdc9c72e35a1c7410ac8191749` | Activity writes wired into the real Kernel lifecycle | 4 files, +1,440 / −13 |
| **4C.2e** | `e97602c5b94e9141bcd232421f3e2e2a75edfe67` | `agent_os.task.completed` opened to the browser | 6 files, +252 / −4 |
| **4C.2f** | `a405bca6e1efb48a110cca1de988050e00acf16c` | Agents entity, panel, `/agents` route, realtime reconciliation | 9 files, +1,191 / −25 |

**Total against `origin/phase-4`:** 56 files changed, +7,136 / −48.

**4C.2g (this pass)** adds documentation, verification and this Gate Review.
It introduces **no product functionality** — §14 lists every file it touches
and why.

### 1.1 The one thing worth understanding about this milestone

The six slices are not arbitrary decomposition. Each one was blocked by the
previous, and the ordering was chosen so that **no slice could fake the one
before it**:

`list_packages` gives the Kernel something true to report → the activity table
gives it somewhere to record → the REST surface exposes both → the lifecycle
wiring makes the table non-empty when work actually happens → the realtime
topic tells the browser when it changed → the panel renders it.

Reversing any pair would have required a placeholder. None was written.

---

## 2. Why each architectural decision was made

| Decision | Choice | Why |
|---|---|---|
| **D-1** (Registry degradation) | `GET /v1/agents` answers **503**, never `200` with `packages: []` | `200 []` means a healthy Registry holding nothing. Collapsing the two would report "no agents are installed" when the truth is "the Registry is down" — the exact inversion `api-gateway`'s own envelope module already forbids. |
| **D-2** | No `installed_at` on `AgentPackageSnapshot` | Nothing renders it; an external read-only surface carries the minimum. |
| **D-3** | Transactional coupling where an activity accompanies a state change | Two commits can disagree. A crash between them leaves a running instance with no record of starting, or a `"completed"` instance whose history stops at dispatch. |
| **D-4** | Kernel gains a minimal read-only `/v1` surface | The panel needs point-in-time queries an event stream cannot answer: a client joining mid-stream sees no history. Explicit Phase 4 amendment to a ratified Phase 3E narrowing (master scope §9), not a correction of it. |
| **D-4, third route** | `GET /v1/agents/{id}` added and ratified | It is the existence check `/activity` needs so an unknown instance answers 404 rather than an empty page. Flagged before implementation, ratified on review (master scope §9.1). |
| **B2** (4C.2d) | `interrupted` reuses the published event's correlation id | The id already exists and is already on the bus, so the row and the event are joinable. `NULL` when no event is published — never a second id minted to avoid a null. |
| **C** (4C.2d) | All four peer-review verdicts recorded | `not_required` and `timed_out` mean "nobody reviewed this" while the task still finalises `"success"`. Suppressing them would make that absence invisible. |
| **4C.2e** | `agent_os.task.*` on the bus, **not** `agent_os.*` | `fnmatchcase` lets `*` span dots, so `agent_os.*` would subscribe the gateway process to every Registry and Supervisor RPC subject. |
| **4C.2f** | Realtime **refetches**, does not patch | The payload carries `outcome`; the cache holds `status`. The mapping is the Kernel's own `_handle_outcome` policy, and copying it into the browser would let it drift. |

---

## 3. Tradeoffs considered

- **Refetch vs. targeted cache patch (4C.2f).** A patch is cheaper and is what
  every other topic in `reconcile.ts` does. Rejected here because the payload
  is insufficient — no `health_status`, no activity row, and an `outcome`
  vocabulary that is not the `status` vocabulary. The event names *which*
  instance changed; the server says *what* it changed to.
- **One `agent_os.*` subscription vs. the narrow `agent_os.task.*`.** The wide
  form is one line shorter and would have matched every future
  `agent_os.task.x` automatically. Rejected: it also matches every RPC subject.
- **Deriving `status` from `outcome` in the browser.** Rejected as duplicating
  backend domain logic.
- **A supervisor id.** Rejected: Phase 3E has no supervisor identity
  mechanism, so any id would have been invented. The response instead carries
  `membership_is_derived: true` and the panel renders that disclosure.

---

## 4. Known limitations

1. **`agent_instance` is empty without a model provider**, so `instances`,
   `activity` and the peer-review path have no production data to render. This
   is the AC-4 deferral, traced in master scope §1.1, and is a provider gap
   rather than a 4C.2 gap.
2. **`supervisor_id` is always `null`.** The column exists (TDD 3E §4); no code
   path writes it. Surfaced honestly rather than hidden.
3. **A Registry outage blanks the whole `/v1/agents` response**, instances
   included, because the Kernel assembles one response and `api-gateway`
   forwards one upstream per prefix. Correct per D-1, but worth stating: a
   degraded Registry currently costs the operator the instance list too.
4. **`GET /v1/agents/{id}` has no UI caller.** The panel renders instance rows
   from the overview's `instances[]`, which returns the identical projection.
   The hook exists and is exported; it is what a deep-link route would use. No
   redundant request was manufactured to make the endpoint look used.

---

## 5. Technical debt introduced

**None deliberately.** The two items closest to debt are recorded elsewhere as
deferred findings rather than debt: the pinned over-broad `communication.*` /
`personality.*` bus patterns (pre-existing, §13.1) and the hand-maintained
codegen `MODELS` list (pre-existing, §13.3).

---

## 6. Verification results

All gates run in this pass against `a405bca` plus this pass's documentation.

| Gate | Command | Result |
|---|---|---|
| Lint + types | `pnpm turbo run lint` | **30/30 successful** |
| Typecheck | `pnpm turbo run typecheck` | **5/5 successful** |
| Tests, **uncached** | `pnpm turbo run test --force` | **30/30 successful, `Cached: 0`** |
| Aggregate | — | **2,242 passing** via turbo + **218** `tools/tests` = **2,460**; 322 deselected (`real_infra` and other markers) |
| Import boundaries | `uv run lint-imports` | **7 kept, 0 broken** |
| Scaffolding tools | `uv run pytest tools/tests -q` | **218 passed** |
| compose | `docker compose … config --quiet` | **valid** |
| Codegen drift | regenerate + `git status` | **116 files, zero drift** |

**Per-package, the four packages 4C.2 touched:**

| Package | Tests | Domain coverage (gate: 85%) |
|---|---|---|
| `agent-os/kernel` | 190 passed, 48 deselected | **99%** |
| `agent-os/registry` | 68 passed, 18 deselected | **99%** |
| `services/api-gateway` | 88 passed | n/a (no `--cov` target) |
| `services/ws-gateway` | 103 passed | n/a (no `--cov` target) |
| `apps/web-client` | 173 passed | n/a (vitest) |

**Codegen:** no regeneration was required by any slice after 4C.2a. The
`/v1/agents` response models are FastAPI types internal to the Kernel, not
`nova_contracts` bus types; `AgentOsTaskCompletedPayload` was already generated
and exported.

---

## 7. Negative controls and flakiness

Per protocol §9.2, every property-asserting test in this milestone was proven
to fail when the property was removed. **20 negative controls across the six
slices, all fired**, each with the tree restored and re-verified afterwards.

| Slice | Controls | Representative |
|---|---|---|
| 4C.2a | 2 | Registry listing order broken; RPC subject added to `PUBLIC_TOPICS` |
| 4C.2b | 4 | Cursor ordering flipped; correlation dropped in the mapper |
| 4C.2c | 4 | Registry failure swallowed into `[]`; mutation route added; invalid cursor swallowed; `agent-os/registry` fronted |
| 4C.2d | 5 | `dispatched` split into its own transaction; `restart_planned` written unconditionally; B2 correlation reuse broken; `peer_review` suppressed for `not_required`; activity failure swallowed |
| 4C.2e | 4 | Bus pattern widened to `agent_os.*`; unpublished sibling topic added; approved topic silently dropped; browser authorization made prefix-based |
| 4C.2f | 5 | D-1 branch disabled; placeholder agent fabricated; cache patched from payload; `exact: true` dropped; nav entry removed |

**One control did not fire on the first attempt, and that is recorded rather
than smoothed over.** In 4C.2f, disabling the D-1 branch left the test passing:
it matched on body text that the *generic* degradation notice also renders,
because the gateway's own error message contains the same words. The assertion
was strengthened to target the notice **title**, which is the element that
actually distinguishes the two paths, and the control then failed correctly.
The weakness was in the test, not the implementation.

**Flakiness (protocol §9.2, ≥10×):**

| Suite | Runs | Result |
|---|---|---|
| Kernel activity wiring | 10× | 35/35 every run |
| Kernel lifecycle (scheduler, reconciliation, restart, parallel dispatch) | 10× | 31/31 every run |
| Kernel agents API | 10× | 30/30 every run |
| api-gateway | 10× | 88/88 every run |
| ws-gateway | 10× | 103/103 every run |
| web-client focused (agents, routing, reconcile, security) | 10× | 73/73 every run |
| web-client full | 5× | 173/173 every run |

Zero variance in every series.

---

## 8. Real-infrastructure status

**Docker is unavailable in this environment. No real-infrastructure result is
claimed, and none was simulated.**

```
$ docker info   → Docker daemon UNREACHABLE
                  ("Error while fetching server API version", FileNotFoundError on the socket)
```

`docker compose config --quiet` **does** pass and is reported as a local
result, because it is the Compose CLI parsing a file and needs no daemon.

**Deselected `real_infra` tests, enumerated by package:**

| Package | `real_infra` tests | Covers 4C.2 code? | In the CI matrix? |
|---|---|---|---|
| `agent-os/kernel` | **48** (of 238) | Yes — 4C.2b's activity persistence and transaction rollback; 4C.2c's `list_instances`; 4C.2d's lifecycle-through-real-Postgres suite | **Yes** (`real-infra-checks.yml:80-81`) |
| `agent-os/registry` | **18** (of 86) | Yes — 4C.2a's `list_all` ordering | **Yes** |
| `services/ws-gateway` | 0 (103 deselected by marker filter) | n/a — no `real_infra` tests exist | Correctly absent |
| `services/api-gateway` | 0 | n/a | Correctly absent |

The CI job runs `pytest -m real_infra` from each matrix package directory, so
it selects by marker and picks up every test the slices added without a matrix
edit. **This is the basis of condition C-1 in §15** — the suites are written
and unverified here, not assumed passing.

---

## 9. Acceptance criteria

Verified by **source inspection plus tests**, not by test names.

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Registry `list_packages` RPC exists and is internal | **Met** | `registry/events/list_packages_handler.py`; subject absent from `PUBLIC_TOPICS` and matched by no subscribable pattern (§10) |
| 2 | Activity persistence, append-only | **Met** | `alembic/versions/0002_agent_activity.py`; `KernelRepository` exposes `insert`/`append_activity`/`list_activity` and **no** `update_activity` or `delete_activity` |
| 3 | All six lifecycle activity kinds produced | **Met** | Enum at `domain/activity.py:79-84`; five write sites — `scheduler.py:282,430,459,560`, `reconciliation.py:88` — covering all six kinds |
| 4 | Transaction semantics | **Met** | `dispatched`/`completed`/`failed` ride `insert`/`update_status` (`scheduler.py:426,453`); `interrupted` rides `update_status` (`reconciliation.py:83`); `restart_planned`/`peer_review` are standalone appends (`scheduler.py:279,557`) because no state transition occurs there |
| 5 | `correlation_id` propagated, never fabricated | **Met** | Scheduler carries the inbound id; reconciliation reuses the published event's id and stores `NULL` when no event is published |
| 6 | Peer-review semantics, all four verdicts | **Met** | `scheduler.py:279-292`, recorded inside the branch that ran the round |
| 7 | Kernel API — three read-only routes | **Met** | `api/agents.py:155,214,228` — all three are `@router.get`; no non-GET route exists |
| 8 | `api-gateway` forwarding | **Met** | `routing.py:137-140`, one prefix → `agent-os-kernel`, forwarded 1:1 |
| 9 | Public realtime topic | **Met** | `PUBLIC_TOPICS` contains exactly one `agent_os.` entry: `agent_os.task.completed` |
| 10 | Browser security boundary | **Met** | §10 — full sweep |
| 11 | Agents frontend entity | **Met** | `entities/agents.ts`, strict schemas mirroring the Kernel's response models |
| 12 | Agents panel | **Met** | `panels/agents/AgentsPanel.tsx`; 19 component tests |
| 13 | Routing and navigation | **Met** | `/shell/agents` in `router.routesById`; nav and route sets asserted equal (`routing.test.ts`) |
| 14 | Cursor pagination, no offset | **Met** | `useInfiniteQuery` + `getNextPageParam` on the server's `next_cursor`; no `offset` string anywhere in the agents surface |
| 15 | Provider-free healthy empty behaviour | **Met** | Panel renders `instances-empty` with the reason; a negative control proves a fabricated instance fails the suite |
| 16 | Registry degraded behaviour | **Met** | 503 → named Registry notice; `200 []` → "reachable, holds nothing"; asserted on the notice title |
| 17 | No fake runtime agents | **Met** | Negative control fired |
| 18 | No provider / Ollama / model execution | **Met** | Zero matches across the 4C.2 diff |
| 19 | No direct browser-to-NATS path | **Met** | §10 |
| 20 | No `/internal/*` exposure | **Met** | `RouteTable` rejects non-`/v1/` prefixes at construction; `apiUrl` refuses them client-side |
| 21 | No mutation endpoints | **Met** | Only `@router.get` on the Kernel; no `useMutation`, no mutating method in the entity |
| 22 | No polling | **Met** | No `refetchInterval` / `setInterval` in the agents surface |
| 23 | No optimistic state mutation | **Met** | Realtime invalidates only; a test asserts no agent cache entry is *written* from the payload |
| **AC-4** | *"`agent-os` runs as containers under `docker compose up`, and the Agents panel renders live agent instances, supervisor structure, and at least one real peer-review round."* | **NOT MET — two clauses Deferred by approval (2026-09-07)** | Clause 1 discharged by 4C.1. Clauses 2 and 3 need an `agent_instance` row, created only by Kernel dispatch, reached only from an LLM-backed decomposition with no deterministic fallback (master scope §1.1) |

**23 of 23 milestone criteria are met.** The unmet criterion is the
phase-level **AC-4**, whose second and third clauses remain Deferred by
explicit user approval. 4C.2 built every provider-free part of them and
weakened nothing.

---

## 10. Security sweep

Run against the live allow-lists by importing them, not by reading source.

**`PUBLIC_TOPICS` — 18 exact strings, zero wildcards, one `agent_os.` entry:**
`agent_os.task.completed`.

**`SUBSCRIBABLE_SUBJECTS` — 11 patterns.** `agent_os.task.*` is present;
`agent_os.*`, `>` and `*` are not.

**Authorization mechanism:** `partition_topics` is `topic in PUBLIC_TOPICS`
against a `frozenset` — exact membership, never a prefix, never a pattern.

| Probe | Browser | Bus pattern |
|---|---|---|
| `agent_os.task.completed` | **ALLOW** | `agent_os.task.*` |
| `agent_os.registry.list_packages.request` / `.reply` | reject | — |
| `agent_os.registry.find_healthy_package.request` / `.reply` | reject | — |
| `agent_os.supervisor.restart_plan.request` / `.reply` | reject | — |
| `agent_os.supervisor.peer_review.request` / `.reply` | reject | — |
| `agent_os.health.snapshot` | reject | — |
| `agent_os.instance.inbox`, `agent_os.internal.rpc` | reject | — |
| `agent.started`, `agent.instance.running`, `agent.lifecycle.started` | reject | — |
| `agent_os.*`, `agent.*`, `agent_os.task.*`, `>`, `*` | reject | — |
| `agent_os.task.completedX`, `…completed.extra`, `agent_os.task.started` | **reject** | `agent_os.task.*` |

The last row is the layered defence working as designed: those subjects match
the *bus* pattern but are refused to a browser, because exact membership — not
the pattern — governs what a client may name.

**Repository-wide check across all 30 declared RPC subjects:** zero leaked
into `PUBLIC_TOPICS`.

**Browser source:** no NATS client, no `nats://`, no `:4222`, no
`agent-os-kernel` host, no `/internal/` path. `apiUrl` refuses any path outside
`/v1/`; every agents request goes through `gatewayFetch`, and every `/v1/`
literal in the entity starts with `/v1/agents`.

**No wildcard authorization and no approximate matching were introduced.**

---

## 11. CI and branch evidence

| Item | Value |
|---|---|
| Branch | `phase-4c.2` |
| Head SHA at review | `a405bca6e1efb48a110cca1de988050e00acf16c` |
| Ahead / behind `origin/phase-4` | **6 / 0** |
| Merge commits | **0** |
| Working tree at the six commits | clean |
| PR | **None.** No PR has been opened for `phase-4c.2` — the standing instruction across all six slices was "no PR yet" |
| Protected refs | `origin/main` `7e273e6`, `origin/phase-4` `3433fbe`, `origin/phase-4c` `e4900eb` — all unchanged throughout |
| History rewrites | none — every commit verified unamended, original trees and parents intact, each push a fast-forward |

**Real GitHub Actions CI has not run against `a405bca`.** No PR exists, so no
workflow has been triggered for this branch head. Every result in §6 and §7 is
a **local** result and is labelled as such. This is **condition C-2** in §15.

---

## 12. Compatibility with the NOVA Project Bible

- **Part 4 (multi-agent).** The panel renders the observed deployment
  topology — Kernel → one Engineering Supervisor → instances — and marks
  supervisor membership as derived rather than presenting a construction as a
  recorded relationship.
- **Part 6 / doc 04 §4 ("never generate fake animations").** No status dot in
  the Agents panel passes `animate`; health is a standing reading, not an
  arrival.
- **Part 8 (confidence) and Part 19 (explainability).** `correlation_id` is a
  first-class column and reaches the client on both transports, so
  reasoning → plan → instance → activity stays traversable.
- **Part 4 ("departments never communicate directly with the user").**
  Preserved: the browser reaches one REST gateway and one realtime bridge, and
  no engine or `agent-os` component is addressable from it.

---

## 13. Gaps, ambiguities, and deferred findings

### 13.1 Over-broad `communication.*` / `personality.*` bus patterns — CARRIED FORWARD, unchanged

`ws-gateway`'s 4A-era `communication.*` and `personality.*` subscription
patterns match **six internal RPC request subjects**. Discovered 2026-09-08
during 4C.2a; **still present, still exactly six, unchanged by 4C.2**.

- **Not a client-visible exposure.** `PUBLIC_TOPICS` names none of them, and
  4C.2e added a per-subject test asserting each is rejected from browser
  subscription.
- **The exposure is that the gateway *process* may receive internal RPC
  traffic**, which is wider than doc 09 §6's "already-finalized events plus
  read-only telemetry".
- **Deliberately not fixed here.** Narrowing them is a `ws-gateway` behaviour
  change needing its own verification of which finalized subjects the 4A/4B
  panels actually consume — out of scope for a documentation slice, and not an
  acceptance-criterion blocker. Pinned in `test_protocol.py` with a staleness
  test so the list may shrink and can never grow.

### 13.2 A prior correction note contained a false claim — corrected additively

`docs/design/phase-3/03-gateway-web-prerequisite.md`'s 2026-08-29 correction
asserts that *"the `agent.*`/`agent_os.*` **events** this panel needs do exist
and are published."* **That was wrong when written.**
`agent.<instance_id>.<state>` has no payload in `nova-contracts` and appears in
no `PUBLISHABLE_SUBJECTS`; the same Phase 3E Gate Review that added the note
recorded its absence as DEV-2. Corrected additively in this pass — the original
sentence is preserved and superseded, per protocol §0.3.4.

### 13.3 Carried forward unchanged from earlier slices

| Finding | Origin | Status |
|---|---|---|
| Codegen `MODELS` list is hand-maintained in two places | 4C.2a | Reported, not fixed |
| Prometheus scrapes only `nova-core` | 4C.1 | Reported, not fixed |
| `supervisor_id` is dead schema | 4C.2c | Surfaced as `null`, not fixed |
| CF-8's six Phase 3E narrowings | Phase 3E | Unchanged; 4C built against observed behaviour |
| CF-9 (ADR-032 identity-confidence policy has no creation path) | 4B | Unchanged, routed to 4D |

### 13.4 Nothing requires a user decision before this milestone can be called done

No architectural ambiguity was left unresolved. The two that arose during the
milestone — the third route, and the scope conflict in 4C.2d — were both
escalated before implementation and explicitly ratified.

---

## 14. Documentation updated by this review

| Document | Change | Why |
|---|---|---|
| `design/phase-4/00-master-scope.md` | §6 panel table `agents/` row rewritten; correction note added; **new §9.2** recording the surface as built | The row named `agent.*`/`agent_os.*`; neither shipped |
| `design/phase-4/01-tdd-4a-gateways-and-web-client.md` | §3.2 topic row → `agent_os.task.*`; correction note; §3.3 two-allow-list explanation | Same stale prediction |
| `architecture/09-event-bus-architecture.md` | `agent.<agent_id>.*` subject line replaced; additive correction note | The canonical subject list named a family that was never built |
| `architecture/11-api-architecture.md` | Additive note giving the `/v1/agents` surface's read-only, 503, 404, empty-page and cursor semantics | §2 listed the routes without their semantics |
| `architecture/12-agent-architecture.md` | **New §15.1** — activity lifecycle, transaction coupling, correlation semantics, peer-review verdicts, and what actually feeds the panel | §13 describes the panel as fed by `agent_os.health.snapshot`, which does not exist |
| `architecture/07-database-architecture.md` | `agent_activity` table added; stale "not yet implemented" preamble corrected | Protocol §14 trigger: a new table |
| `design/phase-3/08-tdd-3e-agent-os.md` | Additive note at §4 recording D-4's amendment of the health-only narrowing | The health-only text would otherwise read as current |
| `design/phase-3/03-gateway-web-prerequisite.md` | Second additive correction (§13.2) | A prior correction contained a false claim |
| **This document** | New | The milestone's Gate Review |

**Documents inspected and found accurate — no change needed:**
`architecture/04-frontend-architecture.md` (its `agents/` panel entry, the
no-polling rule and the no-optimistic-mutation rule all describe what 4C.2f
built); `architecture/10-inter-engine-communication.md` (row 15 already names
`agent_os.task.completed` correctly); `architecture/20-engine-responsibility-boundaries.md`
(state ownership unchanged — the Kernel owns instances and activity, Registry
owns packages).

**Historical records deliberately left as written**, per protocol §0.3.4 and
the explicit instruction for this slice: the Phase 3E Gate Review, the Phase 4B
Gate Review, `project-health/phase-3e.md`, the 2026-08-29 Project Health
Review, and the Phase 3 research documents. Each accurately records what was
true when written.

---

## 15. Gate verdict

### **CONDITIONAL-GO**

Substantively complete. Every milestone acceptance criterion is met, every
gate is green, no undisclosed deviation exists, and no document contradicts the
repository state. Three conditions remain, each with an owner and a discharge
event:

| # | Condition | Owner | Discharged by |
|---|---|---|---|
| **C-1** | **66 `real_infra` tests unverified** (48 kernel, 18 registry). Docker is unavailable locally; they are written and in the CI matrix, but have not executed | Phase 4C closure | A `real-infra-checks` run against this head |
| **C-2** | **No GitHub Actions CI has run against `a405bca`** — no PR exists, so no workflow triggered. All §6/§7 evidence is local | Phase 4C closure | Opening the Phase 4C PR and recording `pr-checks` + `build-and-scan` conclusions against the exact SHA |
| **C-3** | **AC-4 remains NOT MET**, two clauses Deferred by approval | Phase 4D or a provider slice | A model provider existing, at which point both clauses become demonstrable without further Agents work |

**Why not GO:** protocol §3.2 requires real CI green against the exact head SHA
(item 7) and real-infrastructure verification either passed or disclosed as a
named scoped gap (item 8). C-1 and C-2 are precisely the disclosed gaps that
make this CONDITIONAL rather than clean.

**Why not NO-GO:** no acceptance criterion is unmet without approval, no gate
is red, no scope was silently narrowed, no undisclosed deviation exists, and no
open item requires a user decision.

**CONDITIONAL-GO is not being used to pass an unmet criterion.** AC-4's
deferral is a prior explicit user approval (2026-09-07), cited, not granted
here.

---

## 16. Project Metrics

Per SAD 15 §10 and `METRICS_TEMPLATE.md`.

**Production SLOC — measured, `cloc` v2.06** (same tool *and* version the Phase
4B closure pass used, so the series continues comparably):

| Scope | Now | Phase 4B | Δ | Files |
|---|---|---|---|---|
| Comparable (`services/*/src packages/*/src services/*/alembic/versions`) | **32,948** | 32,923 | **+25** | 551 |
| Phase 3E full scope (+ `agent-os/*`, `agents/*`) | **36,573** | 36,050 | **+523** | 623 |
| Full, incl. web client (+ `apps/*/src`) | **39,258** | 38,369 | **+889** | 662 |

The comparable scope barely moves because 4C.2's production code lands almost
entirely in `agent-os/` and `apps/`, which that scope excludes — the +25 is
`api-gateway`'s routing entry and config field.

**SLOC milestone status:**

- **~30,000 reminder** — crossed at Phase 3E, discharged by the Project Health
  Review 2026-08-29 (HEALTHY). Not re-triggered; SAD 15 §10's reminder fires on
  crossing, not on remaining above.
- **~50,000 gate** — **NOT crossed.** Highest figure on any scope is **39,258**,
  leaving ~10,742 of headroom. Feature development does not pause.

> **A measurement error caught during this pass, recorded because the number
> would have entered a permanent record.** A first, hand-rolled line count
> returned **49,112** and appeared to put the project within 900 lines of the
> 50k gate. It was wrong: a `grep`-based filter cannot strip multi-line Python
> docstrings, which this codebase uses heavily. `cloc` — the established tool —
> gives 39,258 on the same scope. The false figure is recorded here rather than
> discarded, because "we nearly paused feature development on a bad line count"
> is worth one paragraph.

**Implementation statistics:** 56 files changed, +7,136 / −48 across six
commits, plus this pass's documentation.
**Architecture metrics:** 16 `services/`, 4 `agent-os/`, 5 `agents/`, 9
`packages/`, **24 ADRs**, **7 import-linter contracts (0 broken)**, **117
generated TypeScript files**, **37 compose services**.
**Quality metrics:** **2,460 tests passing, 0 failing** (2,242 turbo + 218
`tools/tests`); 322 deselected; coverage **99%** on both affected Python
packages against an 85% gate; **20/20 negative controls fired**; **65 flakiness
runs clean** across seven series.

---

## 17. Definition of Done — the ten items

| # | Item | Status |
|---|---|---|
| 1 | Architecture documentation | **Yes** — §14 |
| 2 | Sequence diagrams | **N/A** — no new cross-engine sequence; 4C.2 reuses doc 10 row 15's existing flow |
| 3 | Component diagrams | **N/A** — no new component; `agent-os/kernel` gained a surface, not an identity |
| 4 | API documentation | **Yes** — doc 11 §2, with full semantics |
| 5 | Unit tests | **Yes** — every slice |
| 6 | Integration tests | **Yes** — kernel API, gateway forwarding, panel components |
| 7 | Performance benchmarks | **N/A** — no performance-sensitive path added; pagination is bounded and keyset |
| 8 | Failure scenarios | **Yes** — 503, 404, 400, upstream failure, activity-write rollback, all tested |
| 9 | Logging strategy | **Yes** — `list_agents` logs the Registry failure before answering 503; `_plan_restart_or_decline` logs its degradation |
| 10 | Observability metrics | **Deferred** — no new metric was added. `agent_activity` is queryable but not exported to Prometheus, which still scrapes only `nova-core` (§13.3) |

---

## Sign-off

**Verdict: CONDITIONAL-GO**, conditions C-1 … C-3 above.

Completing this milestone is **not** authorization to begin the next. 4C.3 —
or whatever follows — is a separate decision, and it is the user's.

**Prepared:** 2026-09-10, against `phase-4c.2` head
`a405bca6e1efb48a110cca1de988050e00acf16c`.
**Every figure in this document was produced by a command run in this session.**
Nothing is carried over from a previous report without re-verification, and
nothing that could not be verified is stated as verified.

---

## 18. Closure addendum — 2026-09-11

**Additive. Sections 0–17 and the Sign-off above are unchanged and are left as
written against head `a405bca`** (protocol §0.3.4, §3.3). Where a figure below
differs from one above, the one above was correct for its own head and remains
the historical record; this section supplies the current value and says why it
moved.

### 18.1 Current state

| Item | Value |
|---|---|
| **Head** | `1182816ffea6702a686ec3e5057fc8b5d8e2f9cf` |
| **PR** | **#26**, `phase-4c.2` → `phase-4`, **open, not merged**, `mergeable_state: clean` |
| **Base** | `phase-4` = `3433fbea25b19217542cd20155b866ca46589f01` — unchanged |
| **CI** | **34 of 34 check runs green** against exactly `1182816` |
| **Topology** | 10 ahead / 0 behind, **0 merge commits**, linear, working tree clean |
| **Protected refs** | `origin/main` `7e273e6`, `origin/phase-4` `3433fbe`, `origin/phase-4c` `e4900eb` — still byte-identical to §11 |

Four commits landed after `a405bca`. Exactly **one production source file**
changed across all four — `repository/postgres_kernel_repository.py`:

| Commit | What it did |
|---|---|
| `69a9461` | 4C.2g documentation + this Gate Review (no product functionality) |
| `4eafa80` | **Fixed the transaction-ordering defect** below, and added two kernel regression tests |
| `388c271` | **Fixed the Phase 3E E2E database-isolation defect** below (test infrastructure only) |
| `1182816` | Refreshed the `js-yaml` resolution in `pnpm-lock.yaml` (no manifest change) |

Production SLOC moved by **+1 line** on every measured scope — the flush fix.
The **~50,000 gate remains uncrossed**; §16's conclusion is unaffected.

### 18.2 C-1 — **DISCHARGED**, and not cleanly

`real-infra-checks` ran against `1182816`: **all 12 matrix jobs success.**

```
real-infra (kernel, agent-os/kernel)   50 passed, 190 deselected, 9 warnings in 21.57s
real-infra (registry, agent-os/registry)  success
```

The kernel's 50 ran **in a single pytest process**, which is the only
configuration able to prove the absence of cross-test contamination. The Phase
3E real-PostgreSQL acceptance E2E passed at position 8 of 50.

**Current `real_infra` count: 50 kernel + 18 registry = 68.** §8's and §15's
**48 kernel (66 total) was correct at `a405bca` and stays as written** — the
count rose because `4eafa80` added two regression tests for the defect below.

**C-1 did not discharge on the first attempt. The first run with a real
database exposed two defects, which is precisely why the condition existed.**

**Defect A — transaction ordering (production).** `AgentActivityORM` declares a
real foreign key to `agent_instance.id` but no ORM `relationship()`, so
SQLAlchemy's unit of work had no dependency edge between the two mappers and
fell back to sorting them by mapper name — emitting the **child INSERT first**.
Every `insert(instance, activity=…)` therefore raised
`ForeignKeyViolationError` against a real database. Compounded by a blanket
`except IntegrityError` wrapped around `commit()`, which reported that
foreign-key failure as `AgentInstanceAlreadyExistsError` — the inverse of the
truth, and what hid the cause. **Fixed in `4eafa80`** by flushing the instance
inside the still-open transaction before the activity is added, and narrowing
the translation to that flush. **Decision D-3 is preserved exactly**: one
`async with` block, one `commit()`, one logical operation; a failure on the
activity write still rolls the flushed instance back with it.

**Defect B — Phase 3E E2E database isolation (test infrastructure).** The
Phase 3E real-Postgres E2E is the only test in the repository that commits
permanently: it must let `create_*_app`'s own lifespan build the real
repository from `<ENGINE>_POSTGRES_DSN`, which is the production wiring it
exists to prove, so it cannot use `nova-testkit`'s rollback-isolated
`postgres_session_factory`. Its three committed `agent_os.agent_instance` rows
were visible to `test_repository_real_postgres.py`'s four `list_instances`
tests, which read deliberately unfiltered global state (decision D-4). Latent
since 4C.2c (`92ba4d7`), masked by Defect A, and exposed the moment A was
fixed. **Fixed in `388c271`** by giving the E2E its own database inside the
same session-scoped container. **`list_instances()` production behaviour is
unchanged**, and no assertion was weakened to accommodate the fix.

### 18.3 Correction to §9, acceptance item 4

§9 records **"Transaction semantics — Met"**, evidenced by source inspection
and fake-repository tests. **That claim was locally evidenced only, and was not
true against a real database at `a405bca`**: Defect A meant every coupled
insert raised. The evidence available at the time — inspection plus a
fake repository — cannot exercise a foreign key, which is the whole reason
condition C-1 existed.

**The claim is now genuinely proven** at `1182816`, against real PostgreSQL, by
`test_insert_commits_the_instance_and_its_activity_together`,
`test_the_instance_and_its_activity_are_one_transaction` and
`test_an_unrelated_integrity_error_is_not_reported_as_a_duplicate_instance`.
The §9 row is left as written per the additive-correction rule and is
superseded by this paragraph.

### 18.4 C-2 — **DISCHARGED**

**34 of 34 check runs `success` against exactly `1182816`:**

| Group | Result |
|---|---|
| `checks` (pr-checks) | success |
| `build-and-scan` — 19 images, incl. Trivy `CRITICAL,HIGH`, `exit-code: 1` | 19/19 success |
| `real-infra` — 12 packages | 12/12 success |
| `Playwright golden path (staged, non-blocking)` | success |
| `dependency-audit` | success |

§11's *"No PR has been opened"* and *"Real GitHub Actions CI has not run against
`a405bca`"* were both true when written; PR #26 now exists and CI has run.
`dependency-audit` was outside C-2's wording and was red on an independent,
pre-existing `js-yaml` advisory (GHSA-2883-xcg3-v3hh) unrelated to 4C.2; it is
green at `1182816`, fixed by a lockfile-only resolution refresh within the
existing semver ranges — no manifest, dependency or version change.

### 18.5 C-3 — **remains OPEN, unchanged**

**AC-4 is still NOT MET.** Its second and third clauses — *"renders live agent
instances"* and *"at least one real peer-review round"* — remain **Deferred by
explicit user approval, 2026-09-07**, traced through code in master scope §1.1.
Nothing in this addendum implements them, and nothing in 4C.2 weakened them.
The discharge event is unchanged: a milestone that configures a model provider.
**C-3 is not altered by this pass.**

### 18.6 New condition C-4 — documentation reconciliation

Identified by this pass. The roadmap's `4C` row read **"Not started"**, which
the repository contradicts. Corrected in the same pass as this addendum; see
the reconciliation table below.

### 18.7 Condition status after this addendum

| # | Condition | Status |
|---|---|---|
| **C-1** | Real-infrastructure suites unverified | **DISCHARGED** — 68/68 green against `1182816`, two defects found and fixed |
| **C-2** | No GitHub Actions CI against the head | **DISCHARGED** — 34/34 green against `1182816` |
| **C-3** | AC-4 NOT MET, two clauses Deferred by approval | **OPEN** — unchanged; a provider milestone |
| **C-4** | Documentation reconciliation | **This pass** — roadmap row corrected; ledger below opened |

### 18.8 Deferred-obligations ledger (protocol §0.2)

These are **documentation and closure obligations, not 4C.2 implementation
gaps**. Nothing below is a missing feature, a missing test, or an unmet
milestone criterion, and none is created or modified by this pass.

| Obligation | Current state | Owner / closure point |
|---|---|---|
| `docs/project-health/phase-4c.md` | **Does not exist.** Protocol §0.1 makes category 4 deferrable for a Slice; `project-health/README.md` requires it before the **phase** is closed | **Phase 4C closure** |
| `docs/project-health/project-health-master.md` | No `Phase 4C` row in the summary table; §2 needs no methodology entry (tool and scope unchanged — `cloc` v2.06) | **Phase 4C closure** |
| `README.md` `## Status` | Makes **zero** Phase 4 claims, so it contradicts nothing today; it will need a Phase 4 status line at phase closure | **Phase 4 closure** |

**A process note, recorded rather than smoothed over.** This document, as
originally written, contained no explicit §0.2 deferred-obligations ledger —
§13.3 lists carried-forward *findings*, which is a different thing. That is why
the three rows above were not visible as owed until the final review. The
ledger exists from here.

### 18.9 Verdict after this addendum

### **CONDITIONAL-GO — unchanged**

C-1 and C-2 are discharged. **C-3 remains open**, by a prior explicit user
approval that this document cites rather than grants, and **the verdict is not
raised to GO.**

Protocol §3.2's GO items 1–8 and 11 now hold, including item 7 (real CI green
against the exact head SHA) and item 8 (real-infrastructure verification
**passed**, rather than merely disclosed). The verdict stays CONDITIONAL for
two reasons, both stated plainly:

1. **C-3 is still open.** This project's recorded convention is that GO
   requires every condition closed — Phase 3E reached GO only once all six of
   its conditions were closed, and Phase 4B stayed CONDITIONAL-GO with all
   eleven §3.2 items holding because four conditions remained open.
2. **§3.2 item 9 is not yet fully satisfied**: the Phase 4C Project Health
   record does not exist. It is deferrable for a Slice and is now in the
   ledger, but it is not done.

**CONDITIONAL-GO is still not being used to pass an unmet criterion.** AC-4's
deferral is the 2026-09-07 user approval, cited here, not granted here.

**Completing this milestone remains no authorization to begin the next.**

**Prepared:** 2026-09-11, against `phase-4c.2` head
`1182816ffea6702a686ec3e5057fc8b5d8e2f9cf`, PR #26 open and unmerged. Every
figure in this addendum was produced by a command run or a CI result read in
this session.
