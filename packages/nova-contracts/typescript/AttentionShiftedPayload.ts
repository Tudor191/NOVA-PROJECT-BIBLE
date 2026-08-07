export type UserId = string;
export type EntityId = string;
export type AttentionScore = number;
export type SchemaVersion = number;

export interface AttentionShiftedPayload {
  user_id: UserId;
  entity_id: EntityId;
  attention_score: AttentionScore;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
