export type AudioBytes = string;
export type AudioFormat = "wav" | "opus" | "pcm16";
export type LanguageHint = string | null;
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
 * Event Bus RPC for speech-to-text (docs/design/phase-2d/
 * 01-communication-engine.md §0.3) -- `communication-engine`'s only legal path
 * to a speech provider, per ADR-020. Non-streaming: transcription operates on
 * one bounded utterance per call (the caller decides utterance boundaries via
 * its own Transport VAD), never a transport-level stream.
 */
export interface TranscribeRequestPayload {
  audio_bytes: AudioBytes;
  audio_format?: AudioFormat;
  language_hint?: LanguageHint;
  privacy_hint?: PrivacyLevel;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
