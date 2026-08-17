export type Outcome = "success" | "failure" | "sandbox_violation";
export type Result = {
  [k: string]: unknown;
} | null;
export type Error = string | null;
export type SchemaVersion = number;

export interface CapabilityInvokeReplyPayload {
  outcome: Outcome;
  result?: Result;
  error?: Error;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
