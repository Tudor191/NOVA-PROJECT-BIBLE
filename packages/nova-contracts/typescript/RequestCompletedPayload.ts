export type CorrelationId = string;
export type RequestingEngine = string;
export type Provider = string;
export type ModelId = string;
export type InputTokens = number;
export type OutputTokens = number;
export type EstimatedCost = number;
export type LatencyMs = number;
export type RetryCount = number;
export type FallbackUsed = boolean;
/**
 * Mirrors `UsageRecord.outcome` (design doc §4) -- a closed set describing
 * how a routed request concluded, independent of the connector-specific
 * reason why.
 */
export type RequestOutcome = "success" | "fallback" | "failed";
export type SchemaVersion = number;

/**
 * Published after every successful (including fallback-recovered) request
 * -- the event-bus mirror of the `usage_record` row `UsageRepository.
 * record_usage` persists (ADR-021's mandated structured telemetry).
 */
export interface RequestCompletedPayload {
  correlation_id: CorrelationId;
  requesting_engine: RequestingEngine;
  provider: Provider;
  model_id: ModelId;
  input_tokens: InputTokens;
  output_tokens: OutputTokens;
  estimated_cost: EstimatedCost;
  latency_ms: LatencyMs;
  retry_count?: RetryCount;
  fallback_used?: FallbackUsed;
  outcome: RequestOutcome;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
