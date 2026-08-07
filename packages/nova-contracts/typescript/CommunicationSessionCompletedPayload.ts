export type SessionId = string;
export type UserId = string;
export type Objective = string | null;
export type TurnCount = number;
export type ClosedAt = string;
export type SchemaVersion = number;

/**
 * Design doc Sec8.6 -- the only long-term retention of conversation
 * content; Memory Engine is this event's intended (not yet wired,
 * out of Phase 2D-A scope) subscriber.
 */
export interface CommunicationSessionCompletedPayload {
  session_id: SessionId;
  user_id: UserId;
  objective?: Objective;
  turn_count: TurnCount;
  closed_at: ClosedAt;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
