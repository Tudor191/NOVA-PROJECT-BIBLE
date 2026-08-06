export type Text = string;
export type VoiceProfile = string | null;
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
 * Event Bus RPC for text-to-speech (docs/design/phase-2d/
 * 01-communication-engine.md §0.3). Non-streaming, the same reason as
 * `TranscribeRequestPayload` -- `EventBus.request()` returns a single
 * `EventEnvelope`, never a stream (per `nova_ai_model_orchestration_engine.
 * domain.ports.ModelConnector.synthesize_stream`'s own docstring).
 * `communication-engine` achieves perceived streaming by calling this RPC
 * once per response chunk (sentence/phrase), not by streaming one call.
 */
export interface SynthesizeRequestPayload {
  text: Text;
  voice_profile?: VoiceProfile;
  audio_format?: AudioFormat;
  privacy_hint?: PrivacyLevel;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
