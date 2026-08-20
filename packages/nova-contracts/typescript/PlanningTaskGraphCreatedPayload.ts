export type Id = string;
export type RootObjective = string;
export type Id1 = string;
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
export type Nodes = TaskNodeSnapshot[];
export type CriticalPath = string[];
export type ApprovedAt = string | null;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * TDD 3B §6.2: published on graph creation *and* on major mutation
 * (doc 10 row 6's own "creation/major mutation" wording) -- the same
 * subject and payload shape for both, distinguished only by whether
 * `graph.id` was already seen by a subscriber, not by a second subject.
 */
export interface PlanningTaskGraphCreatedPayload {
  graph: TaskGraphSnapshot;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
/**
 * Wire-shaped mirror of `nova_planning_engine.domain.models.TaskGraph`
 * at the moment of publication -- the full graph, not a delta, matching
 * every other "snapshot event" convention in this codebase (e.g.
 * `world_model.active_context.updated`).
 */
export interface TaskGraphSnapshot {
  id: Id;
  root_objective: RootObjective;
  nodes: Nodes;
  critical_path: CriticalPath;
  approved_at?: ApprovedAt;
  [k: string]: unknown;
}
/**
 * Wire-shaped mirror of `nova_planning_engine.domain.models.TaskNode`
 * (field-for-field), independently defined per this module's own
 * docstring -- never imports the domain type.
 */
export interface TaskNodeSnapshot {
  id: Id1;
  objective: Objective;
  depends_on?: DependsOn;
  assigned_agent_category?: AssignedAgentCategory;
  effort_hours: EffortHours;
  confidence: Confidence;
  risk: RiskLevel;
  status: Status;
  [k: string]: unknown;
}
