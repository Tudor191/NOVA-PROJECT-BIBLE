export type Matched = boolean;
export type Confidence = number;
export type SchemaVersion = number;

/**
 * Deliberately subject-named `.detected`, not `.observed` (design doc
 * Sec13.2) -- never matches World Model's `perception.*.observed`
 * wildcard.
 */
export interface PerceptionWakeDetectedPayload {
  matched: Matched;
  confidence: Confidence;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
