export type Passed = boolean;
export type AdjustedContent = string | null;
/**
 * Design doc Sec4's four validator check families.
 */
export type ViolationCheckFamily =
  "confidence_language" | "forbidden_pattern" | "emotional_stability" | "professionalism_floor";
export type Detail = string;
export type Violations = ViolationRecordPayload[];
export type SchemaVersion = number;

export interface PersonalityValidateResponseReplyPayload {
  passed: Passed;
  adjusted_content?: AdjustedContent;
  violations?: Violations;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
/**
 * One entry in a `ValidationResult.violations` list (design doc Sec4,
 * Sec9's `validation_audit` table).
 */
export interface ViolationRecordPayload {
  check_family: ViolationCheckFamily;
  detail: Detail;
  [k: string]: unknown;
}
