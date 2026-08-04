export type KnowledgeNodeId = string;

export interface KnowledgeLinkReplyPayload {
  knowledge_node_id: KnowledgeNodeId;
  [k: string]: unknown;
}
