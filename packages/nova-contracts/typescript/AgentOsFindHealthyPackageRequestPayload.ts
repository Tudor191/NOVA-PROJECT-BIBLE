export type Category = string;
export type RequestingEngine = string;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * Kernel Scheduler -> Registry: "query Registry for healthy candidates
 * in the required category" (TDD 3E §4, step 1), literally. Registry
 * answers with a single winner rather than a list: it reads every
 * installed row for the category and applies its own
 * `domain/selection.py::select_dispatch_version` policy -- the highest
 * **healthy** version by dotted-integer comparison, falling back to the
 * highest healthy older version when the newest is not healthy (TDD 3E
 * §14 acceptance criterion #3, approved 2026-08-28; full record in
 * `docs/design/phase-3/16-3e-hot-load-design-decision.md`). Doc 12 §6's
 * richer scoring inputs (historical success rate, average execution time,
 * resource efficiency) have no persistence in Phase 3, so version and
 * health are the only selection inputs today -- a disclosed, unchanged
 * gap, not a silent simplification.
 */
export interface AgentOsFindHealthyPackageRequestPayload {
  category: Category;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
