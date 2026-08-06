export type CorrelationId = string;
/**
 * Design doc Sec7.3 -- what a caller reports happened after acting on
 * an arbitration decision.
 */
export type OutcomeReportResult = "succeeded" | "failed" | "abandoned";
export type ActualDurationMs = number | null;
export type Note = string | null;
export type SchemaVersion = number;

/**
 * Design doc Sec7.3 -- the optional, genuinely-opt-in outcome-report
 * RPC. No caller is required to send this, and arbitration correctness
 * never depends on one arriving.
 */
export interface ExecutiveOutcomeReportPayload {
  correlation_id: CorrelationId;
  outcome: OutcomeReportResult;
  actual_duration_ms?: ActualDurationMs;
  note?: Note;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
