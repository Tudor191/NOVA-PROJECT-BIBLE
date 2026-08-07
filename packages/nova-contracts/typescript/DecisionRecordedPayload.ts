export type DecisionId = string;
export type MemoryId = string;
export type UserId = string;
export type Objective = string;
export type ChosenAlternative = string;
export type ConfidenceAtDecision = number | null;
export type SchemaVersion = number;

export interface DecisionRecordedPayload {
  decision_id: DecisionId;
  memory_id: MemoryId;
  user_id: UserId;
  objective: Objective;
  chosen_alternative: ChosenAlternative;
  confidence_at_decision?: ConfidenceAtDecision;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
