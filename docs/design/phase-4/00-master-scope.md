# Phase 4 — Master Scope Document

**Status: design preparation. No production code is authorized by this
document.** This is the top-level scope reference for the Phase 4 TDD
package. It defines the boundary between Phase 3 (closed, promoted to
`main`) and Phase 4, records the eight architectural decisions taken on
2026-09-01, and establishes the Phase 4 branch and PR workflow.

Phase 4 begins from `main` at
`7e273e62e942ecd5528ca807e65933d6bb675669` — the merge commit that
promoted the completed Phase 3 into `main`, verified green by 27 of 27
GitHub Actions Check Runs.

---

## 0. What changed relative to the roadmap's Phase 4 entry

[`ENGINEERING_ROADMAP.md`](../../roadmap/ENGINEERING_ROADMAP.md) §"Phase 4 —
Perception, Autonomy & Digital Twin" defines Phase 4's deliverables and an
implementation order beginning with `nova-companion` (Rust, per-platform OS
sensors). **This document reorders that sequence and does not change its
contents.** Every deliverable the roadmap names remains in Phase 4. One
deliverable the roadmap *assumes* — a working `apps/web-client` — is
promoted from an implicit precondition to Phase 4's first milestone,
because it does not exist.

The justification is in the roadmap's own text. Phase 4's acceptance
criterion 4 reads: *"Revoking a sensor's OS permission immediately stops
that perception stream, visibly, in the (still-minimal) UI."* Autonomy
Level 1 is defined as *"Suggestive"*. Both are untestable without a user
interface. The roadmap lists `apps/web-client`: Autonomy + Digital Twin
panels as a Phase 4 deliverable — **panels added to a shell that has never
been built.** See §2.

---

## 1. Phase 4 goal

**NOVA becomes observable and operable by a human for the first time, and
then gains disciplined initiative — in that order.**

Phase 3 moved NOVA from "answers questions" to "does work." Everything it
built is real, tested, and CI-verified, and **none of it is visible.**
Phase 4's first job is to close that gap using the architecture the project
has already specified, not a new one. Its second job is the roadmap's
stated Phase 4 content: extended perception, disciplined autonomy, the full
Digital Twin, and NOVA's own internal attention.

### 1.1 Acceptance criteria

| # | Criterion | Milestone |
|---|---|---|
| **AC-1** | A user opens the web client, authenticates via the Phase-4-scoped session mechanism (§7), and holds a live text conversation rendered through the Conversation panel. This is [`3-P`](../phase-3/03-gateway-web-prerequisite.md) §11 criterion 1, unmet since Phase 2D. | 4A |
| **AC-2** | `ws-gateway` is provably the only path a browser-originated connection can use to observe bus activity — no direct NATS exposure, verified by test, not by inspection. | 4A |
| **AC-3** | Every Phase 3 sub-phase 3A–3D is exercised end-to-end **from the browser**: a plan is generated and rendered, a reasoning trace is inspected, a capability is installed, and a risky action is blocked pending approval and then approved. | 4B |
| **AC-4** | `agent-os` runs as containers under `docker compose up`, and the Agents panel renders live agent instances, supervisor structure, and at least one real peer-review round. **Two of its three clauses are Deferred by approval — see below.** | 4C |
| **AC-5** | An autonomous suggestion at Autonomy Level 1 is **proposed, not executed**, is visible in the Autonomy panel, and executing it requires explicit user approval. | 4D |
| **AC-6** | The Digital Twin's project model correctly reconstructs "what was I doing on Project X" after a simulated multi-week gap, and the reconstruction is visible in the Digital Twin panel. | 4E |
| **AC-7** | *(**Revised 2026-09-15**, ratified — see the note below.)* A known project becoming active on the user's machine is detected by a `nova-companion` sensor, without user action, and is reflected in the World Model **within five seconds**; and revoking that sensor's OS-level permission stops the perception stream, visibly, in the Digital Twin / Cognitive State panel. | 4F |
| **AC-8** | The same action category that is blocked at Level 1 auto-executes at Level 2 for a low-risk case, purely by policy — no code path differs. | 4F |

> **AC-7 revised 2026-09-15 (ratified).** ***The original text, preserved per
> protocol §0.3.4:*** *"Opening a known project in the IDE is detected and
> reflected in the World Model **within one second** with no user action, and
> revoking a sensor's OS permission immediately and visibly stops that perception
> stream in the UI."*
>
> **Why.** The Phase 4F design pass found the one-second budget unreachable
> without changing the transactional outbox architecture. Every
> `perception-engine` publisher returns an `OutboxEvent`, and dispatch runs on a
> **fixed 10-second cron**, so worst-case perception-to-bus latency is ~10 s
> before `world-model-engine` receives anything. The three ways to close that gap
> — shortening the global cron, a direct-publish bypass, or push-triggered
> dispatch — were each evaluated and **declined**: push-triggered dispatch would
> require `SELECT … FOR UPDATE SKIP LOCKED` in **13** engines' dispatch queries
> (no row locking exists anywhere in the repository today) to avoid duplicate
> publication, which is a repository-wide concurrency change disproportionate to
> one criterion. **Decision D-4F-1: the outbox architecture is unchanged and the
> budget moves to five seconds.**
>
> **Two further changes.** *"in the IDE"* became *"becoming active on the user's
> machine"* so the criterion is **modality-neutral**: the CI acceptance path uses
> a genuine **filesystem** sensor, because the runner has no desktop session, no
> `DISPLAY` and no IDE, and fabricating a window-focus reading is forbidden
> (decision D-4F-8). **IDE/window-focus sensing is explicitly outside the Phase 4F
> CI acceptance path.** And *"the UI"* became a named panel, so the clause is
> testable.
>
> **What did not change.** The criterion still requires a real sensor, a real OS
> permission revocation, no user action, real World Model reflection, and
> measured elapsed time.
>
> **The five seconds are honest** *(second ratification, 2026-09-15)*. The E2E
> **may not** align its measurement window to the 10-second outbox dispatcher
> cron, **may not** use a bounded retry or any scheduling technique that avoids
> worst-case dispatch latency, and **may not** fabricate a timestamp, clock,
> sleep, injected Event Bus message, mocked transport or sensor event. Elapsed
> time is measured from the real filesystem event to the observable World Model
> result across the **unchanged** outbox and dispatcher. **If the real latency
> exceeds five seconds the test must fail and expose the figure**, and that is
> reported as a **blocking Gate Review finding** rather than resolved by
> weakening the criterion again. See
> [`06-tdd-4f-companion-and-cognitive-state.md`](06-tdd-4f-companion-and-cognitive-state.md)
> §4.1 and §19.

**AC-1 through AC-4 do not depend on any new engine.** They depend only on
surfacing what Phase 3 already built.

> **AC-4 — two clauses Deferred by approval, 2026-09-07.** Recorded per
> protocol §2.4 (*"Deferred by approval (approval cited)"*), with the user's
> approval of the Phase 4C design decisions as the citation.
>
> **The deferred clauses:** *"renders live agent instances"* and *"at least
> one real peer-review round"*. The remaining clause — *"`agent-os` runs as
> containers under `docker compose up`"* — is 4C.1's and is not deferred.
>
> **Why, traced through code rather than inferred.** Both deferred clauses
> need an `agent_instance` row to exist, and there is exactly one code path
> that creates one: `agent-os/kernel`'s `domain/scheduler.py::_spawn_tracked`,
> reached only from `planning.task_graph.created`, published only by
> `planning-engine`, written only at `events/handlers.py:107` — whose sole
> input is `domain/decomposition.py::decompose()`, which calls
> `ai_model.generate.request` and has **no deterministic fallback** (a model
> timeout, a `finish_reason == "error"`, or a missing `propose_task_graph`
> tool call each raise `DecompositionError`). There is no `POST /v1/plans`, no
> seed, and no other writer. **With no LLM provider configured, `agent_instance`
> is permanently empty**, so no dispatch and no peer-review round can occur.
>
> Everything downstream of the task graph is provider-free and already real:
> `coding-agent`'s handler is scripted with no LLM call, declares
> `peer_reviewer_category: architect`, and `architect-agent` reviews without a
> model. Only the *trigger* is provider-dependent.
>
> **This is the same dependency as condition C-2** from the
> [Phase 4B Gate Review](../../roadmap/architecture-reviews/phase-4b-observability-panels-gate-review.md)
> §9.3, which deferred two AC-3 sub-clauses for it. Its discharge event is
> unchanged: the milestone that configures a provider, still undesignated.
>
> **What was explicitly rejected**, at the user's direction: introducing
> Ollama, model weights, or provider non-determinism into Phase 4C solely to
> force the acceptance test; fabricating agent instances; seeding task graphs;
> and mocking peer-review rounds for acceptance. **This is a scope deferral
> only. AC-4 remains NOT MET, its deferred clauses must not be represented as
> met, and the provider dependency is not weakened.**

---

## 2. The inherited UI gap — a two-phase-old carry-forward

This is the single most consequential piece of inherited state in Phase 4,
and it is not new information: the project already diagnosed it and already
designed the fix.

| When | What happened |
|---|---|
| Phase 2D | `api-gateway` + `ws-gateway` "minimal implementation" and `apps/web-client`'s first panel were a **Phase 2D deliverable** (`ENGINEERING_ROADMAP.md:451`), confirmed in the Phase 2D Master Blueprint §141-145, never excluded by its own exclusion list — and **never built**. |
| Phases 2D-A/2D-B | Every Gate Review silently re-deferred it through a "0 React files" metrics-table line. It was never surfaced as an explicit scope decision. |
| Phase 3 | Diagnosed and designed in full as [`3-P` — Gateway & Web-Client Prerequisite](../phase-3/03-gateway-web-prerequisite.md), 284 lines. Approved in design, **never authorized for code**. |
| Phase 3 close | Recorded as an open carry-forward: *"The gateway/web-client prerequisite … and `apps/web-client`'s Planning/Agent Activity panels remain **design-only**, no production code authorized yet."* (`ENGINEERING_ROADMAP.md:515`) |

**Phase 4 executes `3-P` rather than redesigning it.** `3-P` §2, §3, §4 and
§7–§10 are carried forward substantially unchanged into
[`01-tdd-4a-gateways-and-web-client.md`](01-tdd-4a-gateways-and-web-client.md);
this document records only what Phase 4 *changes* or *adds*.

---

## 3. Verified starting state

Measured against `main` at `7e273e6` on 2026-09-01, not assumed.

| Area | State |
|---|---|
| Engines | **14** under `services/`, all with real `/v1` REST surfaces — **26** distinct path prefixes declared in code |
| `agent-os` | 4 components (`kernel`, `registry`, `supervisors`, `sdk/python`), **zero REST API** — health-only by deliberate design, TDD 3E §4 |
| Agent Packages | **5** under `agents/` (`research`, `coding`, `qa`, `architect`, `documentation`) |
| `nova-contracts` TypeScript codegen | **98 generated `.ts` files, zero consumers anywhere in the repository** |
| `services/api-gateway`, `services/ws-gateway` | **Neither exists** |
| `services/nova-auth` | **Does not exist** — full OIDC is a Phase 7 deliverable |
| `packages/nova-ui` (`@nova/ui`) | **Does not exist** — named in doc [01](../../architecture/01-technology-stack.md) §6 and doc [04](../../architecture/04-frontend-architecture.md) |
| `apps/` | **Does not exist**; **zero `.tsx` files repository-wide** |
| `pnpm-workspace.yaml` | **Already contains `apps/*`** — the workspace is pre-wired for the web client |
| `pr-checks.yml` | Already runs `pnpm turbo run lint` and `pnpm turbo run test` — a new app in `apps/` is picked up automatically; **no TypeScript-aware step exists** |
| `docker-compose.local.yml` | 14 engine services + full infra — **`agent-os` absent** |
| `build-and-scan.yml` matrix | 14 services + `dependency-audit` — **`agent-os` absent** |
| `tools/scaffold-engine.py:28` | `_NAME_PATTERN = ^[a-z][a-z0-9]*(-[a-z0-9]+)*-engine$` — requires a literal `-engine` suffix, **blocks scaffolding both gateways** |

---

## 4. Inherited Phase 3 carry-forwards and limitations

Every item below is inherited, disclosed, and unresolved as of `7e273e6`.
None is a defect introduced by Phase 4.

| ID | Carry-forward | Source | Phase 4 impact | Disposition |
|---|---|---|---|---|
| **CF-1** | `3-P` gateways + web-client remain design-only | `ENGINEERING_ROADMAP.md:515` | The entire UI track starts here | **Resolved by 4A** |
| **CF-2** | `GET /v1/agents` and `GET /v1/agents/{id}/activity` are named in doc [11](../../architecture/11-api-architecture.md) §2 but unbuilt, and explicitly *"an open `3-P` prerequisite with no owning TDD"* | [`3-P`](../phase-3/03-gateway-web-prerequisite.md) §5 | **Blocks the Agents panel** | **Discharged by 4C.2c, 2026-09-09** (§9.1). Both named routes are built on `agent-os/kernel`, plus a third resource read; all three are forwarded by `api-gateway` under the `/v1/agents` prefix, so the panel has a reachable data source. Note that the *data* behind `instances` and `activity` stays empty without a model provider — AC-4 clauses 2 and 3 remain Deferred (§1.1), and that is a provider gap, not a CF-2 one |
| **CF-3** | Phase 3E condition **C-3**, ratified as a *deferred obligation*: `agent-os` has no Dockerfile, no compose service, no `build-and-scan` matrix entry, and therefore no Trivy scan | [Phase 3E Gate Review](../../roadmap/architecture-reviews/phase-3e-agent-os-gate-review.md) §10; [`phase-3e.md`](../../project-health/phase-3e.md) field 20(b) | **`agent-os` cannot run under `docker compose up`** — blocks any live agent panel | **Discharged by 4C.1, 2026-09-07** (§10's implementation note). Three Dockerfiles, three compose services, three `build-and-scan` matrix entries with first-ever Trivy coverage, migrator wiring, and all three started and restart-checked by the e2e job |
| **CF-4** | Phase 3E narrowings: restart-resume (AC-2) and hot-load (AC-3) are proven at unit + integration + real-Postgres level, **not by a full-path E2E**; hot-load is version *pinning*, not concurrent execution of two bytecode versions | [16-3e-hot-load-design-decision.md](../phase-3/16-3e-hot-load-design-decision.md) | A UI makes both newly demonstrable | **Opportunity, not a blocker.** Phase 4 does not claim to close them |
| **CF-5** | `PHR-1` / `PHR-2` — pre-existing Phase-1 defects, reported and not fixed | Project Health Review 2026-08-29 | None direct | **Carried forward unchanged** |
| **CF-6** | Real-Postgres verification of `personality-engine`, `communication-engine`, `perception-engine` repository layers still pending | Open task | 4A's Conversation panel exercises `communication-engine` | **Flagged.** 4A's real-infra job covers it incidentally; not claimed as closure |
| **CF-7** | **Doc 11 §2's documented paths diverge from the paths actually implemented** — see §8 | doc [11](../../architecture/11-api-architecture.md) §2 vs. code | `api-gateway` must forward *somewhere* | **Resolved by D-6** |
| **CF-9** | *(added 2026-09-06 by the Phase 4B closure pass)* **ADR-032 decision point 2 has no implementation.** Every gating engine must expose *"a configurable identity-confidence threshold per privileged capability (or per capability class), never a single hardcoded system-wide threshold"*. `action-engine` **enforces** the gate (`domain/pipeline.py:180-192`) and **models** the policy (`domain/models.py:46`; table `action.identity_confidence_policy`), but nothing in the repository can **create** a policy row — no endpoint, no seed, no migration insert, no admin surface. **Originating owner: Phase 3D / ADR-032.** Discovering phase: 4B | [ADR-032](../../architecture/adr/ADR-032-identity-confidence-is-also-an-authorization-signal.md) pt. 2; [TDD 3D](../phase-3/07-tdd-3d-action-engine.md) §7, §8; [Phase 4B Gate Review](../../roadmap/architecture-reviews/phase-4b-observability-panels-gate-review.md) §0.3 | **Every Critical-risk Action is denied at stage 3**, so the Phase 3D approval loop is unreachable from any client. Blocks **AC-3**'s approval clause. Absent policy fails closed at confidence 1.0, and `perception-engine`'s `SINGLE_SIGNAL_CONFIDENCE_CEILING = 0.75` means even a real single-signal identity cannot clear it — the gate is passable *only* with a policy row | **Deferred by explicit user approval, 2026-09-06** (Gate Review §0.3, §9.2, condition C-1). **Routed to 4D** as the appropriate future policy surface — a forward routing decision, **not** a reassignment of historical ownership, and **not** a claim that AC-3 depends on 4D (§1.1 says the opposite). No threshold was invented; the fail-closed default is unchanged |
| **CF-8** | Six Phase 3E TDD deviations ratified as explicit narrowings (Scheduler scoring; `agent.{instance_id}.{state}` lifecycle events; `agent_os.health.snapshot`; `planning.decompose.request` never called; in-process `AgentMessage` mailbox; `DecisionMemoryPort` log stub) | Phase 3E Gate Review §2 | The Agents panel must render what *is*, not what the TDD described | **Carried forward.** 4C's panel is built against observed behavior |

---

## 5. Milestones 4A–4F

Each milestone ends with a system a person can open in a browser and use.
No milestone requires the next one to be useful.

### 4A — Gateways & Shell

`services/api-gateway`, `services/ws-gateway`, `packages/nova-ui`,
`apps/web-client` shell, the Conversation panel, the presence/identity
indicator, the System Pulse, and the Phase-4-scoped session model.

**Depends on:** nothing new. Every backend it talks to
(`communication-engine`, `personality-engine`, `perception-engine`,
`world-model-engine`) shipped in Phase 2D and is Gate-Reviewed.
**Satisfies:** AC-1, AC-2.
**Full design:** [`01-tdd-4a-gateways-and-web-client.md`](01-tdd-4a-gateways-and-web-client.md).

### 4B — Observability panels

Panels: **Planning** (live `TaskGraph`, dependency + critical path),
**Reasoning Trace** (including 3A's recursion depth), **Capabilities**
(list / install / uninstall), **Approvals** (risk classification,
approve/reject), **Event Stream** (filterable raw bus inspector), **System
Health**.

Backend additions: `GET /v1/system/health` aggregate (doc 11 §2 names it;
no engine owns it — `nova-core` is the natural owner), plus widened
`api-gateway` forwarding and `ws-gateway` allow-lists.

**Depends on:** 4A. **Satisfies:** AC-3.
**This is the milestone that makes Phase 3 visible.**

> **Implementation status — 2026-09-06 (added by the Phase 4B closure pass; the
> text above is preserved verbatim as written).**
>
> All six panels were built and are browser-verified against the real Docker
> stack: 30/30 CI Check Runs green against head `0f3412c`. **The gate verdict is
> nonetheless NO-GO** — see the
> [Phase 4B Gate Review](../../roadmap/architecture-reviews/phase-4b-observability-panels-gate-review.md).
>
> **Three capabilities named above were not built**, and none had an approval to
> narrow it:
>
> - **Capabilities** shipped as **list only**. "install / uninstall" above was not
>   built, though `capability-engine` already exposes `POST /v1/capabilities/install`
>   and `DELETE /v1/capabilities/{id}` and the gateway forwards `/v1/capabilities`.
> - **Event Stream** shipped **without a filter**. "filterable" above was not built.
> - **Reasoning Trace** renders `reasoning_level` — the 1–4 reasoning tier — not
>   "3A's recursion depth", which is a different field
>   (`MultiStepConfig.max_step_depth` / `multistep_recursion_exhausted`).
>
> **`GET /v1/system/health` was not built.** `nova-core` exposes only
> `/internal/*`, which doc 11 §3 makes permanently unroutable, so building it
> would mean giving `nova-core` a public HTTP surface — a decision no phase has
> taken. The Health panel is push-fed from `nova.heartbeat`,
> `nova.module.status_changed` and `ai_model.model.health_changed` instead. Doc
> 11 §2 now carries the same note.
>
> **AC-3 is therefore not met** (Gate Review §9): of its four sub-clauses, two
> need an LLM provider Phase 4 does not add, and two need controls that were not
> built. Whether to defer AC-3 and ratify the three narrowings is an open
> decision for the user, recorded in Gate Review §13 and §15.
>
> **Two backend additions not anticipated above** were required and built:
> `GET /v1/plans` (planning-engine) and `GET /v1/action/approvals`
> (action-engine), plus `reasoning-engine-worker` and
> `ai-model-orchestration-engine-worker` compose services — without which those
> engines' outbox rows are persisted and never published.

### 4C — Agent Activity

Discharges **CF-3** by containerizing the three deployable `agent-os`
components and adding them to `docker-compose.local.yml` and the
`build-and-scan.yml` matrix. Closes **CF-2** by adding a minimal read-only
`/v1` surface to `agent-os/kernel` (§9). Adds the **Agents** panel:
registered packages, live instances, supervisor tree, per-instance
activity, peer-review rounds.

**Depends on:** 4B, D-4, D-5. **Satisfies:** AC-4.

> **Wording corrected 2026-09-07 (user approval, Phase 4C design decision
> 5).** The paragraph above read *"containerizing all four `agent-os`
> components"*, which contradicted §10 item 1 — *"a Dockerfile for `kernel`,
> `registry`, and `supervisors`. (`sdk/python` is a library — no Dockerfile,
> consistent with `packages/*`.)"* — and would have read as a mandate for a
> fourth container. **§10 is authoritative: three containers, not four.**
> `agent-os` does have four *components* (§3 says so, and that count stands);
> only three are deployable. The original wording is preserved here as the
> superseded record, per the project's documentation protocol. Enforced rather
> than only written down: `tools/tests/test_e2e_stack_completeness.py::test_the_agent_os_library_has_no_container`.

> **Implementation status — 2026-09-07 (milestone 4C.1).** Containerization is
> built: three Dockerfiles, three `docker-compose.local.yml` services, three
> `build-and-scan.yml` matrix entries — **the first Trivy coverage any
> `agent-os` component has ever had** — `agent-os/kernel` and
> `agent-os/registry` added to `run-migrations.sh`, and all three started and
> restart-checked by `pr-checks.yml`'s e2e job.
>
> **4C.1 discharges the containerization portion of AC-4, but AC-4 remains
> NOT MET** until the remaining required clauses are demonstrated or
> explicitly deferred. Nothing else in this milestone's list is built: no
> `/v1/agents`, no activity persistence, no peer-review persistence, no Agents
> panel, no new realtime exposure, no supervisor tree.
>
> **AC-4's remaining two clauses are deferred by explicit user approval,
> 2026-09-07** — see the AC-4 row in §1.1.

### 4D — Autonomy

`services/autonomy-engine`: Autonomy Levels 0–2 defined, **Levels 0–1
enabled** (Observation Only → Suggestive; no auto-execution), Trust Engine,
Policy Engine, Permission Matrix. The Trust Engine consumes Phase 2D-D's
conversational trust-development signal as one input rather than
re-deriving an unrelated one. Adds the **Autonomy** panel: level selector,
trust score, policy editor, suggestion inbox.

**Depends on:** 4C. **Satisfies:** AC-5.

> **Implementation status note (added 2026-09-13; the scope text above is
> unchanged).** 4D is **implemented and locally verified on `phase-4d`, head
> `de6dbc9` — not merged, and with no CI run at any SHA**, because both
> workflows trigger only on `pull_request` or a push to `main` and no pull
> request was opened. Gate verdict **CONDITIONAL-GO** with four open conditions,
> **none of which is an approved deferral**, so it must not be read as GO: C-1
> no CI run · C-2 the `real_infra` tier unexecuted · C-3 the AC-5 Playwright
> spec unexecuted · C-4 two TDD clauses need reconciling. See the
> [Gate Review](../../roadmap/architecture-reviews/phase-4d-autonomy-engine-gate-review.md)
> and [`phase-4d.md`](../../project-health/phase-4d.md).
>
> **What shipped, against the paragraph above.** Levels 0–2 defined with Bible
> Part 14's vocabulary, 0–1 selectable and Level 2 defined-but-disabled per
> decision D-1; the Trust Engine, Policy Engine and Permission Matrix, with the
> matrix carrying Part 14's ten categories verbatim and in its order; doc 07's
> append-only `autonomy.decision_log` plus four supporting tables; the
> `/v1/autonomy/*` REST surface fronted 1:1 by `api-gateway`; and the Autonomy
> panel with all four named widgets.
>
> **Two things in this section's own sentence turned out not to be
> implementable, and are recorded rather than narrowed silently.** *"The Trust
> Engine consumes Phase 2D-D's conversational trust-development signal as one
> input"* — it consumes the signal's **shape**, and every `None` path is tested,
> but **no read surface for that signal exists**: `digital-twin-engine` serves
> only `digital_twin.preferences.get.request` and exposes no trust route, and
> `BoundEventBus.request()` gates on the publishable allow-list that ratified
> decision **D-4D-1** requires to stay empty. The input is therefore reported
> `UNAVAILABLE` with its reason — exactly the fail-closed behaviour TDD 4D §13
> specifies — and the gap is carried forward as **CF-10**. Separately, the
> *"suggestion inbox"* has **no producer**: D-4D-1 removed the Event Bus origin
> and TDD §8.1 defines no creation route, so in production the inbox is
> permanently empty and says so. Carried forward as **CF-11**. 4D builds the
> decision surface, not the initiative surface.
>
> **§15's two matrix rows below are half-discharged by this milestone**: the
> `autonomy-engine` entries in `build-and-scan.yml` and `real-infra-checks.yml`
> both exist. The `cognitive-state-engine` entries remain 4F's.

> **CI verification note (added 2026-09-13, later the same day; the note above is
> left as written, per protocol §0.3.4).** **PR #27** (`phase-4d` → `phase-4`) was
> opened solely to obtain CI evidence, with merge authorization explicitly
> withheld, and the branch advanced to head **`f5f263f`** (`de6dbc9` → `5a2bf77`
> docs → `32b6dcd` three CI fixes → `f5f263f`). Three sentences of the note above
> are consequently out of date:
>
> - *"no CI run at any SHA"* — **36 checks ran.** **C-1 is discharged for 4D's
>   scope**: every check exercising 4D is green.
> - *"C-2 the `real_infra` tier unexecuted"* — **discharged.**
>   `real-infra (autonomy-engine)` ran **16 passed, 222 deselected**, twice.
> - *"C-3 the AC-5 Playwright spec unexecuted"* — **discharged.** Both AC-5 specs
>   executed and passed in a real browser (they ran; they were not skipped).
>
> **Two conditions remain open, neither an approved deferral**, so this still must
> not be read as GO: **C-4** (the TDD §5.3/§4.1 reconciliation, offered for
> ratification — no implementation depends on it) and the new **C-5**
> (`build-and-scan (ws-gateway)` fails on 3 CRITICAL + 9 HIGH pre-existing Debian
> CVEs; `git diff origin/phase-4..f5f263f -- services/ws-gateway/` is **0 lines**,
> and the one-line fix was deliberately not applied because that component is
> outside this branch's ratified scope).
>
> **`CF-10` and `CF-11` above are re-verified at source and stay OPEN** — no trust
> RPC, no Event Bus subject and no production producer was created to make them
> disappear. **CF-9 stays OPEN** by decision D-4D-2. The separately-recorded CF-12
> (both tiers unexecuted) is **CLOSED** by the runs above. **Nothing is merged**;
> `phase-4` and `main` are untouched.

> **Final Gate Review note (added 2026-09-14; both notes above are left as
> written, per protocol §0.3.4).** Phase 4D's verdict is now **GO** (Gate Review
> §22). **All five conditions C-1…C-5 are DISCHARGED** and CI is **36/36 green at
> head `9afddf6`**, zero failed and zero cancelled — so the two notes above,
> which record C-4 and C-5 as open and `phase-4` as untouched, are superseded on
> those three points.
>
> - **C-5** was fixed at its **root**, not worked around: `tools/scaffold-engine.py`'s
>   Dockerfile template predated the 2026-08-17 runtime-hardening convention by
>   nine days, so every engine scaffolded afterwards inherited an unpatched base.
>   Corrected on a repository-maintenance branch as **PR #28**, merged into
>   `phase-4` as **`dd6a147`** and inherited by `phase-4d` at **`9afddf6`**. All
>   **20 of 20** images now carry the convention, and a guard test asserts it
>   against the `build-and-scan` matrix. **`phase-4` therefore advanced to
>   `dd6a147`** — by Phase 4 maintenance, not by 4D landing. `main` is still
>   `7e273e6`.
> - **C-4** was discharged by a ratified **documentation-only** reconciliation of
>   TDD §5.3 and §4.1. **No Event Bus trust subject, no RPC and no architecture
>   change**; the diagram edge is annotated NOT IMPLEMENTED rather than redrawn.
>
> **CF-9, CF-10 and CF-11 remain OPEN** exactly as the note above describes them,
> and GO does not close them. **PR #27 is still open and not merged.**

> **Closure note (added 2026-09-14; every note above is left as written, per
> protocol §0.3.4).** **Phase 4D is CLOSED.** PR #27 merged into `phase-4` on
> explicit user authorization as **`68397a200f08db497fc4f36a1b14422dc953298e`** —
> a normal two-parent merge of `dd6a147` and `dff646c`, no squash, no rebase, no
> force-push — so the sentence directly above, *"PR #27 is still open and not
> merged"*, is superseded. `phase-4d` is preserved at `dff646c`, not deleted, and
> is an ancestor of `phase-4`. `main` remains `7e273e6`, still frozen per §16
> rule 2.
>
> **Milestone state: 4A, 4B, 4C and 4D are merged into `phase-4`; 4E and 4F
> remain.** Per §16 rule 4 the next milestone branch is cut only after this merge
> is verified — which it is — and **`phase-4e` has not been created**.
>
> **CF-9, CF-10 and CF-11 stay OPEN and are inherited by Phase 4's closure**,
> joining §4's register above. 4D's GO closes none of them: CF-9 by ratified
> decision D-4D-2, CF-10 because no `TrustMetric` read surface exists in any
> engine, CF-11 because no component produces a suggestion. **No `autonomy.*`
> Event Bus subject, no `TrustMetric` RPC or subject, and no production
> suggestion producer was created at any point in 4D.**

### 4E — Digital Twin

`digital-twin-engine` **extension** — the remaining nine of Bible Part 16's
eleven domains, populated from real Perception + Memory data for the first
time, additive to the **two** domains already shipped in Phase 2D-D. Adds the
**Digital Twin** panel.

> **Enumeration corrected 2026-09-14 (ratified).** This paragraph originally
> read: *"the remaining nine of Bible Part 16's eleven domains (goal model,
> project model, software/hardware environment, skill model, knowledge profile,
> productivity patterns, learning progress), populated from real Perception +
> Memory data for the first time, additive to the Communication Profile domain
> shipped in Phase 2D-D."* Preserved verbatim per protocol §0.3.4; two things in
> it were wrong, and the count **nine is not one of them**.
>
> **The parenthetical enumerated eight, not nine** — expanding
> "software/hardware environment" into the two domains Part 16 names separately
> — and omitted **Personal Workflow**, which Part 16 lists first. **The nine
> remaining domains, complete and in Part 16's own vocabulary, are:**
>
> 1. **Personal Workflow**
> 2. **Projects**
> 3. **Software Environment**
> 4. **Hardware Environment**
> 5. **Knowledge Profile**
> 6. **Skill Profile**
> 7. **Productivity Patterns**
> 8. **Goals**
> 9. **Learning Progress**
>
> **"additive to the Communication Profile domain" implied ten remaining, not
> nine.** **Two** Part 16 domains ship today, and both are unchanged by 4E:
> **Communication Style** (as `CommunicationProfile`) and **Preferences** (as
> `PreferenceEvolutionHistory`, the served RPC
> `digital_twin.preferences.get.request`, and `GET /preferences`). With both
> counted the arithmetic closes exactly — **11 − 2 = 9** — which is why the
> original count was right even though its list was short.
>
> All eleven names are Part 16's own (lines 75–95), verified line by line. **No
> domain is invented, renamed or merged by this correction.** See
> [`05-tdd-4e-digital-twin-extension.md`](05-tdd-4e-digital-twin-extension.md)
> §0.1 and §4.

**Depends on:** 4D. **Satisfies:** AC-6.

> **Closure note (added 2026-09-15; every note above is left as written, per
> protocol §0.3.4).** **Phase 4E is CLOSED.** PR #29 merged into `phase-4` on
> explicit user authorization as **`59bbeee3838290ab31b0627b64c6fc0b2bceb13b`** —
> a normal two-parent merge of `f39fa6c` and `df4606c`, no squash, no rebase, no
> force push. `phase-4e` is preserved at `df4606c`, not deleted, and is an
> ancestor of `phase-4`; **all ten Phase 4E commits remain reachable**, which is
> what §16's close-out sequence item 6 requires a merge commit for. `main`
> remains `7e273e6`, still frozen per §16 rule 2.
>
> **AC-6 is MET** — the Digital Twin's project model reconstructs a project
> across a genuine multi-week gap and the reconstruction is visible in the panel,
> proven at unit, integration, real-Postgres and browser tier. Final gate verdict
> **GO with no conditions attached**; CI was 37/37 green at the merged head
> `df4606c`.
>
> **Milestone state: 4A, 4B, 4C, 4D and 4E are merged into `phase-4`; 4F
> remains.** Per §16 rule 4 the next milestone branch is cut only after this
> merge is verified — which it is — and **`phase-4f` has not been created. No
> Phase 4F functionality has been started: no `nova-companion`, no
> `cognitive-state-engine`, and no Autonomy Level 2.**
>
> **CF-9, CF-10 and CF-11 stay OPEN and are inherited by Phase 4's closure**,
> unchanged by 4E's GO or its merge. **Phase 4E's own three findings also stay
> OPEN**: `nova_testkit`'s Postgres fixture image drift, the D-6 prefix exposing
> six pre-4E `digital-twin-engine` operations that take a caller-supplied
> `user_id` (reported not fixed, pinned by two tests), and the stranded-outbox
> guard that does not yet watch the `memory` schema. **No Event Bus subject, no
> `PUBLIC_TOPICS` entry, no `autonomy.*` subject and no `TrustMetric` surface was
> created at any point in 4E.**

### 4F — Senses & inner life

`nova-companion` (Rust): desktop/window-focus, clipboard, filesystem, and
process/system-health sensors; terminal and window-control actuators,
registered behind Phase 2D-B's existing Sensor Abstraction Layer.
`perception-engine` **extension**: event normalization, context enrichment,
multi-modal fusion (the "meeting begins" scenario becomes real).
`services/cognitive-state-engine`: Active Thoughts, Focus System, Attention
Layers — explicitly distinct from Phase 2D-C's session-scoped conversation
memory. **Autonomy Level 2** enabled. Adds the **Cognitive State** panel.

**Depends on:** 4E. **Satisfies:** AC-7, AC-8.
**This milestone carries all of Phase 4's platform risk, and it comes last
by design (D-1).**

---

## 6. UI panel scope by milestone

Doc [04](../../architecture/04-frontend-architecture.md) §2 names twelve
panels. Phase 4 builds **eleven**. The scope line is explicit so it cannot
drift.

> **Count discrepancy resolved 2026-09-08 by explicit user approval (Phase 4C
> design decision 6); G-6 is closed.** The sentence above **read "eight"** and
> the table below lists **eleven** rows assigned to a Phase 4 milestone —
> `conversation/` (4A), the six 4B panels, `agents/` (4C), `autonomy/` (4D),
> `digital-twin/` (4E) and `cognitive-state/` (4F). The two could not both be
> right.
>
> **The table is authoritative and the prose was wrong.** Eleven is the number
> the arithmetic closes on: doc 04 §2 names twelve panels, §13's non-goals defer
> five of them to Phase 5 (`memory-timeline/`, `knowledge-graph/`,
> `world-model/`, `personality/`, `executive/`), leaving seven, and Phase 4 adds
> four that doc 04 predates (`capabilities/`, `approvals/`, `events/`,
> `cognitive-state/`) — 12 − 5 + 4 = **11**. Nothing reconciles to eight.
>
> **This is a documentation-only correction.** No acceptance criterion depends
> on the count: AC-1…AC-8 name panels individually and never a number. **D-8's
> "all six 4B panels" is a different, correct count and is unchanged.** The
> discrepancy was pre-existing, not introduced by Phase 4B, and the table — not
> the prose — is what 4B was built against, so no shipped scope changes. The
> original wording is preserved here as the superseded record, per the project's
> documentation protocol. It **was** recorded as an open question needing the
> user's call in the
> [Phase 4B Gate Review](../../roadmap/architecture-reviews/phase-4b-observability-panels-gate-review.md)
> §13 (G-6), which still describes it that way: that Gate Review is a dated
> record of the 4B gate and is deliberately left as written.

| Panel | Milestone | Primary source |
|---|---|---|
| `conversation/` | **4A** | `communication-engine` |
| `system/` | **4B** | ~~`GET /v1/system/health`~~ (never built — see §5's 4B note), `nova.heartbeat` + `nova.module.status_changed` + `ai_model.model.health_changed` (as built, 2026-09-06) |
| `planning/` | **4B** | `planning-engine` `/v1/plans`, `planning.task_graph.*` |
| `reasoning/` | **4B** | `reasoning-engine` `/v1/reasoning`, `/v1/reasoning/decisions` |
| `capabilities/` | **4B** | `capability-engine` `/v1/capabilities` |
| `approvals/` | **4B** | `action-engine` `/v1/action/approvals/{id}/decide` |
| `events/` | **4B** | `ws-gateway` raw allow-listed stream |
| `agents/` | **4C** | `agent-os/kernel` `/v1/agents` (D-4) + `agent_os.task.completed` (**as built, 2026-09-10** — see the note below this table) |
| `autonomy/` | **4D** | `autonomy-engine` |
| `digital-twin/` | **4E** | `digital-twin-engine` `/v1/digital-twin` |
| `cognitive-state/` | **4F** | `cognitive-state-engine` |
| `memory-timeline/` | **Phase 5** | — |
| `knowledge-graph/` | **Phase 5** | — |
| `world-model/` | **Phase 5** | — |
| `personality/` | **Phase 5** | — |
| `executive/` | **Phase 5** | — |

`capabilities/`, `approvals/`, `events/` and `cognitive-state/` are Phase 4
additions to doc 04's named set; the first three exist because Phase 3
built engines that doc 04 predates. **Doc 04 §2 will be amended additively
in 4B** to record them — it is not being redesigned.

> **The `agents/` row corrected, 2026-09-10 (4C.2g closure).** This row read
> *"`agent.*`/`agent_os.*`"*. **4C shipped neither pattern**, and the row is
> corrected rather than the code bent to match a prediction written before the
> surface existed.
>
> - **`agent.*`** is the `agent.{instance_id}.{state}` lifecycle family that
>   Phase 3E never built. **CF-8** ratified its absence as an explicit
>   narrowing, and 4C's approved design (decision D-4) declined to revive it:
>   a public topic nothing publishes is a topic a browser subscribes to and
>   then waits on forever.
> - **`agent_os.*`** was never a browser-public pattern and must not be
>   documented as one. `BoundEventBus` matches with `fnmatchcase`, where `*`
>   spans dots, so that prefix would cover every Registry and Supervisor RPC
>   subject — `agent_os.registry.list_packages.request` among them.
>
> **What actually ships.** One public topic, `agent_os.task.completed` — the
> only broadcast event `agent-os/kernel` publishes — reached through the
> `agent_os.task.*` Event Bus subscription and named exactly by the browser.
> Full detail in §9.2.

---

## 7. Dependencies and implementation order

```
4A  Gateways & Shell ────────────────┐  depends on nothing new
     │                                │
4B  Observability panels ─────────────┤  depends on 4A
     │                                │
4C  agent-os containerize + /v1 ──────┤  depends on 4B, D-4, D-5
     │                                │
4D  autonomy-engine L0-L1 ────────────┤  depends on 4C
     │                                │
4E  digital-twin extension ───────────┤  depends on 4D
     │                                │
4F  nova-companion + cognitive-state ─┘  depends on 4E; carries all platform risk
```

**Ordered implementation steps**

1. **Pre-work.** Relax `tools/scaffold-engine.py`'s `_NAME_PATTERN` (D-2). Scaffold both gateways. **Compile the 98 generated contract types under a real `tsconfig` before any application code is written** — this de-risks R-3 at the lowest possible cost.
2. `api-gateway` fronting exactly one engine end-to-end (`communication-engine`) plus the session model. Verified by integration test.
3. `ws-gateway` bridging `communication.*` only. Verified by a real WebSocket receiving a real bus event.
4. `packages/nova-ui` minimum; `apps/web-client` shell + `entities/` + `realtime/` + Conversation panel + System Pulse. **Playwright golden path — AC-1.**
5. Widen gateway forwarding and allow-lists; build the six 4B panels. **AC-3.**
6. Containerize `agent-os`; add `/v1/agents` + `/v1/agents/{id}/activity`; Agents panel. **AC-4.**
7. `autonomy-engine` L0–L1 + Autonomy panel. **AC-5.**
8. `digital-twin-engine` extension + Digital Twin panel. **AC-6.**
9. `cognitive-state-engine`, then `nova-companion`, then Autonomy Level 2. **AC-7, AC-8.**

---

## 8. API path decisions (D-6)

Doc [11](../../architecture/11-api-architecture.md) §2's representative
endpoint list was written before several engines shipped, and **diverges
from the paths actually implemented**. The divergence was found by
comparing doc 11 §2 against every `/v1` prefix declared in
`services/*/src/*/api/*.py`.

| Doc 11 §2 says | Code actually exposes | Owner |
|---|---|---|
| `POST /v1/conversations`, `/v1/conversations/{id}/messages` | `/v1/communication/sessions`, `/v1/communication/notifications` | `communication-engine` |
| `GET /v1/memory/search`, `/v1/memory/{id}` | `/v1/memories` | `memory-engine` |
| `GET /v1/knowledge/graph` | `/v1/knowledge`, `/v1/knowledge/contradictions` | `knowledge-engine` |
| `GET /v1/world-model/context` | `/v1/world`, `/v1/world/objects` | `world-model-engine` |
| `POST /v1/autonomy/approvals/{id}/decide` | `/v1/action/approvals/{id}/decide` | `action-engine` |
| `GET /v1/plans/{task_graph_id}` | `/v1/plans` ✅ matches | `planning-engine` |
| `GET /v1/capabilities` | `/v1/capabilities` ✅ matches | `capability-engine` |

The `/v1/communication/*` shape is not accidental — it is the result of a
deliberate normalization to `/v1/<domain>/...` performed during Phase 2D.

**D-6 decision (approved): correct doc 11 §2 to match the shipped code;
`api-gateway` forwards 1:1 with no path rewriting.** A translation layer
between documented and real paths would be a permanent source of drift,
and the shipped names are the more consistent of the two. Doc 11 §2 is
amended additively in 4A, preserving the original list as the superseded
record per the project's documentation protocol.

**One genuine gap remains after the correction:** `/v1/autonomy/...` is a
real future surface owned by `autonomy-engine` (4D), distinct from
`action-engine`'s existing approval endpoint. Both will exist; they are not
duplicates. 4D defines the boundary.

---

## 9. `agent-os` API amendment (D-4)

TDD 3E §4 deliberately gave `agent-os/kernel` a **health-only** HTTP
surface (`/internal/health`, `/internal/readiness`, `/internal/metrics`)
and no `/v1` REST surface at all, on the reasoning that the Kernel's work
is Event-Bus- and internal-loop-driven. That reasoning was correct for
Phase 3, in which nothing consumed a Kernel API.

**Phase 4 amends it.** The Agents panel needs point-in-time queries — "what
packages are registered", "what is instance X doing" — which an event
stream alone cannot answer. A client that joins mid-stream sees no history.

**Approved amendment.** `agent-os/kernel` gains a **minimal, read-only**
`/v1` surface:

```
GET /v1/agents                 # registered packages + live instances
GET /v1/agents/{id}/activity   # per-instance activity, cursor-paginated
```

Constraints on the amendment, all binding:

- **Read-only.** No mutation endpoint is added. Agent lifecycle stays
  Event-Bus-driven, exactly as TDD 3E designed it.
- Both endpoints already appear in doc 11 §2 — **this builds a documented
  surface, it does not invent one.**
- Cursor-based pagination on `/activity`, per doc 11 §2's rule for
  unbounded collections.
- The doc 11 §4 envelope applies.
- Reachable **only** through `api-gateway`. `/internal/*` remains
  unexposed.

This is recorded as an **explicit Phase 4 amendment to a ratified Phase 3E
narrowing**, not a correction of it — TDD 3E's decision was right on the
evidence available in Phase 3.

### 9.1 The third route — implemented and ratified (4C.2c, 2026-09-09)

D-4 as originally approved names **two** routes. The surface built in 4C.2c
has **three**:

```
GET /v1/agents                             # overview
GET /v1/agents/{agent_instance_id}         # individual instance lookup
GET /v1/agents/{agent_instance_id}/activity
```

**`GET /v1/agents/{agent_instance_id}` is explicitly ratified by the user
(2026-09-09) as an approved part of the 4C.2c read-only REST surface.** It
was flagged before implementation as a widening of an approved decision,
implemented, and then ratified on review rather than absorbed silently.

The ratified reasoning:

- `GET /v1/agents` provides the **overview**.
- `GET /v1/agents/{id}` provides **individual instance lookup**.
- `GET /v1/agents/{id}/activity` **requires existence validation**, so that
  an unknown instance returns `404` rather than being confused with a valid
  instance that simply has no activity. The single-instance lookup that
  check needs is what this route is the external expression of.

It violates none of D-4's binding constraints: still `GET`-only, still
behind `api-gateway`, still no mutation, `/internal/*` still unexposed. It
is a read of a single row already returned in bulk by `GET /v1/agents`,
exposing no field the list endpoint does not and no data D-4 did not
already authorise. It also matches the shape doc 11 §2 already uses for
every other collection — `/v1/plans` + `/v1/plans/{task_graph_id}`,
`/v1/memory/search` + `/v1/memory/{id}`; `/v1/agents` was the one
collection in that document with a sub-resource but no resource read.

Doc 11 §2's endpoint list is amended in the same slice to name all three,
so the document and the code do not diverge again.

**What was *not* added, and why:** no `GET /v1/agents/packages`, no
supervisor-scoped route, no per-instance mutation. Each would have widened
D-4 further with no consumer asking for it.

### 9.2 The Agents surface as built — Phase 4C.2 (closed 2026-09-10)

4C.2 delivered the Agents surface end to end in **six slices**, each reviewed
and committed separately on `phase-4c.2`:

| Slice | Commit | What it added |
|---|---|---|
| **4C.2a** | `8ed7436` | Registry `agent_os.registry.list_packages` RPC — **internal**, never browser-reachable |
| **4C.2b** | `c1dbd44` | `agent_os.agent_activity` table, append-only, with the transactional repository surface |
| **4C.2c** | `92ba4d7` | The Kernel's read-only `/v1/agents` REST surface, fronted by `api-gateway` |
| **4C.2d** | `e0489b9` | Activity writes wired into the real Kernel lifecycle |
| **4C.2e** | `e97602c` | `agent_os.task.completed` opened to the browser through `ws-gateway` |
| **4C.2f** | `a405bca` | The Agents entity, panel, `/agents` route and realtime reconciliation |

4C.2g is this closure pass — documentation, verification and the Gate Review.
It added no product functionality.

**REST — three read-only routes, no mutation path.** `GET /v1/agents`,
`GET /v1/agents/{agent_instance_id}` (ratified, §9.1) and
`GET /v1/agents/{agent_instance_id}/activity`. Activity is **keyset**
paginated on an opaque cursor; there is no offset anywhere. A degraded
Registry answers **503** and never an empty package list (decision D-1) — `200`
with `packages: []` means a healthy Registry holding nothing, and the two are
kept distinct at every layer. An unknown instance is **404**; a known instance
with no history is a successful **empty page**. `/internal/*` remains
unroutable.

**Activity — six kinds, all produced by transitions that already existed.**
`dispatched`, `completed`, `failed`, `restart_planned`, `interrupted`,
`peer_review`. The first three and `interrupted` are written **in the same
database transaction** as the `agent_instance` mutation they describe;
`restart_planned` and `peer_review` are standalone appends, because no state
transition happens at those points and inventing one to obtain coupling would
record a change that did not occur. `correlation_id` is propagated, never
minted: the scheduler carries the id that arrived on
`planning.task_graph.created`, and reconciliation reuses the exact id its
published `agent_os.task.completed` carries, storing `NULL` when no event is
published. All four peer-review verdicts are recorded, `not_required` and
`timed_out` included.

**Realtime — one public topic.** `agent_os.task.completed`, subscribed on the
bus as `agent_os.task.*` and named by the browser through exact-string
membership in `PUBLIC_TOPICS`. Browser → `ws-gateway` → Event Bus is the only
realtime path; the browser never connects to NATS. Registry and Supervisor RPC
subjects, `agent_os.health.snapshot`, and the legacy `agent.*` family are all
rejected from browser subscription.

**Frontend.** An `entities/agents.ts` model, the `agents/` panel, the
`/agents` route (lazily loaded, nested under the shell) and a navigation
entry. A completed task **refetches** the affected Agents queries rather than
patching them — the event payload carries `outcome` while the cache holds
`status`, and the mapping between them is the Kernel's own policy. No polling,
no optimistic mutation of shared cognitive state.

**Provider-free behaviour is the steady state, and the panel renders it as
healthy.** With no model provider configured, `agent_instance` is permanently
empty (§1.1 traces why), so the panel shows the installed packages and
explains that no agent has run yet. **AC-4's second and third clauses remain
Deferred by approval** — 4C.2 makes them *demonstrable the moment a provider
exists*, and does not make them met.

> **Addendum, 2026-09-11 — verified against real PostgreSQL, and what that
> found.** The paragraphs above were written on 2026-09-10, before any CI run
> with a real database existed. That run has since happened: **all 12
> `real-infra` jobs are green against head `1182816`**, the kernel's 50
> `real_infra` tests passing in a single pytest process alongside the Phase 3E
> real-Postgres acceptance E2E. **Two defects were exposed and fixed during
> that verification**, both invisible to every gate that can run without a
> database:
>
> 1. **Transaction ordering.** The same-transaction coupling described above
>    was correct as a design and broken as code — `agent_activity` has a
>    foreign key but no ORM `relationship()`, so SQLAlchemy emitted the child
>    INSERT before its parent and every coupled insert failed. Fixed in
>    `4eafa80` by flushing the instance inside the still-open transaction.
>    **Decision D-3 is unchanged**: still one transaction, one commit, one
>    logical operation.
> 2. **Test isolation.** The Phase 3E E2E commits permanently, by design, and
>    its rows were visible to the Kernel repository's unfiltered
>    `list_instances` tests. Fixed in `388c271` by giving that E2E its own
>    database. **`list_instances()` production behaviour is unchanged** and no
>    assertion was weakened.
>
> **No acceptance scope was reduced, silently or otherwise.** Everything §9.2
> describes as built is built, and the transaction property it asserts is now
> proven against a real database rather than inferred from source. AC-4's
> deferral is unchanged. Full record: [Gate Review §18](../../roadmap/architecture-reviews/phase-4c2-agents-surface-gate-review.md).

---

## 10. `agent-os` Docker and CI integration (D-5)

Phase 3E ratified its own condition **C-3** as a *deferred obligation*: no
Dockerfile, no `docker-compose.local.yml` service, no `build-and-scan.yml`
matrix entry, and therefore **no Trivy scan** for any of the four
`agent-os` components. The Gate Review justified the deferral criterion by
criterion — correctly, because no Phase 3E acceptance criterion required a
container.

**Phase 4 discharges it, because 4C's acceptance criterion does require
one.** `agent-os` must run under `docker compose up` for the Agents panel
to show anything real.

Work required in 4C:

1. A `Dockerfile` for `kernel`, `registry`, and `supervisors`. (`sdk/python` is a library — no Dockerfile, consistent with `packages/*`.)
2. Compose services for those three, joined to the existing network with the same Postgres/NATS dependencies the engines use.
3. Three new `build-and-scan.yml` matrix entries, which **also brings the first Trivy scan** these components have ever had.
4. Real-infra CI coverage already exists for `kernel` and `registry` and is unaffected.

**Known risk:** these components have never been containerized, and the
engine Dockerfiles required two separate `uv`-workspace fixes historically
(PR #4, PR #6). See **R-2**.

> **Implemented 2026-09-07 (milestone 4C.1). Four things this list did not
> name were required; recorded here rather than left as undocumented work.**
>
> 1. **`run-migrations.sh` — a fifth work item.** The script's own comment
>    stated the exclusion: *"agent-os/kernel and agent-os/registry are
>    deliberately absent: both have alembic configs, and neither has a service
>    in docker-compose.local.yml."* Adding the compose services removes that
>    premise. Without the corresponding `ENGINES` entries both containers would
>    start against a database with no `agent_os` schema and crash-loop — the
>    exact failure that script exists to prevent.
>    `agent-os/supervisors` stays out, and for a different reason: it has no
>    alembic config, no `postgres_dsn` and an empty `repository/` (TDD 3E §7).
>
> 2. **Item 3 understated the matrix change.** `build-and-scan.yml`'s matrix
>    was a flat list of names consumed as
>    `file: services/${{ matrix.service }}/Dockerfile`, so three entries could
>    not simply be appended — the path is now carried per entry.
>
> 3. **R-2 was correct, and the defect it predicted was real.**
>    `agent-os/kernel` imports `nova_agent_sdk` in `domain/ports.py`,
>    `domain/scheduler.py` and `domain/execution_backend.py` but never declared
>    it, so `uv sync --frozen --no-dev --package kernel` resolved without it
>    (`uv tree --package kernel --no-dev` returned zero matches) and the image
>    would have raised `ModuleNotFoundError` at startup. Invisible until this
>    component was first containerized, because the workspace-wide dev
>    environment installs everything. Declared in 4C.1; `uv.lock` changes by
>    two lines and no version moves.
>
> 4. **Both `kernel` and `registry` need `agents/` inside the image.**
>    `Settings.agents_root` defaults to `"agents"`, resolved against the
>    process CWD. For Registry the consequence is the quieter one:
>    `discover_agent_packages` returns `[]` for a missing directory rather than
>    raising, so the container would have started, passed its healthcheck, and
>    registered zero Agent Packages. Agent Packages are not workspace members
>    (doc 02 :162-169), so they are copied as plain files, after `uv sync` so
>    an Agent Package edit does not invalidate the dependency layer.
>
> Item 4 of the original list — *"Real-infra CI coverage already exists for
> `kernel` and `registry` and is unaffected"* — was verified and holds:
> `real-infra-checks.yml`'s matrix is unchanged by 4C.1.

---

## 11. Decisions D-1 … D-8 — approved status

All eight were proposed on 2026-09-01 and are **approved** except where
noted.

| ID | Decision | Status |
|---|---|---|
| **D-1** | **Reorder Phase 4 to start with the web UI and gateways; move `nova-companion` and Autonomy Level 2 to the final milestone (4F).** | **APPROVED** — 2026-09-01 |
| **D-2** | Relax `tools/scaffold-engine.py`'s `_NAME_PATTERN` to also accept a `-gateway` suffix, so both gateways can use the existing scaffold. Both belong under `services/` per doc 02 and are ordinary FastAPI services — unlike `agent-os/kernel`, which needed a different tool. | **APPROVED** — carried from [`3-P`](../phase-3/03-gateway-web-prerequisite.md) §2, where it was flagged and never actioned |
| **D-3** | **Phase-4-scoped session model**: a single long-lived local session token issued at first run, validated by `api-gateway` on every request, with no multi-user or RBAC concept. Grounded in **ADR-025** (single-trusted-user-per-instance). A disclosed, bounded departure from doc [13](../../architecture/13-auth-and-security.md)'s eventual OIDC design, **not a redesign of doc 13**. Full OIDC via a real `nova-auth` remains Phase 7. | **APPROVED** — carried from [`3-P`](../phase-3/03-gateway-web-prerequisite.md) §2 |
| **D-4** | `agent-os/kernel` gains a minimal read-only `/v1/agents` and `/v1/agents/{id}/activity`. **Explicit Phase 4 amendment to Phase 3E's health-only narrowing** (§9). | **APPROVED** — 2026-09-01 |
| **D-5** | Discharge Phase 3E condition **C-3**: containerize `agent-os`, add compose services and `build-and-scan` matrix entries (§10). | **APPROVED** — 2026-09-01 |
| **D-6** | Correct doc 11 §2 to match shipped paths; `api-gateway` forwards 1:1 with no rewriting (§8). | **APPROVED** |
| **D-7** | **A web application is the correct first UI.** Doc [05](../../architecture/05-desktop-architecture.md) §36-38 has Phase 5's Tauri desktop shell **reuse this same React application** — building web first is on the critical path to the desktop client, not a detour from it. A CLI would ship sooner but cannot satisfy doc 04 §4's living-interface requirement or render graphs and timelines. | **APPROVED** |
| **D-8** | Build all six 4B panels before advancing to 4C, rather than a subset. Each is small once the shell, `entities/` and `realtime/` exist; the marginal cost of the sixth is far below the cost of a second pass. | **APPROVED** |

**No decision in this list reverses a Phase 3 decision on the grounds that
it was wrong.** D-4 amends a Phase 3E narrowing because Phase 4 introduces
the first consumer that requires it; D-5 discharges an obligation Phase 3E
explicitly deferred rather than cancelled.

---

## 12. Risks R-1 … R-6 and mitigations

| ID | Risk | Severity | Mitigation |
|---|---|---|---|
| **R-1** | **Docker has been unavailable in the development environment throughout Phase 3** (`docker info` non-zero). Playwright E2E and full-stack local runs may not be executable locally at all. | **High** | CI must carry E2E as the authoritative signal. **A green local run must never be reported as equivalent** — this is precisely the C-1 pattern that Phase 3E had to correct. Every 4A–4F Gate Review states which evidence is local and which is CI. |
| **R-2** | `agent-os` has **never been containerized**. The first build may surface `uv`-workspace issues — the same defect class that broke engine Dockerfiles twice (PR #4, PR #6). | **Medium** | Containerize **early in 4C**, before the Agents panel depends on it. Treat a failed first build as expected, not as a blocker. |
| **R-3** | The **98 generated TypeScript contract types have never been compiled by any consumer.** They may not typecheck under a real `tsconfig`, or may reference types the generator does not emit. | **Medium** | **De-risk in step 1 of §7, before any application code.** A throwaway `tsconfig` + `tsc --noEmit` over all 98 files is a minutes-long check that de-risks the entire `entities/` layer. |
| **R-4** | **No TypeScript-aware CI exists.** `pr-checks.yml` runs `pnpm turbo run lint`/`test` but nothing type-checks or runs a browser. | **Medium** | Add `tsc --noEmit`, `vitest`, and a Playwright job in 4A. `apps/*` is already in the pnpm workspace, so the wiring is small. |
| **R-5** | **Scope creep.** Doc 04 names twelve panels; Phase 4 builds eleven *(corrected from "eight" 2026-09-08, decision 6 — see §6)*. Panels are individually cheap and collectively unbounded. | **Medium** | §6's table is the contract. `memory-timeline`, `knowledge-graph`, `world-model`, `personality`, `executive` are **Phase 5** and are named in §13's non-goals. |
| **R-6** | **Phase 4 as scoped is larger than Phase 3** — two gateways, one application, one design system, two new engines, and a Rust component. | **High** | The 4A–4F split exists for exactly this. Each milestone is independently shippable and independently valuable; work can stop after any one of them with a coherent system. |

---

## 13. Non-goals — explicitly out of scope for Phase 4

- **The desktop shell.** `apps/desktop-client` (Tauri) is Phase 5.
- **The five deferred panels** — `memory-timeline/`, `knowledge-graph/`, `world-model/`, `personality/`, `executive/` — Phase 5.
- **Full OIDC / PKCE via a real `nova-auth`** — Phase 7. D-3's session model is deliberately minimal.
- **Full RBAC and permission-derived subscription allow-lists** — depends on Phase 7's `nova-auth`. Phase 4's allow-list is a fixed, bounded list, not a policy engine.
- **Multi-user support of any kind.** ADR-025 governs.
- **Voice UI presentation** — waveform, listening/speaking indicators, wake-word UX polish are Phase 5. The voice *channel* already exists from Phase 2D-A/2D-B; Phase 4 neither builds nor visualizes it.
- **`@nova/ui` as a finished design system** — Phase 4 builds only what its eleven panels need *(corrected from "eight" 2026-09-08, decision 6 — see §6)*. Finalization, idle-state animation driven by real telemetry, and the full System Pulse treatment are Phase 5.
- **Mobile, third-party API access, marketplace features.**
- **Closing CF-4.** Phase 4 does not claim to convert Phase 3E's restart-resume or hot-load narrowings into full-path E2E proofs, even though the UI makes them more demonstrable.
- **Phase 5 work of any kind.**

---

## 14. Testing strategy

| Tier | Scope | Where it runs |
|---|---|---|
| **Unit** | `api-gateway` forwarding and rate-limit logic; `ws-gateway` allow-list construction; every panel's pure logic; `entities/` hooks against fixtures | Local + CI |
| **Contract** | Every `entities/` hook's types are imported from `nova-contracts` generated output — a panel cannot invent a payload shape | CI (`tsc --noEmit`) |
| **Integration** | A real WebSocket through `ws-gateway` receiving a real `communication.intent.*` event and reconciling into a real TanStack Query cache; a real REST round trip through `api-gateway` to `communication-engine` | Local + CI |
| **Real-infrastructure** | No new Postgres schema in 4A (Redis-backed rate-limit state only). 4C adds `agent-os` container coverage; 4D/4E/4F add per-engine real-Postgres tests following the established pattern | CI (`real-infra-checks.yml`) |
| **E2E (Playwright)** | The golden path per doc [16](../../architecture/16-testing-strategy.md) §125 — already the documented tool choice. 4A: open the client, hold a text conversation, see it rendered live. Each later milestone adds one golden path matching its acceptance criterion. | **CI is authoritative (R-1)** |
| **Security boundary** | A test proving a browser-originated connection cannot reach NATS except through `ws-gateway`, and that `/internal/*` is not routable through `api-gateway` — **AC-2 is proven by test, not by inspection** | CI |
| **Per-platform sensor** | Windows/macOS/Linux runners validating the `Sensor`/`Actuator` trait contract; permission-boundary tests asserting fail-closed behavior | 4F only |

---

## 15. CI requirements

Additive to the three existing workflows. **No existing job is modified in
a way that weakens it.**

| Workflow | Addition | Milestone |
|---|---|---|
| `pr-checks.yml` | `tsc --noEmit` across `apps/*` and `packages/nova-ui` | 4A |
| `pr-checks.yml` | `vitest` unit suite | 4A |
| `pr-checks.yml` | Playwright E2E job (own job — needs a browser and a running stack) | 4A |
| `build-and-scan.yml` | Matrix entries: `api-gateway`, `ws-gateway` | 4A |
| `build-and-scan.yml` | Matrix entries: `agent-os/kernel`, `agent-os/registry`, `agent-os/supervisors` — **first Trivy coverage these have ever had** (D-5) | 4C |
| `build-and-scan.yml` | Matrix entries: `autonomy-engine`, `cognitive-state-engine` | 4D, 4F |
| `real-infra-checks.yml` | Entries for the two new engines | 4D, 4F |
| `.importlinter` | Contracts for both gateways and both new engines | per milestone |

> **Additive correction, 2026-09-15 (Phase 4E; required by ratified TDD 4E
> §19.4).** The `real-infra-checks.yml` row assigns entries to *"the two new
> engines"* — 4D's `autonomy-engine` and 4F's `cognitive-state-engine`. **4E
> extends an existing engine rather than adding one**, so the row does not cover
> it, and §19.4 ratified that 4E must still have real-Postgres verification.
>
> **Two facts, both verified against the repository at `04eb77c` rather than
> assumed:**
>
> 1. **`digital-twin-engine` is already in the matrix**, added in Phase 2D-D. The
>    ratified requirement is therefore met by an entry that already exists; 4E
>    adds its new real-Postgres tests to the file that entry already runs, and
>    adds no matrix row. *(`.importlinter` is the same shape:
>    `nova_digital_twin_engine` is already in every contract, added when the
>    engine was scaffolded. Nothing to add there either.)*
> 2. **4E does add one `real-infra-checks.yml` row — `memory-engine` —** and it
>    is not a Digital Twin entry. `memory-engine` had **no real-Postgres coverage
>    at all**, which is how `PostgresMemoryRepository.create_long_term` shipped
>    without writing `created_at` or `updated_at`: the column defaults filled
>    them in, so every tier above the real driver saw a plausible timestamp while
>    the caller's own value was discarded. AC-6 is measured in that field (TDD 4E
>    §20.1), so the tier that can see it is now mandatory.
>
> **No existing job is weakened**, and `build-and-scan.yml` needs nothing:
> `digital-twin-engine` has been in that matrix since 2D-D.

`pnpm-workspace.yaml` already contains `apps/*`, and `pr-checks.yml`
already runs `pnpm turbo run lint`/`test`, so a correctly-configured
`apps/web-client` is picked up by existing CI with no workflow change —
only the TypeScript-aware steps above are genuinely new.

---

## 16. Phase 4 branch and PR workflow

Phase 4 uses a **long-lived integration branch** with a **strictly
sequential milestone chain**, deliberately different from Phase 3's shape.

```
main  (7e273e6, frozen for the duration of Phase 4)
 ↓
phase-4                          ← canonical Phase 4 integration branch
 ↓
phase-4a → implement → test → verify → PR → merge into phase-4 → verify phase-4
 ↓
phase-4b → implement → test → verify → PR → merge into phase-4 → verify phase-4
 ↓
phase-4c → …   phase-4d → …   phase-4e → …   phase-4f → …
 ↓
Phase 4 Gate Review → GO
 ↓
one final PR: phase-4 → main (merge commit)
```

**Rules, binding for the whole phase:**

1. `phase-4` is created from `main` at `7e273e62e942ecd5528ca807e65933d6bb675669` and is the single source of truth for all Phase 4 work.
2. **No Phase 4 work is developed directly on `main`.** `main` stays unchanged until final promotion.
3. Every milestone is developed on its own branch and lands via a PR **targeting `phase-4`**, never `main`.
4. **Milestone branches are created strictly one at a time.** `phase-4b` is not created until `phase-4a` is merged into `phase-4` and that merge is verified. The same applies to every subsequent milestone.
5. **Every milestone branches from the freshly merged `phase-4` HEAD** — never from an older snapshot. If 4A changes a file 4B later needs, 4B receives the exact final version by construction.
6. Each PR runs the CI and validation the milestone's code and architecture require, followed by **one comprehensive final audit before the PR is opened** — not continuous re-verification of every small change. Verification is proportional to the milestone.
7. After each merge, `phase-4` is verified to contain the complete milestone result and to be clean before the next branch is cut.
8. Phase 3 history is never modified.

**Why sequential, stated explicitly.** Phase 3 ran several branches and
several documentation states concurrently, and they had to be reconciled
afterwards — a cost paid repeatedly in audit passes near the end of the
phase. The sequential chain removes the possibility: at any moment there is
exactly one Phase 4 branch under development, and it starts from the
actual, verified state its predecessor produced. **No parallel branch ever
modifies the same file as another.**

**Phase 4 close-out sequence:**

1. Confirm `phase-4` contains the complete Phase 4 implementation.
2. Run the complete Phase 4 validation and CI suite against `phase-4`'s head.
3. Verify `phase-4` is internally consistent and production-ready.
4. Open **one** final PR, `phase-4` → `main`.
5. Merge only after the Phase 4 Gate Review records **GO**.
6. **Preserve full Phase 4 history with a merge commit** — not a squash — unless a later explicit decision changes this policy. Phase 3 established the precedent and the reason: project-health records and Gate Reviews cite individual commit SHAs, and a squash makes those citations unreachable.

**Known constraint.** Remote *branch deletion* is currently blocked by an
organization egress policy (HTTP 403 on ref deletion; ref creation and
updates work normally). Phase 4 feature branches will therefore accumulate
and require manual deletion. This is a known environmental limitation, not
a workflow defect, and must not be worked around.

---

## 17. Documents in this package

| Document | Contents | Status |
|---|---|---|
| `00-master-scope.md` (this document) | Phase 4 goal, acceptance criteria, milestones 4A–4F, carry-forwards, decisions D-1…D-8, risks R-1…R-6, non-goals, branch workflow | **Design preparation** |
| [`01-tdd-4a-gateways-and-web-client.md`](01-tdd-4a-gateways-and-web-client.md) | 4A technical design: gateway architecture, security boundaries, session model, web-client architecture, panel scope, testing, acceptance criteria | **Design preparation** |
| `02-tdd-4b-observability-panels.md` | 4B — not yet written | Planned |
| `03-tdd-4c-agent-os-api-and-containerization.md` | 4C — **never written; waived at Phase 4C closure, 2026-09-12** (see the note below) | **Waived, not owed** |
| [`04-tdd-4d-autonomy-engine.md`](04-tdd-4d-autonomy-engine.md) | 4D technical design: architecture and the binding gate order, Trust Engine inputs, Policy Engine, Permission Matrix, contracts, persistence, security boundaries, CF-9 handling, the panel, testing, acceptance criteria, and §0.1's two ratified refinements **D-4D-1** and **D-4D-2** | **Written 2026-09-12** (`eedb8ad`), corrected `f5ca915` |
| [`05-tdd-4e-digital-twin-extension.md`](05-tdd-4e-digital-twin-extension.md) | 4E technical design: Bible Part 16's eleven domains and which nine remain, the real Memory and Perception evidence sources, ownership boundaries, the `/v1/digital-twin/*` contracts, event and realtime behaviour, persistence, degraded semantics, the panel, testing, AC-6 mapping, and §0.1's findings plus the ratified decisions in §19 and §20 | **Written 2026-09-14; ratified 2026-09-14 (§19) and 2026-09-14 (§20.1, the AC-6 temporal-gap mechanism). Implemented on `phase-4e` from 2026-09-15.** §0.1.5 and §0.1.6 record two findings produced *during* implementation and their resolutions. *(This cell read "design preparation, **not ratified**; §19 must be answered before implementation" — correct until the ratifications.)* |
| [`06-tdd-4f-companion-and-cognitive-state.md`](06-tdd-4f-companion-and-cognitive-state.md) | 4F technical design: `nova-companion` and its ownership boundary, Sensor Abstraction Layer integration, normalization, enrichment and multi-modal fusion, the `cognitive-state-engine` (Active Thoughts, Focus, Attention Layers), the **five separable states of Autonomy Level 2**, the complete AC-8 path from trigger to execution, Event Bus and `PUBLIC_TOPICS` impact, persistence, transport, CI, testing, AC-7 and AC-8 mapping, milestone decomposition, and the ratified decisions D-4F-1 … D-4F-8 | **Written 2026-09-15 on the preparation branch `phase-4f-tdd`; RATIFIED 2026-09-15 (§19), not yet implemented.** All three blocking findings are resolved: **AC-7 is re-scoped from one second to five** with modality-neutral wording and the transactional outbox left unchanged (D-4F-1), **CF-9 is taken as an explicit 4F dependency** with its write surface in the owning `action-engine` (D-4F-2), and **`cognitive-state-engine` owns the initiative trigger** under eight prohibitions (D-4F-3). §20 records two non-blocking open questions. *(This cell read "4F — not yet written | Planned" until 2026-09-15, and "design preparation, NOT RATIFIED" until the ratification later the same day.)* ***Superseded 2026-09-16:*** "not yet implemented" was true when written and is preserved as written. **Slices 4F.1 and 4F.2 are now implemented and merged into `phase-4`** — `4605d649` and `5b5ebfd0` respectively, both normal two-parent merges. 4F.3–4F.8 remain unimplemented, so the TDD as a whole is still only partly built. This document's own §17 SLOC table is **not** reconciled by this slice closure; that is ledgered as L-5 in the [4F.2 completion record](../../roadmap/architecture-reviews/phase-4f2-workspace-perception-completion-record.md) §11 and settles at 4F closure.* |
| [`07-tdd-4f3-nova-companion.md`](07-tdd-4f3-nova-companion.md) | **4F.3 slice design**, subordinate to TDD 4F: the `nova-companion` Cargo workspace, the filesystem sensor and its two distinct halves (the Rust OS watcher and the Python `Sensor` registry entry), the intake client against 4F.2's existing route, the Dockerfile and the minimal Rust CI addition, plus scope and non-goals, acceptance criteria, test strategy, security/privacy and observability boundaries, SLOC, and the deferred obligations it settles | **Written 2026-09-16 on the preparation branch `phase-4f3-tdd`; RATIFIED 2026-09-16 (§20).** All four decisions are recorded as **D-4F3-1 … D-4F3-4**: the Rust/Python sensor split is intentional and the registry entry required; `perception-engine` is the **single** path-hashing authority, with the security requirement stated over persisted/outbox/event outputs rather than the wire; consent is a **policy boundary, not a new implementation** — no consent subsystem is added, the watcher is bound to an explicitly configured directory only, and the gap is carried as **L-14**; and the Dockerfile runtime-hardening guard is **generalized structurally for multiple runtime families**, never bypassed or weakened. *(This cell read "NOT RATIFIED. §20 records four questions that must be answered before implementation" until the ratification.)* Declares **no new Event Bus subject, no `PUBLIC_TOPICS` change, no gateway change, no migration and no ORM model** |
| [`09-tdd-4f5-autonomy-level-2.md`](09-tdd-4f5-autonomy-level-2.md) | **4F.5 slice design**, subordinate to TDD 4F: Autonomy Level 2's five separable states and which three this slice owns (selectable, policy-permitted, executing — **not** the trigger, which is CF-11 and 4F.6's), the single dispatch point that makes AC-8's *"no code path differs"* literally true, `action.execute` acquiring its first producer as a **request/reply RPC** on an existing contract, and the disclosed retirement of 4D's control 8 in favour of the tighter *"publishes `action.execute` and nothing else"*. Declares **no new Event Bus subject, no `PUBLIC_TOPICS` change, no gateway change, no new REST route, no migration and no ORM model** — the `autonomy` schema has **zero CHECK constraints** and stores `policy.effect` and `decision_log.outcome` as `TEXT`, so a new policy effect and a newly-reachable `EXECUTE` outcome both persist unchanged. Records that **Digital Twin, Memory and Perception are read by nothing in this slice**. | **Written 2026-09-20 on the preparation branch `phase-4f5-tdd`; NOT RATIFIED.** §20 records **four** questions that must be answered before implementation: **A-4F5-1** how a policy may lower `requires_approval` without making an empty policy set permissive (the current `PolicyEvaluation.requires_approval` defaults to `False`, and `evaluate_gates` discards it — wiring it through as-is would be **fail-open**); **A-4F5-2** where `action.execute`'s mandatory `action_type`/`execution_target`/`verification_method` come from, given `DecisionRequest` carries none of them and `PermissionCategory`→`ActionType` is ten-to-two; **A-4F5-3** whether `decide()` awaits the RPC reply and with what timeout, given `action-engine`'s approval loop defaults to 300s; and **A-4F5-4** whether `permits_execution` becomes level-aware and what replaces `_forbid_execution` as §16 control 3's target. **CF-9, CF-10 and CF-11 all stay OPEN**, and this slice contributes closure evidence to none of them |

Each later TDD is written immediately before its milestone begins, not up
front — the same cadence Phase 3 used, which let each TDD incorporate what
the previous milestone actually revealed.

> **`03-tdd-4c-…` waived at Phase 4C closure, 2026-09-12.** Phase 4C shipped
> without it. The row is settled as a **waiver** rather than left reading
> "Planned", because Phase 4C is now complete and merged (`phase-4` head
> `b1d7ca5`) and a document written *after* the milestone it was meant to
> design cannot serve its stated purpose — *"written immediately before its
> milestone begins"*, so that it can incorporate what the previous milestone
> revealed. Writing one now would be a retrospective narrative, not a
> technical design, and this package does not manufacture those.
>
> **What carried the design load instead**, and why the waiver is recorded
> rather than treated as a gap to backfill: §9 and §9.1 hold decision **D-4**
> and the ratified third route; §9.2 records the surface as built; §10 holds
> the containerization design (**D-5**); §5's dated implementation notes record
> 4C.1's scope; and the
> [Phase 4C.2 Gate Review](../../roadmap/architecture-reviews/phase-4c2-agents-surface-gate-review.md)
> holds the decisions, tradeoffs, limitations, verification and acceptance
> assessment a TDD would otherwise carry forward. Between them the milestone is
> fully specified in this repository — it simply is not specified in one file
> named `03-…`.
>
> **This waiver settles the row; it does not set a precedent.** `04-tdd-4d-…`
> remains **Planned and owed**, to be written immediately before `phase-4d` is
> cut, per the cadence above. **`02-tdd-4b-…` is untouched here** — 4B's row is
> Phase 4B's to settle, not 4C's, and nothing in this pass changes it.
