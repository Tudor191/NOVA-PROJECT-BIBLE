/**
 * Doc 12 §10, verbatim.
 */
export type AgentMessageType =
  | "assign"
  | "pause"
  | "resume"
  | "peer_review_request"
  | "peer_review_result"
  | "conflict_escalation"
  | "delegation"
  | "health_ping";
export type FromInstanceId = string | null;
export type ToInstanceId = string;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * TDD 3E §6 -- the Agent Mailbox envelope. `from_instance_id=None` for
 * Kernel/Supervisor-originated messages (doc 12 §10: "kernel-to-agent,
 * supervisor-to-agent, and (never direct) agent-to-agent" -- agent-to-agent
 * traffic is still routed through this envelope, just always carrying a
 * non-`None` `from_instance_id` set by the mediating Supervisor, never a
 * direct bus subscription between two instances).
 */
export interface AgentMessage {
  message_type: AgentMessageType;
  from_instance_id?: FromInstanceId;
  to_instance_id: ToInstanceId;
  payload: Payload;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
export interface Payload {
  [k: string]: unknown;
}
