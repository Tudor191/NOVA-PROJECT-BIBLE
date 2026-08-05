export type ModelId = string;
/**
 * Mirrors `ModelDescriptor.health_status` (design doc §4).
 */
export type ModelHealthStatus = "healthy" | "degraded" | "unhealthy" | "unknown";
export type SchemaVersion = number;

export interface ModelHealthChangedPayload {
  model_id: ModelId;
  previous_status: ModelHealthStatus;
  new_status: ModelHealthStatus;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
