export type CorrelationId = string;
export type RequestingEngine = string;
export type AttemptedModelIds = string[];
export type FinalError = string;
export type SchemaVersion = number;

/**
 * Published when the fallback chain is exhausted with no candidate left
 * to try (design doc §7, §17).
 */
export interface RequestFailedPayload {
  correlation_id: CorrelationId;
  requesting_engine: RequestingEngine;
  attempted_model_ids: AttemptedModelIds;
  final_error: FinalError;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
