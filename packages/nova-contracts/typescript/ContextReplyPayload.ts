export type UserId = string;
export type Objective = string | null;
export type ProjectId = string | null;
export type Device = string | null;
export type Task = string | null;
export type Activity = string | null;
export type Confidence = number | null;
export type UpdatedAt = string | null;
export type Degraded = boolean;

export interface ContextReplyPayload {
  user_id: UserId;
  objective?: Objective;
  project_id?: ProjectId;
  device?: Device;
  task?: Task;
  activity?: Activity;
  confidence?: Confidence;
  updated_at?: UpdatedAt;
  degraded?: Degraded;
  [k: string]: unknown;
}
