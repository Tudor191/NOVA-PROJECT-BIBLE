export type MemoryId = string;
/**
 * The six persisted long-term memory categories (Bible Part 3). Sensory,
 * Working, and Short Term memory are not `memory_type` values -- they are held in
 * distinct stores (in-process buffer, Redis, `short_term_record`), per
 * docs/design/phase-1/01-memory-engine.md §2. Relationship Memory is not stored
 * here at all (§5: delegated entirely to Knowledge Engine).
 */
export type MemoryType = "semantic" | "procedural" | "episodic" | "project" | "preference" | "decision";
export type Content = string;
export type Score = number;
export type Similarity = number | null;
export type ImportanceScore = number;
export type RecencyDecay = number | null;
export type Confidence = number | null;

/**
 * One ranked result within a `MemoryRetrieveReplyPayload`. Component scores are
 * included per docs/design/phase-1/01-memory-engine.md §7 step 7 -- retrieval is
 * explainable, not just a bare ranked list.
 */
export interface MemorySearchResultPayload {
  memory_id: MemoryId;
  memory_type: MemoryType;
  content: Content;
  score: Score;
  similarity?: Similarity;
  importance_score: ImportanceScore;
  recency_decay?: RecencyDecay;
  confidence?: Confidence;
  [k: string]: unknown;
}
