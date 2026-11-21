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

*(Updated 2026-09-26, Phase 4F.7, additively.)* The table above is the 4B set.
4C added `/v1/agents` → `agent-os-kernel`, 4D `/v1/autonomy` → `autonomy-engine`
and 4E `/v1/digital-twin` → `digital-twin-engine`; **4F.7 adds
`/v1/cognitive-state` → `cognitive-state-engine`** (RS-5), making nine. The
engine serves three `GET`s under it and answers 405 to any other method, which
the gateway forwards unchanged; there is no `user_id` parameter to forward
(identity is resolved in the engine). `domain/routing.py` is the authority, and
`tests/integration/test_gateway.py` pins the exact set of nine.

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
- Forwarded prefixes — the five in the table above *(nine since 4F.7; see the
  note under the table)*
- `GET /internal/health`
- `GET /internal/readiness`
- `GET /internal/metrics` — the Prometheus scrape endpoint, mounted as a
  sub-application in `main.py` rather than declared in `api/health.py`.

## Internal structure

*(Added 2026-10-16, SAD 15 §9.1 item 3. Drawn from `src/` at this commit.)*

```
src/nova_api_gateway/
├── main.py             create_app(): settings, route table, session validator,
│                       rate limiter, metrics, routers, /internal/metrics mount
├── config.py           Settings (env prefix API_GATEWAY_)
├── observability.py    GatewayMetrics: the four instruments below
├── api/
│   ├── auth.py         POST/GET/DELETE /v1/auth/session (decision D-3)
│   ├── forward.py      /v1/{path} catch-all: authenticate → route → limit → forward
│   └── health.py       /internal/health, /internal/readiness
├── clients/
│   └── upstream.py     UpstreamClient (httpx), header filtering, UpstreamUnavailableError
├── domain/             no I/O
│   ├── envelope.py     doc 11 §4 envelope, correlation ids
│   ├── routing.py      RouteTable: the nine allow-listed prefixes, endpoint_class()
│   ├── rate_limit.py   InMemoryRateLimiter, NullRateLimiter
│   └── session.py      LocalTokenSessionValidator (constant-time comparison)
├── events/             published.py / subscribed.py: both sets empty by design
├── models/             scaffold package; empty
└── repository/         scaffold package; empty (the gateway owns no data)
```

Shared packages: `nova-observability` (logging, metrics). `nova-contracts`
and `nova-eventbus-sdk` are declared dependencies, but the gateway publishes
and subscribes to nothing.

## Observability

*(Added 2026-10-16, SAD 15 §9.1 items 9 and 10.)*

**Metrics**, scraped from `/internal/metrics`. Every label is bounded: no
path, query, token or correlation id is ever a label.

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `api_gateway_requests_total` | counter | `upstream`, `method`, `outcome` | Every `/v1/*` forwarding decision |
| `api_gateway_request_duration_seconds` | histogram | `upstream`, `outcome` | Time to answer a `/v1/*` request |
| `api_gateway_upstream_duration_seconds` | histogram | `upstream`, `outcome` | Time inside the upstream call alone |
| `api_gateway_session_exchanges_total` | counter | `outcome` | `issued`, `invalid_token`, `not_configured` |

`outcome` is one of `forwarded`, `upstream_error`, `upstream_unavailable`,
`unauthenticated`, `no_route`, `rate_limited`. Histogram buckets are in
seconds (5 ms to 30 s); the OpenTelemetry default buckets assume
milliseconds and would put every request in one bucket.

**Logs** (JSON, via `nova-observability`). Each refusal or failure carries
the request's `correlation_id`, its method and its path:

| Message | Level | When |
|---|---|---|
| `request refused`, `reason=unauthenticated` | info | No valid session; no upstream was contacted |
| `request refused`, `reason=no_route` | info | Not an allow-listed prefix |
| `request refused`, `reason=rate_limited` | warning | The limiter refused; carries `endpoint_class` |
| `upstream unavailable` | warning | The upstream could not be reached (502) |
| `upstream returned an error` | info | The upstream answered ≥ 400; carries `upstream_status` |
| `session exchange refused` | warning | `reason=invalid_token` or `session_not_configured`. The presented value is never logged |
| `session issued` | info | A session cookie was set |

**Not built: traces.** `configure_observability()` installs an OTLP
exporter, but no span is created here or anywhere in the repository, and
no trace context is propagated to upstreams. SAD 15 §9.1 item 10 asks for
both; doing it needs a propagation decision across HTTP and the Event Bus
envelope, recorded as open in the Phase 4 closure matrix.

**Rate limiting differs from its design.** TDD 4A §2.3 specifies a
Redis-backed token bucket with three classes. What runs is an in-process
fixed-window counter with two (`read`, `write`); see
`domain/rate_limit.py`. The deviation is disclosed and awaiting a decision.

**A 429 carries `Retry-After`** *(added 2026-10-16)*: the whole seconds until
the fixed window ends, never 0. This is TDD 4A §7's "structured retry hint",
which the 429 lacked until now. It is the standard header, so the envelope's
`error` schema is unchanged. `web-client` reads the header and shows the hint.

## Testing

```bash
uv run --package api-gateway pytest services/api-gateway/tests
```
