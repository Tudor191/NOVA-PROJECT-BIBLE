export type FromNodeId = string;
export type ToNodeId = string;
export type RelationshipType = string;
export type Confidence = number;

export interface KnowledgeEdgeCreatedPayload {
  from_node_id: FromNodeId;
  to_node_id: ToNodeId;
  relationship_type: RelationshipType;
  confidence: Confidence;
  [k: string]: unknown;
}
