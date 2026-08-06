export type AudioBytes = string;
export type AudioFormat = "wav" | "opus" | "pcm16";
export type StructuralConfidence = number;
export type ModelId = string;
export type Provider = string;
export type Error = string | null;
export type SchemaVersion = number;

export interface SynthesizeReplyPayload {
  audio_bytes: AudioBytes;
  audio_format: AudioFormat;
  structural_confidence: StructuralConfidence;
  model_id: ModelId;
  provider: Provider;
  error?: Error;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
