export type AgentInstanceId = string;
export type TaskNodeId = string;
export type Status = "success" | "failure" | "needs_revision";
export type Confidence = number | null;
export type SelfValidationPassed = boolean;
export type CorrelationId = string;
export type ReviewerCategory = string;
export type ReviewerAvailable = boolean;
export type RequestingEngine = string;
export type CorrelationId1 = string;
export type SchemaVersion = number;

/**
 * Kernel -> Supervisors, disclosed addition (coding-agent slice):
 * doc 12 §9's peer review is "implemented once at the Supervisor level,"
 * including "recorded to Decision Memory either way" (§9 also covers
 * conflict resolution with that exact phrase) -- but only Kernel holds an
 * `AgentExecutionBackend` able to actually spawn a reviewer instance
 * (Phase 3's synchronous `inprocess` backend has no live, addressable
 * instance for `agent-os/supervisors`' own already-built
 * `AgentInstancePort.deliver()` to reach, see `agent-os/kernel/src/
 * nova_agent_os_kernel/domain/execution_backend.py`'s own module
 * docstring for the full disclosure). Kernel therefore performs the
 * mechanical work (resolve a healthy reviewer package via Registry,
 * `spawn_and_review()` it) and reports the raw outcome here so the
 * Supervisor -- not Kernel -- still makes the accept/reject
 * classification and Decision Memory recording, matching doc 12 §9's
 * ownership split even though the *delivery* mechanism differs from a
 * live Agent Mailbox `send()`.
 *
 * `reviewer_result=None, reviewer_available=False` covers both a real
 * RPC-level timeout and "no healthy package installed for
 * `reviewer_category` yet" (e.g. `coding-agent` validated before
 * `architect-agent` exists) -- TDD 3E §12 names only `"timed_out"` as the
 * disclosed non-fatal outcome for an unreachable reviewer; both cases are
 * modeled as that same outcome here rather than inventing a second value
 * for what is, from the primary result's perspective, an identical
 * "could not get a real review" fact.
 */
export interface AgentOsPeerReviewRequestPayload {
  primary_result: AgentResult;
  reviewer_category: ReviewerCategory;
  reviewer_result?: AgentResult | null;
  reviewer_available: ReviewerAvailable;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId1;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
/**
 * TDD 3E §6, Fork 3E-1 (RESOLVED, approved as proposed) -- what a
 * Supervisor collects for the primary result AND for every peer-review
 * round (`PEER_REVIEW_RESULT`). In-process by default (a Supervisor
 * collects it directly from `execute()`'s return value); also carried
 * inside an `AgentMessage.payload` when reported across the Agent Mailbox
 * (e.g. a peer reviewer's result reaching the Supervisor) -- placed here,
 * not in `events/agent_os.py`, because it is never independently published
 * under its own Event Bus subject (only `AgentMessage` is).
 */
export interface AgentResult {
  agent_instance_id: AgentInstanceId;
  task_node_id: TaskNodeId;
  status: Status;
  output: Output;
  confidence?: Confidence;
  self_validation_passed: SelfValidationPassed;
  correlation_id: CorrelationId;
  [k: string]: unknown;
}
export interface Output {
  [k: string]: unknown;
}
