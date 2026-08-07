export type Delivered = boolean;
export type PersonalityValidated = boolean;
export type Degraded = boolean;
export type TurnId = string | null;
export type RejectionReason = string | null;
export type SchemaVersion = number;

/**
 * `delivered=False` covers two distinct causes, distinguished by
 * `rejection_reason`: a personality hard-stop (content must never reach
 * the user, design doc Sec7 step 2 / 02-personality-engine.md Sec8) versus
 * a channel/session-level delivery failure (design doc Sec9).
 */
export interface CommunicationIntentDeliverReplyPayload {
  delivered: Delivered;
  personality_validated: PersonalityValidated;
  degraded?: Degraded;
  turn_id?: TurnId;
  rejection_reason?: RejectionReason;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
