export type CapabilityId = string;
export type Operation = string;
export type RequestingEngine = string;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * Action-Principle-lifecycle stage 6, "Execute" -- invoke a resolved
 * capability's adapter. `capability-engine`'s own process performs the
 * real git/filesystem/terminal/http operation (Fork 3C-1's resolution);
 * the caller never receives adapter code, only a structured result.
 *
 * `operation`/`parameters` are deliberately adapter-agnostic (mirrors
 * `Capability.input_schema`/`output_schema` already being untyped
 * `dict`s rather than per-adapter fields) -- e.g. a `filesystem`
 * capability's `operation` might be `"read"`/`"write"`/`"list"`, a
 * `terminal` capability's might be `"execute"`. Exact per-adapter
 * operation vocabularies are adapter-implementation detail, not fixed
 * here (same discipline as every other new payload in this package).
 */
export interface CapabilityInvokeRequestPayload {
  capability_id: CapabilityId;
  operation: Operation;
  parameters?: Parameters;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
export interface Parameters {
  [k: string]: unknown;
}
