export type SessionId = string;
export type UserId = string;
/**
 * Design doc Sec3.2, Sec5 -- extensible; exactly two ship this phase.
 */
export type ChannelType = "text" | "voice";
export type DeviceId = string;
export type CreatedAt = string;
export type SchemaVersion = number;

export interface CommunicationSessionCreatedPayload {
  session_id: SessionId;
  user_id: UserId;
  channel: ChannelType;
  device_id: DeviceId;
  created_at: CreatedAt;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
