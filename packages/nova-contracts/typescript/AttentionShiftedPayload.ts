export type UserId = string;
export type EntityId = string;
export type AttentionScore = number;

export interface AttentionShiftedPayload {
  user_id: UserId;
  entity_id: EntityId;
  attention_score: AttentionScore;
  [k: string]: unknown;
}
