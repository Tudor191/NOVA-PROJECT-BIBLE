export type GazeDirection = "toward_device" | "away" | "unknown";
export type StructuralConfidence = number;
export type ModelId = string;
export type Provider = string;
export type Error = string | null;
export type SchemaVersion = number;

export interface GazeEstimateReplyPayload {
  gaze_direction: GazeDirection;
  structural_confidence: StructuralConfidence;
  model_id: ModelId;
  provider: Provider;
  error?: Error;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
