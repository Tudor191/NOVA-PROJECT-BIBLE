/**
 * Part 20 "Execution Modes".
 */
export type SystemMode =
  "interactive" | "silent" | "developer" | "research" | "presentation" | "gaming" | "travel" | "offline" | "emergency";
export type ChangedBy = string;

export interface ModeChangedPayload {
  mode: SystemMode;
  previous_mode?: SystemMode | null;
  changed_by: ChangedBy;
  [k: string]: unknown;
}
