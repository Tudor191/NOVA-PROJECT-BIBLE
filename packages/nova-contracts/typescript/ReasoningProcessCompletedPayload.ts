export type ReasoningProcessId = string;
export type CorrelationId = string;
export type RequestingEngine = string;
export type UserId = string;
/**
 * Design doc §6's ten reasoning-mode taxonomy.
 */
export type ReasoningMode =
  | "reactive"
  | "analytical"
  | "strategic"
  | "long_term_planning"
  | "goal_driven"
  | "constraint_based"
  | "multi_step"
  | "reflective"
  | "self_evaluation"
  | "collaborative";
export type ReasoningLevel = number;
export type ConfidenceScore = number;
export type ExecutionDurationMs = number;
/**
 * Design doc §5's four terminal lifecycle states.
 */
export type ReasoningOutcome = "decided" | "degraded" | "failed" | "abandoned";
export type ObjectiveText = string;
export type ChosenDescription = string | null;
export type SchemaVersion = number;

/**
 * Published for every terminal outcome that produced a decision --
 * `decided` or `degraded` alike (design doc §5) -- the event-bus mirror of
 * the `reasoning_process`/`decision` rows `ReasoningRepository` persists.
 */
export interface ReasoningProcessCompletedPayload {
  reasoning_process_id: ReasoningProcessId;
  correlation_id: CorrelationId;
  requesting_engine: RequestingEngine;
  user_id: UserId;
  reasoning_mode: ReasoningMode;
  reasoning_level: ReasoningLevel;
  confidence_score: ConfidenceScore;
  execution_duration_ms: ExecutionDurationMs;
  outcome: ReasoningOutcome;
  objective_text: ObjectiveText;
  chosen_description?: ChosenDescription;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
