import type { QueryClient } from "@tanstack/react-query";

import type {
  CommunicationIntentDeliveredPayload,
  CommunicationSessionStateChangedPayload,
  CommunicationTurnReceivedPayload,
  HeartbeatPayload,
  PerceptionIdentityObservedPayload,
} from "@nova/nova-contracts";

import type { TranscriptEntry } from "../entities/conversation";
import {
  conversationKeys,
  entryFromDelivery,
  entryFromTurn,
} from "../entities/conversation";
import type { PresentIdentity } from "../entities/presence";
import { entryFromObservation, presenceKeys, reducePresence } from "../entities/presence";
import type { PulseState } from "../entities/pulse";
import { pulseKeys, reducePulse } from "../entities/pulse";
import type { EventFrame } from "./protocol";

/**
 * Bus frame -> Query cache.
 *
 * Kept as pure functions plus one thin dispatcher so the interesting part --
 * what a frame does to what the user sees -- is testable without React, a
 * socket, or a running gateway. `applyFrame` is deliberately boring; every
 * decision lives in a `reduce*` that takes the current value and returns the
 * next one.
 *
 * Two rules hold across all of them:
 *
 * 1. **Ordering is by the event's own time, not arrival order.** The bus
 *    makes no ordering promise across subjects, and a reply rendered above
 *    the question it answers is a wrong transcript.
 * 2. **A repeat is not a duplicate row.** At-least-once delivery is normal;
 *    `turn_id` deduplicates.
 */

export function reduceTranscript(
  existing: TranscriptEntry[] | undefined,
  entry: TranscriptEntry,
): TranscriptEntry[] {
  const current = existing ?? [];
  if (current.some((candidate) => candidate.id === entry.id)) {
    return current;
  }
  return [...current, entry].sort((a, b) => {
    const byTime = Date.parse(a.at) - Date.parse(b.at);
    // Same millisecond: fall back to a stable key so the order does not
    // flicker between renders.
    return byTime !== 0 ? byTime : a.id.localeCompare(b.id);
  });
}

/** The session id the transcript keys on, or `null` when none is open. */
export type ActiveSession = string | null;

export function applyFrame(
  queryClient: QueryClient,
  frame: EventFrame,
  activeSessionId: ActiveSession,
): void {
  const { correlation_id: correlationId, generated_at: generatedAt } = frame.meta;

  switch (frame.topic) {
    case "communication.turn.received": {
      const payload = frame.data as unknown as CommunicationTurnReceivedPayload;
      if (!belongsToSession(payload.session_id, activeSessionId)) return;
      queryClient.setQueryData<TranscriptEntry[]>(
        conversationKeys.transcript(payload.session_id),
        (existing) => reduceTranscript(existing, entryFromTurn(payload, correlationId)),
      );
      return;
    }

    case "communication.intent.delivered": {
      const payload = frame.data as unknown as CommunicationIntentDeliveredPayload;
      if (!belongsToSession(payload.session_id, activeSessionId)) return;
      queryClient.setQueryData<TranscriptEntry[]>(
        conversationKeys.transcript(payload.session_id),
        (existing) => reduceTranscript(existing, entryFromDelivery(payload, correlationId)),
      );
      return;
    }

    case "communication.session.state_changed": {
      const payload = frame.data as unknown as CommunicationSessionStateChangedPayload;
      if (!belongsToSession(payload.session_id, activeSessionId)) return;
      queryClient.setQueryData(conversationKeys.state(payload.session_id), payload.to_state);
      return;
    }

    case "perception.identity.observed": {
      const payload = frame.data as unknown as PerceptionIdentityObservedPayload;
      const identity = entryFromObservation(payload, generatedAt);
      if (identity === null) return;
      queryClient.setQueryData<PresentIdentity[] | null>(presenceKeys.present, (existing) =>
        reducePresence(existing ?? null, identity),
      );
      return;
    }

    case "nova.heartbeat": {
      const payload = frame.data as unknown as HeartbeatPayload;
      queryClient.setQueryData<PulseState | null>(pulseKeys.current, (existing) =>
        reducePulse(existing ?? null, payload, generatedAt),
      );
      return;
    }

    default:
      // Subscribed but not yet rendered by any 4A panel
      // (`communication.session.created`/`.completed`,
      // `perception.presence.observed`). Ignored deliberately, and
      // deliberately not an error: 4B panels consume them.
      return;
  }
}

/**
 * Frames for other sessions are dropped.
 *
 * A single-user instance (ADR-025) will rarely have two, but the socket
 * carries a topic, not a session -- so without this the transcript would
 * merge conversations the moment a second one existed.
 */
function belongsToSession(sessionId: unknown, activeSessionId: ActiveSession): boolean {
  return typeof sessionId === "string" && sessionId === activeSessionId;
}
