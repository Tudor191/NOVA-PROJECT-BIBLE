export type Module = string;
/**
 * Mirrors the module lifecycle states from Part 20's Module Lifecycle.
 */
export type ModuleStatus = "starting" | "healthy" | "degraded" | "down";
export type Reason = string | null;
export type SchemaVersion = number;

export interface ModuleStatusChangedPayload {
  module: Module;
  previous_status?: ModuleStatus | null;
  status: ModuleStatus;
  reason?: Reason;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
