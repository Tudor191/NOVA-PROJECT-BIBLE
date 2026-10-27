export type SessionId = string;
/**
 * Bible Part 13's nine-style palette.
 */
export type CommunicationStyle =
  | "professional"
  | "educational"
  | "technical"
  | "friendly"
  | "executive"
  | "creative"
  | "minimal"
  | "analytical"
  | "emergency";
export type Verbosity = string;
export type TechnicalDepth = string;
export type SituationHint = string | null;
export type ResponseLanguage = string;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * Phase 2D-C addition (04-conversation-intelligence.md Sec0.7/Sec7/
 * Sec8/Sec10) -- published alongside (same `correlation_id` as)
 * `communication.turn.received`, never merged into that payload: this is
 * a policy decision *about* the turn, not a property *of* it (the same
 * "decision-trace-shaped data gets its own payload" convention
 * `ArbitrationResult` already established relative to
 * `ExecutiveRequestPayload` in Phase 2C). `communication-engine` computes
 * and publishes this; it does not itself apply it to any generated
 * content (Sec0.1 -- this engine never generates content). Whether/how a
 * content-source engine (e.g. Reasoning Engine) currently consumes it is
 * explicitly *not* implied by this payload's existence -- see Sec0.7's
 * own disclosed finding that no such consumer exists yet.
 */
export interface ResponseShapingDirectivePayload {
  session_id: SessionId;
  style: CommunicationStyle;
  verbosity: Verbosity;
  technical_depth: TechnicalDepth;
  situation_hint?: SituationHint;
  response_language?: ResponseLanguage;
  correlation_id?: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
