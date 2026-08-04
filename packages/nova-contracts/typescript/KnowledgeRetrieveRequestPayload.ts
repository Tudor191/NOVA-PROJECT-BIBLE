export type QueryText = string | null;
export type SeedNodeId = string | null;
/**
 * Part 10's Domain/Personal/Project Knowledge distinction, implemented as one
 * column rather than separate tables (docs/design/phase-1/02-knowledge-engine.md
 * §2).
 */
export type KnowledgeScope = "global" | "project" | "personal";
export type ProjectId = string | null;
export type UserId = string | null;
export type MaxHops = number;
export type Limit = number;

/**
 * Request/reply RPC served by Knowledge Engine (docs/design/phase-1/
 * 02-knowledge-engine.md §13, §14).
 */
export interface KnowledgeRetrieveRequestPayload {
  query_text?: QueryText;
  seed_node_id?: SeedNodeId;
  scope?: KnowledgeScope | null;
  project_id?: ProjectId;
  user_id?: UserId;
  max_hops?: MaxHops;
  limit?: Limit;
  [k: string]: unknown;
}
