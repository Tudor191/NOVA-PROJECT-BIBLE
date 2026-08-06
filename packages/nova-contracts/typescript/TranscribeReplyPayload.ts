export type Text = string;
export type DetectedLanguage = string | null;
export type StructuralConfidence = number;
export type ModelId = string;
export type Provider = string;
export type Error = string | null;
export type SchemaVersion = number;

export interface TranscribeReplyPayload {
  text: Text;
  detected_language?: DetectedLanguage;
  structural_confidence: StructuralConfidence;
  model_id: ModelId;
  provider: Provider;
  error?: Error;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
