import { skipToken, useQuery } from "@tanstack/react-query";

import type { PerceptionIdentityObservedPayload } from "@nova/nova-contracts";

/**
 * Who NOVA currently believes is present.
 *
 * Sourced only from `perception.identity.observed`, pushed over
 * `ws-gateway`. There is no REST fallback and no polling: the indicator
 * shows what perception-engine actually observed, or it shows that it does
 * not know.
 *
 * **`null` means "we have not heard", and it is not the same as an empty
 * list.** An empty list would be a claim -- "nobody is here" -- that this
 * client is in no position to make from an absence of events. Doc 04 §4's
 * rule against rendering something the system does not hold applies as much
 * to a confident absence as to a confident presence.
 *
 * `observedAt` comes from the *envelope's* `generated_at`, not from the
 * payload: the generated contract has no timestamp field, and minting one
 * from `Date.now()` here would date the observation to when the browser
 * happened to receive it.
 */

export type PresentIdentity = {
  userId: string;
  /** perception-engine's own number. Copied, never derived. */
  confidence: number | null;
  /** perception-engine's own tier word, carried alongside the number. */
  confidenceTier: string | null;
  observedAt: string;
};

export const presenceKeys = { present: ["presence"] as const };

export function entryFromObservation(
  payload: PerceptionIdentityObservedPayload,
  observedAt: string,
): PresentIdentity | null {
  // perception-engine's own World Model handler skips observations with no
  // `user_id`. An unidentified presence is not an identity, and admitting
  // one here would put a person on screen who was never recognised. The
  // contract says the field is required; this guards the wire, not the type.
  if (typeof payload.user_id !== "string" || !payload.user_id) {
    return null;
  }
  return {
    userId: payload.user_id,
    confidence: typeof payload.confidence === "number" ? payload.confidence : null,
    confidenceTier: typeof payload.confidence_tier === "string" ? payload.confidence_tier : null,
    observedAt,
  };
}

/**
 * Merge an observation into the known set, newest-wins per user.
 *
 * Pure so it can be tested without React, and so the reconciler in
 * `realtime/` stays a dispatcher rather than a place logic accumulates.
 */
export function reducePresence(
  existing: PresentIdentity[] | null,
  identity: PresentIdentity,
): PresentIdentity[] {
  const others = (existing ?? []).filter((entry) => entry.userId !== identity.userId);
  return [...others, identity].sort((a, b) => a.userId.localeCompare(b.userId));
}

export function usePresentIdentities() {
  return useQuery<PresentIdentity[] | null>({
    queryKey: presenceKeys.present,
    queryFn: skipToken,
    initialData: null,
  });
}
