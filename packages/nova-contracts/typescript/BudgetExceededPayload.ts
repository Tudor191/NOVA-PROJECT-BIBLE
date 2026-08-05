/**
 * Mirrors `Budget.scope` (design doc §4) -- what a spending limit applies to.
 */
export type BudgetScope = "global" | "provider" | "model";
export type ScopeRef = string | null;
export type LimitAmount = number;
export type CurrentSpend = number;
export type SchemaVersion = number;

export interface BudgetExceededPayload {
  scope: BudgetScope;
  scope_ref?: ScopeRef;
  limit_amount: LimitAmount;
  current_spend: CurrentSpend;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
