export type UserId = string;
export type Scope = string | null;

/**
 * The highest-QPS internal call in the whole Phase 1 surface -- every
 * Reasoning pipeline execution calls it (docs/design/phase-1/
 * 03-world-model-engine.md §14-15). `scope` selects Agent-Awareness filtering
 * (Part 11), e.g. `"agent:coding-agent"`; `None` returns the full Active
 * Context.
 */
export interface ContextRequestPayload {
  user_id: UserId;
  scope?: Scope;
  [k: string]: unknown;
}
