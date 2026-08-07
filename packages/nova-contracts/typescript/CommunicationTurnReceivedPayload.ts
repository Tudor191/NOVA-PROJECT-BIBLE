export type SessionId = string;
export type TurnId = string;
export type UserId = string;
export type Content = string;
/**
 * Design doc Sec3.2, Sec5 -- extensible; exactly two ship this phase.
 */
export type ChannelType = "text" | "voice";
export type CreatedAt = string;
export type SchemaVersion = number;

/**
 * Design doc Sec6's "Determine Intent" pass-through -- published for
 * Reasoning Engine (or any future content-source engine) to subscribe to;
 * this engine forms no judgment about what the turn means.
 */
export interface CommunicationTurnReceivedPayload {
  session_id: SessionId;
  turn_id: TurnId;
  user_id: UserId;
  content: Content;
  channel: ChannelType;
  created_at: CreatedAt;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
