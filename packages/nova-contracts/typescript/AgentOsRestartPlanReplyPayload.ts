export type RestartInstanceIds = string[];
export type SchemaVersion = number;

export interface AgentOsRestartPlanReplyPayload {
  restart_instance_ids?: RestartInstanceIds;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
