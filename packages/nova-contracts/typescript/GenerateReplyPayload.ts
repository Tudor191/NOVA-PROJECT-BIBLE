export type Text = string;
export type Id = string;
export type ToolName = string;
export type ToolCalls = ToolCallPayload[];
export type InputTokens = number;
export type OutputTokens = number;
export type FinishReason = "stop" | "length" | "tool_calls" | "error";
export type StructuralConfidence = number;
export type ModelId = string;
export type Provider = string;
export type Error = string | null;
export type SchemaVersion = number;

export interface GenerateReplyPayload {
  text: Text;
  tool_calls?: ToolCalls;
  input_tokens: InputTokens;
  output_tokens: OutputTokens;
  finish_reason: FinishReason;
  structural_confidence: StructuralConfidence;
  model_id: ModelId;
  provider: Provider;
  error?: Error;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
/**
 * A normalized tool-call request from a model's response, identical in
 * shape regardless of which connector produced it (ADR-023).
 */
export interface ToolCallPayload {
  id: Id;
  tool_name: ToolName;
  arguments: Arguments;
  [k: string]: unknown;
}
export interface Arguments {
  [k: string]: unknown;
}
