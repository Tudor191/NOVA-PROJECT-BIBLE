export type UserId = string | null;
export type Present = boolean;
export type Confidence = number;
/**
 * Matches `nova_perception_engine.domain.models.Source` exactly.
 */
export type PerceptionSource = "microphone" | "camera";
export type SchemaVersion = number;

/**
 * Matches `PresenceObservation`; wildcard-matched by World Model's
 * `perception.*.observed` subscription (`domain/context.py::
 * clear_present_identities`, `present=False` case).
 */
export interface PerceptionPresenceObservedPayload {
  user_id?: UserId;
  present: Present;
  confidence: Confidence;
  source: PerceptionSource;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
