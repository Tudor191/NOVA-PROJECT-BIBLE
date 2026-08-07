export type SessionId = string;
export type Content = string;
export type ConfidenceTier = string;
export type RequestingEngine = string;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * Every candidate outbound utterance, from any content-source engine
 * (Sec8.2), arrives as this request. `confidence_tier` is forwarded
 * verbatim to `personality.validate_response` (epistemic deference,
 * ADR-028's pattern).
 */
export interface CommunicationIntentDeliverRequestPayload {
  session_id: SessionId;
  content: Content;
  confidence_tier?: ConfidenceTier;
  requesting_engine: RequestingEngine;
  correlation_id?: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
