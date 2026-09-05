import { skipToken, useQuery } from "@tanstack/react-query";

import type { EventFrame } from "../realtime/protocol";

/**
 * Every frame the client actually received, in arrival order.
 *
 * The one panel with no data source of its own: it renders the socket. That
 * makes it the honest answer to "is anything flowing?", and the first place
 * to look when another panel is empty -- an empty transcript with
 * `communication.turn.received` visible here is a rendering bug, and an
 * empty transcript with nothing here is a transport one.
 *
 * **Arrival order, not event order.** Every other reducer in this client
 * sorts by the event's own timestamp, because a reply rendered above its
 * question is a wrong transcript. Here the opposite is true: the question
 * this panel answers is what reached the browser and when, so re-ordering
 * by `generated_at` would hide exactly the out-of-order delivery worth
 * seeing. `receivedAt` is therefore the browser's clock, and is labelled as
 * such rather than presented as when the event happened.
 */

export type ObservedEvent = {
  /** Monotonic within a session; frames carry no id of their own on the wire. */
  seq: number;
  topic: string;
  correlationId: string;
  /** The event's own time, from the envelope. */
  generatedAt: string;
  /** This browser's clock when the frame arrived. Not the same thing. */
  receivedAt: string;
  confidence: number | null;
  data: Record<string, unknown>;
};

export const eventKeys = { feed: ["events", "feed"] as const };

/**
 * Bounded on purpose. A session left open overnight receives a heartbeat
 * every five seconds; unbounded, this list is a memory leak with a UI.
 */
export const EVENT_FEED_LIMIT = 200;

export function useEventFeed() {
  return useQuery<ObservedEvent[]>({
    queryKey: eventKeys.feed,
    queryFn: skipToken,
    initialData: [],
  });
}

export function observedFromFrame(
  frame: EventFrame,
  seq: number,
  receivedAt: string,
): ObservedEvent {
  return {
    seq,
    topic: frame.topic,
    correlationId: frame.meta.correlation_id,
    generatedAt: frame.meta.generated_at,
    receivedAt,
    confidence: typeof frame.meta.confidence === "number" ? frame.meta.confidence : null,
    data: frame.data,
  };
}

export function reduceEventFeed(
  existing: ObservedEvent[] | undefined,
  entry: ObservedEvent,
): ObservedEvent[] {
  // Newest first for reading, capped for memory.
  return [entry, ...(existing ?? [])].slice(0, EVENT_FEED_LIMIT);
}
