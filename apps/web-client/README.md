# `apps/web-client`

NOVA's first usable interface. Built in **Phase 4A**; implements
[doc 04 §2](../../docs/architecture/04-frontend-architecture.md) as written,
per [TDD 4A](../../docs/design/phase-4/01-tdd-4a-gateways-and-web-client.md) §5.

Before this, the repository contained **no `apps/` directory and zero `.tsx`
files**, and the 98 generated TypeScript contracts in `packages/nova-contracts`
had **zero consumers**. `src/entities/` is the first code in the project's
history to import them.

## Layout

```
src/
├── app/        Routing, layout shell, System Pulse, presence, session gate
├── entities/   Typed data layer, one module per domain entity
├── realtime/   The WebSocket client and bus-frame → cache reconciliation
├── panels/
│   └── conversation/   The only panel 4A builds
└── shared/     Config (the two gateway addresses) and ephemeral UI state
```

## The rules this application is built around

These are not style preferences; each is an architectural constraint with a
test that fails when it is broken.

**The frontend never calls an engine.** `shared/config.ts` has no engine URL
and no way to configure one, and `apiUrl()` throws on any path outside
`/v1/`. Everything goes through `api-gateway` (doc 11 §1, §3).

**The browser never speaks to the bus.** `realtime/client.ts` is the only
WebSocket in the application and refuses any scheme but `ws:`/`wss:`.
`ws-gateway` is the sole bridge (doc 09 §6). Enforced three ways: the runtime
check, `no-restricted-imports` in `eslint.config.js`, and
`tests/unit/security-boundary.test.ts`, which scans every source file for a
NATS import, a `nats://` URL, or the bus port.

**Reads are pushed, never polled.** Every cache entry except the session
probe declares `queryFn: skipToken` — it has no fetcher at all, because
`realtime/` is its only writer.

**Writes are never optimistic.** A sent turn appears in the transcript when
`communication.turn.received` comes back over the socket, not when Send is
clicked. The UI must never show a belief NOVA does not hold. Local composer
text is the one exemption, and it is the whole of `shared/store.ts`.

**Nothing is invented.** A confidence that was not reported renders as *"no
confidence reported"*. `communication.intent.delivered` reports a tier *word*
and is displayed as one — no layer converts it to a number. Presence is
`null` (unknown) until perception says otherwise, which is not the same as an
empty list. The System Pulse animates once per real heartbeat and goes
`unknown` when the heartbeat stops.

**Degradation is disclosed.** An unreachable engine, an expired session, a
rate limit and a contract mismatch each render a `DegradationNotice` with the
error code and correlation id — never an empty panel.

## Checks

```
pnpm --filter @nova/web-client run test       # vitest, 87 tests
pnpm --filter @nova/web-client run typecheck  # tsc --noEmit, strict
pnpm --filter @nova/web-client run lint       # eslint
pnpm --filter @nova/web-client run build      # vite production build
```

`pnpm --filter @nova/web-client run test:e2e` runs the Playwright golden
path. **It is CI-only evidence.** It needs the full local stack via Docker,
which is unavailable in the development environment, so it has never been run
locally and no local result should be reported for it (TDD 4A §10's R-1, and
Phase 3E condition C-1). The authoritative signal is the `e2e` job in
`pr-checks.yml`.

## Development

```
pnpm --filter @nova/web-client run dev
```

Vite proxies `/v1` to `api-gateway` and `/ws` to `ws-gateway` (override with
`NOVA_API_GATEWAY_URL` / `NOVA_WS_GATEWAY_URL`). The proxy exists so the
browser only ever sees one origin — the session cookie is `SameSite=Strict`,
and talking to an engine on another port in development would train the
client to do exactly what the architecture forbids in production.

## Known limitations in 4A

- **A reload starts the transcript empty.** `communication-engine` exposes no
  endpoint returning a session's turns (`GET .../context` returns a
  `turn_count`, not the turns), so there is nothing to hydrate from. Adding
  one is engine work and 4A changes no engine API beyond the single event it
  had to add.
- **`d3` and `framer-motion` are not installed.** Both are part of the
  decided stack (Fork E4) and both arrive with the panels that need them
  (4B+). The only motion in 4A is one CSS keyframe bound to a real heartbeat;
  installing an animation library for that would add dependency and audit
  surface for nothing.
- **One panel.** Every other panel is 4B or later, per
  [master scope](../../docs/design/phase-4/00-master-scope.md) §6.
