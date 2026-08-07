export type MemoryId = string;
export type ConceptName = string;
export type SchemaVersion = number;

/**
 * Create-or-find a Concept (or other labeled) node and link it to a memory.
 * Served by Knowledge Engine's `graph_operations.py`.
 */
export interface KnowledgeLinkRequestPayload {
  memory_id: MemoryId;
  concept_name: ConceptName;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
