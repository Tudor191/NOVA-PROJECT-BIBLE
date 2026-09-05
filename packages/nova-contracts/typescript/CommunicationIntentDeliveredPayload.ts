export type SessionId = string;
export type TurnId = string;
export type UserId = string;
export type Content = string;
/**
 * Design doc Sec3.2, Sec5 -- extensible; exactly two ship this phase.
 */
export type ChannelType = "text" | "voice";
export type ConfidenceTier = string;
export type PersonalityValidated = boolean;
export type Degraded = boolean;
export type DeliveredAt = string;
export type SchemaVersion = number;

/**
 * What NOVA actually said, after the ADR-005 intent gate passed it.
 *
 * Added in Phase 4A. Until now the only broadcast half of a conversation
 * was the user's own (`communication.turn.received`): a reply reached the
 * user solely over this engine's own WebSocket channel adapter, so no
 * subscriber -- and therefore no browser, since doc 11 §1 forbids the
 * frontend from talking to an engine directly -- could observe what NOVA
 * said. That made the Conversation panel's half of Phase 4 **AC-1**
 * unreachable. This event closes it, and it is the *only* engine change
 * 4A makes.
 *
 * Published **after** delivery succeeds, never before, and never for
 * content the gate rejected: `content` is the post-validation text
 * (02-personality-engine.md Sec8 may adjust it), so a subscriber can never
 * see an utterance the personality layer stopped or rewrote.
 *
 * `confidence_tier` is the string the content-source engine supplied,
 * carried verbatim. It is deliberately **not** converted into the
 * envelope's numeric `confidence`: no engine reported a number here, and
 * manufacturing one would corrupt exactly the signal Part 8's Confidence
 * System exists to carry.
 *
 * `personality_validated` and `degraded` travel with it so a consumer can
 * disclose a degraded path rather than present it as a clean answer --
 * the project's standing "never silence, always disclose degradation"
 * rule applied to the last hop.
 */
export interface CommunicationIntentDeliveredPayload {
  session_id: SessionId;
  turn_id: TurnId;
  user_id: UserId;
  content: Content;
  channel: ChannelType;
  confidence_tier?: ConfidenceTier;
  personality_validated: PersonalityValidated;
  degraded?: Degraded;
  delivered_at: DeliveredAt;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
