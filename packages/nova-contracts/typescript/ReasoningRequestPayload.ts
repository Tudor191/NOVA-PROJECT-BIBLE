export type ObjectiveText = string;
export type UserId = string;
export type RequestingEngine = string;
export type CorrelationId = string;
/**
 * Design doc §6's ten reasoning-mode taxonomy.
 */
export type ReasoningMode =
  | "reactive"
  | "analytical"
  | "strategic"
  | "long_term_planning"
  | "goal_driven"
  | "constraint_based"
  | "multi_step"
  | "reflective"
  | "self_evaluation"
  | "collaborative";
export type ReasoningLevelHint = number | null;
export type ThinkingModeHint = string | null;
export type Id = string;
export type Description = string;
export type Priority = number;
export type Goals = GoalPayload[];
/**
 * Design doc §9's constraint sources.
 */
export type ConstraintKind = "budget" | "privacy" | "time" | "resource" | "policy";
export type Description1 = string;
export type Hard = boolean;
export type Constraints = ConstraintPayload[];
export type ParentProcessId = string | null;
export type SchemaVersion = number;

/**
 * Event Bus RPC counterpart to `POST /v1/reasoning/reason` (design doc
 * §23) -- for callers (e.g. a future Planning Engine, §7.1) that prefer
 * request/reply over HTTP.
 */
export interface ReasoningRequestPayload {
  objective_text: ObjectiveText;
  user_id: UserId;
  requesting_engine: RequestingEngine;
  correlation_id?: CorrelationId;
  reasoning_mode_hint?: ReasoningMode | null;
  reasoning_level_hint?: ReasoningLevelHint;
  thinking_mode_hint?: ThinkingModeHint;
  goals?: Goals;
  constraints?: Constraints;
  parent_process_id?: ParentProcessId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
/**
 * Design doc §8 -- one Current Goal, as read from `GoalsPort`
 * (a caller-supplied placeholder until Planning Engine exists, §7.1).
 */
export interface GoalPayload {
  id: Id;
  description: Description;
  priority: Priority;
  [k: string]: unknown;
}
/**
 * Design doc §9 -- a hard gate applied before scoring, never blended into
 * the Decision Matrix. `hard=False` constraints instead contribute a scoring
 * penalty (not implemented as a gate) -- see design doc §9.
 */
export interface ConstraintPayload {
  kind: ConstraintKind;
  description: Description1;
  hard?: Hard;
  [k: string]: unknown;
}
