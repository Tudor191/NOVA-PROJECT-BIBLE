export type FailedInstanceId = string;
export type RestartStrategy = "one_for_one" | "one_for_all" | "rest_for_one";
export type Id = string;
export type Category = string;
export type RestartStrategy1 = "one_for_one" | "one_for_all" | "rest_for_one";
export type StartedOrder = number;
export type Status = "running" | "completed" | "failed";
export type Siblings = SupervisedInstanceSnapshot[];
export type RequestingEngine = string;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * Kernel -> Supervisors: "owning Supervisor applies its configured
 * restart strategy" (TDD 3E §12's failure table, doc 12 §9). `siblings`
 * includes the failed instance itself (mirrors `plan_restart()`'s own
 * parameter contract).
 */
export interface AgentOsRestartPlanRequestPayload {
  failed_instance_id: FailedInstanceId;
  restart_strategy: RestartStrategy;
  siblings?: Siblings;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
/**
 * Wire-shaped mirror of `agent-os/supervisors`'s own `SupervisedInstance`
 * domain model (field-for-field) -- the minimum a Supervisor needs to run
 * its already-built `domain/restart.py::plan_restart()` for a real failure,
 * crossing the wire because ADR-004 forbids Kernel from importing
 * `nova_agent_os_supervisors` internals directly.
 */
export interface SupervisedInstanceSnapshot {
  id: Id;
  category: Category;
  restart_strategy: RestartStrategy1;
  started_order: StartedOrder;
  status: Status;
  [k: string]: unknown;
}
