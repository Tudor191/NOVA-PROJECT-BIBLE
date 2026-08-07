export type SessionId = string;
export type RequestingEngine = string;
export type CorrelationId = string;
export type SchemaVersion = number;

export interface CommunicationSessionCloseRequestPayload {
  session_id: SessionId;
  requesting_engine: RequestingEngine;
  correlation_id?: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
