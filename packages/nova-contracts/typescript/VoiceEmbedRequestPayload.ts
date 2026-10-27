export type AudioBytes = string;
export type AudioFormat = "wav" | "opus" | "pcm16";
/**
 * Bible Part 7's privacy classification, propagated on every entity per
 * docs/design/phase-1/00-shared-foundations.md's "Confidence and privacy,
 * everywhere" convention. Enforcement point is the Model Orchestration Engine
 * (Phase 2); Phase 1 stores and propagates the field correctly from day one.
 */
export type PrivacyLevel = "public" | "internal" | "confidential" | "highly_sensitive";
export type RequestingEngine = string;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * Event Bus RPC for voiceprint extraction (docs/design/phase-2d/
 * 03-perception-engine.md §0.2) -- `perception-engine`'s only legal path to a
 * speaker-embedding model, per ADR-020. Distinct from `ai_model.embed` (text
 * embedding, §10 of the Phase 2A design doc): a voice embedding takes raw
 * audio, never text, and the two are never interchangeable.
 */
export interface VoiceEmbedRequestPayload {
  audio_bytes: AudioBytes;
  audio_format?: AudioFormat;
  privacy_hint?: PrivacyLevel;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
