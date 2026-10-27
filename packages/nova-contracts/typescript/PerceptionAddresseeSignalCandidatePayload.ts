export type WakeWordMatched = boolean;
export type WakeWordConfidence = number;
export type IdentityId = string | null;
export type IdentityConfidence = number;
/**
 * Matches `AttentionObservation.gaze_direction`'s existing `Literal`
 * exactly.
 */
export type GazeDirection = "toward_device" | "away" | "unknown";
export type SessionActive = boolean;
export type UserId = string;
export type SchemaVersion = number;

/**
 * Master Blueprint Sec5 / design doc Sec10 -- raw candidate signals
 * only, no verdict field of any kind (`should_respond`/`is_addressed` are
 * deliberately absent). Deliberately subject-named `.candidate`, not
 * `.observed` -- never matches World Model's wildcard. The sole input
 * contract for `communication-engine`'s Phase 2D-C addressee-detection
 * fusion (docs/design/phase-2d/04-conversation-intelligence.md Sec4).
 *
 * `user_id` (Phase 2D-C Closure Priority 2, docs/design/phase-2d/
 * 05-conversation-intelligence-closure.md Sec4) -- required, breaking
 * addition to an already-registered contract, coordinated same-release
 * since `communication-engine` is this payload's only consumer and both
 * engines deploy from the same monorepo (Sec12's own migration-strategy
 * reasoning). **Deliberately not the same claim as `identity_id`:**
 * `user_id` is perception-engine's configured instance owner
 * (`Settings.primary_user_id`, ADR-025's single-trusted-user default),
 * present on every candidate regardless of whether biometric identity
 * matched this window; `identity_id` is a per-window, evidence-scored
 * verification result, `None` whenever no match occurred. A future
 * consumer must not treat `user_id` as an identity-confidence claim --
 * that is what `identity_id`/`identity_confidence` are for.
 */
export interface PerceptionAddresseeSignalCandidatePayload {
  wake_word_matched: WakeWordMatched;
  wake_word_confidence: WakeWordConfidence;
  identity_id?: IdentityId;
  identity_confidence: IdentityConfidence;
  gaze_direction: GazeDirection;
  session_active: SessionActive;
  user_id: UserId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
