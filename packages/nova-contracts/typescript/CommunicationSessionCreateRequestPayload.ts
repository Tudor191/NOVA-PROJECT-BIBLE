export type UserId = string;
/**
 * Design doc Sec3.2, Sec5 -- extensible; exactly two ship this phase.
 */
export type ChannelType = "text" | "voice";
export type DeviceId = string;
export type RequestingEngine = string;
export type CorrelationId = string;
export type SchemaVersion = number;

export interface CommunicationSessionCreateRequestPayload {
  user_id: UserId;
  channel: ChannelType;
  device_id: DeviceId;
  requesting_engine: RequestingEngine;
  correlation_id?: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
