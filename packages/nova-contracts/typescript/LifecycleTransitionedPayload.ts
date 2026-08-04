export type MemoryId = string;
export type UserId = string;
/**
 * The five-stage forgetting state machine, docs/design/phase-1/
 * 01-memory-engine.md §6. `ARCHIVED -> SCHEDULED_FOR_DELETION` is never a passive
 * time-based transition in Phase 1 -- see that section for the explicit triggers
 * required.
 */
export type LifecycleState = "active" | "weak" | "archived" | "scheduled_for_deletion" | "deleted";
export type Reason = string;

export interface LifecycleTransitionedPayload {
  memory_id: MemoryId;
  user_id: UserId;
  previous_state: LifecycleState;
  new_state: LifecycleState;
  reason: Reason;
  [k: string]: unknown;
}
