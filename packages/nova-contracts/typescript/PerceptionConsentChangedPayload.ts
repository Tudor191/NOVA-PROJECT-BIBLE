export type UserId = string;
export type Source = string;
export type Granted = boolean;
export type SchemaVersion = number;

/**
 * Doc 22 Principle 8 -- explicit per-source consent, revocable at any
 * time with immediate effect.
 */
export interface PerceptionConsentChangedPayload {
  user_id: UserId;
  source: Source;
  granted: Granted;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
