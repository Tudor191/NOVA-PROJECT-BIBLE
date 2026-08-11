export type SessionId = string;
export type UserId = string;
export type Objective = string | null;
export type TurnCount = number;
export type ClosedAt = string;
export type Corrections = string[];
export type Preferences = string[];
export type Feedback = string[];
export type Decisions = string[];
export type SchemaVersion = number;

/**
 * Design doc Sec8.6 -- the only long-term retention of conversation
 * content; Memory Engine is this event's intended (not yet wired,
 * out of Phase 2D-A scope) subscriber.
 *
 * `corrections`/`preferences`/`feedback`/`decisions` (Phase 2D-D,
 * docs/design/phase-2d/06-personal-companion.md Sec6) -- additive
 * (ADR-024), sourced verbatim from the session's own `ConversationMemory`
 * at close time, same field names, same default-empty-list convention
 * (`ConversationMemory` itself never uses `None` for these -- an absent
 * category is an empty list, not a null). `digital-twin-engine` is this
 * addition's own intended subscriber, learning Communication Profile/
 * Preference Evolution/correction-frequency trust-metric evidence from
 * them (Sec9).
 */
export interface CommunicationSessionCompletedPayload {
  session_id: SessionId;
  user_id: UserId;
  objective?: Objective;
  turn_count: TurnCount;
  closed_at: ClosedAt;
  corrections?: Corrections;
  preferences?: Preferences;
  feedback?: Feedback;
  decisions?: Decisions;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
