export type Content = string;
/**
 * Mirrors Doc 23 Sec5.2's four confidence levels -- caller-supplied
 * (epistemic deference, ADR-028's pattern applied here per design doc
 * Sec4): this engine cross-checks phrasing against the tier, it never
 * re-derives the tier itself.
 */
export type ConfidenceTier = "high" | "medium" | "low" | "unknown";
export type SessionId = string;
export type RequestingEngine = string;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * Event Bus RPC counterpart to `POST /validate` (design doc Sec7.1,
 * Sec11) -- the ADR-005 gate's synchronous dependency, called by
 * `communication-engine` before every delivered response.
 */
export interface PersonalityValidateResponseRequestPayload {
  content: Content;
  confidence_tier?: ConfidenceTier;
  session_id: SessionId;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
