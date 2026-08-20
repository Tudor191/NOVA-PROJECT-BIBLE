export type TaskNodeId = string;
export type RequestingEngine = string;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * TDD 3B §6.2, per doc 12 §11: a Supervisor (agent-os, not built until
 * TDD 3E) or any other caller may request further decomposition of one
 * `TaskNode` "still too coarse for a single leaf agent," scoped to that
 * node's own subtree. `requesting_engine`/`correlation_id` follow the
 * same request/reply RPC shape as every other `nova_contracts` RPC
 * payload (e.g. `CapabilityResolveRequestPayload`).
 */
export interface PlanningDecomposeRequestPayload {
  task_node_id: TaskNodeId;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
