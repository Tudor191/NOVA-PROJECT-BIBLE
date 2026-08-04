export type MemoryId = string;
export type ConceptName = string;

/**
 * Create-or-find a Concept (or other labeled) node and link it to a memory.
 * Served by Knowledge Engine's `graph_operations.py`.
 */
export interface KnowledgeLinkRequestPayload {
  memory_id: MemoryId;
  concept_name: ConceptName;
  [k: string]: unknown;
}
