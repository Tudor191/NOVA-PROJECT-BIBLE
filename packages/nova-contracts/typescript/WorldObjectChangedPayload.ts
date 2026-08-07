export type ObjectId = string;
export type Label = string;
export type UserId = string;
/**
 * World Model's object-state model (docs/design/phase-1/
 * 03-world-model-engine.md §6) -- deliberately not a "lifecycle" in Memory
 * Engine's sense: there is no forgetting/deletion path here, only transitions
 * between states of *current* reality. `UNKNOWN` is the only state with no
 * incoming transition from another state (`[*] --> Unknown` in §6's diagram).
 */
export type ObjectState = "unknown" | "active" | "idle" | "executing" | "completed" | "failed" | "waiting" | "learning";
export type Confidence = number | null;
export type SchemaVersion = number;

/**
 * Shared shape for `.created`/`.updated`/`.deleted` -- the three subjects
 * differ only in when they fire (docs/design/phase-1/03-world-model-engine.md
 * §13).
 */
export interface WorldObjectChangedPayload {
  object_id: ObjectId;
  label: Label;
  user_id: UserId;
  previous_state?: ObjectState | null;
  new_state: ObjectState;
  confidence?: Confidence;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
