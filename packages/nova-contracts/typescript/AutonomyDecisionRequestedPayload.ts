export type ThoughtId = string;
/**
 * Bible Part 14 "PERMISSION MATRIX" -- the ten categories, verbatim and in
 * the Bible's own order. `autonomy-engine`'s `PERMISSION_CATEGORY_ORDER` pins
 * the ordering separately because `StrEnum` membership alone would let a later
 * edit reorder them silently.
 *
 * *(Defined in `nova_autonomy_engine.domain.models` until Phase 4F.6, and
 * moved rather than copied -- A-4F6-2b. There is exactly one definition.)*
 */
export type PermissionCategory =
  "read" | "analyze" | "recommend" | "create" | "modify" | "delete" | "execute" | "deploy" | "purchase" | "communicate";
/**
 * Bible Part 14's risk classification scale
 * (`docs/bible/part-14-autonomy-engine.md:271-279`), reused verbatim --
 * the one canonical risk-tier scale anywhere in this project, rather than
 * a second, `planning-engine`-specific scale that `action-engine` (TDD 3D)
 * would otherwise have to reinterpret or map.
 */
export type RiskLevel = "negligible" | "low" | "moderate" | "high" | "critical";
export type ActionType = "terminal" | "filesystem";
export type ExecutionTarget = string;
export type VerificationMethod = string;
export type Title = string;
export type Detail = string;
export type Priority = number;
export type RequestingEngine = string;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * A thought's authored `ProposedAction`, offered to `autonomy-engine` for a
 * decision. **A request, never an authorization**: every gate 4F.5 built runs
 * on it exactly as on any other `DecisionRequest`.
 *
 * **Two fields are absent on purpose, and a test pins both -- and unknown
 * fields are rejected, so neither can be smuggled in:**
 *
 * * **No `subject_id`.** The decision's identity is derived by the consumer
 *   as `uuid5(namespace, str(envelope.event_id))` (A-4F6-3). A producer that
 *   could name it could collide with -- or replay -- a decision it did not
 *   make.
 * * **No `user_id`.** Identity is resolved server-side from
 *   `primary_user_id` (TDD 4F §12); a caller-supplied `user_id` would be a
 *   privilege-escalation surface.
 *
 * `category`, `risk` and the three execution fields are **authored** on the
 * thought and copied verbatim. `action_type` is the `action.execute` literal,
 * so a value `action-engine` could never run is rejected **here**, at the
 * contract boundary, instead of reaching dispatch.
 *
 * **`extra="forbid"`** -- TDD 4F.6 §9 (*"Producer-supplied `user_id`:
 * **Rejected**"*) and §10's negative tier. A payload naming `user_id` or
 * `subject_id` fails validation, so `decide()` is never reached with it.
 * Ignoring the field silently would leave a producer believing it had steered
 * something; `autonomy-engine`'s own `api/schemas.py` `_Strict` base already
 * takes this position for its HTTP bodies.
 */
export interface AutonomyDecisionRequestedPayload {
  thought_id: ThoughtId;
  category: PermissionCategory;
  risk: RiskLevel;
  action_type: ActionType;
  execution_target: ExecutionTarget;
  verification_method: VerificationMethod;
  title: Title;
  detail?: Detail;
  priority?: Priority;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
}
