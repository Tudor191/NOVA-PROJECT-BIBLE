export type RunId = string;
export type SchemaVersion = number;

export interface ConsolidationStartedPayload {
  run_id: RunId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
