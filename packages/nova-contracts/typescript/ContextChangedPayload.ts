export type UserId = string;
export type Objective = string | null;
export type ProjectId = string | null;
export type Device = string | null;
export type Task = string | null;
export type Activity = string | null;
export type Confidence = number;
export type IdentityId = string | null;
export type Confidence1 = number;
export type ModalitySummary = string;
export type PresentIdentities = PresentIdentityPayload[];
export type SchemaVersion = number;

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
  present_identities?: PresentIdentities;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
/**
 * One currently-present identity (docs/design/phase-2d/
 * 03-perception-engine.md §0.6) -- a direct pass-through of that engine's own
 * `IdentityObservation`/`IdentityConfidenceState` signal, never
 * re-interpreted here. `identity_id` is `None` for a confidently-detected-
 * but-unenrolled presence.
 */
export interface PresentIdentityPayload {
  identity_id?: IdentityId;
  confidence: Confidence1;
  modality_summary: ModalitySummary;
  [k: string]: unknown;
}
