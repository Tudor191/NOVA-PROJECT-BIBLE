export type AudioBytes = string;
export type AudioFormat = "wav" | "opus" | "pcm16";
export type WakePhrase = string | null;
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
 * Event Bus RPC for wake-phrase detection (docs/design/phase-2d/
 * 03-perception-engine.md §0.2) -- `perception-engine`'s only legal path to a
 * wake-word-spotting model, per ADR-020. Non-streaming: one bounded audio
 * window per call, the same "caller owns chunking" boundary
 * `TranscribeRequestPayload` already keeps.
 */
export interface WakePhraseDetectRequestPayload {
  audio_bytes: AudioBytes;
  audio_format?: AudioFormat;
  wake_phrase?: WakePhrase;
  privacy_hint?: PrivacyLevel;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
