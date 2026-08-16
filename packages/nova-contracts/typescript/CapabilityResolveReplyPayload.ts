export type Found = boolean;
export type Id = string;
export type Name = string;
export type Description = string;
export type Category = string;
export type Version = string;
export type Dependencies = string[];
export type RequiredPermissions = string[];
export type RequiredResources = string[];
export type ExecutionAdapter = string;
export type HealthStatus = "unknown" | "healthy" | "degraded" | "unhealthy";
export type InstalledAt = string;
export type SchemaVersion = number;

export interface CapabilityResolveReplyPayload {
  found: Found;
  capability?: Capability | null;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
/**
 * TDD 3C §2.1's 13-field Phase-3-scoped subset of Bible Part 15's
 * 18-field Capability Object Model. `author`, `confidence`,
 * `performance_metrics`, `documentation`, `example_workflows`, and
 * `Supported Platforms` are explicitly deferred, not silently dropped.
 */
export interface Capability {
  id: Id;
  name: Name;
  description: Description;
  category: Category;
  version: Version;
  dependencies?: Dependencies;
  required_permissions: RequiredPermissions;
  required_resources?: RequiredResources;
  input_schema: InputSchema;
  output_schema: OutputSchema;
  execution_adapter: ExecutionAdapter;
  health_status: HealthStatus;
  installed_at: InstalledAt;
  [k: string]: unknown;
}
export interface InputSchema {
  [k: string]: unknown;
}
export interface OutputSchema {
  [k: string]: unknown;
}
