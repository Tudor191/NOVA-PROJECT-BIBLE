export type ModelId = string;
export type Name = string;
export type Provider = string;
export type SchemaVersion = number;

/**
 * Shared shape for `.registered`/`.deregistered` -- the two subjects differ
 * only in when they fire, the same convention as World Model's `WorldObjectChangedPayload`.
 */
export interface ModelRegistryChangedPayload {
  model_id: ModelId;
  name: Name;
  provider: Provider;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
