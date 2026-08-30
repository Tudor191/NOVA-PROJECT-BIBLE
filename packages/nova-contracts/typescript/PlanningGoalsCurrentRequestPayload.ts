export type UserId = string;
export type Scope = string | null;
export type RequestingEngine = string;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * TDD 3E §8 -- the real-RPC replacement for `GoalsPort`'s own
 * caller-supplied placeholder. Field names/optionality mirror
 * `GoalsPort.current_goals()`'s own Protocol signature exactly (both
 * `reasoning-engine`'s and `executive-cognition-engine`'s
 * `clients/goals_client.py`), which this RPC's own client adapter calls
 * through unchanged -- the Protocol itself, and every one of its callers,
 * is never touched by this migration.
 */
export interface PlanningGoalsCurrentRequestPayload {
  user_id: UserId;
  scope?: Scope;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
