export type TaskNodeId = string;
export type AgentInstanceId = string;
export type Outcome = "success" | "failure" | "needs_revision" | "interrupted";
export type Result = {
  [k: string]: unknown;
} | null;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * TDD 3E §10 -- new subject, owned by `agent-os/kernel`; `TDD 3B` §6.1
 * already names `planning-engine` as this subject's consumer ("mutate the
 * corresponding `TaskNode.status`"), field-level shape not previously
 * defined anywhere (confirmed: no payload existed under this subject
 * before this module, `agent_os.task.completed` was absent from every
 * engine's `events/published.py`/`subscribed.py`, including
 * `planning-engine`'s own -- `05-tdd-3b-planning-engine.md` §6.1's claim
 * that a handler "is defined and tested now" does not match the merged
 * `phase-3b-planning-persistence` code, a real, disclosed staleness in
 * that document, not a design ambiguity: the intended behavior was never
 * in question, only the field shape and the fact of non-implementation).
 *
 * `outcome` extends `AgentResult.status`'s vocabulary (`entities.py`)
 * with `"interrupted"` -- the one outcome an `AgentResult` itself can
 * never carry, since it is produced only by a live `execute()` call.
 * `"interrupted"` is exclusively for Kernel-restart reconciliation (TDD
 * 3E §4/§12): a Kernel process restart finds `agent_instance` rows still
 * `status="running"` whose actual `inprocess` asyncio task died with the
 * old process -- there is no `AgentResult` to report, only the fact that
 * the assignment was lost and the `TaskNode` must revert to `"ready"` for
 * redispatch, never left `"running"` forever.
 *
 * `planning-engine`'s own consumption of this subject is intentionally
 * not built by this change (`agent-os/kernel`'s milestone 2 slice) --
 * "real code, no real caller yet" is this project's own established
 * idiom (`GoalsPort`/`DigitalTwinPort`/Fork D precedent, TDD 3B §6.1's
 * own words), and wiring the consumer side is `planning-engine`'s
 * separate, disclosed follow-up.
 */
export interface AgentOsTaskCompletedPayload {
  task_node_id: TaskNodeId;
  agent_instance_id: AgentInstanceId;
  outcome: Outcome;
  result?: Result;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
