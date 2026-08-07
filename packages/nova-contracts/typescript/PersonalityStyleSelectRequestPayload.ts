export type SituationHint = string | null;
export type Channel = string | null;
export type RequestingEngine = string;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * Event Bus RPC counterpart to `GET /style` (design doc Sec7.1, Sec11).
 */
export interface PersonalityStyleSelectRequestPayload {
  situation_hint?: SituationHint;
  channel?: Channel;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
