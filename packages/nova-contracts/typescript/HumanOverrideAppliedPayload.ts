export type ReasoningProcessId = string;
/**
 * Design doc §18's human-override action set.
 */
export type OverrideAction = "confirm" | "redirect" | "reject";
export type RedirectAlternativeId = string | null;
export type Note = string | null;
export type SchemaVersion = number;

/**
 * Design doc §18 -- published whenever a human confirms, redirects, or
 * rejects a decision awaiting override.
 */
export interface HumanOverrideAppliedPayload {
  reasoning_process_id: ReasoningProcessId;
  action: OverrideAction;
  redirect_alternative_id?: RedirectAlternativeId;
  note?: Note;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
