export type PredictionId = string;
export type UserId = string;
export type Prediction = string;
export type Confidence = number;
export type PredictedFor = string | null;
export type SchemaVersion = number;

export interface PredictionPayload {
  prediction_id: PredictionId;
  user_id: UserId;
  prediction: Prediction;
  confidence: Confidence;
  predicted_for?: PredictedFor;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
