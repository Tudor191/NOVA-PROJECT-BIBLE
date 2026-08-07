export type SeedNodeId = string;
export type MaxHops = number;
export type SchemaVersion = number;

/**
 * Bounded graph traversal from an existing node -- unbounded traversal is
 * deliberately not expressible (docs/design/phase-1/02-knowledge-engine.md §7).
 */
export interface KnowledgeTraverseRequestPayload {
  seed_node_id: SeedNodeId;
  max_hops?: MaxHops;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
