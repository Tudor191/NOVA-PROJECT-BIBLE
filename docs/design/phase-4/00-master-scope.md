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
| **AC-4** | `agent-os` runs as containers under `docker compose up`, and the Agents panel renders live agent instances, supervisor structure, and at least one real peer-review round. | 4C |
| **AC-5** | An autonomous suggestion at Autonomy Level 1 is **proposed, not executed**, is visible in the Autonomy panel, and executing it requires explicit user approval. | 4D |
| **AC-6** | The Digital Twin's project model correctly reconstructs "what was I doing on Project X" after a simulated multi-week gap, and the reconstruction is visible in the Digital Twin panel. | 4E |
| **AC-7** | Opening a known project in the IDE is detected and reflected in the World Model within one second with no user action, and revoking a sensor's OS permission immediately and visibly stops that perception stream in the UI. | 4F |
| **AC-8** | The same action category that is blocked at Level 1 auto-executes at Level 2 for a low-risk case, purely by policy — no code path differs. | 4F |

**AC-1 through AC-4 do not depend on any new engine.** They depend only on
surfacing what Phase 3 already built.

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
| **CF-2** | `GET /v1/agents` and `GET /v1/agents/{id}/activity` are named in doc [11](../../architecture/11-api-architecture.md) §2 but unbuilt, and explicitly *"an open `3-P` prerequisite with no owning TDD"* | [`3-P`](../phase-3/03-gateway-web-prerequisite.md) §5 | **Blocks the Agents panel** | **Resolved by 4C via D-4** |
| **CF-3** | Phase 3E condition **C-3**, ratified as a *deferred obligation*: `agent-os` has no Dockerfile, no compose service, no `build-and-scan` matrix entry, and therefore no Trivy scan | [Phase 3E Gate Review](../../roadmap/architecture-reviews/phase-3e-agent-os-gate-review.md) §10; [`phase-3e.md`](../../project-health/phase-3e.md) field 20(b) | **`agent-os` cannot run under `docker compose up`** — blocks any live agent panel | **Discharged by 4C via D-5** |
| **CF-4** | Phase 3E narrowings: restart-resume (AC-2) and hot-load (AC-3) are proven at unit + integration + real-Postgres level, **not by a full-path E2E**; hot-load is version *pinning*, not concurrent execution of two bytecode versions | [16-3e-hot-load-design-decision.md](../phase-3/16-3e-hot-load-design-decision.md) | A UI makes both newly demonstrable | **Opportunity, not a blocker.** Phase 4 does not claim to close them |
| **CF-5** | `PHR-1` / `PHR-2` — pre-existing Phase-1 defects, reported and not fixed | Project Health Review 2026-08-29 | None direct | **Carried forward unchanged** |
| **CF-6** | Real-Postgres verification of `personality-engine`, `communication-engine`, `perception-engine` repository layers still pending | Open task | 4A's Conversation panel exercises `communication-engine` | **Flagged.** 4A's real-infra job covers it incidentally; not claimed as closure |
| **CF-7** | **Doc 11 §2's documented paths diverge from the paths actually implemented** — see §8 | doc [11](../../architecture/11-api-architecture.md) §2 vs. code | `api-gateway` must forward *somewhere* | **Resolved by D-6** |
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

### 4C — Agent Activity

Discharges **CF-3** by containerizing all four `agent-os` components and
adding them to `docker-compose.local.yml` and the `build-and-scan.yml`
matrix. Closes **CF-2** by adding a minimal read-only `/v1` surface to
`agent-os/kernel` (§9). Adds the **Agents** panel: registered packages,
live instances, supervisor tree, per-instance activity, peer-review rounds.

**Depends on:** 4B, D-4, D-5. **Satisfies:** AC-4.

### 4D — Autonomy

`services/autonomy-engine`: Autonomy Levels 0–2 defined, **Levels 0–1
enabled** (Observation Only → Suggestive; no auto-execution), Trust Engine,
Policy Engine, Permission Matrix. The Trust Engine consumes Phase 2D-D's
conversational trust-development signal as one input rather than
re-deriving an unrelated one. Adds the **Autonomy** panel: level selector,
trust score, policy editor, suggestion inbox.

**Depends on:** 4C. **Satisfies:** AC-5.

### 4E — Digital Twin

`digital-twin-engine` **extension** — the remaining nine of Bible Part 16's
eleven domains (goal model, project model, software/hardware environment,
skill model, knowledge profile, productivity patterns, learning progress),
populated from real Perception + Memory data for the first time, additive
to the Communication Profile domain shipped in Phase 2D-D. Adds the
**Digital Twin** panel.

**Depends on:** 4D. **Satisfies:** AC-6.

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
panels. Phase 4 builds **eight**. The scope line is explicit so it cannot
drift.

| Panel | Milestone | Primary source |
|---|---|---|
| `conversation/` | **4A** | `communication-engine` |
| `system/` | **4B** | `GET /v1/system/health`, `nova.heartbeat` |
| `planning/` | **4B** | `planning-engine` `/v1/plans`, `planning.task_graph.*` |
| `reasoning/` | **4B** | `reasoning-engine` `/v1/reasoning`, `/v1/reasoning/decisions` |
| `capabilities/` | **4B** | `capability-engine` `/v1/capabilities` |
| `approvals/` | **4B** | `action-engine` `/v1/action/approvals/{id}/decide` |
| `events/` | **4B** | `ws-gateway` raw allow-listed stream |
| `agents/` | **4C** | `agent-os/kernel` `/v1/agents` (D-4), `agent.*`/`agent_os.*` |
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
| **R-5** | **Scope creep.** Doc 04 names twelve panels; Phase 4 builds eight. Panels are individually cheap and collectively unbounded. | **Medium** | §6's table is the contract. `memory-timeline`, `knowledge-graph`, `world-model`, `personality`, `executive` are **Phase 5** and are named in §13's non-goals. |
| **R-6** | **Phase 4 as scoped is larger than Phase 3** — two gateways, one application, one design system, two new engines, and a Rust component. | **High** | The 4A–4F split exists for exactly this. Each milestone is independently shippable and independently valuable; work can stop after any one of them with a coherent system. |

---

## 13. Non-goals — explicitly out of scope for Phase 4

- **The desktop shell.** `apps/desktop-client` (Tauri) is Phase 5.
- **The five deferred panels** — `memory-timeline/`, `knowledge-graph/`, `world-model/`, `personality/`, `executive/` — Phase 5.
- **Full OIDC / PKCE via a real `nova-auth`** — Phase 7. D-3's session model is deliberately minimal.
- **Full RBAC and permission-derived subscription allow-lists** — depends on Phase 7's `nova-auth`. Phase 4's allow-list is a fixed, bounded list, not a policy engine.
- **Multi-user support of any kind.** ADR-025 governs.
- **Voice UI presentation** — waveform, listening/speaking indicators, wake-word UX polish are Phase 5. The voice *channel* already exists from Phase 2D-A/2D-B; Phase 4 neither builds nor visualizes it.
- **`@nova/ui` as a finished design system** — Phase 4 builds only what its eight panels need. Finalization, idle-state animation driven by real telemetry, and the full System Pulse treatment are Phase 5.
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
| `03-tdd-4c-agent-os-api-and-containerization.md` | 4C — not yet written | Planned |
| `04-tdd-4d-autonomy-engine.md` | 4D — not yet written | Planned |
| `05-tdd-4e-digital-twin-extension.md` | 4E — not yet written | Planned |
| `06-tdd-4f-companion-and-cognitive-state.md` | 4F — not yet written | Planned |

Each later TDD is written immediately before its milestone begins, not up
front — the same cadence Phase 3 used, which let each TDD incorporate what
the previous milestone actually revealed.
