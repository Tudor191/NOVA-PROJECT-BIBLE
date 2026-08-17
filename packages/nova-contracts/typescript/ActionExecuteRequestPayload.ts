export type ActionId = string;
export type ActionType = "terminal" | "filesystem";
/**
 * Bible Part 12's own 6-tier scheduling-priority scale
 * (`part-12-action-engine.md:473-489`) -- architecturally independent of
 * `RiskLevel` (risk = how dangerous an action is; priority = how urgently
 * it should be scheduled). A Background-priority action can still be
 * Critical-risk, and vice versa (TDD 3D §3.3).
 */
export type ActionPriority = "emergency" | "critical" | "high" | "normal" | "low" | "background";
export type Source = string;
export type RequestedBy = string;
export type ExecutionTarget = string;
export type DependsOn = string[];
export type ExpectedResult = string | null;
export type TimeoutSeconds = number;
export type MaxRetries = number;
export type BackoffSeconds = number;
export type Kind = "restore_file" | "undo_configuration" | "restart_service" | "manual";
export type Detail = string | null;
export type RequiredPermissions = string[];
export type VerificationMethod = string;
export type RequestingEngine = string;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * Doc 10 row 7: *"an agent instance (via its Supervisor) ->
 * `action.execute`"* -- served now, no real caller until Phase 3E (TDD
 * 3D §5). `action_id` is caller-supplied (not server-generated) -- this
 * is what natural-key idempotency on `Action.id` (approved,
 * `13-3d-action-engine-research.md` §5.3) is built on: a genuine retry
 * supplies the same `action_id` as the original attempt.
 *
 * `risk`/`status`/`confidence` are deliberately absent -- these are
 * server-computed by the Action Principle lifecycle's own stages
 * (Estimate Risk, stage 4; ongoing status transitions), never
 * caller-supplied.
 */
export interface ActionExecuteRequestPayload {
  action_id: ActionId;
  action_type: ActionType;
  priority: ActionPriority;
  source: Source;
  requested_by: RequestedBy;
  execution_target: ExecutionTarget;
  depends_on?: DependsOn;
  parameters?: Parameters;
  expected_result?: ExpectedResult;
  timeout_seconds?: TimeoutSeconds;
  retry_policy?: RetryPolicy;
  rollback_strategy?: RollbackStrategy | null;
  required_permissions?: RequiredPermissions;
  verification_method: VerificationMethod;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
export interface Parameters {
  [k: string]: unknown;
}
/**
 * TDD 3D §3.1 -- Bible names the field, not a schema; proposed here,
 * ratified by the Phase 3D research/approval pass.
 */
export interface RetryPolicy {
  max_retries?: MaxRetries;
  backoff_seconds?: BackoffSeconds;
  [k: string]: unknown;
}
/**
 * TDD 3D §3.1 -- Bible gives six examples (`part-12-action-engine.md:275-285`),
 * no enum; proposed here, ratified by the Phase 3D research/approval pass.
 * The *mechanism* behind `"restore_file"` (read-before-write via
 * `action-engine`'s own `CapabilityPort`, Fork 3C-3's resolution) is
 * concrete; this model itself is unaffected by that resolution.
 */
export interface RollbackStrategy {
  kind: Kind;
  detail?: Detail;
  [k: string]: unknown;
}
