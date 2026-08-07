export type SessionId = string;
/**
 * Bible Part 13's ten conversation states (design doc Sec3.1).
 * `EXECUTING`/`MONITORING`/`LEARNING` are reserved -- no Phase 2D-A
 * transition produces them (Phase 3/2D-D do).
 */
export type ConversationState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "waiting"
  | "paused"
  | "completed"
  | "executing"
  | "monitoring"
  | "learning";
export type ClosedAt = string;
export type SchemaVersion = number;

export interface CommunicationSessionCloseReplyPayload {
  session_id: SessionId;
  state: ConversationState;
  closed_at: ClosedAt;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
