export type ContradictionId = string;
export type NodeAId = string;
export type NodeBId = string;
export type Description = string;
export type Status = string;
export type Resolution = string | null;

/**
 * Shared shape for `.detected` and `.resolved` -- `resolution`/`resolved_at`
 * are unset on `.detected` (docs/design/phase-1/02-knowledge-engine.md §13).
 */
export interface ContradictionPayload {
  contradiction_id: ContradictionId;
  node_a_id: NodeAId;
  node_b_id: NodeBId;
  description: Description;
  status: Status;
  resolution?: Resolution;
  [k: string]: unknown;
}
