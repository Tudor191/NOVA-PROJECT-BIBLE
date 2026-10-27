export type UserId = string;
export type IdentityId = string | null;
export type Confidence = number;
/**
 * Mirrors Doc 23 Sec5.2's four confidence levels -- caller-supplied
 * (epistemic deference, ADR-028's pattern applied here per design doc
 * Sec4): this engine cross-checks phrasing against the tier, it never
 * re-derives the tier itself.
 */
export type ConfidenceTier = "high" | "medium" | "low" | "unknown";
export type ModalitySummary = string;
export type SchemaVersion = number;

/**
 * Matches `IdentityConfidenceState`, published only on a
 * `smoothed_tier` change, not every correlation window (design doc
 * Sec13.2); wildcard-matched by World Model's `perception.*.observed`
 * subscription (`domain/context.py::upsert_present_identity`).
 */
export interface PerceptionIdentityObservedPayload {
  user_id: UserId;
  identity_id?: IdentityId;
  confidence: Confidence;
  confidence_tier: ConfidenceTier;
  modality_summary: ModalitySummary;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
