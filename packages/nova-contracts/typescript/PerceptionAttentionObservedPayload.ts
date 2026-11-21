export type IdentityId = string | null;
/**
 * Matches `AttentionObservation.attention_state`'s existing `Literal`
 * exactly.
 */
export type AttentionState = "engaged" | "disengaged" | "unknown";
/**
 * Matches `AttentionObservation.gaze_direction`'s existing `Literal`
 * exactly.
 */
export type GazeDirection = "toward_device" | "away" | "unknown";
export type Confidence = number;
export type SchemaVersion = number;

/**
 * Matches `AttentionObservation` -- a candidate signal for addressee
 * detection (design doc Sec10), never a verdict.
 */
export interface PerceptionAttentionObservedPayload {
  identity_id?: IdentityId;
  attention_state: AttentionState;
  gaze_direction: GazeDirection;
  confidence: Confidence;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
