export type KnowledgeNodeId = string;
export type SchemaVersion = number;

export interface KnowledgeLinkReplyPayload {
  knowledge_node_id: KnowledgeNodeId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
