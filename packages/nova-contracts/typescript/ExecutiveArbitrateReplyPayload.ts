export type CorrelationId = string;
export type ExecutiveDecisionId = string;
/**
 * Design doc Sec4 -- the four outcomes every arbitration produces.
 */
export type ArbitrationOutcome = "proceed" | "proceed_reduced" | "wait" | "escalated";
export type RetryAfterMs = number | null;
export type ReducedBudgetHint = number | null;
export type Urgency = number;
export type Importance = number;
export type Complexity = number;
export type Risk = number;
export type LearningValue = number;
export type ResourceCost = number;
export type UserImpact = number;
export type LongTermAlignment = number;
export type Composite = number;
export type Error = string | null;
export type SchemaVersion = number;

export interface ExecutiveArbitrateReplyPayload {
  correlation_id: CorrelationId;
  executive_decision_id: ExecutiveDecisionId;
  outcome: ArbitrationOutcome;
  retry_after_ms?: RetryAfterMs;
  reduced_budget_hint?: ReducedBudgetHint;
  priority_score: CognitivePriorityScore;
  error?: Error;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
/**
 * Design doc Sec6, Sec6.1 -- the eight-factor Cognitive Priority Matrix
 * breakdown for one contending request. The first seven factors are
 * caller-supplied on `ExecutiveRequestPayload`; `long_term_alignment` and
 * `composite` are computed by this engine itself, never invented by a
 * caller (ADR-028's epistemic-deference boundary applies to the seven
 * caller-supplied factors -- this engine trusts what it's told about a
 * request's own urgency/importance/etc., but the alignment and composite
 * scores are its own structural arithmetic, not another engine's
 * assertion).
 */
export interface CognitivePriorityScore {
  urgency: Urgency;
  importance: Importance;
  complexity: Complexity;
  risk: Risk;
  learning_value: LearningValue;
  resource_cost: ResourceCost;
  user_impact: UserImpact;
  long_term_alignment: LongTermAlignment;
  composite: Composite;
  [k: string]: unknown;
}
