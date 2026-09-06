# api-gateway

The single external REST surface for the whole system ([11](../../docs/architecture/11-api-architecture.md)
§1). Every browser request enters here and nowhere else: engines are not
published to the host, and no client is permitted to address one directly. The
gateway terminates the session, applies rate limiting, wraps every response in
the canonical `{data, meta, error}` envelope, and forwards the request verbatim
to exactly one upstream engine.

It implements no Bible Part of its own — it is the transport boundary in front of
the engines that do. Its security posture is governed by
[13](../../docs/architecture/13-auth-and-security.md) and ADR-025
(single-trusted-user-per-instance).

**Forwarding is an allow-list, not a pattern** (Phase 4 decision **D-6**). Paths
are matched by prefix against a fixed table and passed through unchanged, so a
new upstream cannot be reached until it is added deliberately.

| Prefix | Upstream |
|---|---|
| `/v1/communication` | `communication-engine` |
| `/v1/plans` | `planning-engine` |
| `/v1/reasoning` | `reasoning-engine` |
| `/v1/capabilities` | `capability-engine` |
| `/v1/action` | `action-engine` |

`executive-cognition-engine` and `nova-core` are deliberately **not** fronted —
see `domain/routing.py`'s docstring for why. **`/internal/*` is never routable**
([11](../../docs/architecture/11-api-architecture.md) §3): it is not a special
case in the table, it is simply absent from it, so an `/internal/health` request
is indistinguishable from any other unrouted path. That indistinguishability is
asserted by an end-to-end test, not by inspection.

## Owned events

None. The gateway publishes and subscribes to no bus subject; it is a
request/response boundary only. Realtime delivery to the browser is
`ws-gateway`'s job ([09](../../docs/architecture/09-event-bus-architecture.md) §6).

## Owned APIs

- `POST /v1/auth/session` — exchange the local instance token for an httpOnly
  cookie (the Phase-4-scoped session mechanism, decision **D-3**)
- `GET /v1/auth/session` — is the current session still valid
- `DELETE /v1/auth/session` — sign out
- Forwarded prefixes — the five in the table above
- `GET /internal/health`
- `GET /internal/readiness`

There is deliberately **no `/internal/metrics`** here. The scaffold README that
this file replaced listed one; the gateway has never exposed it. (Corrected
2026-09-06, Phase 4B closure pass.)

## Testing

```bash
uv run --package api-gateway pytest services/api-gateway/tests
```
