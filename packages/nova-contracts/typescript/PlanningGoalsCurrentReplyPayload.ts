export type Id = string;
export type Description = string;
export type Priority = number;
export type GoalTier = "ad_hoc" | "established";
export type Goals = GoalSnapshot[];
export type SchemaVersion = number;

export interface PlanningGoalsCurrentReplyPayload {
  goals?: Goals;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
/**
 * TDD 3E §8, Fork 3E-3 (RESOLVED, approved as proposed) -- the wire
 * shape of one active `TaskGraph`, mapped to a `Goal`. Deliberately **not**
 * named `Goal` -- `reasoning-engine`'s and `executive-cognition-engine`'s
 * own domain-local `Goal` types have already diverged by one field
 * (`goal_tier`, per ADR-029) and neither imports this type or is imported
 * by it; each engine's own `clients/goals_client.py` adapter is what
 * translates a `GoalSnapshot` into that engine's own `Goal` at the RPC
 * boundary, the same wire-payload-to-domain-type translation pattern used
 * everywhere else in this codebase.
 *
 * `goal_tier` is derived by `planning-engine` at read time from
 * `len(task_graph.nodes) > 1`, never persisted (TDD 3B §6.2's own
 * additive note). `priority` is derived at read time from the requesting
 * user's full set of active `TaskGraph`s, ranked descending by
 * critical-path effort sum and tie-broken by `TaskGraph.id`:
 * `1.0 - (rank_index / max(1, len(active_task_graphs) - 1))`.
 */
export interface GoalSnapshot {
  id: Id;
  description: Description;
  priority: Priority;
  goal_tier: GoalTier;
  [k: string]: unknown;
}
