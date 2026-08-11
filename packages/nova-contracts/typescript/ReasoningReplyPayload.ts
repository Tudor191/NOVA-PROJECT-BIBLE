export type ReasoningProcessId = string;
export type DecisionId = string | null;
export type ChosenDescription = string | null;
export type Explanation = string | null;
export type ConfidenceScore = number | null;
/**
 * Design doc §5's four terminal lifecycle states.
 */
export type ReasoningOutcome = "decided" | "degraded" | "failed" | "abandoned";
export type TraceId = string | null;
export type Error = string | null;
export type IsCorrection = boolean | null;
export type SchemaVersion = number;

export interface ReasoningReplyPayload {
  reasoning_process_id: ReasoningProcessId;
  decision_id?: DecisionId;
  chosen_description?: ChosenDescription;
  explanation?: Explanation;
  confidence_score?: ConfidenceScore;
  outcome: ReasoningOutcome;
  trace_id?: TraceId;
  error?: Error;
  is_correction?: IsCorrection;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
