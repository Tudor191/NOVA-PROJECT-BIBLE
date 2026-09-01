# TDD 4A — `api-gateway`, `ws-gateway`, `@nova/ui`, and the
## `apps/web-client` Shell + Conversation Panel

**Status: design complete pending approval. No production code
authorized.**

Milestone 4A of [Phase 4](00-master-scope.md). This TDD **executes**
[`3-P` — Gateway & Web-Client Prerequisite](../phase-3/03-gateway-web-prerequisite.md),
which was designed in Phase 3 and never authorized for code. Sections
carried forward from `3-P` are marked as such; this document records what
Phase 4 changes, adds, or makes concrete.

---

## 0. Scope and dependencies

**In scope.** `services/api-gateway`, `services/ws-gateway`,
`packages/nova-ui` (minimum viable), `apps/web-client` (shell, `entities/`,
`realtime/`, the Conversation panel, the presence/identity indicator, the
System Pulse), and the Phase-4-scoped session model.

**Depends on: nothing new.** Every backend 4A talks to shipped in Phase 2D
and is Gate-Reviewed: `communication-engine`, `personality-engine`,
`perception-engine`, `world-model-engine`. **Zero dependency on 3A–3E** —
which is why 4A is first.

**Satisfies:** Phase 4 **AC-1** and **AC-2**.

---

## 1. Existing capability vs. what is being built

| Capability | Today | After 4A |
|---|---|---|
| External API surface | None — engines expose `/v1` directly, nothing fronts them | `api-gateway` fronts `communication-engine`; the pattern for all others is proven |
| Browser access to bus events | None; no browser client exists | `ws-gateway` bridges a bounded allow-list |
| TypeScript contract types | **98 generated files, zero consumers** | `entities/` is the first consumer in the project's history |
| Web client | **No `apps/`, zero `.tsx` files** | Shell + one working panel |
| Session auth | None | Single local session token (§4) |
| Design system | `@nova/ui` named in docs, does not exist | Minimum viable package |

---

## 2. `api-gateway` — design

**Role**, per doc [11](../../architecture/11-api-architecture.md) §1
(already authoritative, not phase-specific): *"The one stable, versioned,
documented surface the outside world … talks to … enforces auth, rate
limiting, and request shaping before forwarding to the appropriate engine
or, more commonly, publishing an event."* **The frontend never calls any
engine directly.**

### 2.1 REST forwarding

Forwards **1:1, with no path rewriting**, to each engine's already-built
`/v1` surface. This is decision **D-6** ([master scope](00-master-scope.md)
§8): doc 11 §2's documented paths diverge from the shipped paths, and the
resolution is to correct the document rather than build a translation
layer that would drift.

4A wires **one** engine end-to-end:

```
/v1/communication/sessions        → communication-engine
/v1/communication/notifications   → communication-engine
```

4B widens this to `planning-engine`, `reasoning-engine`,
`capability-engine`, `action-engine`; 4C to `agent-os/kernel`. **No
gateway redesign is required for any of them** — only configuration.

### 2.2 Response envelope

Every response conforms to doc 11 §4:

```json
{ "data": {...}, "meta": { "confidence": 0.87, "correlation_id": "...", "generated_at": "..." }, "error": null }
```

The gateway **does not synthesize** `confidence` — it passes through what
the engine reports, and omits the field when the engine does not report
one. Inventing a confidence value would corrupt the exact signal doc 11 §4
exists to preserve.

### 2.3 Rate limiting

Redis-backed token bucket per `(session, endpoint class)`, classes `read` /
`write` / `expensive-reasoning` per doc 11 §5. **Redis already exists in
`docker-compose.local.yml`** — no new infrastructure dependency. The
gateway is otherwise stateless: **no new Postgres schema in 4A.**

### 2.4 Scaffolding gap — carried from `3-P` §2

`tools/scaffold-engine.py:28` defines:

```python
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*-engine$")
```

Neither `api-gateway` nor `ws-gateway` ends in `-engine`, so **neither can
use the existing scaffold tool** — the same class of gap TDD 3E hit with
`agent-os/kernel`.

Unlike `agent-os`, both gateways *do* belong under `services/` per doc
[02](../../architecture/02-repository-and-folder-structure.md) and are
ordinary FastAPI services — they are simply not domain "engines". The
generated skeleton (FastAPI app, health endpoints, Dockerfile) is exactly
what both need.

**Decision D-2 (approved): relax `_NAME_PATTERN` to also accept a
`-gateway` suffix.** This was recommended in `3-P` §2 and never actioned.
The tool's existing tests are extended, not replaced.

---

## 3. `ws-gateway` — design

**Role**, per doc [09](../../architecture/09-event-bus-architecture.md) §6
(already authoritative): *"The only component allowed to bridge bus
subjects to a browser/desktop client … it only ever receives
already-finalized `communication.*` events plus read-only telemetry, never
raw internal engine chatter."*

**This is the load-bearing security property of 4A, and AC-2 requires it to
be proven by test rather than asserted by inspection.**

### 3.1 Transport

WebSocket primary, SSE fallback (doc 01 §6, doc 04 §3). Forwards to the
browser's `realtime/` client, which reconciles **directly into the TanStack
Query cache** via `queryClient.setQueryData`. **No polling anywhere in the
application.**

### 3.2 Subscription allow-list — bounded and explicit

4A's allow-list is a **fixed list, not a policy engine**:

| Subject prefix | Purpose | Milestone |
|---|---|---|
| `communication.*` | Conversation panel | **4A** |
| `personality.*` (read-only telemetry) | Presence indicator | **4A** |
| `perception.*` (read-only telemetry) | Presence indicator | **4A** |
| `nova.heartbeat` | System Pulse | **4A** |
| `planning.task_graph.*` | Planning panel | 4B |
| `action.*` | Approvals panel | 4B |
| `agent.*`, `agent_os.*` | Agents panel | 4C |
| `autonomy.*` | Autonomy panel | 4D |

Each later milestone **extends the allow-list only** — the bridging
mechanism itself is never redesigned. Under **ADR-025** and D-3, the
"permission-derived allow-list" doc 09 §6 eventually describes simplifies
to "this instance's one trusted user's subjects." Full RBAC-scoped
allow-lists depend on Phase 7's `nova-auth` and are a stated non-goal.

### 3.3 What is deliberately not bridged

Raw inter-engine RPC subjects, `/internal/*` traffic, and any subject not
on the list above. **A subject absent from the allow-list is not
forwarded**, and the gateway fails closed on an unknown subject rather than
defaulting to forward.

---

## 4. Session authentication model (D-3)

Doc [13](../../architecture/13-auth-and-security.md) §2 specifies an
Ed25519 device keypair unlocked by OS-native biometrics, and §3 specifies
OIDC Authorization Code + PKCE terminating at the API Gateway for
enterprise mode. Both are behind a `packages/nova-auth` interface.

**`nova-auth` does not exist** — confirmed: no `services/nova-auth`, no
`packages/nova-auth`, only a placeholder comment in `nova-core`'s
`boot.py`. Full OIDC is a **Phase 7** deliverable. Building a real identity
provider now would be scope creep far beyond this milestone.

### 4.1 Approved Phase-4-scoped mechanism

Grounded in **ADR-025** (*single-trusted-user-per-instance deployment
assumption*, confirmed still governing and unchanged through Phase 3):

- A **single long-lived local session token**, generated at first run and stored in the instance's local configuration.
- Delivered to the browser as an **httpOnly cookie**, per doc 04 §5's `useSession()` row.
- Validated by `api-gateway` on **every** request and by `ws-gateway` at connection establishment.
- **No multi-user concept. No RBAC. No external identity provider. No refresh-token rotation.**

### 4.2 What this is, and is not

This is *"ship a real but intentionally minimal instance"* applied to auth
exactly as Phase 3 applied it to sandboxing (3C) and execution backends
(3E). It is a **disclosed, bounded departure from doc 13's eventual
design, scoped to the single-user assumption — not a redesign of doc 13**,
which is left intact and remains the Phase 7 target.

It is **not a security regression**: no web client exists today, so there
is no prior posture being weakened. It *is* a real boundary — without it,
the gateways would be unauthenticated.

**Upgrade path.** `api-gateway` validates sessions behind a single
`SessionValidator` interface, so Phase 7 replaces the implementation
without touching any route handler.

---

## 5. `apps/web-client` — architecture

**Doc [04](../../architecture/04-frontend-architecture.md) §2 is
implemented verbatim. It is not redesigned.**

```
apps/web-client/
├── src/
│   ├── app/          # Routing (TanStack Router), layout shell, System Pulse
│   ├── panels/
│   │   └── conversation/    # the only panel built in 4A
│   ├── entities/     # typed data-layer hooks per domain entity (from nova-contracts)
│   ├── realtime/     # WebSocket client, event → cache reconciliation
│   ├── shared/
│   └── main.tsx
└── tests/
    ├── unit/         # vitest
    └── e2e/          # Playwright
```

### 5.1 Stack — already decided, not an open choice

Per **Fork E4**, resolved in
[`01-tdd-preparation-and-fork-resolutions.md`](../phase-3/01-tdd-preparation-and-fork-resolutions.md)
§2 and restated in `3-P` §4: **React 18, TypeScript 5, Vite, TanStack
Router, TanStack Query, Zustand, React Hook Form + zod, Framer Motion,
D3.js, Tailwind CSS + `@nova/ui`.** No substitution is proposed or
permitted by this TDD.

### 5.2 Data flow

```
Event Bus ──allow-listed──> ws-gateway ──WebSocket──> realtime/
                                                         │
                                          queryClient.setQueryData
                                                         ▼
panels/* <──────────────────── TanStack Query cache
   │
   └─user action─> api-gateway ─> engine /v1 ─> publishes events ──┐
                                                                    └─> back around
```

Four binding properties:

1. **Reads are pushed, never polled.**
2. **Writes never mutate optimistically** for anything affecting shared cognitive state (doc 04 §3) — the UI must never display a belief NOVA does not hold. Local composer text is ephemeral UI state and is exempt.
3. **`entities/` imports its types from `nova-contracts` generated output.** A panel cannot invent a payload shape. This is what makes the client architecturally coupled to the system rather than bolted onto it.
4. **The envelope is rendered, not hidden.** `meta.confidence` and `meta.correlation_id` appear in the UI chrome — Part 8's Confidence System and Part 19's Explainability made visible, and what turns the client into a debugging instrument rather than a chat window.

### 5.3 State management, per doc 04 §5

| Category | Tool |
|---|---|
| Server/shared cognitive state | TanStack Query, hydrated by `realtime/` |
| Ephemeral UI state | Zustand |
| Form/input state | React Hook Form + zod |
| Auth/session | `useSession()` backed by the httpOnly cookie (§4) |

### 5.4 First consumer of a zero-consumer pipeline

`packages/nova-contracts/typescript/` contains **98 generated `.ts` files**
and has **zero consumers repository-wide**. `entities/` is the first code
in this project to import from it.

**This is R-3, and it is de-risked before any application code is
written:** step 1 of the implementation order compiles all 98 files under a
real `tsconfig` with `tsc --noEmit`. If the generator emits types that do
not typecheck, that is discovered in minutes rather than after `entities/`
is built on top of them.

---

## 6. Panel scope for 4A

**One panel: `conversation/`.** Plus two shell-level components.

| Surface | Source | Notes |
|---|---|---|
| Conversation panel | `communication-engine` — REST via `api-gateway`, live turns via `ws-gateway` | Text only. Voice is Phase 5 presentation work; the channel already exists |
| Presence/identity indicator | `perception-engine` / `world-model-engine` `present_identities` | Shell-level, always visible |
| System Pulse | `nova.heartbeat` | Shell header, always visible, per doc 04 §4 |

Doc 04 §4 requires idle state driven by **real background-engine
telemetry** — Part 6 is explicit: *"never generate fake animations."* The
System Pulse binds to the real heartbeat or it renders a disconnected
state. It never animates decoratively.

Every other panel is 4B or later, per [master scope](00-master-scope.md) §6.

---

## 7. Failure and degraded behavior

Carried from `3-P` §7, extended.

| Condition | Behavior |
|---|---|
| `ws-gateway` connection drops | `realtime/` reconnects with exponential backoff. The Query cache is **not cleared, only marked stale** — no flash-of-empty-state on a transient drop. Connection state is visible in the shell |
| An engine behind `api-gateway` is unavailable | The gateway returns a **structured error, never a silent empty success**. The frontend surfaces the failure — consistent with this project's standing "never silence, always disclose degradation" discipline |
| Session token expired or invalid | `api-gateway` rejects with 401; the frontend re-runs the first-run session flow (§4). **No silent re-auth against a nonexistent OIDC provider** |
| Rate limit exceeded | 429 with a structured retry hint; the panel surfaces it rather than retrying invisibly |
| An event arrives for an unknown subject | `ws-gateway` **fails closed** and does not forward it |
| Generated contract type mismatch at runtime | The `entities/` hook surfaces a parse error rather than rendering partial data |

---

## 8. Observability

Carried from `3-P` §8.

- `gateway_rest_request_total{engine, status}`, `gateway_rest_request_duration_ms` (histogram) — `api-gateway`.
- `gateway_ws_connections_active`, `gateway_ws_messages_forwarded_total{subject_prefix}` — `ws-gateway`.
- `gateway_ws_messages_rejected_total{reason}` — **added by this TDD.** A subject rejected by the allow-list is a security-relevant event and must be countable, not silent.
- Standard `/internal/health`, `/internal/readiness`, `/internal/metrics` via `nova-service-kit` for both gateways.

---

## 9. Security boundaries

1. **`ws-gateway` is the only component that may bridge bus subjects to a browser** (doc 09 §6). 4A *implements* this property; it does not merely document it.
2. **`/internal/*` is never routable through `api-gateway`** (doc 11 §3). There must be no network path from the browser to an engine's internal RPC surface.
3. **The frontend never calls an engine directly** (doc 11 §1).
4. The session model (§4) is a disclosed scope reduction of doc 13, not a weakening of an existing posture.

**AC-2 requires 1 and 2 to be proven by an executable test** — a test that
attempts direct NATS access and an `/internal/*` fetch from the client
context and asserts both fail. Inspection is not sufficient evidence.

---

## 10. Testing strategy

| Tier | Content |
|---|---|
| **Unit** | `api-gateway` forwarding, envelope construction, rate-limit bucket logic; `ws-gateway` allow-list construction and fail-closed behavior; `realtime/` reconciliation reducers; Conversation panel logic |
| **Contract** | `tsc --noEmit` over all 98 generated types plus every `entities/` hook — a panel cannot compile against an invented shape |
| **Integration** | A real WebSocket through `ws-gateway` receiving a real `communication.intent.*` event and reconciling into a real TanStack Query cache; a real REST round trip through `api-gateway` to `communication-engine`'s `/v1/communication/...` |
| **Security boundary** | The two AC-2 tests in §9 |
| **Real-infrastructure** | None new — 4A adds no Postgres schema. Redis-backed rate-limit state only. `communication-engine`'s existing real-infra coverage is unchanged (note **CF-6**: its repository-layer real-Postgres verification remains an open carry-forward and 4A does **not** claim to close it) |
| **E2E (Playwright)** | **The golden path: open the web client, authenticate, hold a live text conversation, see it rendered.** This is `3-P` §11 criterion 1 and Phase 4 **AC-1** — the "first real UI" acceptance criterion Phase 2D set and never delivered |

**R-1 governs how E2E evidence is reported.** Docker has been unavailable
in the development environment throughout Phase 3, so Playwright may not be
runnable locally. **CI is the authoritative signal, and a green local run
must never be reported as equivalent** — this is precisely the pattern
Phase 3E's condition C-1 existed to correct.

---

## 11. CI requirements

| Workflow | Addition |
|---|---|
| `pr-checks.yml` | `tsc --noEmit` across `apps/*` and `packages/nova-ui` |
| `pr-checks.yml` | `vitest` unit suite |
| `pr-checks.yml` | Playwright E2E as its **own job** — it needs a browser and a running stack, and must not be able to mask a unit-suite failure |
| `build-and-scan.yml` | Matrix entries for `api-gateway` and `ws-gateway` |
| `.importlinter` | Contracts for both gateways |

`pnpm-workspace.yaml` **already contains `apps/*`**, and `pr-checks.yml`
already runs `pnpm turbo run lint` and `pnpm turbo run test` — a correctly
configured `apps/web-client` is picked up by the existing pipeline with no
workflow change. Only the TypeScript-aware and browser steps above are
genuinely new. **This is R-4's mitigation.**

---

## 12. Acceptance criteria for 4A

1. A user opens the web client, authenticates via the §4 session mechanism, and holds a **live text conversation** rendered through the Conversation panel, verified by a Playwright E2E run **in CI**. *(Phase 4 AC-1; `3-P` §11 criterion 1.)*
2. `ws-gateway` is **provably** the only path a browser-originated connection can use to observe bus activity, verified by the §9 tests — not by inspection. *(Phase 4 AC-2.)*
3. `/internal/*` is not routable through `api-gateway`, verified by test.
4. `entities/` imports generated types from `nova-contracts`, and `tsc --noEmit` passes over all 98 generated files.
5. The presence/identity indicator and System Pulse render from **real** telemetry; neither animates when its source is disconnected.
6. `api-gateway` returns a structured error, never a silent empty success, when `communication-engine` is unavailable — verified by test.
7. All required GitHub Actions Check Runs are green against the exact reviewed head SHA. **Local-only evidence does not satisfy this criterion.**

---

## 13. Non-goals for 4A

- **Every panel except `conversation/`.** The six 4B panels, `agents/` (4C), `autonomy/` (4D), `digital-twin/` (4E), `cognitive-state/` (4F), and the five Phase 5 panels are all out of scope.
- **Voice UI.** The channel exists from Phase 2D-A/2D-B; its visual presentation is Phase 5.
- **Full OIDC / PKCE / `nova-auth`** — Phase 7.
- **RBAC, multi-user, permission-derived allow-lists** — Phase 7.
- **The Tauri desktop shell** — Phase 5, and it reuses this same React application (doc 05).
- **`@nova/ui` as a finished design system** — 4A builds only what the shell and one panel require.
- **Any change to an engine's own `/v1` surface.** 4A fronts what exists; it does not modify it.
- **`agent-os` work of any kind** — that is 4C.

---

## 14. Approval status of items affecting Phase 3 artifacts

Three of the four items below edit or depart from something Phase 3
ratified, and each was flagged for explicit approval. **All three were
approved on 2026-09-01.**

| # | Item | Status |
|---|---|---|
| 1 | **D-2** — relax `tools/scaffold-engine.py`'s `_NAME_PATTERN` to accept a `-gateway` suffix. Modifies a Phase 3 tool. | **APPROVED — 2026-09-01.** Flagged in [`3-P`](../phase-3/03-gateway-web-prerequisite.md) §2 and never actioned; the alternative was hand-scaffolding both services |
| 2 | **D-3** — the Phase-4-scoped session model (§4). A disclosed, bounded departure from doc [13](../../architecture/13-auth-and-security.md)'s eventual OIDC design. | **APPROVED — 2026-09-01.** Scoped to ADR-025's single-user assumption, reversible behind a `SessionValidator` interface, superseded by Phase 7 |
| 3 | **D-6** — correct doc [11](../../architecture/11-api-architecture.md) §2 to match shipped paths rather than rewriting paths in the gateway (see [master scope](00-master-scope.md) §8). Edits an authoritative architecture document. | **APPROVED — 2026-09-01.** Five real divergences found; the shipped names are the more consistent set, and a mapping layer would drift permanently |
| 4 | Doc [04](../../architecture/04-frontend-architecture.md) §2's panel list gains `capabilities/`, `approvals/`, `events/`, `cognitive-state/`. Doc 04 predates the Phase 3 engines that motivate them. | **Deferred to 4B**, where those panels are built. Amended **additively**, preserving the original list per the documentation protocol |

None of these is a Phase 3 correction. Each is a Phase 4 extension of a
decision that was correct on the evidence available when it was made.
