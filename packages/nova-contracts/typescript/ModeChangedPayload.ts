/**
 * Part 20 "Execution Modes".
 */
export type SystemMode =
  "interactive" | "silent" | "developer" | "research" | "presentation" | "gaming" | "travel" | "offline" | "emergency";
export type ChangedBy = string;
export type SchemaVersion = number;

export interface ModeChangedPayload {
  mode: SystemMode;
  previous_mode?: SystemMode | null;
  changed_by: ChangedBy;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
