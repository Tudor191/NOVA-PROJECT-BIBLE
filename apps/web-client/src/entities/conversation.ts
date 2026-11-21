import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import type {
  CommunicationIntentDeliveredPayload,
  CommunicationSessionStateChangedPayload,
  CommunicationTurnReceivedPayload,
} from "@nova/nova-contracts";

import { gatewayFetch } from "./http";

/**
 * The Conversation panel's data layer.
 *
 * **This module is the first consumer of `packages/nova-contracts/typescript`
 * in the project's history.** Ninety-eight generated files had existed since
 * Phase 1 with nothing importing them; the types below are pinned to them, so
 * a panel cannot invent a payload shape and a contract change breaks the
 * build rather than the screen (TDD 4A §5.4).
 *
 * The pinning is structural, not decorative: `entryFromTurn` and
 * `entryFromDelivery` take the generated payload types as their parameters
 * and read fields off them directly. Rename or drop a field in the contract
 * and this file stops compiling -- which is the whole point of generating
 * the types rather than hand-writing them.
 */

// --- what the panel renders -------------------------------------------------

export type TranscriptEntry = {
  id: string;
  /** `user` is a turn the person sent; `nova` is what the intent gate let out. */
  author: "user" | "nova";
  content: string;
  at: string;
  /**
   * Only ever a tier word, never a number. `communication.intent.delivered`
   * reports `confidence_tier`, and nothing on that path converts it.
   */
  confidenceTier: string | null;
  correlationId: string;
  /** True when personality validation was skipped because the RPC failed. */
  degraded: boolean;
};

export type ConversationState =
  CommunicationSessionStateChangedPayload["to_state"];

// The generated payloads are the source of truth for what arrives. These
// aliases exist so the reconciler below cannot drift from them silently.
export type TurnReceived = CommunicationTurnReceivedPayload;
export type IntentDelivered = CommunicationIntentDeliveredPayload;

/** Build a transcript entry from the user's own turn. */
export function entryFromTurn(payload: TurnReceived, correlationId: string): TranscriptEntry {
  return {
    id: payload.turn_id,
    author: "user",
    content: payload.content,
    at: payload.created_at,
    // The user's own words carry no engine confidence, and inventing one
    // here would be the same error as inventing it on the reply.
    confidenceTier: null,
    correlationId,
    degraded: false,
  };
}

/** Build a transcript entry from what NOVA actually said. */
export function entryFromDelivery(
  payload: IntentDelivered,
  correlationId: string,
): TranscriptEntry {
  return {
    id: payload.turn_id,
    author: "nova",
    content: payload.content,
    at: payload.delivered_at,
    confidenceTier: payload.confidence_tier ?? null,
    correlationId,
    degraded: payload.degraded ?? false,
  };
}

// --- REST -------------------------------------------------------------------

/**
 * `communication-engine`'s `SessionResponse`, as it arrives through the
 * gateway. Hand-written because it is an HTTP response model rather than an
 * event payload, so the codegen (which covers bus contracts) does not emit
 * it -- noted here rather than left to look like an oversight.
 */
const sessionResponseSchema = z.object({
  session_id: z.string(),
  user_id: z.string(),
  channel: z.enum(["text", "voice"]),
  device_id: z.string(),
  state: z.string(),
  objective: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  closed_at: z.string().nullable(),
});

export type ConversationSession = z.infer<typeof sessionResponseSchema>;

const sendMessageResponseSchema = z.object({
  turn_id: z.string(),
  session_id: z.string(),
  accepted: z.boolean(),
});

export const conversationKeys = {
  session: ["conversation", "session"] as const,
  transcript: (sessionId: string) => ["conversation", sessionId, "transcript"] as const,
  state: (sessionId: string) => ["conversation", sessionId, "state"] as const,
};

export function useCreateConversationSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { userId: string; deviceId: string }) => {
      const { data } = await gatewayFetch("/v1/communication/sessions", sessionResponseSchema, {
        method: "POST",
        body: { user_id: input.userId, channel: "text", device_id: input.deviceId },
      });
      return data;
    },
    onSuccess: (session) => {
      queryClient.setQueryData(conversationKeys.session, session);
      queryClient.setQueryData(conversationKeys.state(session.session_id), session.state);
      // Seed an empty transcript so the panel distinguishes "a session
      // exists and nothing has been said" from "no session yet".
      queryClient.setQueryData<TranscriptEntry[]>(
        conversationKeys.transcript(session.session_id),
        (existing) => existing ?? [],
      );
    },
  });
}

/**
 * Send a turn.
 *
 * **No optimistic update.** TDD 4A §5.2 property 2: nothing that affects
 * shared cognitive state may be rendered before the system holds it. The
 * engine answers `202 Accepted` with a `turn_id`; the turn appears in the
 * transcript when `communication.turn.received` arrives over the socket,
 * which is the system confirming it, not this client assuming it.
 */
export function useSendMessage(sessionId: string | null) {
  return useMutation({
    mutationFn: async (content: string) => {
      if (!sessionId) {
        throw new Error("No conversation session is open.");
      }
      const { data } = await gatewayFetch(
        `/v1/communication/sessions/${sessionId}/messages`,
        sendMessageResponseSchema,
        { method: "POST", body: { content } },
      );
      return data;
    },
  });
}

/**
 * The live transcript.
 *
 * Reads are pushed, never polled (TDD 4A §5.2 property 1), so this query has
 * no fetcher at all -- `realtime/` writes into the same cache key.
 *
 * Known 4A limitation, stated rather than hidden: a reload starts the
 * transcript empty. `communication-engine` exposes no endpoint that returns
 * a session's turns (`GET .../context` returns a `turn_count`, not the
 * turns), so there is nothing to hydrate from. Adding one is engine work,
 * and 4A changes no engine API beyond the event it had to add.
 */
export function useTranscript(sessionId: string | null) {
  return useQuery<TranscriptEntry[]>({
    queryKey: conversationKeys.transcript(sessionId ?? "none"),
    // `skipToken` states the invariant rather than merely producing it:
    // this entry has no fetcher at all, because `realtime/` is its only
    // writer. `enabled: false` would read as "not fetching *yet*".
    queryFn: skipToken,
    initialData: [],
  });
}

export function useConversationState(sessionId: string | null) {
  return useQuery<string | null>({
    queryKey: conversationKeys.state(sessionId ?? "none"),
    queryFn: skipToken,
    initialData: null,
  });
}
