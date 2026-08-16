export type CapabilityId = string;
export type RequestingEngine = string;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * Action-Principle-lifecycle stage 5, "Prepare Resources"
 * (docs/design/phase-3/07-tdd-3d-action-engine.md §6) -- resolve a
 * `Capability` by id and confirm `health_status`.
 */
export interface CapabilityResolveRequestPayload {
  capability_id: CapabilityId;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
