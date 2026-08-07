export type Module = string;
/**
 * Mirrors the module lifecycle states from Part 20's Module Lifecycle.
 */
export type ModuleStatus = "starting" | "healthy" | "degraded" | "down";
export type UptimeSeconds = number;
export type BootPhase = number | null;
export type SchemaVersion = number;

export interface HeartbeatPayload {
  module: Module;
  status: ModuleStatus;
  uptime_seconds: UptimeSeconds;
  boot_phase?: BootPhase;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
