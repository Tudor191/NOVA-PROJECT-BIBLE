export type RequestingEngine = string;
export type RequestKind = string;
export type CorrelationId = string;
export type Urgency = number;
export type Importance = number;
export type Complexity = number;
export type Risk = number;
export type LearningValue = number;
export type ResourceCost = number;
export type UserImpact = number;
export type Deadline = string | null;
export type GoalId = string | null;
export type GoalTier = ("ad_hoc" | "established") | null;
export type SchemaVersion = number;

/**
 * Event Bus RPC counterpart to `POST /v1/executive/arbitrate` (design
 * doc Sec5.1-Sec5.2) -- submitted by a coordinated engine (AI Model
 * Orchestration Engine, Reasoning Engine, and in future phases Planning
 * Engine/NAOS, design doc Sec5.9-Sec5.10) before starting cognitive work
 * that would compete for a shared resource budget.
 */
export interface ExecutiveRequestPayload {
  requesting_engine: RequestingEngine;
  request_kind: RequestKind;
  correlation_id?: CorrelationId;
  urgency: Urgency;
  importance: Importance;
  complexity: Complexity;
  risk: Risk;
  learning_value: LearningValue;
  resource_cost: ResourceCost;
  user_impact: UserImpact;
  deadline?: Deadline;
  goal_id?: GoalId;
  goal_tier?: GoalTier;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
