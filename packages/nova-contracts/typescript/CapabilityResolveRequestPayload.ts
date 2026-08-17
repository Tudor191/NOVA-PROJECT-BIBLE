export type CapabilityId = string | null;
export type Name = string | null;
export type RequestingEngine = string;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * Action-Principle-lifecycle stage 5, "Prepare Resources"
 * (docs/design/phase-3/07-tdd-3d-action-engine.md §6) -- resolve a
 * `Capability` by id or by name and confirm `health_status`.
 *
 * **Additive extension, Phase 3D research pass, approved
 * (`docs/design/phase-3/13-3d-action-engine-research.md` §5.1):**
 * `name` was added alongside the original `capability_id` so
 * `action-engine` can resolve `Action.execution_target` (a stable
 * capability name, e.g. `"git"`) without needing to know a
 * Postgres-generated `capability_id` in advance. Per ADR-024, adding a
 * field to an existing payload is never a version bump -- the original
 * by-id resolution path (every existing caller) is unaffected. Exactly
 * one of `capability_id`/`name` must be set; validated below.
 */
export interface CapabilityResolveRequestPayload {
  capability_id?: CapabilityId;
  name?: Name;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
