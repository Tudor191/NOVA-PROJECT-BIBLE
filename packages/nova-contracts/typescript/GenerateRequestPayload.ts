export type Source = string;
export type Text = string;
export type TokenEstimate = number;
export type Priority = number;
export type TruncationPolicy = "drop" | "truncate_end" | "summarize_external";
export type Context = ContextComponentPayload[];
export type Name = string;
export type Description = string;
export type Tools = ToolSchemaPayload[];
export type TaskType = string;
/**
 * Bible Part 7's privacy classification, propagated on every entity per
 * docs/design/phase-1/00-shared-foundations.md's "Confidence and privacy,
 * everywhere" convention. Enforcement point is the Model Orchestration Engine
 * (Phase 2); Phase 1 stores and propagates the field correctly from day one.
 */
export type PrivacyLevel = "public" | "internal" | "confidential" | "highly_sensitive";
export type RequestingEngine = string;
export type CorrelationId = string;
export type PreferredModelId = string | null;
export type MaxOutputTokens = number | null;
export type SchemaVersion = number;

/**
 * Event Bus RPC counterpart to `POST /v1/models/generate` (design doc §13,
 * §14) -- for callers that prefer request/reply over HTTP.
 */
export interface GenerateRequestPayload {
  context: Context;
  tools?: Tools;
  task_type?: TaskType;
  privacy_hint?: PrivacyLevel;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  preferred_model_id?: PreferredModelId;
  max_output_tokens?: MaxOutputTokens;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
/**
 * One pre-assembled, source-labeled block of context (design doc §0) --
 * this engine formats and fits these into a model's window; it never sources
 * them.
 */
export interface ContextComponentPayload {
  source: Source;
  text: Text;
  token_estimate: TokenEstimate;
  priority?: Priority;
  truncation_policy?: TruncationPolicy;
  [k: string]: unknown;
}
/**
 * A tool's name/description/parameters, supplied by the caller (design doc
 * §0's Function Registry boundary) -- this engine translates it into a
 * provider's wire format and back; it never knows what the tool does.
 */
export interface ToolSchemaPayload {
  name: Name;
  description: Description;
  parameters_json_schema: ParametersJsonSchema;
  [k: string]: unknown;
}
export interface ParametersJsonSchema {
  [k: string]: unknown;
}
