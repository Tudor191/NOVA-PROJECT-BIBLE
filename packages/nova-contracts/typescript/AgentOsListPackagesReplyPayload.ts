export type Id = string;
export type Category = string;
export type Version = string;
export type HealthStatus = string;
export type Packages = AgentPackageSnapshot[];
export type SchemaVersion = number;

/**
 * Every installed `agent_package` row, as the same
 * `AgentPackageSnapshot` the dispatch RPC already returns -- no second
 * wire shape for the same entity.
 *
 * An **empty list means Registry is healthy and has nothing installed.**
 * It never means Registry could not be reached: an unreachable Registry
 * raises at the caller (`RegistryClient` does not catch), which is what
 * lets `GET /v1/agents` answer 503 rather than a misleading empty 200
 * (decision **D-1**, approved 2026-09-08). The distinction is asserted by
 * `agent-os/kernel`'s own client tests, not left to documentation.
 */
export interface AgentOsListPackagesReplyPayload {
  packages?: Packages;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
/**
 * Wire-shaped mirror of `agent-os/registry`'s own `AgentPackage` domain
 * model (repository-internal, never itself published) -- the shape a
 * Scheduler needs to select and load a candidate. `id` is the surrogate
 * UUID primary key (per `docs/design/phase-3/
 * 15-3e-supervisor-reconciliation.md` §A), carried here so the Kernel
 * Scheduler can populate `agent_instance.agent_package_id` (TDD 3E §4, an
 * already-approved FK-shaped column) with the exact installed row it
 * dispatched against, not merely `category`/`version`. `category`/
 * `version` remain the natural key; `manifest_json` is what the Scheduler
 * reads the manifest's own `id` (e.g. `"research-agent"`) from, to resolve
 * `agents/<id>/src/handler.py` on disk -- the same filesystem-based
 * discovery convention doc 12 §6/§15 already establishes for Registry's
 * own install pipeline, applied here at dispatch time instead of install
 * time.
 */
export interface AgentPackageSnapshot {
  id: Id;
  category: Category;
  version: Version;
  manifest_json: ManifestJson;
  health_status: HealthStatus;
  [k: string]: unknown;
}
export interface ManifestJson {
  [k: string]: unknown;
}
