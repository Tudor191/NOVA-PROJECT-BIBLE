export type UserId = string;
export type SchemaVersion = number;

/**
 * Design doc Sec0.6 -- defined now per ADR-024 versioning discipline;
 * no Phase 2D-A code path calls it. Real integration arrives in Phase
 * 2D-C, once `digital-twin-engine` (Phase 2D-D) exists.
 */
export interface DigitalTwinPreferencesGetRequestPayload {
  user_id: UserId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
