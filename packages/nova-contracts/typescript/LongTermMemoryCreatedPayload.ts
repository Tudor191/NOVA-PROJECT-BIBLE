export type MemoryId = string;
export type UserId = string;
export type ProjectId = string | null;
/**
 * The six persisted long-term memory categories (Bible Part 3). Sensory,
 * Working, and Short Term memory are not `memory_type` values -- they are held in
 * distinct stores (in-process buffer, Redis, `short_term_record`), per
 * docs/design/phase-1/01-memory-engine.md §2. Relationship Memory is not stored
 * here at all (§5: delegated entirely to Knowledge Engine).
 */
export type MemoryType = "semantic" | "procedural" | "episodic" | "project" | "preference" | "decision";
export type ImportanceScore = number;
export type Confidence = number | null;
/**
 * Bible Part 7's privacy classification, propagated on every entity per
 * docs/design/phase-1/00-shared-foundations.md's "Confidence and privacy,
 * everywhere" convention. Enforcement point is the Model Orchestration Engine
 * (Phase 2); Phase 1 stores and propagates the field correctly from day one.
 */
export type PrivacyLevel = "public" | "internal" | "confidential" | "highly_sensitive";
export type KnowledgeNodeId = string | null;

export interface LongTermMemoryCreatedPayload {
  memory_id: MemoryId;
  user_id: UserId;
  project_id?: ProjectId;
  memory_type: MemoryType;
  importance_score: ImportanceScore;
  confidence?: Confidence;
  privacy_level: PrivacyLevel;
  knowledge_node_id?: KnowledgeNodeId;
  [k: string]: unknown;
}
