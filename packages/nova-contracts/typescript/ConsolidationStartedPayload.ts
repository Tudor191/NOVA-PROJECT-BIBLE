export type RunId = string;

export interface ConsolidationStartedPayload {
  run_id: RunId;
  [k: string]: unknown;
}
