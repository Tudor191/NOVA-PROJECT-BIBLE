export type ConnectedNodeIds = string[];

export interface KnowledgeTraverseReplyPayload {
  connected_node_ids?: ConnectedNodeIds;
  [k: string]: unknown;
}
