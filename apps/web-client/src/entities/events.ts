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

/**
 * The two dimensions a raw bus frame is identified by.
 *
 * Master scope §5 calls this panel a "filterable raw bus inspector" without
 * enumerating the dimensions, so they are taken from what a frame actually
 * is rather than invented: the **subject** it was published on, and the
 * **correlation id** that threads one interaction across every engine that
 * touched it. Those are the two questions an inspector gets asked -- "show
 * me the approval events" and "show me everything from that one request" --
 * and doc 11 §4 puts `correlation_id` in `meta` precisely so the second one
 * is answerable.
 *
 * Nothing filters on payload contents or on time. Both were considered and
 * rejected: neither is a property of the envelope, and a filter that reaches
 * into `data` would couple this panel to payload shapes it deliberately
 * does not parse.
 */
export type EventFilters = {
  /** Case-insensitive substring of the subject. Empty means no constraint. */
  topic: string;
  /** Case-insensitive substring of the correlation id. Empty means no constraint. */
  correlationId: string;
};

export const EMPTY_EVENT_FILTERS: EventFilters = { topic: "", correlationId: "" };

/**
 * Applied at **render**, never at ingest.
 *
 * The feed itself always records every frame that arrived, because the
 * question this panel exists to answer is what reached the browser. Filtering
 * on the way in would delete the evidence: a frame dropped while a filter was
 * set would still be missing after the filter was cleared, and "nothing is
 * arriving" would become indistinguishable from "nothing matches". So the
 * reducer stays unfiltered and realtime keeps writing through a filter the
 * same way it does without one.
 */
export function filterEvents(events: ObservedEvent[], filters: EventFilters): ObservedEvent[] {
  const topic = filters.topic.trim().toLowerCase();
  const correlationId = filters.correlationId.trim().toLowerCase();
  if (!topic && !correlationId) return events;
  return events.filter(
    (event) =>
      (!topic || event.topic.toLowerCase().includes(topic)) &&
      (!correlationId || event.correlationId.toLowerCase().includes(correlationId)),
  );
}
