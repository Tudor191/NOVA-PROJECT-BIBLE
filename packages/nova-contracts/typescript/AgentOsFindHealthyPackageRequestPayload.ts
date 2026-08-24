export type Category = string;
export type RequestingEngine = string;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * Kernel Scheduler -> Registry: "query Registry for healthy candidates
 * in the required category" (TDD 3E §4, step 1), literally. Registry's own
 * `find_latest_by_category` port method (already built, Milestone 3)
 * answers this directly -- "candidates," scoped to Phase 3's one-healthy-
 * version-per-category reality, resolves to "the most recently installed
 * healthy row," not a list requiring a separate scoring step here.
 */
export interface AgentOsFindHealthyPackageRequestPayload {
  category: Category;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
