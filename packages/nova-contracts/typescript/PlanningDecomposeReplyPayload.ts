export type AlreadyMinimal = boolean;
export type Id = string;
export type Objective = string;
export type DependsOn = string[];
export type AssignedAgentCategory = string | null;
export type EffortHours = number;
export type Confidence = number;
/**
 * Bible Part 14's risk classification scale
 * (`docs/bible/part-14-autonomy-engine.md:271-279`), reused verbatim --
 * the one canonical risk-tier scale anywhere in this project, rather than
 * a second, `planning-engine`-specific scale that `action-engine` (TDD 3D)
 * would otherwise have to reinterpret or map.
 */
export type RiskLevel = "negligible" | "low" | "moderate" | "high" | "critical";
export type Status = "pending" | "ready" | "running" | "blocked" | "completed" | "failed";
export type NewNodes = TaskNodeSnapshot[];
export type SchemaVersion = number;

/**
 * `already_minimal=True` and `new_nodes=[]` together are TDD 3B §8's
 * own explicitly-required "already minimal" case -- a structured,
 * distinguishable reply, never a silent no-op indistinguishable from
 * success.
 */
export interface PlanningDecomposeReplyPayload {
  already_minimal: AlreadyMinimal;
  new_nodes?: NewNodes;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
/**
 * Wire-shaped mirror of `nova_planning_engine.domain.models.TaskNode`
 * (field-for-field), independently defined per this module's own
 * docstring -- never imports the domain type.
 */
export interface TaskNodeSnapshot {
  id: Id;
  objective: Objective;
  depends_on?: DependsOn;
  assigned_agent_category?: AssignedAgentCategory;
  effort_hours: EffortHours;
  confidence: Confidence;
  risk: RiskLevel;
  status: Status;
  [k: string]: unknown;
}
