export type NodeId = string;
export type Label = string;
export type Name = string;
export type Domain = string | null;
/**
 * Part 10's Domain/Personal/Project Knowledge distinction, implemented as one
 * column rather than separate tables (docs/design/phase-1/02-knowledge-engine.md
 * §2).
 */
export type KnowledgeScope = "global" | "project" | "personal";
export type Confidence = number;
/**
 * The seven-stage knowledge maturity state machine, docs/design/phase-1/
 * 02-knowledge-engine.md §6. Unlike Memory's lifecycle, this never terminates in
 * deletion -- Part 10 has no forgetting model for knowledge, only maturation.
 */
export type KnowledgeLayer = "raw" | "processed" | "verified" | "connected" | "applied" | "expert" | "strategic";
export type Version = number;
export type SchemaVersion = number;

/**
 * Shared shape for both `knowledge.node.created` and `.updated` -- the two
 * subjects differ only in when they fire, not in payload shape (docs/design/
 * phase-1/02-knowledge-engine.md §13). Published only after the Neo4j side of the
 * saga (§17) has actually applied -- consumers never see a node "created" before
 * it's queryable in the graph.
 */
export interface KnowledgeNodeChangedPayload {
  node_id: NodeId;
  label: Label;
  name: Name;
  domain?: Domain;
  scope: KnowledgeScope;
  confidence: Confidence;
  layer: KnowledgeLayer;
  version: Version;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
