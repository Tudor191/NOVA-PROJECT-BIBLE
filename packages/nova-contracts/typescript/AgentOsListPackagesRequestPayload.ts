export type RequestingEngine = string;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * Kernel -> Registry, disclosed addition (Phase 4C milestone 4C.2a,
 * approved 2026-09-08): "what packages are registered", the question
 * `GET /v1/agents` (decision **D-4**, master scope §9) has to answer and
 * which `find_healthy_package` above deliberately cannot.
 *
 * That RPC answers with a **single winner** -- it exists to pick one
 * package to dispatch against, and applies `domain/selection.py`'s health
 * and version policy to do it. A listing is a different question with a
 * different answer shape, and reusing the dispatch RPC for it would mean
 * either widening its reply (breaking its "one winner" contract) or
 * calling it once per category and silently dropping every version that
 * lost selection. Neither describes what is installed.
 *
 * **Why an RPC and not a direct table read.** `agent_package` is
 * `agent-os/registry`'s own table. ADR-004 forbids one component reaching
 * into another's internals, and both components' own `repository/models.py`
 * docstrings already record that each defines exactly the one table it
 * owns. The Kernel therefore asks, over the bus, and Registry stays
 * authoritative for packages.
 *
 * **Why request/reply and not a broadcast.** This answers a point-in-time
 * query for one caller. A broadcast would need a Kernel-side cache with a
 * cold-start hole -- a Kernel starting after Registry would hold nothing
 * until the next install, and installs happen only at Registry startup
 * (doc 12 §15's filesystem discovery).
 *
 * **Internal only.** This subject is never a `PUBLIC_TOPIC` and never
 * matches a `ws-gateway` subscribable pattern: a browser reaches this data
 * through `GET /v1/agents`, never over the bus. `ws-gateway`'s own
 * `domain/protocol.py` docstring states the rule ("a client cannot
 * subscribe to ... an internal RPC subject"), and
 * `services/ws-gateway/tests/unit/test_protocol.py` now enforces it for
 * every `agent_os.*` RPC subject rather than leaving it to convention.
 *
 * No filter fields: Phase 3's filesystem discovery installs the five
 * packages under `agents/` at Registry startup and nothing else ever adds
 * one, so the installed set is small and bounded by the repository's own
 * contents. A `category` filter would be a field with no caller.
 */
export interface AgentOsListPackagesRequestPayload {
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
