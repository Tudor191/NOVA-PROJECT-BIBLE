export type ActionId = string;
export type Risk = string;
export type RequestedAt = string;
export type SchemaVersion = number;

/**
 * TDD 3D §4 point 2 -- published, new Phase-3-owned namespace. **Never
 * `autonomy.approval.requested`**, which stays reserved, undefined, for
 * `autonomy-engine` to claim in Phase 4 (Fork E2's resolution).
 */
export interface ActionApprovalRequestedPayload {
  action_id: ActionId;
  risk: Risk;
  requested_at: RequestedAt;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
