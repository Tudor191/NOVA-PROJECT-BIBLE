export type ConnectedNodeIds = string[];
export type SchemaVersion = number;

export interface KnowledgeTraverseReplyPayload {
  connected_node_ids?: ConnectedNodeIds;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
