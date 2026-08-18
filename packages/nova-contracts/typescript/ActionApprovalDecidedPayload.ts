export type ActionId = string;
export type Decision = "approved" | "denied";
export type DecidedAt = string;
export type Reason = string | null;
export type SchemaVersion = number;

/**
 * TDD 3D §4 point 5 -- published, new Phase-3-owned namespace. **Never
 * `autonomy.decision.made`**, which stays reserved for Phase 4.
 */
export interface ActionApprovalDecidedPayload {
  action_id: ActionId;
  decision: Decision;
  decided_at: DecidedAt;
  reason?: Reason;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
