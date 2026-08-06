export type ExecutiveDecisionId = string;
/**
 * Design doc Sec13's human-override action set -- identical shape to
 * Reasoning Engine's own `OverrideAction` (design doc Sec18 of that
 * engine), redefined here rather than imported so each engine's contracts
 * module stays self-contained, the same convention every engine's own
 * enums already follow even where two engines' vocabularies coincide.
 */
export type ExecutiveOverrideAction = "confirm" | "redirect" | "reject";
/**
 * Design doc Sec4 -- the four outcomes every arbitration produces.
 */
export type ArbitrationOutcome = "proceed" | "proceed_reduced" | "wait" | "escalated";
export type Note = string | null;
export type SchemaVersion = number;

/**
 * Design doc Sec13 -- published whenever a human confirms, redirects,
 * or rejects an executive decision, the direct analog of Reasoning
 * Engine's own `HumanOverrideAppliedPayload`.
 */
export interface ExecutiveHumanOverrideAppliedPayload {
  executive_decision_id: ExecutiveDecisionId;
  action: ExecutiveOverrideAction;
  redirect_outcome?: ArbitrationOutcome | null;
  note?: Note;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
