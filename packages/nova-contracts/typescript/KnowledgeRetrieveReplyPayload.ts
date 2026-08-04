export type NodeId = string;
export type Label = string;
export type Name = string;
export type Score = number;
export type Similarity = number | null;
export type Confidence = number;
/**
 * The seven-stage knowledge maturity state machine, docs/design/phase-1/
 * 02-knowledge-engine.md §6. Unlike Memory's lifecycle, this never terminates in
 * deletion -- Part 10 has no forgetting model for knowledge, only maturation.
 */
export type KnowledgeLayer = "raw" | "processed" | "verified" | "connected" | "applied" | "expert" | "strategic";
export type RelatedNodeIds = string[];
export type Results = KnowledgeSearchResultPayload[];
export type Degraded = boolean;

export interface KnowledgeRetrieveReplyPayload {
  results?: Results;
  degraded?: Degraded;
  [k: string]: unknown;
}
/**
 * One ranked result within a `KnowledgeRetrieveReplyPayload`, richer than
 * Memory's equivalent because "the surrounding context, the relationships, the
 * history" is the point of Knowledge retrieval (docs/design/phase-1/
 * 02-knowledge-engine.md §7 step 6).
 */
export interface KnowledgeSearchResultPayload {
  node_id: NodeId;
  label: Label;
  name: Name;
  score: Score;
  similarity?: Similarity;
  confidence: Confidence;
  layer: KnowledgeLayer;
  related_node_ids?: RelatedNodeIds;
  [k: string]: unknown;
}
