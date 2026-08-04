export type UserId = string;
export type Objective = string | null;
export type ProjectId = string | null;
export type Device = string | null;
export type Task = string | null;
export type Activity = string | null;
export type Confidence = number;

/**
 * One fused Active Context update (docs/design/phase-1/
 * 03-world-model-engine.md §3) -- `domain/fusion.py` publishes at most one of
 * these per correlation window, never one per raw signal.
 */
export interface ContextChangedPayload {
  user_id: UserId;
  objective?: Objective;
  project_id?: ProjectId;
  device?: Device;
  task?: Task;
  activity?: Activity;
  confidence: Confidence;
  [k: string]: unknown;
}
