export type NodeId = string;
/**
 * The seven-stage knowledge maturity state machine, docs/design/phase-1/
 * 02-knowledge-engine.md §6. Unlike Memory's lifecycle, this never terminates in
 * deletion -- Part 10 has no forgetting model for knowledge, only maturation.
 */
export type KnowledgeLayer = "raw" | "processed" | "verified" | "connected" | "applied" | "expert" | "strategic";
export type Reason = string;

export interface LayerAdvancedPayload {
  node_id: NodeId;
  previous_layer: KnowledgeLayer;
  new_layer: KnowledgeLayer;
  reason: Reason;
  [k: string]: unknown;
}
