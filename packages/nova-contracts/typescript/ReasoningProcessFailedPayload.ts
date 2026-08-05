export type ReasoningProcessId = string;
export type CorrelationId = string;
export type RequestingEngine = string;
export type Stage = string;
/**
 * Design doc §17's Bible Part 8 failure-recovery action set.
 */
export type FailureAction =
  | "restart"
  | "reduce_complexity"
  | "request_clarification"
  | "delegate"
  | "retrieve_more_knowledge"
  | "escalate_deeper";
export type Reason = string;
export type RetryCount = number;
export type SchemaVersion = number;

/**
 * Published when Failure Recovery (design doc §17) cannot produce any
 * decision -- `outcome in {"failed", "abandoned"}`.
 */
export interface ReasoningProcessFailedPayload {
  reasoning_process_id: ReasoningProcessId;
  correlation_id: CorrelationId;
  requesting_engine: RequestingEngine;
  stage: Stage;
  action: FailureAction;
  reason: Reason;
  retry_count?: RetryCount;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
