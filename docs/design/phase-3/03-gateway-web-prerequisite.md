# `3-P` — Gateway & Web-Client Prerequisite

**Status: design only, awaiting approval. No production code authorized.**
Not Phase 2E (user decision) — a bounded, explicitly-scoped prerequisite
slice inside Phase 3, per `02-master-scope.md` §1.2.

---

## 0. Scope and dependencies

**`3-P.1` scope.** `api-gateway`, `ws-gateway`, the base `apps/web-client`
shell, the Conversation panel, and a presence/identity indicator.
**Depends only on Phase 2D-D being closed** — every backend it talks to
(`communication-engine`, `personality-engine`, `perception-engine`)
already exists and is already Gate-Reviewed. Zero dependency on `3A`-`3E`.

**`3-P.2` scope.** The Planning panel (depends on `3B`) and the Agent
Activity panel (depends on `3E`) — additive to `3-P.1`'s already-working
shell. Can ship independently of each other, whenever their respective
engine TDD completes. **Also additive, corrected during the Phase 3C
reconciliation pass to match what §2/§5 already state:**
`api-gateway`'s REST-forwarding automatically covers `capability-engine`'s
(`3C`) stopgap `/v1/capabilities` surface once `3C` ships — this is
endpoint-fronting only, not a dedicated web-client panel, since Phase 3
ships no capability panel (`docs/design/phase-3/06-tdd-3c-capability-engine.md` §14
Non-goals — no Visual Capability Center in Phase 3). This addition was
previously omitted from this scope statement even though §2/§5 already
described it, an internal inconsistency this pass corrects.

---

## 1. Why this gap exists (recap, full detail in `01-tdd-preparation-and-fork-resolutions.md` §11)

`api-gateway` + `ws-gateway` "minimal implementation" and `apps/web-client`'s
first panel were a **Phase 2D** deliverable (`ENGINEERING_ROADMAP.md:450-452`),
confirmed in-scope by the Phase 2D Master Blueprint
(`docs/design/phase-2d/00-master-blueprint.md:141-145`) and never
excluded by its own §3.2 exclusion list — but never built. Every Gate
Review through Phase 2D-B silently re-deferred it via a "0 React files"
metrics-table line, never surfaced as an explicit scope decision. This
slice closes that gap under Phase 3's own umbrella, per the user's
explicit decision not to introduce a new phase number for it.

---

## 2. `api-gateway` design

**Role**, per `docs/architecture/11-api-architecture.md:1-17` (already
authoritative, not phase-specific): *"The one stable, versioned,
documented surface the outside world... talks to... enforces auth, rate
limiting, and request shaping before forwarding to the appropriate
engine or, more commonly, publishing an event."* The frontend never
calls any engine directly.

**REST write path.** Forwards to each engine's own already-built direct
`/v1/...` REST surface — `planning-engine`'s `/v1/plans/...` (`3B`),
`action-engine`'s `/v1/action/approvals/{id}/decide` (`3D`),
`capability-engine`'s `/v1/capabilities` (`3C`), `communication-engine`'s
existing `/v1/communication/...` (task #92's normalization). This is
**purely additive** — every one of those endpoints was already designed
to be fronted by `api-gateway` later (each TDD's own "stopgap, to be
fronted by `api-gateway` once built" language) — no redesign of any
engine's own API needed.

**Scaffolding gap, newly identified this pass.** `tools/scaffold-engine.py`'s
`_NAME_PATTERN` (`^[a-z][a-z0-9]*(-[a-z0-9]+)*-engine$`) requires a
literal `-engine` suffix — `api-gateway` and `ws-gateway` (neither ends
in `-engine`) **cannot use the existing scaffold tool any more than
`agent-os/kernel` could** (TDD 3E §3's identical class of gap, not
previously flagged for the gateways specifically by any prior research
pass). **Required tooling change:** either relax `_NAME_PATTERN` to also
accept a `-gateway` suffix (simpler than TDD 3E's agent-os case, since
both gateways *do* belong under `services/` per doc 02's own target tree,
`02-repository-and-folder-structure.md:50-51` — unlike `agent-os/kernel`,
they are ordinary FastAPI services, just not domain "engines"), or
scaffold them manually. **Recommendation: relax the name pattern** — the
generated skeleton (FastAPI app, health endpoints, Dockerfile) is
otherwise exactly what both gateways need. **Flagged for approval.**

**Auth/session, scoped for Phase 3.** `docs/architecture/13-auth-and-security.md:24,39`
specifies OIDC Authorization Code + PKCE terminating at the API Gateway
as the eventual design — but `nova-auth` does not exist yet (confirmed:
no `services/nova-auth`, only a placeholder comment in `nova-core`'s
`boot.py:85`; full OIDC is a **Phase 7** deliverable per
`ENGINEERING_ROADMAP.md:699`). Building a real OIDC provider now would be
scope creep far beyond this slice's bounds. **Proposed, scoped-down
Phase 3 mechanism, grounded in ADR-025** (*"single-trusted-user-per-instance
deployment assumption"* — confirmed still governing, unchanged through
Phase 2D): a single long-lived local session token issued at first-run
(no external identity provider), validated by `api-gateway` on every
request, with no multi-user/RBAC concept — consistent with "ship a real
but intentionally minimal instance" applied to auth the same way it's
applied to sandboxing (`3C`) and execution backends (`3E`). **Flagged for
explicit approval** — this is a genuine, disclosed departure from doc
13's eventual design, scoped explicitly to Phase 3's single-user
assumption, not a redesign of doc 13 itself.

**Rate limiting / request shaping state:** Redis-backed (existing
infrastructure, already used elsewhere in this project — no new
dependency), not a new Postgres schema; `api-gateway` itself is
stateless beyond that.

---

## 3. `ws-gateway` design

**Role**, per `docs/architecture/09-event-bus-architecture.md:139-145`
(already authoritative): *"The only component allowed to bridge bus
subjects to a browser/desktop client... through a per-connection
subscription allow-list derived from the authenticated user's
permissions... keeps ADR-005 true even though the frontend is,
mechanically, 'subscribed to the bus': it only ever receives
already-finalized `communication.*` events plus read-only telemetry,
never raw internal engine chatter."*

**Read path**, per doc 01 §6 and doc 04 §3: WebSocket primary, SSE
fallback; subscribes to bus topics scoped to the authenticated
session (per §2's Phase-3-scoped single-session-token model — the
"permission-derived allow-list" simplifies to "this instance's one
trusted user's own subjects," consistent with ADR-025, not a full RBAC
allow-list engine); forwards to the browser's `realtime/` client, which
reconciles directly into the TanStack Query cache
(`queryClient.setQueryData`) — no polling.

**Explicitly bounded allow-list for `3-P.1`:** `communication.*`
(existing), `personality.*`/`perception.*` read-only telemetry for the
presence indicator (existing). **`3-P.2` extends the allow-list** with
`planning.task_graph.*` (once `3B` ships) and `agent.*`/`agent_os.*`
(once `3E` ships) — additive, no redesign of the bridge mechanism itself.

**Scaffolding:** same gap and same recommendation as `api-gateway` (§2).

---

## 4. Base `apps/web-client` shell

Per `docs/architecture/04-frontend-architecture.md:12-33` (already
authoritative, quoted verbatim — not redesigned here):

```
apps/web-client/
├── src/
│   ├── app/                    # Routing (TanStack Router), layout shell
│   ├── panels/
│   │   └── conversation/       # the only panel built in 3-P.1
│   ├── entities/                # typed data-layer hooks per domain entity (from nova-contracts)
│   ├── realtime/                 # WebSocket client, event → cache reconciliation
│   ├── shared/
│   └── main.tsx
```

**Stack, already fully documented (Fork E4's resolution — not an open
choice, per `01-tdd-preparation-and-fork-resolutions.md` §2 Fork E4):**
React 18, TypeScript 5, Vite, TanStack Router, TanStack Query, Zustand,
React Hook Form + zod, Framer Motion, D3.js, Tailwind CSS + `@nova/ui`.
**No different stack is being proposed or substituted here.**

**First real consumer of an already-built, zero-consumer pipeline.**
`packages/nova-contracts/typescript/` codegen already exists and is
fully wired (confirmed: `turbo run build --filter=@nova/nova-contracts`
generates dozens of `.ts` files) but has **zero consumers anywhere in
the repository today** (confirmed by repo-wide grep). `entities/`'s
typed hooks are the first code in this project to actually import
generated types from that pipeline.

**`3-P.1`'s one panel: Conversation**, per Phase 2D's own undelivered
"first real UI" framing (`ENGINEERING_ROADMAP.md:451`) — depends only on
`communication-engine` (existing WebSocket `api/websocket.py`, mediated
through `ws-gateway`/`api-gateway` per doc 09 §6, never bypassed
directly) plus a presence/identity indicator sourced from
`perception-engine`/`world-model-engine`'s existing `present_identities`.

---

## 5. Dependency mapping against Phase 3 components (explicit, not forced)

| Component | Depends on |
|---|---|
| `api-gateway` | Nothing new — fronts already-existing engines (`3-P.1`) plus `3B`/`3C`/`3D`'s already-built stopgap endpoints once they exist (`3-P.2`, additive). |
| `ws-gateway` | Same — existing `communication.*`/`personality.*`/`perception.*` subjects for `3-P.1`; `planning.*`/`agent.*`/`agent_os.*` added once `3B`/`3E` ship. |
| Base shell + Conversation panel | Nothing new — existing engines only. |
| Planning panel | `3B` (`planning-engine`'s `planning.task_graph.created` + `GET /v1/plans/{id}`). |
| Agent Activity panel | `3E` (`agent.*`/`agent_os.*` events, `GET /v1/agents`/`GET /v1/agents/{id}/activity`, both already named in doc 11 §2 but not yet implemented by any TDD in this package — flagged as a small, disclosed addition to `3E`'s own API surface, not built by this document). **Correction, 2026-08-29 (Phase 3E Gate Review), additive:** Phase 3E shipped and did **not** add those two endpoints. TDD 3E §4 gives `agent-os/kernel` a health-only surface (`/internal/health`, `/internal/readiness`, `/internal/metrics`) and no `/v1/...` REST surface at all, deliberately — the Kernel's work is Event-Bus- and internal-loop-driven. The `agent.*`/`agent_os.*` **events** this panel needs do exist and are published. The two REST endpoints remain unbuilt and are now an open `3-P` prerequisite with no owning TDD, not a "disclosed addition to `3E`'s own API surface". |
| **`3A`-`3E` (the engines themselves)** | **Nothing depends on `3-P` in the reverse direction** — every engine is built, unit/integration/real-infra-tested, and independently verifiable exactly as every prior engine in this project has been, with zero UI. |

---

## 6. What's strictly required for Phase 3 vs. future work

**Strictly required (this slice):** `api-gateway`, `ws-gateway`
(minimal, per §2/§3's scoped-down auth model), base shell, Conversation
panel, presence indicator (`3-P.1`); Planning panel, Agent Activity panel
(`3-P.2`, once `3B`/`3E` ship respectively).

**Explicitly future work, not built here:**
- Every other Bible-named panel (`memory-timeline/`, `knowledge-graph/`,
  `world-model/`, `autonomy/`, `digital-twin/`, `personality/`,
  `executive/`, `system/`) — Autonomy + Digital Twin panels are named
  Phase 4 deliverables (`ENGINEERING_ROADMAP.md:574`); the rest have no
  assigned phase yet and are not claimed by this slice.
- Full OIDC/PKCE via a real `nova-auth` (Phase 7).
- The desktop Tauri shell reusing this same React app
  (`docs/architecture/05-desktop-architecture.md:36-38`) — Phase 5
  (`ENGINEERING_ROADMAP.md:603`, *"Desktop App & Living Interface"*).
- Git/HTTP-based multi-tenant rate limiting, full RBAC-scoped
  subscription allow-lists (depends on Phase 7's `nova-auth`).

---

## 7. Failure and degraded behavior

| Condition | Behavior |
|---|---|
| `ws-gateway` connection drops | `realtime/` client reconnects with backoff; TanStack Query cache is not cleared, only marked stale — no flash-of-empty-state on a transient drop. |
| An engine behind `api-gateway` is unavailable | `api-gateway` returns a structured error, never a silent empty success — the frontend surfaces the failure, consistent with this project's "never silence, always disclose degradation" discipline. |
| Session token expired/invalid | `api-gateway` rejects with 401; frontend re-issues the first-run session flow (§2) — no silent re-auth against a nonexistent OIDC provider. |

---

## 8. Observability

- `gateway_rest_request_total{engine=..., status=...}`,
  `gateway_rest_request_duration_ms` (histogram) — `api-gateway`.
- `gateway_ws_connections_active`, `gateway_ws_messages_forwarded_total{subject_prefix=...}`
  — `ws-gateway`.
- Standard health/readiness/metrics via `nova-service-kit` for both
  (once §2/§3's scaffolding-tool fix lands).

---

## 9. Security boundaries

Doc 09 §6's boundary — `ws-gateway` is the *only* component allowed to
bridge bus subjects to a browser — is the load-bearing security property
this slice implements, not just documents. The Phase-3-scoped session
model (§2) is a disclosed, approved-scope-reduction of doc 13's eventual
design, not a security regression relative to what exists today (no web
client exists today at all, so there is no prior security posture being
weakened).

---

## 10. Testing strategy

**Unit:** `api-gateway` request-forwarding/rate-limit logic;
`ws-gateway` subscription-allow-list construction.

**Integration:** a real WebSocket connection through `ws-gateway`
receiving a real `communication.intent.*` event and reconciling into a
fake TanStack Query cache; a real REST round trip through `api-gateway`
to `communication-engine`'s existing `/v1/communication/...` surface.

**E2E (Playwright, per `docs/architecture/16-testing-strategy.md:125`,
already the documented tool choice):** the "first real UI" golden path
— open the web client, hold a text conversation, see it rendered live —
the same golden path already named for Phase 2D's own undelivered
acceptance criterion, finally exercised here.

**Real-infrastructure:** none new beyond what `communication-engine`/
`personality-engine`/`perception-engine` already have — `3-P.1` adds no
new Postgres schema of its own (Redis-backed rate-limit state only, §2).

---

## 11. Acceptance criteria

1. A user can open the web client, authenticate via the Phase-3-scoped
   session mechanism (§2), and hold a live text conversation rendered
   through the Conversation panel — the literal "first real UI" Phase 2D
   never delivered.
2. `ws-gateway` is provably the only path a browser-originated connection
   can use to observe bus activity — no direct NATS exposure.
3. Once `3B` ships, the Planning panel renders a real `TaskGraph` with no
   change to `ws-gateway`'s bridging mechanism, only its subscription
   allow-list (§5).
4. Once `3E` ships, the same is true for the Agent Activity panel.

---

## 12. Non-goals (see §6 for the full list)

Full RBAC, full OIDC, the desktop shell, and every panel beyond
Conversation/Planning/Agent-Activity are explicitly out of scope for
this slice.
