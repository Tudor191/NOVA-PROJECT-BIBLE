export type CorrelationId = string;
export type Reason = string;
export type SchemaVersion = number;

/**
 * Published when arbitration itself cannot produce any outcome (design
 * doc Sec14) -- a malformed request, an unrecoverable internal failure --
 * distinct from a genuine `escalated` outcome, which is still a
 * successfully-produced decision (design doc Sec4, Sec13).
 */
export interface ExecutiveDecisionFailedPayload {
  correlation_id: CorrelationId;
  reason: Reason;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
