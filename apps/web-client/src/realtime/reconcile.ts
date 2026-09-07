import type { QueryClient } from "@tanstack/react-query";

import type {
  ActionApprovalDecidedPayload,
  ActionApprovalRequestedPayload,
  CommunicationIntentDeliveredPayload,
  CommunicationSessionStateChangedPayload,
  CommunicationTurnReceivedPayload,
  HeartbeatPayload,
  ModelHealthChangedPayload,
  ModuleStatusChangedPayload,
  PerceptionIdentityObservedPayload,
  PlanningTaskGraphCreatedPayload,
  ReasoningProcessCompletedPayload,
  ReasoningProcessFailedPayload,
} from "@nova/nova-contracts";

import type { TranscriptEntry } from "../entities/conversation";
import {
  conversationKeys,
  entryFromDelivery,
  entryFromTurn,
} from "../entities/conversation";
import type { PresentIdentity } from "../entities/presence";
import { entryFromObservation, presenceKeys, reducePresence } from "../entities/presence";
import type { PendingApproval } from "../entities/approvals";
import { approvalKeys, reduceDecided, reduceRequested } from "../entities/approvals";
import type { ObservedEvent } from "../entities/events";
import { eventKeys, observedFromFrame, reduceEventFeed } from "../entities/events";
import type { HealthState } from "../entities/health";
import {
  healthKeys,
  reduceHeartbeat,
  reduceModelHealth,
  reduceModuleStatus,
} from "../entities/health";
import type { TaskGraph } from "../entities/planning";
import { planningKeys, reduceTaskGraphCreated } from "../entities/planning";
import type { PulseState } from "../entities/pulse";
import { pulseKeys, reducePulse } from "../entities/pulse";
import type { LiveProcess } from "../entities/reasoning";
import {
  processFromCompleted,
  processFromFailed,
  reasoningKeys,
  reduceProcess,
} from "../entities/reasoning";
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

/**
 * Arrival order for the Events panel.
 *
 * Frames carry no id of their own on the wire, and `generated_at` is the
 * event's time rather than the browser's, so two frames can share it. A
 * counter is the only thing here that can say which arrived first.
 * Module-level rather than derived from the feed's length, because the feed
 * is capped -- length stops increasing long before the session ends.
 */
let sequence = 0;

function nextSequence(): number {
  sequence += 1;
  return sequence;
}

/** Test seam: a fresh feed per test, so ids do not leak between them. */
export function resetSequenceForTests(): void {
  sequence = 0;
}

export function applyFrame(
  queryClient: QueryClient,
  frame: EventFrame,
  activeSessionId: ActiveSession,
): void {
  const { correlation_id: correlationId, generated_at: generatedAt } = frame.meta;

  // The Events panel records every frame, *before* the switch below and
  // regardless of whether any panel renders it. That ordering is the whole
  // point: a topic this client subscribes to but does not yet handle still
  // shows up as arriving, so "the panel is empty" and "nothing is arriving"
  // stay distinguishable. It is also why the `default` case below can stay
  // a silent no-op without hiding anything.
  queryClient.setQueryData<ObservedEvent[]>(eventKeys.feed, (existing) =>
    reduceEventFeed(existing, observedFromFrame(frame, nextSequence(), new Date().toISOString())),
  );

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
      // The same beat feeds the Health panel's per-module reading. One
      // event, two views: the header dot summarises, the panel expands.
      queryClient.setQueryData<HealthState>(healthKeys.modules, (existing) =>
        reduceHeartbeat(existing, payload, generatedAt),
      );
      return;
    }

    // --- Phase 4B panels ---------------------------------------------------

    case "planning.task_graph.created": {
      const payload = frame.data as unknown as PlanningTaskGraphCreatedPayload;
      queryClient.setQueryData<TaskGraph[]>(planningKeys.all, (existing) =>
        reduceTaskGraphCreated(existing, payload),
      );
      return;
    }

    case "reasoning.process.completed": {
      const payload = frame.data as unknown as ReasoningProcessCompletedPayload;
      queryClient.setQueryData<LiveProcess[]>(reasoningKeys.live, (existing) =>
        reduceProcess(existing, processFromCompleted(payload, generatedAt)),
      );
      return;
    }

    case "reasoning.process.failed": {
      const payload = frame.data as unknown as ReasoningProcessFailedPayload;
      queryClient.setQueryData<LiveProcess[]>(reasoningKeys.live, (existing) =>
        reduceProcess(existing, processFromFailed(payload, generatedAt)),
      );
      return;
    }

    case "action.approval.requested": {
      const payload = frame.data as unknown as ActionApprovalRequestedPayload;
      queryClient.setQueryData<PendingApproval[]>(approvalKeys.pending, (existing) =>
        reduceRequested(existing, payload),
      );
      return;
    }

    case "action.approval.decided": {
      const payload = frame.data as unknown as ActionApprovalDecidedPayload;
      queryClient.setQueryData<PendingApproval[]>(approvalKeys.pending, (existing) =>
        reduceDecided(existing, payload),
      );
      return;
    }

    case "nova.module.status_changed": {
      const payload = frame.data as unknown as ModuleStatusChangedPayload;
      queryClient.setQueryData<HealthState>(healthKeys.modules, (existing) =>
        reduceModuleStatus(existing, payload, generatedAt),
      );
      return;
    }

    case "ai_model.model.health_changed": {
      const payload = frame.data as unknown as ModelHealthChangedPayload;
      queryClient.setQueryData<HealthState>(healthKeys.modules, (existing) =>
        reduceModelHealth(existing, payload, generatedAt),
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
