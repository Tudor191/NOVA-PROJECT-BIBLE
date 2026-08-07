export type Verbosity = string | null;
export type TechnicalDepth = string | null;
export type TerminologyPreference = {
  [k: string]: unknown;
} | null;
export type Source = string;
export type SchemaVersion = number;

/**
 * Inbound from `digital-twin-engine` once it exists (Phase 2D-D) --
 * design doc Sec0.2, Sec7.2, ADR-030. Defined now, per ADR-024 versioning
 * discipline, unused until Phase 2D-D ships; this engine's own Personality
 * Memory (design doc Sec6) is a static default until then.
 */
export interface PersonalityMemoryUpdatePayload {
  verbosity?: Verbosity;
  technical_depth?: TechnicalDepth;
  terminology_preference?: TerminologyPreference;
  source?: Source;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
