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
export type ChangedAt = string;
export type SchemaVersion = number;

/**
 * Design doc Sec3.1, Sec11 -- the Live Communication Dashboard's data
 * source: the real current state, never an approximation.
 */
export interface CommunicationSessionStateChangedPayload {
  session_id: SessionId;
  from_state: ConversationState;
  to_state: ConversationState;
  changed_at: ChangedAt;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
