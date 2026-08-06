export type ExecutiveDecisionId = string;
export type CorrelationId = string;
/**
 * Design doc Sec18 -- what kind of decision an Executive Decision Trace records.
 */
export type ExecutiveDecisionType = "resource_arbitration" | "conflict_resolution" | "human_override";
export type RequestingEngine = string;
export type RequestKind = string;
export type CorrelationId1 = string;
export type ContendingRequests = ContenderSummary[];
export type WinnerCorrelationId = string | null;
/**
 * Design doc Sec4 -- the four outcomes every arbitration produces.
 */
export type ArbitrationOutcome = "proceed" | "proceed_reduced" | "wait" | "escalated";
export type ExecutionDurationMs = number;
export type SchemaVersion = number;

/**
 * Published for every arbitration that produced an outcome --
 * `proceed`, `proceed_reduced`, `wait`, or `escalated` alike (design doc
 * Sec4, Sec7) -- the event-bus mirror of the `executive_decision` row
 * `ExecutiveRepository` persists. Distinct from `.failed` below the same
 * way Reasoning Engine's own `.completed`/`.failed` split works: this
 * event means arbitration itself succeeded at producing *some* outcome,
 * not that the outcome was necessarily `proceed`.
 */
export interface ExecutiveDecisionCompletedPayload {
  executive_decision_id: ExecutiveDecisionId;
  correlation_id: CorrelationId;
  decision_type: ExecutiveDecisionType;
  contending_requests: ContendingRequests;
  winner_correlation_id?: WinnerCorrelationId;
  outcome: ArbitrationOutcome;
  execution_duration_ms: ExecutionDurationMs;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
/**
 * Design doc Sec18 -- identifies one request that participated in an
 * arbitration, without carrying any of its domain content.
 */
export interface ContenderSummary {
  requesting_engine: RequestingEngine;
  request_kind: RequestKind;
  correlation_id: CorrelationId1;
  [k: string]: unknown;
}
