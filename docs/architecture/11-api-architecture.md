# 11 — API Architecture

## 1. Two API surfaces, deliberately separated

| Surface | Purpose | Consumers |
|---|---|---|
| **External API** (`api-gateway`) | The one stable, versioned, documented surface the outside world (web client, desktop client, third-party integrations, future mobile) talks to | apps/*, external developers |
| **Internal engine APIs** | Each engine's own FastAPI app, used for direct engine-to-engine request/reply *when routed through the bus* and for operational/admin access | Other engines (via bus), operators |

The frontend never calls `memory-engine` or `reasoning-engine` directly — it calls the
**API Gateway**, which enforces auth, rate limiting, and request shaping before
forwarding to the appropriate engine or, more commonly, publishing an event and letting
the response arrive asynchronously over the WebSocket ([09](09-event-bus-architecture.md)).
This indirection is what lets internal engines be added, removed, or re-architected
without ever touching a client's integration contract — Part 1's "every subsystem must
expose clean APIs" is satisfied at the boundary the outside world actually sees, not by
exposing 19 raw service APIs and hoping clients don't couple to internals.

## 2. External API design

- **Style:** REST + JSON for commands/queries, WebSocket for live/streaming data
  (chat streaming, dashboards). GraphQL was considered and rejected: the Bible's data
  is graph-shaped *internally* (Knowledge Graph, World Model), but the client surface
  is a set of well-known, purpose-built views (panels), not ad hoc client-defined
  queries — REST's simplicity, cacheability, and easier auth/versioning story wins here.
- **Versioning:** URL-path versioned (`/v1/...`), additive changes only within a major
  version; breaking changes require a new major version with a documented deprecation
  window — required by Part 1's "production ready at all times."
- **Schema source of truth:** every route's request/response model comes from
  `nova-contracts`; the Gateway's OpenAPI spec is generated, not hand-maintained.
- **Pagination:** cursor-based on all list endpoints (memory timeline, knowledge graph
  nodes, agent activity) — required given these collections are unbounded by design.

### Representative endpoint groups

```
POST   /v1/conversations                     # start a session (Part 13 "Conversation Model")
POST   /v1/conversations/{id}/messages        # send a message
GET    /v1/conversations/{id}/messages        # history (cursor paginated)
WS     /v1/stream                             # ws-gateway: filtered event subscription

GET    /v1/memory/search?mode=semantic|graph|timeline...
GET    /v1/memory/{id}
DELETE /v1/memory/{id}                        # user-initiated forgetting (Part 3 "User Control")

GET    /v1/knowledge/graph?scope=project:<id>
GET    /v1/world-model/context

GET    /v1/plans/{task_graph_id}
POST   /v1/plans/{task_graph_id}/approve      # Part 9 "Collaborative Planning"

GET    /v1/agents
GET    /v1/agents/{id}/activity

POST   /v1/autonomy/approvals/{id}/decide      # approve/reject a pending autonomous action
GET    /v1/autonomy/policies
PUT    /v1/autonomy/policies                    # Part 14 "Governance"

GET    /v1/capabilities
POST   /v1/capabilities/install
DELETE /v1/capabilities/{id}

GET    /v1/digital-twin/profile
PATCH  /v1/digital-twin/profile                  # Part 16 "User Control"

GET    /v1/system/health                          # Part 20 dashboard feed
```

## 3. Internal engine API contracts

Every engine's FastAPI app exposes:

```
GET  /internal/health           # liveness (Part 20 heartbeat)
GET  /internal/readiness        # dependency checks passed
GET  /internal/metrics          # Prometheus scrape endpoint
POST /internal/rpc/<method>      # typed request/reply methods callable via the bus bridge
```

`/internal/*` is never exposed through the API Gateway or the public ingress — it is
reachable only inside the private network/service mesh (or, in local-first mode, on
`localhost` only). This is the concrete enforcement mechanism behind "departments never
communicate directly with the user" (Part 4): there is no network path from the public
internet to an engine's internal RPC surface.

## 4. Request/response envelope

Every API response uses a consistent envelope so the frontend's data layer
(`entities/`, [04](04-frontend-architecture.md)) can handle any endpoint generically:

```json
{
  "data": { "...": "..." },
  "meta": { "confidence": 0.87, "correlation_id": "...", "generated_at": "..." },
  "error": null
}
```

Surfacing `confidence` and `correlation_id` at the API envelope level (not buried in
payloads) is a direct, deliberate expression of Part 8's Confidence System and Part 19's
Explainability requirement — every response the user sees can be traced back through
the event chain that produced it.

## 5. Rate limiting & quotas

Enforced at the Gateway using a Redis-backed token bucket per `(user, endpoint class)`.
Endpoint classes: `read` (generous), `write` (moderate), `expensive-reasoning`
(strict — protects local GPU/cloud budget, ties into Part 7's Cost Management).

## 6. Backward compatibility & deprecation policy

- A field is never removed from a `v1` response; it may be marked deprecated in the
  OpenAPI spec and stops being *populated* only after a documented notice period.
- Event schemas ([09](09-event-bus-architecture.md)) follow the same rule — additive
  fields only within a schema version, since JetStream-durable events may be replayed
  by consumers written against an older schema.
