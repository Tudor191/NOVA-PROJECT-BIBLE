export type Texts = string[];
export type RequestingEngine = string;
export type CorrelationId = string;
/**
 * Bible Part 7's privacy classification, propagated on every entity per
 * docs/design/phase-1/00-shared-foundations.md's "Confidence and privacy,
 * everywhere" convention. Enforcement point is the Model Orchestration Engine
 * (Phase 2); Phase 1 stores and propagates the field correctly from day one.
 */
export type PrivacyLevel = "public" | "internal" | "confidential" | "highly_sensitive";
export type PreferredModelId = string | null;
export type SchemaVersion = number;

/**
 * Event Bus RPC counterpart to `POST /v1/models/embed` (design doc §10).
 */
export interface EmbedRequestPayload {
  texts: Texts;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  privacy_hint?: PrivacyLevel;
  preferred_model_id?: PreferredModelId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
