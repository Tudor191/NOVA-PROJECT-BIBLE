export type ActionId = string;
export type Status =
  "pending" | "approval_required" | "approved" | "denied" | "executing" | "completed" | "failed" | "rolled_back";
export type Result = {
  [k: string]: unknown;
} | null;
export type Error = string | null;
export type SchemaVersion = number;

/**
 * TDD 3D §6 stage 11, "Report Outcome" -- also this RPC's reply
 * payload (§5). A repeat `action.execute` for an already-terminal
 * `action_id` (§5.3's idempotency guard) returns this same payload from
 * the original attempt, unmodified -- never a second, possibly-different
 * result.
 */
export interface ActionResultPayload {
  action_id: ActionId;
  status: Status;
  result?: Result;
  error?: Error;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
