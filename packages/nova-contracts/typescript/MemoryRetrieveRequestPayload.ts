export type UserId = string;
export type QueryText = string | null;
export type ProjectId = string | null;
/**
 * The six persisted long-term memory categories (Bible Part 3). Sensory,
 * Working, and Short Term memory are not `memory_type` values -- they are held in
 * distinct stores (in-process buffer, Redis, `short_term_record`), per
 * docs/design/phase-1/01-memory-engine.md §2. Relationship Memory is not stored
 * here at all (§5: delegated entirely to Knowledge Engine).
 */
export type MemoryType = "semantic" | "procedural" | "episodic" | "project" | "preference" | "decision";
export type IncludeRelationships = boolean;
export type Limit = number;

/**
 * Request/reply RPC served by Memory Engine
 * (docs/design/phase-1/01-memory-engine.md §13, §14).
 */
export interface MemoryRetrieveRequestPayload {
  user_id: UserId;
  query_text?: QueryText;
  project_id?: ProjectId;
  memory_type?: MemoryType | null;
  include_relationships?: IncludeRelationships;
  limit?: Limit;
  [k: string]: unknown;
}
